# -*- coding: utf-8 -*-
"""
Backfill Binance Vision raw spot trades locally, aggregate to the SAME schema as
int_market_trades_hourly, and save ONE Parquet file per output day.

This version matches the dbt incremental idea more closely:
  - keep a 3-day rolling window in memory: D-2, D-1, D
  - calculate return_1h and rolling 24h metrics on the full 3-day window
  - output only day D
  - save day D immediately as a small Parquet file
  - slide the window forward and delete older days from memory

Flow:
  Binance Vision daily raw trades ZIP
    -> chunked local aggregation per symbol/day
    -> daily hourly frame, about 24 rows per symbol
    -> rolling 3-day hourly window
    -> output only target day D
    -> local Parquet flat file for Iceberg loading

Use case:
  Backfill int_market_trades_hourly without uploading raw trades to cloud.

Important:
  - This script does NOT upload raw trades.
  - This script does NOT keep a full year in memory.
  - It only keeps hourly aggregates for the rolling window, not raw rows.
  - Do NOT run dbt full-refresh for int_market_trades_hourly after loading this,
    unless you also backfilled raw_crypto.binance_trades_raw.
"""

import argparse
import io
import logging
import os
import sys
import time
import zipfile
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
session.mount("https://", HTTPAdapter(max_retries=retries))

# =========================================================
# TARGET SCHEMA: int_market_trades_hourly
# Keep this aligned with models/intermediate/int_market_trades_hourly.sql
# =========================================================
HOURLY_SCHEMA_COLUMNS = {
    "hour_ts": "datetime64[ns, UTC]",
    "symbol": "string",
    "pair_symbol": "string",

    "open_price": "float64",
    "high_price": "float64",
    "low_price": "float64",
    "close_price": "float64",
    "vwap_price": "float64",

    "trade_count": "int64",
    "unique_trade_count": "int64",
    "base_volume": "float64",
    "quote_volume": "float64",

    "taker_sell_quote_volume": "float64",
    "taker_buy_quote_volume": "float64",
    "taker_buy_quote_ratio": "float64",

    "first_trade_at": "datetime64[ns, UTC]",
    "last_trade_at": "datetime64[ns, UTC]",
    "loaded_at": "datetime64[ns, UTC]",
    "available_at": "datetime64[ns, UTC]",

    "return_1h": "float64",
    "log_return_1h": "float64",
    "quote_volume_24h": "float64",
    "avg_return_24h": "float64",
    "realized_volatility_24h": "float64",
    "quote_volume_zscore_24h": "float64",
}

RAW_COLUMNS = [
    "trade_id",
    "price",
    "quantity",
    "quote_quantity",
    "trade_time",
    "is_buyer_maker",
    "is_best_match",
]

# Normalize symbols to uppercase and remove whitespaces
def normalize_symbols(symbols: Sequence[str]) -> List[str]:
    return [s.upper().strip() for s in symbols if s and s.strip()]

# Get the base symbol from a pair symbol(e.g. BTCUSDT -> BTC)
def base_symbol(pair_symbol: str) -> str:
    pair_symbol = pair_symbol.upper()
    if pair_symbol.endswith("USDT"):
        return pair_symbol[:-4]
    return pair_symbol

# Generate a list of dates between two dates(e.g. 2024-05-01 -> 2024-05-04: [2024-05-01, 2024-05-02, 2024-05-03, 2024-05-04])
def date_range(start_str: str, end_str: str) -> Iterable[str]:
    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
    end_dt = datetime.strptime(end_str, "%Y-%m-%d")
    if end_dt < start_dt:
        raise ValueError("Start date cannot be greater than end date")

    for i in range((end_dt - start_dt).days + 1):
        yield (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")

# Add days to a date(e.g. 2024-05-01 + 3 days = 2024-05-04)
def add_days(date_str: str, days: int) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt + timedelta(days=days)).strftime("%Y-%m-%d")

# Get the current UTC timestamp
def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")

# Get the available_at timestamp for a given hour_ts (e.g. 2024-05-01 00:00:00 -> 2024-05-01 04:30:00)
def available_at_for_hour(hour_ts: pd.Timestamp) -> pd.Timestamp:
    """
    Match dbt logic:
    TIMESTAMP(DATETIME(DATE_ADD(DATE(hour_ts), INTERVAL 1 DAY), TIME '04:30:00'), 'UTC')
    """
    if hour_ts.tzinfo is None:
        hour_ts = hour_ts.tz_localize("UTC")
    next_date = hour_ts.date() + timedelta(days=1)
    return pd.Timestamp(datetime.combine(next_date, datetime.min.time()), tz="UTC") + pd.Timedelta(hours=4, minutes=30)

