# -*- coding: utf-8 -*-
"""
Load local hourly backfill Parquet files into BigQuery native table:
  project-lambda-crypto.dbt_quants_dev.int_market_trades_hourly

Why this loader exists:
  - int_market_trades_hourly is a BigQuery/dbt-managed native table, not an Iceberg table.
  - Backfill files are local Parquet files created by:
      binance_backfill_raw_trades_to_hourly_int_daily_window.py
  - BigQuery can fail on Parquet TIMESTAMP_NANOS, so this loader rewrites a temporary
    Parquet copy with all timestamp columns coerced to TIMESTAMP_MICROS before loading.

Only Google/GCP values come from .env:
  GCP_PROJECT_ID=project-lambda-crypto
  GCP_LOCATION=asia-southeast1
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json  # optional if ADC is configured
"""

import argparse
import glob
import logging
import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

load_dotenv()

# =========================================================
# PIPELINE DEFAULTS
# =========================================================
# Path to local Parquet files produced by binance_backfill_raw_trades_to_hourly_int_daily_window.py
LOCAL_OUTPUT_DIR = "output_data/binance_batch_trades"
FILE_PATTERN = "*binance_market_hourly_*.parquet"

# Information about the target BigQuery table.
BQ_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "project-lambda-crypto")
BQ_DATASET = "dbt_quants_dev"
BQ_TABLE = "int_market_trades_hourly"
BQ_LOCATION = os.environ.get("GCP_LOCATION", "asia-southeast1")

# Path to the target BigQuery table.
FULL_TABLE_ID = f"{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"

# Partition and clustering fields.
PARTITION_COL = "hour_ts"
CLUSTER_FIELDS = ["symbol"]

# Whether to move successfully loaded files into _processed.
# If False, they will be left in the local dir.
MOVE_PROCESSED_FILES = True
TMP_DIR_NAME = "_bq_tmp"
PROCESSED_DIR_NAME = "_processed"
FAILED_DIR_NAME = "_failed"

