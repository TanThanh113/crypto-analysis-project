#!/usr/bin/env python3
"""
Local-only microstructure + DOWN recall focus sprint.

This runner narrows the Feature Engineering V1 search to microstructure and
selected lag-return families. It reads only local artifacts, evaluates a small
candidate set with fixed time splits, and writes local-only reports.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

from local_automl_research import LOCAL_RESEARCH_ROOT, build_research_configs
from local_feature_ablation_research import (
    FeatureFamily,
    engineered_features_from_frame,
    ensure_local_research_path,
    group_engineered_features,
    model_config_for_family,
    tradeoff_note,
)
from local_feature_engineering_research import (
    DOWN_CLASS,
    OVERFIT_GAP_THRESHOLD,
    FeatureCandidate,
    build_candidate_model,
    class_recall,
    evaluate_predictions,
    fit_model,
    per_class_metrics,
    predict_with_down_threshold,
)
from time_split import apply_train_window
from train_model import (
    ModelConfig,
    evaluate_model,
    load_yaml,
    safe_predict_proba,
    split_xy,
    validate_training_data,
)


FOCUS_ROOT = LOCAL_RESEARCH_ROOT / "down_recall_focus_v1"
DEFAULT_INPUT_PARQUET = (
    LOCAL_RESEARCH_ROOT
    / "feature_engineering_v1"
    / "engineered_training_features.parquet"
)
DEFAULT_ABLATION_LEADERBOARD = (
    LOCAL_RESEARCH_ROOT / "feature_ablation_v1" / "leaderboard.csv"
)
DEFAULT_ABLATION_SUMMARY = (
    LOCAL_RESEARCH_ROOT / "feature_ablation_v1" / "research_summary.json"
)
DEFAULT_REPORT_PATH = LOCAL_RESEARCH_ROOT / "down_recall_focus_v1_report.md"
DEFAULT_LEADERBOARD_PATH = FOCUS_ROOT / "leaderboard.csv"
DEFAULT_SUMMARY_PATH = FOCUS_ROOT / "research_summary.json"

MAX_ALLOWED_F1_DROP = 0.005
MAX_ALLOWED_MIN_RECALL_DROP = 0.03
MAX_ALLOWED_VALIDATION_TEST_GAP = 0.06
MIN_DOWN_RECALL_GAIN = 0.005

LOCAL_ONLY_WRITES = {
    "wrote_gcs": False,
    "wrote_bigquery_output": False,
    "updated_registry": False,
    "production_predict_behavior_changed": False,
}


@dataclass(frozen=True)
class FocusCandidate:
    feature_family: str
    model_name: str
    model_type: str
    train_window_days: Optional[int] = None
    class_weight: Optional[str] = None

    @property
    def candidate_name(self) -> str:
        return f"{self.feature_family}__{self.model_name}"


@dataclass(frozen=True)
class ReferenceMetrics:
    validation_f1_macro: Optional[float]
    validation_down_recall: Optional[float]
    per_class_recall_min: Optional[float]
    validation_test_gap: Optional[float]


@dataclass(frozen=True)
class FocusResult:
    candidate_name: str
    feature_family: str
    model_name: str
    model_type: str
    status: str
    feature_count: int
    engineered_feature_count: int
    selection_score: Optional[float]
    validation_f1_macro: Optional[float]
    test_f1_macro: Optional[float]
    validation_down_recall: Optional[float]
    test_down_recall: Optional[float]
    per_class_recall_min: Optional[float]
    log_loss: Optional[float]
    brier_score: Optional[float]
    validation_test_gap: Optional[float]
    overfit_flag: bool
    tradeoff_note: str
    keep_candidate: bool
    keep_reason: str
    threshold_policy: Optional[dict[str, Any]]
    artifact_path: Optional[str]
    reasons: list[str]

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local-only DOWN recall focus research."
    )
    parser.add_argument("--config", default="feature_list.yml")
    parser.add_argument("--input-parquet", default=str(DEFAULT_INPUT_PARQUET))
    parser.add_argument("--artifact-dir", default=str(FOCUS_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--ablation-leaderboard", default=str(DEFAULT_ABLATION_LEADERBOARD))
    parser.add_argument("--ablation-summary", default=str(DEFAULT_ABLATION_SUMMARY))
    return parser.parse_args()


def selected_lag_return_features(engineered_features: list[str]) -> list[str]:
    desired = {
        "return_24h_symbol_zscore_research",
        "return_1h_rolling_mean_24h_research",
        "return_1h_rolling_sum_24h_research",
        "return_24h_lag_1h_research",
        "rolling_drawdown_24h_research",
        "return_4h_lag_1h_research",
        "return_1h_rolling_mean_4h_research",
        "return_1h_rolling_sum_4h_research",
    }
    return sorted(feature for feature in engineered_features if feature in desired)


def focus_feature_families(engineered_features: list[str]) -> dict[str, FeatureFamily]:
    families = group_engineered_features(engineered_features)
    microstructure = families["microstructure_liquidity"].engineered_features
    selected_lags = selected_lag_return_features(engineered_features)
    combined = sorted(set(microstructure + selected_lags))
    return {
        "original_only": families["original_only"],
        "microstructure_liquidity": families["microstructure_liquidity"],
        "lag_rolling_returns": families["lag_rolling_returns"],
        "microstructure_selected_lag_returns": FeatureFamily(
            name="microstructure_selected_lag_returns",
            description=(
                "Original features plus microstructure/liquidity and selected "
                "high-signal lag/rolling return features."
            ),
            engineered_features=combined,
        ),
    }


def candidate_specs() -> list[FocusCandidate]:
    return [
        FocusCandidate("original_only", "logistic_balanced", "logistic", class_weight="balanced"),
        FocusCandidate("microstructure_liquidity", "logistic_balanced", "logistic", class_weight="balanced"),
        FocusCandidate("microstructure_liquidity", "extratrees", "extratrees", class_weight="balanced"),
        FocusCandidate("microstructure_liquidity", "lightgbm_rolling_90d", "lightgbm", train_window_days=90),
        FocusCandidate("lag_rolling_returns", "extratrees", "extratrees", class_weight="balanced"),
        FocusCandidate("microstructure_selected_lag_returns", "logistic_balanced", "logistic", class_weight="balanced"),
        FocusCandidate("microstructure_selected_lag_returns", "extratrees", "extratrees", class_weight="balanced"),
    ]


def select_candidates(max_candidates: Optional[int]) -> list[FocusCandidate]:
    candidates = candidate_specs()
    if max_candidates is None:
        return candidates
    return candidates[:max_candidates]


def make_feature_candidate(candidate: FocusCandidate) -> FeatureCandidate:
    return FeatureCandidate(
        name=candidate.candidate_name,
        model_type=candidate.model_type,
        train_window_days=candidate.train_window_days,
        class_weight=candidate.class_weight,
    )


def load_reference_metrics(leaderboard_path: Path) -> ReferenceMetrics:
    if not leaderboard_path.exists():
        return ReferenceMetrics(None, None, None, None)
    leaderboard = pd.read_csv(leaderboard_path)
    row = leaderboard[
        leaderboard["candidate_name"] == "original_only__logistic_balanced"
    ]
    if row.empty:
        return ReferenceMetrics(None, None, None, None)
    record = row.iloc[0]
    return ReferenceMetrics(
        validation_f1_macro=float(record["validation_f1_macro"]),
        validation_down_recall=float(record["validation_down_recall"]),
        per_class_recall_min=float(record["per_class_recall_min"]),
        validation_test_gap=float(record["validation_test_gap"]),
    )


def keep_decision(
    *,
    validation_f1_macro: Optional[float],
    validation_down_recall: Optional[float],
    per_class_recall_min: Optional[float],
    validation_test_gap: Optional[float],
    reference: ReferenceMetrics,
) -> tuple[bool, str]:
    if (
        validation_f1_macro is None
        or validation_down_recall is None
        or per_class_recall_min is None
        or validation_test_gap is None
        or reference.validation_f1_macro is None
        or reference.validation_down_recall is None
        or reference.per_class_recall_min is None
    ):
        return False, "insufficient_metrics"

    reasons = []
    if validation_f1_macro < reference.validation_f1_macro - MAX_ALLOWED_F1_DROP:
        reasons.append("validation_f1_below_budget")
    if validation_down_recall < reference.validation_down_recall + MIN_DOWN_RECALL_GAIN:
        reasons.append("down_recall_not_clearly_higher")
    if per_class_recall_min < reference.per_class_recall_min - MAX_ALLOWED_MIN_RECALL_DROP:
        reasons.append("per_class_recall_min_drops_too_much")
    if validation_test_gap > MAX_ALLOWED_VALIDATION_TEST_GAP:
        reasons.append("validation_test_gap_too_large")

    if reasons:
        return False, ",".join(reasons)
    return True, "meets_focus_keep_rule"


def select_down_threshold_policy(
    *,
    model: Any,
    x_validation: pd.DataFrame,
    y_validation: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    labels: list[str],
    reference: ReferenceMetrics,
) -> Optional[dict[str, Any]]:
    proba_validation = safe_predict_proba(model, x_validation)
    proba_test = safe_predict_proba(model, x_test)
    if proba_validation is None or proba_test is None or reference.validation_f1_macro is None:
        return None

    rows = []
    for threshold in np.linspace(0.20, 0.55, 36):
        pred = predict_with_down_threshold(
            proba_validation,
            classes=labels,
            down_threshold=float(threshold),
        )
        metrics = evaluate_predictions(y_validation, pred, labels=labels)
        eligible = bool(metrics["f1_macro"] >= reference.validation_f1_macro - MAX_ALLOWED_F1_DROP)
        rows.append(
            {
                "threshold": float(threshold),
                "eligible": eligible,
                **metrics,
            }
        )

    eligible_rows = [row for row in rows if row["eligible"]]
    pool = eligible_rows or rows
    selected = sorted(
        pool,
        key=lambda row: (
            row["down_recall"] if row["down_recall"] is not None else -1.0,
            row["f1_macro"],
            row["per_class_recall_min"] if row["per_class_recall_min"] is not None else -1.0,
        ),
        reverse=True,
    )[0]
    test_pred = predict_with_down_threshold(
        proba_test,
        classes=labels,
        down_threshold=float(selected["threshold"]),
    )
    test_metrics = evaluate_predictions(y_test, test_pred, labels=labels)
    return {
        "selected_threshold": selected["threshold"],
        "eligible": bool(selected["eligible"]),
        "selected_reason": (
            "within_original_f1_drop_budget"
            if selected["eligible"]
            else "rejected_f1_drop_gt_0.005_vs_original_only"
        ),
        "validation_f1_macro": selected["f1_macro"],
        "validation_down_recall": selected["down_recall"],
        "validation_per_class_recall_min": selected["per_class_recall_min"],
        "test": test_metrics,
    }


def evaluate_focus_candidate(
    *,
    candidate: FocusCandidate,
    family: FeatureFamily,
    frame: pd.DataFrame,
    model_config: ModelConfig,
    training_config: Any,
    artifact_dir: Path,
    reference: ReferenceMetrics,
) -> FocusResult:
    try:
        family_config = model_config_for_family(model_config, family)
        candidate_frame = apply_train_window(
            frame,
            split_column=family_config.split_column,
            train_window_days=candidate.train_window_days,
        )
        validate_training_data(candidate_frame, family_config, training_config)

        model = build_candidate_model(make_feature_candidate(candidate), family_config)
        x_train, y_train, w_train = split_xy(candidate_frame, "train", family_config)
        x_val, y_val, _ = split_xy(candidate_frame, "validation", family_config)
        x_test, y_test, _ = split_xy(candidate_frame, "test", family_config)
        fit_model(model, x_train, y_train, w_train)

        validation_metrics = evaluate_model(model, x_val, y_val)
        test_metrics = evaluate_model(model, x_test, y_test)
        validation_pred = model.predict(x_val)
        test_pred = model.predict(x_test)
        validation_per_class = per_class_metrics(
            y_val,
            validation_pred,
            labels=family_config.valid_classes,
        )
        test_per_class = per_class_metrics(
            y_test,
            test_pred,
            labels=family_config.valid_classes,
        )
        validation_f1 = validation_metrics.get("f1_macro")
        test_f1 = test_metrics.get("f1_macro")
        validation_down = class_recall(validation_per_class, DOWN_CLASS)
        test_down = class_recall(test_per_class, DOWN_CLASS)
        gap = (
            float(validation_f1) - float(test_f1)
            if validation_f1 is not None and test_f1 is not None
            else None
        )
        keep, keep_reason = keep_decision(
            validation_f1_macro=validation_f1,
            validation_down_recall=validation_down,
            per_class_recall_min=validation_metrics.get("per_class_recall_min"),
            validation_test_gap=gap,
            reference=reference,
        )
        threshold_policy = None
        if candidate.model_type == "logistic":
            threshold_policy = select_down_threshold_policy(
                model=model,
                x_validation=x_val,
                y_validation=y_val,
                x_test=x_test,
                y_test=y_test,
                labels=family_config.valid_classes,
                reference=reference,
            )

        model_dir = artifact_dir / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = model_dir / f"{candidate.candidate_name}.joblib"
        joblib.dump(
            {
                "model": model,
                "candidate": asdict(candidate),
                "feature_family": asdict(family),
                "validation_metrics": validation_metrics,
                "test_metrics": test_metrics,
                "threshold_policy": threshold_policy,
                "saved_at": utc_now_iso(),
            },
            artifact_path,
        )

        return FocusResult(
            candidate_name=candidate.candidate_name,
            feature_family=candidate.feature_family,
            model_name=candidate.model_name,
            model_type=candidate.model_type,
            status="completed",
            feature_count=len(family_config.all_features),
            engineered_feature_count=len(family.engineered_features),
            selection_score=float(validation_f1) if validation_f1 is not None else None,
            validation_f1_macro=float(validation_f1) if validation_f1 is not None else None,
            test_f1_macro=float(test_f1) if test_f1 is not None else None,
            validation_down_recall=validation_down,
            test_down_recall=test_down,
            per_class_recall_min=validation_metrics.get("per_class_recall_min"),
            log_loss=validation_metrics.get("log_loss"),
            brier_score=validation_metrics.get("brier_score"),
            validation_test_gap=gap,
            overfit_flag=bool(gap is not None and gap > OVERFIT_GAP_THRESHOLD),
            tradeoff_note=tradeoff_note(
                validation_f1_macro=validation_f1,
                validation_down_recall=validation_down,
                baseline_validation_f1_macro=reference.validation_f1_macro,
                baseline_validation_down_recall=reference.validation_down_recall,
            ),
            keep_candidate=keep,
            keep_reason=keep_reason,
            threshold_policy=threshold_policy,
            artifact_path=str(artifact_path),
            reasons=[],
        )
    except Exception as exc:
        return FocusResult(
            candidate_name=candidate.candidate_name,
            feature_family=candidate.feature_family,
            model_name=candidate.model_name,
            model_type=candidate.model_type,
            status="skipped",
            feature_count=0,
            engineered_feature_count=len(family.engineered_features),
            selection_score=None,
            validation_f1_macro=None,
            test_f1_macro=None,
            validation_down_recall=None,
            test_down_recall=None,
            per_class_recall_min=None,
            log_loss=None,
            brier_score=None,
            validation_test_gap=None,
            overfit_flag=False,
            tradeoff_note="skipped",
            keep_candidate=False,
            keep_reason="skipped",
            threshold_policy=None,
            artifact_path=None,
            reasons=[str(exc)],
        )


def choose_best_by_validation(results: list[FocusResult]) -> Optional[FocusResult]:
    completed = [
        result for result in results
        if result.status == "completed" and result.validation_f1_macro is not None
    ]
    if not completed:
        return None
    return sorted(
        completed,
        key=lambda result: (
            result.validation_f1_macro if result.validation_f1_macro is not None else -1.0,
            result.validation_down_recall if result.validation_down_recall is not None else -1.0,
            result.per_class_recall_min if result.per_class_recall_min is not None else -1.0,
        ),
        reverse=True,
    )[0]


def choose_best_keep(results: list[FocusResult]) -> Optional[FocusResult]:
    keepers = [
        result for result in results
        if result.status == "completed" and result.keep_candidate
    ]
    if not keepers:
        return None
    return sorted(
        keepers,
        key=lambda result: (
            result.validation_down_recall if result.validation_down_recall is not None else -1.0,
            result.validation_f1_macro if result.validation_f1_macro is not None else -1.0,
            result.per_class_recall_min if result.per_class_recall_min is not None else -1.0,
        ),
        reverse=True,
    )[0]


def markdown_table(frame: pd.DataFrame, columns: Optional[list[str]] = None, max_rows: int = 40) -> str:
    if frame is None or frame.empty:
        return "_No data._"
    visible = frame.copy()
    if columns is not None:
        visible = visible[columns]
    visible = visible.head(max_rows)
    headers = list(visible.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in visible.iterrows():
        cells = []
        for header in headers:
            value = row[header]
            if isinstance(value, (dict, list)):
                cells.append(json.dumps(value, default=str))
            elif pd.isna(value):
                cells.append("")
            elif isinstance(value, float):
                cells.append(f"{value:.4f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_outputs(
    *,
    artifact_dir: Path,
    results: list[FocusResult],
    best_validation: Optional[FocusResult],
    best_keep: Optional[FocusResult],
    families: dict[str, FeatureFamily],
    input_parquet: Path,
    reference: ReferenceMetrics,
    ablation_summary: dict[str, Any],
    dry_run: bool,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    leaderboard = pd.DataFrame([result.to_row() for result in results])
    leaderboard.to_csv(DEFAULT_LEADERBOARD_PATH, index=False)

    threshold_rows = [
        {
            "candidate_name": result.candidate_name,
            **(result.threshold_policy or {}),
        }
        for result in results
        if result.threshold_policy
    ]
    threshold_frame = pd.DataFrame(threshold_rows)
    keep_frame = leaderboard[leaderboard["keep_candidate"] == True].copy() if not leaderboard.empty else pd.DataFrame()

    summary = {
        "created_at": utc_now_iso(),
        "dry_run": dry_run,
        "input_parquet": str(input_parquet),
        "artifact_dir": str(artifact_dir),
        "leaderboard_path": str(DEFAULT_LEADERBOARD_PATH),
        "report_path": str(DEFAULT_REPORT_PATH),
        "reference_metrics": asdict(reference),
        "candidate_names": [result.candidate_name for result in results],
        "feature_families": {
            name: asdict(family)
            for name, family in families.items()
        },
        "best_validation_model": best_validation.to_row() if best_validation else None,
        "best_keep_model": best_keep.to_row() if best_keep else None,
        "keeper_count": int(len(keep_frame)),
        "ablation_best_model": ablation_summary.get("best_model"),
        **LOCAL_ONLY_WRITES,
    }
    DEFAULT_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    report = f"""# Local Microstructure + DOWN Recall Focus V1

