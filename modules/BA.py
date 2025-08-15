import streamlit as st
import pandas as pd
import json
import plotly.express as px
import chardet
from io import BytesIO
import requests

def run_business_analyst_tab():
    

    # --- Gemini API Setup ---
    GEMINI_API_KEY = "AIzaSyD9DfnqPz7vMgh5aUHaMAVjeJbg20VZMvU"
    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    # --- Load CSV or Excel Smartly ---
    def load_data_smart(file):
        try:
            raw = file.read()
            if file.name.endswith(".csv"):
                encoding = chardet.detect(raw)["encoding"] or "ISO-8859-1"
                return pd.read_csv(BytesIO(raw), encoding=encoding)
            elif file.name.endswith(".xlsx"):
                return pd.read_excel(BytesIO(raw), engine="openpyxl")
            else:
                st.error("Unsupported file format. Upload CSV or Excel.")
                return pd.DataFrame()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            return pd.DataFrame()

    # --- Ask Gemini API ---
    def ask_llm(prompt):
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GEMINI_API_KEY
        }
        body = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        try:
            response = requests.post(GEMINI_URL, headers=headers, json=body)
            response.raise_for_status()
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"\u274c Gemini Error: {e}"

    # --- Generate Business Insights ---
    def get_insights_list(df):
        preview = df.head(15).to_string(index=False)
        prompt = f"""
    You are a McKinsey-Partner level business consultant.
    List down all the insights then what measure we should take then check doability and possible outcome from it and then sort it in manner like highest impact with highest doability first.
    while giving insights make sure to consider average and total carefully some time sum, average and median all can give differnt insights but it is your duty to understand which is most appropriate to use.
    You can follow following structure because for every business main issue will be profitability:
    1. Profit is made of Revenue and cost so analyze that at high level.
    2. Dig deeper into these things and understand what is causing problem (Root cause analysis)
    3. Build hypothesis for solution and then after checking them
    4. Give insights

    In insights also, after giving decision tell how can they do like dig deeper into the insights and give lowest level detail and step


    Based on the dataset below, give 3-5 insights as JSON with:
    - decision
    - observation
    - why_it_matters
    - action
    - impact (with numbers)
    try to add numbers in insights title.
    Avoid long sentences. JSON format:
    [
    {{
        "decision": "...",
        "observation": "...",
        "why_it_matters": "...",
        "action": "...",
        "impact": "..."
    }}
    ]

    Data:
    {preview}
    """
        raw = ask_llm(prompt)
        raw = raw.split("```json")[-1].split("```")[0] if "```" in raw else raw
        try:
            return json.loads(raw)
        except Exception as e:
            st.warning(f"\u26a0\ufe0f Failed to parse insights JSON: {e}")
            return []

    # --- Recommend a Chart for Each Insight ---
    def get_chart_spec_from_insight(df, insight_text):
        column_list = ", ".join(df.columns.tolist())
        prompt = f"""
    You are a data visualization expert who know all type of visualizations and know how to show the insights in best possible way.
    while giving graph, make sure that, that particular graph shows what is stated in the insights.
    Make sure to that you show particular things which are mentioned in insights.

    please please and please decide which graph to show based in observation part of insights text or the text I will give below.
    decide X axis and Y axis very very carefully.
    Dataset Columns: {column_list}

    Given this business insight:
    \"{insight_text}\"

    Return a JSON with:
    {{
    "chart_type": "bar" or "scatter" or "line" or "pie",
    "x": "column_name",
    "y": "single column OR multiple columns for comparison (as a list if needed, e.g., ['Sales', 'Profit'])",
    "title": "Descriptive title"
    }}

    Important:
    - Use averages or ratios instead of raw totals when comparing groups like 'Ship Mode', 'Region', or 'Segment'.
    - For example, prefer "average profit per order" instead of total profit if some categories have fewer records.
    - Always try to normalize for number of orders or sales volume to avoid misleading comparisons.
    - decide which graph to show based in action part of insights text or the text I gave.
    Only use column names that exist in the dataset or can be derived from it.
    Return only the JSON.

    Only use column names from the dataset. Return nothing else.
    """
        response = ask_llm(prompt)
        try:
            if "```json" in response:
                response = response.split("```json")[-1]
            if "```" in response:
                response = response.split("```")[0]
            return json.loads(response)
        except Exception as e:
            st.warning(f"⚠️ Failed to parse chart spec: {e}")
            return None


    # --- Generate Plotly Chart ---
    # --- Generate Plotly Chart ---
    def generate_chart(df, spec):
        try:
            chart_type, x, y = spec["chart_type"].lower(), spec["x"], spec["y"]
            title = spec.get("title", "Chart")

            # Handle derived columns
            if isinstance(y, str) and "/" in y:
                num_col, denom_col = [col.strip() for col in y.split("/")]
                if num_col in df.columns and denom_col in df.columns:
                    df[y] = df[num_col] / df[denom_col]
                else:
                    st.error(f"❌ One of the columns '{num_col}' or '{denom_col}' for derived y is missing.")
                    return None

            if x not in df.columns and 'date' in x.lower():
                try:
                    df[x] = pd.to_datetime(df[x], errors='coerce')
                    df = df.dropna(subset=[x])
                    df[x] = df[x].dt.to_period('M').dt.to_timestamp()
                except Exception as e:
                    st.warning(f"⚠️ Failed to create derived date column '{x}': {e}")

            if isinstance(y, str) and (x not in df.columns or y not in df.columns):
                st.error(f"❌ Column '{x}' or '{y}' not in dataset.")
                return None

            df = df.dropna(subset=[x] + ([y] if isinstance(y, str) else y))

            # Handle datetime properly if needed
            if pd.api.types.is_datetime64_any_dtype(df[x]) or 'date' in x.lower():
                try:
                    df[x] = pd.to_datetime(df[x], errors='coerce')
                    df = df.dropna(subset=[x])
                    df[x] = df[x].dt.to_period('M').dt.to_timestamp()
                except Exception as e:
                    st.warning(f"⚠️ Failed to parse dates in '{x}': {e}")

            # Try to detect color grouping column from title or actual values
            color_col = None
            title_lower = title.lower()
            possible_groups = ['Category', 'Sub-Category', 'Segment', 'Region', 'State']
            if any(kw in title_lower for kw in ['category', 'segment', 'region', 'state']):
                for col in possible_groups:
                    if col in df.columns:
                        color_col = col
                        break

            # Support multi-series explicitly defined in spec['y'] as a list
            if isinstance(y, list):
                df = df[[x] + y].copy()
                df = df.dropna()
                df = df.sort_values(by=x)
                df_melted = df.melt(id_vars=x, value_vars=y, var_name="Series", value_name="Value")

                if chart_type == "line":
                    fig = px.line(df_melted, x=x, y="Value", color="Series", title=title)
                elif chart_type == "bar":
                    fig = px.bar(df_melted, x=x, y="Value", color="Series", title=title, barmode="group")
                elif chart_type == "scatter":
                    fig = px.scatter(df_melted, x=x, y="Value", color="Series", title=title)
                else:
                    st.warning("Multi-series not supported for this chart type.")
                    return None

                fig.update_layout(xaxis_tickangle=-45, margin=dict(l=40, r=40, t=60, b=120), plot_bgcolor="rgba(0,0,0,0)")
                return fig

            # Group data properly
            if chart_type == "pie":
                df = df[[x, y]].copy()
                df = df.groupby(x)[y].sum().reset_index()
            elif color_col:
                df = df[[x, y, color_col]].copy()
                df = df.groupby([x, color_col])[y].sum().reset_index()
            else:
                df = df[[x, y]].copy()
                df = df.groupby(x)[y].sum().reset_index()

            df = df.sort_values(by=x)

            # Plot based on chart type
            if chart_type == "bar":
                fig = px.bar(df, x=x, y=y, color=color_col, title=title)
            elif chart_type == "line":
                fig = px.line(df, x=x, y=y, color=color_col, title=title)
            elif chart_type == "scatter":
                fig = px.scatter(df, x=x, y=y, color=color_col, title=title)
            elif chart_type == "pie":
                fig = px.pie(df, names=x, values=y, title=title)
            else:
                st.warning("Unsupported chart type.")
                return None

            fig.update_layout(
                xaxis_tickangle=-45,
                margin=dict(l=40, r=40, t=60, b=120),
                plot_bgcolor="rgba(0,0,0,0)"
            )
            return fig
        except Exception as e:
            st.error(f"Chart error: {e}")
            return None


    # --- Streamlit UI ---
    st.set_page_config(page_title="\U0001f9e0 Insight-by-Insight Analyst", layout="wide")
    st.title("\U0001f916 Gemini-Powered Insight Visualizer")

    uploaded_file = st.file_uploader("\U0001f4c1 Upload CSV or Excel", type=["csv", "xlsx"])

    if uploaded_file:
        df = load_data_smart(uploaded_file)
        if not df.empty:
            st.subheader("\U0001f4c8 Data Preview")
            st.dataframe(df.head(20))

            st.subheader("\U0001f50d Insight-by-Insight Analysis")
            with st.spinner("Analyzing..."):
                insights = get_insights_list(df)

            for i, ins in enumerate(insights):
                st.markdown(f"### \U0001f52e Insight {i+1}: {ins.get('decision')}")
                st.markdown(f"- **Observation:** {ins.get('observation')}")
                st.markdown(f"- **Why it matters:** {ins.get('why_it_matters')}")
                st.markdown(f"- **Action:** {ins.get('action')}")
                st.markdown(f"- **Impact:** {ins.get('impact')}")

                with st.spinner("Generating chart..."):
                    spec = get_chart_spec_from_insight(df, ins.get("decision"))
                    if spec:
                        fig = generate_chart(df, spec)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("\u26a0\ufe0f Couldn't generate chart.")
                    else:
                        st.warning("\u26a0\ufe0f No chart suggested.")