# BigQuery INT schema matching dbt int_market_trades_hourly output.
BQ_SCHEMA = [
    bigquery.SchemaField("hour_ts", "TIMESTAMP"),
    bigquery.SchemaField("symbol", "STRING"),
    bigquery.SchemaField("pair_symbol", "STRING"),

    bigquery.SchemaField("open_price", "FLOAT"),
    bigquery.SchemaField("high_price", "FLOAT"),
    bigquery.SchemaField("low_price", "FLOAT"),
    bigquery.SchemaField("close_price", "FLOAT"),
    bigquery.SchemaField("vwap_price", "FLOAT"),

    bigquery.SchemaField("trade_count", "INTEGER"),
    bigquery.SchemaField("unique_trade_count", "INTEGER"),
    bigquery.SchemaField("base_volume", "FLOAT"),
    bigquery.SchemaField("quote_volume", "FLOAT"),

    bigquery.SchemaField("taker_sell_quote_volume", "FLOAT"),
    bigquery.SchemaField("taker_buy_quote_volume", "FLOAT"),
    bigquery.SchemaField("taker_buy_quote_ratio", "FLOAT"),

    bigquery.SchemaField("first_trade_at", "TIMESTAMP"),
    bigquery.SchemaField("last_trade_at", "TIMESTAMP"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP"),
    bigquery.SchemaField("available_at", "TIMESTAMP"),

    bigquery.SchemaField("return_1h", "FLOAT"),
    bigquery.SchemaField("log_return_1h", "FLOAT"),
    bigquery.SchemaField("quote_volume_24h", "FLOAT"),
    bigquery.SchemaField("avg_return_24h", "FLOAT"),
    bigquery.SchemaField("realized_volatility_24h", "FLOAT"),
    bigquery.SchemaField("quote_volume_zscore_24h", "FLOAT"),
]

# Required columns of the table(s) that are timestamps.
TIMESTAMP_COLUMNS = {
    "hour_ts",
    "first_trade_at",
    "last_trade_at",
    "loaded_at",
    "available_at",
}

# Required columns of the table(s) that are integers.
INT_COLUMNS = {
    "trade_count",
    "unique_trade_count",
}

# Required columns of the table(s) that are floats.
FLOAT_COLUMNS = {
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "vwap_price",
    "base_volume",
    "quote_volume",
    "taker_sell_quote_volume",
    "taker_buy_quote_volume",
    "taker_buy_quote_ratio",
    "return_1h",
    "log_return_1h",
    "quote_volume_24h",
    "avg_return_24h",
    "realized_volatility_24h",
    "quote_volume_zscore_24h",
}

# Required columns of the table(s) that are strings.
STRING_COLUMNS = {
    "symbol",
    "pair_symbol",
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

# Create a client to connect to the dataset.
def bq_client() -> bigquery.Client:
    return bigquery.Client(project=BQ_PROJECT_ID, location=BQ_LOCATION)

# Check if the dataset exists; if not, create it based on location.
def ensure_dataset(client: bigquery.Client) -> None:
    dataset_id = f"{BQ_PROJECT_ID}.{BQ_DATASET}"
    try:
        client.get_dataset(dataset_id)
        logging.info("✅ Dataset exists: %s", dataset_id)
    except NotFound:
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = BQ_LOCATION
        client.create_dataset(dataset)
        logging.info("✅ Created dataset: %s", dataset_id)

# Check if the table exists; if not, create it based on schema.
def ensure_table(client: bigquery.Client) -> bigquery.Table:
    try:
        table = client.get_table(FULL_TABLE_ID)
        logging.info("✅ BigQuery table exists: %s | type=%s", FULL_TABLE_ID, table.table_type)

        if table.time_partitioning:
            logging.info(
                "🧩 Existing partitioning: type=%s field=%s",
                table.time_partitioning.type_,
                table.time_partitioning.field,
            )
        else:
            logging.warning(
                "⚠️ Existing table is not partitioned. BigQuery cannot change partitioning in-place."
            )

        return table

    except NotFound:
        # Create the table and set partitioning and clustering.
        table = bigquery.Table(FULL_TABLE_ID, schema=BQ_SCHEMA)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=PARTITION_COL,
        )
        table.clustering_fields = CLUSTER_FIELDS
        table = client.create_table(table)
        logging.info(
            "✅ Created BigQuery table: %s partition_by=%s cluster_by=%s",
            FULL_TABLE_ID,
            PARTITION_COL,
            CLUSTER_FIELDS,
        )
        return table

# List Parquet files in the local dir.
def list_parquet_files(include_failed: bool = True) -> List[str]:
    pattern = os.path.join(LOCAL_OUTPUT_DIR, "**", FILE_PATTERN)
    candidates = glob.glob(pattern, recursive=True)

    files = []
    for file_path in candidates:
        if not file_path.endswith(".parquet"):
            continue
        
        # Replaace "\" with "/" to match the pattern.
        normalized = file_path.replace("\\", "/")
        if f"/{PROCESSED_DIR_NAME}/" in normalized:
            continue
        if f"/{TMP_DIR_NAME}/" in normalized:
            continue

        if not include_failed and f"/{FAILED_DIR_NAME}/" in normalized:
            continue

        files.append(file_path)

    files.sort()
    return files

# Convert a Parquet column to an Arrow type.
def _target_arrow_type(col_name: str):
    if col_name in TIMESTAMP_COLUMNS:
        return pa.timestamp("us", tz="UTC")
    if col_name in INT_COLUMNS:
        return pa.int64()
    if col_name in FLOAT_COLUMNS:
        return pa.float64()
    if col_name in STRING_COLUMNS:
        return pa.string()
    return pa.string()

# Convert a Parquet table to an Arrow table with the same schema.
def normalize_arrow_table(table: pa.Table) -> pa.Table:
    """Reorder columns and coerce timestamps from ns to us for BigQuery Parquet load."""
    arrays = []
    names = []
    row_count = table.num_rows

    for field in BQ_SCHEMA:
        col_name = field.name
        target_type = _target_arrow_type(col_name)
        names.append(col_name)

        if col_name not in table.column_names:
            arrays.append(pa.nulls(row_count, type=target_type))
            continue

        col = table[col_name]

        try:
            if col_name in TIMESTAMP_COLUMNS:
                # BigQuery load rejects Parquet TIMESTAMP_NANOS. Force TIMESTAMP_MICROS.
                col = pc.cast(col, pa.timestamp("us", tz="UTC"), safe=False)
            elif col_name in INT_COLUMNS:
                col = pc.cast(col, pa.int64(), safe=False)
            elif col_name in FLOAT_COLUMNS:
                col = pc.cast(col, pa.float64(), safe=False)
            elif col_name in STRING_COLUMNS:
                col = pc.cast(col, pa.string(), safe=False)
        except Exception as exc:
            logging.warning(
                "⚠️ Cast warning column=%s source_type=%s target_type=%s error=%s",
                col_name,
                col.type,
                target_type,
                exc,
            )
            col = pc.cast(col, target_type, safe=False)

        arrays.append(col)

    return pa.Table.from_arrays(arrays, names=names)

# Create a copy of the Parquet file that is fully compatible with BigQuery.
def make_bq_compatible_parquet(source_file: str) -> Tuple[str, int]:
    source_path = Path(source_file)
    tmp_dir = Path(LOCAL_OUTPUT_DIR) / TMP_DIR_NAME
    tmp_dir.mkdir(parents=True, exist_ok=True)

    tmp_file = tmp_dir / f"{uuid.uuid4().hex}_{source_path.name}"

    arrow_table = pq.read_table(source_file)
    row_count = arrow_table.num_rows
    normalized = normalize_arrow_table(arrow_table)

    pq.write_table(
        normalized,
        tmp_file,
        compression="snappy",
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
        use_deprecated_int96_timestamps=False,
    )

    return str(tmp_file), row_count

# Implement the process of uploading a single file to BigQuery.
def load_one_file(client: bigquery.Client, source_file: str) -> int:
    tmp_file, row_count = make_bq_compatible_parquet(source_file)
    logging.info("📦 Loading %s | rows=%s | tmp=%s", source_file, f"{row_count:,}", tmp_file)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        schema=BQ_SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
    )

    try:
        with open(tmp_file, "rb") as f:
            job = client.load_table_from_file(
                f,
                FULL_TABLE_ID,
                job_config=job_config,
                location=BQ_LOCATION,
            )
        job.result()
        return row_count
    finally:
        try:
            os.remove(tmp_file)
        except FileNotFoundError:
            pass


