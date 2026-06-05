#!/usr/bin/env python3
"""
Local-only feature/label diagnostics for the crypto direction model.

This script is intentionally separate from production training/prediction.
It reads local research artifacts first, only queries BigQuery read-only if the
local training snapshot is missing, and writes a Markdown report under
ml/artifacts/local_research/.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    precision_recall_fscore_support,
)

from local_automl_research import (
    DEFAULT_LEADERBOARD_PATH,
    DEFAULT_SUMMARY_PATH,
    INPUT_SNAPSHOT_DIR,
    LOCAL_RESEARCH_ROOT,
    build_research_configs,
    load_or_query_training_data,
    snapshot_path,
)
from train_model import (
    ModelConfig,
    clean_features,
    evaluate_model,
    load_yaml,
    safe_predict_proba,
    split_xy,
)


DEFAULT_DIAGNOSTIC_REPORT_PATH = (
    LOCAL_RESEARCH_ROOT / "feature_label_diagnostic_report.md"
)
DEFAULT_LOGISTIC_ARTIFACT_PATH = (
    LOCAL_RESEARCH_ROOT
    / "full_sprint"
    / "models"
    / "logistic_baseline_all_history.joblib"
)

TARGET_DIRECTION_SCORE = {
    "DOWN": -1.0,
    "FLAT": 0.0,
    "UP": 1.0,
}


@dataclass(frozen=True)
class TrainingInput:
    frame: pd.DataFrame
    source: str
    path: Optional[Path]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local-only feature/label diagnostics."
    )
    parser.add_argument("--config", default="feature_list.yml")
    parser.add_argument("--cache-dir", default=str(INPUT_SNAPSHOT_DIR))
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--leaderboard", default=str(DEFAULT_LEADERBOARD_PATH))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument(
        "--logistic-artifact",
        default=str(DEFAULT_LOGISTIC_ARTIFACT_PATH),
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_DIAGNOSTIC_REPORT_PATH),
    )
    return parser.parse_args()


def ensure_local_research_path(path: Path, root: Path = LOCAL_RESEARCH_ROOT) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"Output path must be under {root_resolved}: {resolved}")
    return resolved


def load_training_input(
    *,
    cache_dir: Path,
    refresh_cache: bool,
    config: dict[str, Any],
) -> tuple[TrainingInput, Any, ModelConfig, Any]:
    bq_config, model_config, training_config = build_research_configs(config)
    cache_path = snapshot_path(cache_dir.resolve(), bq_config)
    used_cache = cache_path.exists() and not refresh_cache

    frame = load_or_query_training_data(
        cache_dir=cache_dir.resolve(),
        refresh_cache=refresh_cache,
        bq_config=bq_config,
        model_config=model_config,
    )
    source = "local_cache" if used_cache else "bigquery_read_only"
    path = cache_path if cache_path.exists() else None
    return TrainingInput(frame=frame, source=source, path=path), bq_config, model_config, training_config


def normalize_target(series: pd.Series) -> pd.Series:
    return series.astype(str).str.upper()


def class_distribution(
    frame: pd.DataFrame,
    *,
    target_column: str,
    group_column: Optional[str] = None,
) -> pd.DataFrame:
    data = frame.copy()
    data["_target"] = normalize_target(data[target_column])
    if group_column is None:
        data["_group"] = "all"
        group_names = ["_group"]
    else:
        data["_group"] = data[group_column].astype(str).fillna("UNKNOWN")
        group_names = ["_group"]

    counts = (
        data.groupby(group_names + ["_target"], dropna=False)
        .size()
        .reset_index(name="count")
    )
    totals = counts.groupby(group_names)["count"].transform("sum")
    counts["pct"] = counts["count"] / totals
    counts = counts.rename(columns={"_group": group_column or "group", "_target": "class"})
    return counts.sort_values([group_column or "group", "class"]).reset_index(drop=True)


def monthly_class_distribution(
    frame: pd.DataFrame,
    *,
    target_column: str,
    timestamp_column: str = "hour_ts",
) -> pd.DataFrame:
    data = frame.copy()
    data["month"] = pd.to_datetime(
        data[timestamp_column],
        errors="coerce",
        utc=True,
    ).dt.strftime("%Y-%m")
    data = data[data["month"].notna()]
    return class_distribution(data, target_column=target_column, group_column="month")


def feature_missing_rates(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    rows = []
    for feature in features:
        if feature not in frame.columns:
            rows.append(
                {
                    "feature": feature,
                    "missing_rate": 1.0,
                    "non_null_count": 0,
                }
            )
            continue
        rows.append(
            {
                "feature": feature,
                "missing_rate": float(frame[feature].isna().mean()),
                "non_null_count": int(frame[feature].notna().sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["missing_rate", "feature"],
        ascending=[False, True],
    )


def feature_completeness_by_split(
    frame: pd.DataFrame,
    *,
    features: list[str],
    split_column: str,
) -> pd.DataFrame:
    data = frame.copy()
    present_features = [feature for feature in features if feature in data.columns]
    if not present_features:
        raise ValueError("No feature columns found for completeness diagnostics.")

    data["_feature_completeness"] = data[present_features].notna().mean(axis=1)
    grouped = data.groupby(split_column)["_feature_completeness"]
    return grouped.agg(
        rows="count",
        mean="mean",
        p10=lambda values: float(values.quantile(0.10)),
        min="min",
    ).reset_index()


def infer_feature_group(feature_name: str) -> str:
    name = feature_name.lower()
    if any(token in name for token in ["etf", "ibit", "gbtc"]):
        return "etf"
    if any(token in name for token in ["stablecoin", "usdc", "usdt_supply"]):
        return "stablecoin"
    if any(token in name for token in ["funding", "basis", "leverage", "arbitrage"]):
        return "funding_derivatives"
    if "sentiment" in name or "social" in name:
        return "sentiment"
    if any(token in name for token in ["sp500", "nasdaq", "gold", "vix", "oil", "macro", "safe_haven"]):
        return "macro"
    if any(token in name for token in ["volume", "liquidity", "taker_buy"]):
        return "volume_liquidity"
    if any(token in name for token in ["return", "volatility", "momentum", "price"]):
        return "market_price"
    if "risk" in name or "stress" in name:
        return "risk_scores"
    if name == "symbol":
        return "symbol"
    return "other"


def target_correlations(
    frame: pd.DataFrame,
    *,
    numeric_features: list[str],
    target_column: str,
) -> pd.DataFrame:
    target_score = normalize_target(frame[target_column]).map(TARGET_DIRECTION_SCORE)
    rows = []
    for feature in numeric_features:
        values = pd.to_numeric(frame.get(feature), errors="coerce")
        valid = values.notna() & target_score.notna()
        corr = None
        if valid.sum() >= 3 and values.loc[valid].nunique() > 1:
            corr_value = values.loc[valid].corr(target_score.loc[valid])
            corr = None if pd.isna(corr_value) else float(corr_value)
        rows.append(
            {
                "feature": feature,
                "group": infer_feature_group(feature),
                "target_corr": corr,
                "abs_target_corr": None if corr is None else abs(corr),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["abs_target_corr", "feature"],
        ascending=[False, True],
        na_position="last",
    )


def source_feature_from_processed(
    processed_feature: str,
    *,
    model_config: ModelConfig,
) -> str:
    if processed_feature.startswith("num__"):
        return processed_feature.removeprefix("num__")
    if processed_feature.startswith("cat__"):
        suffix = processed_feature.removeprefix("cat__")
        for feature in model_config.categorical_features:
            if suffix == feature or suffix.startswith(f"{feature}_"):
                return feature
        return suffix.split("_", 1)[0]
    return processed_feature


def processed_feature_names(model: Any) -> list[str]:
    preprocessor = model.named_steps.get("preprocess")
    if preprocessor is None:
        return []
    try:
        return list(preprocessor.get_feature_names_out())
    except Exception:
        return []


def extract_logistic_importance(
    model: Any,
    *,
    model_config: ModelConfig,
) -> pd.DataFrame:
    estimator = model.named_steps.get("model")
    coef = getattr(estimator, "coef_", None)
    names = processed_feature_names(model)
    if coef is None or not names:
        return pd.DataFrame(
            columns=["processed_feature", "feature", "group", "importance"]
        )

    coef_array = np.asarray(coef)
    if coef_array.ndim == 1:
        scores = np.abs(coef_array)
    else:
        scores = np.mean(np.abs(coef_array), axis=0)

    limit = min(len(names), len(scores))
    rows = []
    for name, score in zip(names[:limit], scores[:limit]):
        source = source_feature_from_processed(name, model_config=model_config)
        rows.append(
            {
                "processed_feature": name,
                "feature": source,
                "group": infer_feature_group(source),
                "importance": float(score),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["importance", "processed_feature"],
        ascending=[False, True],
    )


def extract_tree_importance(
    model: Any,
    *,
    model_config: ModelConfig,
) -> pd.DataFrame:
    estimator = model.named_steps.get("model")
    inner_estimator = getattr(estimator, "estimator_", estimator)
    importances = getattr(inner_estimator, "feature_importances_", None)
    names = processed_feature_names(model)
    if importances is None or not names:
        return pd.DataFrame(
            columns=["processed_feature", "feature", "group", "importance"]
        )

    scores = np.asarray(importances)
    limit = min(len(names), len(scores))
    rows = []
    for name, score in zip(names[:limit], scores[:limit]):
        source = source_feature_from_processed(name, model_config=model_config)
        rows.append(
            {
                "processed_feature": name,
                "feature": source,
                "group": infer_feature_group(source),
                "importance": float(score),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["importance", "processed_feature"],
        ascending=[False, True],
    )


def summarize_feature_groups(
    *,
    correlations: pd.DataFrame,
    missing_rates: pd.DataFrame,
    logistic_importance: pd.DataFrame,
    tree_importance: pd.DataFrame,
) -> pd.DataFrame:
    base = correlations[["feature", "group", "abs_target_corr"]].merge(
        missing_rates[["feature", "missing_rate"]],
        on="feature",
        how="left",
    )

    if not logistic_importance.empty:
        logistic_grouped = (
            logistic_importance.groupby("feature")["importance"]
            .sum()
            .rename("logistic_importance")
        )
        base = base.merge(logistic_grouped, on="feature", how="left")
    else:
        base["logistic_importance"] = np.nan

    if not tree_importance.empty:
        tree_grouped = (
            tree_importance.groupby("feature")["importance"]
            .sum()
            .rename("tree_importance")
        )
        base = base.merge(tree_grouped, on="feature", how="left")
    else:
        base["tree_importance"] = np.nan

    return (
        base.groupby("group")
        .agg(
            feature_count=("feature", "count"),
            mean_abs_target_corr=("abs_target_corr", "mean"),
            max_abs_target_corr=("abs_target_corr", "max"),
            mean_missing_rate=("missing_rate", "mean"),
            logistic_importance=("logistic_importance", "sum"),
            tree_importance=("tree_importance", "sum"),
        )
        .reset_index()
        .sort_values(
            ["mean_abs_target_corr", "logistic_importance", "tree_importance"],
            ascending=[False, False, False],
        )
    )


def load_model_from_artifact(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    bundle = joblib.load(path)
    if isinstance(bundle, dict) and "model" in bundle:
        return bundle["model"]
    return bundle


def choose_tree_artifact(leaderboard: pd.DataFrame) -> Optional[Path]:
    if leaderboard.empty or "artifact_path" not in leaderboard.columns:
        return None
    tree_types = {"lightgbm", "xgboost", "extratrees", "hist_gradient_boosting"}
    completed = leaderboard[
        (leaderboard.get("status") == "completed")
        & (leaderboard.get("model_type").isin(tree_types))
    ].copy()
    if completed.empty:
        return None
    completed["selection_score"] = pd.to_numeric(
        completed["selection_score"],
        errors="coerce",
    )
    row = completed.sort_values("selection_score", ascending=False).iloc[0]
    artifact_path = row.get("artifact_path")
    if pd.isna(artifact_path):
        return None
    path = Path(str(artifact_path))
    return path if path.exists() else None


def split_error_summary(
    model: Any,
    frame: pd.DataFrame,
    *,
    split_name: str,
    model_config: ModelConfig,
) -> dict[str, Any]:
    x, y, _ = split_xy(frame, split_name, model_config)
    pred = pd.Series(model.predict(x), index=y.index).astype(str)
    labels = list(model_config.valid_classes)
    matrix = confusion_matrix(y, pred, labels=labels)
    precision, recall, f1, support = precision_recall_fscore_support(
        y,
        pred,
        labels=labels,
        zero_division=0,
    )
    metrics = evaluate_model(model, x, y)
    proba = safe_predict_proba(model, x)
    confidence = confidence_summary(y, pred, proba)

    per_class = pd.DataFrame(
        {
            "class": labels,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    )
    confusion = pd.DataFrame(matrix, index=labels, columns=labels)
    return {
        "split": split_name,
        "metrics": metrics,
        "per_class": per_class,
        "confusion": confusion,
        "top_confusions": top_confusions(confusion),
        "confidence": confidence,
    }


def confidence_summary(
    y_true: pd.Series,
    pred: pd.Series,
    proba: Optional[np.ndarray],
) -> dict[str, Optional[float]]:
    if proba is None or len(proba) == 0:
        return {
            "mean_confidence": None,
            "mean_confidence_correct": None,
            "mean_confidence_wrong": None,
            "high_confidence_rate": None,
            "high_confidence_accuracy": None,
        }

    confidence = pd.Series(np.max(proba, axis=1), index=y_true.index)
    correct = pred.astype(str).to_numpy() == y_true.astype(str).to_numpy()
    high_confidence = confidence >= 0.80
    return {
        "mean_confidence": float(confidence.mean()),
        "mean_confidence_correct": (
            float(confidence[correct].mean()) if bool(np.any(correct)) else None
        ),
        "mean_confidence_wrong": (
            float(confidence[~correct].mean()) if bool(np.any(~correct)) else None
        ),
        "high_confidence_rate": float(high_confidence.mean()),
        "high_confidence_accuracy": (
            float(np.mean(correct[high_confidence.to_numpy()]))
            if bool(high_confidence.any())
            else None
        ),
    }


def top_confusions(confusion: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    rows = []
    for actual in confusion.index:
        for predicted in confusion.columns:
            if actual == predicted:
                continue
            count = int(confusion.loc[actual, predicted])
            if count > 0:
                rows.append(
                    {
                        "actual": actual,
                        "predicted": predicted,
                        "count": count,
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["count", "actual", "predicted"],
        ascending=[False, True, True],
    ).head(limit) if rows else pd.DataFrame(columns=["actual", "predicted", "count"])


def markdown_table(frame: pd.DataFrame, columns: Optional[list[str]] = None, max_rows: int = 20) -> str:
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
        for column in headers:
            value = row[column]
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


def read_leaderboard(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def strongest_feature_group(group_summary: pd.DataFrame) -> str:
    if group_summary.empty:
        return "unknown"
    return str(group_summary.iloc[0]["group"])


def lowest_recall_class(error_summary: dict[str, Any]) -> str:
    per_class = error_summary.get("per_class", pd.DataFrame())
    if per_class.empty:
        return "unknown"
    row = per_class.sort_values(["recall", "class"]).iloc[0]
    return str(row["class"])


def write_diagnostic_report(
    *,
    report_path: Path,
    input_info: TrainingInput,
    bq_table: str,
    leaderboard: pd.DataFrame,
    summary: dict[str, Any],
    full_distribution: pd.DataFrame,
    split_distribution: pd.DataFrame,
    symbol_distribution: pd.DataFrame,
    monthly_distribution: pd.DataFrame,
    missing_rates: pd.DataFrame,
    completeness: pd.DataFrame,
    correlations: pd.DataFrame,
    logistic_importance: pd.DataFrame,
    tree_importance: pd.DataFrame,
    group_summary: pd.DataFrame,
    validation_errors: Optional[dict[str, Any]],
    test_errors: Optional[dict[str, Any]],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    best_model = summary.get("best_model") or {}
    weakest_class = (
        lowest_recall_class(test_errors)
        if test_errors is not None
        else "unknown"
    )
    strongest_group = strongest_feature_group(group_summary)

    calibration_note = "not_available"
    if test_errors is not None:
        metrics = test_errors.get("metrics", {})
        confidence = test_errors.get("confidence", {})
        log_loss_value = metrics.get("log_loss")
        brier_value = metrics.get("brier_score")
        wrong_confidence = confidence.get("mean_confidence_wrong")
        calibration_note = (
            f"log_loss={log_loss_value}, brier_score={brier_value}, "
            f"mean_confidence_wrong={wrong_confidence}"
        )

    content = f"""# Local Feature/Label Diagnostic Report

