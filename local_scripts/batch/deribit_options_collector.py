# -*- coding: utf-8 -*-

import os
import time
import json
import logging
import argparse
import requests
import pandas as pd
import sys

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

from save_dataframe_to_parquet import save_dataframe_to_parquet

load_dotenv()

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
DERIBIT_BASE_URL = "https://www.deribit.com/api/v2"
SUPPORTED_COINS = ["BTC", "ETH"]

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/options")

MAX_WORKERS = 7
REQUEST_TIMEOUT = 10

SCHEMA_COLUMNS = {
    # Identification & Classification
    "timestamp": "string",
    "date": "string",
    "hour": "string",
    "instrument_name": "string",
    "underlying": "string",
    "expiry": "string",
    "strike": "float64",
    "option_type": "string",
    
    # Price & Liquidity
    "underlying_price": "float64",
    "index_price": "float64",
    "mark_price": "float64",
    "mark_iv": "float64",
    "best_bid_price": "float64",
    "best_ask_price": "float64",
    "bid_iv": "float64",
    "ask_iv": "float64",
    "last_price": "float64",
    "open_interest": "float64",
    "volume": "float64",
    "volume_usd": "float64",
    
    # Risk Parameters (Greeks)
    "delta": "float64",
    "gamma": "float64",
    "vega": "float64",
    "theta": "float64",
    "rho": "float64",
    
    # Derivative Features
    "moneyness": "float64",
    "is_atm": "bool",
    "iv_spread": "float64",
    "mid_iv": "float64",
    "is_call": "bool",

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

def safe_request(url, params=None, retries=3):
    delay = 1
    for i in range(retries):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.json()
                
            if response.status_code == 429:
                logging.warning(f"HTTP 429 Limit! Sleep {delay}s and try again...({i+1}/{retries})")
                time.sleep(delay)
                delay *= 2
                continue
                
            logging.warning(f"HTTP {response.status_code}: {url}")
            return None
            
        except Exception as e:
            logging.error(f"Request error: {e}")
            time.sleep(delay)
            delay *= 2
    return None

def enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Type casting and adding missing columns according to standard Schema."""
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
# FETCH INSTRUMENTS
# =========================================================

def fetch_option_instruments(currency="BTC"):
    logging.info(f"📥 Fetching option instruments for {currency}")
    # Config params BTC/ETH
    url = f"{DERIBIT_BASE_URL}/public/get_instruments"
    params = {"currency": currency, "kind": "option", "expired": "false"}

    data = safe_request(url, params)
    if not data or "result" not in data:
        return []

    instruments = data["result"]
    logging.info(f"✅ {currency}: {len(instruments)} active options")

    return instruments

# =========================================================
# FETCH ORDERBOOK
# =========================================================

def fetch_option_orderbook(instrument_name):
    url = f"{DERIBIT_BASE_URL}/public/get_order_book"
    # Config params orderbook
    params = {"instrument_name": instrument_name}

    data = safe_request(url, params)
    time.sleep(1)
    if not data or "result" not in data:
        return None

    return data["result"]

# =========================================================
# PARSE OPTION
# =========================================================
def parse_option_data(orderbook, run_id):
    try:
        timestamp_ms = orderbook.get("timestamp")
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        
        # BTC-27MAR26-60000-C (BTC, 27 MAR 2026, 60000 USD, CALL)
        instrument_name = orderbook.get("instrument_name")
        parts = instrument_name.split("-")
        underlying = parts[0]
        expiry = parts[1]
        strike = float(parts[2])
        option_type = parts[3]

        row = {
            "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"), # Timestamp
            "date": dt.strftime("%Y-%m-%d"),
            "hour": dt.strftime("%H"),

            "instrument_name": instrument_name, # Instrument name
            "underlying": underlying, # Coin
            "expiry": expiry, # Expiry
            "strike": strike, # Strike
            "option_type": option_type, # Option type (CALL/PUT)

            "underlying_price": orderbook.get("underlying_price"), # Underlying price (real price)
            "index_price": orderbook.get("index_price"), # Index price (avg real price)
            "mark_price": orderbook.get("mark_price"), # Mark price (the true value of the ticket)
            "mark_iv": orderbook.get("mark_iv"), # Mark IV (Implied Volatility)

            "best_bid_price": orderbook.get("best_bid_price"), # Best price you can buy
            "best_ask_price": orderbook.get("best_ask_price"), # Best price you can sell

            "bid_iv": orderbook.get("bid_iv"), # It is a volatility index calculated based on the best_bid price.
            "ask_iv": orderbook.get("ask_iv"), # It is a volatility index calculated based on the best_ask price level.

            "last_price": orderbook.get("last_price"), # This is the price of the most recent transaction.
            "open_interest": orderbook.get("open_interest"), # Total number of contracts currently in existence

            "volume": orderbook.get("stats", {}).get("volume"), #same as volume_usd
            "volume_usd": orderbook.get("stats", {}).get("volume_usd"), #Total number of contracts that changed hands in the last 24 hours.(USD)
            
            # GREEKS (Greeks are the key figures that describe the volatility of the underlying asset.)
            "delta": orderbook.get("greeks", {}).get("delta"), # Tell me by how much the ticket price will increase/decrease if the price of Bitcoin increases by $1.
            "gamma": orderbook.get("greeks", {}).get("gamma"), # Measure the degree of change of Delta.
            "vega": orderbook.get("greeks", {}).get("vega"), # Measuring sensitivity to changes in IV
            "theta": orderbook.get("greeks", {}).get("theta"), # Measure the depreciation of value over time.
            "rho": orderbook.get("greeks", {}).get("rho"), # Measure the impact of interest rates on loans.

            # METADATA
            "source": "deribit",
            "run_id": run_id,
            "ingestion_time": datetime.utcnow(),
            "year": dt.strftime("%Y"),
            "month": dt.strftime("%m"),
            "day": dt.strftime("%d")
        }
        return row

    except Exception as e:
        logging.error(f"Parse error: {e}")
        return None

# =========================================================
# FETCH ALL OPTIONS
# =========================================================
def collect_options_for_coin(currency, run_id):
    instruments = fetch_option_instruments(currency)
    if not instruments:
        return pd.DataFrame()
    rows = []
    # Instead of processing each ticket individually, divide the task among the workers so they can ask for information faster.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for instrument in instruments:
            instrument_name = instrument["instrument_name"]
            # executor.submit(function_to_execute, parameter_1, parameter_2, ...)
            futures.append(executor.submit(fetch_option_orderbook, instrument_name))

        # Once the data is available, proceed immediately without waiting.
        for future in as_completed(futures):
            try:
                orderbook = future.result()
                if not orderbook:
                    continue
                row = parse_option_data(orderbook, run_id)
                if row:
                    rows.append(row)

            except Exception as e:
                logging.error(f"Future error: {e}")
    df = pd.DataFrame(rows)
    logging.info(f"✅ Final {currency} rows: {len(df)}\n")
    return df

# =========================================================
# FEATURE ENGINEERING
# =========================================================
def enrich_option_features(df):
    if df.empty:
        return df

    df["moneyness"] = (df["underlying_price"] / df["strike"]) # Moneyness(A price > 1.0 indicates a profit (with Call), a price < 1.0 indicates a loss.)
    df["is_atm"] = (abs(df["moneyness"] - 1.0) <= 0.02) # ATM flag (Mark True if the market price is very close to the strike price.)
    df["iv_spread"] = (df["ask_iv"] - df["bid_iv"]) # IV Spread (Subtract the buyer's IV from the seller's IV.)
    df["mid_iv"] = (df["ask_iv"] + df["bid_iv"]) / 2 # Mid IV (Average IV)
    df["is_call"] = (df["option_type"] == "C") # Call/Put flag

    return df

# =========================================================
# MAIN
# =========================================================
def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--coins", nargs="+", default=["BTC", "ETH"])
    parser.add_argument("--manager", type=str, choices=["iceberg", "hive"], default="hive")
    args = parser.parse_args()

    final_dfs = []
    start = time.time()
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    for coin in args.coins:
        coin = coin.upper()
        if coin not in SUPPORTED_COINS:
            logging.warning(f"Unsupported coin: {coin}")
            continue

        logging.info(f"🚀 Collecting {coin} options")
        df = collect_options_for_coin(coin, run_id)
        if df.empty:
            continue

        df = enrich_option_features(df)
        final_dfs.append(df)

    if not final_dfs:
        logging.error("❌ No option data collected.")
        return

    df_final = pd.concat(final_dfs, ignore_index=True)
    if df_final.empty:
        logging.error("❌ Error during Transform (Empty DataFrame). Cancel saving.")
        return
    
    df_final = enforce_schema(df_final)
    if args.manager == "iceberg":
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=OUTPUT_DIR,
            file_prefix="deribit_options",
            partition_cols=None 
        )
    else:
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=OUTPUT_DIR,
            file_prefix="deribit_options",
            partition_cols=["underlying", "year", "month", "day"]
        )
    
    logging.info(f"📊 Total rows: {len(df_final)}")
    
    elapsed = round(time.time() - start, 2)
    logging.info(f"🎉 Completed in {elapsed}s")

if __name__ == "__main__":
    main()