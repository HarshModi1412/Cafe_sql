import os
import time
import pandas as pd
import streamlit as st
import pyodbc

# === Module Imports ===
from modules.rfm import calculate_rfm, get_campaign_targets, generate_personal_offer
from modules.profiler import generate_customer_profile
from modules.customer_journey import (
    map_customer_journey_and_affinity,
    generate_behavioral_recommendation_with_impact
)
from modules.discount import generate_discount_insights, assign_offer_codes
from modules.personalization import compute_customer_preferences
from modules.sales_analytics import (
    render_sales_analytics,
    render_subcategory_trends,
    generate_sales_insights
)
from modules.smart_insights import generate_dynamic_insights
import BA
import KPI_analyst
import chatbot2

# =========================================================
# REMOTE SQL SERVER CONFIG (GearHost)
#   Tip: set these as environment variables in production.
# =========================================================
SERVER   = os.getenv("DB_SERVER",   "den1.mssql7.gear.host")
DATABASE = os.getenv("DB_NAME",     "billinghistory")
USERNAME = os.getenv("DB_USER",     "billinghistory")
PASSWORD = os.getenv("DB_PASSWORD", "Pk0Z-57_avQe")   # prefer env var in prod

# Optional: limit rows to prevent huge transfers on first load
ROW_LIMIT = int(os.getenv("ROW_LIMIT", "500000"))  # adjust or set to 0 for no limit

# =========================================================
# DB CONNECTION (with encryption, login timeout, retries)
# =========================================================
def get_connection(max_retries: int = 2, sleep_between: int = 2):
    """
    Create and return a SQL Server connection using pyodbc with sane defaults:
    - Encrypt=yes (remote hosts often require TLS)
    - TrustServerCertificate=no (safer; change to yes if your host requires it)
    - Login Timeout (faster fail when unreachable)
    - Query timeout applied on the connection
    - Light retry logic for transient network hiccups
    """
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={USERNAME};"
        f"PWD={PASSWORD};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=yes;"
        f"MultipleActiveResultSets=yes;"
        f"Login Timeout=15;"
    )

    last_err = None
    for attempt in range(1, max_retries + 2):  # e.g., 1 try + 2 retries
        try:
            conn = pyodbc.connect(conn_str, timeout=30)  # connection-establish timeout
            # Apply statement/query timeout to the connection (seconds)
            # (pyodbc docs: connection and cursor both have .timeout)
            conn.timeout = 60
            return conn
        except Exception as e:
            last_err = e
            if attempt <= max_retries:
                time.sleep(sleep_between)
            else:
                break

    st.error(f"❌ Database connection failed after retries: {last_err}")
    return None

# =========================================================
# HELPERS: table existence + resolution + safe select
# =========================================================
def table_exists(conn, table_name: str) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = ?
            """, (table_name,))
            return cur.fetchone()[0] > 0
    except Exception:
        return False

def resolve_table_name(preferred: list[str]) -> str | None:
    """
    Try possible table names in order and return the first that exists.
    """
    conn = get_connection()
    if not conn:
        return None
    try:
        for t in preferred:
            if table_exists(conn, t):
                return t
        return None
    finally:
        conn.close()

@st.cache_data(ttl=600, show_spinner=False)
def read_table(table_name: str, limit: int | None = ROW_LIMIT) -> pd.DataFrame | None:
    """
    Cached table reader. Adds TOP limit if provided.
    Returns None if table missing or query fails.
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        if not table_exists(conn, table_name):
            return None

        top_clause = f"TOP {limit} " if (isinstance(limit, int) and limit > 0) else ""
        sql = f"SELECT {top_clause}* FROM [{table_name}]"
        df = pd.read_sql_query(sql, conn)
        return df
    except Exception as e:
        st.error(f"❌ Error reading table '{table_name}': {e}")
        return None
    finally:
        conn.close()

# =========================================================
# STREAMLIT SETTINGS
# =========================================================
st.set_page_config(
    page_title="Cafe_X Dashboard",
    page_icon="📊",
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": None}
)
st.markdown("""
    <style>
    #MainMenu, footer, header {display: none;}
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    </style>
""", unsafe_allow_html=True)

# Branding
st.markdown("""
<h1 style='text-align: left; color: #FFFFFF; font-size: 3em; margin: 0;'>Cafe_X</h1>
<hr style='margin: 0.5rem auto 1rem auto; border: 1px solid #ccc; width: 100%;' />
""", unsafe_allow_html=True)

# =========================================================
# TABLE NAME MAPPINGS (with fallback for Transactions → billing)
# =========================================================
# Try "transactions" first, then "billing" (you mentioned your table is named 'billing')
CANDIDATES = {
    "Transactions": ["transactions", "billing"],
    "Customers":    ["customers"],
    "Products":     ["products"],
    "Promotions":   ["promotions"],
}

resolved_names = {}
for logical, candidates in CANDIDATES.items():
    tname = resolve_table_name(candidates)
    resolved_names[logical] = tname

# Load data (cached)
st.session_state['txns_df'] = read_table(resolved_names["Transactions"])
st.session_state['cust_df'] = read_table(resolved_names["Customers"])
st.session_state['prod_df'] = read_table(resolved_names["Products"])
st.session_state['promo_df'] = read_table(resolved_names["Promotions"])

txns_df  = st.session_state['txns_df']
cust_df  = st.session_state['cust_df']
prod_df  = st.session_state['prod_df']
promo_df = st.session_state['promo_df']

