# -*- coding: utf-8 -*-
"""
BigQuery native loader for funding hourly backfill.

This is the funding version of load_int_market_trades_hourly_to_bigquery.py.

Flow:
  output_data/binance_batch_trades/*binance_funding_hourly_*.parquet
    -> project-lambda-crypto.dbt_quants_dev.int_funding_hourly
    -> BigQuery native partitioned table by hour_ts
    -> clustered by symbol
    -> move successfully loaded source files to _processed

Why BigQuery native:
  int_funding_hourly is an int/dbt table, so we load into the BigQuery table directly.
  Do not use Iceberg REST here.

Required env vars:
  GCP_PROJECT_ID

Optional env vars:
  GCP_LOCATION=asia-southeast1
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

Notes:
  - The loader rewrites Parquet to a temp file with TIMESTAMP_MICROS to avoid
    BigQuery errors on TIMESTAMP_NANOS.
  - It scans _failed files too, so failed files can be retried after fixing the loader.
  - It skips _processed and _bq_tmp.
"""

import argparse
import glob
import logging
import os
import shutil
import sys
import uuid
from datetime import datetime
from typing import List, Tuple

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from dotenv import load_dotenv
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

load_dotenv()

# =========================================================
# FIXED PIPELINE CONFIG
# =========================================================
LOCAL_OUTPUT_DIR = "output_data/binance_batch_trades"
FILE_PATTERN = "*binance_funding_hourly_*.parquet"

DATASET_ID = "dbt_quants_dev"
TABLE_ID = "int_funding_hourly"

PARTITION_COL = "hour_ts"
CLUSTER_COLS = ["symbol"]

MOVE_PROCESSED_FILES = True

# =========================================================
# GOOGLE ENV CONFIG
# =========================================================
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "project-lambda-crypto")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "asia-southeast1")

FULL_TABLE_ID = f"{GCP_PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

