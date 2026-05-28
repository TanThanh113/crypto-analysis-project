# -*- coding: utf-8 -*-
"""
Backfill exchange-reserve/liquidity context directly into:
  - int_exchange_reserve_hourly
  - int_exchange_reserve_daily

Source:
  CoinGecko free/public exchange endpoints.

Important honesty note:
  CoinGecko free exchange endpoints provide exchange metadata, trust score, and
  historical exchange volume charts. They do NOT provide true Proof-of-Reserve
  historical asset balances. To keep your existing dbt schema unchanged, this
  script derives `actual_reserve_usd` as a conservative *reserve proxy* from
  normalized exchange volume and trust score. This is useful as a liquidity/risk
  proxy for ML, but it is not audited reserve data.

Flow:
  CoinGecko exchange current metadata + volume_chart history
    -> local per-exchange daily source rows
    -> aggregate to exact int_exchange_reserve_hourly schema
    -> expand daily snapshot across 24 hourly rows/day for ML coverage
    -> derive exact int_exchange_reserve_daily schema from the latest hour/day
    -> save Parquet files for Iceberg loading

No new columns are created.
"""

import argparse
import json
import logging
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence

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
    backoff_factor=5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
session.mount("https://", HTTPAdapter(max_retries=retries))

COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "").strip()
COINGECKO_API_BASE = os.environ.get("COINGECKO_API_BASE", "https://api.coingecko.com/api/v3").rstrip("/")

DEFAULT_EXCHANGES = [
    "binance",
    "okx",
    "bybit_spot",
    "gdax",  # Coinbase Exchange
    "kraken",
    "kucoin",
    "bitfinex",
    "bitget",
    "gate",
    "crypto_com",
    "gemini",
]

HOURLY_SCHEMA_COLUMNS = {
    "hour_ts": "datetime64[ns, UTC]",
    "exchange_count": "int64",
    "tier_1_exchange_count": "int64",
    "tier_2_exchange_count": "int64",
    "tier_3_exchange_count": "int64",
    "tier_4_exchange_count": "int64",
    "total_exchange_reserve_usd": "float64",
    "total_exchange_volume_24h_usd": "float64",
    "total_exchange_volume_24h_usd_normalized": "float64",
    "total_wash_trading_volume_usd": "float64",
    "wash_trading_volume_ratio": "float64",
    "system_reserve_utilization": "float64",
    "normalized_system_reserve_utilization": "float64",
    "avg_exchange_trust_score": "float64",
    "reserve_weighted_trust_score": "float64",
    "avg_reserve_utilization": "float64",
    "max_reserve_utilization": "float64",
    "reserve_weighted_utilization": "float64",
    "avg_concentration_risk_score": "float64",
    "max_concentration_risk_score": "float64",
    "reserve_hhi": "float64",
    "total_whale_withdrawal_risk": "float64",
    "max_whale_withdrawal_risk": "float64",
    "high_bank_run_risk_exchange_count": "int64",
    "moderate_bank_run_risk_exchange_count": "int64",
    "safe_bank_run_risk_exchange_count": "int64",
    "high_bank_run_risk_exchange_ratio": "float64",
    "safe_bank_run_risk_exchange_ratio": "float64",
    "top_reserve_exchange": "string",
    "top_reserve_exchange_reserve_usd": "float64",
    "top_volume_exchange": "string",
    "highest_utilization_exchange": "string",
    "highest_utilization_risk_label": "string",
    "highest_whale_withdrawal_risk_exchange": "string",
    "highest_wash_trading_exchange": "string",
    "exchange_reserve_snapshot_json": "string",
    "latest_observed_at": "datetime64[ns, UTC]",
    "loaded_at": "datetime64[ns, UTC]",
    "available_at": "datetime64[ns, UTC]",
}