# =========================================================
# TABS LAYOUT
# =========================================================
tabs = st.tabs([
    "📘 Instructions", 
    "🗂️ Database Tables",
    "📊 Sales Analytics", 
    "🔍 Sub-Category Drilldown",                               
    "📊 RFM Segmentation", 
    "🤖 Business Analyst AI (BETA)",
    "🤖 Chatbot"
])

# Tab 1: Instructions
with tabs[0]:
    st.subheader("📘 Instructions & User Guide")
    st.markdown("""
    1. Data is loaded automatically from the **remote** SQL Server.
    2. Review loaded tables in the **🗂️ Database Tables** tab.
    3. Explore analytics in the other tabs.
    """)
    # Connection health
    col1, col2 = st.columns(2)
    with col1:
        st.caption(f"Server: `{SERVER}`  •  DB: `{DATABASE}`")
    with col2:
        st.caption(f"Resolved 'Transactions' table: `{resolved_names['Transactions'] or 'NOT FOUND'}`")

# Tab 2: Database Tables
with tabs[1]:
    st.subheader("🗂️ Database Tables Preview")
    for name, df in {
        f"Transactions ({resolved_names['Transactions']})": txns_df,
        f"Customers ({resolved_names['Customers']})":      cust_df,
        f"Products ({resolved_names['Products']})":        prod_df,
        f"Promotions ({resolved_names['Promotions']})":    promo_df
    }.items():
        with st.expander(f"📄 {name}"):
            if df is not None and not df.empty:
                st.dataframe(df.head(10), use_container_width=True)
                st.caption(f"Rows loaded: {len(df):,}" + (f" (limited to TOP {ROW_LIMIT:,})" if ROW_LIMIT else ""))
            else:
                st.warning(f"⚠ No data for {name} (table missing or empty).")

# Tab 3: Sales Analytics
with tabs[2]:
    st.subheader("📊 Sales Analytics Overview")
    if txns_df is None or txns_df.empty:
        st.warning("📂 Transactions table not found or empty.")
    elif not st.session_state.get("start_sales_analysis", False):
        if st.button("▶️ Start Sales Analytics"):
            st.session_state.start_sales_analysis = True
            st.rerun()
    else:
        render_sales_analytics(txns_df)
        st.markdown("---")
        st.subheader("💡 Smart Narrative & Dynamic Insights")
        insights = generate_sales_insights(txns_df)
        generate_dynamic_insights(insights)

# Tab 4: Sub-Category Drilldown
with tabs[3]:
    st.subheader("🔍 Sub-Category Drilldown Analysis")
    if txns_df is None or txns_df.empty:
        st.warning("📂 Transactions table not found or empty.")
    elif not st.session_state.get("start_subcat_analysis", False):
        if st.button("▶️ Start Sub-Category Analysis"):
            st.session_state.start_subcat_analysis = True
            st.rerun()
    else:
        render_subcategory_trends(txns_df)

# Tab 5: RFM Segmentation
with tabs[4]:
    st.subheader("🚦 RFM Segmentation Analysis")
    if txns_df is None or txns_df.empty:
        st.warning("⚠ Transactions table not found or empty.")
    elif not st.session_state.get("run_rfm", False):
        if st.button("▶️ Run RFM Analysis"):
            st.session_state.run_rfm = True
            st.rerun()
    else:
        with st.spinner("Running RFM segmentation..."):
            rfm_df = calculate_rfm(txns_df)
            st.session_state['rfm_df'] = rfm_df
        st.success("✅ RFM Analysis Completed!")
        st.dataframe(rfm_df.head(10), use_container_width=True)
        st.download_button("📥 Download RFM Output", rfm_df.to_csv(index=False), "rfm_output.csv")

        if st.button("🚀 Get Campaign Target List"):
            campaign_df = get_campaign_targets(rfm_df)
            st.session_state['campaign_df'] = campaign_df
            st.success(f"🎯 Found {len(campaign_df)} campaign-ready customers.")
            st.dataframe(campaign_df.head(10), use_container_width=True)
            st.download_button("📥 Download Campaign Target List", campaign_df.to_csv(index=False), "campaign_targets.csv")

        if st.button("💬 Send Personalized Message"):
            campaign_df = st.session_state.get('campaign_df')
            if campaign_df is None or campaign_df.empty:
                st.warning("⚠ No campaign targets found.")
            else:
                message = generate_personal_offer(txns_df, cust_df)
                st.success("📨 Message Generated:")
                st.markdown(message)

# Tab 6: Business Analyst + KPI Analyst
with tabs[5]:
    st.subheader("🧠 Business Analyst AI + KPI Analyst")
    if txns_df is None or txns_df.empty:
        st.warning("📂 Transactions table not found or empty.")
    else:
        BA.run_business_analyst_tab({
            "transactions": txns_df,
            "customers": cust_df,
            "products": prod_df,
            "promotions": promo_df
        })
        st.markdown("---")
        KPI_analyst.run_kpi_analyst({
            "transactions": txns_df,
            "customers": cust_df,
            "products": prod_df,
            "promotions": promo_df
        })

# Tab 7: Chatbot
with tabs[6]:
    if txns_df is None or txns_df.empty:
        st.warning("📂 Transactions table not found or empty.")
    else:
        chatbot2.run_chat({
            "transactions": txns_df,
            "customers": cust_df,
            "products": prod_df,
            "promotions": promo_df
        })

