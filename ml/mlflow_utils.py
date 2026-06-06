from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class MLflowSettings:
    enabled: bool
    tracking_uri: str | None
    experiment_name: str
    artifact_root: str | None
    fail_on_error: bool


def get_mlflow_settings(env: Mapping[str, str] | None = None) -> MLflowSettings:
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


def is_mlflow_enabled(env: Mapping[str, str] | None = None) -> bool:
    return get_mlflow_settings(env).enabled


def handle_mlflow_error(message: str, exc: Exception, settings: MLflowSettings | None = None) -> None:
    active_settings = settings or get_mlflow_settings()

    if active_settings.fail_on_error:
        raise exc

    print(f"[mlflow][WARN] {message}: {exc}", file=sys.stderr)


def _sanitize_key(key: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.\-/ ]+", "_", str(key)).strip()
    return sanitized or "value"


def _clean_value(value: Any) -> str | int | float | bool:
    if value is None:
        return ""

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def _clean_mapping(values: Mapping[str, Any] | None) -> dict[str, str | int | float | bool]:
    if not values:
        return {}

    return {
        _sanitize_key(key): _clean_value(value)
        for key, value in values.items()
        if value is not None
    }


def _numeric_metrics(values: Mapping[str, Any] | None) -> dict[str, float]:
    if not values:
        return {}

    metrics: dict[str, float] = {}
    for key, value in values.items():
        if value is None or isinstance(value, bool):
            continue

        try:
            metric_value = float(value)
        except (TypeError, ValueError):
            continue

        if metric_value != metric_value:
            continue

        metrics[_sanitize_key(key)] = metric_value

    return metrics


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


def log_training_run(
    *,
    run_name: str,
    params: Mapping[str, Any] | None = None,
    metrics: Mapping[str, Any] | None = None,
    tags: Mapping[str, Any] | None = None,
    artifact_paths: Sequence[str | Path] | None = None,
    settings: MLflowSettings | None = None,
) -> bool:
    active_settings = settings or get_mlflow_settings()
    if not active_settings.enabled:
        return False

    try:
        import mlflow

        mlflow.set_tracking_uri(active_settings.tracking_uri)
        experiment_id = _get_or_create_experiment_id(mlflow, active_settings)

        with mlflow.start_run(experiment_id=experiment_id, run_name=run_name):
            cleaned_tags = _clean_mapping(tags)
            if cleaned_tags:
                mlflow.set_tags(cleaned_tags)

            for key, value in _clean_mapping(params).items():
                mlflow.log_param(key, value)

            for key, value in _numeric_metrics(metrics).items():
                mlflow.log_metric(key, value)

            for artifact_path in artifact_paths or []:
                path = Path(artifact_path)
                if path.is_file():
                    mlflow.log_artifact(str(path))

        return True

    except Exception as exc:
        handle_mlflow_error("MLflow logging skipped", exc, active_settings)
        return False
