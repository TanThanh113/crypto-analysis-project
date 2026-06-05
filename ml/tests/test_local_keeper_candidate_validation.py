from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from local_keeper_candidate_validation import (
    KeeperResult,
    SliceMetricSummary,
    candidate_specs,
    choose_best_by_validation,
    choose_best_stable,
    keeper_feature_families,
    metric_gap,
    selected_lag_return_features,
    slice_metric_frame,
    stability_decision,
    summarize_slices,
    volatility_regime,
    write_outputs,
)


def _features() -> list[str]:
    return [
        "return_24h_symbol_zscore_research",
        "return_1h_rolling_mean_24h_research",
        "return_1h_rolling_sum_24h_research",
        "return_24h_lag_1h_research",
        "rolling_drawdown_24h_research",
        "quote_volume_zscore_24h_research",
        "taker_buy_pressure_delta_4h_research",
        "liquidity_regime_high_research",
        "liquidity_risk_score_lag_1h_research",
    ]


def _result(
    name: str,
    validation_f1: float,
    down_recall: float,
    stable: bool = False,
) -> KeeperResult:
    return KeeperResult(
        candidate_name=name,
        feature_family="family",
        status="completed",
        feature_count=10,
        engineered_feature_count=2,
        validation_f1_macro=validation_f1,
        test_f1_macro=validation_f1 - 0.02,
        validation_down_recall=down_recall,
        test_down_recall=down_recall - 0.05,
        per_class_recall_min=min(down_recall, 0.2),
        log_loss=1.0,
        brier_score=0.6,
        validation_test_gap=0.02,
        fold_std=0.01,
        monthly_f1_min=0.30,
        monthly_down_recall_min=0.10,
        symbol_f1_gap=0.02,
        symbol_down_recall_gap=0.03,
        overfit_flag=False,
        tradeoff_note="test",
        stable_candidate=stable,
        stability_reason="stable" if stable else "not_stable",
        artifact_path=None,
        reasons=[],
    )


def test_candidate_specs_validate_exact_three_candidates():
    assert [candidate.candidate_name for candidate in candidate_specs()] == [
        "original_only__logistic_balanced",
        "microstructure_liquidity__logistic_balanced",
        "microstructure_selected_lag_returns__logistic_balanced",
    ]


def test_keeper_feature_families_contains_only_three_families():
    families = keeper_feature_families(_features())

    assert set(families) == {
        "original_only",
        "microstructure_liquidity",
        "microstructure_selected_lag_returns",
    }
    assert "quote_volume_zscore_24h_research" in families["microstructure_liquidity"].engineered_features
    assert "return_24h_symbol_zscore_research" in families["microstructure_selected_lag_returns"].engineered_features


def test_volatility_regime_uses_high_low_flags():
    frame = pd.DataFrame(
        {
            "volatility_regime_high_research": [1.0, 0.0, 0.0],
            "volatility_regime_low_research": [0.0, 1.0, 0.0],
        }
    )

    assert list(volatility_regime(frame)) == ["high", "low", "normal"]


def test_slice_metric_frame_reports_group_f1_and_down_recall():
    frame = pd.DataFrame(
        {
            "symbol": ["BTC"] * 4 + ["ETH"] * 4,
            "actual": ["DOWN", "DOWN", "UP", "FLAT"] * 2,
            "predicted": ["DOWN", "UP", "UP", "FLAT", "DOWN", "DOWN", "UP", "FLAT"],
        }
    )

    metrics = slice_metric_frame(
        frame,
        group_column="symbol",
        labels=["UP", "DOWN", "FLAT"],
        min_rows=1,
    )

    assert set(metrics["group"]) == {"BTC", "ETH"}
    assert metric_gap(metrics, "down_recall") == pytest.approx(0.5)


def test_summarize_slices_calculates_stability_fields():
    monthly = pd.DataFrame(
        {"f1_macro": [0.4, 0.3], "down_recall": [0.2, 0.1]}
    )
    symbol = pd.DataFrame(
        {"f1_macro": [0.45, 0.35], "down_recall": [0.25, 0.15]}
    )
    regime = pd.DataFrame(
        {"f1_macro": [0.5, 0.25], "down_recall": [0.3, 0.05]}
    )

    summary = summarize_slices(monthly=monthly, symbol=symbol, regime=regime)

    assert isinstance(summary, SliceMetricSummary)
    assert summary.monthly_f1_min == pytest.approx(0.3)
    assert summary.symbol_down_recall_gap == pytest.approx(0.1)
    assert summary.regime_down_recall_min == pytest.approx(0.05)


def test_stability_decision_accepts_small_f1_drop_with_down_gain():
    baseline = _result("baseline", 0.400, 0.200)
    candidate = _result("candidate", 0.397, 0.210)

    stable, reason = stability_decision(candidate=candidate, baseline=baseline)

    assert stable is True
    assert reason == "stable_keeper_candidate"


def test_stability_decision_rejects_symbol_gap_worse():
    baseline = _result("baseline", 0.400, 0.200)
    candidate = KeeperResult(
        **{
            **_result("candidate", 0.397, 0.210).to_row(),
            "symbol_down_recall_gap": 0.20,
        }
    )

    stable, reason = stability_decision(candidate=candidate, baseline=baseline)

    assert stable is False
    assert "symbol_down_recall_gap_worse" in reason


def test_choose_best_by_validation_and_best_stable_are_separate():
    best_validation = choose_best_by_validation(
        [
            _result("stable_lower_f1", 0.397, 0.22, stable=True),
            _result("high_validation", 0.410, 0.20, stable=False),
        ]
    )
    best_stable = choose_best_stable(
        [
            _result("stable_lower_f1", 0.397, 0.22, stable=True),
            _result("high_validation", 0.410, 0.20, stable=False),
        ]
    )

    assert best_validation is not None
    assert best_validation.candidate_name == "high_validation"
    assert best_stable is not None
    assert best_stable.candidate_name == "stable_lower_f1"


def test_write_outputs_records_local_only_payload(tmp_path, monkeypatch):
    import local_keeper_candidate_validation as module

    monkeypatch.setattr(module, "DEFAULT_LEADERBOARD_PATH", tmp_path / "leaderboard.csv")
    monkeypatch.setattr(module, "DEFAULT_SUMMARY_PATH", tmp_path / "summary.json")
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", tmp_path / "report.md")

    result = _result("candidate", 0.40, 0.22, stable=True)
    write_outputs(
        artifact_dir=tmp_path,
        results=[result],
        slice_tables={"candidate": {"validation_monthly": pd.DataFrame({"a": [1]})}},
        best_validation=result,
        best_stable=result,
        input_parquet=tmp_path / "input.parquet",
        focus_summary={},
        dry_run=True,
    )

    assert (tmp_path / "leaderboard.csv").exists()
    assert (tmp_path / "slice_metrics" / "candidate__validation_monthly.csv").exists()
    summary = (tmp_path / "summary.json").read_text(encoding="utf-8")
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert '"wrote_gcs": false' in summary
    assert "BigQuery output written: `false`" in report
