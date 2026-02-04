import pandas as pd
import yfinance as yf
from neo4j import GraphDatabase

class RiskEngine:
    def __init__(self, driver):
        self.driver = driver

    def get_risk_dashboard_data(self):
        """
        Runs the Master Cypher Query to aggregate all 4 Risk Vectors:
        1. Direct News (AI Surveillance)
        2. Governance Contagion (Director Interlocks)
        3. Supply Chain Concentration (Government Contracts)
        4. Climate & Sector Exposure (Annual Report Scraping) - NEW!
        """
        query = """
        MATCH (c:Company)
        
        // =========================================================
        // VECTOR 1: CLIMATE & SECTOR RISKS (NEW DATA)
        // =========================================================
        // 1a. Sector Exposure (e.g. Lending to Coal)
        OPTIONAL MATCH (c)-[r1:EXPOSED_TO_SECTOR]->(s:Sector)
        WITH c, collect(DISTINCT s.name) as sectors, count(s) as sector_count

        // 1b. Risk Disclosures (e.g. 'Physical Risk')
        OPTIONAL MATCH (c)-[:ACKNOWLEDGES_RISK]->(rd:RiskDisclosure)
        WITH c, sectors, sector_count, collect(DISTINCT rd.type) as risks, count(rd) as risk_count

        // Calculate Climate Score: 10 points per sector link, 5 per risk disclosure
        WITH c, sectors, risks, (sector_count * 10) + (risk_count * 5) as climate_score

        // =========================================================
        // VECTOR 2: DIRECT NEWS RISK
        // =========================================================
        OPTIONAL MATCH (c)-[:HAS_RISK_EVENT]->(n:NewsEvent)
        WITH c, sectors, risks, climate_score, count(n) * 10 AS direct_score, collect(distinct n.title) as news_titles

        // =========================================================
        // VECTOR 3: GOVERNANCE CONTAGION
        // =========================================================
        OPTIONAL MATCH (c)<-[:DIRECTOR_OF]-(p:Person)-[:DIRECTOR_OF]->(infected:Company)
        WHERE (infected)-[:HAS_RISK_EVENT]->() AND c <> infected
        WITH c, sectors, risks, climate_score, direct_score, news_titles,
             collect(DISTINCT p.name + ' via ' + infected.ticker) as contagion_details,
             count(DISTINCT infected) * 5 as contagion_score

        // =========================================================
        // VECTOR 4: GOVERNMENT REVENUE RISK
        // =========================================================
        OPTIONAL MATCH (c)-[:IS_ALSO]->(s:Supplier)-[r:SUPPLIES_TO]->(g:GovernmentAgency)
        WITH c, sectors, risks, climate_score, direct_score, news_titles, contagion_details, contagion_score,
             sum(r.value) as total_contract_val,
             count(distinct g) as agency_count,
             collect(distinct g.name) as agency_names

        // Scoring Logic for Supply Chain
        WITH c, sectors, risks, climate_score, direct_score, news_titles, contagion_details, contagion_score,
             total_contract_val, agency_names, agency_count,
             CASE 
                WHEN total_contract_val > 50000000 AND agency_count = 1 THEN 15 
                WHEN total_contract_val > 50000000 AND agency_count > 1 THEN 5 
                WHEN total_contract_val > 10000000 AND agency_count = 1 THEN 8
                ELSE 0 
             END as supply_score

        // =========================================================
        // FINAL AGGREGATION
        // =========================================================
        WITH c, direct_score, contagion_score, supply_score, climate_score,
             (direct_score + contagion_score + supply_score + climate_score) as total_score,
             news_titles, contagion_details, agency_names, total_contract_val, agency_count, sectors, risks

        WHERE total_score > 0
        
        RETURN c.ticker as Ticker, c.name as Name,
               total_score as Score,
               direct_score as Direct_Risk,
               contagion_score as Contagion_Risk,
               supply_score as Supply_Risk, 
               climate_score as Climate_Risk,
               news_titles as News_Context,
               contagion_details as Contagion_Context,
               agency_names as Govt_Clients,
               total_contract_val as Contract_Value,
               sectors as Exposed_Sectors,
               risks as Disclosed_Risks
        ORDER BY total_score DESC
        """

        with self.driver.session() as session:
            result = session.run(query)
            data = [record.data() for record in result]
            if not data:
                return pd.DataFrame()
            return pd.DataFrame(data)
