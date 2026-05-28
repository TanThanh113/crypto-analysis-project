# -*- coding: utf-8 -*-
"""
Load local Tiingo INT backfill Parquet files into BigQuery native tables.

This is the BigQuery-native replacement for the old Iceberg loader.

Targets:
  output_data/tiingo_int_backfill/int_macro_daily/tiingo_int_macro_daily_*.parquet
    -> project-lambda-crypto.dbt_quants_dev.int_macro_daily

  output_data/tiingo_int_backfill/int_etf_daily/tiingo_int_etf_daily_*.parquet
    -> project-lambda-crypto.dbt_quants_dev.int_etf_daily

Design:
  - Does NOT use PyIceberg.
  - Creates BigQuery native tables if missing.
  - Partitions both tables by price_date.
  - Loads Parquet with WRITE_APPEND.
  - Rewrites a temporary Parquet file with safe timestamp micros before loading.
  - Moves loaded source files into _processed to avoid duplicate append.

Required env:
  GCP_PROJECT_ID

Optional env:
  GCP_LOCATION=asia-southeast1
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
"""

import argparse
import glob
import logging
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Sequence

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

# =========================================================
# FIXED TARGET CONFIG
# =========================================================
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "project-lambda-crypto")
DATASET_ID = "dbt_quants_dev"
LOCATION = os.environ.get("GCP_LOCATION", "asia-southeast1")

OUTPUT_ROOT = "output_data/tiingo_int_backfill"
MOVE_PROCESSED_FILES = True

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


@dataclass(frozen=True)
class TableSpec:
    key: str
    table_name: str
    local_dir: str
    file_pattern: str
    partition_col: str
    schema: Sequence[bigquery.SchemaField]


