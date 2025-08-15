import streamlit as st

def generate_dynamic_insights(insights: dict):
    st.markdown("### 📌 Key Dynamic Insights")

    if not insights or 'monthly_summary' not in insights:
        st.warning("Insufficient data to generate insights.")
        return

    try:
        messages = []

        # Sales change insight
        if 'Sales Change (%)' in insights['monthly_summary'].columns:
            change = insights['monthly_summary']['Sales Change (%)'].iloc[-1]
            if change > 10:
                messages.append(f"📈 Sales increased by **{change:.1f}%** last month. Push more of what's working.")
            elif change < -10:
                messages.append(f"📉 Sales dropped by **{abs(change):.1f}%**. Investigate reasons — pricing, returns, or demand shifts.")
            else:
                messages.append(f"🔄 Sales are stable. Look for incremental wins through product bundling or upselling.")

        # Profitability check
        if insights.get('profit_margin') is not None:
            if insights['profit_margin'] > 40:
                messages.append(f"💰 Profit margin is **excellent ({insights['profit_margin']:.1f}%)**. Consider scaling or running promotions.")
            elif insights['profit_margin'] < 20:
                messages.append(f"⚠️ Low profit margin (**{insights['profit_margin']:.1f}%)**. Review discounting and supplier costs.")

        # Returns
        if insights['total_returns'] > 0:
            return_pct = abs(insights['total_returns']) / insights['total_sales'] * 100 if insights['total_sales'] else 0
            if return_pct > 10:
                messages.append(f"↩️ Return rate is **{return_pct:.1f}%** — monitor quality, logistics, and product issues.")

        # Units sold
        if insights['total_units'] > 1000:
            messages.append("🚚 Strong demand — Units sold crossed 1,000. Prepare inventory for continued momentum.")

        # Customers
        if insights['active_customers'] < 100:
            messages.append("👥 Low active customers. Consider loyalty offers or reactivation campaigns.")
        else:
            messages.append(f"🌟 {insights['active_customers']} unique customers purchased last month. Identify your champions!")

        for msg in messages:
            st.success(msg)

    except Exception as e:
        st.error(f"Error generating insights: {e}")
