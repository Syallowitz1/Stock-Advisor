import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# 1. Set Page to Wide Mode (Uses full screen width)
st.set_page_config(page_title="Equity Value Advisor", page_icon="📈", layout="wide")

# --- Camouflage & Caching ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

@st.cache_data(ttl=3600)  # Caches data for 1 hour so it's instant after the first run
def get_stock_data(ticker):
    """Fetches key metrics from Yahoo Finance with caching to prevent blocking."""
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        stock = yf.Ticker(ticker.upper(), session=session)
        info = stock.info
        
        if not info or 'marketCap' not in info:
            return None
            
        return {
            "Ticker": ticker.upper(),
            "EV/EBITDA": info.get("enterpriseToEbitda", 15),
            "FCF Yield": (info.get("freeCashflow", 0) / info.get("marketCap", 1)) if info.get("freeCashflow") else 0.05,
            "Revenue Growth": info.get("revenueGrowth", 0.1),
            "Op Margin": info.get("operatingMargins", 0.1),
            "P/S Ratio": info.get("priceToSalesTrailing12Months", 3)
        }
    except:
        return None

# --- UI Header ---
st.title("📈 Personal Equity Value Advisor")
st.markdown("---")

# --- Layout: Split Screen ---
input_col, result_col = st.columns([1, 1.2], gap="large")

with input_col:
    st.header("🛠️ Analysis Inputs")
    
    # 1. Target Company
    with st.container(border=True):
        st.subheader("1. Target Asset")
        target_ticker = st.text_input("Enter Ticker (e.g. AMZN, SOFI, AAPL)", value="AMZN").upper()
        
        st.markdown("**Personal Conviction Score**")
        sentiment = st.slider("1 (Bearish) — 5 (Neutral) — 10 (Bullish)", 1, 10, 5, 
                             help="At 5, your sentiment does not affect the calculation. Above 5 boosts the value; below 5 penalizes it.")

    # 2. Peer Groups & Blended Weights
    st.subheader("2. Peer Groups")
    st.info("💡 **Blended Industry Guide:** If a company spans multiple industries (like Amazon: Retail + Cloud), create a group for each and assign weights based on their revenue contribution.")
    
    peer_groups = []
    total_weight = 0

    for i in range(1, 4):
        with st.expander(f"Peer Group {i} {'(Active)' if i==1 else ''}"):
            name = st.text_input(f"Industry Name", key=f"n{i}", value="Retail" if i==1 else "")
            weight = st.number_input(f"Similarity %", min_value=0, max_value=100, value=100 if i==1 else 0, key=f"w{i}")
            tickers = st.text_input(f"Tickers (comma separated)", key=f"t{i}", value="WMT, COST, TGT" if i==1 else "")
            
            if weight > 0 and tickers:
                peer_groups.append({
                    "weight": weight / 100,
                    "tickers": [t.strip().upper() for t in tickers.split(",")]
                })
                total_weight += weight

    # 3. Methodology Transparency
    with st.expander("🔍 View Valuation Methodology & Weights"):
        st.write("**Overall Weighting:**")
        st.write("- 📊 Quantitative Fundamentals: **80%**")
        st.write("- 🧠 Personal Conviction: **20%**")
        st.write("---")
        st.write("**Internal Quantitative Weights:**")
        st.write("- EV/EBITDA: 30% | FCF Yield: 25% | Rev Growth: 20% | Op Margin: 15% | P/S Ratio: 10%")

    run_analysis = st.button("🚀 Run Valuation Analysis", type="primary", use_container_width=True)

with result_col:
    if run_analysis:
        if total_weight != 100:
            st.error(f"Total similarity is {total_weight}%. Please adjust so it equals exactly 100%.")
        else:
            with st.spinner(f"Analyzing {target_ticker}..."):
                target_data = get_stock_data(target_ticker)
                
                if not target_data:
                    st.error(f"Data Fetch Error: Could not find {target_ticker}. Try a different ticker.")
                else:
                    # Logic Setup
                    metrics = ["EV/EBITDA", "FCF Yield", "Revenue Growth", "Op Margin", "P/S Ratio"]
                    q_weights = {"EV/EBITDA": 0.30, "FCF Yield": 0.25, "Revenue Growth": 0.20, "Op Margin": 0.15, "P/S Ratio": 0.10}
                    benchmarks = {m: 0 for m in metrics}

                    # Fetch Peer Data
                    for group in peer_groups:
                        group_metrics = []
                        for t in group['tickers']:
                            d = get_stock_data(t)
                            if d: group_metrics.append(d)
                        
                        if group_metrics:
                            df_p = pd.DataFrame(group_metrics)
                            for m in metrics:
                                benchmarks[m] += df_p[m].mean() * group['weight']

                    # Math: Quant Score
                    quant_score = 0
                    for m, w in q_weights.items():
                        if m in ["EV/EBITDA", "P/S Ratio"]: # Lower is better
                            score = benchmarks[m] / target_data[m] if target_data[m] != 0 else 1
                        else: # Higher is better
                            score = target_data[m] / benchmarks[m] if benchmarks[m] != 0 else 1
                        quant_score += (score * w)

                    # Math: Sentiment Adjustment (5 is neutral)
                    # Each point away from 5 adjusts the final score by 4% (Total 20% swing)
                    sentiment_adj = (sentiment - 5) * 0.04
                    final_signal = quant_score + sentiment_adj

                    # --- Display Results ---
                    st.header(f"Results for {target_ticker}")
                    
                    # 1. Big Signal
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("Final Value Score", f"{final_signal:.2%}", 
                                  delta=f"{sentiment_adj:+.1%} Sentiment Effect", delta_color="normal")
                    
                    with col_b:
                        if final_signal > 1.15: st.success("SIGNAL: STRONG BUY")
                        elif final_signal > 1.05: st.info("SIGNAL: ACCUMULATE")
                        elif final_signal < 0.85: st.error("SIGNAL: OVERVALUED")
                        else: st.warning("SIGNAL: FAIR VALUE")

                    # 2. Visual Chart
                    chart_data = pd.DataFrame({
                        "Metric": metrics,
                        "Target": [target_data[m] for m in metrics],
                        "Peer Average": [benchmarks[m] for m in metrics]
                    }).set_index("Metric")
                    
                    st.subheader("Metric Comparison")
                    st.bar_chart(chart_data)

                    # 3. Data Table
                    st.subheader("Raw Data Comparison")
                    st.table(chart_data.style.format("{:.2f}"))
    else:
        st.info("Fill out the parameters on the left and click 'Run' to see the valuation.")
