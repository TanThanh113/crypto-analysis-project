from __future__ import annotations

import json
from pathlib import Path

import joblib
import pytest

import local_microstructure_subset_contract_trial as trial


def _write_bundle(artifact_dir: Path, *, candidate: str, validation_f1: float, test_f1: float) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{candidate}.joblib"
    bundle = {
        "model_name": f"{candidate}_model",
        "model_version": "research_v1",
        "model_key": "logistic_baseline_all_history",
        "features": ["symbol", "return_1h", *trial.SUBSET9_FEATURES],
        "numeric_features": ["return_1h", *trial.SUBSET9_FEATURES],
        "metrics": {
            "train": {"f1_macro": validation_f1 + 0.01},
            "validation": {
                "f1_macro": validation_f1,
                "per_class_recall_min": 0.2,
                "log_loss": 1.0,
                "brier_score": 0.6,
            },
            "test": {
                "f1_macro": test_f1,
                "per_class_recall_min": 0.18,
                "log_loss": 1.1,
                "brier_score": 0.65,
            },
        },
    }
    joblib.dump(bundle, artifact_path)
    manifest = {
        "artifact_path": str(artifact_path),
        "best_model_key": "logistic_baseline_all_history",
    }
    (artifact_dir / "latest_model.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_subset9_feature_contract_has_exact_expected_features():
    assert trial.SUBSET9_FEATURES == [
        "quote_volume_lag_1h",
        "quote_volume_24h_lag_1h",
        "volume_zscore_24h_lag_1h",
        "return_4h_lag_1h",
        "return_24h_lag_1h",
        "return_24h_symbol_zscore",
        "return_1h_rolling_mean_4h",
        "return_1h_rolling_mean_24h",
        "rolling_drawdown_24h",
    ]
    assert "liquidity_risk_score_lag_1h" not in trial.SUBSET9_FEATURES
    assert "taker_buy_pressure_delta_4h" not in trial.SUBSET9_FEATURES


def test_build_leaderboard_reads_local_artifacts(tmp_path, monkeypatch):
    local_root = tmp_path / "local_research"
    trial_root = local_root / "microstructure_subset_v1_train"
    monkeypatch.setattr(trial, "LOCAL_RESEARCH_ROOT", local_root)

    _write_bundle(trial_root / "baseline", candidate="baseline", validation_f1=0.4008, test_f1=0.39)
    _write_bundle(trial_root / "safe16", candidate="safe16", validation_f1=0.3973, test_f1=0.38)
    _write_bundle(trial_root / "subset9", candidate="subset9", validation_f1=0.3990, test_f1=0.388)

    leaderboard = trial.build_leaderboard(trial.default_trial_specs(trial_root), read_bigquery=False)
    decisions = trial.trial_decisions(leaderboard)

    assert leaderboard.iloc[0]["candidate"] == "baseline"
    assert decisions["subset9_better_than_safe16"] is True
    assert decisions["subset9_near_baseline_f1"] is True


def test_write_report_stays_under_local_research(tmp_path, monkeypatch):
    local_root = tmp_path / "local_research"
    trial_root = local_root / "microstructure_subset_v1_train"
    monkeypatch.setattr(trial, "LOCAL_RESEARCH_ROOT", local_root)

    _write_bundle(trial_root / "baseline", candidate="baseline", validation_f1=0.4008, test_f1=0.39)
    _write_bundle(trial_root / "safe16", candidate="safe16", validation_f1=0.3973, test_f1=0.38)
    _write_bundle(trial_root / "subset9", candidate="subset9", validation_f1=0.3990, test_f1=0.388)

    args = type(
        "Args",
        (),
        {
            "artifact_dir": str(trial_root),
            "report_path": str(local_root / "report.md"),
            "summary_path": str(trial_root / "research_summary.json"),
            "leaderboard_path": str(trial_root / "leaderboard.csv"),
            "read_bigquery": False,
        },
    )()
    trial.run(args)

    assert (trial_root / "leaderboard.csv").exists()
    assert (trial_root / "research_summary.json").exists()
    assert "GCS output written: `false`" in (local_root / "report.md").read_text(encoding="utf-8")


def test_rejects_output_outside_local_research(tmp_path, monkeypatch):
    monkeypatch.setattr(trial, "LOCAL_RESEARCH_ROOT", tmp_path / "local_research")
    with pytest.raises(ValueError, match="Path must stay under"):
        trial.ensure_local_research_path(Path("/tmp/not-local-research"))