# Save a dataframe to a Parquet file in the given directory
def save_dataframe_to_parquet(
    df: pd.DataFrame,
    base_dir: str,
    partition_cols: Optional[List[str]] = None,
    file_prefix: str = "data",
    compression: str = "snappy",
) -> List[str]:
    """Same style as your helper: partition_cols=None means Iceberg flat staging file."""
    # If the dataframe is empty, skip saving it.
    if df is None or df.empty:
        logging.warning("⚠️ DataFrame is empty, skip save.")
        return []

    # Save the dataframe to a flat Parquet file.(Iceberg mode)
    saved_files: List[str] = []
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")

    if not partition_cols:
        os.makedirs(base_dir, exist_ok=True)
        filename = os.path.join(base_dir, f"{file_prefix}_{timestamp}.parquet")
        df.to_parquet(filename, index=False, engine="pyarrow", compression=compression)
        logging.info("✅ [ICEBERG MODE] Saved flat Parquet file: %s", filename)
        saved_files.append(filename)
        return saved_files
    
    # If partition_cols is not None, group the dataframe by the partition columns and save each group to a separate Parquet file.
    missing_cols = [col for col in partition_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"❌ Partition columns not found in DataFrame: {missing_cols}")

    # Create the directory structure for the partitioned Parquet files.(Hive mode)
    # Group the dataframe by the partition columns and save each group to a separate Parquet file.
    groups = df.groupby(partition_cols)
    for group_keys, subset in groups:
        if not isinstance(group_keys, tuple):
            group_keys = (group_keys,)

        partition_path_parts = [f"{col}={val}" for col, val in zip(partition_cols, group_keys)]
        partition_dir = os.path.join(base_dir, *partition_path_parts)
        os.makedirs(partition_dir, exist_ok=True)

        val_str = "_".join(str(v) for v in group_keys)
        filename = os.path.join(partition_dir, f"{file_prefix}_{val_str}_part-{timestamp}.parquet")
        subset.to_parquet(filename, index=False, engine="pyarrow", compression=compression)
        saved_files.append(filename)

    logging.info("✅ Successfully saved %s Hive partitions to: %s", len(saved_files), base_dir)
    return saved_files

# Enforce the hourly schema for the given dataframe.
def enforce_hourly_schema(df: pd.DataFrame) -> pd.DataFrame:
    for col in HOURLY_SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[list(HOURLY_SCHEMA_COLUMNS.keys())].copy()

    for col, dtype in HOURLY_SCHEMA_COLUMNS.items():
        try:
            if "datetime" in dtype:
                df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
            elif dtype == "float64":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
            elif dtype == "int64":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            else:
                df[col] = df[col].astype(dtype)
        except Exception as e:
            logging.warning("⚠️ Schema cast warning %s: %s", col, e)

    return df

# Initialize an empty state dictionary for a given hour_ts and symbol.
def empty_hour_state(symbol: str, pair_symbol: str, hour_ts: pd.Timestamp) -> Dict:
    return {
        "hour_ts": hour_ts,
        "symbol": symbol,
        "pair_symbol": pair_symbol,

        "open_price": np.nan,
        "open_order_ts": pd.Timestamp.max.tz_localize("UTC"),
        "open_order_trade_id": 10**30,

        "high_price": -np.inf,
        "low_price": np.inf,

        "close_price": np.nan,
        "close_order_ts": pd.Timestamp.min.tz_localize("UTC"),
        "close_order_trade_id": -1,

        "sum_price_qty": 0.0,

        "trade_count": 0,
        "unique_trade_count": 0,
        "base_volume": 0.0,
        "quote_volume": 0.0,

        "taker_sell_quote_volume": 0.0,
        "taker_buy_quote_volume": 0.0,

        "first_trade_at": pd.Timestamp.max.tz_localize("UTC"),
        "last_trade_at": pd.Timestamp.min.tz_localize("UTC"),
        "loaded_at": pd.Timestamp.min.tz_localize("UTC"),
    }


