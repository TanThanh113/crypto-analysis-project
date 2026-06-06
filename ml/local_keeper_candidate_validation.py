#!/usr/bin/env python3
"""
Local-only keeper candidate validation for crypto direction.

This sprint validates whether the microstructure keeper candidate is stable
enough to justify a later dbt productionization review. It reads only local
artifacts/parquet, trains three logistic-balanced candidates, computes
symbol/month/regime stability, and writes local-only reports.
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
from sklearn.metrics import f1_score, precision_recall_fscore_support

from local_automl_research import LOCAL_RESEARCH_ROOT, build_research_configs
from local_down_recall_focus_research import (
    FocusCandidate,
    focus_feature_families,
    make_feature_candidate,
    selected_lag_return_features,
)
from local_feature_ablation_research import (
    FeatureFamily,
    engineered_features_from_frame,
    ensure_local_research_path,
    model_config_for_family,
    tradeoff_note,
)
from local_feature_engineering_research import (
    DOWN_CLASS,
    OVERFIT_GAP_THRESHOLD,
    build_candidate_model,
    class_recall,
    fit_model,
    per_class_metrics,
)
from train_model import (
    ModelConfig,
    evaluate_model,
    load_yaml,
    split_xy,
    validate_training_data,
)


KEEPER_ROOT = LOCAL_RESEARCH_ROOT / "keeper_candidate_validation_v1"
DEFAULT_INPUT_PARQUET = (
    LOCAL_RESEARCH_ROOT
    / "feature_engineering_v1"
    / "engineered_training_features.parquet"
)
DEFAULT_FOCUS_LEADERBOARD = (
    LOCAL_RESEARCH_ROOT / "down_recall_focus_v1" / "leaderboard.csv"
)
DEFAULT_FOCUS_SUMMARY = (
    LOCAL_RESEARCH_ROOT / "down_recall_focus_v1" / "research_summary.json"
)
DEFAULT_REPORT_PATH = LOCAL_RESEARCH_ROOT / "keeper_candidate_validation_v1_report.md"
DEFAULT_LEADERBOARD_PATH = KEEPER_ROOT / "leaderboard.csv"
DEFAULT_SUMMARY_PATH = KEEPER_ROOT / "research_summary.json"

MAX_ALLOWED_F1_DROP = 0.005
MIN_DOWN_RECALL_GAIN = 0.005
MAX_ALLOWED_MIN_RECALL_DROP = 0.03
MAX_ALLOWED_GAP = 0.06
MAX_EXTRA_SYMBOL_GAP = 0.05
MAX_MONTHLY_STABILITY_DROP = 0.03
MIN_SLICE_ROWS = 60

LOCAL_ONLY_WRITES = {
    "wrote_gcs": False,
    "wrote_bigquery_output": False,
    "updated_registry": False,
    "production_predict_behavior_changed": False,
}


@dataclass(frozen=True)
class KeeperCandidate:
    feature_family: str
    model_name: str = "logistic_balanced"
    model_type: str = "logistic"
    class_weight: str = "balanced"

    @property
    def candidate_name(self) -> str:
        return f"{self.feature_family}__{self.model_name}"


@dataclass(frozen=True)
class SliceMetricSummary:
    monthly_f1_min: Optional[float]
    monthly_down_recall_min: Optional[float]
    monthly_f1_std: Optional[float]
    monthly_down_recall_std: Optional[float]
    symbol_f1_gap: Optional[float]
    symbol_down_recall_gap: Optional[float]
    regime_f1_min: Optional[float]
    regime_down_recall_min: Optional[float]


@dataclass(frozen=True)
class KeeperResult:
    candidate_name: str
    feature_family: str
    status: str
    feature_count: int
    engineered_feature_count: int
    validation_f1_macro: Optional[float]
    test_f1_macro: Optional[float]
    validation_down_recall: Optional[float]
    test_down_recall: Optional[float]
    per_class_recall_min: Optional[float]
    log_loss: Optional[float]
    brier_score: Optional[float]
    validation_test_gap: Optional[float]
    fold_std: Optional[float]
    monthly_f1_min: Optional[float]
    monthly_down_recall_min: Optional[float]
    symbol_f1_gap: Optional[float]
    symbol_down_recall_gap: Optional[float]
    overfit_flag: bool
    tradeoff_note: str
    stable_candidate: bool
    stability_reason: str
    artifact_path: Optional[str]
    reasons: list[str]

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local-only keeper candidate validation."
    )
    parser.add_argument("--config", default="feature_list.yml")
    parser.add_argument("--input-parquet", default=str(DEFAULT_INPUT_PARQUET))
    parser.add_argument("--artifact-dir", default=str(KEEPER_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--focus-leaderboard", default=str(DEFAULT_FOCUS_LEADERBOARD))
    parser.add_argument("--focus-summary", default=str(DEFAULT_FOCUS_SUMMARY))
    return parser.parse_args()


def candidate_specs() -> list[KeeperCandidate]:
    return [
        KeeperCandidate("original_only"),
        KeeperCandidate("microstructure_liquidity"),
        KeeperCandidate("microstructure_selected_lag_returns"),
    ]


def keeper_feature_families(engineered_features: list[str]) -> dict[str, FeatureFamily]:
    families = focus_feature_families(engineered_features)
    return {
        name: families[name]
        for name in [
            "original_only",
            "microstructure_liquidity",
            "microstructure_selected_lag_returns",
        ]
    }


def make_focus_candidate(candidate: KeeperCandidate) -> FocusCandidate:
    return FocusCandidate(
        feature_family=candidate.feature_family,
        model_name=candidate.model_name,
        model_type=candidate.model_type,
        class_weight=candidate.class_weight,
    )


def prediction_frame(
    *,
    frame: pd.DataFrame,
    model: Any,
    model_config: ModelConfig,
    split_name: str,
) -> pd.DataFrame:
    split = frame[frame[model_config.split_column] == split_name].copy()
    x = split[model_config.all_features]
    split["actual"] = split[model_config.target_name].astype(str).str.upper()
    split["predicted"] = pd.Series(model.predict(x), index=split.index).astype(str)
    split["hour_ts"] = pd.to_datetime(split["hour_ts"], errors="coerce", utc=True)
    split["month"] = split["hour_ts"].dt.strftime("%Y-%m")
    split["volatility_regime"] = volatility_regime(split)
    return split


def volatility_regime(frame: pd.DataFrame) -> pd.Series:
    high = pd.to_numeric(
        frame.get("volatility_regime_high_research", 0.0),
        errors="coerce",
    ).fillna(0.0)
    low = pd.to_numeric(
        frame.get("volatility_regime_low_research", 0.0),
        errors="coerce",
    ).fillna(0.0)
    return pd.Series(
        np.where(high >= 0.5, "high", np.where(low >= 0.5, "low", "normal")),
        index=frame.index,
    )


def slice_metric_frame(
    pred_frame: pd.DataFrame,
    *,
    group_column: str,
    labels: list[str],
    min_rows: int = MIN_SLICE_ROWS,
) -> pd.DataFrame:
    rows = []
    for group_name, group in pred_frame.groupby(group_column, dropna=False):
        if len(group) < min_rows:
            continue
        y_true = group["actual"].astype(str)
        y_pred = group["predicted"].astype(str)
        if y_true.nunique() < 2:
            continue
        per_class = per_class_metrics(y_true, y_pred, labels=labels)
        rows.append(
            {
                "group": str(group_name),
                "row_count": int(len(group)),
                "f1_macro": float(
                    f1_score(
                        y_true,
                        y_pred,
                        labels=labels,
                        average="macro",
                        zero_division=0,
                    )
                ),
                "down_recall": class_recall(per_class, DOWN_CLASS),
                "per_class_recall_min": float(per_class["recall"].min()),
            }
        )
    return pd.DataFrame(rows)


def metric_min(frame: pd.DataFrame, column: str) -> Optional[float]:
    if frame.empty or column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(values.min()) if not values.empty else None


def metric_std(frame: pd.DataFrame, column: str) -> Optional[float]:
    if frame.empty or column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(values.std(ddof=0)) if len(values) > 1 else 0.0 if len(values) == 1 else None


def metric_gap(frame: pd.DataFrame, column: str) -> Optional[float]:
    if frame.empty or column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.max() - values.min())


def summarize_slices(
    *,
    monthly: pd.DataFrame,
    symbol: pd.DataFrame,
    regime: pd.DataFrame,
) -> SliceMetricSummary:
    return SliceMetricSummary(
        monthly_f1_min=metric_min(monthly, "f1_macro"),
        monthly_down_recall_min=metric_min(monthly, "down_recall"),
        monthly_f1_std=metric_std(monthly, "f1_macro"),
        monthly_down_recall_std=metric_std(monthly, "down_recall"),
        symbol_f1_gap=metric_gap(symbol, "f1_macro"),
        symbol_down_recall_gap=metric_gap(symbol, "down_recall"),
        regime_f1_min=metric_min(regime, "f1_macro"),
        regime_down_recall_min=metric_min(regime, "down_recall"),
    )


def stability_decision(
    *,
    candidate: KeeperResult,
    baseline: Optional[KeeperResult],
) -> tuple[bool, str]:
    if baseline is None:
        return False, "missing_baseline"
    required = [
        candidate.validation_f1_macro,
        candidate.validation_down_recall,
        candidate.per_class_recall_min,
        candidate.validation_test_gap,
        candidate.monthly_f1_min,
        candidate.monthly_down_recall_min,
        candidate.symbol_f1_gap,
        candidate.symbol_down_recall_gap,
        baseline.validation_f1_macro,
        baseline.validation_down_recall,
        baseline.per_class_recall_min,
        baseline.monthly_f1_min,
        baseline.monthly_down_recall_min,
        baseline.symbol_f1_gap,
        baseline.symbol_down_recall_gap,
    ]
    if any(value is None for value in required):
        return False, "insufficient_stability_metrics"

    reasons = []
    if candidate.validation_f1_macro < baseline.validation_f1_macro - MAX_ALLOWED_F1_DROP:
        reasons.append("validation_f1_below_budget")
    if candidate.validation_down_recall < baseline.validation_down_recall + 0.005:
        reasons.append("down_recall_not_stably_higher")
    if candidate.per_class_recall_min < baseline.per_class_recall_min - MAX_ALLOWED_MIN_RECALL_DROP:
        reasons.append("per_class_recall_min_drops_too_much")
    if candidate.monthly_f1_min < baseline.monthly_f1_min - MAX_MONTHLY_STABILITY_DROP:
        reasons.append("monthly_f1_min_worse")
    if candidate.monthly_down_recall_min < baseline.monthly_down_recall_min - MAX_MONTHLY_STABILITY_DROP:
        reasons.append("monthly_down_recall_min_worse")
    if candidate.symbol_f1_gap > baseline.symbol_f1_gap + MAX_EXTRA_SYMBOL_GAP:
        reasons.append("symbol_f1_gap_worse")
    if candidate.symbol_down_recall_gap > baseline.symbol_down_recall_gap + MAX_EXTRA_SYMBOL_GAP:
        reasons.append("symbol_down_recall_gap_worse")
    if candidate.validation_test_gap is not None and candidate.validation_test_gap > MAX_ALLOWED_GAP:
        reasons.append("validation_test_gap_too_large")

    if reasons:
        return False, ",".join(reasons)
    return True, "stable_keeper_candidate"


def evaluate_candidate(
    *,
    candidate: KeeperCandidate,
    family: FeatureFamily,
    frame: pd.DataFrame,
    model_config: ModelConfig,
    training_config: Any,
    artifact_dir: Path,
) -> tuple[KeeperResult, dict[str, pd.DataFrame]]:
    try:
        family_config = model_config_for_family(model_config, family)
        validate_training_data(frame, family_config, training_config)
        model = build_candidate_model(make_feature_candidate(make_focus_candidate(candidate)), family_config)
        x_train, y_train, w_train = split_xy(frame, "train", family_config)
        x_val, y_val, _ = split_xy(frame, "validation", family_config)
        x_test, y_test, _ = split_xy(frame, "test", family_config)
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

        validation_predictions = prediction_frame(
            frame=frame,
            model=model,
            model_config=family_config,
            split_name="validation",
        )
        test_predictions = prediction_frame(
            frame=frame,
            model=model,
            model_config=family_config,
            split_name="test",
        )
        monthly = slice_metric_frame(
            validation_predictions,
            group_column="month",
            labels=family_config.valid_classes,
        )
        symbol = slice_metric_frame(
            validation_predictions,
            group_column="symbol",
            labels=family_config.valid_classes,
        )
        regime = slice_metric_frame(
            validation_predictions,
            group_column="volatility_regime",
            labels=family_config.valid_classes,
        )
        test_monthly = slice_metric_frame(
            test_predictions,
            group_column="month",
            labels=family_config.valid_classes,
        )
        test_symbol = slice_metric_frame(
            test_predictions,
            group_column="symbol",
            labels=family_config.valid_classes,
        )
        test_regime = slice_metric_frame(
            test_predictions,
            group_column="volatility_regime",
            labels=family_config.valid_classes,
        )
        summary = summarize_slices(monthly=monthly, symbol=symbol, regime=regime)

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
                "slice_summary": asdict(summary),
                "saved_at": utc_now_iso(),
            },
            artifact_path,
        )

        result = KeeperResult(
            candidate_name=candidate.candidate_name,
            feature_family=candidate.feature_family,
            status="completed",
            feature_count=len(family_config.all_features),
            engineered_feature_count=len(family.engineered_features),
            validation_f1_macro=float(validation_f1) if validation_f1 is not None else None,
            test_f1_macro=float(test_f1) if test_f1 is not None else None,
            validation_down_recall=validation_down,
            test_down_recall=class_recall(test_per_class, DOWN_CLASS),
            per_class_recall_min=validation_metrics.get("per_class_recall_min"),
            log_loss=validation_metrics.get("log_loss"),
            brier_score=validation_metrics.get("brier_score"),
            validation_test_gap=gap,
            fold_std=summary.monthly_f1_std,
            monthly_f1_min=summary.monthly_f1_min,
            monthly_down_recall_min=summary.monthly_down_recall_min,
            symbol_f1_gap=summary.symbol_f1_gap,
            symbol_down_recall_gap=summary.symbol_down_recall_gap,
            overfit_flag=bool(gap is not None and gap > OVERFIT_GAP_THRESHOLD),
            tradeoff_note="pending_baseline",
            stable_candidate=False,
            stability_reason="pending_baseline",
            artifact_path=str(artifact_path),
            reasons=[],
        )
        return result, {
            "validation_monthly": monthly,
            "validation_symbol": symbol,
            "validation_regime": regime,
            "test_monthly": test_monthly,
            "test_symbol": test_symbol,
            "test_regime": test_regime,
        }
    except Exception as exc:
        result = KeeperResult(
            candidate_name=candidate.candidate_name,
            feature_family=candidate.feature_family,
            status="skipped",
            feature_count=0,
            engineered_feature_count=len(family.engineered_features),
            validation_f1_macro=None,
            test_f1_macro=None,
            validation_down_recall=None,
            test_down_recall=None,
            per_class_recall_min=None,
            log_loss=None,
            brier_score=None,
            validation_test_gap=None,
            fold_std=None,
            monthly_f1_min=None,
            monthly_down_recall_min=None,
            symbol_f1_gap=None,
            symbol_down_recall_gap=None,
            overfit_flag=False,
            tradeoff_note="skipped",
            stable_candidate=False,
            stability_reason="skipped",
            artifact_path=None,
            reasons=[str(exc)],
        )
        return result, {}


def finalize_results(results: list[KeeperResult]) -> list[KeeperResult]:
    baseline = next(
        (
            result
            for result in results
            if result.candidate_name == "original_only__logistic_balanced"
            and result.status == "completed"
        ),
        None,
    )
    finalized = []
    for result in results:
        if result.status != "completed":
            finalized.append(result)
            continue
        stable, reason = stability_decision(candidate=result, baseline=baseline)
        note = tradeoff_note(
            validation_f1_macro=result.validation_f1_macro,
            validation_down_recall=result.validation_down_recall,
            baseline_validation_f1_macro=baseline.validation_f1_macro if baseline else None,
            baseline_validation_down_recall=baseline.validation_down_recall if baseline else None,
        )
        finalized.append(
            KeeperResult(
                **{
                    **result.to_row(),
                    "tradeoff_note": note,
                    "stable_candidate": stable,
                    "stability_reason": reason,
                }
            )
        )
    return finalized


def choose_best_by_validation(results: list[KeeperResult]) -> Optional[KeeperResult]:
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
            result.monthly_down_recall_min if result.monthly_down_recall_min is not None else -1.0,
        ),
        reverse=True,
    )[0]


def choose_best_stable(results: list[KeeperResult]) -> Optional[KeeperResult]:
    stable = [
        result for result in results
        if result.status == "completed" and result.stable_candidate
    ]
    if not stable:
        return None
    return sorted(
        stable,
        key=lambda result: (
            result.validation_down_recall if result.validation_down_recall is not None else -1.0,
            result.validation_f1_macro if result.validation_f1_macro is not None else -1.0,
            result.monthly_down_recall_min if result.monthly_down_recall_min is not None else -1.0,
        ),
        reverse=True,
    )[0]


def markdown_table(frame: pd.DataFrame, columns: Optional[list[str]] = None, max_rows: int = 50) -> str:
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
            if pd.isna(value):
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
    results: list[KeeperResult],
    slice_tables: dict[str, dict[str, pd.DataFrame]],
    best_validation: Optional[KeeperResult],
    best_stable: Optional[KeeperResult],
    input_parquet: Path,
    focus_summary: dict[str, Any],
    dry_run: bool,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    leaderboard = pd.DataFrame([result.to_row() for result in results])
    leaderboard.to_csv(DEFAULT_LEADERBOARD_PATH, index=False)

    slice_dir = artifact_dir / "slice_metrics"
    slice_dir.mkdir(parents=True, exist_ok=True)
    slice_paths: dict[str, dict[str, str]] = {}
    for candidate_name, tables in slice_tables.items():
        slice_paths[candidate_name] = {}
        for table_name, table in tables.items():
            path = slice_dir / f"{candidate_name}__{table_name}.csv"
            table.to_csv(path, index=False)
            slice_paths[candidate_name][table_name] = str(path)

    stable_frame = leaderboard[leaderboard["stable_candidate"] == True].copy() if not leaderboard.empty else pd.DataFrame()
    baseline = next(
        (
            result
            for result in results
            if result.candidate_name == "original_only__logistic_balanced"
        ),
        None,
    )
    micro = next(
        (
            result
            for result in results
            if result.candidate_name == "microstructure_liquidity__logistic_balanced"
        ),
        None,
    )
    selected = next(
        (
            result
            for result in results
            if result.candidate_name == "microstructure_selected_lag_returns__logistic_balanced"
        ),
        None,
    )

    summary = {
        "created_at": utc_now_iso(),
        "dry_run": dry_run,
        "input_parquet": str(input_parquet),
        "artifact_dir": str(artifact_dir),
        "leaderboard_path": str(DEFAULT_LEADERBOARD_PATH),
        "report_path": str(DEFAULT_REPORT_PATH),
        "slice_metric_paths": slice_paths,
        "candidate_names": [result.candidate_name for result in results],
        "best_validation_model": best_validation.to_row() if best_validation else None,
        "best_stable_model": best_stable.to_row() if best_stable else None,
        "stable_candidate_count": int(len(stable_frame)),
        "focus_best_keep_model": focus_summary.get("best_keep_model"),
        **LOCAL_ONLY_WRITES,
    }
    DEFAULT_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    production_recommendation = (
        "review_microstructure_selected_lag_returns"
        if best_stable and best_stable.candidate_name == "microstructure_selected_lag_returns__logistic_balanced"
        else "review_microstructure_liquidity"
        if best_stable and best_stable.candidate_name == "microstructure_liquidity__logistic_balanced"
        else "do_not_productionize_yet"
    )

    report = f"""# Local Keeper Candidate Validation V1

