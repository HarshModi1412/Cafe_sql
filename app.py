import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error

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


# === Safe Table Loader ===
def safe_select_all(table_name, connection):
    """
    Runs SELECT * FROM <table_name>.
    If table doesn't exist, returns None instead of crashing.
    """
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        return pd.DataFrame(rows, columns=columns)
    except Error as e:
        if "doesn't exist" in str(e).lower():
            st.warning(f"⚠️ Table '{table_name}' does not exist. Skipping...")
            return None
        else:
            raise


# === UI Cleanup ===
hide_ui = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    a[href*="github.com"] {visibility: hidden;}
    .css-1lsmgbg.e1fqkh3o5 {display: none;}
    </style>
"""
st.markdown(hide_ui, unsafe_allow_html=True)


# === Page Config ===
st.set_page_config(
    page_title="Cafe_X Dashboard",
    page_icon="📊",
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": None}
)


# === Branding ===
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
</style>
<h1 style='text-align: left; color: #FFFFFF; font-size: 3em; margin: 0;'>Cafe_X</h1>
<hr style='margin: 0.5rem auto 1rem auto; border: 1px solid #ccc; width: 100%;' />
""", unsafe_allow_html=True)


# === Sidebar Upload ===
st.sidebar.title("📁 Upload Your CSV Files")
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
    st.info("👈 Please upload your CSV files from the sidebar to get started.")
elif uploaded_files and not st.session_state["files_mapped"]:
    st.warning("📤 Files uploaded. Go to the **🗂️ File Mapping** tab to proceed.")
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
    Welcome to the **Retail Analytics Dashboard**. Steps:
    1. 📁 Upload your data files from the **sidebar**
    2. Map them in the **🗂️ File Mapping** tab
    3. Navigate through tabs to run analysis
    4. Download results wherever applicable
    """)


# === Tab 2: File Mapping ===
with tabs[1]:
    st.subheader("🗂️ File Mapping & Confirmation")

    if uploaded_files:
        st.markdown("### 🧩 Column Mapping for Each File")

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
            with st.expander("📄 Transactions Sample"):
                st.dataframe(txns_df.head(10) if txns_df is not None else "⚠️ No Transactions data.")
            with st.expander("📄 Customers Sample"):
                st.dataframe(cust_df.head(10) if cust_df is not None else "⚠️ No Customers data.")
            with st.expander("📄 Products Sample"):
                st.dataframe(prod_df.head(10) if prod_df is not None else "⚠️ No Products data.")
            with st.expander("📄 Promotions Sample"):
                st.dataframe(promo_df.head(10) if promo_df is not None else "⚠️ No Promotions data.")
    else:
        st.info("👈 Please upload your CSV files to start mapping.")


# === Tab 3: Sales Analytics ===
with tabs[2]:
    st.subheader("📊 Sales Analytics Overview")
    
    if txns_df is None:
        st.warning("📂 Please upload the Transactions CSV file.")
    else:
        if "start_sales_analysis" not in st.session_state:
            st.session_state.start_sales_analysis = False

        if not st.session_state.start_sales_analysis:
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
        st.warning("📂 Please upload your Transactions file.")
    else:
        if "start_subcat_analysis" not in st.session_state:
            st.session_state.start_subcat_analysis = False

        if st.session_state.start_subcat_analysis:
            render_subcategory_trends(txns_df)
        else:
            st.info("Click to start sub-category analysis.")
            if st.button("▶️ Start Sub-Category Analysis"):
                st.session_state.start_subcat_analysis = True
                st.rerun()


# === Tab 5: RFM Segmentation ===
with tabs[4]:
    st.subheader("🚦 RFM Segmentation Analysis")
    if txns_df is None:
        st.warning("⚠️ Please upload the Transactions CSV file.")
    else:
        if "run_rfm" not in st.session_state:
            st.session_state.run_rfm = False

        if not st.session_state.run_rfm:
            if st.button("▶️ Run RFM Analysis"):
                st.session_state.run_rfm = True
                st.rerun()

        if st.session_state.run_rfm:
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
                    st.warning("⚠️ No campaign targets found. Please run RFM first.")
                else:
                    message = generate_personal_offer(txns_df, cust_df)
                    if "No eligible customers" in message:
                        st.warning(message)
                    else:
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
