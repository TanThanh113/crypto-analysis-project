from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from local_microstructure_safe_parity_debug import (
    compare_parity,
    coverage_rows,
    ensure_local_research_path,
    safe_feature_specs,
    summary_payload,
    write_outputs,
)


def _frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    hours = pd.date_range("2026-01-01", periods=4, freq="h", tz="UTC")
    dbt_rows = []
    py_rows = []
    specs = safe_feature_specs()
    for idx, hour in enumerate(hours):
        row = {
            "hour_ts": hour,
            "symbol": "BTC",
            "split_name": "train" if idx < 2 else "validation",
        }
        py_row = dict(row)
        for spec in specs:
            value = float(idx + 1)
            row[spec.dbt_feature] = value
            py_row[spec.python_feature] = value
        dbt_rows.append(row)
        py_rows.append(py_row)
    dbt_rows[0]["quote_volume_lag_1h"] = None
    return pd.DataFrame(dbt_rows), pd.DataFrame(py_rows)


def test_safe_specs_exclude_taker_pressure_features():
    names = [spec.dbt_feature for spec in safe_feature_specs()]

    assert len(names) == 16
    assert "taker_buy_quote_ratio_lag_1h" not in names
    assert "taker_buy_pressure_delta_4h" not in names
    assert "quote_volume_lag_1h" in names


def test_coverage_rows_report_split_and_source_metadata():
    dbt_df, _ = _frames()
    rows = coverage_rows(dbt_df, safe_feature_specs())
    frame = pd.DataFrame([row.__dict__ for row in rows])

    quote_all = frame[(frame["feature"] == "quote_volume_lag_1h") & (frame["scope"] == "all")].iloc[0]
    split_scopes = frame[frame["scope"] == "split"]["group"].unique().tolist()
    liquidity = frame[(frame["feature"] == "liquidity_risk_score_lag_1h") & (frame["scope"] == "all")].iloc[0]

    assert quote_all["non_null_pct"] == pytest.approx(0.75)
    assert set(split_scopes) == {"train", "validation"}
    assert liquidity["source_available_flag"] == "partial_coverage"


def test_compare_parity_marks_exact_and_mismatch():
    dbt_df, py_df = _frames()
    dbt_df.loc[1, "return_4h_lag_1h"] = 999.0
    rows = compare_parity(dbt_df, py_df, safe_feature_specs())
    frame = pd.DataFrame([row.__dict__ for row in rows])

    exact = frame[frame["feature"] == "return_24h_lag_1h"].iloc[0]
    mismatch = frame[frame["feature"] == "return_4h_lag_1h"].iloc[0]

    assert exact["parity_status"] == "exact"
    assert mismatch["parity_status"] == "mismatch"


def test_summary_payload_recommends_high_coverage_backfilled_subset():
    dbt_df, py_df = _frames()
    coverage = pd.DataFrame([row.__dict__ for row in coverage_rows(dbt_df, safe_feature_specs())])
    parity = pd.DataFrame([row.__dict__ for row in compare_parity(dbt_df, py_df, safe_feature_specs())])
    summary = summary_payload(
        table_fqn="project.dataset.table",
        coverage=coverage,
        parity=parity,
        specs=safe_feature_specs(),
        read_bigquery=False,
    )

    assert summary["wrote_gcs"] is False
    assert "quote_volume_24h_lag_1h" in summary["features_depending_only_on_backfilled_sources"]
    assert "liquidity_risk_score_lag_1h" in summary["prediction_availability_risk_features"]


def test_outputs_stay_local_and_write_report(tmp_path, monkeypatch):
    import local_microstructure_safe_parity_debug as module

    local_root = tmp_path / "local_research"
    monkeypatch.setattr(module, "LOCAL_RESEARCH_ROOT", local_root)
    artifact_dir = local_root / "debug"
    report_path = local_root / "report.md"
    dbt_df, py_df = _frames()
    coverage = pd.DataFrame([row.__dict__ for row in coverage_rows(dbt_df, safe_feature_specs())])
    parity = pd.DataFrame([row.__dict__ for row in compare_parity(dbt_df, py_df, safe_feature_specs())])
    summary = summary_payload(
        table_fqn="project.dataset.table",
        coverage=coverage,
        parity=parity,
        specs=safe_feature_specs(),
        read_bigquery=False,
    )

    write_outputs(
        artifact_dir=ensure_local_research_path(artifact_dir),
        report_path=ensure_local_research_path(report_path),
        coverage=coverage,
        parity=parity,
        summary=summary,
        specs=safe_feature_specs(),
    )

    assert (artifact_dir / "feature_coverage.csv").exists()
    assert "GCS output written: `false`" in report_path.read_text(encoding="utf-8")


def test_rejects_paths_outside_local_research(tmp_path, monkeypatch):
    import local_microstructure_safe_parity_debug as module

    monkeypatch.setattr(module, "LOCAL_RESEARCH_ROOT", tmp_path / "local_research")
    with pytest.raises(ValueError, match="Path must stay under"):
        ensure_local_research_path(Path("/tmp/outside"))