## Safety

- GCS output written: `false`
- BigQuery output written: `false`
- Registry updated: `false`
- Production predict behavior changed: `false`
- Dry run flag: `{dry_run}`
- Input parquet: `{input_parquet}`

## Leaderboard

Selection uses validation metrics and stability. Test is final reporting only.

{markdown_table(leaderboard, columns=[
    "candidate_name",
    "status",
    "validation_f1_macro",
    "test_f1_macro",
    "validation_down_recall",
    "test_down_recall",
    "per_class_recall_min",
    "log_loss",
    "brier_score",
    "validation_test_gap",
    "fold_std",
    "monthly_f1_min",
    "monthly_down_recall_min",
    "symbol_f1_gap",
    "symbol_down_recall_gap",
    "overfit_flag",
    "stable_candidate",
    "stability_reason",
])}

## Stable Candidates

{markdown_table(stable_frame, columns=[
    "candidate_name",
    "validation_f1_macro",
    "validation_down_recall",
    "monthly_f1_min",
    "monthly_down_recall_min",
    "symbol_f1_gap",
    "symbol_down_recall_gap",
    "stability_reason",
])}

## Comparison

- Baseline validation F1: `{baseline.validation_f1_macro if baseline else "N/A"}`
- Baseline validation DOWN recall: `{baseline.validation_down_recall if baseline else "N/A"}`
- Microstructure validation F1: `{micro.validation_f1_macro if micro else "N/A"}`
- Microstructure validation DOWN recall: `{micro.validation_down_recall if micro else "N/A"}`
- Selected micro+lag validation F1: `{selected.validation_f1_macro if selected else "N/A"}`
- Selected micro+lag validation DOWN recall: `{selected.validation_down_recall if selected else "N/A"}`

