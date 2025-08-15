import pandas as pd

def assign_offer_codes(promo_df: pd.DataFrame) -> pd.DataFrame:
    """
    Assigns unique Offer Codes to each promotion Description.
    """
    if 'Description' not in promo_df.columns:
        raise ValueError("'Description' column is required in promo file.")

    promo_df['Offer_Code'] = pd.factorize(promo_df['Description'])[0] + 1
    promo_df['Offer_Code'] = promo_df['Offer_Code'].apply(lambda x: f"OFF{x:03}")
    return promo_df


def label_transactions_with_offers(txn_df: pd.DataFrame, promo_df: pd.DataFrame) -> pd.DataFrame:
    """
    Matches transactions with promo_df based on Date and Discount within Start and End Date range.
    """
    txn_df['Date'] = pd.to_datetime(txn_df['Date'], errors='coerce')
    promo_df['Start Date'] = pd.to_datetime(promo_df['Start'], errors='coerce')
    promo_df['End Date'] = pd.to_datetime(promo_df['End'], errors='coerce')

    txn_df['Offer_Code'] = None
    txn_df['Offer ID'] = 'No Offer'
    txn_df['Description'] = None

    for _, promo in promo_df.iterrows():
        mask = (
            (txn_df['Date'] >= promo['Start Date']) &
            (txn_df['Date'] <= promo['End Date']) &
            (txn_df['Discount'] == promo['Discont'])
        )
        txn_df.loc[mask, 'Offer_Code'] = promo['Offer_Code']
        txn_df.loc[mask, 'Offer ID'] = promo['Offer_Code']
        txn_df.loc[mask, 'Description'] = promo['Description']

    return txn_df


def generate_discount_insights(txn_df: pd.DataFrame, promo_df: pd.DataFrame) -> dict:
    """
    Generate discount summaries and uplift metrics from labeled transactions.
    """
    txn_df = label_transactions_with_offers(txn_df, promo_df)
    txn_df['Month'] = txn_df['Date'].dt.to_period('M').astype(str)
    txn_df['Discount'] = txn_df['Discount'].fillna(0)
    txn_df['Qty'] = txn_df['Quantity'] if 'Quantity' in txn_df.columns else 1
    txn_df['Offer ID'] = txn_df['Offer ID'].fillna('No Offer')

    # --- Monthly Summary ---
    monthly = txn_df.groupby('Month').agg({
        'Invoice Total': 'sum',
        'Discount': 'sum',
        'Invoice ID': 'nunique'
    }).reset_index()
    monthly['Discount (%)'] = (monthly['Discount'] / monthly['Invoice Total']) * 100

    # --- Sub-Category Summary ---
    subcat = txn_df.groupby('Sub Category').agg({
        'Invoice Total': 'sum',
        'Discount': 'sum',
        'Invoice ID': 'nunique'
    }).reset_index()
    subcat['Discount (%)'] = (subcat['Discount'] / subcat['Invoice Total']) * 100

    # --- Offer Summary ---
    offer = txn_df.groupby('Offer ID').agg({
        'Invoice Total': 'sum',
        'Discount': 'sum',
        'Invoice ID': 'nunique'
    }).reset_index()
    offer['Discount (%)'] = (offer['Discount'] / offer['Invoice Total']) * 100

    # --- Uplift Summary ---
    uplift_data = []
    grouped = txn_df.groupby(['Offer_Code', 'Sub Category'])

    for (offer_code, subcat_name), group in grouped:
        offer_grp = group[group['Offer ID'] != 'No Offer']
        control_grp = txn_df[(txn_df['Sub Category'] == subcat_name) & (txn_df['Offer ID'] == 'No Offer')]

        if offer_grp.empty or control_grp.empty:
            continue

        row = {
            'Offer_Code': offer_code,
            'Sub Category': subcat_name,
            'Offer_Orders': offer_grp['Invoice ID'].nunique(),
            'Control_Orders': control_grp['Invoice ID'].nunique(),
            'Offer_Sales': offer_grp['Invoice Total'].sum(),
            'Control_Sales': control_grp['Invoice Total'].sum(),
            'Offer_Qty': offer_grp['Qty'].sum(),
            'Control_Qty': control_grp['Qty'].sum(),
        }

        row['Avg_Sale_Offer'] = row['Offer_Sales'] / row['Offer_Orders'] if row['Offer_Orders'] else 0
        row['Avg_Sale_Control'] = row['Control_Sales'] / row['Control_Orders'] if row['Control_Orders'] else 0
        row['Avg_Qty_Offer'] = row['Offer_Qty'] / row['Offer_Orders'] if row['Offer_Orders'] else 0
        row['Avg_Qty_Control'] = row['Control_Qty'] / row['Control_Orders'] if row['Control_Orders'] else 0

        row['Uplift_Sales_%'] = ((row['Avg_Sale_Offer'] - row['Avg_Sale_Control']) / row['Avg_Sale_Control']) * 100 if row['Avg_Sale_Control'] else 0
        row['Uplift_Qty_%'] = ((row['Avg_Qty_Offer'] - row['Avg_Qty_Control']) / row['Avg_Qty_Control']) * 100 if row['Avg_Qty_Control'] else 0
        row['Uplift_Overall_%'] = (row['Uplift_Sales_%'] + row['Uplift_Qty_%']) / 2

        uplift_data.append(row)

    uplift_df = pd.DataFrame(uplift_data)

    # --- Recommendations ---
    rec = "### 💡 Recommendations Based on Discount Patterns\n"
    high_leak = subcat[subcat['Discount (%)'] > 15]
    if not high_leak.empty:
        rec += "• Sub-categories with >15% discount:\n"
        for _, row in high_leak.iterrows():
            rec += f"   - **{row['Sub Category']}** → {row['Discount (%)']:.2f}% of sales in discounts.\n"
    else:
        rec += "• ✅ No high-discount sub-categories.\n"

    low_eff = offer[(offer['Discount (%)'] > 10) & (offer['Invoice Total'] < 50000)]
    if not low_eff.empty:
        rec += "\n• High discount but low revenue offers:\n"
        for _, row in low_eff.iterrows():
            rec += f"   - Offer **{row['Offer ID']}** → {row['Discount (%)']:.2f}% discount, only ₹{row['Invoice Total']:.0f} revenue.\n"
    else:
        rec += "\n• ✅ All offers generate adequate revenue.\n"

    peak = monthly.sort_values(by='Discount (%)', ascending=False).iloc[0]
    if peak['Discount (%)'] > 20:
        rec += f"\n• ⚠️ Highest discount month: **{peak['Month']}** at {peak['Discount (%)']:.2f}%.\n"

    return {
        "monthly_summary": monthly,
        "subcat_summary": subcat.sort_values(by='Discount (%)', ascending=False),
        "offer_summary": offer.sort_values(by='Discount (%)', ascending=False),
        "uplift_summary": uplift_df.sort_values(by='Uplift_Overall_%', ascending=False),
        "recommendations": rec
    }
