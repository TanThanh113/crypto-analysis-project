# -*- coding: utf-8 -*-
import os
import time
import logging
import requests
import argparse
import pandas as pd
import numpy as np
import sys

from datetime import datetime
from dotenv import load_dotenv

from save_dataframe_to_parquet import save_dataframe_to_parquet

# =========================================================
# LOGGING & CONFIG
# =========================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output_data/liquidation_map")

SYMBOLS = ["BTCUSDT_PERP.A", "ETHUSDT_PERP.A"]

COINALYZE_API_KEY = os.getenv("COINALYZE_API_KEY")
if not COINALYZE_API_KEY:
    logging.error("🚨 CRITICAL: API Key not found in .env file!")
    exit(1)

SCHEMA_COLUMNS = {
    # Identifier
    "symbol": "string",
    "price_bucket": "float64",
    "snapshot_timestamp": "string",
    
    # Liquidation Value & Volume (Raw)
    "total_liq_usd_bucket": "float64",
    "long_sum": "float64",
    "short_sum": "float64",
    "oi_avg": "float64",
    "vol_sum": "float64",
    "hit_count": "int64",
    
    # Analytical Indicators (Features) 
    "avg_weighted_liq_ratio": "float64",
    "avg_panic": "float64",
    "avg_money_flow": "float64",
    "distance_pct": "float64",
    "weighted_liq_ratio": "float64",
    "distance_decay": "float64",
    "magnet_score": "float64",
    "magnet_zscore": "float64",
    "magnet_norm": "float64",
    
    # Classification & Ranking
    "squeeze_signal": "string",
    "panic_norm": "float64",
    "hit_norm": "float64",
    "rank_score": "float64",
    "dominant_side": "string",
    "stress_level": "string",
    
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
def safe_get(endpoint, symbol):
    logging.info(f"📥 Retrieving {endpoint} for {symbol}...")
    
    # Endpoint retrieves accumulated liquidation data.
    url_base = "https://api.coinalyze.net/v1"
    headers = {"api_key": COINALYZE_API_KEY}
    
    # 24-hour interval: View the accumulated liquidation volume over the past 12 hours.
    end_time = int(time.time())
    start_time = end_time - (24 * 3600)
    
    params = {
        "symbols": symbol,
        "interval": "5min",
        "from": start_time,
        "to": end_time
    }
    res = requests.get(f"{url_base}/{endpoint}", headers=headers, params=params, timeout=15)
    if res.status_code != 200:
        logging.warning(f"⚠️ {endpoint} returns HTTP error {res.status_code}")
        return []
    data = res.json()
    # Check if there is data in the array.
    if not data or not isinstance(data, list) or len(data) == 0:
        logging.warning(f"⚠️ {endpoint} no data available (Empty List)")
        return []
    return data[0].get("history", [])

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
# FETCH LIQUIDATION MAP FROM COINGLASS
# =========================================================
def fetch_liquidation_heatmap(symbol, run_id):

    try:
        # Fetch the data from COINALYZE.
        ohlcv_data = safe_get("ohlcv-history", symbol) # OHLCV (Open, High, Low, Close, Volume)
        time.sleep(1) 
        liq_data = safe_get("liquidation-history", symbol) # Liquidation History
        time.sleep(1)
        oi_data = safe_get("open-interest-history", symbol) # Open Interest

        # Check if the data is available.
        if not ohlcv_data or not liq_data or not oi_data:
            logging.error(f"❌ Missing data piece for {symbol}. Don't calculate Magnet Score.")
            return pd.DataFrame()

        # Rename the columns to perform the join.
        df_p = pd.DataFrame(ohlcv_data).rename(columns={'t': 'time', 'c': 'close', 'v': 'volume'})
        df_l = pd.DataFrame(liq_data).rename(columns={'t': 'time', 'l': 'long_liq', 's': 'short_liq'})
        df_o = pd.DataFrame(oi_data).rename(columns={'t': 'time', 'c': 'oi'})
        df = df_p.merge(df_l, on="time", how="inner").merge(df_o, on="time", how="inner")

        # Handle if no data is available. 
        df['oi'] = df['oi'].ffill().fillna(0) # Using old data or NaN with 0.
        df[['long_liq', 'short_liq']] = (df[['long_liq', 'short_liq']].fillna(0)) # Fill NaN with 0.

        # Calculate the total liquidated value (USD) and volume (USD).
        df['total_liq_usd'] = (df['long_liq'] + df['short_liq']) * df['close']
        df['volume_usd'] = df['volume'] * df['close']

        # Get the current price.
        current_price = df['close'].iloc[-1]

        # Calculate the liquidation ratio. See whether long or short is dominant (normalized to [0,1])
        df['liq_ratio'] = np.where(
            df['long_liq'] + df['short_liq'] > 1,
            (df['long_liq'] - df['short_liq']) / (df['long_liq'] + df['short_liq'] + 1e-9),
            0
        )
        # Multiply by the total liquidation amount to calculate the weighted total liquidation amount.
        df['weighted_liq_ratio'] = (df['liq_ratio'] * df['total_liq_usd']) 

        # Calculate the panic index (Normalize to (0, 100) to avoid outliers.).
        df['panic_index'] = (df['total_liq_usd'] / (df['volume_usd'] + 1e-9)) * 100
        df['panic_index'] = df['panic_index'].clip(0, 100)
        
        # Price clustering to create a heatmap 
        bucket_size = 50 if "BTC" in symbol else 10
        df['price_bucket'] = (df['close'] / bucket_size).round() * bucket_size
        df['oi_delta'] = df['oi'].diff().fillna(0)

        # Calculate the money flow
        # Note: Here, ML compression is used to return the data to [-1, 1].
        price_return = df['close'].pct_change().fillna(0)
        oi_mean = df['oi'].rolling(12, min_periods=1).mean()
        df['money_flow'] = np.tanh(((df['oi_delta'] / (oi_mean + 1e-9)) * price_return) * 100)

        # Group by Price Bucket 
        heatmap = df.groupby('price_bucket').agg(
            total_liq_usd_bucket=('total_liq_usd', 'sum'), # Total liquidated value (USD) in the bucket
            long_sum=('long_liq', 'sum'), # Total liquidated value (USD) for long positions
            short_sum=('short_liq', 'sum'), # Total liquidated value (USD) for short positions
            oi_avg=('oi', 'mean'), # Average open interest
            vol_sum=('volume_usd', 'sum'), # Total volume (USD) in the bucket
            hit_count=('time', 'count'), # Number of liquidations in the bucket
            avg_weighted_liq_ratio=('weighted_liq_ratio', 'sum'), # Average weighted liquidation ratio
            avg_panic=('panic_index', 'mean'), # Average panic index
            avg_money_flow=('money_flow', 'mean') # Average money flow
        ).reset_index()

        # Calculate the distance percentage and weighted liquidation ratio(normalized to total liquidation amount)
        heatmap['distance_pct'] = ((heatmap['price_bucket'] - current_price) / current_price) * 100
        heatmap['weighted_liq_ratio'] = (heatmap['avg_weighted_liq_ratio'] / (heatmap['total_liq_usd_bucket'] + 1e-9)).clip(-1, 1)

        # Use the exponential function to decrease the distance (with lambda = 0.2).
        heatmap['distance_decay'] = np.exp(-abs(heatmap['distance_pct']) / 5)

        # Calculate the raw magnet score (Magnet Score)
        raw_magnet_score = (heatmap['total_liq_usd_bucket'] * heatmap['oi_avg']) / (heatmap['vol_sum'] + 1e-9)
        heatmap['magnet_score'] = raw_magnet_score * heatmap['distance_decay']

        # Calculate the standard deviation of the raw magnet score.
        score_std = heatmap['magnet_score'].std()
        if pd.isna(score_std) or score_std < 1e-9:
            heatmap['magnet_zscore'] = 0
        else:
            heatmap['magnet_zscore'] = (heatmap['magnet_score'] - heatmap['magnet_score'].mean()) / score_std
        heatmap['magnet_norm'] = np.tanh(heatmap['magnet_zscore']) # Normalize the magnet score to [-1, 1]

        # Calculate the squeeze signal (Squeeze Signal)
        heatmap['squeeze_signal'] = np.where(
            (heatmap['avg_money_flow'] > 0.2) & (heatmap['weighted_liq_ratio'] < -0.5),
            "SHORT_SQUEEZE_SETUP",

            np.where(
                (heatmap['avg_money_flow'] < -0.3) & (heatmap['weighted_liq_ratio'] > 0.3),
                "LONG_SQUEEZE_SETUP",
                "NEUTRAL"
            )
        )

        # # Calculate the rank score
        # Normalize the panic index to [0, 1]
        heatmap['panic_norm'] = (
            heatmap['avg_panic'] /
            (heatmap['avg_panic'].max() + 1e-9)
        )
        # Normalize the hit count to [0, 1]
        heatmap['hit_norm'] = (
            heatmap['hit_count'] /
            (heatmap['hit_count'].max() + 1e-9)
        )
        heatmap['rank_score'] = (
            heatmap['magnet_norm'] * 0.5 +
            heatmap['panic_norm'] * 0.2 +
            abs(heatmap['weighted_liq_ratio']) * 0.2 +
            heatmap['hit_norm'] * 0.1
        )   

        # Find the dominant side of the heatmap
        heatmap['dominant_side'] = np.where(heatmap['long_sum'] > heatmap['short_sum'], "LONG_REKT", "SHORT_REKT")
        
        # Classification of attractiveness levels
        def set_stress(val):
            if val > 10_000_000: return "HIGH"
            if val > 2_000_000: return "MEDIUM"
            return "LOW"
        heatmap['stress_level'] = heatmap['total_liq_usd_bucket'].apply(set_stress)

        # Standardized beauty symbol
        heatmap['symbol'] = symbol.split('_')[0]

        # Metadata
        now = datetime.utcnow()
        heatmap['snapshot_timestamp'] = now.strftime('%Y-%m-%d %H:%M:%S')
        heatmap['source'] = "coinalyze"
        heatmap['run_id'] = run_id
        heatmap['ingestion_time'] = now
        heatmap['year'] = now.strftime("%Y")
        heatmap['month'] = now.strftime("%m")
        heatmap['day'] = now.strftime("%d")

        return heatmap

    except Exception as e:
        logging.error(f"❌ Error in Radar {symbol}: {e}")
        return pd.DataFrame()

# =========================================================
# MAIN
# =========================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=OUTPUT_DIR)
    parser.add_argument("--manager", type=str, choices=["iceberg", "hive"], default="hive")
    args = parser.parse_args()

    start_time = time.time()
    final_dfs = []

    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    for sym in SYMBOLS:
        df = fetch_liquidation_heatmap(sym, run_id)
        if not df.empty:
            final_dfs.append(df)
        time.sleep(2)

    if not final_dfs:
        logging.error("❌ No data collected.")
        return

    df_final = pd.concat(final_dfs, ignore_index=True)
    if df_final.empty:
        logging.error("❌ Error during Transform (Empty DataFrame). Cancel saving.")
        return
    
    df_final = enforce_schema(df_final)

    if args.manager == "iceberg":
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=args.output,
            file_prefix="liquidation_map",
            partition_cols=None 
        )
    else:
        save_dataframe_to_parquet(
            df=df_final,
            base_dir=args.output,
            file_prefix="liquidation_map",
            partition_cols=["symbol", "year", "month", "day"]
        )
    
    print("\n🧲 TOP 10 MAGNET ZONES (THE PRICE RANGE WITH THE STRONGEST ATTRACTION):")
    top_clusters = df_final.nlargest(10, "rank_score").copy()

    top_clusters['liq_sum_fmt'] = top_clusters['total_liq_usd_bucket'].apply(lambda x: f"${x:,.0f}")
    top_clusters['rank_score'] = top_clusters['rank_score'].round(3)
    top_clusters['distance'] = top_clusters['distance_pct'].apply(lambda x: f"{x:+.2f}%")
    
    display_cols = ["symbol", "price_bucket", "distance", "liq_sum_fmt", "squeeze_signal", "rank_score"]
    print(top_clusters[display_cols].to_string(index=False))

    logging.info(f"🎉 Complete the 'Data-Rich' Radar in {round(time.time() - start_time, 2)}s")

if __name__ == "__main__":
    main()