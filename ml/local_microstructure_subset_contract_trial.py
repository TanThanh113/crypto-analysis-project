#!/usr/bin/env python3
"""
Local Step B2 contract trial report for the 9-feature microstructure subset.

The script reads local train_model.py dry-run artifacts, optionally reads the
dev dbt training table read-only to compute per-class recall, and writes only
local artifacts under ml/artifacts/local_research/.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
import yaml
from google.cloud import bigquery
from sklearn.metrics import precision_recall_fscore_support

from train_model import (
    build_configs,
    clean_features,
    query_training_data,
    validate_training_data,
)


ML_ROOT = Path(__file__).resolve().parent
LOCAL_RESEARCH_ROOT = ML_ROOT / "artifacts" / "local_research"
DEFAULT_TRIAL_ROOT = LOCAL_RESEARCH_ROOT / "microstructure_subset_v1_train"
DEFAULT_REPORT_PATH = LOCAL_RESEARCH_ROOT / "microstructure_subset_v1_contract_trial_report.md"
DEFAULT_SUMMARY_PATH = DEFAULT_TRIAL_ROOT / "research_summary.json"
DEFAULT_LEADERBOARD_PATH = DEFAULT_TRIAL_ROOT / "leaderboard.csv"

SUBSET9_FEATURES = [
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

PARITY_CLOSE_FEATURES = {
    "return_1h_rolling_mean_4h",
    "return_1h_rolling_mean_24h",
    "rolling_drawdown_24h",
}


@dataclass(frozen=True)
class TrialSpec:
    name: str
    label: str
    config_path: Path
    artifact_dir: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_local_research_path(path: Path) -> Path:
    resolved = path.resolve()
    root = LOCAL_RESEARCH_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path must stay under {root}: {resolved}")
    return resolved


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def numeric_features(config_path: Path) -> list[str]:
    config = load_yaml(config_path)
    return list(config.get("model", {}).get("numeric_features", []) or [])


def default_trial_specs(trial_root: Path) -> list[TrialSpec]:
    return [
        TrialSpec(
            name="baseline",
            label="baseline production feature list",
            config_path=ML_ROOT / "feature_list.yml",
            artifact_dir=trial_root / "baseline",
        ),
        TrialSpec(
            name="safe16",
            label="full safe16 research feature list",
            config_path=ML_ROOT / "research" / "configs" / "feature_list_microstructure_safe_v1.yml",
            artifact_dir=trial_root / "safe16",
        ),
        TrialSpec(
            name="subset9",
            label="strict safe subset9 research feature list",
            config_path=ML_ROOT / "research" / "configs" / "feature_list_microstructure_subset_v1.yml",
            artifact_dir=trial_root / "subset9",
        ),
    ]


def load_bundle_from_artifact_dir(artifact_dir: Path) -> dict[str, Any]:
    manifest_path = artifact_dir / "latest_model.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing latest_model.json: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_path = Path(str(manifest.get("artifact_path") or manifest.get("artifact_uri") or ""))
    if not artifact_path.exists():
        raise FileNotFoundError(f"Missing model artifact: {artifact_path}")

    bundle = joblib.load(artifact_path)
    if not isinstance(bundle, dict):
        raise ValueError(f"Invalid model bundle: {artifact_path}")

    bundle["_manifest"] = manifest
    bundle["_artifact_path"] = str(artifact_path)
    return bundle


def metric(metrics: dict[str, Any], split_name: str, metric_name: str) -> Optional[float]:
    value = metrics.get(split_name, {}).get(metric_name)
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:
        return None
    return numeric


def _round_or_none(value: Optional[float], digits: int = 6) -> Optional[float]:
    return None if value is None else round(float(value), digits)


def summarize_bundle(spec: TrialSpec, bundle: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(bundle.get("metrics") or {})
    train_f1 = metric(metrics, "train", "f1_macro")
    validation_f1 = metric(metrics, "validation", "f1_macro")
    test_f1 = metric(metrics, "test", "f1_macro")
    validation_test_gap = (
        None
        if validation_f1 is None or test_f1 is None
        else validation_f1 - test_f1
    )
    train_validation_gap = (
        None
        if train_f1 is None or validation_f1 is None
        else train_f1 - validation_f1
    )

    return {
        "candidate": spec.name,
        "label": spec.label,
        "config_path": str(spec.config_path),
        "artifact_dir": str(spec.artifact_dir),
        "artifact_path": bundle.get("_artifact_path"),
        "model_name": bundle.get("model_name"),
        "model_version": bundle.get("model_version"),
        "best_model_key": bundle.get("model_key"),
        "feature_count": len(bundle.get("features") or []),
        "numeric_feature_count": len(bundle.get("numeric_features") or []),
        "validation_f1_macro": _round_or_none(validation_f1),
        "test_f1_macro": _round_or_none(test_f1),
        "validation_test_gap": _round_or_none(validation_test_gap),
        "train_validation_gap": _round_or_none(train_validation_gap),
        "per_class_recall_min": _round_or_none(metric(metrics, "validation", "per_class_recall_min")),
        "test_per_class_recall_min": _round_or_none(metric(metrics, "test", "per_class_recall_min")),
        "log_loss": _round_or_none(metric(metrics, "validation", "log_loss")),
        "brier_score": _round_or_none(metric(metrics, "validation", "brier_score")),
        "overfit_flag": bool(
            (train_validation_gap is not None and train_validation_gap > 0.05)
            or (
                validation_test_gap is not None
                and abs(validation_test_gap) > 0.05
            )
        ),
        "validation_down_recall": None,
        "test_down_recall": None,
        "null_warning_features": [],
    }


def attach_bigquery_per_class_metrics(row: dict[str, Any], spec: TrialSpec, bundle: dict[str, Any]) -> None:
    config = load_yaml(spec.config_path)
    bq_config, model_config, training_config = build_configs(config)
    client = bigquery.Client(project=bq_config.project_id)
    frame = query_training_data(client, bq_config, model_config)
    frame = clean_features(frame, model_config, training_config)
    validate_training_data(frame, model_config, training_config)

    model = bundle["model"]
    labels = list(model_config.valid_classes)
    for split_name in ["validation", "test"]:
        split = frame[frame[model_config.split_column] == split_name].copy()
        if split.empty:
            continue
        x_values = split[model_config.all_features]
        y_true = split[model_config.target_name].astype(str).str.upper()
        y_pred = model.predict(x_values)
        _, recall, _, _ = precision_recall_fscore_support(
            y_true,
            y_pred,
            labels=labels,
            average=None,
            zero_division=0,
        )
        recall_by_class = {
            label: float(value)
            for label, value in zip(labels, recall)
        }
        row[f"{split_name}_down_recall"] = _round_or_none(recall_by_class.get("DOWN"))

    null_warnings: list[str] = []
    for feature in [feature for feature in SUBSET9_FEATURES if feature in frame.columns]:
        null_pct = float(frame[feature].isna().mean())
        if null_pct > 0.05:
            null_warnings.append(f"{feature}:{null_pct:.4f}")
    row["null_warning_features"] = null_warnings


def build_leaderboard(
    specs: list[TrialSpec],
    *,
    read_bigquery: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        bundle = load_bundle_from_artifact_dir(spec.artifact_dir)
        row = summarize_bundle(spec, bundle)
        if read_bigquery:
            attach_bigquery_per_class_metrics(row, spec, bundle)
        rows.append(row)

    leaderboard = pd.DataFrame(rows)
    return leaderboard.sort_values(
        by=["validation_f1_macro", "per_class_recall_min"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)


def _value(frame: pd.DataFrame, candidate: str, column: str) -> Optional[float]:
    match = frame[frame["candidate"] == candidate]
    if match.empty or column not in match.columns:
        return None
    value = match.iloc[0][column]
    if pd.isna(value):
        return None
    return float(value)


def trial_decisions(leaderboard: pd.DataFrame) -> dict[str, Any]:
    baseline_f1 = _value(leaderboard, "baseline", "validation_f1_macro")
    safe16_f1 = _value(leaderboard, "safe16", "validation_f1_macro")
    subset9_f1 = _value(leaderboard, "subset9", "validation_f1_macro")
    baseline_recall_min = _value(leaderboard, "baseline", "per_class_recall_min")
    subset9_recall_min = _value(leaderboard, "subset9", "per_class_recall_min")
    subset9_down = _value(leaderboard, "subset9", "validation_down_recall")
    baseline_down = _value(leaderboard, "baseline", "validation_down_recall")

    best_row = leaderboard.iloc[0].to_dict() if not leaderboard.empty else {}
    subset_near_baseline = (
        False
        if baseline_f1 is None or subset9_f1 is None
        else baseline_f1 - subset9_f1 <= 0.005
    )
    subset_better_than_safe16 = (
        False
        if safe16_f1 is None or subset9_f1 is None
        else subset9_f1 > safe16_f1
    )
    subset_improves_recall_min = (
        False
        if baseline_recall_min is None or subset9_recall_min is None
        else subset9_recall_min > baseline_recall_min
    )
    subset_improves_down = (
        None
        if baseline_down is None or subset9_down is None
        else subset9_down > baseline_down
    )
    subset_beats_baseline = (
        False
        if baseline_f1 is None or subset9_f1 is None
        else subset9_f1 > baseline_f1
    )
    consider_guarded_pr = bool(subset_better_than_safe16 and subset_near_baseline)

    return {
        "best_candidate_by_validation_f1": best_row.get("candidate"),
        "best_validation_f1_macro": best_row.get("validation_f1_macro"),
        "subset9_beats_baseline_f1": subset_beats_baseline,
        "subset9_better_than_safe16": subset_better_than_safe16,
        "subset9_near_baseline_f1": subset_near_baseline,
        "subset9_improves_per_class_recall_min": subset_improves_recall_min,
        "subset9_improves_down_recall": subset_improves_down,
        "subset9_has_source_risk": False,
        "subset9_parity_close_features": sorted(PARITY_CLOSE_FEATURES),
        "consider_guarded_subset9_contract_pr": consider_guarded_pr,
        "recommend_enable_subset9_next": bool(subset_beats_baseline),
        "recommendation": (
            "hold"
            if not consider_guarded_pr
            else "consider_guarded_feature_contract_pr_but_do_not_switch_default_model_yet"
        ),
    }


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No data._"
    visible = frame.copy()
    headers = list(visible.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in visible.iterrows():
        cells = []
        for header in headers:
            value = row[header]
            if isinstance(value, list):
                cells.append(", ".join(str(item) for item in value) or "none")
            elif pd.isna(value):
                cells.append("")
            elif isinstance(value, float):
                cells.append(f"{value:.4f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(
    *,
    leaderboard: pd.DataFrame,
    decisions: dict[str, Any],
    report_path: Path,
    summary_path: Path,
    leaderboard_path: Path,
    read_bigquery: bool,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    leaderboard.to_csv(leaderboard_path, index=False)
    summary_payload = {
        "created_at": utc_now_iso(),
        "read_bigquery": read_bigquery,
        "wrote_gcs": False,
        "wrote_bigquery_output": False,
        "updated_registry": False,
        "production_feature_list_changed": False,
        "subset9_features": SUBSET9_FEATURES,
        "leaderboard": leaderboard.to_dict(orient="records"),
        "decisions": decisions,
        "leaderboard_path": str(leaderboard_path),
        "report_path": str(report_path),
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2, default=str), encoding="utf-8")

    selected_columns = [
        "candidate",
        "validation_f1_macro",
        "test_f1_macro",
        "validation_test_gap",
        "validation_down_recall",
        "per_class_recall_min",
        "log_loss",
        "brier_score",
        "overfit_flag",
    ]
    table = leaderboard[[column for column in selected_columns if column in leaderboard.columns]]

    recommendation = decisions["recommendation"]
    enable_answer = (
        "Chua nen bat nhu production default vi baseline van thang validation F1."
        if not decisions["recommend_enable_subset9_next"]
        else "Co the xem xet bat trong production feature_list."
    )
    guarded_answer = (
        "co the xem xet PR nho co guard"
        if decisions["consider_guarded_subset9_contract_pr"]
        else "chua nen"
    )
    down_answer = decisions["subset9_improves_down_recall"]
    if down_answer is None:
        down_text = "DOWN recall khong duoc tinh tu artifact neu khong doc BigQuery."
    else:
        down_text = "co" if down_answer else "khong"

    report = f"""# Microstructure Subset V1 Contract Trial Report

