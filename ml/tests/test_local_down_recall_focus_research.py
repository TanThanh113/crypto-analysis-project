from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from local_down_recall_focus_research import (
    FocusResult,
    ReferenceMetrics,
    choose_best_by_validation,
    choose_best_keep,
    candidate_specs,
    focus_feature_families,
    keep_decision,
    selected_lag_return_features,
    select_candidates,
    write_outputs,
)


def _features() -> list[str]:
    return [
        "return_24h_symbol_zscore_research",
        "return_1h_rolling_mean_24h_research",
        "return_1h_rolling_sum_24h_research",
        "return_24h_lag_1h_research",
        "rolling_drawdown_24h_research",
        "return_4h_lag_1h_research",
        "quote_volume_zscore_24h_research",
        "taker_buy_pressure_delta_4h_research",
        "liquidity_regime_high_research",
        "liquidity_risk_score_lag_1h_research",
    ]


def _result(
    name: str,
    validation_f1: float,
    down_recall: float,
    keep: bool = False,
) -> FocusResult:
    return FocusResult(
        candidate_name=name,
        feature_family="family",
        model_name="model",
        model_type="logistic",
        status="completed",
        feature_count=10,
        engineered_feature_count=2,
        selection_score=validation_f1,
        validation_f1_macro=validation_f1,
        test_f1_macro=validation_f1 - 0.02,
        validation_down_recall=down_recall,
        test_down_recall=down_recall - 0.05,
        per_class_recall_min=min(down_recall, 0.2),
        log_loss=1.0,
        brier_score=0.6,
        validation_test_gap=0.02,
        overfit_flag=False,
        tradeoff_note="test",
        keep_candidate=keep,
        keep_reason="meets_focus_keep_rule" if keep else "not_keep",
        threshold_policy=None,
        artifact_path=None,
        reasons=[],
    )


def test_selected_lag_return_features_uses_small_high_signal_subset():
    selected = selected_lag_return_features(_features())

    assert "return_24h_symbol_zscore_research" in selected
    assert "return_1h_rolling_mean_24h_research" in selected
    assert "quote_volume_zscore_24h_research" not in selected


def test_focus_feature_families_adds_microstructure_selected_lag_family():
    families = focus_feature_families(_features())

    combined = families["microstructure_selected_lag_returns"].engineered_features
    assert set(families) == {
        "original_only",
        "microstructure_liquidity",
        "lag_rolling_returns",
        "microstructure_selected_lag_returns",
    }
    assert "quote_volume_zscore_24h_research" in combined
    assert "return_24h_symbol_zscore_research" in combined


def test_candidate_specs_match_focus_prompt():
    names = [candidate.candidate_name for candidate in select_candidates(None)]

    assert names == [
        "original_only__logistic_balanced",
        "microstructure_liquidity__logistic_balanced",
        "microstructure_liquidity__extratrees",
        "microstructure_liquidity__lightgbm_rolling_90d",
        "lag_rolling_returns__extratrees",
        "microstructure_selected_lag_returns__logistic_balanced",
        "microstructure_selected_lag_returns__extratrees",
    ]
    assert len(candidate_specs()) == 7


def test_keep_decision_requires_f1_budget_and_down_gain():
    reference = ReferenceMetrics(0.40, 0.20, 0.19, 0.03)

    keep, reason = keep_decision(
        validation_f1_macro=0.396,
        validation_down_recall=0.207,
        per_class_recall_min=0.18,
        validation_test_gap=0.03,
        reference=reference,
    )

    assert keep is True
    assert reason == "meets_focus_keep_rule"


def test_keep_decision_rejects_when_down_recall_not_higher():
    reference = ReferenceMetrics(0.40, 0.20, 0.19, 0.03)

    keep, reason = keep_decision(
        validation_f1_macro=0.40,
        validation_down_recall=0.202,
        per_class_recall_min=0.19,
        validation_test_gap=0.03,
        reference=reference,
    )

    assert keep is False
    assert "down_recall_not_clearly_higher" in reason


def test_choose_best_by_validation_ignores_keep_flag():
    best = choose_best_by_validation(
        [
            _result("high_keep", 0.38, 0.35, keep=True),
            _result("high_validation", 0.41, 0.21, keep=False),
        ]
    )

    assert best is not None
    assert best.candidate_name == "high_validation"


def test_choose_best_keep_prefers_down_recall_among_keepers():
    best = choose_best_keep(
        [
            _result("lower_down", 0.40, 0.23, keep=True),
            _result("higher_down", 0.39, 0.30, keep=True),
        ]
    )

    assert best is not None
    assert best.candidate_name == "higher_down"


def test_write_outputs_records_local_only_payload(tmp_path, monkeypatch):
    import local_down_recall_focus_research as module

    monkeypatch.setattr(module, "DEFAULT_LEADERBOARD_PATH", tmp_path / "leaderboard.csv")
    monkeypatch.setattr(module, "DEFAULT_SUMMARY_PATH", tmp_path / "summary.json")
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", tmp_path / "report.md")

    result = _result("candidate", 0.40, 0.25, keep=True)
    write_outputs(
        artifact_dir=tmp_path,
        results=[result],
        best_validation=result,
        best_keep=result,
        families=focus_feature_families(_features()),
        input_parquet=tmp_path / "input.parquet",
        reference=ReferenceMetrics(0.40, 0.20, 0.19, 0.03),
        ablation_summary={},
        dry_run=True,
    )

    assert (tmp_path / "leaderboard.csv").exists()
    summary = (tmp_path / "summary.json").read_text(encoding="utf-8")
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert '"wrote_gcs": false' in summary
    assert "BigQuery output written: `false`" in report