DAILY_SCHEMA_COLUMNS = {
    "snapshot_date": "object",
    "latest_hour_ts": "datetime64[ns, UTC]",
    "exchange_count": "int64",
    "tier_1_exchange_count": "int64",
    "tier_2_exchange_count": "int64",
    "tier_3_exchange_count": "int64",
    "tier_4_exchange_count": "int64",
    "total_exchange_reserve_usd": "float64",
    "total_exchange_volume_24h_usd": "float64",
    "total_exchange_volume_24h_usd_normalized": "float64",
    "total_wash_trading_volume_usd": "float64",
    "wash_trading_volume_ratio": "float64",
    "system_reserve_utilization": "float64",
    "normalized_system_reserve_utilization": "float64",
    "avg_exchange_trust_score": "float64",
    "reserve_weighted_trust_score": "float64",
    "avg_reserve_utilization": "float64",
    "max_reserve_utilization": "float64",
    "reserve_weighted_utilization": "float64",
    "avg_concentration_risk_score": "float64",
    "max_concentration_risk_score": "float64",
    "reserve_hhi": "float64",
    "total_whale_withdrawal_risk": "float64",
    "max_whale_withdrawal_risk": "float64",
    "high_bank_run_risk_exchange_count": "int64",
    "moderate_bank_run_risk_exchange_count": "int64",
    "safe_bank_run_risk_exchange_count": "int64",
    "high_bank_run_risk_exchange_ratio": "float64",
    "safe_bank_run_risk_exchange_ratio": "float64",
    "top_reserve_exchange": "string",
    "top_reserve_exchange_reserve_usd": "float64",
    "top_volume_exchange": "string",
    "highest_utilization_exchange": "string",
    "highest_utilization_risk_label": "string",
    "highest_whale_withdrawal_risk_exchange": "string",
    "highest_wash_trading_exchange": "string",
    "exchange_reserve_snapshot_json": "string",
    "exchange_reserve_return_1d": "float64",
    "exchange_reserve_change_1d_usd": "float64",
    "exchange_volume_return_1d": "float64",
    "exchange_volume_change_1d_usd": "float64",
    "system_reserve_utilization_change_1d": "float64",
    "normalized_system_reserve_utilization_change_1d": "float64",
    "reserve_hhi_change_1d": "float64",
    "high_bank_run_risk_exchange_count_change_1d": "float64",
    "whale_withdrawal_risk_change_1d": "float64",
    "wash_trading_volume_ratio_change_1d": "float64",
    "loaded_at": "datetime64[ns, UTC]",
    "available_at": "datetime64[ns, UTC]",
}