## Safety

- GCS output written: `false`
- BigQuery output written: `false`
- Registry updated: `false`
- Production predict behavior changed: `false`
- Dry run flag: `{dry_run}`
- Input parquet: `{input_parquet}`

## Reference

- Original validation F1: `{reference.validation_f1_macro}`
- Original validation DOWN recall: `{reference.validation_down_recall}`
- Original per-class recall min: `{reference.per_class_recall_min}`
- Keep rule F1 floor: `{None if reference.validation_f1_macro is None else reference.validation_f1_macro - MAX_ALLOWED_F1_DROP}`
- Keep rule min DOWN recall: `{None if reference.validation_down_recall is None else reference.validation_down_recall + MIN_DOWN_RECALL_GAIN}`

## Candidate Leaderboard

Selection uses validation macro F1. Test is final reporting only.

{markdown_table(leaderboard, columns=[
    "candidate_name",
    "feature_family",
    "model_name",
    "status",
    "validation_f1_macro",
    "test_f1_macro",
    "validation_down_recall",
    "test_down_recall",
    "per_class_recall_min",
    "log_loss",
    "brier_score",
    "validation_test_gap",
    "overfit_flag",
    "tradeoff_note",
    "keep_candidate",
    "keep_reason",
])}

## Keep Candidates