MACRO_SCHEMA = [
    bigquery.SchemaField("price_date", "DATE"),
    bigquery.SchemaField("sp500_close", "FLOAT"),
    bigquery.SchemaField("nasdaq_close", "FLOAT"),
    bigquery.SchemaField("gold_close", "FLOAT"),
    bigquery.SchemaField("vix_close", "FLOAT"),
    bigquery.SchemaField("oil_close", "FLOAT"),
    bigquery.SchemaField("sp500_return_1d", "FLOAT"),
    bigquery.SchemaField("nasdaq_return_1d", "FLOAT"),
    bigquery.SchemaField("gold_return_1d", "FLOAT"),
    bigquery.SchemaField("vix_return_1d", "FLOAT"),
    bigquery.SchemaField("oil_return_1d", "FLOAT"),
    bigquery.SchemaField("sp500_return_5d", "FLOAT"),
    bigquery.SchemaField("nasdaq_return_5d", "FLOAT"),
    bigquery.SchemaField("gold_return_5d", "FLOAT"),
    bigquery.SchemaField("vix_return_5d", "FLOAT"),
    bigquery.SchemaField("oil_return_5d", "FLOAT"),
    bigquery.SchemaField("sp500_return_10d", "FLOAT"),
    bigquery.SchemaField("nasdaq_return_10d", "FLOAT"),
    bigquery.SchemaField("gold_return_10d", "FLOAT"),
    bigquery.SchemaField("vix_return_10d", "FLOAT"),
    bigquery.SchemaField("oil_return_10d", "FLOAT"),
    bigquery.SchemaField("total_macro_proxy_volume", "FLOAT"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP"),
    bigquery.SchemaField("available_at", "TIMESTAMP"),
    bigquery.SchemaField("nasdaq_sp500_ratio", "FLOAT"),
    bigquery.SchemaField("nasdaq_sp500_relative_return_1d", "FLOAT"),
    bigquery.SchemaField("safe_haven_bid_1d", "FLOAT"),
    bigquery.SchemaField("safe_haven_bid_5d", "FLOAT"),
    bigquery.SchemaField("oil_equity_relative_return_1d", "FLOAT"),
    bigquery.SchemaField("macro_risk_regime", "STRING"),
    bigquery.SchemaField("macro_risk_score_direction", "INTEGER"),
    bigquery.SchemaField("macro_risk_appetite_score", "FLOAT"),
    bigquery.SchemaField("macro_defensive_pressure_score", "FLOAT"),
]

ETF_SCHEMA = [
    bigquery.SchemaField("price_date", "DATE"),
    bigquery.SchemaField("etf_count", "INTEGER"),
    bigquery.SchemaField("btc_etf_count", "INTEGER"),
    bigquery.SchemaField("eth_etf_count", "INTEGER"),
    bigquery.SchemaField("total_etf_volume", "FLOAT"),
    bigquery.SchemaField("btc_etf_volume", "FLOAT"),
    bigquery.SchemaField("eth_etf_volume", "FLOAT"),
    bigquery.SchemaField("btc_etf_volume_share", "FLOAT"),
    bigquery.SchemaField("eth_etf_volume_share", "FLOAT"),
    bigquery.SchemaField("btc_etf_volume_weighted_return_1d", "FLOAT"),
    bigquery.SchemaField("eth_etf_volume_weighted_return_1d", "FLOAT"),
    bigquery.SchemaField("total_etf_volume_weighted_return_1d", "FLOAT"),
    bigquery.SchemaField("btc_etf_volume_weighted_return_5d", "FLOAT"),
    bigquery.SchemaField("eth_etf_volume_weighted_return_5d", "FLOAT"),
    bigquery.SchemaField("total_etf_volume_weighted_return_5d", "FLOAT"),
    bigquery.SchemaField("btc_etf_flow_proxy", "FLOAT"),
    bigquery.SchemaField("eth_etf_flow_proxy", "FLOAT"),
    bigquery.SchemaField("total_etf_flow_proxy", "FLOAT"),
    bigquery.SchemaField("ibit_close", "FLOAT"),
    bigquery.SchemaField("fbtc_close", "FLOAT"),
    bigquery.SchemaField("gbtc_close", "FLOAT"),
    bigquery.SchemaField("etha_close", "FLOAT"),
    bigquery.SchemaField("feth_close", "FLOAT"),
    bigquery.SchemaField("ethe_close", "FLOAT"),
    bigquery.SchemaField("ibit_return_1d", "FLOAT"),
    bigquery.SchemaField("fbtc_return_1d", "FLOAT"),
    bigquery.SchemaField("gbtc_return_1d", "FLOAT"),
    bigquery.SchemaField("etha_return_1d", "FLOAT"),
    bigquery.SchemaField("feth_return_1d", "FLOAT"),
    bigquery.SchemaField("ethe_return_1d", "FLOAT"),
    bigquery.SchemaField("ibit_volume", "FLOAT"),
    bigquery.SchemaField("fbtc_volume", "FLOAT"),
    bigquery.SchemaField("gbtc_volume", "FLOAT"),
    bigquery.SchemaField("etha_volume", "FLOAT"),
    bigquery.SchemaField("feth_volume", "FLOAT"),
    bigquery.SchemaField("ethe_volume", "FLOAT"),
    bigquery.SchemaField("most_active_etf", "STRING"),
    bigquery.SchemaField("most_active_etf_group", "STRING"),
    bigquery.SchemaField("most_active_etf_return_1d", "FLOAT"),
    bigquery.SchemaField("most_active_etf_volume", "FLOAT"),
    bigquery.SchemaField("etf_snapshot_json", "STRING"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP"),
    bigquery.SchemaField("available_at", "TIMESTAMP"),
    bigquery.SchemaField("btc_eth_etf_return_spread_1d", "FLOAT"),
    bigquery.SchemaField("btc_eth_etf_flow_proxy_spread", "FLOAT"),
    bigquery.SchemaField("crypto_etf_momentum_regime", "STRING"),
]


TABLE_SPECS: Dict[str, TableSpec] = {
    "macro": TableSpec(
        key="macro",
        table_name="int_macro_daily",
        local_dir=os.path.join(OUTPUT_ROOT, "int_macro_daily"),
        file_pattern="*tiingo_int_macro_daily_*.parquet",
        partition_col="price_date",
        schema=MACRO_SCHEMA,
    ),
    "etf": TableSpec(
        key="etf",
        table_name="int_etf_daily",
        local_dir=os.path.join(OUTPUT_ROOT, "int_etf_daily"),
        file_pattern="*tiingo_int_etf_daily_*.parquet",
        partition_col="price_date",
        schema=ETF_SCHEMA,
    ),
}


def bq_table_id(spec: TableSpec) -> str:
    return f"{PROJECT_ID}.{DATASET_ID}.{spec.table_name}"


def ensure_dataset(client: bigquery.Client) -> None:
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    dataset_ref.location = LOCATION

    try:
        client.get_dataset(dataset_ref)
        logging.info("✅ Dataset exists: %s.%s", PROJECT_ID, DATASET_ID)
    except Exception:
        client.create_dataset(dataset_ref)
        logging.info("📁 Created dataset: %s.%s", PROJECT_ID, DATASET_ID)


def ensure_table(client: bigquery.Client, spec: TableSpec) -> None:
    table_id = bq_table_id(spec)

    try:
        table = client.get_table(table_id)
        logging.info("✅ BigQuery table exists: %s | type=%s", table_id, table.table_type)
        if not table.time_partitioning or table.time_partitioning.field != spec.partition_col:
            logging.warning(
                "⚠️ Table %s exists but is not partitioned by %s. Current partitioning=%s",
                table_id,
                spec.partition_col,
                table.time_partitioning,
            )
        return

    except Exception:
        logging.info("🏗️ Creating BigQuery table: %s", table_id)

    table = bigquery.Table(table_id, schema=list(spec.schema))
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field=spec.partition_col,
    )
    client.create_table(table)
    logging.info("🎉 Created table: %s partitioned by %s", table_id, spec.partition_col)


def list_candidate_files(spec: TableSpec) -> List[str]:
    pattern = os.path.join(spec.local_dir, "**", spec.file_pattern)
    files = sorted(glob.glob(pattern, recursive=True))
    return [
        f for f in files
        if f.endswith(".parquet")
        and f"{os.sep}_processed{os.sep}" not in f
        and f"{os.sep}_failed{os.sep}" not in f
        and f"{os.sep}_state{os.sep}" not in f
        and f"{os.sep}_bq_tmp{os.sep}" not in f
    ]


def bigquery_type_to_arrow_type(bq_type: str) -> pa.DataType:
    bq_type = bq_type.upper()
    if bq_type == "STRING":
        return pa.string()
    if bq_type in ("INTEGER", "INT64"):
        return pa.int64()
    if bq_type in ("FLOAT", "FLOAT64"):
        return pa.float64()
    if bq_type in ("BOOLEAN", "BOOL"):
        return pa.bool_()
    if bq_type == "DATE":
        return pa.date32()
    if bq_type == "TIMESTAMP":
        return pa.timestamp("us", tz="UTC")
    return pa.string()


def rewrite_parquet_for_bigquery(file_path: str, spec: TableSpec) -> str:
    source_table = pq.read_table(file_path)
    arrays = []
    names = []
    row_count = source_table.num_rows

    for field in spec.schema:
        col_name = field.name
        target_type = bigquery_type_to_arrow_type(field.field_type)
        names.append(col_name)

        if col_name not in source_table.column_names:
            arrays.append(pa.nulls(row_count, type=target_type))
            continue

        col = source_table[col_name]
        try:
            if field.field_type.upper() == "TIMESTAMP":
                col = pc.cast(col, pa.timestamp("us", tz="UTC"), safe=False)
            elif field.field_type.upper() == "DATE":
                col = pc.cast(col, pa.date32(), safe=False)
            else:
                col = pc.cast(col, target_type, safe=False)
        except Exception as exc:
            logging.warning("⚠️ Could not cast %s from %s to %s: %s", col_name, col.type, target_type, exc)

        arrays.append(col)

    out_table = pa.Table.from_arrays(arrays, names=names)

    tmp_dir = os.path.join(spec.local_dir, "_bq_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_{os.path.basename(file_path)}")

    pq.write_table(
        out_table,
        tmp_path,
        compression="snappy",
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )
    return tmp_path


def move_file(spec: TableSpec, file_path: str, folder_name: str) -> str:
    target_dir = os.path.join(spec.local_dir, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    basename = os.path.basename(file_path)
    target_path = os.path.join(target_dir, f"{stamp}_{uuid.uuid4().hex[:8]}_{basename}")
    shutil.move(file_path, target_path)
    return target_path


def load_one_file(client: bigquery.Client, spec: TableSpec, file_path: str) -> int:
    rows = pq.ParquetFile(file_path).metadata.num_rows
    tmp_path = rewrite_parquet_for_bigquery(file_path, spec)

    logging.info("📦 Loading %s | rows=%s | tmp=%s", file_path, f"{rows:,}", tmp_path)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        schema=list(spec.schema),
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    with open(tmp_path, "rb") as source_file:
        load_job = client.load_table_from_file(
            source_file,
            bq_table_id(spec),
            job_config=job_config,
            location=LOCATION,
        )

    try:
        load_job.result()
    finally:
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass

    logging.info("✅ Loaded file successfully | rows=%s | %s", f"{rows:,}", file_path)
    return rows


def dry_run_spec(spec: TableSpec) -> None:
    files = list_candidate_files(spec)
    logging.info("🚀 DRY RUN target: %s", bq_table_id(spec))
    logging.info("📂 Local dir: %s", spec.local_dir)
    logging.info("🔎 Pattern: %s", spec.file_pattern)
    logging.info("🧩 Partition column: %s", spec.partition_col)
    logging.info("📦 Found files: %s", len(files))

    total_rows = 0
    for file_path in files:
        rows = pq.ParquetFile(file_path).metadata.num_rows
        total_rows += rows
        logging.info("DRY %s | rows=%s", file_path, f"{rows:,}")

    logging.info("✅ DRY RUN %s total rows=%s", spec.table_name, f"{total_rows:,}")


def process_spec(client: bigquery.Client, spec: TableSpec, keep_files: bool) -> None:
    files = list_candidate_files(spec)
    if not files:
        logging.warning("⚠️ No files found for %s in %s", spec.table_name, spec.local_dir)
        return

    ensure_dataset(client)
    ensure_table(client, spec)

    loaded_files = 0
    loaded_rows = 0
    failed_files = 0

    for file_path in files:
        try:
            rows = load_one_file(client, spec, file_path)
            loaded_files += 1
            loaded_rows += rows

            if MOVE_PROCESSED_FILES and not keep_files:
                processed_path = move_file(spec, file_path, "_processed")
                logging.info("🧹 Moved to processed: %s", processed_path)

        except Exception as exc:
            failed_files += 1
            logging.error("❌ Failed loading %s: %s", file_path, exc)
            try:
                failed_path = move_file(spec, file_path, "_failed")
                logging.error("Moved failed file to: %s", failed_path)
            except Exception as move_exc:
                logging.error("Could not move failed file %s: %s", file_path, move_exc)

    logging.info(
        "🎉 BigQuery load complete | table=%s | loaded_files=%s | loaded_rows=%s | failed_files=%s",
        bq_table_id(spec),
        loaded_files,
        f"{loaded_rows:,}",
        failed_files,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Tiingo INT daily Parquet files into BigQuery native tables.")
    parser.add_argument("--type", choices=["macro", "etf", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-files", action="store_true", help="Do not move loaded files into _processed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected_specs = TABLE_SPECS.values() if args.type == "all" else [TABLE_SPECS[args.type]]

    logging.info("🚀 Starting Tiingo BigQuery native loader")
    logging.info("🎯 Project=%s Dataset=%s Location=%s", PROJECT_ID, DATASET_ID, LOCATION)

    if args.dry_run:
        for spec in selected_specs:
            dry_run_spec(spec)
        return

    client = bigquery.Client(project=PROJECT_ID, location=LOCATION)
    for spec in selected_specs:
        process_spec(client, spec, keep_files=args.keep_files)

    logging.info("🎉 Tiingo BigQuery native load complete")


if __name__ == "__main__":
    main()
