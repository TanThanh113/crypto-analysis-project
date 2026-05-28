# -*- coding: utf-8 -*-
"""
Backfill Tiingo daily prices locally and write Parquet files that match the dbt INT models directly:

  - int_macro_daily
  - int_etf_daily

This follows the same backfill idea as the Binance hourly backfill:
  Tiingo API -> local Pandas calculation -> exact INT schema -> local Parquet -> Iceberg loader appends to dbt_quants_dev.*

It intentionally skips the raw/staging Tiingo tables for historical backfill.
Daily pipeline can still use raw -> stg -> int later.

Only required env var for this script:
  TIINGO_API_KEY
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from dotenv import load_dotenv
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

script_dir = Path(__file__).resolve().parent
env_path = script_dir.parent / '.env'
load_dotenv(dotenv_path=env_path)

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
# DEFAULTS
# =========================================================
TIINGO_API_KEY = os.environ.get("TIINGO_API_KEY")
OUTPUT_ROOT = "output_data/tiingo_int_backfill"

# Keep symbolic names aligned with int_macro_daily.sql pivot logic.
MACRO_ASSETS: Dict[str, str] = {
    "SP500": "SPY",
    "NASDAQ": "QQQ",
    "GOLD": "GLD",
    # VXX is commonly used as tradable VIX futures ETN proxy.
    # If you prefer VIXY, change this one line only.
    "VIX": "VXX",
    "OIL": "USO",
}

# Keep ETF list broad for aggregate volume/flow proxy; int_etf_daily exposes selected ETF columns.
ETF_ASSETS: Dict[str, str] = {
    "IBIT": "IBIT",
    "FBTC": "FBTC",
    "GBTC": "GBTC",
    "BITB": "BITB",
    "ARKB": "ARKB",
    "HODL": "HODL",
    "BTCO": "BTCO",
    "EZBC": "EZBC",
    "BTCW": "BTCW",
    "BRRR": "BRRR",
    "ETHA": "ETHA",
    "FETH": "FETH",
    "ETHE": "ETHE",
    "ETHW": "ETHW",
}

ETH_ETF_SYMBOLS = {"ETHA", "FETH", "ETHE", "ETHW"}

# Exact output order for int_macro_daily.sql
MACRO_INT_COLUMNS = [
    "price_date",
    "sp500_close",
    "nasdaq_close",
    "gold_close",
    "vix_close",
    "oil_close",
    "sp500_return_1d",
    "nasdaq_return_1d",
    "gold_return_1d",
    "vix_return_1d",
    "oil_return_1d",
    "sp500_return_5d",
    "nasdaq_return_5d",
    "gold_return_5d",
    "vix_return_5d",
    "oil_return_5d",
    "sp500_return_10d",
    "nasdaq_return_10d",
    "gold_return_10d",
    "vix_return_10d",
    "oil_return_10d",
    "total_macro_proxy_volume",
    "loaded_at",
    "available_at",
    "nasdaq_sp500_ratio",
    "nasdaq_sp500_relative_return_1d",
    "safe_haven_bid_1d",
    "safe_haven_bid_5d",
    "oil_equity_relative_return_1d",
    "macro_risk_regime",
    "macro_risk_score_direction",
    "macro_risk_appetite_score",
    "macro_defensive_pressure_score",
]

# Exact output order for int_etf_daily.sql
ETF_INT_COLUMNS = [
    "price_date",
    "etf_count",
    "btc_etf_count",
    "eth_etf_count",
    "total_etf_volume",
    "btc_etf_volume",
    "eth_etf_volume",
    "btc_etf_volume_share",
    "eth_etf_volume_share",
    "btc_etf_volume_weighted_return_1d",
    "eth_etf_volume_weighted_return_1d",
    "total_etf_volume_weighted_return_1d",
    "btc_etf_volume_weighted_return_5d",
    "eth_etf_volume_weighted_return_5d",
    "total_etf_volume_weighted_return_5d",
    "btc_etf_flow_proxy",
    "eth_etf_flow_proxy",
    "total_etf_flow_proxy",
    "ibit_close",
    "fbtc_close",
    "gbtc_close",
    "etha_close",
    "feth_close",
    "ethe_close",
    "ibit_return_1d",
    "fbtc_return_1d",
    "gbtc_return_1d",
    "etha_return_1d",
    "feth_return_1d",
    "ethe_return_1d",
    "ibit_volume",
    "fbtc_volume",
    "gbtc_volume",
    "etha_volume",
    "feth_volume",
    "ethe_volume",
    "most_active_etf",
    "most_active_etf_group",
    "most_active_etf_return_1d",
    "most_active_etf_volume",
    "etf_snapshot_json",
    "loaded_at",
    "available_at",
    "btc_eth_etf_return_spread_1d",
    "btc_eth_etf_flow_proxy_spread",
    "crypto_etf_momentum_regime",
]

# Arrow schemas keep price_date as DATE, not TIMESTAMP.
MACRO_ARROW_SCHEMA = pa.schema([
    pa.field("price_date", pa.date32()),
    *[pa.field(c, pa.float64()) for c in MACRO_INT_COLUMNS[1:22]],
    pa.field("loaded_at", pa.timestamp("us", tz="UTC")),
    pa.field("available_at", pa.timestamp("us", tz="UTC")),
    *[pa.field(c, pa.float64()) for c in MACRO_INT_COLUMNS[24:29]],
    pa.field("macro_risk_regime", pa.string()),
    pa.field("macro_risk_score_direction", pa.int64()),
    pa.field("macro_risk_appetite_score", pa.float64()),
    pa.field("macro_defensive_pressure_score", pa.float64()),
])

ETF_ARROW_SCHEMA = pa.schema([
    pa.field("price_date", pa.date32()),
    pa.field("etf_count", pa.int64()),
    pa.field("btc_etf_count", pa.int64()),
    pa.field("eth_etf_count", pa.int64()),
    *[pa.field(c, pa.float64()) for c in ETF_INT_COLUMNS[4:36]],
    pa.field("most_active_etf", pa.string()),
    pa.field("most_active_etf_group", pa.string()),
    pa.field("most_active_etf_return_1d", pa.float64()),
    pa.field("most_active_etf_volume", pa.float64()),
    pa.field("etf_snapshot_json", pa.string()),
    pa.field("loaded_at", pa.timestamp("us", tz="UTC")),
    pa.field("available_at", pa.timestamp("us", tz="UTC")),
    pa.field("btc_eth_etf_return_spread_1d", pa.float64()),
    pa.field("btc_eth_etf_flow_proxy_spread", pa.float64()),
    pa.field("crypto_etf_momentum_regime", pa.string()),
])


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def add_days(date_str: str, days: int) -> str:
    return (parse_date(date_str) + timedelta(days=days)).strftime("%Y-%m-%d")


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def output_dir_for(table_name: str) -> str:
    return os.path.join(OUTPUT_ROOT, table_name)


def save_arrow_parquet(df: pd.DataFrame, table_name: str, schema: pa.Schema, file_prefix: str, compression: str) -> str:
    if df.empty:
        raise ValueError(f"No rows to save for {table_name}")

    base_dir = output_dir_for(table_name)
    os.makedirs(base_dir, exist_ok=True)

    # Ensure column order and missing columns.
    columns = schema.names
    for col in columns:
        if col not in df.columns:
            df[col] = None
    out = df[columns].copy()

    # Keep DATE as Python date so Arrow writes date32.
    out["price_date"] = pd.to_datetime(out["price_date"]).dt.date

    for col in ["loaded_at", "available_at"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], utc=True, errors="coerce")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(base_dir, f"{file_prefix}_{timestamp}.parquet")

    table = pa.Table.from_pandas(out, schema=schema, preserve_index=False)
    pq.write_table(table, path, compression=compression)
    logging.info("✅ Saved %s rows to %s", f"{len(out):,}", path)
    return path


def fetch_tiingo_daily(symbol_name: str, ticker: str, asset_class: str, start: str, end: str, sleep_on_429: int = 30) -> pd.DataFrame:
    if not TIINGO_API_KEY:
        raise RuntimeError("Missing TIINGO_API_KEY in environment")

    logging.info("📥 [%s] Fetching %s (%s) %s -> %s", asset_class.upper(), symbol_name, ticker, start, end)
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices"
    params = {
        "startDate": start,
        "endDate": end,
        "token": TIINGO_API_KEY,
        "format": "json",
    }
    headers = {"User-Agent": "crypto-analysis-bot/1.0"}

    response = session.get(url, params=params, headers=headers, timeout=60)
    if response.status_code == 429:
        logging.error("❌ Tiingo rate limit 429 for %s. Sleep %ss then skip this ticker.", ticker, sleep_on_429)
        time.sleep(sleep_on_429)
        return pd.DataFrame()
    if response.status_code != 200:
        logging.error("❌ Tiingo error %s for %s: %s", response.status_code, ticker, response.text[:500])
        return pd.DataFrame()

    data = response.json()
    if not data:
        logging.warning("⚠️ No Tiingo data for %s", ticker)
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df.rename(columns={"adjClose": "adj_close"})
    if "adj_close" not in df.columns:
        df["adj_close"] = df.get("close")
    if "volume" not in df.columns:
        df["volume"] = 0.0

    run_ts = utc_now()
    df["price_date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.date
    df["symbol"] = symbol_name.upper()
    df["ticker"] = ticker.upper()
    df["asset_class"] = asset_class.lower()
    df["close_price"] = pd.to_numeric(df.get("close"), errors="coerce")
    df["adj_close_price"] = pd.to_numeric(df.get("adj_close"), errors="coerce")
    df["volume"] = pd.to_numeric(df.get("volume"), errors="coerce").fillna(0.0)
    df["ingestion_time"] = run_ts

    df = df.drop_duplicates(subset=["price_date", "symbol"], keep="last")
    df = df[(df["price_date"].notna()) & (df["close_price"] > 0) & (df["adj_close_price"] > 0)].copy()
    return df[["price_date", "symbol", "ticker", "asset_class", "close_price", "adj_close_price", "volume", "ingestion_time"]]


def fetch_asset_group(assets: Dict[str, str], asset_class: str, fetch_start: str, end: str, sleep: float) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for symbol_name, ticker in assets.items():
        df = fetch_tiingo_daily(symbol_name, ticker, asset_class, fetch_start, end)
        if not df.empty:
            frames.append(df)
        time.sleep(sleep)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["price_date", "symbol"], keep="last")
    return out


def add_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return prices

    df = prices.copy()
    df["price_date"] = pd.to_datetime(df["price_date"])
    df = df.sort_values(["symbol", "price_date"]).reset_index(drop=True)

    parts: List[pd.DataFrame] = []
    for _, g in df.groupby("symbol", sort=False):
        g = g.sort_values("price_date").copy()
        prev_1 = g["adj_close_price"].shift(1)
        prev_5 = g["adj_close_price"].shift(5)
        prev_10 = g["adj_close_price"].shift(10)
        g["return_1d"] = (g["adj_close_price"] - prev_1) / prev_1.replace({0: np.nan})
        g["return_5d"] = (g["adj_close_price"] - prev_5) / prev_5.replace({0: np.nan})
        g["return_10d"] = (g["adj_close_price"] - prev_10) / prev_10.replace({0: np.nan})
        parts.append(g)

    return pd.concat(parts, ignore_index=True)


def filter_output_dates(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    if df.empty:
        return df
    start_date = pd.to_datetime(start).date()
    end_date = pd.to_datetime(end).date()
    d = pd.to_datetime(df["price_date"]).dt.date
    return df[(d >= start_date) & (d <= end_date)].copy()


def build_int_macro_daily(raw_prices: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    if raw_prices.empty:
        return pd.DataFrame(columns=MACRO_INT_COLUMNS)

    prices = add_daily_returns(raw_prices)
    prices = prices[prices["asset_class"] == "macro"].copy()

    rows = []
    for price_date, g in prices.groupby("price_date", sort=True):
        def max_for(symbol: str, col: str) -> float:
            vals = g.loc[g["symbol"] == symbol, col]
            if vals.empty:
                return np.nan
            return vals.max(skipna=True)

        loaded_at = pd.to_datetime(g["ingestion_time"], utc=True).max()
        price_date_obj = pd.to_datetime(price_date).date()
        available_at = pd.Timestamp(datetime.combine(price_date_obj, datetime.min.time()), tz="UTC") + pd.Timedelta(hours=22)

        sp500_return_1d = max_for("SP500", "return_1d")
        nasdaq_return_1d = max_for("NASDAQ", "return_1d")
        gold_return_1d = max_for("GOLD", "return_1d")
        vix_return_1d = max_for("VIX", "return_1d")
        oil_return_1d = max_for("OIL", "return_1d")
        sp500_return_5d = max_for("SP500", "return_5d")
        gold_return_5d = max_for("GOLD", "return_5d")

        sp500_close = max_for("SP500", "close_price")
        nasdaq_close = max_for("NASDAQ", "close_price")
        nasdaq_sp500_ratio = nasdaq_close / sp500_close if pd.notna(nasdaq_close) and pd.notna(sp500_close) and sp500_close != 0 else np.nan

        nasdaq_sp500_relative_return_1d = np.nan_to_num(nasdaq_return_1d, nan=0.0) - np.nan_to_num(sp500_return_1d, nan=0.0)
        safe_haven_bid_1d = np.nan_to_num(gold_return_1d, nan=0.0) - np.nan_to_num(sp500_return_1d, nan=0.0)
        safe_haven_bid_5d = np.nan_to_num(gold_return_5d, nan=0.0) - np.nan_to_num(sp500_return_5d, nan=0.0)
        oil_equity_relative_return_1d = np.nan_to_num(oil_return_1d, nan=0.0) - np.nan_to_num(sp500_return_1d, nan=0.0)

        sp500_1 = np.nan_to_num(sp500_return_1d, nan=0.0)
        nasdaq_1 = np.nan_to_num(nasdaq_return_1d, nan=0.0)
        gold_1 = np.nan_to_num(gold_return_1d, nan=0.0)
        vix_1 = np.nan_to_num(vix_return_1d, nan=0.0)

        if vix_1 > 0.05 and sp500_1 < 0:
            macro_risk_regime = "RISK_OFF"
        elif vix_1 < -0.03 and sp500_1 > 0:
            macro_risk_regime = "RISK_ON"
        elif gold_1 > sp500_1 and vix_1 > 0:
            macro_risk_regime = "DEFENSIVE"
        else:
            macro_risk_regime = "NEUTRAL"

        if sp500_1 > 0 and nasdaq_1 > 0 and vix_1 < 0:
            macro_risk_score_direction = 1
        elif sp500_1 < 0 and nasdaq_1 < 0 and vix_1 > 0:
            macro_risk_score_direction = -1
        else:
            macro_risk_score_direction = 0

        rows.append({
            "price_date": price_date_obj,
            "sp500_close": sp500_close,
            "nasdaq_close": nasdaq_close,
            "gold_close": max_for("GOLD", "close_price"),
            "vix_close": max_for("VIX", "close_price"),
            "oil_close": max_for("OIL", "close_price"),
            "sp500_return_1d": sp500_return_1d,
            "nasdaq_return_1d": nasdaq_return_1d,
            "gold_return_1d": gold_return_1d,
            "vix_return_1d": vix_return_1d,
            "oil_return_1d": oil_return_1d,
            "sp500_return_5d": sp500_return_5d,
            "nasdaq_return_5d": max_for("NASDAQ", "return_5d"),
            "gold_return_5d": gold_return_5d,
            "vix_return_5d": max_for("VIX", "return_5d"),
            "oil_return_5d": max_for("OIL", "return_5d"),
            "sp500_return_10d": max_for("SP500", "return_10d"),
            "nasdaq_return_10d": max_for("NASDAQ", "return_10d"),
            "gold_return_10d": max_for("GOLD", "return_10d"),
            "vix_return_10d": max_for("VIX", "return_10d"),
            "oil_return_10d": max_for("OIL", "return_10d"),
            "total_macro_proxy_volume": g["volume"].sum(skipna=True),
            "loaded_at": loaded_at,
            "available_at": available_at,
            "nasdaq_sp500_ratio": nasdaq_sp500_ratio,
            "nasdaq_sp500_relative_return_1d": nasdaq_sp500_relative_return_1d,
            "safe_haven_bid_1d": safe_haven_bid_1d,
            "safe_haven_bid_5d": safe_haven_bid_5d,
            "oil_equity_relative_return_1d": oil_equity_relative_return_1d,
            "macro_risk_regime": macro_risk_regime,
            "macro_risk_score_direction": macro_risk_score_direction,
            "macro_risk_appetite_score": (sp500_1 + nasdaq_1 - vix_1) / 3.0,
            "macro_defensive_pressure_score": (gold_1 + vix_1 - sp500_1) / 3.0,
        })

    out = pd.DataFrame(rows)
    out = filter_output_dates(out, start, end)
    return out[MACRO_INT_COLUMNS].sort_values("price_date").reset_index(drop=True)


def etf_group_for(symbol: str) -> str:
    return "ETH_ETF" if symbol.upper() in ETH_ETF_SYMBOLS else "BTC_ETF"


def _safe_div(num: float, den: float) -> float:
    if den is None or pd.isna(den) or den == 0:
        return np.nan
    return num / den


def _clean_json_value(v):
    if pd.isna(v):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return str(v)
    return v


def build_int_etf_daily(raw_prices: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    if raw_prices.empty:
        return pd.DataFrame(columns=ETF_INT_COLUMNS)

    prices = add_daily_returns(raw_prices)
    prices = prices[prices["asset_class"] == "etf"].copy()
    if prices.empty:
        return pd.DataFrame(columns=ETF_INT_COLUMNS)

    prices["etf_group"] = prices["symbol"].apply(etf_group_for)

    rows = []
    for price_date, g in prices.groupby("price_date", sort=True):
        price_date_obj = pd.to_datetime(price_date).date()
        loaded_at = pd.to_datetime(g["ingestion_time"], utc=True).max()
        available_at = pd.Timestamp(datetime.combine(price_date_obj, datetime.min.time()), tz="UTC") + pd.Timedelta(hours=22, minutes=30)

        btc = g[g["etf_group"] == "BTC_ETF"]
        eth = g[g["etf_group"] == "ETH_ETF"]
        total_volume = float(g["volume"].sum(skipna=True))
        btc_volume = float(btc["volume"].sum(skipna=True))
        eth_volume = float(eth["volume"].sum(skipna=True))

        # BigQuery SUM(IF(condition, return * volume, 0)) behavior is approximated by filling NaN products with 0.
        g_product_1d = (g["return_1d"] * g["volume"]).fillna(0.0)
        g_product_5d = (g["return_5d"] * g["volume"]).fillna(0.0)
        btc_product_1d = (btc["return_1d"] * btc["volume"]).fillna(0.0)
        eth_product_1d = (eth["return_1d"] * eth["volume"]).fillna(0.0)
        btc_product_5d = (btc["return_5d"] * btc["volume"]).fillna(0.0)
        eth_product_5d = (eth["return_5d"] * eth["volume"]).fillna(0.0)

        def max_symbol(symbol: str, col: str) -> float:
            vals = g.loc[g["symbol"] == symbol, col]
            if vals.empty:
                return np.nan
            return vals.max(skipna=True)

        sorted_snapshot = g.sort_values("volume", ascending=False)
        snapshot = []
        for _, r in sorted_snapshot.iterrows():
            snapshot.append({
                "symbol": _clean_json_value(r.get("symbol")),
                "ticker": _clean_json_value(r.get("ticker")),
                "etf_group": _clean_json_value(r.get("etf_group")),
                "close_price": _clean_json_value(r.get("close_price")),
                "adj_close_price": _clean_json_value(r.get("adj_close_price")),
                "volume": _clean_json_value(r.get("volume")),
                "return_1d": _clean_json_value(r.get("return_1d")),
                "return_5d": _clean_json_value(r.get("return_5d")),
            })

        most_active = sorted_snapshot.iloc[0] if not sorted_snapshot.empty else None
        btc_etf_vw_ret_1d = _safe_div(float(btc_product_1d.sum()), btc_volume)
        eth_etf_vw_ret_1d = _safe_div(float(eth_product_1d.sum()), eth_volume)

        if np.nan_to_num(btc_etf_vw_ret_1d, nan=0.0) > 0.01 and np.nan_to_num(eth_etf_vw_ret_1d, nan=0.0) > 0.01:
            regime = "BROAD_CRYPTO_ETF_BID"
        elif np.nan_to_num(btc_etf_vw_ret_1d, nan=0.0) < -0.01 and np.nan_to_num(eth_etf_vw_ret_1d, nan=0.0) < -0.01:
            regime = "BROAD_CRYPTO_ETF_SELL_PRESSURE"
        elif np.nan_to_num(btc_etf_vw_ret_1d, nan=0.0) > np.nan_to_num(eth_etf_vw_ret_1d, nan=0.0):
            regime = "BTC_ETF_LEADERSHIP"
        elif np.nan_to_num(eth_etf_vw_ret_1d, nan=0.0) > np.nan_to_num(btc_etf_vw_ret_1d, nan=0.0):
            regime = "ETH_ETF_LEADERSHIP"
        else:
            regime = "NEUTRAL"

        btc_flow_proxy = float(btc_product_1d.sum())
        eth_flow_proxy = float(eth_product_1d.sum())

        rows.append({
            "price_date": price_date_obj,
            "etf_count": int(len(g)),
            "btc_etf_count": int(len(btc)),
            "eth_etf_count": int(len(eth)),
            "total_etf_volume": total_volume,
            "btc_etf_volume": btc_volume,
            "eth_etf_volume": eth_volume,
            "btc_etf_volume_share": _safe_div(btc_volume, total_volume),
            "eth_etf_volume_share": _safe_div(eth_volume, total_volume),
            "btc_etf_volume_weighted_return_1d": btc_etf_vw_ret_1d,
            "eth_etf_volume_weighted_return_1d": eth_etf_vw_ret_1d,
            "total_etf_volume_weighted_return_1d": _safe_div(float(g_product_1d.sum()), total_volume),
            "btc_etf_volume_weighted_return_5d": _safe_div(float(btc_product_5d.sum()), btc_volume),
            "eth_etf_volume_weighted_return_5d": _safe_div(float(eth_product_5d.sum()), eth_volume),
            "total_etf_volume_weighted_return_5d": _safe_div(float(g_product_5d.sum()), total_volume),
            "btc_etf_flow_proxy": btc_flow_proxy,
            "eth_etf_flow_proxy": eth_flow_proxy,
            "total_etf_flow_proxy": float(g_product_1d.sum()),
            "ibit_close": max_symbol("IBIT", "close_price"),
            "fbtc_close": max_symbol("FBTC", "close_price"),
            "gbtc_close": max_symbol("GBTC", "close_price"),
            "etha_close": max_symbol("ETHA", "close_price"),
            "feth_close": max_symbol("FETH", "close_price"),
            "ethe_close": max_symbol("ETHE", "close_price"),
            "ibit_return_1d": max_symbol("IBIT", "return_1d"),
            "fbtc_return_1d": max_symbol("FBTC", "return_1d"),
            "gbtc_return_1d": max_symbol("GBTC", "return_1d"),
            "etha_return_1d": max_symbol("ETHA", "return_1d"),
            "feth_return_1d": max_symbol("FETH", "return_1d"),
            "ethe_return_1d": max_symbol("ETHE", "return_1d"),
            "ibit_volume": max_symbol("IBIT", "volume"),
            "fbtc_volume": max_symbol("FBTC", "volume"),
            "gbtc_volume": max_symbol("GBTC", "volume"),
            "etha_volume": max_symbol("ETHA", "volume"),
            "feth_volume": max_symbol("FETH", "volume"),
            "ethe_volume": max_symbol("ETHE", "volume"),
            "most_active_etf": None if most_active is None else str(most_active["symbol"]),
            "most_active_etf_group": None if most_active is None else str(most_active["etf_group"]),
            "most_active_etf_return_1d": np.nan if most_active is None else float(most_active["return_1d"]) if pd.notna(most_active["return_1d"]) else np.nan,
            "most_active_etf_volume": np.nan if most_active is None else float(most_active["volume"]),
            "etf_snapshot_json": json.dumps(snapshot, separators=(",", ":")),
            "loaded_at": loaded_at,
            "available_at": available_at,
            "btc_eth_etf_return_spread_1d": np.nan_to_num(btc_etf_vw_ret_1d, nan=0.0) - np.nan_to_num(eth_etf_vw_ret_1d, nan=0.0),
            "btc_eth_etf_flow_proxy_spread": btc_flow_proxy - eth_flow_proxy,
            "crypto_etf_momentum_regime": regime,
        })

    out = pd.DataFrame(rows)
    out = filter_output_dates(out, start, end)
    return out[ETF_INT_COLUMNS].sort_values("price_date").reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    default_start = add_days(yesterday, -7)
    parser = argparse.ArgumentParser(description="Backfill Tiingo macro/ETF prices directly to int_macro_daily and int_etf_daily Parquet schemas.")
    parser.add_argument("--type", choices=["macro", "etf", "all"], default="all")
    parser.add_argument("--start", type=str, default=default_start, help="Output start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=yesterday, help="Output end date YYYY-MM-DD")
    parser.add_argument("--warmup-days", type=int, default=30, help="Fetch extra calendar days before start for 1d/5d/10d returns")
    parser.add_argument("--sleep", type=float, default=1.5, help="Sleep seconds between Tiingo ticker requests")
    parser.add_argument("--compression", choices=["snappy", "gzip", "brotli"], default="snappy")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output marker and write another Parquet file")
    return parser.parse_args()


def state_marker(table_name: str, start: str, end: str) -> str:
    return os.path.join(output_dir_for(table_name), "_state", f"{table_name}_{start}_{end}.success")


def already_done(table_name: str, start: str, end: str) -> bool:
    return os.path.exists(state_marker(table_name, start, end))


def mark_success(table_name: str, start: str, end: str, path: str) -> None:
    marker = state_marker(table_name, start, end)
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(path + "\n")


def main() -> None:
    args = parse_args()
    if not TIINGO_API_KEY:
        logging.error("❌ Missing TIINGO_API_KEY in .env")
        sys.exit(1)

    fetch_start = add_days(args.start, -max(args.warmup_days, 0))
    logging.info("⚙️ Output range: %s -> %s", args.start, args.end)
    logging.info("⚙️ Fetch range with warmup: %s -> %s", fetch_start, args.end)
    logging.info("⚙️ Type: %s", args.type)

    if args.type in ("macro", "all"):
        table_name = "int_macro_daily"
        if not args.force and already_done(table_name, args.start, args.end):
            logging.info("⏭️ Skip existing %s range %s -> %s", table_name, args.start, args.end)
        else:
            raw_macro = fetch_asset_group(MACRO_ASSETS, "macro", fetch_start, args.end, args.sleep)
            macro_df = build_int_macro_daily(raw_macro, args.start, args.end)
            if macro_df.empty:
                logging.warning("⚠️ No int_macro_daily rows generated")
            else:
                path = save_arrow_parquet(
                    macro_df,
                    table_name=table_name,
                    schema=MACRO_ARROW_SCHEMA,
                    file_prefix=f"tiingo_int_macro_daily_{args.start}_{args.end}",
                    compression=args.compression,
                )
                mark_success(table_name, args.start, args.end, path)

    if args.type in ("etf", "all"):
        table_name = "int_etf_daily"
        if not args.force and already_done(table_name, args.start, args.end):
            logging.info("⏭️ Skip existing %s range %s -> %s", table_name, args.start, args.end)
        else:
            raw_etf = fetch_asset_group(ETF_ASSETS, "etf", fetch_start, args.end, args.sleep)
            etf_df = build_int_etf_daily(raw_etf, args.start, args.end)
            if etf_df.empty:
                logging.warning("⚠️ No int_etf_daily rows generated")
            else:
                path = save_arrow_parquet(
                    etf_df,
                    table_name=table_name,
                    schema=ETF_ARROW_SCHEMA,
                    file_prefix=f"tiingo_int_etf_daily_{args.start}_{args.end}",
                    compression=args.compression,
                )
                mark_success(table_name, args.start, args.end, path)

    logging.info("🎉 Tiingo int backfill complete")


if __name__ == "__main__":
    main()
