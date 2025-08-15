# profiler.py

import pandas as pd
from datetime import datetime

def generate_customer_profile(customer_id, transactions_df, customers_df, products_df):
    """
    Generate a detailed customer profile using transaction, customer, and product data.
    
    Args:
        customer_id (int): Target customer ID
        transactions_df (pd.DataFrame): Filtered transactions
        customers_df (pd.DataFrame): Customer master data
        products_df (pd.DataFrame): Product master data
        
    Returns:
        pd.DataFrame: Single-row customer profile
    """

    # Filter transactions for the customer
    customer_txns = transactions_df[transactions_df['Customer ID'] == customer_id].copy()

    if customer_txns.empty:
        return pd.DataFrame([{'Customer_ID': customer_id, 'Error': 'No transactions found'}])

    # Merge product data to get subcategories
    #product_info = products_df[['Product ID', 'Sub Category']]
    #customer_txns = customer_txns.merge(product_info, on='Product ID', how='left')

    # Demographics
    customer_row = customers_df[customers_df['Customer ID'] == customer_id]
    if not customer_row.empty:
        row = customer_row.iloc[0]
        name = row.get('Name')
        email = row.get('Email')
        phone = row.get('Telephone')
        gender = row.get('Gender')
        dob = pd.to_datetime(row.get('Date Of Birth'), errors='coerce')
        age = int((pd.to_datetime('today') - dob).days / 365.25) if not pd.isnull(dob) else None
    else:
        name = email = phone = gender = age = None

    # Ensure Date column is datetime
    customer_txns['Date'] = pd.to_datetime(customer_txns['Date'], errors='coerce')

    # RFM-like features
    snapshot_date = pd.to_datetime('today')
    recency = (snapshot_date - customer_txns['Date'].max()).days
    frequency = customer_txns['Invoice ID'].nunique()
    monetary = customer_txns.groupby('Invoice ID')['Invoice Total'].first().sum()
    avg_basket_size = customer_txns['Invoice Total'].mean()
    unique_categories = customer_txns['Sub Category'].nunique()

    # Sub-category preferences
    top_categories = customer_txns['Sub Category'].value_counts().head(10).index.tolist()
    all_categories = customer_txns['Sub Category'].dropna().unique().tolist()
    # Improved Preference Logic
    cat_counts = customer_txns['Sub Category'].value_counts()
    total_txns = cat_counts.sum()
    top_cat_vector = {}

    for cat, count in cat_counts.items():
        share = count / total_txns
        top_cat_vector[f'pref_{cat}'] = int(count >= 2 and share >= 0)


    # Final Profile
    profile = {
        'Customer_ID': customer_id,
        'Name': name,
        'Email': email,
        'Phone': phone,
        'Gender': gender,
        'Age': age,
        'Recency': recency,
        'Frequency': frequency,
        'Monetary': monetary,
        'Avg_Basket_Size': avg_basket_size,
        'Unique_Categories': unique_categories,
    }

    profile.update(top_cat_vector)
    # Return as vertical table
    vertical_df = pd.DataFrame(list(profile.items()), columns=['Feature', 'Value'])
    return vertical_df