## Safety

- GCS output written: `false`
- BigQuery output tables written: `false`
- Registry updated: `false`
- Production `ml/feature_list.yml` changed: `false`
- BigQuery read-only input used for report: `{read_bigquery}`

## Leaderboard

{markdown_table(table)}

## Trial Answers

1. Subset9 better than full safe16: `{decisions["subset9_better_than_safe16"]}`.
2. Subset9 near baseline F1 within 0.005: `{decisions["subset9_near_baseline_f1"]}`.
3. Subset9 improves DOWN recall: `{down_text}`.
4. Subset9 improves per_class_recall_min: `{decisions["subset9_improves_per_class_recall_min"]}`.
5. Subset9 source risk: `false`; all 9 selected features are Binance/history based.
6. Subset9 parity note: close, not exact, for `{", ".join(decisions["subset9_parity_close_features"])}`.
7. Guarded subset9 feature-contract PR next: `{guarded_answer}`.
8. Enable subset9 as production default now: `{enable_answer}`
9. Bring back taker-pressure features later: `yes`, but only after live prediction source coverage is stable.

## Interpretation

The Step B2 subset intentionally excludes `liquidity_risk_score_lag_1h`, the
z-score/regime interaction features that still need parity review, and all
taker-pressure features. Model choice should still be based on validation F1,
not test score. Test metrics here are final sanity checks only.