# Update the state dictionary with the given chunk.
def update_hourly_state_from_chunk(
    state: Dict[Tuple[str, pd.Timestamp], Dict],
    chunk: pd.DataFrame,
    pair_symbol: str,
    ingestion_time: pd.Timestamp,
) -> int:
    """Aggregate one raw trades chunk into a dictionary keyed by (symbol, hour_ts)."""
    if chunk is None or chunk.empty:
        return 0

    chunk = chunk[chunk["trade_id"].astype(str) != "trade_id"].copy()
    if chunk.empty:
        return 0

    chunk["trade_id"] = pd.to_numeric(chunk["trade_id"], errors="coerce")
    chunk["price"] = pd.to_numeric(chunk["price"], errors="coerce")
    chunk["quantity"] = pd.to_numeric(chunk["quantity"], errors="coerce")
    chunk["quote_quantity"] = pd.to_numeric(chunk["quote_quantity"], errors="coerce")
    chunk["trade_time"] = pd.to_numeric(chunk["trade_time"], errors="coerce").astype("float64")

    # Normalize microseconds to milliseconds if needed.
    mask_micro_or_nano = chunk["trade_time"] > 1e14
    chunk.loc[mask_micro_or_nano, "trade_time"] = (chunk.loc[mask_micro_or_nano, "trade_time"] / 1000.0)

    chunk = chunk[
        chunk["trade_id"].notna()
        & chunk["trade_time"].notna()
        & (chunk["price"] > 0)
        & (chunk["quantity"] > 0)
        & (chunk["quote_quantity"] > 0)
    ].copy()

    if chunk.empty:
        return 0

    chunk["trade_id"] = chunk["trade_id"].astype("int64")
    chunk["trade_ts"] = pd.to_datetime(chunk["trade_time"], unit="ms", utc=True, errors="coerce")
    chunk = chunk[chunk["trade_ts"].notna()].copy()
    if chunk.empty:
        return 0

    base = base_symbol(pair_symbol)
    chunk["hour_ts"] = chunk["trade_ts"].dt.floor("h")

    buyer_maker = chunk["is_buyer_maker"].astype(str).str.lower().isin(["true", "1"])
    chunk["price_x_quantity"] = chunk["price"] * chunk["quantity"]
    chunk["taker_sell_quote_volume"] = np.where(buyer_maker, chunk["quote_quantity"], 0.0)
    chunk["taker_buy_quote_volume"] = np.where(~buyer_maker, chunk["quote_quantity"], 0.0)

    valid_rows = len(chunk)

    for hour_ts, g in chunk.groupby("hour_ts", sort=False):
        key = (base, hour_ts)
        if key not in state:
            state[key] = empty_hour_state(symbol=base, pair_symbol=pair_symbol, hour_ts=hour_ts)

        s = state[key]

        # Reproduce ARRAY_AGG(price ORDER BY trade_ts ASC, trade_id ASC LIMIT 1).
        g_sorted = g.sort_values(["trade_ts", "trade_id"], kind="mergesort")
        first = g_sorted.iloc[0]
        last = g_sorted.iloc[-1]

        first_ts = first["trade_ts"]
        first_trade_id = int(first["trade_id"])
        if (first_ts < s["open_order_ts"]) or (
            first_ts == s["open_order_ts"] and first_trade_id < s["open_order_trade_id"]
        ):
            s["open_price"] = float(first["price"])
            s["open_order_ts"] = first_ts
            s["open_order_trade_id"] = first_trade_id

        last_ts = last["trade_ts"]
        last_trade_id = int(last["trade_id"])
        if (last_ts > s["close_order_ts"]) or (
            last_ts == s["close_order_ts"] and last_trade_id > s["close_order_trade_id"]
        ):
            s["close_price"] = float(last["price"])
            s["close_order_ts"] = last_ts
            s["close_order_trade_id"] = last_trade_id

        s["high_price"] = max(s["high_price"], float(g["price"].max()))
        s["low_price"] = min(s["low_price"], float(g["price"].min()))
        s["sum_price_qty"] += float(g["price_x_quantity"].sum())

        s["trade_count"] += int(len(g))
        s["unique_trade_count"] += int(g["trade_id"].nunique())
        s["base_volume"] += float(g["quantity"].sum())
        s["quote_volume"] += float(g["quote_quantity"].sum())
        s["taker_sell_quote_volume"] += float(g["taker_sell_quote_volume"].sum())
        s["taker_buy_quote_volume"] += float(g["taker_buy_quote_volume"].sum())

        s["first_trade_at"] = min(s["first_trade_at"], g["trade_ts"].min())
        s["last_trade_at"] = max(s["last_trade_at"], g["trade_ts"].max())
        s["loaded_at"] = max(s["loaded_at"], ingestion_time)

    return valid_rows


