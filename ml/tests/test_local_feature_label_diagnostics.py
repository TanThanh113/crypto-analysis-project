from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from local_feature_label_diagnostics import (
    TrainingInput,
    class_distribution,
    ensure_local_research_path,
    feature_completeness_by_split,
    infer_feature_group,
    target_correlations,
    write_diagnostic_report,
)


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hour_ts": pd.date_range("2026-01-01", periods=6, freq="h", tz="UTC"),
            "split_name": ["train", "train", "validation", "validation", "test", "test"],
            "symbol": ["BTC", "ETH", "BTC", "ETH", "BTC", "ETH"],
            "future_direction_4h": ["UP", "DOWN", "FLAT", "UP", "DOWN", "FLAT"],
            "return_1h": [0.01, -0.02, 0.0, 0.03, -0.01, None],
            "avg_funding_rate_usdt": [0.1, 0.2, None, 0.1, 0.3, 0.4],
        }
    )


def test_class_distribution_counts_and_percentages():
    distribution = class_distribution(
        _sample_frame(),
        target_column="future_direction_4h",
        group_column="split_name",
    )

    validation = distribution[distribution["split_name"] == "validation"]
    assert set(validation["class"]) == {"FLAT", "UP"}
    assert validation["count"].sum() == 2
    assert validation["pct"].sum() == pytest.approx(1.0)


def test_feature_completeness_by_split_uses_local_columns():
    completeness = feature_completeness_by_split(
        _sample_frame(),
        features=["return_1h", "avg_funding_rate_usdt"],
        split_column="split_name",
    )

    test_row = completeness[completeness["split_name"] == "test"].iloc[0]
    assert test_row["rows"] == 2
    assert test_row["mean"] == pytest.approx(0.75)


def test_infer_feature_group_covers_expected_crypto_groups():
    assert infer_feature_group("return_4h") == "market_price"
    assert infer_feature_group("quote_volume_24h") == "volume_liquidity"
    assert infer_feature_group("avg_funding_rate_usdt") == "funding_derivatives"
    assert infer_feature_group("sp500_return_1d") == "macro"
    assert infer_feature_group("social_sentiment_score") == "sentiment"


def test_target_correlations_orders_strongest_signal_first():
    correlations = target_correlations(
        _sample_frame(),
        numeric_features=["return_1h", "avg_funding_rate_usdt"],
        target_column="future_direction_4h",
    )

    assert "abs_target_corr" in correlations.columns
    assert correlations.iloc[0]["abs_target_corr"] >= correlations.iloc[-1]["abs_target_corr"]


def test_report_path_must_stay_under_local_research_root(tmp_path):
    with pytest.raises(ValueError, match="Output path must be under"):
        ensure_local_research_path(Path("/tmp/outside.md"), root=tmp_path / "root")


def test_write_diagnostic_report_records_local_only_safety(tmp_path):
    report_path = tmp_path / "feature_label_diagnostic_report.md"
    frame = _sample_frame()
    distribution = class_distribution(frame, target_column="future_direction_4h")
    split_distribution = class_distribution(
        frame,
        target_column="future_direction_4h",
        group_column="split_name",
    )
    symbol_distribution = class_distribution(
        frame,
        target_column="future_direction_4h",
        group_column="symbol",
    )
    missing = pd.DataFrame(
        [{"feature": "return_1h", "missing_rate": 0.1, "non_null_count": 5}]
    )
    completeness = pd.DataFrame(
        [{"split_name": "train", "rows": 2, "mean": 1.0, "p10": 1.0, "min": 1.0}]
    )
    correlations = pd.DataFrame(
        [{"feature": "return_1h", "group": "market_price", "target_corr": 0.2, "abs_target_corr": 0.2}]
    )
    group_summary = pd.DataFrame(
        [
            {
                "group": "market_price",
                "feature_count": 1,
                "mean_abs_target_corr": 0.2,
                "max_abs_target_corr": 0.2,
                "mean_missing_rate": 0.1,
                "logistic_importance": 0.3,
                "tree_importance": 0.4,
            }
        ]
    )

    write_diagnostic_report(
        report_path=report_path,
        input_info=TrainingInput(frame=frame, source="local_cache", path=tmp_path / "cache.parquet"),
        bq_table="project.dataset.table",
        leaderboard=pd.DataFrame(),
        summary={"best_model": {"candidate_name": "logistic"}},
        full_distribution=distribution,
        split_distribution=split_distribution,
        symbol_distribution=symbol_distribution,
        monthly_distribution=distribution.rename(columns={"group": "month"}),
        missing_rates=missing,
        completeness=completeness,
        correlations=correlations,
        logistic_importance=pd.DataFrame(),
        tree_importance=pd.DataFrame(),
        group_summary=group_summary,
        validation_errors=None,
        test_errors=None,
    )

    report = report_path.read_text(encoding="utf-8")
    assert "GCS output written: `false`" in report
    assert "BigQuery output written: `false`" in report
    assert "Training input source: `local_cache`" in report