## Safety

- GCS output written: `false`
- BigQuery output written: `false`
- Registry updated: `false`
- Production predict behavior changed: `false`
- Training input source: `{input_info.source}`
- Training input cache: `{input_info.path or ""}`
- Training table: `{bq_table}`

## AutoML Context

- Best model from local sprint: `{best_model.get("candidate_name", "unknown")}`
- Best selection score: `{best_model.get("selection_score", "unknown")}`
- Best validation f1_macro: `{best_model.get("validation_f1_macro", "unknown")}`
- Best test f1_macro: `{best_model.get("test_f1_macro", "unknown")}`
- Weakest class in Logistic test recall: `{weakest_class}`
- Strongest feature group by simple target correlation: `{strongest_group}`

## Leaderboard Snapshot

{markdown_table(leaderboard, max_rows=20)}

## Target Distribution

### Overall

{markdown_table(full_distribution)}

### By Split

{markdown_table(split_distribution, max_rows=30)}

### By Symbol

{markdown_table(symbol_distribution, max_rows=30)}

### By Month

{markdown_table(monthly_distribution, max_rows=60)}

## Feature Quality

### Feature Completeness By Split

{markdown_table(completeness)}

### Highest Missing Rates

{markdown_table(missing_rates, max_rows=20)}

### Top Absolute Correlations With Target Direction Proxy

