# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

import pandas as pd
from google.cloud import bigquery

from quality_audit.settings import QualityAuditSettings

# Create a new dataclass to BiqQuery Audit Client.
class BigQueryAuditClient:
    # Update the configuration of the class setting variable.
    def __init__(self, settings: QualityAuditSettings):
        self.settings = settings
        # Create a new BigQuery client.
        self.client = bigquery.Client(
            project=settings.project_id,
            location=settings.location,
        )
    
    # Create a table reference.
    def table_ref(self, dataset: str, table: str) -> str:
        return f"`{self.settings.project_id}.{dataset}.{table}`"

    # Function to pass SQL statements to BigQuery and receive dataframes in return.
    def read_dataframe(self, sql: str) -> pd.DataFrame:
        query_job = self.client.query(sql, location=self.settings.location)
        return query_job.result().to_dataframe()

    # Create the full path to the destination table where the data will be stored.
    def write_dataframe(self, df: pd.DataFrame, table_name: str) -> None:
        destination = (
            f"{self.settings.project_id}."
            f"{self.settings.ml_outputs_dataset}."
            f"{table_name}"
        )

        # Create schema for the save table and add-to-end write mode.
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema=[
                bigquery.SchemaField("audit_ts", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("project_id", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("suite_name", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("expectation_type", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("success", "BOOLEAN", mode="REQUIRED"),
                bigquery.SchemaField("severity", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("result_json", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("expectation_json", "STRING", mode="NULLABLE"),
            ],
        )

        # Create a job to load the data into the table.
        job = self.client.load_table_from_dataframe(
            df,  # Pass the dataframe to the job.
            destination,  # Pass the destination table.
            job_config=job_config,  # Pass the job configuration.
        )
        job.result() # Wait until data writing is complete.
        print(f"[quality-audit] Wrote {len(df)} rows to {destination}")
