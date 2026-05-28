# -*- coding: utf-8 -*-

import os
import time
import logging
import argparse
import requests
import pandas as pd
import sys

from datetime import datetime, timezone
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
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/funding")

SYMBOLS = ["BTC", "ETH"]
MAX_WORKERS = 16
REQUEST_TIMEOUT = 10

SCHEMA_COLUMNS = {
    # Identifier
    "exchange": "string",
    "symbol": "string",
    "timestamp": "string",
    "date": "string",
    
    # Spot vs Futures
    "mark_price": "float64",
    "spot_price": "float64",
    "basis_spread": "float64",
    "basis_pct": "float64",
    
    # Funding
    "funding_rate_coin": "float64",
    "funding_rate_usdt": "float64",
    
    # Converted to Annualized Years
    "annualized_funding_coin": "float64",
    "annualized_funding_usdt": "float64",
    "annualized_basis_coin": "float64",
    "annualized_basis_usdt": "float64",
    
    # Arbitrage Profit
    "arbitrage_spread": "float64",
    "next_funding_time": "float64",
    
    # Feature Engineering
    "funding_regime": "string",
    "arbitrage_opportunity": "string",
    "leverage_stress": "float64",

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
# BINANCE
# =========================================================

def fetch_binance_funding(base_symbol, run_id):
    try:
        funding_usdt = 0
        funding_coin = 0
        data_coin_source = None

        # USDT-M
        usdt_symbol = f"{base_symbol}USDT"
        url_usdt = "https://fapi.binance.com/fapi/v1/premiumIndex"
        data_usdt = safe_request(url_usdt, params={"symbol": usdt_symbol})

        if data_usdt and isinstance(data_usdt, dict):
            funding_usdt = float(data_usdt.get("lastFundingRate", 0))

        # COIN-M
        coin_m_symbol = f"{base_symbol}USD_PERP"
        url_coin = "https://dapi.binance.com/dapi/v1/premiumIndex"
        data_coin_source = safe_request(url_coin, params={"symbol": coin_m_symbol})

        if data_coin_source and isinstance(data_coin_source, list) and len(data_coin_source) > 0:
            data_coin = data_coin_source[0]
            funding_coin = float(data_coin.get("lastFundingRate", 0))
            
            mark_price = float(data_coin.get("markPrice", 0)) # Bitcoin price on the Futures market
            index_price = float(data_coin.get("indexPrice", 0)) # The "real" price of Bitcoin on the Spot market.
            next_funding_time = data_coin.get("nextFundingTime")
            
            # Calculate the percentage deviation of the Futures price from the Spot price.
            basis_pct = ((mark_price - index_price) / index_price) * 100 if index_price > 0 else 0
            
            # Calculate the annualized conversion array
            annualized_basis_usdt = funding_usdt * 3 * 365 * 100 # Calculate the annual interest rate at the basic rate.
            annualized_basis_coin = funding_coin * 3 * 365 * 100

            now = datetime.utcnow()
            row = {
                "exchange": "binance_coin_m", # Exchange name
                "symbol": base_symbol, # Symbol name

                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), # Timestamp
                "date": datetime.utcnow().strftime("%Y-%m-%d"), # Date

                "mark_price": mark_price, 
                "spot_price": index_price, 
                "basis_spread": mark_price - index_price,
                "basis_pct": basis_pct, 

                "funding_rate_coin": funding_coin,
                "funding_rate_usdt": funding_usdt,
                "annualized_funding_coin": funding_coin * 3 * 365 * 100,
                "annualized_funding_usdt": funding_usdt * 3 * 365 * 100,
                "annualized_basis_coin": annualized_basis_coin,
                "annualized_basis_usdt": annualized_basis_usdt,
                "arbitrage_spread": annualized_basis_coin - annualized_basis_usdt,
                "next_funding_time": next_funding_time, 

                # Metadata
                "source": "binance",
                "run_id": run_id,
                "ingestion_time": now,
                "year": now.strftime("%Y"),
                "month": now.strftime("%m"),
                "day": now.strftime("%d")
            }
            return row
        else:
            logging.warning(f"No COIN-M data found for {base_symbol}")
            return None

    except Exception as e:
        logging.error(f"Binance parse error: {e}")
        return None
