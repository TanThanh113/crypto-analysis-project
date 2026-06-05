#!/usr/bin/env python3
"""
Local-only feature family ablation research for crypto direction.

The runner reads the Feature Engineering V1 parquet, evaluates feature-family
subsets with time-ordered production splits, and writes only local research
artifacts. It does not touch production feature contracts, dbt, GCS, BigQuery
outputs, model registry, or prediction behavior.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

from local_automl_research import LOCAL_RESEARCH_ROOT, build_research_configs
from local_feature_engineering_research import (
    DOWN_CLASS,
    OVERFIT_GAP_THRESHOLD,
    FeatureCandidate,
    build_candidate_model,
    class_recall,
    fit_model,
    per_class_metrics,
)
from time_split import apply_train_window
from train_model import (
    ModelConfig,
    evaluate_model,
    load_yaml,
    split_xy,
    validate_training_data,
)


ABLATION_ROOT = LOCAL_RESEARCH_ROOT / "feature_ablation_v1"
DEFAULT_INPUT_PARQUET = (
    LOCAL_RESEARCH_ROOT
    / "feature_engineering_v1"
    / "engineered_training_features.parquet"
)
DEFAULT_REPORT_PATH = LOCAL_RESEARCH_ROOT / "feature_ablation_v1_report.md"
DEFAULT_LEADERBOARD_PATH = ABLATION_ROOT / "leaderboard.csv"
DEFAULT_SUMMARY_PATH = ABLATION_ROOT / "research_summary.json"
DEFAULT_FEATURE_V1_SUMMARY_PATH = (
    LOCAL_RESEARCH_ROOT / "feature_engineering_v1" / "research_summary.json"
)
DEFAULT_FEATURE_V1_LEADERBOARD_PATH = (
    LOCAL_RESEARCH_ROOT / "feature_engineering_v1" / "leaderboard.csv"
)

LOCAL_ONLY_WRITES = {
    "wrote_gcs": False,
    "wrote_bigquery_output": False,
    "updated_registry": False,
    "production_predict_behavior_changed": False,
}


@dataclass(frozen=True)
class FeatureFamily:
    name: str
    description: str
    engineered_features: list[str]


@dataclass(frozen=True)
class AblationCandidate:
    feature_family: str
    model_name: str
    model_type: str
    train_window_days: Optional[int] = None
    class_weight: Optional[str] = None

    @property
    def candidate_name(self) -> str:
        return f"{self.feature_family}__{self.model_name}"


@dataclass(frozen=True)
class AblationResult:
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
    artifact_path: Optional[str]
    reasons: list[str]

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local-only feature family ablation research."
    )
    parser.add_argument("--config", default="feature_list.yml")
    parser.add_argument("--input-parquet", default=str(DEFAULT_INPUT_PARQUET))
    parser.add_argument("--artifact-dir", default=str(ABLATION_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--feature-v1-summary", default=str(DEFAULT_FEATURE_V1_SUMMARY_PATH))
    parser.add_argument("--feature-v1-leaderboard", default=str(DEFAULT_FEATURE_V1_LEADERBOARD_PATH))
    return parser.parse_args()


def ensure_local_research_path(path: Path) -> Path:
    resolved = path.resolve()
    root = LOCAL_RESEARCH_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path must stay under {root}: {resolved}")
    return resolved


def engineered_features_from_frame(
    frame: pd.DataFrame,
    original_numeric_features: list[str],
) -> list[str]:
    original = set(original_numeric_features)
    return sorted(
        column
        for column in frame.columns
        if column.endswith("_research") and column not in original
    )


def group_engineered_features(
    engineered_features: list[str],
) -> dict[str, FeatureFamily]:
    features = set(engineered_features)

    def pick(*tokens: str) -> list[str]:
        return sorted(
            feature
            for feature in features
            if any(token in feature for token in tokens)
        )

    lag_rolling_returns = pick(
        "return_1h_lag",
        "return_1h_rolling",
        "return_4h_lag",
        "return_24h_lag",
        "return_24h_symbol_zscore",
        "rolling_drawdown",
    )
    regime = pick(
        "volatility_regime",
        "liquidity_regime",
        "trend_regime",
    )
    symbol_aware = pick(
        "is_eth",
        "symbol_zscore",
    )
    microstructure_liquidity = pick(
        "quote_volume",
        "volume_zscore",
        "taker_buy",
        "liquidity_regime",
        "liquidity_risk_score_lag",
    )
    risk_macro_funding_lag = pick(
        "market_momentum_delta",
        "overall_risk_delta",
        "rolling_avg_overall_risk",
        "derivatives_risk_score_lag",
        "macro_risk_score_lag",
        "overall_risk_score_lag",
        "avg_funding_rate",
        "avg_basis",
    )

    return {
        "original_only": FeatureFamily(
            name="original_only",
            description="Original production feature contract only.",
            engineered_features=[],
        ),
        "lag_rolling_returns": FeatureFamily(
            name="lag_rolling_returns",
            description="Original features plus lagged/rolling return and drawdown features.",
            engineered_features=lag_rolling_returns,
        ),
        "regime_features": FeatureFamily(
            name="regime_features",
            description="Original features plus volatility/liquidity/trend regime flags.",
            engineered_features=regime,
        ),
        "symbol_aware_features": FeatureFamily(
            name="symbol_aware_features",
            description="Original features plus symbol-aware z-scores and ETH interactions.",
            engineered_features=symbol_aware,
        ),
        "microstructure_liquidity": FeatureFamily(
            name="microstructure_liquidity",
            description="Original features plus volume, taker-buy, and liquidity pressure features.",
            engineered_features=microstructure_liquidity,
        ),
        "risk_macro_funding_lags": FeatureFamily(
            name="risk_macro_funding_lags",
            description="Original features plus lagged risk, macro, funding, and basis features.",
            engineered_features=risk_macro_funding_lag,
        ),
        "all_engineered_features": FeatureFamily(
            name="all_engineered_features",
            description="Original features plus every engineered feature from V1.",
            engineered_features=sorted(engineered_features),
        ),
    }


def model_config_for_family(
    model_config: ModelConfig,
    family: FeatureFamily,
) -> ModelConfig:
    numeric_features = list(
        dict.fromkeys(model_config.numeric_features + family.engineered_features)
    )
    return replace(model_config, numeric_features=numeric_features)


def candidate_specs() -> list[AblationCandidate]:
    """Order is intentional: max-candidates=12 still covers every family."""

    return [
        AblationCandidate("original_only", "logistic_baseline", "logistic", class_weight=None),
        AblationCandidate("original_only", "logistic_balanced", "logistic", class_weight="balanced"),
        AblationCandidate("original_only", "extratrees", "extratrees", class_weight="balanced"),
        AblationCandidate("lag_rolling_returns", "logistic_balanced", "logistic", class_weight="balanced"),
        AblationCandidate("regime_features", "logistic_balanced", "logistic", class_weight="balanced"),
        AblationCandidate("symbol_aware_features", "logistic_balanced", "logistic", class_weight="balanced"),
        AblationCandidate("microstructure_liquidity", "logistic_balanced", "logistic", class_weight="balanced"),
        AblationCandidate("risk_macro_funding_lags", "logistic_balanced", "logistic", class_weight="balanced"),
        AblationCandidate("all_engineered_features", "logistic_balanced", "logistic", class_weight="balanced"),
        AblationCandidate("lag_rolling_returns", "extratrees", "extratrees", class_weight="balanced"),
        AblationCandidate("all_engineered_features", "extratrees", "extratrees", class_weight="balanced"),
        AblationCandidate("all_engineered_features", "lightgbm_rolling_90d", "lightgbm", train_window_days=90),
    ]


def select_candidates(max_candidates: Optional[int]) -> list[AblationCandidate]:
    candidates = candidate_specs()
    if max_candidates is None:
        return candidates
    return candidates[:max_candidates]


def make_feature_candidate(candidate: AblationCandidate) -> FeatureCandidate:
    return FeatureCandidate(
        name=candidate.candidate_name,
        model_type=candidate.model_type,
        train_window_days=candidate.train_window_days,
        class_weight=candidate.class_weight,
    )


def tradeoff_note(
    *,
    validation_f1_macro: Optional[float],
    validation_down_recall: Optional[float],
    baseline_validation_f1_macro: Optional[float],
    baseline_validation_down_recall: Optional[float],
) -> str:
    if (
        validation_f1_macro is None
        or validation_down_recall is None
        or baseline_validation_f1_macro is None
        or baseline_validation_down_recall is None
    ):
        return "insufficient_baseline"

    f1_delta = validation_f1_macro - baseline_validation_f1_macro
    down_delta = validation_down_recall - baseline_validation_down_recall
    if f1_delta >= 0 and down_delta >= 0:
        return "improves_macro_f1_and_down_recall"
    if f1_delta >= 0 and down_delta < 0:
        return "macro_f1_up_down_recall_down"
    if f1_delta < 0 and down_delta >= 0:
        return "down_recall_up_macro_f1_down"
    return "worse_macro_f1_and_down_recall"


def evaluate_candidate(
    *,
    candidate: AblationCandidate,
    family: FeatureFamily,
    frame: pd.DataFrame,
    model_config: ModelConfig,
    training_config: Any,
    artifact_dir: Path,
    baseline_validation_f1_macro: Optional[float],
    baseline_validation_down_recall: Optional[float],
) -> AblationResult:
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
                "saved_at": utc_now_iso(),
            },
            artifact_path,
        )

        return AblationResult(
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
                baseline_validation_f1_macro=baseline_validation_f1_macro,
                baseline_validation_down_recall=baseline_validation_down_recall,
            ),
            artifact_path=str(artifact_path),
            reasons=[],
        )
    except Exception as exc:
        return AblationResult(
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
            artifact_path=None,
            reasons=[str(exc)],
        )


def choose_best(results: list[AblationResult]) -> Optional[AblationResult]:
    completed = [
        result for result in results
        if result.status == "completed" and result.selection_score is not None
    ]
    if not completed:
        return None
    return sorted(
        completed,
        key=lambda result: (
            result.selection_score if result.selection_score is not None else -1.0,
            result.validation_down_recall if result.validation_down_recall is not None else -1.0,
            result.per_class_recall_min if result.per_class_recall_min is not None else -1.0,
            -(result.log_loss if result.log_loss is not None else 999.0),
        ),
        reverse=True,
    )[0]


def family_summary_frame(results: list[AblationResult]) -> pd.DataFrame:
    rows = [result.to_row() for result in results if result.status == "completed"]
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    idx = (
        frame.sort_values(
            [
                "feature_family",
                "validation_f1_macro",
                "validation_down_recall",
                "per_class_recall_min",
            ],
            ascending=[True, False, False, False],
        )
        .groupby("feature_family", as_index=False)
        .head(1)
        .index
    )
    return frame.loc[idx].sort_values(
        ["validation_f1_macro", "validation_down_recall"],
        ascending=[False, False],
    )


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
    results: list[AblationResult],
    best: Optional[AblationResult],
    families: dict[str, FeatureFamily],
    input_parquet: Path,
    feature_v1_summary: dict[str, Any],
    dry_run: bool,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    leaderboard = pd.DataFrame([result.to_row() for result in results])
    leaderboard.to_csv(DEFAULT_LEADERBOARD_PATH, index=False)
    family_summary = family_summary_frame(results)

    baseline = feature_v1_summary.get("baseline_reference", {})
    original_balanced = next(
        (
            result
            for result in results
            if result.candidate_name == "original_only__logistic_balanced"
            and result.status == "completed"
        ),
        None,
    )
    best_down = None
    completed = [result for result in results if result.status == "completed"]
    if completed:
        best_down = sorted(
            completed,
            key=lambda result: (
                result.validation_down_recall if result.validation_down_recall is not None else -1.0,
                result.validation_f1_macro if result.validation_f1_macro is not None else -1.0,
            ),
            reverse=True,
        )[0]

    summary = {
        "created_at": utc_now_iso(),
        "dry_run": dry_run,
        "input_parquet": str(input_parquet),
        "artifact_dir": str(artifact_dir),
        "leaderboard_path": str(DEFAULT_LEADERBOARD_PATH),
        "report_path": str(DEFAULT_REPORT_PATH),
        "feature_families": {
            name: asdict(family)
            for name, family in families.items()
        },
        "candidate_names": [result.candidate_name for result in results],
        "best_model": best.to_row() if best else None,
        "best_down_recall_model": best_down.to_row() if best_down else None,
        "family_summary": family_summary.to_dict(orient="records"),
        "feature_v1_baseline_reference": baseline,
        "original_balanced_reference": (
            original_balanced.to_row() if original_balanced else None
        ),
        **LOCAL_ONLY_WRITES,
    }
    DEFAULT_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    report = f"""# Local Feature Family Ablation V1