# =========================================================
# TARGET BIGQUERY SCHEMA: int_funding_hourly
# Keep aligned with dbt model output.
# =========================================================
BQ_SCHEMA = [
    bigquery.SchemaField("hour_ts", "TIMESTAMP"),
    bigquery.SchemaField("symbol", "STRING"),

    bigquery.SchemaField("exchanges_reporting", "INTEGER"),

    bigquery.SchemaField("avg_mark_price", "FLOAT"),
    bigquery.SchemaField("avg_spot_price", "FLOAT"),
    bigquery.SchemaField("avg_basis_spread", "FLOAT"),
    bigquery.SchemaField("avg_basis_pct", "FLOAT"),
    bigquery.SchemaField("max_abs_basis_pct", "FLOAT"),

    bigquery.SchemaField("avg_funding_rate_coin", "FLOAT"),
    bigquery.SchemaField("avg_funding_rate_usdt", "FLOAT"),
    bigquery.SchemaField("avg_annualized_funding_coin", "FLOAT"),
    bigquery.SchemaField("avg_annualized_funding_usdt", "FLOAT"),
    bigquery.SchemaField("funding_dispersion_coin", "FLOAT"),

    bigquery.SchemaField("avg_annualized_basis_coin", "FLOAT"),
    bigquery.SchemaField("avg_annualized_basis_usdt", "FLOAT"),
    bigquery.SchemaField("avg_arbitrage_spread", "FLOAT"),
    bigquery.SchemaField("max_abs_arbitrage_spread", "FLOAT"),

    bigquery.SchemaField("max_leverage_stress", "FLOAT"),
    bigquery.SchemaField("avg_leverage_stress", "FLOAT"),

    bigquery.SchemaField("dominant_funding_regime", "STRING"),
    bigquery.SchemaField("dominant_arbitrage_opportunity", "STRING"),
    bigquery.SchemaField("strongest_arbitrage_exchange", "STRING"),
    bigquery.SchemaField("highest_stress_exchange", "STRING"),
    bigquery.SchemaField("exchange_snapshot_json", "STRING"),

    bigquery.SchemaField("latest_observed_at", "TIMESTAMP"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP"),
    bigquery.SchemaField("available_at", "TIMESTAMP"),
]

BQ_TYPE_TO_ARROW = {
    "STRING": pa.string(),
    "INTEGER": pa.int64(),
    "INT64": pa.int64(),
    "FLOAT": pa.float64(),
    "FLOAT64": pa.float64(),
    "BOOL": pa.bool_(),
    "BOOLEAN": pa.bool_(),
    "TIMESTAMP": pa.timestamp("us", tz="UTC"),
    "DATETIME": pa.timestamp("us"),
    "DATE": pa.date32(),
}


def bq_arrow_type(field: bigquery.SchemaField) -> pa.DataType:
    return BQ_TYPE_TO_ARROW.get(field.field_type.upper(), pa.string())


def validate_env() -> None:
    if not GCP_PROJECT_ID:
        raise RuntimeError("Missing GCP_PROJECT_ID")


def make_client() -> bigquery.Client:
    validate_env()
    return bigquery.Client(project=GCP_PROJECT_ID, location=GCP_LOCATION)


def ensure_dataset(client: bigquery.Client) -> None:
    dataset_ref = f"{GCP_PROJECT_ID}.{DATASET_ID}"

    try:
        client.get_dataset(dataset_ref)
        logging.info("✅ Dataset exists: %s", dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = GCP_LOCATION
        client.create_dataset(dataset)
        logging.info("📁 Created dataset: %s | location=%s", dataset_ref, GCP_LOCATION)


def ensure_table(client: bigquery.Client) -> None:
    ensure_dataset(client)

    try:
        table = client.get_table(FULL_TABLE_ID)
        logging.info("✅ BigQuery table exists: %s | type=%s", FULL_TABLE_ID, table.table_type)

        if table.table_type != "TABLE":
            raise RuntimeError(f"{FULL_TABLE_ID} exists but is not a TABLE. Type={table.table_type}")

        if not table.time_partitioning or table.time_partitioning.field != PARTITION_COL:
            logging.warning(
                "⚠️ Table exists but partitioning is not field=%s. Current partitioning=%s. "
                "If this table is new/empty, recreate it for best performance.",
                PARTITION_COL,
                table.time_partitioning,
            )

        current_clusters = list(table.clustering_fields or [])
        if current_clusters != CLUSTER_COLS:
            logging.warning(
                "⚠️ Table exists but clustering is not %s. Current clustering=%s.",
                CLUSTER_COLS,
                current_clusters,
            )

        return

    except NotFound:
        logging.info("🏗️ Creating BigQuery native table: %s", FULL_TABLE_ID)

    table = bigquery.Table(FULL_TABLE_ID, schema=BQ_SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field=PARTITION_COL,
    )
    table.clustering_fields = CLUSTER_COLS

    client.create_table(table)
    logging.info(
        "🎉 Created table: %s | partition=%s | cluster=%s",
        FULL_TABLE_ID,
        PARTITION_COL,
        CLUSTER_COLS,
    )


def list_parquet_files() -> List[str]:
    pattern = os.path.join(LOCAL_OUTPUT_DIR, "**", FILE_PATTERN)
    candidates = glob.glob(pattern, recursive=True)

    files = []
    for f in candidates:
        if not f.endswith(".parquet"):
            continue

        # Do not reload already loaded files or temporary rewritten files.
        if f"{os.sep}_processed{os.sep}" in f:
            continue
        if f"{os.sep}_bq_tmp{os.sep}" in f:
            continue

        # Keep _failed included so fixed loader can retry failed files.
        files.append(f)

    files.sort()
    return files


def move_file(file_path: str, folder_name: str) -> str:
    target_dir = os.path.join(LOCAL_OUTPUT_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)

    basename = os.path.basename(file_path)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target_path = os.path.join(target_dir, f"{stamp}_{uuid.uuid4().hex[:8]}_{basename}")

    shutil.move(file_path, target_path)
    return target_path


def align_arrow_table_to_bq_schema(table: pa.Table) -> pa.Table:
    arrays = []
    names = []
    row_count = table.num_rows

    for field in BQ_SCHEMA:
        col_name = field.name
        target_type = bq_arrow_type(field)
        names.append(col_name)

        if col_name not in table.column_names:
            arrays.append(pa.nulls(row_count, type=target_type))
            continue

        column = table[col_name]

        try:
            if field.field_type.upper() == "TIMESTAMP":
                column = pc.cast(column, pa.timestamp("us", tz="UTC"), safe=False)
            elif field.field_type.upper() in ("FLOAT", "FLOAT64"):
                column = pc.cast(column, pa.float64(), safe=False)
            elif field.field_type.upper() in ("INTEGER", "INT64"):
                column = pc.cast(column, pa.int64(), safe=False)
            elif field.field_type.upper() == "STRING":
                column = pc.cast(column, pa.string(), safe=False)
            elif field.field_type.upper() in ("BOOL", "BOOLEAN"):
                column = pc.cast(column, pa.bool_(), safe=False)
        except Exception as exc:
            logging.warning(
                "⚠️ Could not cast column %s from %s to %s: %s",
                col_name,
                column.type,
                target_type,
                exc,
            )

        arrays.append(column)

    return pa.Table.from_arrays(arrays, names=names)


def rewrite_parquet_for_bigquery(source_path: str) -> Tuple[str, int]:
    """Rewrite source Parquet as a temporary BigQuery-compatible Parquet file.

    Main purpose:
      - convert TIMESTAMP_NANOS to TIMESTAMP_MICROS
      - align columns/order with target table
      - add missing nullable columns if needed
    """
    tmp_dir = os.path.join(LOCAL_OUTPUT_DIR, "_bq_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_{os.path.basename(source_path)}")

    source_table = pq.read_table(source_path)
    aligned_table = align_arrow_table_to_bq_schema(source_table)

    pq.write_table(
        aligned_table,
        tmp_path,
        compression="snappy",
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )

    return tmp_path, aligned_table.num_rows


def load_one_file(client: bigquery.Client, file_path: str) -> int:
    tmp_path, rows = rewrite_parquet_for_bigquery(file_path)

    logging.info("📦 Loading %s | rows=%s | tmp=%s", file_path, f"{rows:,}", tmp_path)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema=BQ_SCHEMA,
    )

    try:
        with open(tmp_path, "rb") as f:
            job = client.load_table_from_file(
                f,
                FULL_TABLE_ID,
                job_config=job_config,
                location=GCP_LOCATION,
            )
        job.result()
        return rows

    finally:
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass


def dry_run(files: List[str]) -> None:
    total = 0

    logging.info("🚀 DRY RUN target: %s", FULL_TABLE_ID)
    logging.info("📂 Local dir: %s", LOCAL_OUTPUT_DIR)
    logging.info("🔎 Pattern: %s", FILE_PATTERN)
    logging.info("📦 Found files: %s", len(files))

    for file_path in files:
        parquet_file = pq.ParquetFile(file_path)
        rows = parquet_file.metadata.num_rows
        total += rows
        logging.info(
            "DRY %s | rows=%s | columns=%s",
            file_path,
            f"{rows:,}",
            parquet_file.schema_arrow.names,
        )

    logging.info("✅ DRY RUN total rows=%s", f"{total:,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load int_funding_hourly Parquet backfill files to BigQuery native table.")
    parser.add_argument("--dry-run", action="store_true", help="List files and row counts without loading.")
    parser.add_argument("--keep-files", action="store_true", help="Do not move loaded files to _processed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.info("🚀 Starting BigQuery native funding loader")
    logging.info("🎯 Target table: %s", FULL_TABLE_ID)
    logging.info("📂 Local dir: %s", LOCAL_OUTPUT_DIR)
    logging.info("🔎 File pattern: %s", FILE_PATTERN)
    logging.info("🧩 Partition column: %s", PARTITION_COL)
    logging.info("📍 BigQuery location: %s", GCP_LOCATION)

    files = list_parquet_files()
    if not files:
        logging.warning("⚠️ No funding files found in %s pattern=%s", LOCAL_OUTPUT_DIR, FILE_PATTERN)
        return

    if args.dry_run:
        dry_run(files)
        return

    client = make_client()
    ensure_table(client)

    loaded_files = 0
    loaded_rows = 0
    failed_files = 0

    for file_path in files:
        try:
            rows = load_one_file(client, file_path)
            loaded_files += 1
            loaded_rows += rows

            logging.info("✅ Loaded file successfully | rows=%s | %s", f"{rows:,}", file_path)

            if MOVE_PROCESSED_FILES and not args.keep_files:
                processed_path = move_file(file_path, "_processed")
                logging.info("🧹 Moved to processed: %s", processed_path)

        except Exception as exc:
            failed_files += 1
            logging.error("❌ Failed loading %s: %s", file_path, exc)

            try:
                failed_path = move_file(file_path, "_failed")
                logging.error("Moved failed file to: %s", failed_path)
            except Exception as move_exc:
                logging.error("Could not move failed file %s: %s", file_path, move_exc)

    logging.info(
        "🎉 BigQuery funding load complete | loaded_files=%s | loaded_rows=%s | failed_files=%s | target=%s",
        loaded_files,
        f"{loaded_rows:,}",
        failed_files,
        FULL_TABLE_ID,
    )


if __name__ == "__main__":
    main()
