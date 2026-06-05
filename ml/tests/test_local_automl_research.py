from __future__ import annotations

import argparse

import pandas as pd
import pytest

from local_automl_research import (
    CandidateResult,
    ResearchCandidate,
    choose_best,
    candidate_specs,
    leaderboard_frame,
    make_walk_forward_folds,
    select_candidates,
    validate_local_only_args,
    write_report,
)
from train_model import BigQueryConfig, ModelConfig


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
        numeric_features=["feature_a"],
    )


def _sample_frame() -> pd.DataFrame:
    hours = pd.date_range("2026-01-01", periods=36, freq="h", tz="UTC")
    split_name = ["train"] * 18 + ["validation"] * 10 + ["test"] * 8
    labels = ["UP", "DOWN", "FLAT"] * 12
    return pd.DataFrame(
        {
            "hour_ts": hours,
            "split_name": split_name,
            "symbol": ["BTC", "ETH"] * 18,
            "feature_a": list(range(36)),
            "future_direction_4h": labels,
            "sample_weight_4h": [1.0] * 36,
        }
    )


def _result(name: str, selection: float, test: float) -> CandidateResult:
    return CandidateResult(
        candidate_name=name,
        model_type="test",
        status="completed",
        selection_score=selection,
        validation_f1_macro=selection,
        test_f1_macro=test,
        validation_test_gap=selection - test,
        log_loss=1.0,
        brier_score=0.5,
        per_class_recall_min=0.2,
        walk_forward_f1_macro_mean=selection,
        walk_forward_f1_macro_std=0.01,
        overfit_flag=False,
        artifact_path=None,
        reasons=[],
        optuna_best_params={},
    )


def test_candidate_specs_include_smoke_candidates_first():
    names = [candidate.name for candidate in select_candidates(4)]

    assert names == [
        "logistic_baseline_all_history",
        "lightgbm_rolling_90d",
        "xgboost_rolling_90d",
        "extratrees_all_history_baseline",
    ]
    assert "hist_gradient_boosting_all_history" in [
        candidate.name for candidate in candidate_specs()
    ]


def test_validate_local_only_args_rejects_non_local_storage():
    with pytest.raises(ValueError, match="only supports --artifact-storage local"):
        validate_local_only_args(
            argparse.Namespace(
                artifact_storage="gcs",
                optuna_n_trials=2,
                walk_forward_folds=2,
            )
        )


def test_walk_forward_folds_do_not_leak_time():
    folds = make_walk_forward_folds(
        _sample_frame(),
        model_config=_model_config(),
        n_folds=2,
        train_window_days=None,
    )

    assert len(folds) == 2
    for fold in folds:
        assert pd.Timestamp(fold.train_end) < pd.Timestamp(fold.validation_start)


def test_choose_best_uses_selection_not_test_score():
    best = choose_best(
        [
            _result("high_test_low_validation", selection=0.40, test=0.90),
            _result("better_validation", selection=0.50, test=0.55),
        ]
    )

    assert best is not None
    assert best.candidate_name == "better_validation"


def test_leaderboard_frame_contains_required_report_columns():
    frame = leaderboard_frame([_result("candidate", selection=0.5, test=0.4)])

    for column in [
        "validation_f1_macro",
        "test_f1_macro",
        "validation_test_gap",
        "log_loss",
        "brier_score",
        "per_class_recall_min",
        "overfit_flag",
        "walk_forward_f1_macro_std",
    ]:
        assert column in frame.columns


def test_write_report_records_local_only_outputs(tmp_path):
    report_path = tmp_path / "model_search_report.md"
    leaderboard_path = tmp_path / "leaderboard.csv"
    summary_path = tmp_path / "research_summary.json"
    result = _result("candidate", selection=0.5, test=0.45)

    write_report(
        results=[result],
        best=result,
        report_path=report_path,
        leaderboard_path=leaderboard_path,
        summary_path=summary_path,
        artifact_dir=tmp_path / "artifacts",
        bq_config=BigQueryConfig(
            project_id="project",
            analytics_dataset="analytics",
            ml_outputs_dataset="ml_outputs",
            training_table="training",
            metrics_table="metrics",
        ),
        candidates=[ResearchCandidate("candidate", "test", None)],
        run_id="run-1",
    )

    report = report_path.read_text(encoding="utf-8")
    assert "GCS output written: `false`" in report
    assert "BigQuery output written: `false`" in report
    assert leaderboard_path.exists()
    assert summary_path.exists()
