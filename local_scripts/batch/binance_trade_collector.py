# -*- coding: utf-8 -*-
import os
import io
import time
import zipfile
import requests
import pandas as pd
import logging
import argparse
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

from save_dataframe_to_parquet import save_dataframe_to_parquet
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stdout)
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=5,
    status_forcelist=[429, 500, 502, 503, 504],
    raise_on_status=False
)
session.mount("https://", HTTPAdapter(max_retries=retries))

# =========================================================
# CONFIG & SCHEMA
# =========================================================
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/binance_batch_trades")

SCHEMA_COLUMNS = {
    # --- Các trường phái sinh & Metadata ---
    "trade_ts": "datetime64[ns, UTC]",
    "trade_time": "float64",
    "symbol": "string",
    "source": "string",
    "data_provider": "string",
    "run_id": "string",
    "ingestion_time": "datetime64[ns, UTC]",
    "year": "string",
    "month": "string",
    "day": "string",
    
    "trade_id": "int64",
    "price": "float64",
    "quantity": "float64",
    "quote_quantity": "float64",     
    "is_buyer_maker": "string",
    "is_best_match": "string"
}

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
            else:
                df[col] = df[col].astype(dtype)
        except Exception as e:
            logging.warning(f"⚠️ Schema cast warning {col}: {e}")
    return df

# =========================================================
# FETCH BINANCE VISION
# =========================================================
def fetch_binance_daily_trades(symbol="BTCUSDT", target_date=None):
    
    # If no date is specified, the default is to go back one day (using yesterday).
    if target_date is None:
        yesterday = datetime.utcnow() - timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")

    symbol = symbol.upper() # Uppercase the symbol
    logging.info(f"📥 Loading {symbol} data for {target_date} from Binance Vision warehouse....")

    # Standard URL structure for Binance Public Data
    base_url = "https://data.binance.vision/data/spot/daily/trades"
    file_name = f"{symbol}-trades-{target_date}.zip"
    url = f"{base_url}/{symbol}/{file_name}"

    try:
        # Load the ZIP file into RAM (use stream=True to avoid memory bottlenecks).
        response = session.get(url, stream=True, timeout=60)
        if response.status_code == 404:
            logging.warning(f"⚠️  Binance has not yet finished compiling the data for the {target_date} date (usually it takes until 3-4 AM UTC).")
            return pd.DataFrame()
        
        response.raise_for_status()

        # Technique for extracting files directly from RAM (Avoid writing junk files to the hard drive)
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_filename = z.namelist()[0]  # Get the CSV filename located inside the zip file.
            
            with z.open(csv_filename) as csv_file:
                # Read using Pandas (Binance CSV files don't have column names, we have to name them ourselves)
                columns = [
                    "trade_id", "price", "quantity", 
                    "quote_quantity", "trade_time", 
                    "is_buyer_maker", "is_best_match"
                ]
                df = pd.read_csv(csv_file, names=columns)

        df = df[df["trade_id"] != "trade_id"].copy()
        df["trade_time"] = df["trade_time"].astype(float)
        df.loc[df["trade_time"] > 1e14, "trade_time"] = df["trade_time"] / 1000

        # Standardize the format to be exactly the same as your streaming stream.
        df["symbol"] = symbol
        df["trade_ts"] = pd.to_datetime(df["trade_time"], unit="ms")

        dt_obj = datetime.strptime(target_date, "%Y-%m-%d")
        df["year"] = str(dt_obj.year)
        df["month"] = f"{dt_obj.month:02d}"
        df["day"] = f"{dt_obj.day:02d}"

        df["source"] = "binance_vision"
        df["data_provider"] = "binance"
        df["run_id"] = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        df["ingestion_time"] = datetime.utcnow()
        
        # Only include the necessary columns in BigQuery/DataLake.
        df_final = enforce_schema(df)

        logging.info(f"✅ Success! The {len(df_final):,} transaction of {symbol} has been extracted.")
        return df_final

    except Exception as e:
        logging.error(f"❌ Error when fetching data from Binance Vision: {e}")
        return pd.DataFrame()

def main():
    parser = argparse.ArgumentParser(description="Binance Historical Trades Batch Pipeline")
    parser.add_argument("--start", type=str, default=None, help="Start date of the YYYY-MM-DD format")
    parser.add_argument("--end", type=str, default=None, help="Start date of the YYYY-MM-DD format")
    parser.add_argument("--manager", type=str, choices=["iceberg", "hive"], default="hive")
    args = parser.parse_args()

    if not args.start or not args.end:
        # DAILY MODE: Binance usually takes 1 day to consolidate zip files, so we'll default to yesterday's date.
        logging.info("⚙️  Running DAILY mode...")
        yesterday = datetime.utcnow() - timedelta(days=1)
        start_str = yesterday.strftime('%Y-%m-%d')
        end_str = start_str
    else:
        # BACKFILL MODE: Based on the time period entered by the user.
        logging.info(f"⚙️ Running BACKFILL {args.start} -> {args.end}")
        start_str = args.start
        end_str = args.end

    # Create a list of dates to download (Date Range Generator)
    start_dt = datetime.strptime(start_str, '%Y-%m-%d')
    end_dt = datetime.strptime(end_str, '%Y-%m-%d')
    delta = end_dt - start_dt
    
    if delta.days < 0:
        logging.error("❌ Error: Start date cannot be greater than end date!")
        return

    # Generate a list of dates: e.g., ['2024-05-01', '2024-05-02', '2024-05-03']
    date_list = [(start_dt + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(delta.days + 1)]

    base_output_dir = os.environ.get("OUTPUT_DIR", "output_data/binance_batch_trades")
    os.makedirs(base_output_dir, exist_ok=True)

    symbols_to_fetch = ["BTCUSDT", "ETHUSDT"]
    
    all_dfs = []

    for target_date in date_list:
        logging.info(f"🚀 SCANNING DATE: {target_date}")
        for sym in symbols_to_fetch:
            df = fetch_binance_daily_trades(symbol=sym, target_date=target_date)
            if not df.empty:
                all_dfs.append(df)
            time.sleep(1)

    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        
        if args.manager == "iceberg":
            save_dataframe_to_parquet(
                df=df_final,
                base_dir=OUTPUT_DIR,
                file_prefix="binance_trades",
                partition_cols=None 
            )
        else:
            save_dataframe_to_parquet(
                df=df_final,
                base_dir=OUTPUT_DIR,
                file_prefix="binance_trades",
                partition_cols=["symbol", "year", "month", "day"]
            )

        logging.info(f"🎉 Pipeline complete! Total {len(df_final):,} rows processed.")
    else:
        logging.error("❌ No data was collected.")

if __name__ == "__main__":
    main()