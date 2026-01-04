import streamlit as st
import pandas as pd
from neo4j import GraphDatabase
from risk_engine import RiskEngine
from streamlit_agraph import agraph, Node, Edge, Config

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Nexus-Watch | Systemic Risk Engine",
    page_icon="🛑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .metric-card {
        background-color: #262730;
        border-left: 5px solid #FF4B4B;
        padding: 15px;
        border-radius: 5px;
    }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #FF4B4B; }
    h1, h2, h3 { color: #FAFAFA !important; }
    /* Custom Legend Styling in Sidebar */
    .legend-row {
        display: flex; 
        justify-content: space-between; 
        padding: 5px 0; 
        border-bottom: 1px solid #444;
        font-size: 13px;
    }
    .legend-ticker { font-weight: bold; color: #FF4B4B; }
    .legend-name { color: #ddd; text-align: right; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
@st.cache_resource
def get_driver():
    # REPLACE THESE WITH YOUR SECRETS OR LOCAL CREDENTIALS
    # For local testing, you can swap st.secrets with raw strings if needed
    try:
        URI = st.secrets["NEO4J_URI"]
        USER = st.secrets["NEO4J_USER"]
        PASSWORD = st.secrets["NEO4J_PASSWORD"]
        return GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    except:
        st.error("Secrets not found. If running locally, ensure .streamlit/secrets.toml exists.")
        return None

def get_risk_data(driver):
    # Use the RiskEngine class we built to get the raw dataframe
    engine = RiskEngine(driver)
    return engine.get_risk_dashboard_data()

# --- MAIN APP ---
try:
    driver = get_driver()
    if not driver:
        st.stop()

    df = get_risk_data(driver)

    # SIDEBAR
    st.sidebar.title("🛑 Nexus-Watch")
    st.sidebar.markdown("### **Systemic Risk Monitor**")
    
    # 1. Filters
    st.sidebar.markdown("---")
    min_score = st.sidebar.slider("Minimum Risk Score", 0, 50, 5)
    
    if not df.empty:
        filtered_df = df[df['Score'] >= min_score]
    else:
        filtered_df = pd.DataFrame()

    # 2. COMPANY LEGEND (New Feature!)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📖 Company Reference")
    st.sidebar.info("Full names of companies currently visible in the dashboard.")
    
    if not filtered_df.empty:
        # Use an Expander so it doesn't clutter the view unless asked
        with st.sidebar.expander("Show Full Company Names", expanded=True):
            # Sort by Score so the most risky ones are at the top
            legend_df = filtered_df[['Ticker', 'Name', 'Score']].sort_values(by='Score', ascending=False)
            
            for index, row in legend_df.iterrows():
                st.markdown(
                    f"""
                    <div class="legend-row">
                        <span class="legend-ticker">{row['Ticker']}</span>
                        <span class="legend-name">{row['Name'][:25]}...</span> 
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                # Note: truncated name to 25 chars to fit sidebar

    # DASHBOARD HEADER
    st.title("Nexus-Watch: Live Intelligence")
    st.markdown(f"**Status:** Scanning {len(filtered_df)} high-risk entities.")

    # METRICS ROW
    if not filtered_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🚨 Total At Risk", len(filtered_df))
        with col2:
            # Human readable millions
            total_val = filtered_df['Contract_Value'].sum()
            st.metric("🏛️ Govt Exposure", f"${total_val:,.0f}")
        with col3:
            critical_cnt = len(filtered_df[filtered_df['Supply_Risk'] >= 15])
            st.metric("⚠️ Single Points of Failure", critical_cnt)
        with col4:
            news_cnt = len(filtered_df[filtered_df['Direct_Risk'] > 0])
            st.metric("📰 Active News Alerts", news_cnt)

    st.markdown("---")

    # --- TABS FOR LAYOUT ---
    tab_gov, tab_supply, tab_graph = st.tabs(["🤝 Governance Risks", "🏛️ Supply Chain Risks", "🕸️ Interactive Graph"])

# === TAB 1: GOVERNANCE & REPUTATION ===
    with tab_gov:
        # --- SECTION 1: HIDDEN CONTAGION ---
        st.subheader("Boardroom Contagion (The 'Old Boys Club')")
        st.caption("⚠️ Companies flagged because their Directors sit on the boards of other 'Infected' firms.")
        
        # Filter for Governance risks
        gov_df = filtered_df[filtered_df['Contagion_Risk'] > 0].copy()
        
        if not gov_df.empty:
            st.dataframe(
                gov_df[['Ticker', 'Name', 'Score', 'Contagion_Context']],
                use_container_width=True,
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Risk Score", format="%d", min_value=0, max_value=50
                    ),
                    "Contagion_Context": st.column_config.ListColumn(
                        "Shared Director Links (Source of Risk)"
                    )
                },
                hide_index=True
            )
        else:
            st.info("✅ No Boardroom Contagion detected in the current filter.")

        st.markdown("---") # Visual Divider

        # --- SECTION 2: DIRECT NEWS THREATS ---
        st.subheader("🚨 Active Reputational Threats (Direct News)")
        st.caption("🔥 Companies currently mentioned in negative news stories (Fraud, Lawsuits, Investigations).")

        # Filter for Direct News risks
        news_df = filtered_df[filtered_df['Direct_Risk'] > 0].copy()

        if not news_df.empty:
            # Clean up the list to show the top headline
            news_df['Latest Headline'] = news_df['News_Context'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else "Unknown")
            
            st.dataframe(
                news_df[['Ticker', 'Name', 'Score', 'Latest Headline']],
                use_container_width=True,
                column_config={
                    "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                    "Score": st.column_config.NumberColumn("Severity Score"),
                    "Latest Headline": st.column_config.TextColumn(
                        "Latest AI-Detected Headline",
                        width="large"
                    )
                },
                hide_index=True
            )
        else:
            st.success("✅ No Active News Threats detected in the current filter.")

    # === TAB 2: SUPPLY CHAIN (GOVERNMENT) ===
    with tab_supply:
        st.subheader("Government Revenue Vulnerability")
        st.caption("Companies with high dependency on federal contracts. High Risk = Un-hedged revenue.")
        
        if not filtered_df.empty:
            # Filter for Supply Chain risks
            supply_df = filtered_df[filtered_df['Supply_Risk'] > 0].copy()
            
            # Create a "Status" column for readability
            def get_status(row):
                if row['Supply_Risk'] >= 15: return "🔴 CRITICAL (Single Client)"
                if row['Supply_Risk'] >= 5: return "🟠 SYSTEMIC (High Value)"
                return "🟡 MODERATE"

            supply_df['Status'] = supply_df.apply(get_status, axis=1)

            # Select columns
            supply_display = supply_df[['Ticker', 'Name', 'Status', 'Contract_Value', 'Govt_Clients']]

            st.dataframe(
                supply_display,
                use_container_width=True,
                column_config={
                    "Contract_Value": st.column_config.NumberColumn(
                        "Total Locked Revenue",
                        format="$%d",  # <--- THIS FIXES THE NUMBER FORMATTING
                    ),
                    "Govt_Clients": st.column_config.ListColumn(
                        "Key Government Agencies"
                    ),
                    "Status": st.column_config.TextColumn(
                        "Risk Classification"
                    )
                },
                hide_index=True
            )
        else:
            st.success("No Supply Chain Risks detected.")


# === TAB 3: THE INTERACTIVE GRAPH ===
# === TAB 3: THE INTERACTIVE GRAPH ===
    with tab_graph:
        st.subheader("🕸️ Network Contagion Map")
        
        # 1. Custom Legend
        st.markdown("""
        <div style="display: flex; gap: 15px; margin-bottom: 10px; justify-content: center; flex-wrap: wrap;">
            <div style="display: flex; align-items: center;">
                <div style="width: 12px; height: 12px; background-color: #FF4B4B; border-radius: 50%; margin-right: 5px;"></div>
                <span style="color: #ddd; font-size: 12px;">Target Company</span>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 12px; height: 12px; background-color: #0084ff; margin-right: 5px;"></div>
                <span style="color: #ddd; font-size: 12px;">Govt Revenue</span>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 12px; height: 12px; background-color: #9b59b6; transform: rotate(45deg); margin-right: 5px;"></div>
                <span style="color: #ddd; font-size: 12px;">Infected Source</span>
            </div>
             <div style="display: flex; align-items: center; border-left: 1px solid #555; padding-left: 10px;">
                <span style="color: #888; font-size: 12px;"><i>*Scroll to Zoom. Drag to move.</i></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if not filtered_df.empty:
            nodes = []
            edges = []
            added_node_ids = set()

            for index, row in filtered_df.head(50).iterrows():
                # Node Generation (Same as before)
                if row['Ticker'] not in added_node_ids:
                    nodes.append(Node(id=row['Ticker'], label=row['Ticker'], title=f"Name: {row['Name']}\nRisk Score: {row['Score']}", size=25, color="#FF4B4B", font={'color': 'white'}))
                    added_node_ids.add(row['Ticker'])

                if row['Supply_Risk'] > 0:
                    if "GOVT" not in added_node_ids:
                        nodes.append(Node(id="GOVT", label="GOVT CONTRACTS", title="Federal Government Revenue", size=35, color="#0084ff", symbolType="square", font={'color': 'white'}))
                        added_node_ids.add("GOVT")
                    
                    val_millions = row['Contract_Value'] / 1000000
                    width = 4 if row['Contract_Value'] > 50000000 else 1.5
                    edges.append(Edge(source=row['Ticker'], target="GOVT", label=f"${val_millions:.0f}M", color="#5e8bfa", strokeWidth=width))

                if row['Contagion_Risk'] > 0:
                    if "INFECTED" not in added_node_ids:
                        nodes.append(Node(id="INFECTED", label="RISK VECTOR", size=20, color="#9b59b6", symbolType="diamond", font={'color': 'white'}))
                        added_node_ids.add("INFECTED")
                    edges.append(Edge(source=row['Ticker'], target="INFECTED", label="Director Link", color="#d2b4de"))

            # --- CONFIGURATION FIX (CENTERED & ZOOMED OUT) ---
            config = Config(
                width="100%", 
                height=600, 
                directed=True, 
                nodeHighlightBehavior=True, 
                highlightColor="#F7A7A6",
                collapsible=False,
                
                # 1. AUTO-FIT: This is the command to fit everything in the viewport
                fit=True,
                
                # 2. PHYSICS TUNING FOR STABILITY
                physicsOptions={
                    "solver": "barnesHut",
                    "barnesHut": {
                        # Moderate repulsion: Pushes nodes apart so they don't overlap, but doesn't blast them off-screen
                        "gravitationalConstant": -2000, 
                        
                        # HIGH CENTRAL GRAVITY (0.55): This is the fix. 
                        # It acts like a strong magnet in the center of the screen, preventing the "Blank Screen" issue.
                        "centralGravity": 0.55, 
                        
                        "springLength": 90, 
                        "springConstant": 0.04,
                        "damping": 0.09,
                        "avoidOverlap": 0.5
                    },
                    # 3. STABILIZATION: Pre-simulates the layout so it loads "settled"
                    "stabilization": {
                        "enabled": True,
                        "iterations": 1000,
                        "fit": True
                    }
                }
            )
            
            agraph(nodes=nodes, edges=edges, config=config)

            
except Exception as e:
    st.error(f"Application Error: {e}")