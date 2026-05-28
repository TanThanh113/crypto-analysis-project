# -*- coding: utf-8 -*-

import os
import time
import logging
import argparse
import requests
import pandas as pd
import numpy as np
import sys

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from save_dataframe_to_parquet import save_dataframe_to_parquet

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
# =========================================================
# CONFIG
# =========================================================
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/stablecoin_supply")

STABLECOINS = {
    "USDT": {
        "coingecko_id": "tether",
        "decimals": 6
    },
    "USDC": {
        "coingecko_id": "usd-coin",
        "decimals": 6
    },
    "DAI": {
        "coingecko_id": "dai",
        "decimals": 18
    },
    "FDUSD": {
        "coingecko_id": "first-digital-usd",
        "decimals": 18
    },
    "TUSD": {
        "coingecko_id": "true-usd",
        "decimals": 18
    }
}
MAX_WORKERS = 8
REQUEST_TIMEOUT = 15

SCHEMA_COLUMNS = {
    # Identifier
    "symbol": "string",
    "coin_id": "string",
    "timestamp": "string",
    "date": "string",
    
    # Source Specifications (Raw)
    "price_usd": "float64",
    "market_cap_usd": "float64",
    "fully_diluted_valuation_usd": "float64",
    "volume_24h_usd": "float64",
    "circulating_supply": "float64",
    "total_supply": "float64",
    "max_supply": "float64",
    "market_cap_rank": "int64",
    
    # Feature: Exchange Rate Risk (Peg Risk) 
    "peg_deviation_pct": "float64",
    "utilization_ratio": "float64",
    "volume_to_marketcap": "float64",
    "peg_regime": "string",
    "depeg_risk_score": "float64",
    
    # Feature: Normalization (Log)
    "market_cap_usd_log": "float64",
    "volume_24h_usd_log": "float64",
    "circulating_supply_log": "float64",
    
    # Feature: Assessing Position
    "stablecoin_dominance_pct": "float64",
    "liquidity_tier": "string",
    "liquidity_score": "float64",
    
    # Feature: Time-series
    "timestamp_unix": "int64",
    "hour": "int64",
    "day_of_week": "int64",
    "hour_sin": "float64",
    "hour_cos": "float64",
    
    # Feature: Quality (Quality Flags)
    "is_peg_outlier": "int64",
    "is_volume_outlier": "int64",

    # Data Lake standard metadata
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
def safe_request(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            logging.warning(f"HTTP {response.status_code}: {url}")
            return None
        return response.json()
    except Exception as e:
        logging.error(f"Request error: {e}")
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
# COINGECKO
# =========================================================
def fetch_stablecoin_supply(symbol, config, run_id):
    coin_id = config["coingecko_id"]
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"

    # Config params for CoinGecko API (only market data)
    data = safe_request(url,
        params={
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false"
        }
    )
    if not data:
        return None
    try:
        market_data = data.get("market_data", {})

        current_price = (market_data.get("current_price", {}).get("usd", 0)) # Current price
        market_cap = (market_data.get("market_cap", {}).get("usd", 0)) # Market capitalization.
        fdv = (market_data.get("fully_diluted_valuation", {}).get("usd", 0)) # Fully Diluted Valuation
        volume_24h = (market_data.get("total_volume", {}).get("usd", 0)) # The volume of transactions in one day.
        circulating_supply = market_data.get("circulating_supply", 0) # Amount of coins in circulation
        total_supply = market_data.get("total_supply", 0) # Total supply of coins
        max_supply = market_data.get("max_supply", 0) # Maximum supply of coins
        market_cap_rank = data.get("market_cap_rank") # Market capitalization rank
        
        # FEATURE ENGINEERING
        peg_deviation_pct = ( (current_price - 1.0) / 1.0 * 100 if current_price else 0 ) # Exchange rate deviation
        # This formula calculates by what percentage the current price is deviating from $1.0.

        utilization_ratio = (circulating_supply / total_supply if total_supply and total_supply > 0 else None) # Usage rate
        

        volume_to_marketcap = (volume_24h / market_cap if market_cap and market_cap > 0 else None) # Capital turnover ratio
        # If the market capitalization is $100 billion but the daily trading volume is only $1 billion (1%),
        # it indicates that the currency has poor liquidity.

        # Locating the state of panic
        if peg_deviation_pct >= 0.5:
            peg_regime = "premium"
        elif peg_deviation_pct <= -0.5:
            peg_regime = "depeg_risk"
        else:
            peg_regime = "stable"

        # OUTPUT
        now = datetime.utcnow()
        row = {
            "symbol": symbol, # Symbol name
            "coin_id": coin_id, # Coin ID
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), # Timestamp
            "timestamp_unix": int(now.timestamp()),
            "date": now.strftime("%Y-%m-%d"), # Date
            
            "price_usd": current_price, # Current price
            "market_cap_usd": market_cap, # Market capitalization
            "fully_diluted_valuation_usd": fdv, # Fully Diluted Valuation
            "volume_24h_usd": volume_24h, # Volume in 24h

            "circulating_supply": circulating_supply, # Number of coins in circulation
            "total_supply": total_supply, # Total supply of coins
            "max_supply": max_supply, # Maximum supply of coins

            "market_cap_rank": market_cap_rank,
            "peg_deviation_pct": peg_deviation_pct,
            "utilization_ratio": utilization_ratio,
            "volume_to_marketcap": volume_to_marketcap,

            "peg_regime": peg_regime,

            # Metadata
            "source": "coingecko",
            "run_id": run_id,
            "ingestion_time": now,
            "year": now.strftime("%Y"),
            "month": now.strftime("%m"),
            "day": now.strftime("%d")
        }

        logging.info(f"✅ {symbol} | " f"MCAP=${market_cap:,.0f} | " f"Supply={circulating_supply:,.0f} | " f"Peg={peg_deviation_pct:.4f}%")
        return row
    
    except Exception as e:
        logging.error(f"{symbol} parse error: {e}")
        return None

# =========================================================
# COLLECTOR
# =========================================================

def collect_all(run_id):
    rows = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for symbol, config in STABLECOINS.items():
            # executor.submit(function_to_execute, parameter_1, parameter_2, ...)
            futures.append(executor.submit(fetch_stablecoin_supply, symbol, config, run_id))

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
# FEATURE ENGINEERING
# =========================================================
def enrich_features(df):
    if df.empty:
        return df
    logging.info("⚙️ Building stablecoin features")

    # Stablecoin dominance
    total_market_cap = df["market_cap_usd"].sum() # Total market cap of all stablecoins
    if total_market_cap > 0:
        df["stablecoin_dominance_pct"] = (df["market_cap_usd"] / total_market_cap) * 100
    else:
        df["stablecoin_dominance_pct"] = 0

    # Risk score
    df["depeg_risk_score"] = (abs(df["peg_deviation_pct"]) * df["volume_to_marketcap"].fillna(0))

    # Liquidity tier
    def classify_liquidity(mcap):
        if mcap >= 50_000_000_000:
            return "mega"
        elif mcap >= 5_000_000_000:
            return "large"
        elif mcap >= 500_000_000:
            return "medium"
        return "small"

    df["liquidity_tier"] = (df["market_cap_usd"].apply(classify_liquidity))

    df["liquidity_score"] = (
        df["market_cap_usd_log"] * 0.5 +
        df["volume_to_marketcap"] * 0.3 -
        abs(df["peg_deviation_pct"]) * 0.2
    )

    return df

def add_time_features(df):

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek

    df["hour_sin"] = np.sin(
        2 * np.pi * df["hour"] / 24
    )

    df["hour_cos"] = np.cos(
        2 * np.pi * df["hour"] / 24
    )

    return df

def add_normalized_features(df):

    log_cols = [
        "market_cap_usd",
        "volume_24h_usd",
        "circulating_supply"
    ]

    for col in log_cols:
        df[f"{col}_log"] = np.log1p(df[col])

    return df

def add_quality_flags(df):

    df["is_peg_outlier"] = (
        abs(df["peg_deviation_pct"]) > 2
    ).astype(int)

    df["is_volume_outlier"] = (
        df["volume_to_marketcap"] > 1.5
    ).astype(int)

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

    logging.info("🚀 Starting stablecoin supply collector")
    df = collect_all(run_id)
    if df.empty:
        logging.error("❌ No stablecoin data collected")
        return
    
    df_final = add_time_features(df)
    df_final = add_normalized_features(df_final) 
    df_final = enrich_features(df_final)
    df_final = add_quality_flags(df_final)

    if df_final.empty:
        logging.error("❌ Error during Transform (Empty DataFrame). Cancel saving.")
        return
    
    df_final = enforce_schema(df_final)

    if args.manager == "iceberg":
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=args.output,
            file_prefix="stablecoin_supply",
            partition_cols=None 
        )
    else:
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=args.output,
            file_prefix="stablecoin_supply",
            partition_cols=["symbol", "year", "month", "day"]
        )

    logging.info(f"📊 Rows: {len(df)}")
    logging.info("\n📈 Stablecoin Snapshot:")
    print(
        df_final[["symbol", "market_cap_usd", "stablecoin_dominance_pct", "peg_deviation_pct", "hour_sin"]].to_string(index=False)
    )

    elapsed = round(time.time() - start, 2)
    logging.info(f"🎉 Completed in {elapsed}s")

if __name__ == "__main__":
    main()