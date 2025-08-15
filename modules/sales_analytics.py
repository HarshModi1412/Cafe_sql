import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np


def generate_sales_insights(txns_df):
    df = txns_df.copy()

    # Ensure required columns
    required = ['Date', 'Quantity', 'Invoice ID', 'Customer ID',
                'Sub Category', 'Product ID', 'Discount']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    has_cost = 'Production Cost' in df.columns and df['Production Cost'].notna().any()

    # Handle Invoice Total
    if 'Invoice Total' not in df.columns:
        if 'Unit Price' in df.columns:
            df['Invoice Total'] = df['Quantity'] * df['Unit Price']
        else:
            raise ValueError("Missing both 'Invoice Total' and 'Unit Price'. One is required.")

    # Convert date
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Month'] = df['Date'].dt.to_period('M').astype(str)
    df['DayOfWeek'] = df['Date'].dt.day_name()

    # Handle Transaction Type if present
    if 'Transaction Type' in df.columns:
        df['Transaction Type'] = df['Transaction Type'].astype(str).str.strip().str.lower()
        has_sale = df['Transaction Type'].str.contains('sale').any()
        has_return = df['Transaction Type'].str.contains('return').any()

        if has_sale or has_return:
            sales_df = df[df['Transaction Type'].str.contains('sale')]
            return_df = df[df['Transaction Type'].str.contains('return')]
        else:
            sales_df = df.copy()
            return_df = df.iloc[0:0]  # empty return dataframe
    else:
        sales_df = df.copy()
        return_df = df.iloc[0:0]

    # KPIs
    total_sales = sales_df['Invoice Total'].sum()
    total_returns = return_df['Invoice Total'].sum()
    net_sales = total_sales + total_returns
    total_units = sales_df['Quantity'].sum()
    num_orders = sales_df['Invoice ID'].nunique()
    avg_order_value = net_sales / num_orders if num_orders else 0
    active_customers = sales_df['Customer ID'].nunique()

    # Profit if cost available
    gross_profit = None
    profit_margin = None
    if has_cost:
        gross_profit = total_sales - sales_df['Production Cost'].fillna(0).sum()
        profit_margin = (gross_profit / total_sales) * 100 if total_sales else 0

    # Monthly Trends
    monthly_sales = sales_df.groupby('Month')['Invoice Total'].sum()
    monthly_returns = return_df.groupby('Month')['Invoice Total'].sum()
    monthly_summary = pd.concat([
        monthly_sales.rename("Sales"),
        monthly_returns.rename("Returns")
    ], axis=1).fillna(0)

    if has_cost:
        monthly_costs = sales_df.groupby('Month')['Production Cost'].sum()
        monthly_profit = monthly_sales - monthly_costs
        monthly_summary['Costs'] = monthly_costs
        monthly_summary['Profit'] = monthly_profit

    monthly_summary['Net Sales'] = monthly_summary['Sales'] + monthly_summary['Returns']
    monthly_summary['Sales Change (%)'] = monthly_summary['Sales'].pct_change() * 100
    monthly_summary = monthly_summary.reset_index()

    # Subcategory Profitability
    subcat_sales = sales_df.groupby('Sub Category')['Invoice Total'].sum().reset_index()
    if has_cost:
        subcat_cost = sales_df.groupby('Sub Category')['Production Cost'].sum().reset_index()
        subcat_sales = subcat_sales.merge(subcat_cost, on='Sub Category')
        subcat_sales['Gross Profit'] = subcat_sales['Invoice Total'] - subcat_sales['Production Cost']
        subcat_sales = subcat_sales.sort_values(by='Gross Profit', ascending=False)

    # Top Products
    top_products = sales_df.groupby('Product ID')['Invoice Total'].sum().reset_index()
    top_products = top_products.sort_values(by='Invoice Total', ascending=False).head(10)

    # Day of Week Sales
    dow_sales = sales_df.groupby('DayOfWeek')['Invoice Total'].sum().reindex([
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
    ]).reset_index()

    # Discount Analysis
    discount_effectiveness = sales_df[sales_df['Discount'] > 0].groupby('Discount')['Invoice Total'].sum().reset_index()

    # Insight
    if len(monthly_summary) >= 2:
        change = monthly_summary['Sales Change (%)'].iloc[-1]
        latest = monthly_summary['Month'].iloc[-1]
        prev = monthly_summary['Month'].iloc[-2]

        if change < -5:
            insight = f"📉 Sales dropped by {change:.1f}% in {latest} vs {prev}. Investigate returns and sub-category dips."
        elif change > 5:
            insight = f"📈 Sales grew by {change:.1f}% in {latest}. Consider pushing winning SKUs further."
        else:
            insight = f"📊 Sales steady in {latest}. Try bundling or loyalty offers for more uplift."
    else:
        insight = "Not enough data for trend analysis."

    return {
        'total_sales': total_sales,
        'total_returns': total_returns,
        'net_sales': net_sales,
        'total_units': total_units,
        'avg_order_value': avg_order_value,
        'active_customers': active_customers,
        'gross_profit': gross_profit,
        'profit_margin': profit_margin,
        'monthly_summary': monthly_summary,
        'subcat_sales': subcat_sales,
        'top_products': top_products,
        'dow_sales': dow_sales,
        'discount_effectiveness': discount_effectiveness,
        'insight': insight
    }


