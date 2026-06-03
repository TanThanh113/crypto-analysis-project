from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MonitoringSettings:
    project_id: str
    analytics_dataset: str
    ml_outputs_dataset: str
    location: str
    specs_dir: Path


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    raise RuntimeError(f"Missing required environment variable: {name}")


def load_settings() -> MonitoringSettings:
    package_dir = Path(__file__).resolve().parent

    return MonitoringSettings(
        project_id=required_env("GCP_PROJECT_ID"),
        analytics_dataset=os.environ.get("BQ_ANALYTICS_DATASET", "dbt_quants_dev"),
        ml_outputs_dataset=os.environ.get("BQ_ML_OUTPUTS_DATASET", "ml_outputs"),
        location=os.environ.get("BQ_LOCATION", "asia-southeast1"),
        specs_dir=package_dir / "specs",
    )