## Current Answers

- Best candidate by validation F1: `{best_validation.candidate_name if best_validation else "N/A"}`
- Best stable keeper candidate: `{best_stable.candidate_name if best_stable else "N/A"}`
- Candidate microstructure stable vs baseline: `{bool(micro and micro.stable_candidate)}`
- Candidate microstructure+selected lag stable vs baseline: `{bool(selected and selected.stable_candidate)}`
- Production recommendation: `{production_recommendation}`
- Keep logistic balanced as production candidate family: `true`
- Train BTC/ETH separately now: `not_yet; symbol stability should be reviewed in slice CSVs first`

## Recommendation

- Do not automatically productionize from this local sprint.
- If productionizing, start with the stable microstructure keeper family and keep Logistic balanced as the first production candidate.
- Avoid threshold policy for now; previous focus sprint rejected it due macro F1 collapse.
- Review monthly and symbol slice CSVs before dbt implementation.
"""
    DEFAULT_REPORT_PATH.write_text(report, encoding="utf-8")


def run_research(args: argparse.Namespace) -> list[KeeperResult]:
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
    families = keeper_feature_families(engineered_features)
    focus_summary = read_json(Path(args.focus_summary))

    print("[keeper] Candidates:")
    for candidate in candidate_specs():
        print(f"  - {candidate.candidate_name}")

    raw_results = []
    slice_tables: dict[str, dict[str, pd.DataFrame]] = {}
    for candidate in candidate_specs():
        result, tables = evaluate_candidate(
            candidate=candidate,
            family=families[candidate.feature_family],
            frame=frame,
            model_config=model_config,
            training_config=training_config,
            artifact_dir=artifact_dir,
        )
        raw_results.append(result)
        slice_tables[candidate.candidate_name] = tables

    results = finalize_results(raw_results)
    best_validation = choose_best_by_validation(results)
    best_stable = choose_best_stable(results)
    write_outputs(
        artifact_dir=artifact_dir,
        results=results,
        slice_tables=slice_tables,
        best_validation=best_validation,
        best_stable=best_stable,
        input_parquet=input_parquet,
        focus_summary=focus_summary,
        dry_run=args.dry_run,
    )
    print(f"[keeper] Leaderboard: {DEFAULT_LEADERBOARD_PATH}")
    print(f"[keeper] Summary: {DEFAULT_SUMMARY_PATH}")
    print(f"[keeper] Report: {DEFAULT_REPORT_PATH}")
    if best_validation:
        print(f"[keeper] Best validation candidate: {best_validation.candidate_name}")
    if best_stable:
        print(f"[keeper] Best stable candidate: {best_stable.candidate_name}")
    return results


def main() -> int:
    args = parse_args()
    run_research(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