def state_to_hourly_frame(state: Dict[Tuple[str, pd.Timestamp], Dict]) -> pd.DataFrame:
    rows = []
    for s in state.values():
        vwap = np.nan
        if s["base_volume"] and s["base_volume"] > 0:
            vwap = s["sum_price_qty"] / s["base_volume"]

        taker_buy_quote_ratio = np.nan
        if s["quote_volume"] and s["quote_volume"] > 0:
            taker_buy_quote_ratio = s["taker_buy_quote_volume"] / s["quote_volume"]

        rows.append(
            {
                "hour_ts": s["hour_ts"],
                "symbol": s["symbol"],
                "pair_symbol": s["pair_symbol"],
                "open_price": s["open_price"],
                "high_price": s["high_price"],
                "low_price": s["low_price"],
                "close_price": s["close_price"],
                "vwap_price": vwap,
                "trade_count": s["trade_count"],
                "unique_trade_count": s["unique_trade_count"],
                "base_volume": s["base_volume"],
                "quote_volume": s["quote_volume"],
                "taker_sell_quote_volume": s["taker_sell_quote_volume"],
                "taker_buy_quote_volume": s["taker_buy_quote_volume"],
                "taker_buy_quote_ratio": taker_buy_quote_ratio,
                "first_trade_at": s["first_trade_at"],
                "last_trade_at": s["last_trade_at"],
                "loaded_at": s["loaded_at"],
                "available_at": available_at_for_hour(s["hour_ts"]),
            }
        )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(["symbol", "hour_ts"]).reset_index(drop=True)


def fetch_and_aggregate_daily_symbol(pair_symbol: str, target_date: str, chunksize: int) -> pd.DataFrame:
    pair_symbol = pair_symbol.upper()
    logging.info("📥 Loading raw trades for %s %s from Binance Vision...", pair_symbol, target_date)

    base_url = "https://data.binance.vision/data/spot/daily/trades"
    file_name = f"{pair_symbol}-trades-{target_date}.zip"
    url = f"{base_url}/{pair_symbol}/{file_name}"
    ingestion_time = utc_now()

    try:
        response = session.get(url, stream=True, timeout=180)

        if response.status_code == 404:
            logging.warning("⚠️ No file yet or no data: %s %s", pair_symbol, target_date)
            return pd.DataFrame()

        response.raise_for_status()

        state: Dict[Tuple[str, pd.Timestamp], Dict] = {}
        total_valid_rows = 0

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as csv_file:
                reader = pd.read_csv(
                    csv_file,
                    names=RAW_COLUMNS,
                    chunksize=chunksize,
                    low_memory=False,
                )

                for chunk_idx, chunk in enumerate(reader, start=1):
                    valid_rows = update_hourly_state_from_chunk(
                        state=state,
                        chunk=chunk,
                        pair_symbol=pair_symbol,
                        ingestion_time=ingestion_time,
                    )
                    total_valid_rows += valid_rows

                    if chunk_idx % 10 == 0:
                        logging.info(
                            "   processed chunks=%s | valid raw rows=%s | %s %s",
                            chunk_idx,
                            f"{total_valid_rows:,}",
                            pair_symbol,
                            target_date,
                        )

        hourly_df = state_to_hourly_frame(state)
        if hourly_df.empty:
            logging.warning("⚠️ Empty hourly result: %s %s", pair_symbol, target_date)
            return hourly_df

        logging.info(
            "✅ Aggregated %s raw rows -> %s hourly rows | %s | %s",
            f"{total_valid_rows:,}",
            f"{len(hourly_df):,}",
            pair_symbol,
            target_date,
        )
        return hourly_df

    except Exception as e:
        logging.error("❌ Failed fetching/aggregating %s %s: %s", pair_symbol, target_date, e)
        return pd.DataFrame()


