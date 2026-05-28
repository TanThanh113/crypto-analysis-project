# -*- coding: utf-8 -*-

import os
import time
import logging
import argparse
import requests
import pandas as pd
import sys

from dotenv import load_dotenv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from save_dataframe_to_parquet import save_dataframe_to_parquet

# =========================================================
# LOGGING
# =========================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY").strip()
ARKHAM_API_KEY = os.getenv("ARKHAM_API_KEY").strip()

if COINGECKO_API_KEY:
    logging.info("✅ CoinGecko API Key has been identified. The API is being used to retrieve data (Safe Mode).")
else:
    logging.warning("⚠️ No CoinGecko API Key available. The API is being used to retrieve data (Unsafe Mode).")

if not ARKHAM_API_KEY:
    logging.warning("⚠️  No Arkham API Key available. Ignore Tier 2 sources")
    ARKHAM_API_KEY = ""

# =========================================================
# CONFIG
# =========================================================
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/exchange_reserves")

SYMBOLS = ["BTC", "ETH"]

EXCHANGE_MAPPING = {
    "binance": "binance",
    "coinbase": "gdax",
    "kraken": "kraken",
    "bitfinex": "bitfinex",
    "okx": "okex",
    "bybit": "bybit_spot",
    "kucoin": "kucoin"
}

ARKHAM_MAPPING = {
    "binance": "binance",
    "gdax": "coinbase",
    "kraken": "kraken",
    "bitfinex": "bitfinex",
    "okex": "okx",
    "bybit_spot": "bybit",
    "kucoin": "kucoin"
}

MAX_WORKERS=8
REQUEST_TIMEOUT = 15

SCHEMA_COLUMNS = {
    "exchange": "string",
    "coingecko_id": "string",
    "timestamp": "string",
    "date": "string",
    "trust_score": "float64",
    "country": "string",
    "year_established": "string",
    "trade_volume_24h_btc": "float64",
    "trade_volume_24h_btc_normalized": "float64",
    
    "llama_reserve_usd": "float64",
    "arkham_reserve_usd": "float64",
    "actual_reserve_usd": "float64",
    "data_source": "string",
    
    "live_btc_price_usd": "float64",
    "trade_volume_24h_usd": "float64",
    "trade_volume_24h_usd_normalized": "float64",
    
    "reserve_utilization": "float64",
    "bank_run_risk": "string",
    "wash_trading_volume_usd": "float64",
    
    "reserve_dominance_pct": "float64",
    "concentration_risk_score": "float64",
    "liquidity_score": "float64",
    "exchange_tier": "string",
    "whale_withdrawal_risk": "float64",

    # Metadata Data Lake
    "source": "string",
    "run_id": "string",
    "ingestion_time": "datetime64[ns, UTC]",
    "year": "string",
    "month": "string",
    "day": "string"
}

# =========================================================
# HELPERS
# =========================================================
def get_coingecko_headers():
    if COINGECKO_API_KEY:
        return {"x-cg-demo-api-key": COINGECKO_API_KEY}
    return None
