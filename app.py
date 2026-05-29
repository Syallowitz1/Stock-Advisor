import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# Set Page Config
st.set_page_config(page_title="Equity Value Advisor", page_icon="📈")

# --- Camouflage Logic ---
# This tells Yahoo Finance you are a real person using a Chrome browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

def get_stock_data(ticker):
    """Fetches key metrics from Yahoo Finance with a custom session to prevent blocking."""
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        
        stock = yf.Ticker(ticker.upper(), session=session)
        info = stock.info
        
        # Verify that we actually received data
        if not info or 'marketCap' not in info:
            return None
            
        return {
            "Ticker": ticker.upper(),
            "EV/EBITDA": info.get("enterpriseToEbitda", 20),
            "FCF Yield": (info.get("freeCashflow", 0) / info.get("marketCap", 1)) if info.get("freeCashflow") else 0.02,
            "Revenue Growth": info.get("revenueGrowth", 0.1),
            "Op Margin": info.get("operatingMargins", 0.1),
            "P/S Ratio": info.get("priceToSalesTrailing12Months", 5)
        }
    except Exception as e:
        return None

# --- UI Header ---
st.title("📈 Personal Stock Advisor")
st.markdown("Evaluate a company's valuation based on custom peer weights and your personal conviction.")

# --- Sidebar Inputs ---
st.sidebar.header("1. Target Company")
target_ticker = st.sidebar.text_input("Target Ticker", value="AMZN").upper()
sentiment = st.sidebar.slider("Personal Sentiment (1-10)", 1, 10, 5)

st.sidebar.header("2. Peer Groups")
st.sidebar.info("Total similarity must equal 100%")

peer_groups = []
total_weight = 0

for i in range(1, 4):
    with st.sidebar.expander(f"Peer Group {i}"):
        name = st.text_input(f"Group {i} Name", key=f"n{i}", value="" if i > 1 else "Retail")
        weight = st.number_input(f"Similarity %", min_value=0, max_value=100, value=0 if i > 1 else 100, key=f"w{i}")
        tickers = st.text_input(f"Tickers (comma separated)", key=f"t{i}", value="" if i > 1 else "WMT, COST")
        
        if weight > 0 and tickers:
            peer_groups.append({
                "weight": weight / 100,
                "tickers": [t.strip().upper() for t in tickers.split(",")]
            })
            total_weight += weight

# --- Main Logic ---
if st.button("Run Valuation Analysis"):
    if total_weight != 100:
        st.error(f"Total similarity is {total_weight}%. It must be exactly 100% to run.")
    else:
        with st.spinner(f"Fetching data for {target_ticker} and peers..."):
            target_data = get_stock_data(target_ticker)
            
            if not target_data:
                st.error(f"Could not find {target_ticker}. Ensure the ticker is correct and try again.")
            else:
                metrics_to_track = ["EV/EBITDA", "FCF Yield", "Revenue Growth", "Op Margin", "P/S Ratio"]
                quant_weights = {"EV/EBITDA": 0.25, "FCF Yield": 0.20, "Revenue Growth": 0.15, "Op Margin": 0.10, "P/S Ratio": 0.10}
                weighted_benchmarks = {m: 0 for m in metrics_to_track}

                # Fetch Peer Data
                for group in peer_groups:
                    group_data_list = []
                    for t in group['tickers']:
                        data = get_stock_data(t)
                        if data:
                            group_data_list.append(data)
                    
                    if group_data_list:
                        df_cluster = pd.DataFrame(group_data_list)
                        cluster_avg = df_cluster[metrics_to_track].mean()
                        for m in metrics_to_track:
                            weighted_benchmarks[m] += cluster_avg[m] * group['weight']

                # Scoring logic
                total_quant_score = 0
                for m, weight in quant_weights.items():
                    if m in ["EV/EBITDA", "P/S Ratio"]:
                        score = weighted_benchmarks[m] / target_data[m] if target_data[m] != 0 else 1
                    else:
                        score = target_data[m] / weighted_benchmarks[m] if weighted_benchmarks[m] != 0 else 1
                    total_quant_score += (score * weight)

                sentiment_factor = sentiment / 5
                final_signal = (total_quant_score * 0.8) + (sentiment_factor * 0.2)

                # --- UI Output ---
                st.divider()
                st.header(f"Results for {target_ticker}")
                
                if final_signal > 1.15:
                    st.success("ADVISOR SIGNAL: UNDERVALUED (STRONG BUY)")
                elif final_signal > 1.05:
                    st.info("ADVISOR SIGNAL: SLIGHTLY UNDERVALUED")
                elif final_signal < 0.85:
                    st.error("ADVISOR SIGNAL: OVERVALUED (SELL/WAIT)")
                else:
                    st.warning("ADVISOR SIGNAL: FAIRLY VALUED (HOLD)")

                st.metric("Value Score", f"{final_signal:.2%}")

                # Simple comparison table
                peer_vals = [f"{weighted_benchmarks[m]:.2f}" for m in metrics_to_track]
                target_vals = [f"{target_data[m]:.2f}" for m in metrics_to_track]
                
                comparison_df = pd.DataFrame({
                    "Metric": metrics_to_track,
                    "Peer Benchmark": peer_vals,
                    f"{target_ticker} Value": target_vals
                })
                st.table(comparison_df)