def add_rolling_features(hourly_df: pd.DataFrame) -> pd.DataFrame:
    if hourly_df.empty:
        return hourly_df

    df = hourly_df.copy()
    df["hour_ts"] = pd.to_datetime(df["hour_ts"], utc=True)
    df = df.sort_values(["symbol", "hour_ts"]).reset_index(drop=True)

    parts: List[pd.DataFrame] = []

    for symbol, g in df.groupby("symbol", sort=False):
        g = g.sort_values("hour_ts").copy()

        prev_close = g["close_price"].shift(1)
        g["return_1h"] = (g["close_price"] - prev_close) / prev_close.replace({0: np.nan})

        g["log_return_1h"] = np.where(
            (g["close_price"] > 0) & (prev_close > 0),
            np.log(g["close_price"] / prev_close),
            np.nan,
        )

        # Match BigQuery ROWS BETWEEN 23 PRECEDING AND CURRENT ROW.
        g["quote_volume_24h"] = g["quote_volume"].rolling(window=24, min_periods=1).sum()
        g["avg_return_24h"] = g["return_1h"].rolling(window=24, min_periods=1).mean()
        g["realized_volatility_24h"] = g["log_return_1h"].rolling(window=24, min_periods=2).std(ddof=1)

        rolling_mean_quote = g["quote_volume"].rolling(window=24, min_periods=1).mean()
        rolling_std_quote = g["quote_volume"].rolling(window=24, min_periods=2).std(ddof=1)
        g["quote_volume_zscore_24h"] = (g["quote_volume"] - rolling_mean_quote) / rolling_std_quote.replace({0: np.nan})

        parts.append(g)

    return pd.concat(parts, ignore_index=True)


def filter_one_output_day(df: pd.DataFrame, output_date: str) -> pd.DataFrame:
    start_ts = pd.Timestamp(output_date, tz="UTC")
    end_ts = pd.Timestamp(add_days(output_date, 1), tz="UTC")
    return df[(df["hour_ts"] >= start_ts) & (df["hour_ts"] < end_ts)].copy()


def day_marker_path(output_dir: str, output_date: str, symbols: Sequence[str]) -> str:
    key = "__".join(normalize_symbols(symbols))
    return os.path.join(output_dir, "_state", "hourly_daily_window", key, f"{output_date}.success")


def already_done_day(output_dir: str, output_date: str, symbols: Sequence[str]) -> bool:
    return os.path.exists(day_marker_path(output_dir, output_date, symbols))


def mark_success_day(output_dir: str, output_date: str, symbols: Sequence[str], saved_files: List[str]) -> None:
    marker = day_marker_path(output_dir, output_date, symbols)
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write("\n".join(saved_files))


def fetch_and_aggregate_day_all_symbols(target_date: str, symbols: Sequence[str], chunksize: int, sleep: float) -> pd.DataFrame:
    daily_frames: List[pd.DataFrame] = []
    for pair_symbol in symbols:
        df_hourly = fetch_and_aggregate_daily_symbol(
            pair_symbol=pair_symbol,
            target_date=target_date,
            chunksize=chunksize,
        )
        if not df_hourly.empty:
            daily_frames.append(df_hourly)
        time.sleep(sleep)

    if not daily_frames:
        return pd.DataFrame()

    return pd.concat(daily_frames, ignore_index=True)


