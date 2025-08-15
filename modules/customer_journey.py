import pandas as pd
from itertools import combinations
from collections import Counter


def map_customer_journey_and_affinity(filtered_df, customer_id=None):
    df = filtered_df.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    if customer_id:
        df = df[df['Customer ID'] == customer_id]

    df = df.sort_values(by=['Customer ID', 'Date'])
    df['Purchase_Order'] = df.groupby(['Customer ID'])['Date'].rank(method='dense').astype(int)

    # ✅ Journey path (for plotting or analysis)
    journey_path_df = df[['Customer ID', 'Purchase_Order', 'Sub Category']].copy()

    # ✅ Customer journey transitions
    grouped = df.groupby(['Customer ID', 'Purchase_Order'])['Sub Category'].apply(lambda x: list(set(x))).reset_index()
    grouped['Next_Sub_Category'] = grouped.groupby('Customer ID')['Sub Category'].shift(-1)
    grouped = grouped.dropna()

    transitions = []
    for _, row in grouped.iterrows():
        from_cats = row['Sub Category']
        to_cats = row['Next_Sub_Category']
        for f in from_cats:
            for t in to_cats:
                transitions.append((f, t))

    transition_counts = pd.DataFrame(Counter(transitions).items(), columns=['Transition', 'Count'])
    if not transition_counts.empty:
        transition_counts[['From', 'To']] = pd.DataFrame(transition_counts['Transition'].tolist(), index=transition_counts.index)
        transition_counts.drop(columns='Transition', inplace=True)

    # ✅ Product affinity within same invoice
    co_occur = []
    for _, group in df.groupby(['Customer ID', 'Invoice ID']):
        items = list(set(group['Sub Category']))
        for combo in combinations(sorted(items), 2):
            co_occur.append(combo)

    affinity_counts = pd.DataFrame(Counter(co_occur).items(), columns=['Pair', 'Count'])
    if not affinity_counts.empty:
        affinity_counts[['SubCategory_1', 'SubCategory_2']] = pd.DataFrame(affinity_counts['Pair'].tolist(), index=affinity_counts.index)
        affinity_counts.drop(columns='Pair', inplace=True)

    return {
        "journey_path": journey_path_df,
        "journey_transitions": transition_counts,
        "affinity_pairs": affinity_counts
    }


def generate_behavioral_recommendation_with_impact(customer_id, journey_df, affinity_pairs_df, filtered_df):
    # ✅ Validate inputs
    if journey_df is None or affinity_pairs_df is None or journey_df.empty or affinity_pairs_df.empty:
        return f"⚠️ No data available for customer ID {customer_id}."

    customer_df = filtered_df[filtered_df['Customer ID'] == customer_id]
    if customer_df.empty:
        return f"⚠️ No transaction data for customer ID {customer_id}."

    # ✅ Build journey string
    journey_path = journey_df.sort_values(by='Purchase_Order')['Sub Category'].dropna().tolist()
    journey_str = " → ".join(journey_path)

    # ✅ Top affinity pairs
    top_pairs = affinity_pairs_df.sort_values(by='Count', ascending=False).head(2)

    # ✅ Spending metrics
    total_spent = customer_df['Invoice Total'].sum()
    total_orders = customer_df['Invoice ID'].nunique()
    aov = total_spent / total_orders if total_orders > 0 else 0
    uplift_rate = 0.15

    # ✅ Build recommendation string
    rec = f"🧭 Customer Journey — ID: {customer_id}\n"
    rec += f"Journey: {journey_str}\n"
    rec += f"Orders: {total_orders} | Total Spend: ₹{total_spent:.2f} | AOV: ₹{aov:.2f}\n\n"

    rec += f"📈 Product Affinity Highlights:\n"
    impact_rows = []
    for _, row in top_pairs.iterrows():
        pair = f"{row['SubCategory_1']} + {row['SubCategory_2']}"
        strength = row['Count']
        expected_uplift = aov * uplift_rate
        rec += f"- {pair}: co-purchased {strength} times → Suggest bundle (Est. uplift: ₹{expected_uplift:.2f})\n"
        impact_rows.append((pair, expected_uplift))

    total_est_uplift = sum(x[1] for x in impact_rows)

    rec += "\n💡 Recommendations:\n"
    for pair, uplift in impact_rows:
        rec += f"- Bundle: {pair} → Expected uplift ₹{uplift:.2f}\n"

    rec += f"\n📊 Overall Potential Impact: ₹{total_est_uplift:.2f} per future order\n"
    return rec
