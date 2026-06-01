# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

import yaml
import pandas as pd
import great_expectations as gx

from quality_audit.bq_client import BigQueryAuditClient
from quality_audit.gx_runner import GxRunner
from quality_audit.settings import QualityAuditSettings

# Create a new dataclass to run the audit service.
class QualityAuditService:
    # Update the configuration of the class setting variable.
    def __init__(self, settings: QualityAuditSettings):
        self.settings = settings
        self.bq = BigQueryAuditClient(settings)
        self.gx_runner = GxRunner()

    # Function to load the specs from the specified directory.
    def load_specs(self) -> list[dict]:
        specs = []

        # Iterate through all the YAML files in the specified directory.
        for path in sorted(self.settings.specs_dir.glob("*.yml")):
            with path.open("r", encoding="utf-8") as f:
                spec = yaml.safe_load(f) or {} # Load the YAML file as a dictionary.
                spec["_spec_file"] = path.name # Add the file name to the dictionary.
                specs.append(spec)

        # Check if there are any specs.
        if not specs:
            raise RuntimeError(f"No audit specs found in {self.settings.specs_dir}")

        return specs

    # Function to render the SQL query based on the spec.
    def render_sql(self, spec: dict) -> str:
        dataset_name = spec.get("dataset", self.settings.analytics_dataset)
        table_name = spec["table"]

        # Define the default SQL query.
        default_sql = f"""
        SELECT *
        FROM {self.bq.table_ref(dataset_name, table_name)}
        LIMIT {int(spec.get("limit", 1000))}
        """

        return spec.get("sql", default_sql).format(
            project_id=self.settings.project_id,
            analytics_dataset=self.settings.analytics_dataset,
            ml_outputs_dataset=self.settings.ml_outputs_dataset,
        )

    # Function to run the audit for a specific spec.
    def run_spec(self, spec: dict) -> list[dict]:
        dataset_name = spec.get("dataset", self.settings.analytics_dataset)
        table_name = spec["table"]
        full_table_name = f"{self.settings.project_id}.{dataset_name}.{table_name}"
        suite_name = spec.get("suite_name", f"{table_name}_audit")
        severity = spec.get("severity", "critical")

        print(f"[quality-audit] Running spec: {spec['_spec_file']}")
        print(f"[quality-audit] Table: {full_table_name}")

        sql = self.render_sql(spec) # Render the SQL query.
        df = self.bq.read_dataframe(sql) # Read the data from BigQuery.

        # Print the number of rows and columns in the data.
        print(
            f"[quality-audit] Loaded table={full_table_name}, "
            f"rows={len(df)}, columns={len(df.columns)}"
        )

        # Create a new Batch object.
        batch = self.gx_runner.create_batch(df, asset_name=table_name.replace(".", "_"),)

        records = [] # Initialize an empty list to store the records.

        # Check if the row count is specified in the spec.
        row_count = spec.get("row_count", {})
        if row_count:
            records.append(
                self.gx_runner.validate_expectation(
                    batch=batch,
                    project_id=self.settings.project_id,
                    table_name=full_table_name,
                    suite_name=suite_name,
                    expectation=gx.expectations.ExpectTableRowCountToBeBetween(
                        min_value=row_count.get("min"),
                        max_value=row_count.get("max"),
                    ),
                    severity=severity,
                )
            )

        # Check for not null values.
        for column in spec.get("not_null", []):
            if column not in df.columns: # Check if the column exists in the data.
                records.append(
                    self.gx_runner.missing_column_record(
                        project_id=self.settings.project_id,
                        table_name=full_table_name,
                        suite_name=suite_name,
                        column=column,
                        severity=severity,
                    )
                )
                continue
            
            # Validate the expectation.
            records.append(
                self.gx_runner.validate_expectation(
                    batch=batch,
                    project_id=self.settings.project_id,
                    table_name=full_table_name,
                    suite_name=suite_name,
                    expectation=gx.expectations.ExpectColumnValuesToNotBeNull(
                        column=column
                    ),
                    severity=severity,
                )
            )

        # Check for validity of accepted values.
        for check in spec.get("accepted_values", []):
            column = check["column"]
            if column not in df.columns:
                continue

            records.append(
                self.gx_runner.validate_expectation(
                    batch=batch,
                    project_id=self.settings.project_id,
                    table_name=full_table_name,
                    suite_name=suite_name,
                    expectation=gx.expectations.ExpectColumnValuesToBeInSet(
                        column=column,
                        value_set=check["values"],
                    ),
                    severity=severity,
                )
            )

        # Check for validity of ranges.
        for check in spec.get("ranges", []):
            column = check["column"]
            if column not in df.columns:
                continue

            records.append(
                self.gx_runner.validate_expectation(
                    batch=batch,
                    project_id=self.settings.project_id,
                    table_name=full_table_name,
                    suite_name=suite_name,
                    expectation=gx.expectations.ExpectColumnValuesToBeBetween(
                        column=column,
                        min_value=check.get("min"),
                        max_value=check.get("max"),
                    ),
                    severity=severity,
                )
            )

        return records

    def run(self, fail_on_critical: bool) -> int:
        specs = self.load_specs() # Load the specs.

        # Initialize an empty list to store all the records.
        all_records = []
        for spec in specs:
            all_records.extend(self.run_spec(spec))

        # Check if there are any records.
        if not all_records:
            raise RuntimeError("No GE audit records were produced.")

        # Convert the list of records to a DataFrame.
        result_df = pd.DataFrame(all_records)
        self.bq.write_dataframe(result_df, "data_quality_audit_results")

        # Filter the records based on severity and success.
        failed_critical = result_df[
            (result_df["severity"] == "critical")
            & (result_df["success"] == False)
        ]

        failed_warning = result_df[
            (result_df["severity"] == "warning")
            & (result_df["success"] == False)
        ]

        # Print the number of failed critical checks.
        print(f"[quality-audit] Failed critical checks: {len(failed_critical)}")
        print(f"[quality-audit] Failed warning checks: {len(failed_warning)}")

        # Data execution mode options:
        # If True, the system will crash immediately if the data is substandard.
        # If False, the pipeline will continue to run even if the data is substandard, preventing system crashes.
        if fail_on_critical and len(failed_critical) > 0:
            print("[quality-audit] Critical checks failed.")
            return 1

        print("[quality-audit] Completed.")
        return 0