def render_sales_analytics(txns_df):
    st.subheader("📈 Sales Analytics Dashboard")

    if txns_df is None or txns_df.empty:
        st.warning("Please upload transaction data.")
        return

    if st.button("🚀 Start Sales Analytics"):
        st.write("⏳ Running analysis...")

        try:
            insights = generate_sales_insights(txns_df)
        except Exception as e:
            st.error(f"⚠️ Error in processing: {e}")
            return

        # KPI Tiles
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Total Sales", f"₹{insights['total_sales']:,.0f}")
        col2.metric("🔻 Returns", f"₹{insights['total_returns']:,.0f}")
        col3.metric("🧾 Avg Order Value", f"₹{insights['avg_order_value']:,.0f}")
        col4.metric("👥 Active Customers", f"{insights['active_customers']:,}")

        col5, col6, col7 = st.columns(3)
        col5.metric("📦 Units Sold", f"{insights['total_units']:,.0f}")
        col6.metric("💸 Net Sales", f"₹{insights['net_sales']:,.0f}")

        if insights['gross_profit'] is not None:
            col7.metric("📊 Gross Profit", f"₹{insights['gross_profit']:,.0f}", f"{insights['profit_margin']:.1f}% margin")
        else:
            col7.write("📊 Gross Profit data not available")

        st.markdown("---")

        # Monthly Trends - Line Chart
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(x=insights['monthly_summary']['Month'], y=insights['monthly_summary']['Sales'],
                                      mode='lines+markers', name='Sales'))
        fig_line.add_trace(go.Scatter(x=insights['monthly_summary']['Month'], y=insights['monthly_summary']['Returns'],
                                      mode='lines+markers', name='Returns'))
        fig_line.add_trace(go.Scatter(x=insights['monthly_summary']['Month'], y=insights['monthly_summary']['Net Sales'],
                                      mode='lines+markers', name='Net Sales'))
        if 'Profit' in insights['monthly_summary'].columns:
            fig_line.add_trace(go.Scatter(x=insights['monthly_summary']['Month'], y=insights['monthly_summary']['Profit'],
                                          mode='lines+markers', name='Profit'))
        fig_line.update_layout(title="📉 Sales, Returns, Net Sales & Profit Over Time")
        st.plotly_chart(fig_line, use_container_width=True)

        # Sub-category Performance - Bar
        if 'Gross Profit' in insights['subcat_sales'].columns:
            fig2 = px.bar(insights['subcat_sales'], x='Sub Category', y='Gross Profit',
                          title="🏷️ Gross Profit by Sub-Category", text_auto='.2s')
        else:
            fig2 = px.bar(insights['subcat_sales'], x='Sub Category', y='Invoice Total',
                          title="🏷️ Sales by Sub-Category", text_auto='.2s')
        st.plotly_chart(fig2, use_container_width=True)

        # Day of Week - Bar
        fig3 = px.bar(insights['dow_sales'], x='DayOfWeek', y='Invoice Total',
                      title="🗓️ Sales by Day of Week", text_auto='.2s')
        st.plotly_chart(fig3, use_container_width=True)

        # Discount Analysis - Bar
        # Show gross profit if available; else show Invoice Total
        if 'Production Cost' in txns_df.columns and txns_df['Production Cost'].notna().any():
            # Calculate discount effectiveness with gross profit per discount
            discount_df = insights['discount_effectiveness'].copy()
            # We cannot calculate gross profit here directly without product cost info, so just show Invoice Total
            y_field = 'Invoice Total'
            title = "🎯 Discount vs Sales"
        else:
            discount_df = insights['discount_effectiveness']
            y_field = 'Invoice Total'
            title = "🎯 Discount vs Sales"

        fig4 = px.bar(discount_df, x='Discount', y=y_field,
                      title=title, text_auto='.2s')
        st.plotly_chart(fig4, use_container_width=True)

        st.markdown("---")
        st.subheader("💡 Actionable Insight")
        st.success(insights['insight'])

