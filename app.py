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
# DATABASE CONFIG
# =========================================================
SERVER   = os.getenv("DB_SERVER",   "den1.mssql7.gear.host")
DATABASE = os.getenv("DB_NAME",     "billinghistory")
USERNAME = os.getenv("DB_USER",     "billinghistory")
PASSWORD = os.getenv("DB_PASSWORD", "Pk0Z-57_avQe")
ROW_LIMIT = int(os.getenv("ROW_LIMIT", "500000"))

# =========================================================
# DB CONNECTION
# =========================================================
def get_connection(max_retries: int = 2, sleep_between: int = 2):
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
    for attempt in range(1, max_retries + 2):
        try:
            conn = pyodbc.connect(conn_str, timeout=30)
            conn.timeout = 60
            return conn
        except Exception as e:
            last_err = e
            if attempt <= max_retries:
                time.sleep(sleep_between)
    st.error(f"❌ Database connection failed after retries: {last_err}")
    return None

# =========================================================
# HELPER FUNCTIONS
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
    if not table_name:
        return None
    conn = get_connection()
    if not conn:
        return None
    try:
        if not table_exists(conn, table_name):
            return None
        top_clause = f"TOP {limit} " if (isinstance(limit, int) and limit > 0) else ""
        sql = f"SELECT {top_clause}* FROM [{table_name}]"
        return pd.read_sql_query(sql, conn)
    except Exception as e:
        st.warning(f"⚠ Could not read table '{table_name}': {e}")
        return None
    finally:
        conn.close()

def safe_transform_transactions(txns: pd.DataFrame) -> pd.DataFrame:
    """Ensure required columns exist, rename, and always add Sub Category with NA."""
    if txns is None or txns.empty:
        return pd.DataFrame()

    rename_map = {
        "invoice_id": "Invoice ID",
        "timestamp": "Date",
        "quantity": "Quantity",
        "customer_id": "Customer ID",
        "product_id": "Product ID",
        "Product Name": "product_name",
        "unit_price": "Unit Price"
    }
    existing_map = {k: v for k, v in rename_map.items() if k in txns.columns}
    if existing_map:
        txns = txns.rename(columns=existing_map)

    if "Date" in txns.columns:
        txns["Date"] = pd.to_datetime(txns["Date"], errors="coerce").dt.date
    else:
        st.info("ℹ Missing column: 'Date'")

    if "Product ID" not in txns.columns:
        txns["Product ID"] = None

    if "Sub Category" not in txns.columns:
        txns["Sub Category"] = "NA"

    if "Discount" not in txns.columns:
        txns["Discount"] = 0

    return txns
# Normalize customer columns
if cust_df is not None and not cust_df.empty:
    cust_rename_map = {}
    if 'customer_id' in cust_df.columns:
        cust_rename_map['customer_id'] = 'Customer ID'
    if 'customer_name' in cust_df.columns:
        cust_rename_map['customer_name'] = 'Name'
    if 'customer_number' in cust_df.columns:
        cust_rename_map['customer_number'] = 'Phone'

    if cust_rename_map:
        cust_df = cust_df.rename(columns=cust_rename_map)

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
st.markdown("""
<h1 style='text-align: left; color: #FFFFFF; font-size: 3em; margin: 0;'>Cafe_X</h1>
<hr style='margin: 0.5rem auto 1rem auto; border: 1px solid #ccc; width: 100%;' />
""", unsafe_allow_html=True)

# =========================================================
# REFRESH BUTTON
# =========================================================
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.success("✅ Data cache cleared! Reloading...")
    st.rerun()

# =========================================================
# LOAD DATA
# =========================================================
CANDIDATES = {
    "Transactions": ["transactions", "billing"],
    "Customers":    ["customers"],
    "Products":     ["product"],
    "Promotions":   ["promotions"],
}
resolved_names = {logical: resolve_table_name(candidates) for logical, candidates in CANDIDATES.items()}

