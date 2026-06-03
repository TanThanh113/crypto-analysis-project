# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

import os
from dataclasses import dataclass

# Create a new dataclass to store the settings.
@dataclass(frozen=True)
class AlertSettings:
    project_id: str
    ml_outputs_dataset: str
    location: str
    slack_webhook_url: str

# This function takes a file path as input, opens that file, and reads its contents.
def _read_secret_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

def required_env(name: str) -> str:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    raise RuntimeError(f"Missing required environment variable: {name}")

# Function that returns an object of type class AlertSettings.
def load_settings() -> AlertSettings:
    # Get the webhook URL from secret.
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()

    # If the webhook URL is not set, try to read it from a file.
    secret_file = os.environ.get("SLACK_WEBHOOK_URL_FILE", "/var/secrets/SLACK_WEBHOOK_URL")
    if not webhook_url and os.path.exists(secret_file):
        webhook_url = _read_secret_file(secret_file)
    
    # Return the AlertSettings object.
    return AlertSettings(
        project_id=required_env("GCP_PROJECT_ID"),
        ml_outputs_dataset=os.environ.get("BQ_ML_OUTPUTS_DATASET", "ml_outputs"),
        location=os.environ.get("BQ_LOCATION", "asia-southeast1"),
        slack_webhook_url=webhook_url,
    )
