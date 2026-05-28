# -*- coding: utf-8 -*-
"""
Backfill Binance USDⓈ-M Futures funding context directly into the SAME schema as
int_funding_hourly, then save small Parquet files for BigQuery loading.

Flow, same idea as the Binance market backfill:
  Binance Futures funding history + hourly mark klines + hourly spot klines
    -> local hourly feature rows
    -> exact int_funding_hourly schema
    -> one Parquet file per output day
    -> BigQuery loader appends to dbt_quants_dev.int_funding_hourly

Notes:
  - Binance funding events are normally every 8 hours. To make the table useful
    for hourly ML joins, this script forward-fills the last known funding rate
    to each hourly row until the next funding event.
  - No raw funding/staging table is written to cloud.
  - Do NOT dbt full-refresh int_funding_hourly after loading this backfill,
    unless you also backfilled stg_funding_rates.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=3,
    status_forcelist=[418, 429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
session.mount("https://", HTTPAdapter(max_retries=retries))

SPOT_BASE_URL = "https://api.binance.com"
FAPI_BASE_URL = "https://fapi.binance.com"
ONE_HOUR_MS = 60 * 60 * 1000
ONE_DAY_MS = 24 * ONE_HOUR_MS

FUNDING_SCHEMA_COLUMNS = {
    "hour_ts": "datetime64[ns, UTC]",
    "symbol": "string",
    "exchanges_reporting": "int64",
    "avg_mark_price": "float64",
    "avg_spot_price": "float64",
    "avg_basis_spread": "float64",
    "avg_basis_pct": "float64",
    "max_abs_basis_pct": "float64",
    "avg_funding_rate_coin": "float64",
    "avg_funding_rate_usdt": "float64",
    "avg_annualized_funding_coin": "float64",
    "avg_annualized_funding_usdt": "float64",
    "funding_dispersion_coin": "float64",
    "avg_annualized_basis_coin": "float64",
    "avg_annualized_basis_usdt": "float64",
    "avg_arbitrage_spread": "float64",
    "max_abs_arbitrage_spread": "float64",
    "max_leverage_stress": "float64",
    "avg_leverage_stress": "float64",
    "dominant_funding_regime": "string",
    "dominant_arbitrage_opportunity": "string",
    "strongest_arbitrage_exchange": "string",
    "highest_stress_exchange": "string",
    "exchange_snapshot_json": "string",
    "latest_observed_at": "datetime64[ns, UTC]",
    "loaded_at": "datetime64[ns, UTC]",
    "available_at": "datetime64[ns, UTC]",
}


def normalize_symbols(symbols: Sequence[str]) -> List[str]:
    return [s.upper().strip() for s in symbols if s and s.strip()]


def base_symbol(pair_symbol: str) -> str:
    pair_symbol = pair_symbol.upper()
    return pair_symbol[:-4] if pair_symbol.endswith("USDT") else pair_symbol


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def date_range(start_str: str, end_str: str) -> Iterable[str]:
    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
    end_dt = datetime.strptime(end_str, "%Y-%m-%d")
    if end_dt < start_dt:
        raise ValueError("Start date cannot be greater than end date")
    for i in range((end_dt - start_dt).days + 1):
        yield (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")


def add_days(date_str: str, days: int) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


def date_to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def request_json(url: str, params: dict, timeout: int = 60):
    response = session.get(url, params=params, timeout=timeout)
    if response.status_code == 429:
        logging.warning("⚠️ Rate limited: %s params=%s", url, params)
        time.sleep(20)
    response.raise_for_status()
    return response.json()


def fetch_klines(base_url: str, endpoint: str, pair_symbol: str, start_ms: int, end_ms: int, sleep: float) -> pd.DataFrame:
    rows = []
    cursor = start_ms
    url = f"{base_url}{endpoint}"

    while cursor < end_ms:
        params = {
            "symbol": pair_symbol,
            "interval": "1h",
            "startTime": cursor,
            "endTime": end_ms - 1,
            "limit": 1000,
        }
        data = request_json(url, params=params, timeout=60)
        if not data:
            break

        rows.extend(data)
        last_open_time = int(data[-1][0])
        next_cursor = last_open_time + ONE_HOUR_MS
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        time.sleep(sleep)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        rows,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "trade_count",
            "taker_buy_base_volume", "taker_buy_quote_volume", "ignore",
        ],
    )
    df["hour_ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df[["hour_ts", "close"]].drop_duplicates("hour_ts").sort_values("hour_ts")
    return df


def fetch_funding_events(pair_symbol: str, start_ms: int, end_ms: int, sleep: float) -> pd.DataFrame:
    url = f"{FAPI_BASE_URL}/fapi/v1/fundingRate"
    rows = []
    cursor = start_ms

    while cursor < end_ms:
        params = {
            "symbol": pair_symbol,
            "startTime": cursor,
            "endTime": end_ms - 1,
            "limit": 1000,
        }
        data = request_json(url, params=params, timeout=60)
        if not data:
            break
        rows.extend(data)

        last_time = int(data[-1]["fundingTime"])
        next_cursor = last_time + 1
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        time.sleep(sleep)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["funding_at"] = pd.to_datetime(pd.to_numeric(df["fundingTime"], errors="coerce"), unit="ms", utc=True)
    df["funding_rate"] = pd.to_numeric(df.get("fundingRate"), errors="coerce")
    df["funding_mark_price"] = pd.to_numeric(df.get("markPrice"), errors="coerce")
    df = df.dropna(subset=["funding_at", "funding_rate"]).sort_values("funding_at")
    return df[["funding_at", "funding_rate", "funding_mark_price"]]


def classify_funding_regime(annualized_pct: float) -> str:
    if pd.isna(annualized_pct):
        return "UNKNOWN"
    if annualized_pct >= 15:
        return "OVERHEATED_LONGS"
    if annualized_pct >= 2:
        return "POSITIVE_FUNDING"
    if annualized_pct <= -15:
        return "OVERHEATED_SHORTS"
    if annualized_pct <= -2:
        return "NEGATIVE_FUNDING"
    return "NEUTRAL"


def classify_arbitrage(spread: float) -> str:
    if pd.isna(spread):
        return "UNKNOWN"
    if spread >= 5:
        return "FAVOR_COIN_M"
    if spread <= -5:
        return "FAVOR_USDT_M"
    return "BALANCED"


def enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    for col in FUNDING_SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[list(FUNDING_SCHEMA_COLUMNS.keys())].copy()

    for col, dtype in FUNDING_SCHEMA_COLUMNS.items():
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


def aggregate_funding_day_symbol(pair_symbol: str, output_date: str, sleep: float) -> pd.DataFrame:
    pair_symbol = pair_symbol.upper()
    symbol = base_symbol(pair_symbol)
    day_start_ms = date_to_ms(output_date)
    day_end_ms = date_to_ms(add_days(output_date, 1))

    # Warmup gives us the previous settlement to forward-fill early hours.
    funding_start_ms = date_to_ms(add_days(output_date, -2))
    funding_end_ms = date_to_ms(add_days(output_date, 1))

    logging.info("📥 Funding context %s %s", pair_symbol, output_date)
    funding = fetch_funding_events(pair_symbol, funding_start_ms, funding_end_ms, sleep=sleep)
    if funding.empty:
        logging.warning("⚠️ No funding events for %s around %s", pair_symbol, output_date)
        return pd.DataFrame()

    spot = fetch_klines(SPOT_BASE_URL, "/api/v3/klines", pair_symbol, day_start_ms, day_end_ms, sleep=sleep)
    mark = fetch_klines(FAPI_BASE_URL, "/fapi/v1/markPriceKlines", pair_symbol, day_start_ms, day_end_ms, sleep=sleep)

    hours = pd.DataFrame({
        "hour_ts": pd.date_range(
            start=pd.Timestamp(output_date, tz="UTC"),
            end=pd.Timestamp(add_days(output_date, 1), tz="UTC") - pd.Timedelta(hours=1),
            freq="h",
        )
    })
    df = hours.merge(spot.rename(columns={"close": "spot_price"}), on="hour_ts", how="left")
    df = df.merge(mark.rename(columns={"close": "mark_price"}), on="hour_ts", how="left")

    df = pd.merge_asof(
        df.sort_values("hour_ts"),
        funding.rename(columns={"funding_at": "last_funding_at"}).sort_values("last_funding_at"),
        left_on="hour_ts",
        right_on="last_funding_at",
        direction="backward",
    )

    # Fallbacks if a mark kline is missing.
    df["mark_price"] = df["mark_price"].fillna(df["funding_mark_price"]).fillna(df["spot_price"])
    df["spot_price"] = df["spot_price"].fillna(df["mark_price"])
    df = df.dropna(subset=["spot_price", "mark_price", "funding_rate"])
    if df.empty:
        return pd.DataFrame()

    df["basis_spread"] = df["mark_price"] - df["spot_price"]
    df["basis_pct"] = np.where(df["spot_price"] > 0, df["basis_spread"] / df["spot_price"] * 100.0, np.nan)

    # Binance USDT-M funding settlement is generally 8h => 3 payments/day.
    df["annualized_funding_pct"] = df["funding_rate"] * 3 * 365 * 100.0
    df["annualized_basis_pct"] = df["basis_pct"] * 365.0
    df["arbitrage_spread"] = df["annualized_funding_pct"] - df["annualized_basis_pct"]
    df["leverage_stress"] = np.minimum(
        100.0,
        np.abs(df["annualized_funding_pct"]) * 2.0 + np.abs(df["basis_pct"]) * 10.0,
    )
    df["funding_regime"] = df["annualized_funding_pct"].apply(classify_funding_regime)
    df["arbitrage_opportunity"] = df["arbitrage_spread"].apply(classify_arbitrage)

    loaded_at = utc_now()
    out = pd.DataFrame({
        "hour_ts": df["hour_ts"],
        "symbol": symbol,
        "exchanges_reporting": 1,
        "avg_mark_price": df["mark_price"],
        "avg_spot_price": df["spot_price"],
        "avg_basis_spread": df["basis_spread"],
        "avg_basis_pct": df["basis_pct"],
        "max_abs_basis_pct": np.abs(df["basis_pct"]),
        "avg_funding_rate_coin": df["funding_rate"],
        "avg_funding_rate_usdt": df["funding_rate"],
        "avg_annualized_funding_coin": df["annualized_funding_pct"],
        "avg_annualized_funding_usdt": df["annualized_funding_pct"],
        "funding_dispersion_coin": 0.0,
        "avg_annualized_basis_coin": df["annualized_basis_pct"],
        "avg_annualized_basis_usdt": df["annualized_basis_pct"],
        "avg_arbitrage_spread": df["arbitrage_spread"],
        "max_abs_arbitrage_spread": np.abs(df["arbitrage_spread"]),
        "max_leverage_stress": df["leverage_stress"],
        "avg_leverage_stress": df["leverage_stress"],
        "dominant_funding_regime": df["funding_regime"],
        "dominant_arbitrage_opportunity": df["arbitrage_opportunity"],
        "strongest_arbitrage_exchange": "binance",
        "highest_stress_exchange": "binance",
        "latest_observed_at": df["hour_ts"],
        "loaded_at": loaded_at,
        "available_at": df["hour_ts"] + pd.Timedelta(minutes=10),
    })

    snapshots = []
    for _, row in df.iterrows():
        snapshots.append(json.dumps([{
            "exchange": "binance",
            "mark_price": float(row["mark_price"]),
            "spot_price": float(row["spot_price"]),
            "basis_pct": None if pd.isna(row["basis_pct"]) else float(row["basis_pct"]),
            "annualized_funding_coin": float(row["annualized_funding_pct"]),
            "annualized_funding_usdt": float(row["annualized_funding_pct"]),
            "arbitrage_spread": None if pd.isna(row["arbitrage_spread"]) else float(row["arbitrage_spread"]),
            "funding_regime": row["funding_regime"],
            "arbitrage_opportunity": row["arbitrage_opportunity"],
            "leverage_stress": None if pd.isna(row["leverage_stress"]) else float(row["leverage_stress"]),
            "last_funding_at": str(row["last_funding_at"]),
        }], ensure_ascii=False))
    out["exchange_snapshot_json"] = snapshots

    return enforce_schema(out)


def save_dataframe_to_parquet(df: pd.DataFrame, base_dir: str, file_prefix: str, compression: str = "snappy") -> List[str]:
    if df is None or df.empty:
        logging.warning("⚠️ DataFrame empty, skip save")
        return []
    os.makedirs(base_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(base_dir, f"{file_prefix}_{ts}.parquet")
    df.to_parquet(path, index=False, engine="pyarrow", compression=compression)
    logging.info("✅ Saved Parquet: %s rows=%s", path, f"{len(df):,}")
    return [path]


def day_marker_path(output_dir: str, output_date: str, symbols: Sequence[str]) -> str:
    key = "__".join(normalize_symbols(symbols))
    return os.path.join(output_dir, "_state", "funding_daily", key, f"{output_date}.success")


def already_done(output_dir: str, output_date: str, symbols: Sequence[str]) -> bool:
    return os.path.exists(day_marker_path(output_dir, output_date, symbols))


def mark_success(output_dir: str, output_date: str, symbols: Sequence[str], files: List[str]) -> None:
    marker = day_marker_path(output_dir, output_date, symbols)
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write("\n".join(files))


def parse_args() -> argparse.Namespace:
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Backfill Binance funding directly to int_funding_hourly schema")
    parser.add_argument("--start", default=yesterday, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=yesterday, help="End date YYYY-MM-DD")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"], help="Binance symbols")
    parser.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "output_data/binance_funding_hourly_backfill"))
    parser.add_argument("--compression", default="snappy", choices=["snappy", "gzip", "brotli"])
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.symbols = normalize_symbols(args.symbols)
    os.makedirs(args.output_dir, exist_ok=True)

    logging.info("⚙️ Funding backfill: %s -> %s", args.start, args.end)
    logging.info("⚙️ Symbols: %s", args.symbols)
    logging.info("⚙️ Output dir: %s", args.output_dir)

    saved_count = 0
    row_count = 0
    skipped_count = 0

    for output_date in date_range(args.start, args.end):
        if not args.force and already_done(args.output_dir, output_date, args.symbols):
            logging.info("⏭️ Skip existing funding day: %s", output_date)
            skipped_count += 1
            continue

        frames = []
        for pair_symbol in args.symbols:
            df = aggregate_funding_day_symbol(pair_symbol, output_date, sleep=args.sleep)
            if not df.empty:
                frames.append(df)
            time.sleep(args.sleep)

        if not frames:
            logging.warning("⚠️ No output for funding day %s", output_date)
            continue

        df_day = pd.concat(frames, ignore_index=True).sort_values(["symbol", "hour_ts"])
        df_day = enforce_schema(df_day)
        prefix = f"binance_funding_hourly_{output_date}_{'_'.join(args.symbols)}"
        files = save_dataframe_to_parquet(df_day, args.output_dir, prefix, compression=args.compression)
        if files:
            mark_success(args.output_dir, output_date, args.symbols, files)
            saved_count += len(files)
            row_count += len(df_day)

    logging.info("🎉 Funding backfill complete | files=%s | rows=%s | skipped=%s", saved_count, f"{row_count:,}", skipped_count)


if __name__ == "__main__":
    main()
