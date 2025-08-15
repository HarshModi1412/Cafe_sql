import streamlit as st
import pandas as pd
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
# DATABASE CONNECTION
# =========================================================
def get_connection():
    """Create and return a SQL Server connection using pyodbc."""
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=localhost;"
            "DATABASE=billing_history;"
            "UID=sa;"
            "PWD=YourStrongPassword;"
            "TrustServerCertificate=yes",
            timeout=30
        )
        return conn
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        return None

# =========================================================
# SAFE TABLE FETCH FUNCTION
# =========================================================
def safe_select_all(table_name):
    """
    Fetch all rows from a table if it exists.
    Returns None if table is missing or query fails.
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Check existence
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
        """, (table_name,))
        exists = cursor.fetchone()[0] > 0

        if not exists:
            st.warning(f"⚠ Table '{table_name}' does not exist. Skipping...")
            return None

        # Fetch all data
        cursor.execute(f"SELECT * FROM [{table_name}]")
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)

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
# LOAD DATA FROM DATABASE
# =========================================================
table_names = {
    "Transactions": "transactions",
    "Customers": "customers",
    "Products": "products",
    "Promotions": "promotions"
}

st.session_state['txns_df'] = safe_select_all(table_names["Transactions"])
st.session_state['cust_df'] = safe_select_all(table_names["Customers"])
st.session_state['prod_df'] = safe_select_all(table_names["Products"])
st.session_state['promo_df'] = safe_select_all(table_names["Promotions"])

txns_df = st.session_state['txns_df']
cust_df = st.session_state['cust_df']
prod_df = st.session_state['prod_df']
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
    1. Data is loaded automatically from SQL Server.
    2. Review loaded tables in the **🗂️ Database Tables** tab.
    3. Explore analytics in the other tabs.
    """)

# Tab 2: Database Tables
with tabs[1]:
    st.subheader("🗂️ Database Tables Preview")
    for name, df in {
        "Transactions": txns_df,
        "Customers": cust_df,
        "Products": prod_df,
        "Promotions": promo_df
    }.items():
        with st.expander(f"📄 {name} Table Sample"):
            st.dataframe(df.head(10) if df is not None else f"⚠ No {name} data.", use_container_width=True)

# Tab 3: Sales Analytics
with tabs[2]:
    st.subheader("📊 Sales Analytics Overview")
    if txns_df is None:
        st.warning("📂 Transactions table not found.")
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
    if txns_df is None:
        st.warning("📂 Transactions table not found.")
    elif not st.session_state.get("start_subcat_analysis", False):
        if st.button("▶️ Start Sub-Category Analysis"):
            st.session_state.start_subcat_analysis = True
            st.rerun()
    else:
        render_subcategory_trends(txns_df)

# Tab 5: RFM Segmentation
with tabs[4]:
    st.subheader("🚦 RFM Segmentation Analysis")
    if txns_df is None:
        st.warning("⚠ Transactions table not found.")
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
    if txns_df is None:
        st.warning("📂 Transactions table not found.")
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
    if txns_df is None:
        st.warning("📂 Transactions table not found.")
    else:
        chatbot2.run_chat({
            "transactions": txns_df,
            "customers": cust_df,
            "products": prod_df,
            "promotions": promo_df
        })
