# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Create a new dataclass to store the settings.
@dataclass(frozen=True)
# frozen = true: no one can edit it once it has been added.
class QualityAuditSettings:
    project_id: str  # GCP project ID
    analytics_dataset: str  # BigQuery dataset for analytics
    ml_outputs_dataset: str  # BigQuery dataset for ML outputs
    location: str  # GCP location for BigQuery
    specs_dir: Path  # Directory containing specs

# Function that returns an object of type class QualityAuditSettings.
def load_settings() -> QualityAuditSettings:
    # Get the absolute path to the folder containing this file.
    package_dir = Path(__file__).resolve().parent

    return QualityAuditSettings(
        project_id=os.environ.get("GCP_PROJECT_ID", "project-lambda-crypto"),
        analytics_dataset=os.environ.get("BQ_ANALYTICS_DATASET", "dbt_quants_dev"),
        ml_outputs_dataset=os.environ.get("BQ_ML_OUTPUTS_DATASET", "ml_outputs"),
        location=os.environ.get("BQ_LOCATION", "asia-southeast1"),
        specs_dir=package_dir / "specs",
    )