def render_subcategory_trends(txns_df):
    st.subheader("📌 Sub-Category Trends Dashboard")

    if txns_df is None or txns_df.empty:
        st.warning("Please upload transaction data.")
        return

    df = txns_df.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])

    # Extract month and day of week
    df['Month'] = df['Date'].dt.to_period('M').astype(str)
    df['DayOfWeek'] = df['Date'].dt.day_name()

    # Optional: Filter to sales only if Transaction Type column exists
    if 'Transaction Type' in df.columns:
        df['Transaction Type'] = df['Transaction Type'].astype(str).str.lower().str.strip()
        if df['Transaction Type'].str.contains('sale').any():
            df = df[df['Transaction Type'].str.contains('sale', na=False)]

    # Check for Sub Category
    if 'Sub Category' not in df.columns or df['Sub Category'].dropna().empty:
        st.warning("⚠️ No valid 'Sub Category' data found.")
        return

    subcats = sorted(df['Sub Category'].dropna().unique())
    selected_subcat = st.selectbox("Choose a Sub-Category", subcats)
    sub_df = df[df['Sub Category'] == selected_subcat]

    if sub_df.empty:
        st.warning("No data found for this sub-category.")
        return

    # Monthly trend
    trend_df = sub_df.groupby('Month').agg({
        'Invoice Total': 'sum',
        'Production Cost': 'sum' if 'Production Cost' in sub_df.columns else 'size',
        'Quantity': 'sum'
    }).rename(columns={'Production Cost': 'Production Cost'}).reset_index()

    if 'Production Cost' in trend_df.columns:
        trend_df['Gross Profit'] = trend_df['Invoice Total'] - trend_df['Production Cost']
        trend_df['Profit Margin (%)'] = (trend_df['Gross Profit'] / trend_df['Invoice Total']) * 100
    else:
        trend_df['Gross Profit'] = np.nan
        trend_df['Profit Margin (%)'] = np.nan

    st.plotly_chart(
        go.Figure([
            go.Scatter(x=trend_df['Month'], y=trend_df['Invoice Total'], mode='lines+markers', name='Sales'),
            go.Scatter(x=trend_df['Month'], y=trend_df['Gross Profit'], mode='lines+markers', name='Gross Profit'),
            go.Scatter(x=trend_df['Month'], y=trend_df['Quantity'], mode='lines+markers', name='Units Sold')
        ]).update_layout(
            title=f"📊 Monthly Trend - {selected_subcat}",
            xaxis_title="Month",
            yaxis_title="Value",
            legend=dict(orientation='h', y=1.1),
            margin=dict(t=40, b=40)
        ),
        use_container_width=True
    )

    # Day-of-week pattern
    dow_df = sub_df.groupby('DayOfWeek').agg({'Invoice Total': 'sum', 'Quantity': 'sum'}).reindex([
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
    ]).reset_index()

    fig_dow = go.Figure([
        go.Bar(x=dow_df['DayOfWeek'], y=dow_df['Invoice Total'], name='Sales'),
        go.Scatter(x=dow_df['DayOfWeek'], y=dow_df['Quantity'], name='Units Sold', mode='lines+markers', yaxis='y2')
    ])
    fig_dow.update_layout(
        title=f"📅 Day of Week Sales Pattern - {selected_subcat}",
        xaxis_title="Day",
        yaxis=dict(title="Sales (₹)", side='left'),
        yaxis2=dict(title="Units Sold", overlaying='y', side='right'),
        legend=dict(orientation='h', y=1.15)
    )
    st.plotly_chart(fig_dow, use_container_width=True)

    # Smart Insights
    st.subheader("💡 Smart Insights")

    try:
        latest = trend_df.iloc[-1]
        avg_profit = trend_df['Gross Profit'].mean()
        growth_rate = trend_df['Invoice Total'].pct_change().iloc[-1] * 100 if len(trend_df) > 1 else 0
        best_day = dow_df.loc[dow_df['Invoice Total'].idxmax(), 'DayOfWeek']
        worst_day = dow_df.loc[dow_df['Invoice Total'].idxmin(), 'DayOfWeek']

        insights = []

        if growth_rate > 10:
            insights.append(f"📈 Sales for **{selected_subcat}** grew by **{growth_rate:.1f}%** last month. Expand inventory or offer combos.")
        elif growth_rate < -10:
            insights.append(f"📉 Sales dropped by **{abs(growth_rate):.1f}%**. Investigate price, stockouts, or competitor activity.")
        else:
            insights.append(f"🔄 Sales for **{selected_subcat}** remained steady. Consider small nudges like banner placements or bundling.")

        if not np.isnan(latest['Gross Profit']) and latest['Gross Profit'] < 0.8 * avg_profit:
            insights.append(f"⚠️ Profit this month is **below average**. Review COGS or pricing strategy.")

        if not np.isnan(latest['Profit Margin (%)']):
            if latest['Profit Margin (%)'] < 20:
                insights.append(f"💸 Low profit margin (**{latest['Profit Margin (%)']:.1f}%**). You may be **underpricing** or discounting too heavily.")
            elif latest['Profit Margin (%)'] > 50:
                insights.append(f"🚀 High margin (**{latest['Profit Margin (%)']:.1f}%**). Consider **scaling** via promotions or placement.")

        insights.append(f"📊 **Best day** for sales: **{best_day}**. Try pushing promotions here.")
        insights.append(f"😴 **Lowest sales** on: **{worst_day}**. Could test targeted nudges or restocking.")

        st.success("\n\n".join(insights))
    except Exception as e:
        st.warning(f"⚠️ Could not generate insights: {e}")

        st.warning(f"⚠️ Could not generate insights: {e}")

