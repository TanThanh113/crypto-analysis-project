from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from local_feature_engineering_research import (
    DOWN_CLASS,
    build_research_features,
    candidate_specs,
    ensure_local_research_path,
    evaluate_predictions,
    predict_with_down_threshold,
    research_model_config,
    write_outputs,
    BaselineReference,
    FeatureCandidateResult,
)
from train_model import ModelConfig


def _model_config() -> ModelConfig:
    return ModelConfig(
        model_name="crypto_direction_lgbm_v1",
        model_version="v1",
        model_family="crypto_direction",
        algorithm="lightgbm",
        target_name="future_direction_4h",
        split_column="split_name",
        sample_weight_column="sample_weight_4h",
        primary_metric="f1_macro",
        random_state=42,
        valid_classes=["UP", "DOWN", "FLAT"],
        categorical_features=["symbol"],
        numeric_features=[
            "return_1h",
            "return_4h",
            "return_24h",
            "log_return_1h",
            "rolling_volatility_24h",
            "quote_volume",
            "taker_buy_quote_ratio",
            "market_momentum_score",
        ],
    )


def _sample_frame() -> pd.DataFrame:
    hours = pd.date_range("2026-01-01", periods=40, freq="h", tz="UTC")
    rows = []
    for symbol in ["BTC", "ETH"]:
        for idx, hour in enumerate(hours):
            rows.append(
                {
                    "hour_ts": hour,
                    "symbol": symbol,
                    "split_name": "train" if idx < 24 else "validation" if idx < 32 else "test",
                    "is_training_row": True,
                    "sample_weight_4h": 1.0,
                    "future_direction_4h": ["UP", "DOWN", "FLAT"][idx % 3],
                    "return_1h": float(idx),
                    "return_4h": float(idx + 1),
                    "return_24h": float(idx + 2),
                    "log_return_1h": float(idx) / 100.0,
                    "rolling_volatility_24h": float(idx + 3),
                    "quote_volume": float(100 + idx),
                    "taker_buy_quote_ratio": 0.45 + idx / 1000.0,
                    "market_momentum_score": -1.0 if idx % 2 else 1.0,
                }
            )
    return pd.DataFrame(rows)


def _result(name: str) -> FeatureCandidateResult:
    return FeatureCandidateResult(
        candidate_name=name,
        model_type="logistic",
        status="completed",
        selection_score=0.4,
        validation_f1_macro=0.4,
        test_f1_macro=0.35,
        validation_down_recall=0.25,
        test_down_recall=0.2,
        per_class_recall_min=0.2,
        log_loss=1.0,
        brier_score=0.6,
        validation_test_gap=0.05,
        overfit_flag=False,
        artifact_path=None,
        threshold_policy=None,
        reasons=[],
    )


def test_feature_builder_adds_expected_columns_without_future_leak():
    frame, features = build_research_features(_sample_frame(), model_config=_model_config())
    btc = frame[frame["symbol"] == "BTC"].sort_values("hour_ts").reset_index(drop=True)

    assert "return_1h_lag_1h_research" in features
    assert "return_1h_rolling_mean_4h_research" in features
    assert "volatility_regime_high_research" in features
    assert btc.loc[5, "return_1h_lag_1h_research"] == pytest.approx(4.0)
    assert btc.loc[5, "return_1h_rolling_mean_4h_research"] == pytest.approx(2.5)


def test_research_model_config_extends_numeric_features():
    _, features = build_research_features(_sample_frame(), model_config=_model_config())
    config = research_model_config(_model_config(), features)

    assert len(config.numeric_features) > len(_model_config().numeric_features)
    assert "return_1h_lag_1h_research" in config.numeric_features


def test_candidate_specs_include_required_v1_candidates():
    names = [candidate.name for candidate in candidate_specs()]

    assert names == [
        "logistic_research_baseline",
        "logistic_class_weight_balanced",
        "lightgbm_rolling_90d",
        "extratrees_all_history_baseline",
        "xgboost_rolling_90d",
    ]


def test_threshold_helper_can_increase_down_predictions():
    classes = ["UP", "DOWN", "FLAT"]
    proba = np.array(
        [
            [0.40, 0.35, 0.25],
            [0.20, 0.34, 0.46],
            [0.10, 0.55, 0.35],
        ]
    )
    pred = predict_with_down_threshold(proba, classes=classes, down_threshold=0.34)

    assert list(pred).count(DOWN_CLASS) == 3


def test_evaluate_predictions_reports_down_recall():
    y_true = pd.Series(["DOWN", "DOWN", "UP", "FLAT"])
    y_pred = pd.Series(["DOWN", "UP", "UP", "FLAT"])

    metrics = evaluate_predictions(y_true, y_pred, labels=["UP", "DOWN", "FLAT"])

    assert metrics["down_recall"] == pytest.approx(0.5)
    assert metrics["per_class_recall_min"] == pytest.approx(0.5)


def test_artifact_path_must_stay_under_local_research_root(tmp_path):
    with pytest.raises(ValueError, match="Path must stay under"):
        ensure_local_research_path(Path("/tmp/not-local-research"))


def test_write_outputs_records_local_only_payload(tmp_path, monkeypatch):
    import local_feature_engineering_research as module

    monkeypatch.setattr(module, "DEFAULT_LEADERBOARD_PATH", tmp_path / "leaderboard.csv")
    monkeypatch.setattr(module, "DEFAULT_SUMMARY_PATH", tmp_path / "summary.json")
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(module, "DEFAULT_ENGINEERED_PARQUET_PATH", tmp_path / "features.parquet")

    write_outputs(
        artifact_dir=tmp_path,
        results=[_result("candidate")],
        best=_result("candidate"),
        baseline_reference=BaselineReference(0.3, 0.2, 0.1, 0.05),
        feature_signal=pd.DataFrame(
            [{"feature": "return_1h_lag_1h_research", "target_corr": 0.1, "abs_target_corr": 0.1}]
        ),
        engineered_features=["return_1h_lag_1h_research"],
        input_source="local_cache",
        input_cache_path=tmp_path / "cache.parquet",
        dry_run=True,
    )

    summary = (tmp_path / "summary.json").read_text(encoding="utf-8")
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert '"wrote_gcs": false' in summary
    assert '"wrote_bigquery_output": false' in summary
    assert "GCS output written: `false`" in report
