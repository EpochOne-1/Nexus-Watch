import pandas as pd
import yfinance as yf
from neo4j import GraphDatabase

class RiskEngine:
    def __init__(self, driver):
        """
        Initialize with a Neo4j Driver instance.
        """
        self.driver = driver

    def check_market_volatility(self, ticker):
        """
        Real-time check: Has the stock price dropped >2% in the last 5 days?
        Used to filter 'False Alarms' (Noise) from 'True Signals' (Market Moving).
        """
        try:
            # Add .AX for Australian listings
            stock = yf.Ticker(f"{ticker}.AX")
            hist = stock.history(period="5d")

            if len(hist) < 2: 
                return "Unknown (No Data)"

            start_price = hist['Close'].iloc[0]
            end_price = hist['Close'].iloc[-1]
            pct_change = ((end_price - start_price) / start_price) * 100

            if pct_change < -2.0:
                return f"📉 CONFIRMED (Down {pct_change:.1f}%)"
            elif pct_change > 0:
                return f"Uncorrelated (Up {pct_change:.1f}%)"
            else:
                return "Stable"
        except Exception:
            return "Unknown"

    def get_risk_dashboard_data(self):
        """
        Runs the Master Cypher Query to aggregate all 3 Risk Vectors:
        1. Direct News (AI Surveillance)
        2. Governance Contagion (Director Interlocks)
        3. Supply Chain Concentration (Government Contracts)
        
        Returns: A Pandas DataFrame ready for Streamlit.
        """
        query = """
        MATCH (c:Company)
        
        // =========================================================
        // VECTOR 1: DIRECT NEWS RISK (AI Surveillance)
        // =========================================================
        OPTIONAL MATCH (c)-[:HAS_RISK_EVENT]->(n:NewsEvent)
        WITH c, count(n) * 10 AS direct_score, collect(distinct n.title) as news_titles

        // =========================================================
        // VECTOR 2: GOVERNANCE CONTAGION (The 'Director' Graph)
        // =========================================================
        // Find directors connecting this company to an 'infected' company
        OPTIONAL MATCH (c)<-[:DIRECTOR_OF]-(p:Person)-[:DIRECTOR_OF]->(infected:Company)
        WHERE (infected)-[:HAS_RISK_EVENT]->() AND c <> infected

        WITH c, direct_score, news_titles,
             collect(DISTINCT p.name + ' via ' + infected.ticker) as contagion_details,
             count(DISTINCT infected) * 5 as contagion_score

        // =========================================================
        // VECTOR 3: GOVERNMENT REVENUE RISK (The 'Supply Chain' Graph)
        // =========================================================
        // Find if Company is linked to a Supplier that has Govt Contracts
        OPTIONAL MATCH (c)-[:IS_ALSO]->(s:Supplier)-[r:SUPPLIES_TO]->(g:GovernmentAgency)
        
        WITH c, direct_score, news_titles, contagion_details, contagion_score,
             sum(r.value) as total_contract_val,
             count(distinct g) as agency_count,
             collect(distinct g.name) as agency_names

        // --- SCORING LOGIC (Nuanced for Concentration vs Systemic) ---
        WITH c, direct_score, news_titles, contagion_details, contagion_score,
             total_contract_val, agency_names, agency_count,
             CASE 
                // Case A: High Value (> $50M) & Only 1 Client -> HIGH POLICY SENSITIVITY
                // (e.g. Sigma Healthcare relying only on Dept of Health)
                WHEN total_contract_val > 50000000 AND agency_count = 1 THEN 15 
                
                // Case B: High Value (> $50M) & Multiple Clients -> SYSTEMIC IMPORTANCE
                // (e.g. Data#3 supplying everyone)
                WHEN total_contract_val > 50000000 AND agency_count > 1 THEN 5 
                
                // Case C: Medium Value (> $10M) & 1 Client -> MODERATE CONCENTRATION
                WHEN total_contract_val > 10000000 AND agency_count = 1 THEN 8
                
                ELSE 0 
             END as supply_score

        // =========================================================
        // FINAL AGGREGATION
        // =========================================================
        WITH c, direct_score, contagion_score, supply_score, 
             (direct_score + contagion_score + supply_score) as total_score,
             news_titles, contagion_details, agency_names, total_contract_val, agency_count

        // Filter out safe companies (Score 0)
        WHERE total_score > 0
        
        RETURN c.ticker as Ticker, c.name as Name,
               total_score as Score,
               direct_score as Direct_Risk,
               contagion_score as Contagion_Risk,
               supply_score as Supply_Risk, 
               news_titles as News_Context,
               contagion_details as Contagion_Context,
               agency_names as Govt_Clients,
               agency_count as Client_Count,
               total_contract_val as Contract_Value
        ORDER BY total_score DESC
        """

        with self.driver.session() as session:
            result = session.run(query)
            # Convert Neo4j result to a Python list of dictionaries
            data = [record.data() for record in result]
            
            # Convert to Pandas DataFrame for easy display in Streamlit
            if not data:
                return pd.DataFrame() # Return empty if no risks found
            
            return pd.DataFrame(data)