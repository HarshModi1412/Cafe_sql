import pandas as pd
import numpy as np
from datetime import date
from itertools import combinations
from collections import Counter

import pandas as pd

def calculate_rfm(txns_df: pd.DataFrame, today_date=None):
    if today_date is None:
        today_date = pd.to_datetime("today")

    df = txns_df.copy()

    # Clean and validate required columns
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])

    df['Customer ID'] = df['Customer ID'].astype(str)

    # Fallback if 'Invoice Total' is missing
    if 'Invoice Total' not in df.columns:
        if 'Unit Price' in df.columns and 'Quantity' in df.columns:
            df['Invoice Total'] = df['Unit Price'] * df['Quantity']
        else:
            raise ValueError("Required column 'Invoice Total' not found and cannot be computed from Unit Price & Quantity.")

    snapshot = today_date
    rfm = df.groupby('Customer ID').agg({
        'Date': lambda x: (snapshot - x.max()).days,
        'Invoice ID': 'nunique',
        'Invoice Total': 'sum'
    }).rename(columns={
        'Date': 'Recency',
        'Invoice ID': 'Frequency',
        'Invoice Total': 'Monetary'
    }).reset_index()

    rfm['Recency'] = pd.to_numeric(rfm['Recency'], errors='coerce')
    rfm['Frequency'] = pd.to_numeric(rfm['Frequency'], errors='coerce')
    rfm['Monetary'] = pd.to_numeric(rfm['Monetary'], errors='coerce')

    # --- Safe Binning Function ---
    def safe_qcut(series, labels, ascending=True):
        series = series.copy()
        valid_values = series.dropna().unique()

        if len(valid_values) < len(labels):
            mid_label = labels[len(labels)//2]
            return pd.Series([mid_label]*len(series), index=series.index)

        try:
            ranked = series.rank(method='first', ascending=ascending)
            return pd.qcut(ranked, q=len(labels), labels=labels)
        except Exception:
            mid_label = labels[len(labels)//2]
            return pd.Series([mid_label]*len(series), index=series.index)

    # Scoring logic
    r_labels = [5, 4, 3, 2, 1]
    f_labels = [1, 2, 3, 4, 5]
    m_labels = [1, 2, 3, 4, 5]

    rfm['R_Score'] = safe_qcut(rfm['Recency'], r_labels, ascending=False).astype(int)
    rfm['F_Score'] = safe_qcut(rfm['Frequency'], f_labels).astype(int)
    rfm['M_Score'] = safe_qcut(rfm['Monetary'], m_labels).astype(int)

    rfm['RFM_Score'] = (
        rfm['R_Score'].astype(str) +
        rfm['F_Score'].astype(str) +
        rfm['M_Score'].astype(str)
    )

    return rfm




def assign_segment_tags(rfm_df: pd.DataFrame) -> pd.DataFrame:
    df = rfm_df.copy()
    conditions = [
        df['RFM_Score'].astype(int) >= 444,
        (df['RFM_Score'].astype(int) >= 333) & (df['RFM_Score'].astype(int) < 444)
    ]
    choices = ['Champions', 'Loyal Customers']
    df['Segment_Tag'] = np.select(conditions, choices, default='At Risk')
    return df


def get_campaign_targets(rfm_df: pd.DataFrame, today=None, top_n=10000) -> pd.DataFrame:
    if today is None:
        today = date.today()

    if 'Segment_Tag' not in rfm_df.columns:
        rfm_df = assign_segment_tags(rfm_df)

    def should_trigger(row):
        seg, rec = row['Segment_Tag'], row['Recency']
        return (
            (seg == 'At Risk' and rec > 30) or
            (seg == 'Loyal Customers' and rec > 20) or
            (seg == 'Champions' and rec > 30) or
            (seg == 'Recent Customers' and rec <= 7)
        )

    priority = {
        'Champions': 2, 'Loyal Customers': 1, 'Big Spenders': 1,
        'At Risk': 3, 'Hibernating': 0, 'Lost High-Value': 3,
        'Recent Customers': 2, 'Low Value': 0, 'Others': 0
    }

    df = rfm_df.copy()
    df['Segment_Priority'] = df['Segment_Tag'].map(priority).fillna(0).astype(int)
    df['Should_Trigger'] = df.apply(should_trigger, axis=1)

    eligible = df[df['Should_Trigger']]
    ranked = eligible.sort_values(['Segment_Priority', 'Monetary'], ascending=[False, False]).head(top_n)

    return ranked[['Customer ID', 'Segment_Tag', 'Recency', 'Monetary', 'Segment_Priority']]


def map_customer_journey_and_affinity(transactions_df: pd.DataFrame, customer_id=None):
    df = transactions_df.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Customer ID'] = df['Customer ID'].astype(str)
    if customer_id is not None:
        df = df[df['Customer ID'] == str(customer_id)]

    df = df.sort_values(['Customer ID', 'Date'])
    df['Purchase_Order'] = df.groupby('Customer ID')['Date'].rank(method='dense').astype(int)

    journey = df[['Customer ID', 'Purchase_Order', 'Sub Category']]

    # Transitions
    grp = df.groupby(['Customer ID', 'Purchase_Order'])['Sub Category'].apply(lambda x: list(set(x))).reset_index()
    grp['Next'] = grp.groupby('Customer ID')['Sub Category'].shift(-1)
    grp = grp.dropna(subset=['Next'])

    trans = []
    for _, row in grp.iterrows():
        for a in row['Sub Category']:
            for b in row['Next']:
                trans.append((a, b))

    trans_df = pd.DataFrame(Counter(trans).items(), columns=['Pair', 'Count'])
    if not trans_df.empty:
        trans_df[['From', 'To']] = pd.DataFrame(trans_df['Pair'].tolist(), index=trans_df.index)
        trans_df.drop(columns='Pair', inplace=True)

    # Affinity
    co_occur = []
    for _, group in df.groupby(['Customer ID', 'Invoice ID']):
        items = sorted(set(group['Sub Category']))
        co_occur.extend(combinations(items, 2))

    aff_df = pd.DataFrame(Counter(co_occur).items(), columns=['Pair', 'Count'])
    if not aff_df.empty:
        aff_df[['Sub1', 'Sub2']] = pd.DataFrame(aff_df['Pair'].tolist(), index=aff_df.index)
        aff_df.drop(columns='Pair', inplace=True)

    return {
        'journey_path': journey,
        'journey_transitions': trans_df,
        'affinity_pairs': aff_df
    }


def generate_personal_offer(transactions_df: pd.DataFrame, cust_df=None, customer_id=None) -> str:
    rfm = calculate_rfm(transactions_df)
    rfm = assign_segment_tags(rfm)
    targets = get_campaign_targets(rfm)

    if targets.empty:
        return "No eligible customers for today's campaign."

    # ✅ Always keep Customer ID as string
    top_cid = str(customer_id) if customer_id else str(targets.iloc[0]['Customer ID'])

    journey = map_customer_journey_and_affinity(transactions_df, customer_id=top_cid)

    # Next best category
    trans = journey['journey_transitions']
    trans = trans[trans['From'] != trans['To']] if not trans.empty else pd.DataFrame()

    if not trans.empty and 'To' in trans.columns and trans['To'].notna().any():
        next_cat_series = trans.groupby('To')['Count'].sum()
        next_cat = next_cat_series.idxmax() if not next_cat_series.empty else "your favorite category"
    else:
        next_cat = "your favorite category"

    # Bundle
    aff = journey['affinity_pairs']
    if not aff.empty:
        top_bundle = aff.sort_values('Count', ascending=False).iloc[0]
        bundle = f"{top_bundle['Sub1']} + {top_bundle['Sub2']}"
    else:
        bundle = "a matching item"

    # Customer info
    name, phone = "Valued Customer", "N/A"
    if cust_df is not None and top_cid in cust_df['Customer ID'].astype(str).values:
        row = cust_df[cust_df['Customer ID'].astype(str) == top_cid].iloc[0]
        name = row.get('Customer Name', row.get('Name', name))
        phone = row.get('Mobile Number', row.get('Telephone', phone))

    return (
        f"📣 Hi **{name}** (📱 {phone})!\n\n"
        f"You’re eligible for a special offer on **{next_cat}**, "
        f"plus discounts on a **bundle of {bundle}**.\n"
        "Don’t miss this personalized deal crafted just for you!"
    )
