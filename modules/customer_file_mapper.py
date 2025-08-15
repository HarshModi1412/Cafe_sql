import pandas as pd
import streamlit as st
from difflib import get_close_matches

# Define standard columns expected in customer data
REQUIRED_CUSTOMER_COLUMNS = {
    'Customer ID': ['customer_id', 'custid', 'id', 'customerid'],
    'Gender': ['sex', 'customer gender'],
    'Age': ['age group', 'customer age'],
    'Segment': ['tier', 'cluster', 'segment'],
}

def suggest_column_match(user_col, options):
    """
    Suggest the closest match from options for a given user column.
    """
    matches = get_close_matches(user_col.lower(), options, n=1, cutoff=0.6)
    return matches[0] if matches else None

def customer_file_mapper(df: pd.DataFrame):
    """
    Allows users to map their customer data file columns to the standard columns.
    """
    st.markdown("### 🗂️ Map Your Customer File Columns")
    st.markdown("We couldn't detect standard column names. Please map them manually.")

    user_columns = df.columns.tolist()
    standard_map = {}

    # Try auto-mapping first
    for std_col, possible_names in REQUIRED_CUSTOMER_COLUMNS.items():
        suggestion = None
        for name in possible_names:
            if name in map(str.lower, user_columns):
                suggestion = name
                break
        if not suggestion:
            suggestion = suggest_column_match(std_col, user_columns)

        selected = st.selectbox(
            f"🔁 Map to '{std_col}'",
            options=["-- None --"] + user_columns,
            index=user_columns.index(suggestion) + 1 if suggestion in user_columns else 0,
            key=f"map_{std_col}"
        )
        if selected != "-- None --":
            standard_map[std_col] = selected

    # Apply the mapping
    df_mapped = df.rename(columns={v: k for k, v in standard_map.items()})
    missing = [col for col in REQUIRED_CUSTOMER_COLUMNS if col not in df_mapped.columns]

    if missing:
        st.warning(f"⚠️ Still missing required fields: {', '.join(missing)}")
        return None
    else:
        st.success("✅ Columns mapped successfully!")
        return df_mapped
