# -*- coding: utf-8 -*-

import os
import time
import requests
import pandas as pd
import logging
import argparse
import sys

from save_dataframe_to_parquet import save_dataframe_to_parquet
from datetime import datetime, timedelta
from dotenv import load_dotenv

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Configure Session with automatic Retry mechanism
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=5,
    status_forcelist=[429, 500, 502, 503, 504],
    raise_on_status=False
)
session.mount("https://", HTTPAdapter(max_retries=retries))

# =========================================================
# CONFIG & ASSETS
# =========================================================
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data")
TIINGO_API_KEY = os.getenv("TIINGO_API_KEY")

ASSETS = {
    "macro": {
        "SP500": "SPY",
        "NASDAQ": "QQQ",
        "GOLD": "GLD",
        "VIX": "VXX",
        "OIL": "USO"
    },
    "etf": {
        "IBIT": "IBIT", "FBTC": "FBTC", "GBTC": "GBTC", 
        "BITB": "BITB", "ARKB": "ARKB", "HODL": "HODL", 
        "BTCO": "BTCO", "EZBC": "EZBC", "BTCW": "BTCW", "BRRR": "BRRR",
        "ETHA": "ETHA", "FETH": "FETH", "ETHE": "ETHE", "ETHW": "ETHW"
    }
}

# =========================================================
# FIXED SCHEMA
# =========================================================
SCHEMA_COLUMNS = {
    "date": "datetime64[ns, UTC]",
    "timestamp": "int64",
    "symbol": "string",
    "ticker": "string",
    "asset_class": "string",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "adj_close": "float64",
    "volume": "float64",
    "vwap": "float64",
    "trade_count": "float64",
    "exchange": "string",
    "currency": "string",
    "timeframe": "string",
    
    "source": "string",
    "data_provider": "string",
    "run_id": "string",
    "ingestion_time": "datetime64[ns, UTC]",
    "year": "string",
    "month": "string",
    "day": "string"
}

def enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Type casting and adding missing columns according to standard Schema."""
    # Check if there is data in the column; if not, it will be converted to null.
    for col in SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[list(SCHEMA_COLUMNS.keys())].copy()

    for col, dtype in SCHEMA_COLUMNS.items():
        try:
            if "datetime" in dtype:
                df[col] = pd.to_datetime(df[col], utc=True)
            elif dtype == "float64": # Convert to float64(if missing, it will be converted to NaN)
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
            elif dtype == "int64": # Convert to int64(if missing, it will be converted to 0)
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            else:
                df[col] = df[col].astype(dtype)
        except Exception as e:
            logging.warning(f"⚠️ Schema cast warning {col}: {e}")
    return df

# =========================================================
# FETCH TIINGO
# =========================================================
def fetch_tiingo(symbol_name, ticker, asset_class, start_dt, end_dt):
    logging.info(f"📥 [{asset_class.upper()}] Fetching {symbol_name} ({ticker})...")
    
    start_str = start_dt.strftime('%Y-%m-%d')
    end_str = end_dt.strftime('%Y-%m-%d')
    
    try:
        url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices"
        params = {
            "startDate": start_str,
            "endDate": end_str,
            "token": TIINGO_API_KEY,
            "format": "json"
        }
        headers = {"User-Agent": "crypto-analysis-bot/1.0"}
        response = session.get(url, params=params, headers=headers, timeout=30)

        if response.status_code == 429:
            logging.error(f"❌ Tiingo Rate Limit Exceeded (429). Sleep 30 seconds and retry...")
            time.sleep(30)
            return pd.DataFrame()
        
        if response.status_code != 200:
            logging.error(f"❌ Tiingo Error {response.status_code}: {response.text}")
            return pd.DataFrame()
            
        data = response.json()
        if not data:
            logging.warning(f"⚠️ No data for {ticker}")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = df.rename(columns={"date": "raw_date", "adjClose": "adj_close"})
        
        # Handling default values
        if "adj_close" not in df.columns: df["adj_close"] = df["close"]
        if "volume" not in df.columns: df["volume"] = 0

        # Time
        df["date"] = pd.to_datetime(df["raw_date"], utc=True).dt.floor("s")
        df["timestamp"] = df["date"].astype('int64') // 10**9
        df["year"] = df["date"].dt.year.astype(str)
        df["month"] = df["date"].dt.month.astype(str).str.zfill(2)
        df["day"] = df["date"].dt.day.astype(str).str.zfill(2)

        # Metadata
        df["run_id"] = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        df["symbol"] = symbol_name
        df["ticker"] = ticker
        df["asset_class"] = asset_class
        df["source"] = "tiingo"
        df["data_provider"] = "tiingo"
        df["exchange"] = "US"
        df["currency"] = "USD"
        df["timeframe"] = "1d"
        df["ingestion_time"] = datetime.utcnow()

        # Drop duplicates and nulls
        df = df.drop_duplicates(subset=["date"]).dropna(subset=["close"])
        
        # Enforce Schema
        df = enforce_schema(df)
        return df

    except Exception as e:
        logging.error(f"❌ Critical Error {ticker}: {e}")
        return pd.DataFrame()

# =========================================================
# MAIN
# =========================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", type=str, choices=["macro", "etf", "all"], default="all")
    parser.add_argument("--manager", type=str, choices=["iceberg", "hive"], default="hive")
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    args = parser.parse_args()

    if not TIINGO_API_KEY:
        logging.error("❌ Missing TIINGO_API_KEY. Please set it up.")
        return

    # Determine the mode
    if args.start and args.end:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
        end_dt = datetime.strptime(args.end, "%Y-%m-%d")
        logging.info(f"🚀 MODE: BACKFILL ({args.start} -> {args.end})")
    else:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=4)
        logging.info(f"🚀 MODE: DAILY (Last 4 days)")

    # Filter the asset
    target_assets = ASSETS if args.type == "all" else {args.type: ASSETS[args.type]}

    all_dfs = []
    for asset_class, tickers in target_assets.items():
        for name, tick in tickers.items():
            df = fetch_tiingo(name, tick, asset_class, start_dt, end_dt)
            if not df.empty:
                all_dfs.append(df)
            time.sleep(3)

    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        df_final = df_final.drop_duplicates(subset=["date", "symbol"], keep="last")

        dynamic_prefix_iceberg = f"tiingo_{args.type}_raw"
        dynamic_prefix_hive = f"tiingo_{args.type}_daily"

        if args.manager == "iceberg":
            save_dataframe_to_parquet(
                df=df_final,
                base_dir=OUTPUT_DIR,
                file_prefix=dynamic_prefix_iceberg,
                partition_cols=None 
            )
        else:
            save_dataframe_to_parquet(
                df=df_final,
                base_dir=OUTPUT_DIR,
                file_prefix=dynamic_prefix_hive,
                partition_cols=["asset_class", "symbol", "year", "month", "day"]
            )

        logging.info(f"🎉 Pipeline complete! Total {len(df_final)} lines.")

if __name__ == "__main__":
    main()