def generate_dynamic_insights(insights):
    st.subheader("📘 Smart Storytelling Insights")

    # === Monthly Sales Trend ===
    monthly = insights['monthly_summary']
    if len(monthly) >= 2:
        change = monthly['Sales'].pct_change().iloc[-1] * 100
        latest = monthly['Month'].iloc[-1]
        prev = monthly['Month'].iloc[-2]

        if change > 10:
            st.success(f"📈 Sales increased by **{change:.1f}%** in **{latest}** compared to **{prev}**. Expand fast-moving SKUs and consider replicating successful campaigns.")
        elif change < -10:
            st.error(f"📉 Sales dropped by **{abs(change):.1f}%** in **{latest}**. Investigate sub-category declines, returns, or discount strategy.")
        else:
            st.info(f"📊 Sales remained relatively stable in **{latest}**. Consider A/B testing bundles or minor discount tweaks.")

    else:
        st.warning("Not enough monthly data to analyze sales trend.")

    # === Sub-Category Profitability ===
    subcat_df = insights['subcat_sales']
    if not subcat_df.empty:
        if 'Gross Profit' in subcat_df.columns:
            top = subcat_df.iloc[0]
            bottom = subcat_df.iloc[-1]

            st.markdown(f"""
🏷️ **Sub-Category Performance**
- 🥇 Top performer: **{top['Sub Category']}** — ₹{top['Gross Profit']:,.0f} profit  
- 🛑 Lowest performer: **{bottom['Sub Category']}** — ₹{bottom['Gross Profit']:,.0f} profit  
""")
        else:
            top = subcat_df.sort_values(by='Invoice Total', ascending=False).iloc[0]
            st.markdown(f"""
🏷️ **Sub-Category Leader**
- 🛒 Highest sales from **{top['Sub Category']}** — ₹{top['Invoice Total']:,.0f}
""")

    # === Discount Effectiveness ===
    discount_df = insights['discount_effectiveness']
    if not discount_df.empty and 'Discount' in discount_df.columns:
        best = discount_df.loc[discount_df['Invoice Total'].idxmax()]
        worst = discount_df.loc[discount_df['Invoice Total'].idxmin()]
        st.markdown(f"""
🎯 **Discount Strategy Insights**
- 🎉 Best performing discount: **{best['Discount']}%** → ₹{best['Invoice Total']:,.0f} in sales  
- 💤 Least effective discount: **{worst['Discount']}%** → ₹{worst['Invoice Total']:,.0f}  
Consider optimizing the discount ladder to focus on sweet spots that convert.
""")

    # === Day of Week ===
    dow_df = insights['dow_sales']
    if not dow_df.empty:
        best_day = dow_df.loc[dow_df['Invoice Total'].idxmax(), 'DayOfWeek']
        worst_day = dow_df.loc[dow_df['Invoice Total'].idxmin(), 'DayOfWeek']
        st.markdown(f"""
📅 **Weekly Timing Insight**
- 🔥 Best sales day: **{best_day}** — maximize ads, email blasts or SMS offers here.  
- 😴 Slowest day: **{worst_day}** — test exclusive nudges, loyalty rewards, or restocking.
""")

    # === Gross Profit Margin ===
    if insights['profit_margin'] is not None:
        margin = insights['profit_margin']
        if margin < 20:
            st.error(f"💸 Low gross profit margin: **{margin:.1f}%**. You may be underpricing or running too many discounts.")
        elif margin > 50:
            st.success(f"💰 High margin (**{margin:.1f}%**) — opportunity to scale up with more volume or promotions.")

    st.markdown("---")


