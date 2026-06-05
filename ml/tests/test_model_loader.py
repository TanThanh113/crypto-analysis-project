from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from model_loader import build_registry_model_uri, load_model_with_fallback


ML_ROOT = Path(__file__).resolve().parents[1]


def _artifact_bundle() -> dict[str, Any]:
    return {
        "model": object(),
        "model_name": "crypto_direction_lgbm_v1",
        "model_version": "v1",
        "target_name": "future_direction_4h",
        "features": ["feature_a", "feature_b"],
        "artifact_path": "/tmp/local-model.joblib",
    }


def _loader_args(**overrides: Any) -> dict[str, Any]:
    args = {
        "model_source": "artifact",
        "artifact_loader": _artifact_bundle,
        "mlflow_model_uri": None,
        "registered_model_name": None,
        "model_alias": "champion",
        "tracking_uri": None,
        "fallback_to_artifact": True,
        "strict": False,
        "features": ["feature_a", "feature_b"],
        "model_name": "crypto_direction_lgbm_v1",
        "model_version": "v1",
        "target_name": "future_direction_4h",
        "valid_classes": ["UP", "DOWN", "FLAT"],
    }
    args.update(overrides)
    return args


def _dummy_sklearn_model() -> LogisticRegression:
    x = pd.DataFrame(
        {
            "feature_a": [0.0, 0.1, 0.2, 1.0, 1.1, 1.2, 2.0, 2.1, 2.2],
            "feature_b": [0.0, 0.2, 0.1, 1.0, 1.2, 1.1, 2.0, 2.2, 2.1],
        }
    )
    y = ["DOWN", "DOWN", "DOWN", "FLAT", "FLAT", "FLAT", "UP", "UP", "UP"]
    return LogisticRegression(max_iter=500).fit(x, y)


def _register_dummy_model(tmp_path: Path) -> tuple[str, str]:
    import mlflow
    import mlflow.sklearn
    from mlflow.exceptions import MlflowException
    from mlflow.tracking import MlflowClient

    tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    artifact_root = tmp_path / "artifacts"
    experiment_name = "phase_6_model_loader_test"
    registered_model_name = "phase_6_predict_model"

    mlflow.set_tracking_uri(tracking_uri)
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(
            experiment_name,
            artifact_location=artifact_root.as_uri(),
        )
    else:
        experiment_id = experiment.experiment_id

    with mlflow.start_run(experiment_id=experiment_id, run_name="registry-loader") as run:
        try:
            model_info = mlflow.sklearn.log_model(_dummy_sklearn_model(), name="model")
        except TypeError:
            model_info = mlflow.sklearn.log_model(
                _dummy_sklearn_model(),
                artifact_path="model",
            )
        run_id = run.info.run_id

    model_uri = getattr(model_info, "model_uri", None) or f"runs:/{run_id}/model"
    client = MlflowClient(tracking_uri=tracking_uri)
    try:
        client.create_registered_model(registered_model_name)
    except MlflowException as exc:
        if "already exists" not in str(exc).lower():
            raise

    model_version = mlflow.register_model(model_uri, registered_model_name)
    client.set_registered_model_alias(
        registered_model_name,
        "champion",
        model_version.version,
    )

    return tracking_uri, registered_model_name


def test_build_registry_model_uri_explicit_uri_wins():
    assert (
        build_registry_model_uri(
            mlflow_model_uri="models:/explicit@champion",
            registered_model_name="ignored",
            model_alias="candidate",
        )
        == "models:/explicit@champion"
    )


def test_default_artifact_source_uses_artifact_loader():
    result = load_model_with_fallback(**_loader_args())

    assert result.source == "artifact"
    assert result.fallback_used is False
    assert result.bundle["model_source"] == "artifact"
    assert result.model_uri == "/tmp/local-model.joblib"


def test_auto_missing_registry_config_falls_back_to_artifact():
    result = load_model_with_fallback(
        **_loader_args(
            model_source="auto",
            tracking_uri=None,
            registered_model_name=None,
        )
    )

    assert result.source == "artifact"
    assert result.fallback_used is False
    assert "not configured" in result.reasons[0]


def test_registry_enabled_loads_local_sqlite_alias(tmp_path):
    tracking_uri, registered_model_name = _register_dummy_model(tmp_path)

    result = load_model_with_fallback(
        **_loader_args(
            model_source="registry",
            tracking_uri=tracking_uri,
            registered_model_name=registered_model_name,
        )
    )

    assert result.source == "registry"
    assert result.fallback_used is False
    assert result.model_uri == f"models:/{registered_model_name}@champion"
    assert result.bundle["model_source"] == "registry"
    assert result.bundle["registered_model_name"] == registered_model_name
    assert result.bundle["model_alias"] == "champion"
    assert hasattr(result.bundle["model"], "predict_proba")


def test_registry_load_failure_falls_back_to_artifact(tmp_path):
    result = load_model_with_fallback(
        **_loader_args(
            model_source="registry",
            tracking_uri=f"sqlite:///{tmp_path / 'missing.db'}",
            registered_model_name="missing_model",
            fallback_to_artifact=True,
            strict=False,
        )
    )

    assert result.source == "artifact"
    assert result.fallback_used is True
    assert result.bundle["model_source"] == "artifact"
    assert "registry model load failed" in result.reasons[0]
    assert "falling back" in result.reasons[1]


def test_registry_strict_failure_raises(tmp_path):
    with pytest.raises(RuntimeError, match="registry model load failed"):
        load_model_with_fallback(
            **_loader_args(
                model_source="registry",
                tracking_uri=f"sqlite:///{tmp_path / 'strict.db'}",
                registered_model_name="missing_model",
                fallback_to_artifact=True,
                strict=True,
            )
        )


def test_predict_latest_help_lists_model_source_flags():
    result = subprocess.run(
        [sys.executable, str(ML_ROOT / "predict_latest.py"), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    help_text = result.stdout
    assert "--model-source" in help_text
    assert "--mlflow-model-uri" in help_text
    assert "--mlflow-registered-model-name" in help_text
    assert "--mlflow-model-alias" in help_text
    assert "--registry-fallback-to-artifact" in help_text
    assert "--registry-strict" in help_text