def parse_args() -> argparse.Namespace:
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(
        description="Backfill Binance raw trades locally, aggregate to hourly int schema, save one day at a time with 3-day window."
    )
    parser.add_argument("--start", type=str, default=yesterday, help="Output start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=yesterday, help="Output end date YYYY-MM-DD")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTCUSDT", "ETHUSDT"],
        help="Pair symbols to backfill, e.g. BTCUSDT ETHUSDT",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.environ.get("OUTPUT_DIR", "output_data/binance_market_hourly_backfill"),
        help="Local staging dir. The Iceberg loader scans this dir.",
    )
    parser.add_argument("--compression", type=str, default="snappy", choices=["snappy", "gzip", "brotli"])
    parser.add_argument("--chunksize", type=int, default=500_000, help="Raw CSV rows per chunk")
    parser.add_argument("--sleep", type=float, default=1.0, help="Sleep seconds between symbol requests")
    parser.add_argument(
        "--window-days",
        type=int,
        default=3,
        help="Rolling calendar-day window to keep in memory. Default 3 means D-2, D-1, D.",
    )
    parser.add_argument("--force", action="store_true", help="Recompute days even if day marker exists")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.symbols = normalize_symbols(args.symbols)
    os.makedirs(args.output_dir, exist_ok=True)

    if args.window_days < 2:
        raise ValueError("--window-days should be at least 2. Recommended: 3")

    # Counters
    saved_files_total = 0
    output_rows_total = 0
    skipped_days = 0
    missing_or_empty_days = 0

    # Rolling warmup
    warmup_days = args.window_days - 1
    first_output_date = args.start
    fetch_start = add_days(args.start, -warmup_days)

    # Smart resume:
    # Find first output day that has no success marker.
    if not args.force:
        for d in date_range(args.start, args.end):
            if already_done_day(args.output_dir, d, args.symbols):
                skipped_days += 1
                continue

            first_output_date = d
            fetch_start = add_days(first_output_date, -warmup_days)
            break
        else:
            logging.info(
                "⏭️ All output days already done: %s -> %s %s",
                args.start,
                args.end,
                args.symbols,
            )
            return

    logging.info("⚙️ Requested output range: %s -> %s", args.start, args.end)
    logging.info("⚙️ Effective first output date: %s", first_output_date)
    logging.info("⚙️ Rolling window: %s days; fetch starts at %s", args.window_days, fetch_start)
    logging.info("⚙️ Symbols: %s", args.symbols)
    logging.info("⚙️ Output dir: %s", args.output_dir)

    # Buffer stores only hourly aggregates per calendar day, not raw trades.
    day_buffer: Dict[str, pd.DataFrame] = {}

    for current_date in date_range(fetch_start, args.end):
        logging.info("🚀 SCANNING DATE: %s", current_date)

        # Always fetch warmup/current dates so the later output day has context.
        day_df = fetch_and_aggregate_day_all_symbols(
            target_date=current_date,
            symbols=args.symbols,
            chunksize=args.chunksize,
            sleep=args.sleep,
        )

        if day_df.empty:
            logging.warning("⚠️ No hourly rows for buffer date: %s", current_date)
            missing_or_empty_days += 1
        else:
            day_buffer[current_date] = day_df

        # Only output once current_date reaches start.
        if current_date < first_output_date:
            continue

        output_date = current_date

        if not args.force and already_done_day(args.output_dir, output_date, args.symbols):
            logging.info("⏭️ Skip existing successful output day: %s", output_date)
            skipped_days += 1
        else:
            window_dates = [add_days(output_date, -i) for i in range(warmup_days, -1, -1)]
            window_frames = [day_buffer[d] for d in window_dates if d in day_buffer and not day_buffer[d].empty]

            if not window_frames:
                logging.warning("⚠️ No frames available for output day %s; skip.", output_date)
                missing_or_empty_days += 1
            else:
                df_window = pd.concat(window_frames, ignore_index=True)
                df_window = add_rolling_features(df_window)
                df_out = filter_one_output_day(df_window, output_date)
                df_out = enforce_hourly_schema(df_out)

                if df_out.empty:
                    logging.warning("⚠️ Output day has no rows after filtering: %s", output_date)
                    missing_or_empty_days += 1
                else:
                    symbol_key = "_".join(args.symbols)
                    file_prefix = f"binance_market_hourly_{output_date}_{symbol_key}"
                    saved_files = save_dataframe_to_parquet(
                        df=df_out,
                        base_dir=args.output_dir,
                        file_prefix=file_prefix,
                        partition_cols=None,
                        compression=args.compression,
                    )

                    if saved_files:
                        mark_success_day(args.output_dir, output_date, args.symbols, saved_files)
                        saved_files_total += len(saved_files)
                        output_rows_total += len(df_out)
                        logging.info(
                            "✅ Saved output day %s | rows=%s | min_hour=%s | max_hour=%s",
                            output_date,
                            f"{len(df_out):,}",
                            df_out["hour_ts"].min(),
                            df_out["hour_ts"].max(),
                        )

        # Keep only the last window_days in memory.
        oldest_needed = add_days(output_date, -warmup_days)
        for d in list(day_buffer.keys()):
            if d < oldest_needed:
                del day_buffer[d]
                logging.info("🧹 Removed old buffer day from RAM: %s", d)

    logging.info(
        "🎉 Daily-window hourly backfill complete | saved_files=%s | rows=%s | skipped_days=%s | missing_or_empty_days=%s",
        saved_files_total,
        f"{output_rows_total:,}",
        skipped_days,
        missing_or_empty_days,
    )


if __name__ == "__main__":
    main()
