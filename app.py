import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# 1. Set Page to Wide Mode
st.set_page_config(page_title="Equity Value Advisor", page_icon="📈", layout="wide")

# --- Camouflage & Caching ---
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}

@st.cache_data(ttl=3600)
def get_stock_data(ticker):
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        stock = yf.Ticker(ticker.upper(), session=session)
        info = stock.info
        if not info or 'marketCap' not in info: return None
        return {
            "Ticker": ticker.upper(),
            "EV/EBITDA": info.get("enterpriseToEbitda", 15),
            "FCF Yield": (info.get("freeCashflow", 0) / info.get("marketCap", 1)) if info.get("freeCashflow") else 0.05,
            "Revenue Growth": info.get("revenueGrowth", 0.1),
            "Op Margin": info.get("operatingMargins", 0.1),
            "P/S Ratio": info.get("priceToSalesTrailing12Months", 3)
        }
    except: return None

# --- UI Header ---
st.title("📈 Personal Equity Value Advisor")
st.markdown("---")

input_col, result_col = st.columns([1, 1.2], gap="large")

with input_col:
    st.header("🛠️ Analysis Inputs")
    with st.container(border=True):
        st.subheader("1. Target Asset")
        target_ticker = st.text_input("Enter Ticker", value="AMZN").upper()
        sentiment = st.slider("Conviction Score (1-10)", 1, 10, 5, help="5 is Neutral.")

    st.subheader("2. Peer Groups")
    st.info("💡 **Blended Industry Guide:** Use Group 1 for direct competitors and Group 2 for secondary sectors.")
    peer_groups = []
    total_weight = 0
    for i in range(1, 3):
        with st.expander(f"Peer Group {i}", expanded=(i==1)):
            weight = st.number_input(f"Similarity %", min_value=0, max_value=100, value=100 if i==1 else 0, key=f"w{i}")
            tickers = st.text_input(f"Tickers (comma separated)", key=f"t{i}", value="WMT, COST" if i==1 else "")
            if weight > 0 and tickers:
                peer_groups.append({"weight": weight / 100, "tickers": [t.strip().upper() for t in tickers.split(",")]})
                total_weight += weight

    run_analysis = st.button("🚀 Run Valuation Analysis", type="primary", use_container_width=True)

with result_col:
    if run_analysis:
        if total_weight != 100:
            st.error(f"Total similarity must be 100% (Current: {total_weight}%)")
        else:
            target_data = get_stock_data(target_ticker)
            if not target_data:
                st.error("Ticker not found.")
            else:
                metrics = ["EV/EBITDA", "FCF Yield", "Revenue Growth", "Op Margin", "P/S Ratio"]
                q_weights = {"EV/EBITDA": 0.30, "FCF Yield": 0.25, "Revenue Growth": 0.20, "Op Margin": 0.15, "P/S Ratio": 0.10}
                benchmarks = {m: 0 for m in metrics}

                for group in peer_groups:
                    group_metrics = [get_stock_data(t) for t in group['tickers'] if get_stock_data(t)]
                    if group_metrics:
                        df_p = pd.DataFrame(group_metrics)
                        for m in metrics: benchmarks[m] += df_p[m].mean() * group['weight']

                quant_score = sum((benchmarks[m]/target_data[m] if m in ["EV/EBITDA", "P/S Ratio"] else target_data[m]/benchmarks[m]) * q_weights[m] for m in metrics)
                sentiment_adj = (sentiment - 5) * 0.04
                final_signal = quant_score + sentiment_adj

                # --- AI Summary Logic ---
                if final_signal > 1.10:
                    summary = f"{target_ticker} is displaying strong relative value because its growth and margins significantly outpace the peer benchmark despite trading at a more attractive earnings multiple. The model suggests the market may be underpricing its operational efficiency relative to {peer_groups[0]['tickers'][0]}."
                elif final_signal < 0.90:
                    summary = f"{target_ticker} appears overvalued relative to this peer group. Its current price-to-sales or EBITDA multiples are at a significant premium that is not fully justified by its underlying growth rates compared to the selected benchmarks."
                else:
                    summary = f"The valuation for {target_ticker} is currently in-line with the peer group. Its market premium is fairly balanced by its relative performance in revenue growth and operating margins."

                st.header(f"Results for {target_ticker}")
                st.info(f"**AI Insight:** {summary}")
                
                col_a, col_b = st.columns(2)
                col_a.metric("Final Value Score", f"{final_signal:.2%}", delta=f"{sentiment_adj:+.1%} Sentiment")
                if final_signal > 1.05: col_b.success("SIGNAL: BUY")
                elif final_signal < 0.95: col_b.error("SIGNAL: SELL")
                else: col_b.warning("SIGNAL: HOLD")

                chart_data = pd.DataFrame({"Metric": metrics, "Target": [target_data[m] for m in metrics], "Peer Avg": [benchmarks[m] for m in metrics]}).set_index("Metric")
                st.bar_chart(chart_data)
                st.table(chart_data.style.format("{:.2f}"))