# =========================================================
# BYBIT
# =========================================================
def fetch_bybit_funding(base_symbol, run_id):
    try:
        url = "https://api.bybit.com/v5/market/tickers"
        
        # USDT-M (Linear)
        funding_usdt = 0
        data_usdt = safe_request(url, params={"category": "linear", "symbol": f"{base_symbol}USDT"})
        if data_usdt and "result" in data_usdt and "list" in data_usdt["result"] and len(data_usdt["result"]["list"]) > 0:
            funding_usdt = float(data_usdt["result"]["list"][0].get("fundingRate", 0))

        # COIN-M (Inverse)
        data_coin = safe_request(url, params={"category": "inverse", "symbol": f"{base_symbol}USD"})
        if data_coin and "result" in data_coin and "list" in data_coin["result"] and len(data_coin["result"]["list"]) > 0:
            ticker = data_coin["result"]["list"][0]
            
            funding_coin = float(ticker.get("fundingRate", 0))
            mark_price = float(ticker.get("markPrice", 0))
            index_price = float(ticker.get("indexPrice", 0))
            next_funding_time = ticker.get("nextFundingTime")
            
            basis_pct = ((mark_price - index_price) / index_price) * 100 if index_price > 0 else 0
            
            annualized_basis_usdt = funding_usdt * 3 * 365 * 100
            annualized_basis_coin = funding_coin * 3 * 365 * 100

            now = datetime.utcnow()
            row = {
                "exchange": "bybit_coin_m",
                "symbol": base_symbol,

                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "date": datetime.utcnow().strftime("%Y-%m-%d"),

                "mark_price": mark_price, 
                "spot_price": index_price, 
                "basis_spread": mark_price - index_price,
                "basis_pct": basis_pct, 

                "funding_rate_coin": funding_coin,
                "funding_rate_usdt": funding_usdt,
                "annualized_funding_coin": annualized_basis_coin,
                "annualized_funding_usdt": annualized_basis_usdt,
                "annualized_basis_coin": annualized_basis_coin,
                "annualized_basis_usdt": annualized_basis_usdt,
                "arbitrage_spread": annualized_basis_coin - annualized_basis_usdt,
                "next_funding_time": next_funding_time, 

                # Metadata
                "source": "bybit",
                "run_id": run_id,
                "ingestion_time": now,
                "year": now.strftime("%Y"),
                "month": now.strftime("%m"),
                "day": now.strftime("%d")
            }
            return row
    
        else:
            logging.warning(f"No Bybit Inverse (COIN-M) data found for {base_symbol}")
            return None
        
    except Exception as e:
        logging.error(f"Bybit parse error: {e}")
        return None

# =========================================================
# OKX
# =========================================================
def fetch_okx_funding(base_symbol, run_id):
    try:
        url = "https://www.okx.com/api/v5/public/funding-rate"
        ticker_url = "https://www.okx.com/api/v5/market/ticker"

        funding_usdt = 0
        funding_coin = 0
        next_funding_time = None
        mark_price = 0
        spot_price = 0

        # USDT-M
        usdt_instId = f"{base_symbol}-USDT-SWAP"
        data_usdt = safe_request(url, params={"instId": usdt_instId})
        if data_usdt and "data" in data_usdt and isinstance(data_usdt["data"], list) and len(data_usdt["data"]) > 0:
            funding_usdt = float(data_usdt["data"][0].get("fundingRate", 0))

        # COIN-M
        coin_instId = f"{base_symbol}-USD-SWAP"
        coin_data = safe_request(url, params={"instId": coin_instId})
        
        if coin_data and "data" in coin_data and isinstance(coin_data["data"], list) and len(coin_data["data"]) > 0:
            data_item = coin_data["data"][0]
            funding_coin = float(data_item.get("fundingRate", 0))
            next_funding_time = data_item.get("nextFundingTime") # Return timestamp mili-giây
            
            # Mark Price Proxy
            coin_ticker = safe_request(ticker_url, params={"instId": coin_instId})
            if coin_ticker and "data" in coin_ticker and len(coin_ticker["data"]) > 0:
                mark_price = float(coin_ticker["data"][0].get("last", 0))
                
            # Spot Price Proxy
            spot_instId = f"{base_symbol}-USDT"
            spot_ticker = safe_request(ticker_url, params={"instId": spot_instId})
            if spot_ticker and "data" in spot_ticker and len(spot_ticker["data"]) > 0:
                spot_price = float(spot_ticker["data"][0].get("last", 0))

            basis_spread = mark_price - spot_price if (mark_price and spot_price) else 0
            basis_pct = ((mark_price - spot_price) / spot_price) * 100 if (mark_price and spot_price > 0) else 0

            annualized_basis_usdt = funding_usdt * 3 * 365 * 100
            annualized_basis_coin = funding_coin * 3 * 365 * 100

            now = datetime.utcnow()
            row = {
                "exchange": "okx_coin_m",
                "symbol": base_symbol,

                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "date": datetime.utcnow().strftime("%Y-%m-%d"),

                "mark_price": mark_price,
                "spot_price": spot_price,
                "basis_spread": basis_spread,
                "basis_pct": basis_pct,

                "funding_rate_coin": funding_coin,
                "funding_rate_usdt": funding_usdt,
                "annualized_funding_coin": annualized_basis_coin,
                "annualized_funding_usdt": annualized_basis_usdt,
                "annualized_basis_coin": annualized_basis_coin,
                "annualized_basis_usdt": annualized_basis_usdt,
                "arbitrage_spread": annualized_basis_coin - annualized_basis_usdt,
                "next_funding_time": next_funding_time, 

                # Metadata
                "source": "okx",
                "run_id": run_id,
                "ingestion_time": now,
                "year": now.strftime("%Y"),
                "month": now.strftime("%m"),
                "day": now.strftime("%d")
            }
            return row
        else:
            logging.warning(f"No OKX Inverse (COIN-M) data found for {base_symbol}")
            return None
    except Exception as e:
        logging.error(f"OKX parse error: {e}")
        return None