def safe_request(url, params=None, headers=None, max_retries=3, backoff_factor=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                wait_time = backoff_factor * (attempt + 1)
                logging.warning(f"⚠️ HTTP 429 (Rate Limit): Wait {wait_time} and then try again {attempt+1}/{max_retries} for {url}")
                time.sleep(wait_time)
                continue 
            else:
                logging.warning(f"⚠️ HTTP {response.status_code}: {url}")
                return None
                
        except Exception as e:
            logging.error(f"❌ Request error: {e}")
            return None

def enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    for col in SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[list(SCHEMA_COLUMNS.keys())].copy()

    for col, dtype in SCHEMA_COLUMNS.items():
        try:
            if "datetime" in dtype:
                df[col] = pd.to_datetime(df[col], utc=True)
            elif dtype == "float64":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
            elif dtype == "int64":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            elif dtype == "bool":
                df[col] = df[col].astype(bool)
            else:
                df[col] = df[col].astype(dtype)
        except Exception as e:
            logging.warning(f"⚠️ Schema cast warning {col}: {e}")
    return df

# =========================================================
# DATA FETCHERS
# =========================================================
def fetch_live_btc_price():
    logging.info("📥 We are getting the BTC/USD exchange rate directly from CoinGecko....")
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"

    headers = get_coingecko_headers()
    data = safe_request(url, headers=headers)

    if data and "bitcoin" in data:
        price = data["bitcoin"]["usd"]
        logging.info(f"💵 Current exchange rate: 1 BTC = ${price:,.2f}")
        return price
    logging.warning("⚠️ Unable to obtain the BTC price, use the temporary fallback price. (60,000 USD)")
    return 60000.0

def fetch_defillama_dataframe():
    logging.info("📥 Currently pulling on-chain reserves from DefiLlama....")
    url = "https://api.llama.fi/protocols"
    data = safe_request(url)
    rows = []
    if data and isinstance(data, list):
        for protocol in data:
            # ONLY include platforms in the Exchange (CEX) category
            if protocol.get("category") == "CEX":
                raw_name = protocol.get("name", "")
                
                # STANDARDIZATION: Remove the letters "CEX" if present, delete spaces, and convert to lowercase.
                clean_name = raw_name.replace(" CEX", "").strip().lower()
                
                # Compare with the Mapping Dictionary
                if clean_name in EXCHANGE_MAPPING:
                    rows.append({
                        "coingecko_id": EXCHANGE_MAPPING[clean_name], 
                        "exchange_name": raw_name, 
                        "llama_reserve_usd": float(protocol.get("tvl", 0))
                    })
    return pd.DataFrame(rows)

def fetch_arkham_dataframe():
    logging.info("📥 [Tier 2] We are calling Arkham Intelligence to scan hidden wallets....")
    if not ARKHAM_API_KEY:
        logging.warning("⚠️  No Arkham API Key available. Ignore Tier 2 sources")
        return pd.DataFrame(columns=["coingecko_id", "arkham_reserve_usd"])

    headers = {"API-Key": ARKHAM_API_KEY}

    current_time_ms = int(time.time() * 1000)
    params = {"time": current_time_ms} 
    
    rows = []
    target_exchanges = ["gdax", "kraken"] 
    
    for cg_id in target_exchanges:
        arkham_entity = ARKHAM_MAPPING.get(cg_id)
        url = f"https://api.arkhamintelligence.com/portfolio/entity/{arkham_entity}"
        
        data = safe_request(url, params=params, headers=headers) 
        
        if data:
            total_usd = 0.0
            
            for chain, tokens in data.items():
                if isinstance(tokens, dict):
                    for token_key, token_data in tokens.items():
                        if isinstance(token_data, dict) and "usd" in token_data:
                            total_usd += float(token_data.get("usd", 0))
            
            rows.append({
                "coingecko_id": cg_id,
                "arkham_reserve_usd": total_usd
            })
            logging.info(f"🕵️  Arkham discovers wallet {arkham_entity.upper()}: ${total_usd/1e9:,.2f}B")
        else:
            logging.warning(f"⚠️  No data found for {arkham_entity.upper()}")
        
        time.sleep(1)
    
        
    return pd.DataFrame(rows)

def fetch_all_exchanges_raw_data():
    logging.info("📥 Download the CoinGecko overview data set (only once)....")
    url = "https://api.coingecko.com/api/v3/exchanges"
    headers = get_coingecko_headers()
    return safe_request(url, headers=headers)

def process_single_exchange(exchange_name, cg_id, raw_data):
    try:
        exchange_data = None
        for ex in raw_data:
            if ex["id"].lower() == cg_id.lower():
                exchange_data = ex
                break
        if not exchange_data:
            return None

        trust_score = exchange_data.get("trust_score", 0)
        trade_volume_btc = float(exchange_data.get("trade_volume_24h_btc", 0)) 
        trade_volume_btc_normalized = float(exchange_data.get("trade_volume_24h_btc_normalized", 0)) 
        country = exchange_data.get("country", "Unknown")
        year_established = exchange_data.get("year_established", "Unknown")


        now = datetime.utcnow()
        row = {
            "exchange": exchange_name,
            "coingecko_id": cg_id, # Enter your ID so you can join with DefiLlama later.
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "trust_score": trust_score,
            "country": country,
            "year_established": year_established,
            "trade_volume_24h_btc": trade_volume_btc, 
            "trade_volume_24h_btc_normalized": trade_volume_btc_normalized,
            "source": "hybrid_coingecko_defillama"
        }
        return row

    except Exception as e:
        logging.error(f"{exchange_name} parse error: {e}")
        return None
    
# =========================================================
# COLLECTOR
# =========================================================
def collect_cg_base_data():
    rows = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Fetch the raw data from CoinGecko
        raw_data = fetch_all_exchanges_raw_data()
        if not raw_data:
            logging.error("❌ No exchange data collected")
            return pd.DataFrame()
        
        futures = []
        for display_name, cg_id in EXCHANGE_MAPPING.items():
            # executor.submit(function_to_execute, parameter_1, parameter_2, ...)
            futures.append(executor.submit(process_single_exchange, display_name, cg_id, raw_data))

        # Once the data is available, proceed immediately without waiting.
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    rows.append(result)
            except Exception as e:
                logging.error(f"Future error: {e}")
    return pd.DataFrame(rows)
# =========================================================
# FEATURE ENGINEERING & MERGE
# =========================================================
def merge_and_enrich(df_cg, df_llama, df_arkham, btc_price, run_id):
    if df_cg.empty:
        logging.error("⚠️  Missing source data. Cancel join.")
        return pd.DataFrame()

    logging.info("⚙️  We are currently merging data and performing matrix calculations...")
    
    # Merge two data streams using Pandas (Vectorized Join)
    df = df_cg.copy()
    if not df_llama.empty:
        df = pd.merge(df, df_llama, on="coingecko_id", how="left")
    else:
        df["llama_reserve_usd"] = None
        logging.warning("⚠️ No data from DefiLlama. Since there is no data, we will leave it as none.")

    # Join with Arkham (Tier 2)
    if not df_arkham.empty:
        df = pd.merge(df, df_arkham, on="coingecko_id", how="left")
    else:
        df["arkham_reserve_usd"] = None
        logging.warning("⚠️ No data from Arkham. Since there is no data, we will leave it as none.")

    # FALLBACK STRATEGY
    # Get the Llama data first. If Llama is 0, automatically fill with Arkham. If both are corrupted, assign 0.
    df["llama_reserve_usd"] = pd.to_numeric(df["llama_reserve_usd"], errors="coerce")
    df["arkham_reserve_usd"] = pd.to_numeric(df["arkham_reserve_usd"], errors="coerce")
    
    df["actual_reserve_usd"] = df["llama_reserve_usd"].where(
        df["llama_reserve_usd"] > 0, 
        df["arkham_reserve_usd"]
    ).fillna(0.0)

    # Tagging the data source
    def tag_source(row):
        if pd.notna(row.get("llama_reserve_usd")):
            return "DefiLlama"
        elif pd.notna(row.get("arkham_reserve_usd")):
            return "Arkham"
        return "Missing"

    df["data_source"] = df.apply(tag_source, axis=1)
    
    # Standardized USD exchange rate
    df["live_btc_price_usd"] = btc_price
    df["trade_volume_24h_usd"] = df["trade_volume_24h_btc"] * btc_price
    df["trade_volume_24h_usd_normalized"] = df["trade_volume_24h_btc_normalized"] * btc_price

    # Capital utilization ratio (Volume divided by actual Reserve)
    df["reserve_utilization"] = df["trade_volume_24h_usd"] / df["actual_reserve_usd"].replace(0, 1)

    # Risk Assessment (Bank Run)
    def assess_risk(row):
        # If the transaction volume is too large compared to the actual cold wallet capacity (>100% reserve) + Low reputation score
        if row["reserve_utilization"] > 1.0 and row["trust_score"] < 8:
            return "HIGH_RISK"
        elif row["reserve_utilization"] < 0.5 and row["trust_score"] >= 9:
            return "SAFE"
        return "MODERATE"

    df["bank_run_risk"] = df.apply(assess_risk, axis=1)

    # Calculating Volume Manipulation (Wash Trading Proxy)
    # Virtual Volume = Self-declared Volume - Volume filtered (normalized) by CoinGecko
    df["wash_trading_volume_usd"] = df["trade_volume_24h_usd"] - df["trade_volume_24h_usd_normalized"]

    # 5. Metadata
    now = datetime.utcnow()
    df["timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
    df["date"] = now.strftime("%Y-%m-%d")
    df["source"] = "hybrid_pandas_pipeline"
    df["run_id"] = run_id
    df["ingestion_time"] = now
    df["year"] = now.strftime("%Y")
    df["month"] = now.strftime("%m")
    df["day"] = now.strftime("%d")

    df = enrich_features(df)

    return df
    
# =========================================================
# FEATURE ENGINEERING
# =========================================================
def enrich_features(df):
    if df.empty:
        return df
    logging.info("⚙️  Building reserve features")

    # Reserve dominance
    total_reserve = (df["actual_reserve_usd"].sum())

    if total_reserve > 0:
        # Market share of reserves / Dominance
        df["reserve_dominance_pct"] = (df["actual_reserve_usd"] / total_reserve) * 100
    else:
        df["reserve_dominance_pct"] = 0

    # Exchange concentration risk
    df["concentration_risk_score"] = (df["reserve_dominance_pct"] * df["reserve_utilization"])

    # Liquidity score
    df["liquidity_score"] = (df["trust_score"] * df["trade_volume_24h_usd_normalized"] )

    # Exchange tier
    def classify_exchange(volume_usd):
        if volume_usd >= 10_000_000_000: return "tier_1"
        elif volume_usd >= 1_000_000_000: return "tier_2"
        elif volume_usd >= 100_000_000: return "tier_3"
        return "tier_4"

    df["exchange_tier"] = df["trade_volume_24h_usd"].apply(classify_exchange)
    
    # Whale withdrawal risk
    df["whale_withdrawal_risk"] = (abs(df["wash_trading_volume_usd"]) * df["reserve_utilization"])

    return df

# =========================================================
# MAIN
# =========================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=OUTPUT_DIR)
    parser.add_argument("--manager", type=str, choices=["iceberg", "hive"], default="hive")
    args = parser.parse_args()
    start = time.time()

    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    logging.info("🚀 Starting exchange reserve collector")
    df_cg = collect_cg_base_data()

    if df_cg.empty:
        logging.error("❌ No reserve data collected")
        return
    
    btc_price = fetch_live_btc_price()
    df_llama = fetch_defillama_dataframe()
    df_arkham = fetch_arkham_dataframe()

    df_final = merge_and_enrich(df_cg, df_llama, df_arkham, btc_price, run_id)

    if df_final.empty:
        logging.error("❌ Error during Transform (Empty DataFrame). Cancel saving.")
        return
    
    df_final = enforce_schema(df_final)

    if args.manager == "iceberg":
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=args.output,
            file_prefix="exchange_reserve",
            partition_cols=None 
        )
    else:
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=args.output,
            file_prefix="exchange_reserve",
            partition_cols=["exchange", "year", "month", "day"]
        )
    
    logging.info(f"📊 Process completed {len(df_final)} rows.")

    logging.info("\n📈 Exchange Reserve Snapshot (USD):")
    display_cols = ["exchange", "actual_reserve_usd", "trade_volume_24h_usd", "reserve_utilization", "bank_run_risk", "exchange_tier"]
    df_print = df_final[display_cols].copy()
    
    # Format Currency (Billion Dollars)
    df_print["actual_reserve_usd"] = df_print["actual_reserve_usd"].apply(lambda x: f"${x/1e9:,.2f}B")
    df_print["trade_volume_24h_usd"] = df_print["trade_volume_24h_usd"].apply(lambda x: f"${x/1e9:,.2f}B")
    
    # Coefficient Format (Only two decimal places; if divided by zero results in a huge number, write "N/A")
    df_print["reserve_utilization"] = df_print["reserve_utilization"].apply(
        lambda x: "N/A" if x > 1000000 else f"{x:,.3f}"
    )
    
    print(df_print.to_string(index=False))

    elapsed = round(time.time() - start, 2)
    logging.info(f"🎉 Completed in {elapsed}s")

# =========================================================
# ENTRYPOINT
# =========================================================

if __name__ == "__main__":
    main()