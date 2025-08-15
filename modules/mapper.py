import streamlit as st
import pandas as pd
from collections import defaultdict


import chardet


def read_csv_with_encoding(file):
    raw_bytes = file.read()
    result = chardet.detect(raw_bytes)
    encoding = result['encoding'] or 'utf-8'
    file.seek(0)

    return pd.read_csv(file, encoding=encoding, encoding_errors='replace')



# Canonical field dictionary with aliases
REQUIRED_FIELDS = {
    "Transactions": {
        "Invoice ID": ["invoice_id", "bill_no", "invoice number", "InvoiceNo", "Invoice No",'orderid','order id','order_id'],
        "Date": ["date", "invoice_date", "purchase_date", "Invoicedate",'orderdate','order date'],
        "Sub Category": ["subcat", "product_type", "subcategory","sub-category"],
        "Invoice Total": ["amount", "invoice_amount", "total_amount", "grand_total","Sales","sales"],
        "Quantity": ["qty", "units", "number of items"],
        "Discount": ["discount_amt", "disc", "offer_discount", "discount"],
        "Description": ["offer", "promo_desc", "discount name", "description"],
        "Transaction Type": ["transaction_type", "type", "return"],
        "Production Cost": ["cost", "production_cost", "item_cost"],
        # New field: unit cost, to compute production cost if given
        "Unit Cost": ["unit_cost", "unit cost", "cost per unit"],
        "Product ID": ["prod_id", "item_code", "stockcode",'ProductID'],
        "Customer ID": ["customer", "cust_id", "cust number", "client_id", "CustomerID"],
        "Unit Price": ["unit", "price", "unit_price", "product price", "unitprice"]
    },
    "Customers": {
        "Customer ID": ["customer", "cust_id", "cust number", "client_id", "CustomerID"],
        "Gender": ["sex", "customer_gender"],
        "Name": ["name", "NAME",'customer_name'],
        "Telephone": ["telephone", "phone", "number"],
        "Email": ["email", "mail"],
        "Date Of Birth": ["date_of_birth", "dob"]
    },
    "Products": {
        "Product ID": ["prod_id", "item_code", "stockcode",'ProductID'],
        "Sub Category": ["subcategory", "subcat", "product_type", "catagory"],
        "Category": ["cat", "product_cat", "segment"]
    },
    "Promotions": {
        "Description": ["offer_desc", "campaign_desc", "promotion_name"],
        "Start": ["start", "from_date", "campaign_start", "start_date"],
        "End": ["end", "to_date", "campaign_end", "end_date"],
        "Discont": ["discount_value", "discount_rate", "disc"]
    }
}

IMPORTANT_FIELDS = ["Invoice Total", "Quantity", "Unit Price"]

# --- Helper Functions ---
def normalize(col: str) -> str:
    return col.strip().lower().replace(" ", "_")

def build_column_inventory(files):
    inventory = defaultdict(list)
    file_dfs = []

    for file in files:
        try:
            # Detect file format
            file_ext = file.name.lower().split('.')[-1]

            # Load file with encoding handling
            if file_ext == "csv":
                df = read_csv_with_encoding(file)
            elif file_ext in ("xlsx", "xls"):
                df = pd.read_excel(file, engine="openpyxl")
            else:
                st.warning(f"⚠️ Unsupported file format: {file.name}")
                continue

            # Store loaded file and its columns
            file_dfs.append((file.name, df))
            for col in df.columns:
                normalized = normalize(col)
                inventory[normalized].append((file.name, col, df[col]))

        except Exception as e:
            st.error(f"❌ Error reading {file.name}: {e}")

    return inventory, file_dfs



def auto_map_fields(role, inventory):
    mapping = {}
    for field, aliases in REQUIRED_FIELDS[role].items():
        candidates = [normalize(field)] + [normalize(a) for a in aliases]
        for c in candidates:
            if c in inventory:
                mapping[field] = inventory[c][0]
                break
    return mapping

def build_dataframe_from_mapping(mapping, required_fields):
    # Step 1: Pull in each mapped series
    columns = {}
    max_len = 0
    for field, (_, _, series) in mapping.items():
        s = series.reset_index(drop=True)
        columns[field] = s
        max_len = max(max_len, len(s))

    # Step 2: Build DataFrame skeleton
    df = pd.DataFrame({field: columns.get(field, pd.Series([pd.NA] * max_len))
                       for field in required_fields})

    # Step 3: If Invoice Total missing or all null, compute from Unit Price & Quantity
    if "Invoice Total" in required_fields:
        if df["Invoice Total"].isnull().all() and {"Unit Price", "Quantity"}.issubset(df):
            df["Invoice Total"] = (
                pd.to_numeric(df["Unit Price"], errors="coerce") *
                pd.to_numeric(df["Quantity"], errors="coerce")
            )

    # Step 4: Compute Production Cost if missing but Unit Cost provided
    if "Production Cost" in required_fields:
        prod_cost_null = df["Production Cost"].isnull().all() if "Production Cost" in df else True
        if prod_cost_null and "Unit Cost" in df and "Quantity" in df:
            df["Production Cost"] = (
                pd.to_numeric(df["Unit Cost"], errors="coerce") *
                pd.to_numeric(df["Quantity"], errors="coerce")
            )

    return df

def classify_and_extract_data(uploaded_files):
    inventory, file_dfs = build_column_inventory(uploaded_files)
    final_data = {}
    all_mappings = {}

    for role in REQUIRED_FIELDS:
        auto_mapping = auto_map_fields(role, inventory)
        manual_mapping = {}
        missing = [f for f in REQUIRED_FIELDS[role] if f not in auto_mapping]

        st.markdown(f"### 🗂 Mapping for `{role}`")

        if missing:
            st.warning(f"Manual mapping needed for `{role}`: {', '.join(missing)}")
            all_cols = sorted({col for _, df in file_dfs for col in df.columns})
            for field in missing:
                sel = st.selectbox(f"Select column for `{field}`", ["--"] + all_cols, key=f"{role}_{field}")
                if sel and sel != "--":
                    for fname, df in file_dfs:
                        if sel in df.columns:
                            manual_mapping[field] = (fname, sel, df[sel])
                            break

        combined = {**auto_mapping, **manual_mapping}
        # add fallbacks if needed...
        all_mappings[role] = combined

    if st.button("✅ Confirm and Start Analytics"):
        for role, mapping in all_mappings.items():
            fields = list(REQUIRED_FIELDS[role].keys())
            df = build_dataframe_from_mapping(mapping, fields)
            final_data[role] = df
        return final_data

    return None