def move_file(file_path: str, folder_name: str) -> str:
    target_dir = os.path.join(LOCAL_OUTPUT_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    basename = os.path.basename(file_path)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target_path = os.path.join(target_dir, f"{stamp}_{uuid.uuid4().hex[:8]}_{basename}")
    shutil.move(file_path, target_path)
    return target_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load int_market_trades_hourly Parquet backfill into BigQuery native table.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-files", action="store_true")
    parser.add_argument(
        "--skip-failed-dir",
        action="store_true",
        help="Do not retry files currently in _failed. By default this loader retries them.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.info("🚀 Starting BigQuery native loader")
    logging.info("🎯 Target table: %s", FULL_TABLE_ID)
    logging.info("📂 Local dir: %s", LOCAL_OUTPUT_DIR)
    logging.info("🔎 File pattern: %s", FILE_PATTERN)
    logging.info("🧩 Partition column: %s", PARTITION_COL)
    logging.info("📍 BigQuery location: %s", BQ_LOCATION)

    parquet_files = list_parquet_files(include_failed=not args.skip_failed_dir)

    if not parquet_files:
        logging.warning("⚠️ No files found. Nothing to load.")
        return

    logging.info("📄 Found %s parquet files", len(parquet_files))

    if args.dry_run:
        total_rows = 0
        for file_path in parquet_files:
            try:
                rows = pq.ParquetFile(file_path).metadata.num_rows
            except Exception:
                rows = pq.read_table(file_path).num_rows
            logging.info("DRY RUN | %s | rows=%s", file_path, f"{rows:,}")
            total_rows += rows
        logging.info(
            "✅ DRY RUN complete | files=%s | rows=%s | target=%s",
            len(parquet_files),
            f"{total_rows:,}",
            FULL_TABLE_ID,
        )
        return

    client = bq_client()
    ensure_dataset(client)
    ensure_table(client)

    loaded_files = 0
    loaded_rows = 0
    failed_files = 0

    for file_path in parquet_files:
        try:
            rows = load_one_file(client, file_path)
            loaded_files += 1
            loaded_rows += rows
            logging.info("✅ Loaded file successfully | rows=%s | %s", f"{rows:,}", file_path)

            if MOVE_PROCESSED_FILES and not args.keep_files:
                processed_path = move_file(file_path, PROCESSED_DIR_NAME)
                logging.info("🧹 Moved to processed: %s", processed_path)

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            failed_files += 1
            logging.error("❌ Failed loading %s: %s", file_path, exc)

            # Do not keep renesting _failed/_failed. If already failed, leave it there.
            if f"{os.sep}{FAILED_DIR_NAME}{os.sep}" not in file_path and not args.keep_files:
                try:
                    failed_path = move_file(file_path, FAILED_DIR_NAME)
                    logging.error("Moved failed file to: %s", failed_path)
                except Exception as move_exc:
                    logging.error("Could not move failed file %s: %s", file_path, move_exc)

    logging.info(
        "🎉 BigQuery load complete | loaded_files=%s | loaded_rows=%s | failed_files=%s | target=%s",
        loaded_files,
        f"{loaded_rows:,}",
        failed_files,
        FULL_TABLE_ID,
    )


if __name__ == "__main__":
    main()
