from __future__ import annotations

import pandas as pd
from google.cloud import bigquery

from common.bq_io import BigQueryTableWriter, BigQueryWriteSpec
from quality_audit.settings import QualityAuditSettings


AUDIT_RESULT_COLUMNS = [
    "audit_ts",
    "project_id",
    "table_name",
    "suite_name",
    "expectation_type",
    "success",
    "severity",
    "result_json",
    "expectation_json",
]

AUDIT_RESULT_REQUIRED_COLUMNS = [
    "audit_ts",
    "table_name",
    "success",
]


class BigQueryAuditClient:
    def __init__(self, settings: QualityAuditSettings):
        self.settings = settings
        self.client = bigquery.Client(
            project=settings.project_id,
            location=settings.location,
        )
        self.writer = BigQueryTableWriter(self.client)

    def table_ref(self, dataset: str, table: str) -> str:
        return f"`{self.settings.project_id}.{dataset}.{table}`"

    def read_dataframe(self, sql: str) -> pd.DataFrame:
        query_job = self.client.query(sql, location=self.settings.location)
        return query_job.result().to_dataframe()

    def write_dataframe(self, df: pd.DataFrame, table_name: str) -> None:
        spec = BigQueryWriteSpec(
            project_id=self.settings.project_id,
            dataset_id=self.settings.ml_outputs_dataset,
            table_id=table_name,
            location=self.settings.location,
            columns=AUDIT_RESULT_COLUMNS,
            required_columns=AUDIT_RESULT_REQUIRED_COLUMNS,
        )

        self.writer.append_dataframe(df, spec)
