# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

# Import the Great Expectations library
# A standard tool in the data industry for checking whether data meets quality standards.
import great_expectations as gx
import pandas as pd

# Function to get the current UTC time.
def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# Create a new dataclass to run Great Expectations.
class GxRunner:
    # Wrap that table in an entity called a Batch.
    def create_batch(self, df: pd.DataFrame, asset_name: str):
        context = gx.get_context(mode="ephemeral") #(temporary workspace)

        # Create a new Batch object.
        data_source = context.data_sources.add_pandas(name=f"{asset_name}_source")
        data_asset = data_source.add_dataframe_asset(name=f"{asset_name}_asset")
        batch_definition = data_asset.add_batch_definition_whole_dataframe(f"{asset_name}_batch")

        return batch_definition.get_batch(
            batch_parameters={"dataframe": df}
        )

    # Convert the result to a dictionary.
    def to_dict(self, result: Any) -> dict[str, Any]:
        if hasattr(result, "to_json_dict"):
            return result.to_json_dict()

        if hasattr(result, "dict"):
            return result.dict()

        return json.loads(json.dumps(result, default=str))

    def validate_expectation(
        self,
        *,
        batch,
        project_id: str,
        table_name: str,
        suite_name: str,
        expectation,
        severity: str,
    ) -> dict[str, Any]:
        result = batch.validate(expectation) # Check the expectation.
        payload = self.to_dict(result) # Convert the result to a dictionary.

        # Get the name of the type of inspection law
        expectation_type = payload.get("expectation_config", {}).get("type")
        if not expectation_type:
            expectation_type = expectation.__class__.__name__

        # Package the returned results according to the correct structure (Schema) of the BigQuery table.
        return {
            "audit_ts": utc_now(),
            "project_id": project_id,
            "table_name": table_name,
            "suite_name": suite_name,
            "expectation_type": expectation_type,
            "success": bool(payload.get("success", False)), # True if successful, False if incorrect
            "severity": severity, # Severity Level (WARNING/CRITICAL)
            "result_json": json.dumps(payload.get("result", {}), default=str), # Error Details
            "expectation_json": json.dumps(
                payload.get("expectation_config", {}),
                default=str,
            ), # Details of the law
        }

    # Function to handle missing column errors
    def missing_column_record(
        self,
        *,
        project_id: str,
        table_name: str,
        suite_name: str,
        column: str,
        severity: str,
    ) -> dict[str, Any]:
        return {
            "audit_ts": utc_now(),
            "project_id": project_id,
            "table_name": table_name,
            "suite_name": suite_name,
            "expectation_type": "column_exists",
            "success": False,
            "severity": severity,
            "result_json": json.dumps({"missing_column": column}),
            "expectation_json": json.dumps({"column": column}),
        }
