import streamlit as st
import pandas as pd
import pyodbc

# === Module Imports ===
from modules.rfm import calculate_rfm, get_campaign_targets, generate_personal_offer
from modules.profiler import generate_customer_profile
from modules.customer_journey import map_customer_journey_and_affinity, generate_behavioral_recommendation_with_impact
from modules.discount import generate_discount_insights, assign_offer_codes
from modules.personalization import compute_customer_preferences
from modules.sales_analytics import render_sales_analytics, render_subcategory_trends, generate_sales_insights
from modules.mapper import classify_and_extract_data
from modules.smart_insights import generate_dynamic_insights
import BA
import KPI_analyst
import chatbot2


# === Database Connection (SQL Server) ===
def get_connection():
    """Create and return a SQL Server connection using pyodbc."""
    try:
        return pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=localhost;"
            "DATABASE=billing_history;"
            "UID=sa;"
            "PWD=YourStrongPassword;"
            "TrustServerCertificate=yes"
        )
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        return None


# === Safe Table Loader ===
def safe_select_all(table_name):
    """
    SELECT * FROM <table_name>.
    Skips if table doesn't exist.
    Works for any table in the database.
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Check table existence
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = ?
        """, (table_name,))
        exists = cursor.fetchone()[0] > 0

        if not exists:
            st.warning(f"⚠ Table '{table_name}' does not exist. Skipping...")
            return None

        # Fetch data
        cursor.execute(f"SELECT * FROM [{table_name}]")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)

    except Exception as e:
        st.error(f"❌ Error loading table '{table_name}': {e}")
        return None
    finally:
        conn.close()


# === UI Cleanup ===
st.set_page_config(
    page_title="Cafe_X Dashboard",
    page_icon="📊",
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": None}
)
st.markdown("""
    <style>
    #MainMenu, footer, header, a[href*="github.com"], .css-1lsmgbg.e1fqkh3o5 {display: none;}
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    </style>
""", unsafe_allow_html=True)


# === Branding ===
st.markdown("""
<h1 style='text-align: left; color: #FFFFFF; font-size: 3em; margin: 0;'>Cafe_X</h1>
<hr style='margin: 0.5rem auto 1rem auto; border: 1px solid #ccc; width: 100%;' />
""", unsafe_allow_html=True)


# === Sidebar Upload ===
st.sidebar.title("📁 Upload Your CSV/Excel Files")
uploaded_files = st.sidebar.file_uploader(
    "Upload 1–4 CSV or Excel files",
    type=["csv", "xlsx"],
    accept_multiple_files=True
)


# === Session State Init ===
for key in ['uploaded_files', 'files_mapped', 'txns_df', 'cust_df', 'prod_df', 'promo_df']:
    if key not in st.session_state:
        st.session_state[key] = None if key.endswith('_df') else False


# === Store Uploaded Files ===
raw_dfs = {}
if uploaded_files:
    st.session_state["uploaded_files"] = uploaded_files
    for idx, file in enumerate(uploaded_files):
        ext = file.name.split('.')[-1].lower()
        df = pd.read_csv(file) if ext == "csv" else pd.read_excel(file)
        raw_dfs[f'df_{idx+1}'] = df
        raw_dfs[f'df_{idx+1}_name'] = file.name


# === Upload Feedback ===
if not uploaded_files and not st.session_state["files_mapped"]:
    st.info("👈 Please upload your CSV/Excel files from the sidebar.")
elif uploaded_files and not st.session_state["files_mapped"]:
    st.warning("📤 Files uploaded. Go to the **🗂️ File Mapping** tab.")
elif st.session_state["files_mapped"]:
    st.success("✅ Files loaded and mapped. You're ready to explore insights!")


# === Load Mapped Data ===
txns_df = st.session_state.get("txns_df")
cust_df = st.session_state.get("cust_df")
prod_df = st.session_state.get("prod_df")
promo_df = st.session_state.get("promo_df")