## Safety

- GCS output written: `false`
- BigQuery output written: `false`
- Registry updated: `false`
- Production predict behavior changed: `false`
- Dry run flag: `{dry_run}`
- Input parquet: `{input_parquet}`

## Feature Families

{markdown_table(pd.DataFrame([
    {
        "feature_family": family.name,
        "engineered_feature_count": len(family.engineered_features),
        "description": family.description,
    }
    for family in families.values()
]))}

## Leaderboard

Selection uses validation macro F1 first, then validation DOWN recall and minimum per-class recall. Test is final report only.

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
])}

## Best Per Feature Family

{markdown_table(family_summary, columns=[
    "feature_family",
    "candidate_name",
    "validation_f1_macro",
    "test_f1_macro",
    "validation_down_recall",
    "test_down_recall",
    "per_class_recall_min",
    "validation_test_gap",
    "tradeoff_note",
])}

## Current Answers

- Best by validation macro F1: `{best.candidate_name if best else "N/A"}`
- Best feature family by validation macro F1: `{best.feature_family if best else "N/A"}`
- Best by validation DOWN recall: `{best_down.candidate_name if best_down else "N/A"}`
- Original balanced reference in this ablation: `{original_balanced.candidate_name if original_balanced else "N/A"}`
- Should not promote automatically: `true`