Target proxy: DOWN=-1, FLAT=0, UP=1. This is a diagnostic signal only, not a modeling assumption.

{markdown_table(correlations, max_rows=20)}

### Feature Group Summary

{markdown_table(group_summary, max_rows=20)}

## Model Error Diagnostics
"""

    if validation_errors is not None:
        content += f"""
### Logistic Validation Metrics

{markdown_table(pd.DataFrame([validation_errors["metrics"]]))}

### Logistic Validation Per-Class Metrics

{markdown_table(validation_errors["per_class"])}

### Logistic Validation Confusion Matrix

{markdown_table(validation_errors["confusion"].reset_index().rename(columns={"index": "actual"}))}

### Top Validation Confusions

{markdown_table(validation_errors["top_confusions"])}
"""

    if test_errors is not None:
        content += f"""
### Logistic Test Metrics

{markdown_table(pd.DataFrame([test_errors["metrics"]]))}

### Logistic Test Per-Class Metrics

{markdown_table(test_errors["per_class"])}

### Logistic Test Confusion Matrix

{markdown_table(test_errors["confusion"].reset_index().rename(columns={"index": "actual"}))}

### Top Test Confusions

{markdown_table(test_errors["top_confusions"])}

### Logistic Confidence Summary

{markdown_table(pd.DataFrame([test_errors["confidence"]]))}