def date_range(start_str: str, end_str: str) -> Iterable[str]:
    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
    end_dt = datetime.strptime(end_str, "%Y-%m-%d")
    if end_dt < start_dt:
        raise ValueError("Start date cannot be greater than end date")
    for i in range((end_dt - start_dt).days + 1):
        yield (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")


def days_between(start: str, end: str) -> int:
    return (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days + 1


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def headers() -> dict:
    h = {"User-Agent": "crypto-analysis-project/1.0"}
    if COINGECKO_API_KEY:
        # Demo keys use this header on the public api.coingecko.com host.
        h["x-cg-demo-api-key"] = COINGECKO_API_KEY
    return h


def request_json(endpoint: str, params: Optional[dict] = None, timeout: int = 60):
    url = f"{COINGECKO_API_BASE}{endpoint}"
    response = session.get(url, params=params or {}, headers=headers(), timeout=timeout)
    if response.status_code == 429:
        logging.warning("⚠️ CoinGecko rate limit hit; sleeping 30s")
        time.sleep(30)
    response.raise_for_status()
    return response.json()


def fetch_exchange_metadata(exchange_ids: Sequence[str], sleep: float) -> Dict[str, dict]:
    logging.info("📥 Fetching CoinGecko exchange metadata list...")
    metadata: Dict[str, dict] = {}
    page = 1
    while True:
        data = request_json("/exchanges", params={"per_page": 250, "page": page}, timeout=60)
        if not data:
            break
        for item in data:
            ex_id = item.get("id")
            if ex_id in exchange_ids:
                metadata[ex_id] = item
        if len(metadata) >= len(exchange_ids):
            break
        page += 1
        time.sleep(sleep)
        if page > 10:
            break

    missing = [ex for ex in exchange_ids if ex not in metadata]
    if missing:
        logging.warning("⚠️ Some exchange ids were not returned by CoinGecko: %s", missing)
    return metadata


def fetch_btc_price_daily(start: str, end: str, sleep: float) -> pd.DataFrame:
    start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    # include one extra day to avoid timezone edge cases
    end_dt = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).replace(tzinfo=timezone.utc)
    params = {
        "vs_currency": "usd",
        "from": int(start_dt.timestamp()),
        "to": int(end_dt.timestamp()),
    }
    data = request_json("/coins/bitcoin/market_chart/range", params=params, timeout=90)
    prices = data.get("prices", [])
    if not prices:
        return pd.DataFrame()

    df = pd.DataFrame(prices, columns=["ts_ms", "btc_usd"])
    df["date"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.date
    df = df.sort_values("ts_ms").groupby("date", as_index=False).tail(1)
    df["price_date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df[["price_date", "btc_usd"]].drop_duplicates("price_date")


def fetch_exchange_volume_chart(exchange_id: str, days: int, sleep: float) -> pd.DataFrame:
    logging.info("📥 Fetching volume chart for exchange=%s days=%s", exchange_id, days)
    try:
        data = request_json(f"/exchanges/{exchange_id}/volume_chart", params={"days": days}, timeout=90)
    except Exception as e:
        logging.warning("⚠️ Failed volume chart for %s: %s", exchange_id, e)
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=["ts_ms", "volume_btc"])
    df["price_date"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
    df["volume_btc"] = pd.to_numeric(df["volume_btc"], errors="coerce")
    df = df.dropna(subset=["volume_btc"])
    df = df.groupby("price_date", as_index=False).last()
    df["exchange_id"] = exchange_id
    time.sleep(sleep)
    return df[["price_date", "exchange_id", "volume_btc"]]


def tier_from_trust_score(trust_score: float) -> str:
    if trust_score >= 8:
        return "tier_1"
    if trust_score >= 6:
        return "tier_2"
    if trust_score >= 4:
        return "tier_3"
    return "tier_4"


def bank_run_risk_from_utilization(utilization: float) -> str:
    if pd.isna(utilization):
        return "MODERATE"
    if utilization >= 0.70:
        return "HIGH_RISK"
    if utilization >= 0.30:
        return "MODERATE"
    return "SAFE"


def build_source_exchange_daily(
    start: str,
    end: str,
    exchange_ids: Sequence[str],
    reserve_volume_multiple: float,
    sleep: float,
) -> pd.DataFrame:
    metadata = fetch_exchange_metadata(exchange_ids, sleep=sleep)
    btc_prices = fetch_btc_price_daily(start, end, sleep=sleep)
    if btc_prices.empty:
        logging.warning("⚠️ BTC price history unavailable. Using current volume conversion may fail.")

    chart_days = max(days_between(start, end) + 3, 1)
    charts = []
    for ex in exchange_ids:
        df = fetch_exchange_volume_chart(ex, chart_days, sleep=sleep)
        if not df.empty:
            charts.append(df)
    if not charts:
        raise RuntimeError("No exchange volume chart data fetched from CoinGecko")

    volume_df = pd.concat(charts, ignore_index=True)
    volume_df = volume_df[(volume_df["price_date"] >= start) & (volume_df["price_date"] <= end)].copy()
    volume_df = volume_df.merge(btc_prices, on="price_date", how="left")
    volume_df["btc_usd"] = volume_df["btc_usd"].ffill().bfill()
    volume_df["trade_volume_24h_usd"] = volume_df["volume_btc"] * volume_df["btc_usd"]

    rows = []
    loaded_at = utc_now()

    for _, row in volume_df.iterrows():
        ex_id = row["exchange_id"]
        meta = metadata.get(ex_id, {})
        trust_score = float(meta.get("trust_score") or 5)
        exchange_name = meta.get("name") or ex_id
        coingecko_id = ex_id
        tier = tier_from_trust_score(trust_score)

        # Trust-adjusted normalized volume and reserve proxy.
        trust_factor = max(0.35, min(1.0, trust_score / 10.0 + 0.15))
        volume_usd = float(row["trade_volume_24h_usd"] or 0)
        normalized_volume_usd = volume_usd * trust_factor
        wash_volume_usd = max(volume_usd - normalized_volume_usd, 0.0)

        actual_reserve_usd = max(normalized_volume_usd * reserve_volume_multiple, 0.0)
        reserve_utilization = normalized_volume_usd / actual_reserve_usd if actual_reserve_usd > 0 else np.nan
        bank_run_risk = bank_run_risk_from_utilization(reserve_utilization)

        rows.append({
            "price_date": row["price_date"],
            "exchange": exchange_name,
            "coingecko_id": coingecko_id,
            "trust_score": trust_score,
            "trade_volume_24h_usd": volume_usd,
            "trade_volume_24h_usd_normalized": normalized_volume_usd,
            "actual_reserve_usd": actual_reserve_usd,
            "data_source": "coingecko_volume_reserve_proxy",
            "reserve_utilization": reserve_utilization,
            "bank_run_risk": bank_run_risk,
            "wash_trading_volume_usd": wash_volume_usd,
            "liquidity_score": min(100.0, trust_score * 10.0),
            "exchange_tier": tier,
            "loaded_at": loaded_at,
        })

    src = pd.DataFrame(rows)
    if src.empty:
        return src

    # Reserve dominance and derived concentration/whale risk per day.
    total_reserve = src.groupby("price_date")["actual_reserve_usd"].transform("sum")
    src["reserve_dominance_pct"] = np.where(total_reserve > 0, src["actual_reserve_usd"] / total_reserve * 100, np.nan)
    src["concentration_risk_score"] = src["reserve_dominance_pct"].clip(lower=0, upper=100)
    src["whale_withdrawal_risk"] = (
        src["reserve_utilization"].fillna(0) * 50.0
        + (src["reserve_dominance_pct"].fillna(0) / 100.0) * 50.0
    ).clip(lower=0, upper=100)

    return src


def aggregate_hourly_from_source_daily(src: pd.DataFrame) -> pd.DataFrame:
    if src.empty:
        return src

    daily_rows = []
    for price_date, g in src.groupby("price_date"):
        g = g.copy()
        exchange_count = len(g)
        total_reserve = g["actual_reserve_usd"].sum()
        total_vol = g["trade_volume_24h_usd"].sum()
        total_vol_norm = g["trade_volume_24h_usd_normalized"].sum()
        total_wash = g["wash_trading_volume_usd"].sum()

        top_reserve = g.sort_values(["actual_reserve_usd", "trade_volume_24h_usd"], ascending=False).iloc[0]
        top_volume = g.sort_values(["trade_volume_24h_usd", "actual_reserve_usd"], ascending=False).iloc[0]
        highest_util = g.sort_values(["reserve_utilization", "actual_reserve_usd"], ascending=False).iloc[0]
        highest_whale = g.sort_values(["whale_withdrawal_risk", "actual_reserve_usd"], ascending=False).iloc[0]
        highest_wash = g.sort_values(["wash_trading_volume_usd", "trade_volume_24h_usd"], ascending=False).iloc[0]

        snapshot = []
        for _, r in g.sort_values(["actual_reserve_usd", "trade_volume_24h_usd"], ascending=False).iterrows():
            snapshot.append({
                "exchange": r["exchange"],
                "coingecko_id": r["coingecko_id"],
                "trust_score": float(r["trust_score"]),
                "actual_reserve_usd": float(r["actual_reserve_usd"]),
                "trade_volume_24h_usd": float(r["trade_volume_24h_usd"]),
                "trade_volume_24h_usd_normalized": float(r["trade_volume_24h_usd_normalized"]),
                "reserve_utilization": None if pd.isna(r["reserve_utilization"]) else float(r["reserve_utilization"]),
                "reserve_dominance_pct": None if pd.isna(r["reserve_dominance_pct"]) else float(r["reserve_dominance_pct"]),
                "concentration_risk_score": None if pd.isna(r["concentration_risk_score"]) else float(r["concentration_risk_score"]),
                "liquidity_score": float(r["liquidity_score"]),
                "bank_run_risk": r["bank_run_risk"],
                "exchange_tier": r["exchange_tier"],
                "whale_withdrawal_risk": float(r["whale_withdrawal_risk"]),
                "wash_trading_volume_usd": float(r["wash_trading_volume_usd"]),
                "data_source": r["data_source"],
            })

        base = {
            "exchange_count": exchange_count,
            "tier_1_exchange_count": int((g["exchange_tier"] == "tier_1").sum()),
            "tier_2_exchange_count": int((g["exchange_tier"] == "tier_2").sum()),
            "tier_3_exchange_count": int((g["exchange_tier"] == "tier_3").sum()),
            "tier_4_exchange_count": int((g["exchange_tier"] == "tier_4").sum()),
            "total_exchange_reserve_usd": total_reserve,
            "total_exchange_volume_24h_usd": total_vol,
            "total_exchange_volume_24h_usd_normalized": total_vol_norm,
            "total_wash_trading_volume_usd": total_wash,
            "wash_trading_volume_ratio": total_wash / total_vol if total_vol > 0 else np.nan,
            "system_reserve_utilization": total_vol / total_reserve if total_reserve > 0 else np.nan,
            "normalized_system_reserve_utilization": total_vol_norm / total_reserve if total_reserve > 0 else np.nan,
            "avg_exchange_trust_score": g["trust_score"].mean(),
            "reserve_weighted_trust_score": (g["trust_score"] * g["actual_reserve_usd"]).sum() / total_reserve if total_reserve > 0 else np.nan,
            "avg_reserve_utilization": g["reserve_utilization"].mean(),
            "max_reserve_utilization": g["reserve_utilization"].max(),
            "reserve_weighted_utilization": (g["reserve_utilization"] * g["actual_reserve_usd"]).sum() / total_reserve if total_reserve > 0 else np.nan,
            "avg_concentration_risk_score": g["concentration_risk_score"].mean(),
            "max_concentration_risk_score": g["concentration_risk_score"].max(),
            "reserve_hhi": ((g["reserve_dominance_pct"] / 100.0) ** 2).sum(),
            "total_whale_withdrawal_risk": g["whale_withdrawal_risk"].sum(),
            "max_whale_withdrawal_risk": g["whale_withdrawal_risk"].max(),
            "high_bank_run_risk_exchange_count": int((g["bank_run_risk"] == "HIGH_RISK").sum()),
            "moderate_bank_run_risk_exchange_count": int((g["bank_run_risk"] == "MODERATE").sum()),
            "safe_bank_run_risk_exchange_count": int((g["bank_run_risk"] == "SAFE").sum()),
            "top_reserve_exchange": top_reserve["exchange"],
            "top_reserve_exchange_reserve_usd": top_reserve["actual_reserve_usd"],
            "top_volume_exchange": top_volume["exchange"],
            "highest_utilization_exchange": highest_util["exchange"],
            "highest_utilization_risk_label": highest_util["bank_run_risk"],
            "highest_whale_withdrawal_risk_exchange": highest_whale["exchange"],
            "highest_wash_trading_exchange": highest_wash["exchange"],
            "exchange_reserve_snapshot_json": json.dumps(snapshot, ensure_ascii=False),
            "latest_observed_at": pd.Timestamp(price_date, tz="UTC") + pd.Timedelta(hours=23),
            "loaded_at": g["loaded_at"].max(),
            "available_at": pd.Timestamp(price_date, tz="UTC") + pd.Timedelta(hours=23, minutes=30),
        }
        base["high_bank_run_risk_exchange_ratio"] = base["high_bank_run_risk_exchange_count"] / exchange_count if exchange_count else np.nan
        base["safe_bank_run_risk_exchange_ratio"] = base["safe_bank_run_risk_exchange_count"] / exchange_count if exchange_count else np.nan

        # Expand daily snapshot to every hour so hourly ML rows have liquidity context.
        for h in range(24):
            row = dict(base)
            row["hour_ts"] = pd.Timestamp(price_date, tz="UTC") + pd.Timedelta(hours=h)
            row["latest_observed_at"] = row["hour_ts"]
            row["available_at"] = row["hour_ts"] + pd.Timedelta(minutes=30)
            daily_rows.append(row)

    hourly = pd.DataFrame(daily_rows).sort_values("hour_ts").reset_index(drop=True)
    return enforce_schema(hourly, HOURLY_SCHEMA_COLUMNS)


def build_daily_from_hourly(hourly: pd.DataFrame) -> pd.DataFrame:
    if hourly.empty:
        return hourly
    h = hourly.copy()
    h["snapshot_date"] = h["hour_ts"].dt.date
    latest = h.sort_values(["snapshot_date", "hour_ts", "loaded_at"]).groupby("snapshot_date", as_index=False).tail(1)
    d = latest.rename(columns={"hour_ts": "latest_hour_ts"}).copy()

    d = d.sort_values("snapshot_date").reset_index(drop=True)
    d["exchange_reserve_return_1d"] = d["total_exchange_reserve_usd"].pct_change()
    d["exchange_reserve_change_1d_usd"] = d["total_exchange_reserve_usd"].diff()
    d["exchange_volume_return_1d"] = d["total_exchange_volume_24h_usd"].pct_change()
    d["exchange_volume_change_1d_usd"] = d["total_exchange_volume_24h_usd"].diff()
    d["system_reserve_utilization_change_1d"] = d["system_reserve_utilization"].diff()
    d["normalized_system_reserve_utilization_change_1d"] = d["normalized_system_reserve_utilization"].diff()
    d["reserve_hhi_change_1d"] = d["reserve_hhi"].diff()
    d["high_bank_run_risk_exchange_count_change_1d"] = d["high_bank_run_risk_exchange_count"].diff()
    d["whale_withdrawal_risk_change_1d"] = d["total_whale_withdrawal_risk"].diff()
    d["wash_trading_volume_ratio_change_1d"] = d["wash_trading_volume_ratio"].diff()

    return enforce_schema(d, DAILY_SCHEMA_COLUMNS)


def enforce_schema(df: pd.DataFrame, schema: Dict[str, str]) -> pd.DataFrame:
    for col in schema:
        if col not in df.columns:
            df[col] = None
    df = df[list(schema.keys())].copy()
    for col, dtype in schema.items():
        try:
            if "datetime" in dtype:
                df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
            elif dtype == "float64":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
            elif dtype == "int64":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            elif dtype == "object" and col == "snapshot_date":
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            else:
                df[col] = df[col].astype(dtype)
        except Exception as e:
            logging.warning("⚠️ Schema cast warning %s: %s", col, e)
    return df


def save_dataframe_to_parquet(df: pd.DataFrame, base_dir: str, file_prefix: str, compression: str = "snappy") -> List[str]:
    if df is None or df.empty:
        return []
    os.makedirs(base_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(base_dir, f"{file_prefix}_{ts}.parquet")
    df.to_parquet(path, index=False, engine="pyarrow", compression=compression)
    logging.info("✅ Saved %s rows=%s", path, f"{len(df):,}")
    return [path]


def parse_args() -> argparse.Namespace:
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Backfill CoinGecko exchange reserve/liquidity proxy to int schemas")
    parser.add_argument("--start", default=yesterday, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=yesterday, help="End date YYYY-MM-DD")
    parser.add_argument("--exchange-ids", nargs="+", default=DEFAULT_EXCHANGES)
    parser.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "output_data/exchange_reserve_int_backfill"))
    parser.add_argument("--reserve-volume-multiple", type=float, default=3.0, help="Reserve proxy = normalized volume * this multiple")
    parser.add_argument("--sleep", type=float, default=2.0)
    parser.add_argument("--compression", default="snappy", choices=["snappy", "gzip", "brotli"])
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    hourly_dir = os.path.join(args.output_dir, "int_exchange_reserve_hourly")
    daily_dir = os.path.join(args.output_dir, "int_exchange_reserve_daily")
    os.makedirs(hourly_dir, exist_ok=True)
    os.makedirs(daily_dir, exist_ok=True)

    logging.info("⚙️ Exchange reserve/liquidity proxy backfill: %s -> %s", args.start, args.end)
    logging.info("⚙️ Exchanges: %s", args.exchange_ids)
    logging.info("⚙️ Output dir: %s", args.output_dir)

    src = build_source_exchange_daily(
        start=args.start,
        end=args.end,
        exchange_ids=args.exchange_ids,
        reserve_volume_multiple=args.reserve_volume_multiple,
        sleep=args.sleep,
    )
    if src.empty:
        logging.error("❌ Source exchange daily data is empty")
        return

    hourly = aggregate_hourly_from_source_daily(src)
    daily = build_daily_from_hourly(hourly)

    if hourly.empty or daily.empty:
        logging.error("❌ Hourly or daily output empty")
        return

    saved_files = 0
    total_rows = 0

    # Save one file per day for both tables, like the Binance daily backfill style.
    for output_date in date_range(args.start, args.end):
        h_day = hourly[hourly["hour_ts"].dt.strftime("%Y-%m-%d") == output_date].copy()
        d_day = daily[pd.to_datetime(daily["snapshot_date"]).dt.strftime("%Y-%m-%d") == output_date].copy()

        h_files = save_dataframe_to_parquet(
            h_day,
            hourly_dir,
            f"exchange_reserve_hourly_{output_date}",
            compression=args.compression,
        )
        d_files = save_dataframe_to_parquet(
            d_day,
            daily_dir,
            f"exchange_reserve_daily_{output_date}",
            compression=args.compression,
        )
        saved_files += len(h_files) + len(d_files)
        total_rows += len(h_day) + len(d_day)

    logging.info("🎉 Exchange reserve backfill complete | files=%s | rows=%s", saved_files, f"{total_rows:,}")


if __name__ == "__main__":
    main()
