"""Best-effort MLflow experiment logging utilities.

MLflow is optional in this project. Training should continue when
MLFLOW_TRACKING_URI is unset, and MLflow failures are swallowed unless
MLFLOW_FAIL_ON_ERROR is explicitly true. This module only logs experiment
metadata/artifacts; it does not decide model promotion or production serving.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


TRUE_VALUES = {"1", "true", "yes", "y", "on"}

# Contains the configuration settings for MLflow.
@dataclass(frozen=True)
class MLflowSettings:
    enabled: bool
    tracking_uri: str | None
    experiment_name: str
    artifact_root: str | None
    fail_on_error: bool

# Get the environment variables as an integer.
def get_mlflow_settings(env: Mapping[str, str] | None = None) -> MLflowSettings:
    """Read optional MLflow settings from env-like mappings.

    MLflow is considered enabled only when MLFLOW_TRACKING_URI is present.
    """
    source = os.environ if env is None else env
    tracking_uri = source.get("MLFLOW_TRACKING_URI")
    fail_on_error = source.get("MLFLOW_FAIL_ON_ERROR", "").strip().lower() in TRUE_VALUES

    return MLflowSettings(
        enabled=bool(tracking_uri),
        tracking_uri=tracking_uri,
        experiment_name=source.get("MLFLOW_EXPERIMENT_NAME", "crypto_direction_4h"),
        artifact_root=source.get("MLFLOW_ARTIFACT_ROOT"),
        fail_on_error=fail_on_error,
    )

# Check if MLflow is enabled.
def is_mlflow_enabled(env: Mapping[str, str] | None = None) -> bool:
    return get_mlflow_settings(env).enabled

# Handle the MLflow error.
def handle_mlflow_error(message: str, exc: Exception, settings: MLflowSettings | None = None) -> None:
    active_settings = settings or get_mlflow_settings()

    if active_settings.fail_on_error:
        raise exc

    print(f"[mlflow][WARN] {message}: {exc}", file=sys.stderr)

# The function to filter special characters of Key (sanitize_key)
def _sanitize_key(key: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.\-/ ]+", "_", str(key)).strip()
    return sanitized or "value"

# The function to filter special characters of Value (clean_value)
def _clean_value(value: Any) -> str | int | float | bool:
    if value is None:
        return ""

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)

# The function to filter special characters of Mapping (clean_mapping)
# Gather the two upper jaws together to straighten and clear a lump of Dictionary tags or params.
def _clean_mapping(values: Mapping[str, Any] | None) -> dict[str, str | int | float | bool]:
    if not values:
        return {}

    return {
        _sanitize_key(key): _clean_value(value)
        for key, value in values.items()
        if value is not None
    }

# The function to filter special characters of Numeric Metrics (numeric_metrics)
def _numeric_metrics(values: Mapping[str, Any] | None) -> dict[str, float]:
    if not values:
        return {}

    metrics: dict[str, float] = {}
    for key, value in values.items():
        if value is None or isinstance(value, bool): # Filter out None and bool values.
            continue

        try:
            metric_value = float(value) # Convert the value to a float.
        except (TypeError, ValueError):
            continue

        if metric_value != metric_value:
            continue # Filter out NaN and Infinity values.

        metrics[_sanitize_key(key)] = metric_value

    return metrics

# The function to create an experiment ID on the UI interface
def _get_or_create_experiment_id(mlflow: Any, settings: MLflowSettings) -> str:
    experiment = mlflow.get_experiment_by_name(settings.experiment_name)
    if experiment is not None:
        return experiment.experiment_id

    if settings.artifact_root:
        return mlflow.create_experiment(
            settings.experiment_name,
            artifact_location=settings.artifact_root,
        )

    return mlflow.create_experiment(settings.experiment_name)

# The function to log the training run
def log_training_run(
    *,
    run_name: str,
    params: Mapping[str, Any] | None = None,
    metrics: Mapping[str, Any] | None = None,
    tags: Mapping[str, Any] | None = None,
    artifact_paths: Sequence[str | Path] | None = None,
    settings: MLflowSettings | None = None,
) -> bool:
    """Log one training run to MLflow when optional logging is enabled.

    Returns True when a run is logged and False when MLflow is disabled or a
    best-effort logging error is swallowed. Artifact paths are logged only when
    they point to files.
    """
    active_settings = settings or get_mlflow_settings()
    if not active_settings.enabled:
        return False

    try:
        import mlflow

        mlflow.set_tracking_uri(active_settings.tracking_uri)
        experiment_id = _get_or_create_experiment_id(mlflow, active_settings)

        with mlflow.start_run(experiment_id=experiment_id, run_name=run_name):
            # 1. Push the quick sorting tags after cleaning.
            cleaned_tags = _clean_mapping(tags)
            if cleaned_tags:
                mlflow.set_tags(cleaned_tags)
            # 2. Input Configuration (Parameters) Submission Loop
            for key, value in _clean_mapping(params).items():
                mlflow.log_param(key, value)
            # 3. Pure Real Score (Metrics) Submission Loop
            for key, value in _numeric_metrics(metrics).items():
                mlflow.log_metric(key, value)
            # 4. Loop to attach hard files (.json, .joblib, .yml)
            for artifact_path in artifact_paths or []:
                path = Path(artifact_path)
                if path.is_file():
                    mlflow.log_artifact(str(path))

        return True

    except Exception as exc:
        handle_mlflow_error("MLflow logging skipped", exc, active_settings)
        return False