## Output Files

- Leaderboard CSV: `{leaderboard_path}`
- Summary JSON: `{summary_path}`
"""
    report_path.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize local Step B2 subset contract trial.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_TRIAL_ROOT))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--leaderboard-path", default=str(DEFAULT_LEADERBOARD_PATH))
    parser.add_argument("--read-bigquery", action="store_true")
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    trial_root = ensure_local_research_path(Path(args.artifact_dir))
    report_path = ensure_local_research_path(Path(args.report_path))
    summary_path = ensure_local_research_path(Path(args.summary_path))
    leaderboard_path = ensure_local_research_path(Path(args.leaderboard_path))

    specs = default_trial_specs(trial_root)
    leaderboard = build_leaderboard(specs, read_bigquery=bool(args.read_bigquery))
    decisions = trial_decisions(leaderboard)
    write_report(
        leaderboard=leaderboard,
        decisions=decisions,
        report_path=report_path,
        summary_path=summary_path,
        leaderboard_path=leaderboard_path,
        read_bigquery=bool(args.read_bigquery),
    )
    print(f"[subset-trial] Leaderboard: {leaderboard_path}")
    print(f"[subset-trial] Summary: {summary_path}")
    print(f"[subset-trial] Report: {report_path}")
    return {"leaderboard": leaderboard, "decisions": decisions}


def main() -> int:
    run(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
