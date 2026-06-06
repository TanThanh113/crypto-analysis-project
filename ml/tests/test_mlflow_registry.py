from __future__ import annotations

import pytest
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression

from mlflow_registry import register_model_if_enabled
from promotion_gate import PromotionGateResult


def _accepted_promotion() -> PromotionGateResult:
    return PromotionGateResult(
        passed=True,
        status="accepted",
        reasons=["accepted"],
        candidate_score=0.70,
        champion_score=0.60,
        margin=0.01,
        checked_at="2026-01-01T00:00:00+00:00",
    )


def _rejected_promotion() -> PromotionGateResult:
    return PromotionGateResult(
        passed=False,
        status="rejected",
        reasons=["rejected"],
        candidate_score=0.50,
        champion_score=0.60,
        margin=0.01,
        checked_at="2026-01-01T00:00:00+00:00",
    )


def _dummy_model():
    x, y = make_classification(
        n_samples=40,
        n_features=4,
        n_informative=3,
        n_redundant=0,
        random_state=42,
    )
    return LogisticRegression(max_iter=500).fit(x, y)


def test_registry_disabled_does_not_crash(monkeypatch):
    monkeypatch.delenv("MLFLOW_ENABLE_MODEL_REGISTRY", raising=False)

    result = register_model_if_enabled(
        model=None,
        run_name="disabled",
        default_registered_model_name="disabled_model",
        promotion_result=_accepted_promotion(),
    )

    assert result.status == "disabled"
    assert result.reasons == ["MLFLOW_ENABLE_MODEL_REGISTRY is not true"]


def test_registry_enabled_without_tracking_uri_skips(monkeypatch):
    monkeypatch.setenv("MLFLOW_ENABLE_MODEL_REGISTRY", "true")
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)

    result = register_model_if_enabled(
        model=None,
        run_name="missing-tracking",
        default_registered_model_name="missing_tracking_model",
        promotion_result=_accepted_promotion(),
    )

    assert result.status == "skipped"
    assert "MLFLOW_TRACKING_URI is required" in result.reasons[0]


def test_registry_enabled_and_promotion_accepted_registers_version_and_alias(monkeypatch, tmp_path):
    tracking_db = tmp_path / "mlflow.db"
    artifact_root = tmp_path / "artifacts"

    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tracking_db}")
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "phase_4_registry_test")
    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", artifact_root.as_uri())
    monkeypatch.setenv("MLFLOW_ENABLE_MODEL_REGISTRY", "true")
    monkeypatch.setenv("MLFLOW_UPDATE_MODEL_ALIAS", "true")
    monkeypatch.setenv("MLFLOW_REGISTERED_MODEL_NAME", "phase_4_test_model")
    monkeypatch.setenv("MLFLOW_MODEL_ALIAS", "champion")

    result = register_model_if_enabled(
        model=_dummy_model(),
        run_name="accepted",
        default_registered_model_name="fallback_model",
        promotion_result=_accepted_promotion(),
        tags={
            "strategy_name": "lightgbm_rolling_90d",
            "model_choice": "lightgbm",
            "model_name": "crypto_direction_lgbm_v1",
            "model_version": "v1",
            "promotion_status": "accepted",
            "promotion_passed": True,
            "validation_f1_macro": 0.70,
            "created_by": "crypto-analysis-project",
            "phase": "mlflow_mlops_upgrade",
        },
    )

    assert result.status == "registered"
    assert result.registered_model_name == "phase_4_test_model"
    assert result.model_version is not None
    assert result.model_alias == "champion"
    assert result.model_uri is not None

    from mlflow.tracking import MlflowClient

    client = MlflowClient(tracking_uri=f"sqlite:///{tracking_db}")
    model_version = client.get_model_version_by_alias("phase_4_test_model", "champion")

    assert str(model_version.version) == result.model_version
    assert model_version.tags["strategy_name"] == "lightgbm_rolling_90d"
    assert model_version.tags["promotion_status"] == "accepted"
    assert model_version.tags["promotion_passed"] == "true"


def test_registry_promotion_rejected_skips_alias_update(monkeypatch, tmp_path):
    tracking_db = tmp_path / "mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tracking_db}")
    monkeypatch.setenv("MLFLOW_ENABLE_MODEL_REGISTRY", "true")
    monkeypatch.setenv("MLFLOW_UPDATE_MODEL_ALIAS", "true")

    result = register_model_if_enabled(
        model=None,
        run_name="rejected",
        default_registered_model_name="rejected_model",
        promotion_result=_rejected_promotion(),
    )

    assert result.status == "skipped"
    assert "promotion gate is not accepted" in result.reasons[0]


def test_registry_error_best_effort_and_strict(monkeypatch, tmp_path):
    tracking_db = tmp_path / "mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tracking_db}")
    monkeypatch.setenv("MLFLOW_ENABLE_MODEL_REGISTRY", "true")

    import mlflow.sklearn

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(mlflow.sklearn, "log_model", raise_error)

    monkeypatch.setenv("MLFLOW_REGISTRY_FAIL_ON_ERROR", "false")
    result = register_model_if_enabled(
        model=_dummy_model(),
        run_name="best-effort-error",
        default_registered_model_name="error_model",
        promotion_result=_accepted_promotion(),
    )
    assert result.status == "error"
    assert "boom" in result.reasons[0]

    monkeypatch.setenv("MLFLOW_REGISTRY_FAIL_ON_ERROR", "true")
    with pytest.raises(RuntimeError, match="boom"):
        register_model_if_enabled(
            model=_dummy_model(),
            run_name="strict-error",
            default_registered_model_name="error_model",
            promotion_result=_accepted_promotion(),
        )