txns_df  = safe_transform_transactions(read_table(resolved_names["Transactions"]))
cust_df  = read_table(resolved_names["Customers"])
prod_df  = read_table(resolved_names["Products"])
promo_df = read_table(resolved_names["Promotions"])

# Rename columns in prod_df
if prod_df is not None and not prod_df.empty:
    prod_df = prod_df.rename(columns={
        "product_id": "Product ID",
        "product_name": "Product Name",
        "production_cost": "Production Cost",
        "sub_category": "Sub Category"
    })

st.session_state.update({
    'txns_df': txns_df,
    'cust_df': cust_df,
    'prod_df': prod_df,
    'promo_df': promo_df
})

# =========================================================
# TABS
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

# Tab 1
with tabs[0]:
    st.subheader("📘 Instructions & User Guide")
    st.markdown("""
    1. Data loads automatically if tables exist.
    2. Click **🔄 Refresh Data** to instantly reload from the database.
    3. Check the **🗂️ Database Tables** tab for raw previews.
    4. Run analytics from other tabs.
    """)
    st.caption(f"Server: `{SERVER}`  •  DB: `{DATABASE}`")
    st.caption(f"Resolved 'Transactions' table: `{resolved_names['Transactions'] or 'NOT FOUND'}`")

# Tab 2
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
                st.caption(f"Rows loaded: {len(df):,}" + (f" (TOP {ROW_LIMIT:,})" if ROW_LIMIT else ""))
            else:
                st.warning(f"⚠ No data for {name}")

# Tab 3
with tabs[2]:
    st.subheader("📊 Sales Analytics Overview")
    if txns_df.empty:
        st.warning("📂 Transactions missing or empty.")
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

# Tab 4
with tabs[3]:
    st.subheader("🔍 Sub-Category Drilldown Analysis")
    if txns_df.empty:
        st.warning("📂 Transactions missing or empty.")
    elif not st.session_state.get("start_subcat_analysis", False):
        if st.button("▶️ Start Sub-Category Analysis"):
            st.session_state.start_subcat_analysis = True
            st.rerun()
    else:
        render_subcategory_trends(txns_df)

# Tab 5
with tabs[4]:
    st.subheader("🚦 RFM Segmentation Analysis")
    if txns_df.empty:
        st.warning("⚠ Transactions missing or empty.")
    elif not st.session_state.get("run_rfm", False):
        if st.button("▶️ Run RFM Analysis"):
            st.session_state.run_rfm = True
            st.rerun()
    else:
        with st.spinner("Running RFM segmentation..."):
            rfm_df = calculate_rfm(txns_df)
            st.session_state['rfm_df'] = rfm_df
        st.success("✅ RFM Completed!")
        st.dataframe(rfm_df.head(10), use_container_width=True)
        st.download_button("📥 Download RFM", rfm_df.to_csv(index=False), "rfm_output.csv")

        if st.button("🎯 Get Campaign Targets"):
            campaign_df = get_campaign_targets(rfm_df)
            st.session_state['campaign_df'] = campaign_df
            st.success(f"Found {len(campaign_df)} targets.")
            st.dataframe(campaign_df.head(10), use_container_width=True)

        if st.button("💬 Send Personalized Message"):
            campaign_df = st.session_state.get('campaign_df')
            if campaign_df is None or campaign_df.empty:
                st.warning("⚠ No targets found.")
            else:
                message = generate_personal_offer(txns_df, cust_df)
                st.success("📨 Message Generated:")
                st.markdown(message)

# Tab 6
with tabs[5]:
    st.subheader("🧠 Business Analyst AI + KPI Analyst")
    if txns_df.empty:
        st.warning("📂 Transactions missing or empty.")
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

# Tab 7
with tabs[6]:
    if txns_df.empty:
        st.warning("📂 Transactions missing or empty.")
    else:
        chatbot2.run_chat({
            "transactions": txns_df,
            "customers": cust_df,
            "products": prod_df,
            "promotions": promo_df
        })