# =========================================================
# COLLECTOR
# =========================================================
def collect_all(run_id):
    rows = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for symbol in SYMBOLS:
            # executor.submit(function_to_execute, parameter_1, parameter_2, ...)
            futures.append(executor.submit(fetch_binance_funding, symbol, run_id))
            futures.append(executor.submit(fetch_bybit_funding, symbol, run_id))
            futures.append(executor.submit(fetch_okx_funding, symbol, run_id))

        # Once the data is available, proceed immediately without waiting.
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    rows.append(result)
            except Exception as e:
                logging.error(f"Future error: {e}")
    df = pd.DataFrame(rows)
    return df

# =========================================================
# FEATURE ENGINEERING
# =========================================================
def enrich_features(df):
    if df.empty:
        return df
    logging.info("⚙️ Building funding features")
    def classify_funding(x):
        if x >= 10.0:
            return "extreme_long"  
        elif x >= 2.0:
            return "long_bias"  
        elif x <= -10.0:
            return "extreme_short"  
        elif x <= -2.0:
            return "short_bias"  
        return "neutral"

    df["funding_regime"] = df["annualized_funding_coin"].apply(classify_funding)
    def classify_arbitrage(spread):
        if spread >= 5.0:
            return "FAVOR_USDT_M"
        elif spread <= -5.0:
            return "FAVOR_COIN_M"
        return "BALANCED"

    df["arbitrage_opportunity"] = df["arbitrage_spread"].apply(classify_arbitrage)

    df["leverage_stress"] = (abs(df["annualized_funding_coin"]) * abs(df["basis_pct"].fillna(0)))
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
    logging.info("🚀 Starting funding collector")

    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    df = collect_all(run_id)
    if df.empty:
        logging.error("❌ No funding data collected")
        return

    df_final = enrich_features(df)
    if df_final.empty:
        logging.error("❌ Error during Transform (Empty DataFrame). Cancel saving.")
        return
    
    df_final = enforce_schema(df_final)

    if args.manager == "iceberg":
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=args.output,
            file_prefix="funding_rates",
            partition_cols=None 
        )
    else:
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=args.output,
            file_prefix="funding_rates",
            partition_cols=["exchange", "symbol", "year", "month", "day"]
        )

    logging.info(f"📊 Data streams {len(df)} have been collected from all 3 exchanges.")
    logging.info("\n📈 FUNDING GAP OPPORTUNITY REPORT (% ANNUAL):")

    df_print = df[["exchange", "symbol", "annualized_funding_usdt", "annualized_funding_coin", "arbitrage_spread"]].copy()
    df_print["annualized_funding_usdt"] = df_print["annualized_funding_usdt"].apply(lambda x: f"{x:.2f}%")
    df_print["annualized_funding_coin"] = df_print["annualized_funding_coin"].apply(lambda x: f"{x:.2f}%")
    df_print["arbitrage_spread"] = df_print["arbitrage_spread"].apply(lambda x: f"{x:.2f}%")

    print(df_print.to_string(index=False))
    
    logging.info(f"🎉 Complete it at lightning speed in {round(time.time() - start, 2)}s")

if __name__ == "__main__":
    main()