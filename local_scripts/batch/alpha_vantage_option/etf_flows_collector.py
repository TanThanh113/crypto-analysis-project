# -*- coding: utf-8 -*-

import os
import time
import requests
import pandas as pd
import logging
import argparse
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# =========================================================
# CONFIG
# =========================================================
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/etf_flows")

# API Key của bạn (nhớ gán biến môi trường khi chạy terminal)
API_KEY = os.getenv("ALPHA_VANTAGE_ETF_API_KEY", "demo") 

AV_SYMBOLS = { 
    "IBIT": "IBIT", "FBTC": "FBTC", "GBTC": "GBTC", 
    "BITB": "BITB", "ARKB": "ARKB", "HODL": "HODL", 
    "BTCO": "BTCO", "EZBC": "EZBC", "BTCW": "BTCW", "BRRR": "BRRR",
    "ETHA": "ETHA", "FETH": "FETH", "ETHE": "ETHE", "ETHW": "ETHW"
}

# =========================================================
# FETCH ALPHA VANTAGE
# =========================================================
def fetch_alpha_vantage(symbol_name, market_symbol, start_dt, end_dt):
    logging.info(f"📥 Fetching {symbol_name} ({market_symbol}) from Alpha Vantage...")

    try:
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": market_symbol,
            "outputsize": "compact", # <--- ĐÃ SỬA THÀNH COMPACT (Dùng được cho gói Free)
            "apikey": API_KEY
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Kiểm tra lỗi API (Rate limit, Invalid Key...)
        if "Information" in data:
            logging.warning(f"⚠️ API Info/Limit: {data['Information']}")
            return pd.DataFrame()
        if "Error Message" in data:
            logging.error(f"❌ API Error: {data['Error Message']}")
            return pd.DataFrame()

        ts = data.get("Time Series (Daily)", {})
        if not ts:
            logging.warning(f"⚠️ Empty data {symbol_name}")
            return pd.DataFrame()

        rows = []
        for date_str, values in ts.items():
            rows.append({
                "date": pd.to_datetime(date_str, utc=True),
                "open": float(values["1. open"]),
                "high": float(values["2. high"]),
                "low": float(values["3. low"]),
                "close": float(values["4. close"]),
                "volume": float(values["5. volume"])
            })

        df = pd.DataFrame(rows)

        # Lọc dữ liệu theo start_dt và end_dt
        start_tz = pd.Timestamp(start_dt, tz="UTC")
        end_tz = pd.Timestamp(end_dt, tz="UTC")
        df = df[(df["date"] >= start_tz) & (df["date"] <= end_tz)]

        if df.empty:
            logging.warning(f"⚠️ No data in the specified date range for {symbol_name}")
            return pd.DataFrame()

        df = df.sort_values("date")
        df["timestamp"] = df["date"].astype("int64") // 10**9
        df["symbol"] = symbol_name
        df["asset_class"] = "etf_crypto"
        df["adj_close"] = df["close"]
        df["exchange"] = "alpha_vantage"
        df["source"] = "alpha_vantage"
        df["currency"] = "USD"
        df["timeframe"] = "1d"
        df["vwap"] = None
        df["trade_count"] = None
        df["data_provider"] = "alpha_vantage"
        
        df["ingestion_time"] = datetime.utcnow()
        df["year"] = df["date"].dt.year.astype(str)
        df["month"] = df["date"].dt.month.astype(str).str.zfill(2)
        df["day"] = df["date"].dt.day.astype(str).str.zfill(2)

        keep_cols = [
            "date", "timestamp", "symbol", "asset_class", "open", "high", "low", "close",
            "adj_close", "volume", "vwap", "trade_count", "exchange", "source",
            "currency", "timeframe", "data_provider", "ingestion_time", "year", "month", "day"
        ]
        return df[keep_cols]

    except Exception as e:
        logging.error(f"❌ ERROR {symbol_name}: {e}")
        return pd.DataFrame()

# =========================================================
# COLLECTOR
# =========================================================
def collect_all(start_dt, end_dt):
    dfs = []
    for sym_name, av_sym in AV_SYMBOLS.items():
        df = fetch_alpha_vantage(sym_name, av_sym, start_dt, end_dt)
        if not df.empty:
            dfs.append(df)
        
        # NGỦ 12 GIÂY ĐỂ TRÁNH LỖI RATE LIMIT (5 req/phút của Alpha Vantage Free)
        logging.info("⏳ Sleeping 15s to respect Alpha Vantage rate limits...")
        time.sleep(12) 
        
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)

# =========================================================
# SAVE PARQUET
# =========================================================
def save_parquet(df, output_dir, start_str, end_str):
    if df.empty:
        logging.warning("⚠️ Empty DataFrame. Skip saving.")
        return
    today = datetime.utcnow()
    for symbol in df["symbol"].unique():
        subset = df[df["symbol"] == symbol]
        partition_path = (
            f"{output_dir}/"
            f"symbol={symbol}/"
            f"year={today.year}/"
            f"month={today.month:02d}/"
            f"day={today.day:02d}"
        )
        os.makedirs(partition_path, exist_ok=True)
    
        filename = f"{partition_path}/macro_full_{start_str}_to_{end_str}.parquet"
        subset.to_parquet(filename, engine='pyarrow', index=False)
        logging.info(f"🎉 Saved parquet: {filename}")

# =========================================================
# MAIN
# =========================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=OUTPUT_DIR)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    args = parser.parse_args()

    logging.info("🚀 Starting Macro Extract Pipeline (Alpha Vantage ELT)")

    if not API_KEY or API_KEY == "demo":
        logging.warning("⚠️ ALPHA_VANTAGE_API_KEY is missing or set to demo. You might hit limits.")

    if not args.start or not args.end:
        logging.info("⚙️ Running DAILY mode (Fetching last 2 days)...")
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=7)
    else:
        logging.info(f"⚙️ Running BACKFILL mode {args.start} -> {args.end}...")
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
        end_dt = datetime.strptime(args.end, "%Y-%m-%d")

    df_final = collect_all(start_dt, end_dt)

    if df_final.empty:
        logging.error("❌ Pipeline failed. No macro data collected.")
        return
    df_final = df_final.drop_duplicates(subset=["date", "symbol"])

    start_str = start_dt.strftime('%Y-%m-%d')
    end_str = end_dt.strftime('%Y-%m-%d')
    save_parquet(df_final, args.output, start_str, end_str)
    
    logging.info(f"🎉 Completed successfully | total_rows={len(df_final)}")
    print("\n📊 RAW DATA SAMPLE:")
    print(df_final[['date', 'symbol', 'asset_class', 'close', 'source']].head(7).to_string(index=False))

if __name__ == "__main__":
    main()