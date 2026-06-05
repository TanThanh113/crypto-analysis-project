from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml
from lightgbm import LGBMClassifier
from sklearn.datasets import make_classification
from sklearn.pipeline import Pipeline

import optuna_tuning
from optuna_tuning import (
    OptunaTuningSettings,
    get_optuna_settings,
    lightgbm_search_space,
    tune_lightgbm_pipeline,
)
from train_model import (
    BigQueryConfig,
    ModelConfig,
    collect_optuna_results,
    log_optional_mlflow_training_run,
    save_optuna_summary_artifact,
)


ML_ROOT = Path(__file__).resolve().parents[1]


def _tiny_dataset() -> tuple[pd.DataFrame, pd.Series]:
    x, y = make_classification(
        n_samples=54,
        n_features=4,
        n_informative=3,
        n_redundant=0,
        n_classes=3,
        random_state=42,
    )
    labels = pd.Series(y).map({0: "DOWN", 1: "FLAT", 2: "UP"})
    frame = pd.DataFrame(x, columns=["feature_a", "feature_b", "feature_c", "feature_d"])
    return frame, labels


def _tiny_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "model",
                LGBMClassifier(
                    objective="multiclass",
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=1,
                    verbosity=-1,
                ),
            )
        ]
    )


def _settings(**overrides: Any) -> OptunaTuningSettings:
    values = {
        "enabled": True,
        "n_trials": 2,
        "timeout_seconds": None,
        "study_name": None,
        "storage_uri": None,
        "direction": "maximize",
        "metric_name": "f1_macro",
        "strategy_name": None,
        "fail_on_error": False,
    }
    values.update(overrides)
    return OptunaTuningSettings(**values)


def test_optuna_disabled_settings_from_empty_env():
    settings = get_optuna_settings(env={})

    assert settings.enabled is False
    assert settings.n_trials == 20
    assert settings.metric_name == "f1_macro"
    assert settings.direction == "maximize"


def test_lightgbm_search_space_returns_expected_params():
    import optuna

    study = optuna.create_study(direction="maximize")
    trial = study.ask()

    params = lightgbm_search_space(trial)

    assert set(params) == {
        "num_leaves",
        "max_depth",
        "learning_rate",
        "n_estimators",
        "min_child_samples",
        "subsample",
        "colsample_bytree",
        "reg_alpha",
        "reg_lambda",
    }
    assert 15 <= params["num_leaves"] <= 63
    assert 0.01 <= params["learning_rate"] <= 0.08


def test_tiny_synthetic_dataset_runs_two_trials():
    x, y = _tiny_dataset()
    x_train, y_train = x.iloc[:36], y.iloc[:36]
    x_val, y_val = x.iloc[36:], y.iloc[36:]

    result = tune_lightgbm_pipeline(
        model_key="lightgbm_rolling_90d",
        base_model_key="lightgbm_classifier",
        model=_tiny_pipeline(),
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
        sample_weight=None,
        settings=_settings(n_trials=2),
        random_state=42,
    )

    assert result.enabled is True
    assert result.n_trials == 2
    assert result.best_trial_number is not None
    assert result.best_value is not None
    assert result.best_params


