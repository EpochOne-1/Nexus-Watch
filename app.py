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
    div[data-testid="stMetricValue"] { font-size: 24px; color: #FF4B4B; }
    h1, h2, h3 { color: #FAFAFA !important; }
    .legend-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #444; font-size: 13px; }
    .legend-ticker { font-weight: bold; color: #FF4B4B; }
    .legend-name { color: #ddd; text-align: right; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE CONNECTION ---
@st.cache_resource
def get_driver():
    try:
        URI = st.secrets["NEO4J_URI"]
        USER = st.secrets["NEO4J_USER"]
        PASSWORD = st.secrets["NEO4J_PASSWORD"]
        return GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def get_risk_data(driver):
    engine = RiskEngine(driver)
    return engine.get_risk_dashboard_data()

# --- MAIN APP ---
driver = get_driver()
if not driver:
    st.stop()

df = get_risk_data(driver)

# SIDEBAR
st.sidebar.title("🛑 Nexus-Watch")
st.sidebar.markdown("### **Systemic Risk Monitor**")

# 1. Filters
min_score = st.sidebar.slider("Minimum Risk Score", 0, 50, 5)

if not df.empty:
    filtered_df = df[df['Score'] >= min_score]
else:
    filtered_df = pd.DataFrame()
    st.warning("No data found in database.")
    st.stop()

# 2. LEGEND
with st.sidebar.expander("Show Full Company Names", expanded=False):
    legend_df = filtered_df[['Ticker', 'Name', 'Score']].sort_values(by='Score', ascending=False)
    for index, row in legend_df.iterrows():
        st.markdown(f"""<div class="legend-row"><span class="legend-ticker">{row['Ticker']}</span><span class="legend-name">{row['Name'][:25]}...</span></div>""", unsafe_allow_html=True)

# DASHBOARD HEADER
st.title("Nexus-Watch: Live Intelligence")
st.markdown(f"**Status:** Scanning {len(filtered_df)} high-risk entities.")

# METRICS ROW
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🚨 Total At Risk", len(filtered_df))
with col2:
    # Calculate Climate Risk Leaders
    climate_risky = len(filtered_df[filtered_df['Climate_Risk'] > 0])
    st.metric("🌍 Climate Exposed", climate_risky)
with col3:
    total_val = filtered_df['Contract_Value'].sum()
    st.metric("🏛️ Govt Exposure", f"${total_val/1000000:,.1f}M")
with col4:
    news_cnt = len(filtered_df[filtered_df['Direct_Risk'] > 0])
    st.metric("📰 Active News Alerts", news_cnt)

st.markdown("---")

# --- TABS ---
tab_climate, tab_gov, tab_supply, tab_graph = st.tabs(["🌍 Climate & Sector Risk", "🤝 Governance", "🏛️ Supply Chain", "🕸️ Network Graph"])

# === TAB 1: CLIMATE (NEW!) ===
with tab_climate:
    st.subheader("Transition Risk & Sector Exposure")
    st.caption("Auto-extracted from 2025 Annual Reports. Identifies 'Dirty Sector' links and Physical Risk disclosures.")
    
    climate_df = filtered_df[filtered_df['Climate_Risk'] > 0].copy()
    
    if not climate_df.empty:
        # Format columns for display
        climate_df['Primary Risks'] = climate_df['Disclosed_Risks'].apply(lambda x: ", ".join(x[:3]) if x else "None")
        climate_df['Dirty Sectors'] = climate_df['Exposed_Sectors'].apply(lambda x: ", ".join(x[:3]) if x else "None")
        
        st.dataframe(
            climate_df[['Ticker', 'Name', 'Climate_Risk', 'Dirty Sectors', 'Primary Risks']],
            use_container_width=True,
            column_config={
                "Climate_Risk": st.column_config.ProgressColumn("Risk Score", format="%d", min_value=0, max_value=100),
                "Dirty Sectors": st.column_config.TextColumn("⚠️ Sector Exposure"),
                "Primary Risks": st.column_config.TextColumn("📝 Disclosed Risks")
            },
            hide_index=True
        )
    else:
        st.success("No significant Climate Risks detected.")

# === TAB 2: GOVERNANCE ===
with tab_gov:
    st.subheader("Boardroom Contagion")
    gov_df = filtered_df[filtered_df['Contagion_Risk'] > 0].copy()
    if not gov_df.empty:
        st.dataframe(
            gov_df[['Ticker', 'Name', 'Contagion_Risk', 'Contagion_Context']],
            use_container_width=True,
            column_config={
                "Contagion_Risk": st.column_config.NumberColumn("Score"),
                "Contagion_Context": st.column_config.ListColumn("Director Links")
            },
            hide_index=True
        )
    else:
        st.info("No Boardroom Contagion detected.")

# === TAB 3: SUPPLY CHAIN ===
with tab_supply:
    st.subheader("Government Revenue Vulnerability")
    supply_df = filtered_df[filtered_df['Supply_Risk'] > 0].copy()
    if not supply_df.empty:
        supply_df['Status'] = supply_df['Supply_Risk'].apply(lambda x: "🔴 CRITICAL" if x >= 15 else "🟠 SYSTEMIC" if x >= 10 else "🟡 MODERATE")
        
        st.dataframe(
            supply_df[['Ticker', 'Status', 'Contract_Value', 'Govt_Clients']],
            use_container_width=True,
            column_config={
                "Contract_Value": st.column_config.NumberColumn("Revenue", format="$%d"),
                "Govt_Clients": st.column_config.ListColumn("Agencies")
            },
            hide_index=True
        )

# === TAB 4: GRAPH ===
with tab_graph:
    st.subheader("🕸️ Network Contagion Map")
    
    # Legend HTML
    st.markdown("""
    <div style="display: flex; gap: 15px; justify-content: center; margin-bottom: 10px;">
        <span style="color:#FF4B4B">● Company</span>
        <span style="color:#2ecc71">● Sector (Coal/Mining)</span>
        <span style="color:#0084ff">■ Govt Contract</span>
    </div>""", unsafe_allow_html=True)

    nodes = []
    edges = []
    added_ids = set()

    for _, row in filtered_df.head(40).iterrows():
        # Company Node
        if row['Ticker'] not in added_ids:
            nodes.append(Node(id=row['Ticker'], label=row['Ticker'], size=25, color="#FF4B4B", title=row['Name']))
            added_ids.add(row['Ticker'])

        # 1. Supply Chain Nodes
        if row['Contract_Value'] > 0:
            if "GOVT" not in added_ids:
                nodes.append(Node(id="GOVT", label="GOVT", size=30, color="#0084ff", symbolType="square"))
                added_ids.add("GOVT")
            edges.append(Edge(source=row['Ticker'], target="GOVT", label=f"${row['Contract_Value']/1000000:.0f}M"))

        # 2. Climate Sector Nodes
        if row['Exposed_Sectors']:
            for sector in row['Exposed_Sectors']:
                # Clean up sector name
                s_id = f"SECTOR_{sector}"
                if s_id not in added_ids:
                    # Color Dirty Sectors (Coal, Mining) differently if you want, or just generic green
                    nodes.append(Node(id=s_id, label=sector, size=20, color="#2ecc71", symbolType="diamond"))
                    added_ids.add(s_id)
                edges.append(Edge(source=row['Ticker'], target=s_id, color="#2ecc71"))

    config = Config(width="100%", height=600, directed=True, nodeHighlightBehavior=True, highlightColor="#F7A7A6",
                    physicsOptions={"solver": "barnesHut", "barnesHut": {"gravitationalConstant": -2000, "centralGravity": 0.55, "springLength": 90}})
    
    agraph(nodes=nodes, edges=edges, config=config)
    