# === Tabs ===
tabs = st.tabs([
    "📘 Instructions", 
    "🗂️ File Mapping",
    "📊 Sales Analytics", 
    "🔍 Sub-Category Drilldown Analysis",                               
    "📊 RFM Segmentation", 
    "🤖 Business Analyst AI (BETA)",
    "🤖 Chatbot"
])


# === Tab 1: Instructions ===
with tabs[0]:
    st.subheader("📘 Instructions & User Guide")
    st.markdown("""
    1. 📁 Upload data files from the sidebar.
    2. Map them in the **🗂️ File Mapping** tab.
    3. Explore analytics in the other tabs.
    """)


# === Tab 2: File Mapping ===
with tabs[1]:
    st.subheader("🗂️ File Mapping & Confirmation")

    if uploaded_files:
        if not st.session_state.get("files_mapped"):
            mapped_data = classify_and_extract_data(uploaded_files)
            if mapped_data:
                st.session_state['txns_df'] = mapped_data.get("Transactions")
                st.session_state['cust_df'] = mapped_data.get("Customers")
                st.session_state['prod_df'] = mapped_data.get("Products")
                st.session_state['promo_df'] = mapped_data.get("Promotions")
                st.session_state["files_mapped"] = True
                st.rerun()
        else:
            for name, df in {
                "Transactions": txns_df,
                "Customers": cust_df,
                "Products": prod_df,
                "Promotions": promo_df
            }.items():
                with st.expander(f"📄 {name} Sample"):
                    st.dataframe(df.head(10) if df is not None else f"⚠ No {name} data.")
    else:
        st.info("👈 Upload files to start mapping.")


# === Tab 3: Sales Analytics ===
with tabs[2]:
    st.subheader("📊 Sales Analytics Overview")
    if txns_df is None:
        st.warning("📂 Please upload the Transactions file.")
    else:
        if not st.session_state.get("start_sales_analysis", False):
            if st.button("▶️ Start Sales Analytics"):
                st.session_state.start_sales_analysis = True
                st.rerun()
        else:
            render_sales_analytics(txns_df)
            st.markdown("---")
            st.subheader("💡 Smart Narrative & Dynamic Insights")
            insights = generate_sales_insights(txns_df)
            generate_dynamic_insights(insights)


# === Tab 4: Sub-Category Drilldown ===
with tabs[3]:
    st.subheader("🔍 Sub-Category Drilldown Analysis")
    if txns_df is None:
        st.warning("📂 Please upload the Transactions file.")
    else:
        if not st.session_state.get("start_subcat_analysis", False):
            if st.button("▶️ Start Sub-Category Analysis"):
                st.session_state.start_subcat_analysis = True
                st.rerun()
        else:
            render_subcategory_trends(txns_df)


# === Tab 5: RFM Segmentation ===
with tabs[4]:
    st.subheader("🚦 RFM Segmentation Analysis")
    if txns_df is None:
        st.warning("⚠ Please upload the Transactions file.")
    else:
        if not st.session_state.get("run_rfm", False):
            if st.button("▶️ Run RFM Analysis"):
                st.session_state.run_rfm = True
                st.rerun()

        if st.session_state.get("run_rfm", False):
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


# === Tab 6: Business Analyst + KPI Analyst ===
with tabs[5]:
    st.subheader("🧠 Business Analyst AI + KPI Analyst")
    if not raw_dfs:
        st.warning("📂 Please upload at least one raw file.")
    else:
        BA.run_business_analyst_tab(raw_dfs)
        st.markdown("---")
        KPI_analyst.run_kpi_analyst(raw_dfs)


# === Tab 7: Chatbot AI ===
with tabs[6]:
    if not raw_dfs:
        st.warning("📂 Please upload at least one raw file.")
    else:
        chatbot2.run_chat(raw_dfs)


# === Sidebar Reset ===
if st.sidebar.button("🔄 Reset App"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