def test_optuna_error_is_swallowed_when_not_strict(monkeypatch):
    def raise_error(_trial: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(optuna_tuning, "lightgbm_search_space", raise_error)
    x, y = _tiny_dataset()

    result = tune_lightgbm_pipeline(
        model_key="lightgbm_classifier",
        base_model_key="lightgbm_classifier",
        model=_tiny_pipeline(),
        x_train=x.iloc[:36],
        y_train=y.iloc[:36],
        x_val=x.iloc[36:],
        y_val=y.iloc[36:],
        sample_weight=None,
        settings=_settings(n_trials=1, fail_on_error=False),
        random_state=42,
    )

    assert result.enabled is True
    assert result.best_params == {}
    assert "Optuna tuning failed" in result.reasons[0]


def test_optuna_error_raises_when_strict(monkeypatch):
    def raise_error(_trial: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(optuna_tuning, "lightgbm_search_space", raise_error)
    x, y = _tiny_dataset()

    with pytest.raises(RuntimeError, match="boom"):
        tune_lightgbm_pipeline(
            model_key="lightgbm_classifier",
            base_model_key="lightgbm_classifier",
            model=_tiny_pipeline(),
            x_train=x.iloc[:36],
            y_train=y.iloc[:36],
            x_val=x.iloc[36:],
            y_val=y.iloc[36:],
            sample_weight=None,
            settings=_settings(n_trials=1, fail_on_error=True),
            random_state=42,
        )


def test_train_help_lists_optuna_flags():
    result = subprocess.run(
        [sys.executable, str(ML_ROOT / "train_model.py"), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    help_text = result.stdout
    assert "--enable-optuna" in help_text
    assert "--optuna-n-trials" in help_text
    assert "--optuna-study-name" in help_text
    assert "--optuna-storage-uri" in help_text
    assert "--optuna-fail-on-error" in help_text


def test_collect_and_save_optuna_summary(tmp_path):
    results = {
        "lightgbm_rolling_90d": {
            "optuna": {
                "enabled": True,
                "study_name": "study",
                "best_params": {"num_leaves": 31},
                "best_value": 0.5,
                "best_trial_number": 0,
                "n_trials": 2,
                "timeout": None,
                "metric_name": "f1_macro",
                "reasons": ["done"],
            }
        }
    }

    assert collect_optuna_results(results)["lightgbm_rolling_90d"]["best_value"] == 0.5

    path = save_optuna_summary_artifact(
        artifact_dir=tmp_path,
        run_id="run-1",
        results=results,
        best_model_key="lightgbm_rolling_90d",
    )

    assert path is not None
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload["optuna"]["lightgbm_rolling_90d"]["best_params"]["num_leaves"] == 31


def test_mlflow_logging_includes_optuna_summary(monkeypatch, tmp_path):
    tracking_db = tmp_path / "mlflow.db"
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tracking_db}")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "phase_7_optuna_logging")
    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", artifact_root.as_uri())

    config_path = tmp_path / "feature_list.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "model": {
                    "model_name": "crypto_direction_lgbm_v1",
                    "model_version": "v1",
                    "target_name": "future_direction_4h",
                    "categorical_features": ["symbol"],
                    "numeric_features": ["feature_a"],
                }
            }
        ),
        encoding="utf-8",
    )

    artifact_path = tmp_path / "model.joblib"
    artifact_path.write_text("model", encoding="utf-8")
    manifest_path = tmp_path / "latest_model.json"
    manifest_path.write_text("{}", encoding="utf-8")

    optuna_payload = {
        "enabled": True,
        "study_name": "phase_7_study",
        "best_params": {"num_leaves": 31, "learning_rate": 0.03},
        "best_value": 0.61,
        "best_trial_number": 1,
        "n_trials": 2,
        "timeout": None,
        "metric_name": "f1_macro",
        "reasons": ["Optuna tuning completed."],
    }
    results = {
        "lightgbm_rolling_90d": {
            "artifact_path": artifact_path,
            "model_artifact_uri": str(artifact_path),
            "metrics": {
                "validation": {"f1_macro": 0.61, "row_count": 3},
                "test": {"f1_macro": 0.59, "row_count": 3},
            },
            "strategy_metadata": {
                "strategy_name": "lightgbm_rolling_90d",
                "model_choice": "lightgbm",
            },
            "optuna": optuna_payload,
        }
    }
    optuna_summary_path = save_optuna_summary_artifact(
        artifact_dir=tmp_path,
        run_id="run-1",
        results=results,
        best_model_key="lightgbm_rolling_90d",
    )

    args = argparse.Namespace(
        model_choice="auto",
        strategy="lightgbm_rolling_90d",
        strategy_matrix=False,
        git_sha="abc123",
        enable_optuna=True,
        optuna_n_trials=2,
        optuna_timeout_seconds=None,
        optuna_metric="f1_macro",
        optuna_direction="maximize",
        optuna_strategy=None,
    )
    bq_config = BigQueryConfig(
        project_id="project",
        analytics_dataset="analytics",
        ml_outputs_dataset="ml_outputs",
        training_table="training",
        metrics_table="metrics",
    )
    model_config = ModelConfig(
        model_name="crypto_direction_lgbm_v1",
        model_version="v1",
        model_family="crypto_direction",
        algorithm="lightgbm",
        target_name="future_direction_4h",
        split_column="split_name",
        sample_weight_column="sample_weight",
        primary_metric="f1_macro",
        random_state=42,
        valid_classes=["UP", "DOWN", "FLAT"],
        categorical_features=["symbol"],
        numeric_features=["feature_a"],
    )
    df = pd.DataFrame(
        {
            "split_name": ["train", "validation", "test"],
            "hour_ts": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03"],
                utc=True,
            ),
            "future_direction_4h": ["UP", "DOWN", "FLAT"],
            "symbol": ["BTC", "BTC", "ETH"],
            "feature_a": [1.0, 2.0, 3.0],
        }
    )

    log_optional_mlflow_training_run(
        config_path=config_path,
        artifact_dir=tmp_path,
        args=args,
        bq_config=bq_config,
        model_config=model_config,
        df=df,
        results=results,
        run_id="run-1",
        best_model_key="lightgbm_rolling_90d",
        best_artifact_uri=str(artifact_path),
        manifest_path=manifest_path,
        optuna_summary_path=optuna_summary_path,
    )

    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(f"sqlite:///{tracking_db}")
    experiment = mlflow.get_experiment_by_name("phase_7_optuna_logging")
    assert experiment is not None

    client = MlflowClient(tracking_uri=f"sqlite:///{tracking_db}")
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 1

    run = runs[0]
    assert run.data.tags["optuna_enabled"] == "true"
    assert run.data.params["optuna_best_num_leaves"] == "31"
    assert run.data.metrics["optuna_best_value"] == 0.61

    artifact_names = {item.path for item in client.list_artifacts(run.info.run_id)}
    assert optuna_summary_path.name in artifact_names