## Recommendation

- Prefer a feature family only if validation macro F1 improves without a large validation-test gap.
- Treat DOWN recall gains as a trade-off when macro F1 drops.
- Do not productionize noisy families from this smoke ablation alone.
- Consider BTC/ETH-specific training if symbol-aware features rank well or if recall trade-offs differ by symbol in a follow-up diagnostic.
- Re-run AutoML only after selecting one or two feature families from this ablation.
"""
    DEFAULT_REPORT_PATH.write_text(report, encoding="utf-8")


def run_research(args: argparse.Namespace) -> list[AblationResult]:
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
    families = group_engineered_features(engineered_features)
    candidates = select_candidates(args.max_candidates)

    feature_v1_summary = read_json(Path(args.feature_v1_summary))
    baseline = feature_v1_summary.get("best_model", {})
    baseline_validation_f1 = baseline.get("validation_f1_macro")
    baseline_validation_down = baseline.get("validation_down_recall")

    print("[ablation-v1] Feature families:")
    for family in families.values():
        print(f"  - {family.name}: {len(family.engineered_features)} engineered features")
    print("[ablation-v1] Candidates:")
    for candidate in candidates:
        print(f"  - {candidate.candidate_name}")

    results = [
        evaluate_candidate(
            candidate=candidate,
            family=families[candidate.feature_family],
            frame=frame,
            model_config=model_config,
            training_config=training_config,
            artifact_dir=artifact_dir,
            baseline_validation_f1_macro=baseline_validation_f1,
            baseline_validation_down_recall=baseline_validation_down,
        )
        for candidate in candidates
    ]
    best = choose_best(results)
    write_outputs(
        artifact_dir=artifact_dir,
        results=results,
        best=best,
        families=families,
        input_parquet=input_parquet,
        feature_v1_summary=feature_v1_summary,
        dry_run=args.dry_run,
    )

    print(f"[ablation-v1] Leaderboard: {DEFAULT_LEADERBOARD_PATH}")
    print(f"[ablation-v1] Summary: {DEFAULT_SUMMARY_PATH}")
    print(f"[ablation-v1] Report: {DEFAULT_REPORT_PATH}")
    if best is not None:
        print(f"[ablation-v1] Best candidate: {best.candidate_name}")
    return results


def main() -> int:
    args = parse_args()
    run_research(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