{markdown_table(keep_frame, columns=[
    "candidate_name",
    "validation_f1_macro",
    "validation_down_recall",
    "per_class_recall_min",
    "validation_test_gap",
    "keep_reason",
])}

## Threshold Policy Diagnostics

Threshold is selected on validation only and rejected if validation macro F1 drops more than 0.005 vs original_only.

{markdown_table(threshold_frame, max_rows=20)}

## Current Answers

- Best candidate by validation F1: `{best_validation.candidate_name if best_validation else "N/A"}`
- Best kept candidate by focus rule: `{best_keep.candidate_name if best_keep else "N/A"}`
- Should use test to choose: `false`
- Should promote automatically: `false`

## Recommendation

- Promote nothing automatically from this local sprint.
- If a microstructure candidate is kept by the validation rule, consider productionizing only that feature family through dbt after review.
- If ExtraTrees improves DOWN recall but fails macro F1, treat it as a recall-risk trade-off rather than the production default.
- Re-run a focused walk-forward/AutoML sprint only for kept candidates.
"""
    DEFAULT_REPORT_PATH.write_text(report, encoding="utf-8")


def run_research(args: argparse.Namespace) -> list[FocusResult]:
    input_parquet = ensure_local_research_path(Path(args.input_parquet))
    artifact_dir = ensure_local_research_path(Path(args.artifact_dir))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if not input_parquet.exists():
        raise FileNotFoundError(f"Input parquet not found: {input_parquet}")

    config = load_yaml(Path(args.config).resolve())
    _, model_config, training_config = build_research_configs(config)
    frame = pd.read_parquet(input_parquet)
    validate_training_data(frame, model_config, training_config)

    engineered_features = engineered_features_from_frame(frame, model_config.numeric_features)
    families = focus_feature_families(engineered_features)
    candidates = select_candidates(args.max_candidates)
    reference = load_reference_metrics(Path(args.ablation_leaderboard))
    ablation_summary = read_json(Path(args.ablation_summary))

    print("[down-focus] Feature families:")
    for family in families.values():
        print(f"  - {family.name}: {len(family.engineered_features)} engineered features")
    print("[down-focus] Candidates:")
    for candidate in candidates:
        print(f"  - {candidate.candidate_name}")

    results = [
        evaluate_focus_candidate(
            candidate=candidate,
            family=families[candidate.feature_family],
            frame=frame,
            model_config=model_config,
            training_config=training_config,
            artifact_dir=artifact_dir,
            reference=reference,
        )
        for candidate in candidates
    ]
    best_validation = choose_best_by_validation(results)
    best_keep = choose_best_keep(results)
    write_outputs(
        artifact_dir=artifact_dir,
        results=results,
        best_validation=best_validation,
        best_keep=best_keep,
        families=families,
        input_parquet=input_parquet,
        reference=reference,
        ablation_summary=ablation_summary,
        dry_run=args.dry_run,
    )
    print(f"[down-focus] Leaderboard: {DEFAULT_LEADERBOARD_PATH}")
    print(f"[down-focus] Summary: {DEFAULT_SUMMARY_PATH}")
    print(f"[down-focus] Report: {DEFAULT_REPORT_PATH}")
    if best_validation is not None:
        print(f"[down-focus] Best validation candidate: {best_validation.candidate_name}")
    if best_keep is not None:
        print(f"[down-focus] Best keep candidate: {best_keep.candidate_name}")
    return results


def main() -> int:
    args = parse_args()
    run_research(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
