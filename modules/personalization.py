import pandas as pd
from itertools import combinations
from collections import Counter

def compute_customer_preferences(filtered_df, customer_id=None):
    df = filtered_df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    if customer_id:
        df = df[df['Customer ID'] == customer_id]

    df = df.sort_values(by=['Customer ID', 'Date'])
    df['Purchase_Order'] = df.groupby('Customer ID')['Date'].rank(method='dense').astype(int)

    # --- Journey Mapping ---
    journey = df.groupby(['Customer ID', 'Purchase_Order'])['Sub Category'].apply(lambda x: list(set(x))).reset_index()
    journey['Next_Sub_Category'] = journey.groupby('Customer ID')['Sub Category'].shift(-1)
    journey = journey.dropna()

    transitions = []
    for _, row in journey.iterrows():
        from_cats = row['Sub Category']
        to_cats = row['Next_Sub_Category']
        for f in from_cats:
            for t in to_cats:
                transitions.append((f, t))
    transition_counts = pd.DataFrame(Counter(transitions).items(), columns=['Transition', 'Count'])
    transition_counts[['From', 'To']] = pd.DataFrame(transition_counts['Transition'].tolist(), index=transition_counts.index)
    transition_counts.drop(columns='Transition', inplace=True)

    # --- Product Affinity ---
    basket_sets = df.groupby(['Invoice ID'])['Sub Category'].apply(set).tolist()
    affinity_pairs = []
    for items in basket_sets:
        if len(items) > 1:
            for pair in combinations(sorted(items), 2):
                affinity_pairs.append(pair)
    affinity_counts = pd.DataFrame(Counter(affinity_pairs).items(), columns=['Pair', 'Count'])
    affinity_counts[['SubCategory_1', 'SubCategory_2']] = pd.DataFrame(affinity_counts['Pair'].tolist(), index=affinity_counts.index)
    affinity_counts.drop(columns='Pair', inplace=True)
    affinity_counts.sort_values(by='Count', ascending=False, inplace=True)

    # --- Final Outputs ---
    next_best_cat = None
    bundle_cat = None

    if customer_id:
        # Get top transition destination (most common "To" category)
        top_transition = (
            transition_counts.groupby('To')['Count'].sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        if not top_transition.empty:
            next_best_cat = top_transition.iloc[0]['To']

        # Get most frequent co-purchased category
        top_affinity = (
            affinity_counts.groupby('SubCategory_2')['Count'].sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        if not top_affinity.empty:
            bundle_cat = top_affinity.iloc[0]['SubCategory_2']

    return {
        'journey_transitions': transition_counts,
        'product_affinities': affinity_counts,
        'next_best_category': next_best_cat,
        'bundle_suggestion': bundle_cat
    }