Calibration note: `{calibration_note}`
"""

    content += f"""
## Feature Importance

### Logistic Top Coefficients

{markdown_table(logistic_importance, max_rows=20)}

### Tree/Boosting Top Importances

{markdown_table(tree_importance, max_rows=20)}

## Diagnosis

- Logistic likely wins because the current signal is mostly broad, linear-ish, and weak; stronger models can split on noisy local patterns without finding a stable gain.
- Tree/boosting candidates show low minimum class recall, which suggests at least one direction class is hard to separate with the current feature/label setup.
- If monthly or symbol distributions drift, a single global model may be averaging across regimes.
- If confidence on wrong predictions is high while log_loss/brier are weak, calibration should be treated as a first-class improvement track.
- Label noise is plausible when feature groups show weak target correlation and the weakest class has low recall despite balanced/class-weighted baselines.

## Recommended Next Improvements

1. Add regime features: rolling volatility/liquidity/trend regime flags, then evaluate by regime.
2. Add richer lag and rolling features: 1h/4h/8h/12h return lags, rolling max/min drawdown, rolling skew, and volatility-adjusted momentum.
3. Add symbol-aware features: BTC/ETH normalized z-scores, symbol-specific rolling baselines, and symbol interaction terms.
4. Add microstructure/liquidity features: taker buy pressure deltas, volume imbalance over multiple windows, spread/liquidity stress changes.
5. Add missing external context if available: ETF flow/proxy, stablecoin liquidity/supply proxy, market breadth, and macro lag features.

