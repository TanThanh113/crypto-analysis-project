from __future__ import annotations

import pandas as pd
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from common.bq_io import BigQueryTableWriter, BigQueryWriteSpec
from monitoring.settings import MonitoringSettings


HEALTH_RESULT_COLUMNS = [
    "check_ts",
    "run_id",
    "check_id",
    "check_type",
    "severity",
    "success",
    "metric_value",
    "threshold",
    "message",
    "details_json",
]

HEALTH_RESULT_REQUIRED_COLUMNS = [
    "check_ts",
    "run_id",
    "check_id",
    "check_type",
    "severity",
    "success",
]


class BigQueryMonitoringClient:
    def __init__(self, settings: MonitoringSettings):
        self.settings = settings
        self.client = bigquery.Client(
            project=settings.project_id,
            location=settings.location,
        )
        self.writer = BigQueryTableWriter(self.client)

    def table_id(self, dataset: str, table: str) -> str:
        return f"{self.settings.project_id}.{dataset}.{table}"

    def table_ref_sql(self, dataset: str, table: str) -> str:
        return f"`{self.table_id(dataset, table)}`"

    def table_exists(self, dataset: str, table: str) -> bool:
        try:
            self.client.get_table(self.table_id(dataset, table))
            return True
        except NotFound:
            return False

    def read_dataframe(self, sql: str) -> pd.DataFrame:
        query_job = self.client.query(sql, location=self.settings.location)
        return query_job.result().to_dataframe()

    def write_results(self, df: pd.DataFrame, table_name: str) -> None:
        spec = BigQueryWriteSpec(
            project_id=self.settings.project_id,
            dataset_id=self.settings.ml_outputs_dataset,
            table_id=table_name,
            location=self.settings.location,
            columns=HEALTH_RESULT_COLUMNS,
            required_columns=HEALTH_RESULT_REQUIRED_COLUMNS,
        )

        self.writer.append_dataframe(df, spec)
