from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from local_feature_ablation_research import (
    AblationResult,
    choose_best,
    candidate_specs,
    engineered_features_from_frame,
    ensure_local_research_path,
    family_summary_frame,
    group_engineered_features,
    select_candidates,
    tradeoff_note,
    write_outputs,
)


def _engineered_features() -> list[str]:
    return [
        "return_1h_lag_1h_research",
        "return_1h_rolling_mean_24h_research",
        "volatility_regime_high_research",
        "trend_regime_down_research",
        "is_eth_research",
        "is_eth_x_return_24h_lag_1h_research",
        "quote_volume_zscore_24h_research",
        "taker_buy_pressure_delta_4h_research",
        "overall_risk_score_lag_1h_research",
        "avg_funding_rate_usdt_lag_1h_research",
    ]


def _result(
    name: str,
    family: str,
    validation_f1: float,
    down_recall: float,
) -> AblationResult:
    return AblationResult(
        candidate_name=name,
        feature_family=family,
        model_name="logistic_balanced",
        model_type="logistic",
        status="completed",
        feature_count=10,
        engineered_feature_count=1,
        selection_score=validation_f1,
        validation_f1_macro=validation_f1,
        test_f1_macro=validation_f1 - 0.02,
        validation_down_recall=down_recall,
        test_down_recall=down_recall - 0.03,
        per_class_recall_min=min(down_recall, 0.2),
        log_loss=1.0,
        brier_score=0.6,
        validation_test_gap=0.02,
        overfit_flag=False,
        tradeoff_note="test",
        artifact_path=None,
        reasons=[],
    )


def test_engineered_features_from_frame_excludes_original_features():
    frame = pd.DataFrame(
        columns=[
            "return_1h",
            "symbol",
            "return_1h_lag_1h_research",
            "volatility_regime_high_research",
        ]
    )

    features = engineered_features_from_frame(frame, ["return_1h"])

    assert features == [
        "return_1h_lag_1h_research",
        "volatility_regime_high_research",
    ]


def test_group_engineered_features_covers_required_families():
    groups = group_engineered_features(_engineered_features())

    assert set(groups) == {
        "original_only",
        "lag_rolling_returns",
        "regime_features",
        "symbol_aware_features",
        "microstructure_liquidity",
        "risk_macro_funding_lags",
        "all_engineered_features",
    }
    assert groups["original_only"].engineered_features == []
    assert "return_1h_lag_1h_research" in groups["lag_rolling_returns"].engineered_features
    assert "is_eth_research" in groups["symbol_aware_features"].engineered_features


def test_select_candidates_12_covers_every_family():
    families = {candidate.feature_family for candidate in select_candidates(12)}

    assert families == {
        "original_only",
        "lag_rolling_returns",
        "regime_features",
        "symbol_aware_features",
        "microstructure_liquidity",
        "risk_macro_funding_lags",
        "all_engineered_features",
    }
    assert any(candidate.model_type == "lightgbm" for candidate in candidate_specs())


def test_choose_best_uses_validation_not_test():
    best = choose_best(
        [
            _result("high_test", "a", validation_f1=0.30, down_recall=0.90),
            _result("high_validation", "b", validation_f1=0.40, down_recall=0.10),
        ]
    )

    assert best is not None
    assert best.candidate_name == "high_validation"


def test_tradeoff_note_labels_f1_down_recall_up():
    note = tradeoff_note(
        validation_f1_macro=0.35,
        validation_down_recall=0.30,
        baseline_validation_f1_macro=0.40,
        baseline_validation_down_recall=0.20,
    )

    assert note == "down_recall_up_macro_f1_down"


def test_family_summary_keeps_best_per_family():
    summary = family_summary_frame(
        [
            _result("a_low", "family_a", 0.30, 0.40),
            _result("a_high", "family_a", 0.35, 0.20),
            _result("b", "family_b", 0.32, 0.50),
        ]
    )

    assert set(summary["candidate_name"]) == {"a_high", "b"}


def test_path_must_stay_under_local_research_root():
    with pytest.raises(ValueError, match="Path must stay under"):
        ensure_local_research_path(Path("/tmp/outside-ablation"))


def test_write_outputs_records_local_only_artifacts(tmp_path, monkeypatch):
    import local_feature_ablation_research as module

    monkeypatch.setattr(module, "DEFAULT_LEADERBOARD_PATH", tmp_path / "leaderboard.csv")
    monkeypatch.setattr(module, "DEFAULT_SUMMARY_PATH", tmp_path / "summary.json")
    monkeypatch.setattr(module, "DEFAULT_REPORT_PATH", tmp_path / "report.md")
    families = group_engineered_features(_engineered_features())
    result = _result("candidate", "lag_rolling_returns", 0.4, 0.25)

    write_outputs(
        artifact_dir=tmp_path,
        results=[result],
        best=result,
        families=families,
        input_parquet=tmp_path / "input.parquet",
        feature_v1_summary={"baseline_reference": {}},
        dry_run=True,
    )

    assert (tmp_path / "leaderboard.csv").exists()
    summary = (tmp_path / "summary.json").read_text(encoding="utf-8")
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert '"wrote_gcs": false' in summary
    assert "BigQuery output written: `false`" in report