## Target Engineering To Test

1. Tune UP/DOWN/FLAT thresholds only on validation/walk-forward folds, not test.
2. Try volatility-adaptive thresholds so FLAT expands during noisy low-signal periods and contracts during strong regimes.
3. Try alternative horizons or triple-barrier style labels to reduce random 4h noise.

## Modeling Recommendations

- Test class_weight/sample_weight variants because the weakest class recall is the main failure mode.
- Test probability calibration after model selection; do not use calibration to select on test.
- Test BTC-only and ETH-only models if symbol/month distributions show drift.
- Do not promote a new model from this diagnostic alone.
- Run the next model sprint only after adding at least one target/feature improvement track above.
"""

    report_path.write_text(content, encoding="utf-8")


def run_diagnostics(args: argparse.Namespace) -> Path:
    report_path = ensure_local_research_path(Path(args.report))
    config_path = Path(args.config).resolve()
    config = load_yaml(config_path)

    input_info, bq_config, model_config, training_config = load_training_input(
        cache_dir=Path(args.cache_dir),
        refresh_cache=args.refresh_cache,
        config=config,
    )
    raw_df = input_info.frame
    cleaned_df = clean_features(raw_df, model_config, training_config)

    leaderboard = read_leaderboard(Path(args.leaderboard))
    summary = read_json(Path(args.summary))

    full_distribution = class_distribution(
        cleaned_df,
        target_column=model_config.target_name,
    )
    split_distribution = class_distribution(
        cleaned_df,
        target_column=model_config.target_name,
        group_column=model_config.split_column,
    )
    symbol_distribution = class_distribution(
        cleaned_df,
        target_column=model_config.target_name,
        group_column="symbol",
    )
    monthly_distribution = monthly_class_distribution(
        cleaned_df,
        target_column=model_config.target_name,
    )
    missing_rates = feature_missing_rates(raw_df, model_config.all_features)
    completeness = feature_completeness_by_split(
        raw_df,
        features=model_config.all_features,
        split_column=model_config.split_column,
    )
    correlations = target_correlations(
        cleaned_df,
        numeric_features=model_config.numeric_features,
        target_column=model_config.target_name,
    )

    logistic_model = load_model_from_artifact(Path(args.logistic_artifact))
    tree_artifact = choose_tree_artifact(leaderboard)
    tree_model = load_model_from_artifact(tree_artifact) if tree_artifact else None

    logistic_importance = (
        extract_logistic_importance(logistic_model, model_config=model_config)
        if logistic_model is not None
        else pd.DataFrame()
    )
    tree_importance = (
        extract_tree_importance(tree_model, model_config=model_config)
        if tree_model is not None
        else pd.DataFrame()
    )
    group_summary = summarize_feature_groups(
        correlations=correlations,
        missing_rates=missing_rates,
        logistic_importance=logistic_importance,
        tree_importance=tree_importance,
    )

    validation_errors = (
        split_error_summary(
            logistic_model,
            cleaned_df,
            split_name="validation",
            model_config=model_config,
        )
        if logistic_model is not None
        else None
    )
    test_errors = (
        split_error_summary(
            logistic_model,
            cleaned_df,
            split_name="test",
            model_config=model_config,
        )
        if logistic_model is not None
        else None
    )

    write_diagnostic_report(
        report_path=report_path,
        input_info=input_info,
        bq_table=bq_config.training_table_fqn,
        leaderboard=leaderboard,
        summary=summary,
        full_distribution=full_distribution,
        split_distribution=split_distribution,
        symbol_distribution=symbol_distribution,
        monthly_distribution=monthly_distribution,
        missing_rates=missing_rates,
        completeness=completeness,
        correlations=correlations,
        logistic_importance=logistic_importance,
        tree_importance=tree_importance,
        group_summary=group_summary,
        validation_errors=validation_errors,
        test_errors=test_errors,
    )

    print(f"[diagnostic] Report: {report_path}")
    print(f"[diagnostic] Training input source: {input_info.source}")
    if test_errors is not None:
        print(f"[diagnostic] Weakest test class: {lowest_recall_class(test_errors)}")
    print(f"[diagnostic] Strongest feature group: {strongest_feature_group(group_summary)}")
    return report_path


def main() -> int:
    args = parse_args()
    run_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
