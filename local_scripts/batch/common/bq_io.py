from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from google.api_core.exceptions import NotFound
from google.cloud import bigquery


@dataclass(frozen=True)
class BigQueryWriteSpec:
    project_id: str
    dataset_id: str
    table_id: str
    location: str
    columns: list[str]
    required_columns: list[str]


class BigQueryTableWriter:
    """
    Shared BigQuery append-only writer.

    Important:
    - BigQuery table schema is managed by Terraform.
    - Python must not pass schema in LoadJobConfig.
    - This writer only checks table existence, column order, dtypes, and required nulls.
    """

    def __init__(self, client: bigquery.Client):
        self.client = client

    def __init__(self, client: bigquery.Client):
        self.client = client

    def full_table_id(self, spec: BigQueryWriteSpec) -> str:
        return f"{spec.project_id}.{spec.dataset_id}.{spec.table_id}"

    def table_exists(self, spec: BigQueryWriteSpec) -> bool:
        try:
            self.client.get_table(self.full_table_id(spec))
            return True
        except NotFound:
            return False

    def prepare_dataframe(self, df: pd.DataFrame, spec: BigQueryWriteSpec) -> pd.DataFrame:
        missing_columns = [column for column in spec.columns if column not in df.columns]
        if missing_columns:
            raise ValueError(
                f"Missing output columns for {self.full_table_id(spec)}: {missing_columns}"
            )

        prepared = df[spec.columns].copy()

        for column in spec.columns:
            if column.endswith("_ts") or column.endswith("_at"):
                prepared[column] = pd.to_datetime(
                    prepared[column],
                    errors="coerce",
                    utc=True,
                )

        if "success" in prepared.columns:
            prepared["success"] = prepared["success"].astype(bool)

        for column in prepared.columns:
            if column == "success":
                continue
            if column.endswith("_ts") or column.endswith("_at"):
                continue
            prepared[column] = prepared[column].astype("string")

        null_required = {
            column: int(prepared[column].isna().sum())
            for column in spec.required_columns
            if column in prepared.columns
        }
        null_required = {
            column: count
            for column, count in null_required.items()
            if count > 0
        }

        if null_required:
            raise ValueError(
                f"Required columns contain null values for {self.full_table_id(spec)}: {null_required}"
            )

        return prepared

    def append_dataframe(self, df: pd.DataFrame, spec: BigQueryWriteSpec) -> None:
        destination = self.full_table_id(spec)

        if not self.table_exists(spec):
            raise RuntimeError(
                f"Destination table does not exist: {destination}. "
                "Create it with Terraform before running this job."
            )

        prepared = self.prepare_dataframe(df, spec)

        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )

        job = self.client.load_table_from_dataframe(
            prepared,
            destination,
            job_config=job_config,
            location=spec.location,
        )
        job.result()

        print(f"[bq-writer] Wrote {len(prepared)} rows to {destination}")
