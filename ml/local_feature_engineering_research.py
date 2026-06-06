#!/usr/bin/env python3
"""
Local-only feature engineering research sprint for crypto direction.

This runner does not change production training or prediction behavior. It reads
the cached training snapshot when available, builds research-only features in a
local dataframe, evaluates a small candidate set with the existing time splits,
and writes only local artifacts under ml/artifacts/local_research/.
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
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_recall_fscore_support
from sklearn.pipeline import Pipeline

from local_automl_research import (
    DEFAULT_LEADERBOARD_PATH as AUTOML_LEADERBOARD_PATH,
    INPUT_SNAPSHOT_DIR,
    LOCAL_RESEARCH_ROOT,
    LabelEncodedClassifier,
    build_research_configs,
    load_or_query_training_data,
    make_xgboost_pipeline,
    snapshot_path,
)
from mlflow_utils import handle_mlflow_error, is_mlflow_enabled, log_training_run
from time_split import apply_train_window
from train_model import (
    ModelConfig,
    clean_features,
    evaluate_model,
    get_sample_weight,
    load_yaml,
    make_preprocessor,
    safe_predict_proba,
    split_xy,
    validate_training_data,
)


FEATURE_ENGINEERING_ROOT = LOCAL_RESEARCH_ROOT / "feature_engineering_v1"
DEFAULT_REPORT_PATH = LOCAL_RESEARCH_ROOT / "feature_engineering_v1_report.md"
DEFAULT_LEADERBOARD_PATH = FEATURE_ENGINEERING_ROOT / "leaderboard.csv"
DEFAULT_SUMMARY_PATH = FEATURE_ENGINEERING_ROOT / "research_summary.json"
DEFAULT_ENGINEERED_PARQUET_PATH = FEATURE_ENGINEERING_ROOT / "engineered_training_features.parquet"
DEFAULT_PRODUCTION_LOGISTIC_ARTIFACT = (
    LOCAL_RESEARCH_ROOT
    / "full_sprint"
    / "models"
    / "logistic_baseline_all_history.joblib"
)

LOCAL_ONLY_WRITES = {
    "wrote_gcs": False,
    "wrote_bigquery_output": False,
    "updated_registry": False,
    "production_predict_behavior_changed": False,
}
OVERFIT_GAP_THRESHOLD = 0.08
DOWN_CLASS = "DOWN"


@dataclass(frozen=True)
class FeatureCandidate:
    name: str
    model_type: str
    train_window_days: Optional[int] = None
    class_weight: Optional[str] = None


@dataclass(frozen=True)
class FeatureCandidateResult:
    candidate_name: str
    model_type: str
    status: str
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
    artifact_path: Optional[str]
    threshold_policy: Optional[dict[str, Any]]
    reasons: list[str]

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BaselineReference:
    validation_f1_macro: Optional[float]
    test_f1_macro: Optional[float]
    validation_down_recall: Optional[float]
    test_down_recall: Optional[float]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local-only feature engineering research V1."
    )
    parser.add_argument("--config", default="feature_list.yml")
    parser.add_argument("--input-cache-dir", default=str(INPUT_SNAPSHOT_DIR))
    parser.add_argument("--artifact-dir", default=str(FEATURE_ENGINEERING_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--write-engineered-parquet", action="store_true", default=True)
    parser.add_argument(
        "--production-logistic-artifact",
        default=str(DEFAULT_PRODUCTION_LOGISTIC_ARTIFACT),
    )
    return parser.parse_args()


def ensure_local_research_path(path: Path) -> Path:
    resolved = path.resolve()
    root = LOCAL_RESEARCH_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path must stay under {root}: {resolved}")
    return resolved


def load_training_frame(
    *,
    config: dict[str, Any],
    input_cache_dir: Path,
    refresh_cache: bool,
) -> tuple[pd.DataFrame, str, Path, Any, ModelConfig, Any]:
    bq_config, model_config, training_config = build_research_configs(config)
    cache_dir = input_cache_dir.resolve()
    cache_path = snapshot_path(cache_dir, bq_config)
    source = "local_cache" if cache_path.exists() and not refresh_cache else "bigquery_read_only"
    frame = load_or_query_training_data(
        cache_dir=cache_dir,
        refresh_cache=refresh_cache,
        bq_config=bq_config,
        model_config=model_config,
    )
    return frame, source, cache_path, bq_config, model_config, training_config


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _shifted(grouped: Any, column: str, periods: int) -> pd.Series:
    return grouped[column].shift(periods)


def _rolling_from_past(
    frame: pd.DataFrame,
    *,
    symbol_column: str,
    values: pd.Series,
    window: int,
    min_periods: int,
    agg: str,
) -> pd.Series:
    rolling = values.groupby(frame[symbol_column], sort=False).rolling(
        window=window,
        min_periods=min_periods,
    )
    if agg == "mean":
        result = rolling.mean()
    elif agg == "std":
        result = rolling.std()
    elif agg == "sum":
        result = rolling.sum()
    elif agg == "max":
        result = rolling.max()
    elif agg == "min":
        result = rolling.min()
    elif agg == "q33":
        result = rolling.quantile(0.33)
    elif agg == "q66":
        result = rolling.quantile(0.66)
    else:
        raise ValueError(f"Unsupported rolling agg: {agg}")
    return result.reset_index(level=0, drop=True)


def build_research_features(
    frame: pd.DataFrame,
    *,
    model_config: ModelConfig,
) -> tuple[pd.DataFrame, list[str]]:
    """Build research-only features from past/current available columns.

    Lag/rolling features use symbol-grouped shift before rolling, so the row at
    time t never uses return/volume values from t+1 or later.
    """

    engineered = frame.copy()
    engineered["hour_ts"] = pd.to_datetime(engineered["hour_ts"], errors="coerce", utc=True)
    engineered = engineered.sort_values(["symbol", "hour_ts"]).reset_index(drop=True)

    for column in model_config.numeric_features:
        engineered[column] = _numeric(engineered, column)

    grouped = engineered.groupby("symbol", sort=False)
    new_features: list[str] = []

    def add(name: str, values: pd.Series) -> None:
        engineered[name] = pd.to_numeric(values, errors="coerce")
        new_features.append(name)

    if "return_1h" in engineered.columns:
        for lag in [1, 4, 8, 12]:
            add(f"return_1h_lag_{lag}h_research", _shifted(grouped, "return_1h", lag))

        past_return_1h = _shifted(grouped, "return_1h", 1)
        for window in [4, 12, 24]:
            add(
                f"return_1h_rolling_mean_{window}h_research",
                _rolling_from_past(
                    engineered,
                    symbol_column="symbol",
                    values=past_return_1h,
                    window=window,
                    min_periods=max(2, window // 2),
                    agg="mean",
                ),
            )
            add(
                f"return_1h_rolling_sum_{window}h_research",
                _rolling_from_past(
                    engineered,
                    symbol_column="symbol",
                    values=past_return_1h,
                    window=window,
                    min_periods=max(2, window // 2),
                    agg="sum",
                ),
            )

    if "return_4h" in engineered.columns:
        add("return_4h_lag_1h_research", _shifted(grouped, "return_4h", 1))
        add("return_4h_lag_4h_research", _shifted(grouped, "return_4h", 4))

    if "return_24h" in engineered.columns:
        past_return_24h = _shifted(grouped, "return_24h", 1)
        add("return_24h_lag_1h_research", past_return_24h)
        add(
            "return_24h_symbol_zscore_research",
            expanding_symbol_zscore(engineered, past_return_24h),
        )

    if "log_return_1h" in engineered.columns:
        log_return = _numeric(engineered, "log_return_1h").fillna(0.0)
        cumulative = log_return.groupby(engineered["symbol"], sort=False).cumsum()
        past_cumulative = cumulative.groupby(engineered["symbol"], sort=False).shift(1)
        rolling_peak = _rolling_from_past(
            engineered,
            symbol_column="symbol",
            values=past_cumulative,
            window=24,
            min_periods=6,
            agg="max",
        )
        add("rolling_drawdown_24h_research", past_cumulative - rolling_peak)

    if "rolling_volatility_24h" in engineered.columns:
        past_volatility = _shifted(grouped, "rolling_volatility_24h", 1)
        vol_q33 = _rolling_from_past(
            engineered,
            symbol_column="symbol",
            values=past_volatility,
            window=24 * 90,
            min_periods=24,
            agg="q33",
        )
        vol_q66 = _rolling_from_past(
            engineered,
            symbol_column="symbol",
            values=past_volatility,
            window=24 * 90,
            min_periods=24,
            agg="q66",
        )
        add("rolling_volatility_24h_lag_1h_research", past_volatility)
        add("volatility_regime_low_research", (past_volatility <= vol_q33).astype(float))
        add("volatility_regime_high_research", (past_volatility >= vol_q66).astype(float))

    if "rolling_volatility_7d" in engineered.columns:
        past_vol_7d = _shifted(grouped, "rolling_volatility_7d", 1)
        add("rolling_volatility_7d_lag_1h_research", past_vol_7d)
        add("rolling_volatility_7d_symbol_zscore_research", expanding_symbol_zscore(engineered, past_vol_7d))

    if "quote_volume" in engineered.columns:
        past_volume = _shifted(grouped, "quote_volume", 1)
        volume_mean = _rolling_from_past(
            engineered,
            symbol_column="symbol",
            values=past_volume,
            window=24,
            min_periods=6,
            agg="mean",
        )
        volume_std = _rolling_from_past(
            engineered,
            symbol_column="symbol",
            values=past_volume,
            window=24,
            min_periods=6,
            agg="std",
        ).replace(0, np.nan)
        volume_z = (past_volume - volume_mean) / volume_std
        add("quote_volume_lag_1h_research", past_volume)
        add("quote_volume_zscore_24h_research", volume_z)
        add("liquidity_regime_high_research", (volume_z >= 1.0).astype(float))
        add("liquidity_regime_low_research", (volume_z <= -1.0).astype(float))

    if "quote_volume_24h" in engineered.columns:
        add("quote_volume_24h_lag_1h_research", _shifted(grouped, "quote_volume_24h", 1))

    if "volume_zscore_24h" in engineered.columns:
        add("volume_zscore_24h_lag_1h_research", _shifted(grouped, "volume_zscore_24h", 1))

    if "taker_buy_quote_ratio" in engineered.columns:
        ratio_lag_1 = _shifted(grouped, "taker_buy_quote_ratio", 1)
        add("taker_buy_quote_ratio_lag_1h_research", ratio_lag_1)
        add("taker_buy_pressure_delta_4h_research", ratio_lag_1 - _shifted(grouped, "taker_buy_quote_ratio", 5))
        add("taker_buy_pressure_delta_12h_research", ratio_lag_1 - _shifted(grouped, "taker_buy_quote_ratio", 13))

    if "market_momentum_score" in engineered.columns:
        momentum_lag = _shifted(grouped, "market_momentum_score", 1)
        add("market_momentum_score_lag_1h_research", momentum_lag)
        add("trend_regime_up_research", (momentum_lag > 0).astype(float))
        add("trend_regime_down_research", (momentum_lag < 0).astype(float))

    for column in [
        "market_momentum_delta_24h",
        "overall_risk_delta_24h",
        "rolling_avg_overall_risk_24h",
        "derivatives_risk_score",
        "liquidity_risk_score",
        "macro_risk_score",
        "overall_risk_score",
        "avg_funding_rate_usdt",
        "avg_basis_pct",
    ]:
        if column in engineered.columns:
            add(f"{column}_lag_1h_research", _shifted(grouped, column, 1))

    is_eth = engineered["symbol"].astype(str).str.upper().eq("ETH").astype(float)
    add("is_eth_research", is_eth)
    for column in [
        "return_24h_lag_1h_research",
        "rolling_volatility_24h_lag_1h_research",
        "quote_volume_zscore_24h_research",
        "market_momentum_score_lag_1h_research",
    ]:
        if column in engineered.columns:
            add(f"is_eth_x_{column}", is_eth * engineered[column])

    # Keep row ordering friendly for existing split/time validation.
    engineered = engineered.sort_values(["hour_ts", "symbol"]).reset_index(drop=True)
    return engineered, new_features


def expanding_symbol_zscore(frame: pd.DataFrame, values: pd.Series, min_periods: int = 24) -> pd.Series:
    grouped_values = values.groupby(frame["symbol"], sort=False)
    mean = grouped_values.expanding(min_periods=min_periods).mean().reset_index(level=0, drop=True)
    std = grouped_values.expanding(min_periods=min_periods).std().reset_index(level=0, drop=True)
    return (values - mean) / std.replace(0, np.nan)


def research_model_config(
    model_config: ModelConfig,
    engineered_features: list[str],
) -> ModelConfig:
    numeric_features = list(dict.fromkeys(model_config.numeric_features + engineered_features))
    return replace(model_config, numeric_features=numeric_features)


def candidate_specs() -> list[FeatureCandidate]:
    return [
        FeatureCandidate("logistic_research_baseline", "logistic", None, class_weight=None),
        FeatureCandidate("logistic_class_weight_balanced", "logistic", None, class_weight="balanced"),
        FeatureCandidate("lightgbm_rolling_90d", "lightgbm", 90),
        FeatureCandidate("extratrees_all_history_baseline", "extratrees", None, class_weight="balanced"),
        FeatureCandidate("xgboost_rolling_90d", "xgboost", 90),
    ]


def select_candidates(max_candidates: Optional[int]) -> list[FeatureCandidate]:
    candidates = candidate_specs()
    if max_candidates is None:
        return candidates
    return candidates[:max_candidates]


def make_logistic_pipeline(model_config: ModelConfig, class_weight: Optional[str]) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", make_preprocessor(model_config, scale_numeric=True)),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    class_weight=class_weight,
                    solver="lbfgs",
                    random_state=model_config.random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def make_lightgbm_pipeline(model_config: ModelConfig) -> Pipeline:
    from train_model import build_models

    return build_models(model_config)["lightgbm_classifier"]


def make_extratrees_pipeline(model_config: ModelConfig) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", make_preprocessor(model_config, scale_numeric=False)),
            (
                "model",
                ExtraTreesClassifier(
                    n_estimators=300,
                    max_features="sqrt",
                    min_samples_leaf=8,
                    class_weight="balanced",
                    random_state=model_config.random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def build_candidate_model(candidate: FeatureCandidate, model_config: ModelConfig) -> Pipeline:
    if candidate.model_type == "logistic":
        return make_logistic_pipeline(model_config, candidate.class_weight)
    if candidate.model_type == "lightgbm":
        return make_lightgbm_pipeline(model_config)
    if candidate.model_type == "extratrees":
        return make_extratrees_pipeline(model_config)
    if candidate.model_type == "xgboost":
        model = make_xgboost_pipeline(
            model_config,
            {
                "n_estimators": 180,
                "max_depth": 4,
                "learning_rate": 0.04,
                "subsample": 0.85,
                "colsample_bytree": 0.85,
                "reg_alpha": 0.05,
                "reg_lambda": 1.0,
            },
        )
        # make_xgboost_pipeline already wraps labels, this narrows typing only.
        return model
    raise ValueError(f"Unsupported candidate model_type={candidate.model_type}")


def fit_model(
    model: Pipeline,
    x: pd.DataFrame,
    y: pd.Series,
    sample_weight: Optional[np.ndarray],
) -> Pipeline:
    fit_kwargs = {}
    if sample_weight is not None:
        fit_kwargs["model__sample_weight"] = sample_weight
    try:
        model.fit(x, y, **fit_kwargs)
    except TypeError:
        model.fit(x, y)
    return model


def per_class_metrics(
    y_true: pd.Series,
    y_pred: pd.Series | np.ndarray,
    *,
    labels: list[str],
) -> pd.DataFrame:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        zero_division=0,
    )
    return pd.DataFrame(
        {
            "class": labels,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    )


def class_recall(
    per_class: pd.DataFrame,
    class_name: str,
) -> Optional[float]:
    row = per_class[per_class["class"] == class_name]
    if row.empty:
        return None
    return float(row.iloc[0]["recall"])


def evaluate_predictions(
    y_true: pd.Series,
    y_pred: pd.Series | np.ndarray,
    *,
    labels: list[str],
) -> dict[str, Any]:
    per_class = per_class_metrics(y_true, y_pred, labels=labels)
    return {
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "down_recall": class_recall(per_class, DOWN_CLASS),
        "per_class_recall_min": float(per_class["recall"].min()) if not per_class.empty else None,
        "per_class": per_class.to_dict(orient="records"),
    }


def predict_with_down_threshold(
    proba: np.ndarray,
    *,
    classes: list[str],
    down_threshold: float,
) -> np.ndarray:
    default_idx = np.argmax(proba, axis=1)
    predicted = np.asarray([classes[index] for index in default_idx], dtype=object)
    if DOWN_CLASS not in classes:
        return predicted
    down_idx = classes.index(DOWN_CLASS)
    predicted[proba[:, down_idx] >= down_threshold] = DOWN_CLASS
    return predicted


def select_down_threshold_policy(
    *,
    model: Pipeline,
    x_validation: pd.DataFrame,
    y_validation: pd.Series,
    labels: list[str],
    max_macro_f1_drop: float = 0.03,
) -> Optional[dict[str, Any]]:
    proba = safe_predict_proba(model, x_validation)
    if proba is None or DOWN_CLASS not in labels:
        return None

    baseline_pred = model.predict(x_validation)
    baseline = evaluate_predictions(y_validation, baseline_pred, labels=labels)
    min_allowed_f1 = baseline["f1_macro"] - max_macro_f1_drop
    candidates = []
    for threshold in np.linspace(0.20, 0.55, 36):
        pred = predict_with_down_threshold(
            proba,
            classes=labels,
            down_threshold=float(threshold),
        )
        metrics = evaluate_predictions(y_validation, pred, labels=labels)
        metrics["threshold"] = float(threshold)
        metrics["eligible"] = bool(metrics["f1_macro"] >= min_allowed_f1)
        candidates.append(metrics)

    eligible = [item for item in candidates if item["eligible"]]
    pool = eligible or candidates
    best = sorted(
        pool,
        key=lambda item: (
            item["down_recall"] if item["down_recall"] is not None else -1.0,
            item["f1_macro"],
            item["per_class_recall_min"] if item["per_class_recall_min"] is not None else -1.0,
        ),
        reverse=True,
    )[0]
    return {
        "selected_threshold": best["threshold"],
        "eligible": bool(best["eligible"]),
        "selected_reason": (
            "within_macro_f1_drop_budget"
            if best["eligible"]
            else "diagnostic_only_no_threshold_met_f1_drop_budget"
        ),
        "validation_f1_macro": best["f1_macro"],
        "validation_down_recall": best["down_recall"],
        "validation_per_class_recall_min": best["per_class_recall_min"],
        "baseline_validation_f1_macro": baseline["f1_macro"],
        "baseline_validation_down_recall": baseline["down_recall"],
        "max_macro_f1_drop": max_macro_f1_drop,
    }


def apply_down_threshold_policy(
    *,
    model: Pipeline,
    x: pd.DataFrame,
    y: pd.Series,
    labels: list[str],
    threshold: float,
) -> dict[str, Any]:
    proba = safe_predict_proba(model, x)
    if proba is None:
        return {}
    pred = predict_with_down_threshold(proba, classes=labels, down_threshold=threshold)
    return evaluate_predictions(y, pred, labels=labels)


def evaluate_candidate(
    candidate: FeatureCandidate,
    *,
    frame: pd.DataFrame,
    model_config: ModelConfig,
    training_config: Any,
    artifact_dir: Path,
) -> FeatureCandidateResult:
    try:
        candidate_frame = apply_train_window(
            frame,
            split_column=model_config.split_column,
            train_window_days=candidate.train_window_days,
        )
        validate_training_data(candidate_frame, model_config, training_config)

        model = build_candidate_model(candidate, model_config)
        x_train, y_train, w_train = split_xy(candidate_frame, "train", model_config)
        x_val, y_val, _ = split_xy(candidate_frame, "validation", model_config)
        x_test, y_test, _ = split_xy(candidate_frame, "test", model_config)

        fit_model(model, x_train, y_train, w_train)
        validation_metrics = evaluate_model(model, x_val, y_val)
        test_metrics = evaluate_model(model, x_test, y_test)
        validation_pred = model.predict(x_val)
        test_pred = model.predict(x_test)
        validation_per_class = per_class_metrics(
            y_val,
            validation_pred,
            labels=model_config.valid_classes,
        )
        test_per_class = per_class_metrics(
            y_test,
            test_pred,
            labels=model_config.valid_classes,
        )
        validation_f1 = validation_metrics.get("f1_macro")
        test_f1 = test_metrics.get("f1_macro")
        gap = (
            float(validation_f1) - float(test_f1)
            if validation_f1 is not None and test_f1 is not None
            else None
        )

        threshold_policy = None
        if candidate.name == "logistic_class_weight_balanced":
            policy = select_down_threshold_policy(
                model=model,
                x_validation=x_val,
                y_validation=y_val,
                labels=model_config.valid_classes,
            )
            if policy:
                threshold = float(policy["selected_threshold"])
                threshold_policy = {
                    **policy,
                    "test": apply_down_threshold_policy(
                        model=model,
                        x=x_test,
                        y=y_test,
                        labels=model_config.valid_classes,
                        threshold=threshold,
                    ),
                }

        model_dir = artifact_dir / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = model_dir / f"{candidate.name}.joblib"
        joblib.dump(
            {
                "model": model,
                "candidate": asdict(candidate),
                "validation_metrics": validation_metrics,
                "test_metrics": test_metrics,
                "threshold_policy": threshold_policy,
                "saved_at": utc_now_iso(),
            },
            artifact_path,
        )

        return FeatureCandidateResult(
            candidate_name=candidate.name,
            model_type=candidate.model_type,
            status="completed",
            selection_score=float(validation_f1) if validation_f1 is not None else None,
            validation_f1_macro=float(validation_f1) if validation_f1 is not None else None,
            test_f1_macro=float(test_f1) if test_f1 is not None else None,
            validation_down_recall=class_recall(validation_per_class, DOWN_CLASS),
            test_down_recall=class_recall(test_per_class, DOWN_CLASS),
            per_class_recall_min=validation_metrics.get("per_class_recall_min"),
            log_loss=validation_metrics.get("log_loss"),
            brier_score=validation_metrics.get("brier_score"),
            validation_test_gap=gap,
            overfit_flag=bool(gap is not None and gap > OVERFIT_GAP_THRESHOLD),
            artifact_path=str(artifact_path),
            threshold_policy=threshold_policy,
            reasons=[],
        )
    except Exception as exc:
        return FeatureCandidateResult(
            candidate_name=candidate.name,
            model_type=candidate.model_type,
            status="skipped",
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
            artifact_path=None,
            threshold_policy=None,
            reasons=[str(exc)],
        )


def choose_best(results: list[FeatureCandidateResult]) -> Optional[FeatureCandidateResult]:
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


def load_model_bundle(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    bundle = joblib.load(path)
    if isinstance(bundle, dict) and "model" in bundle:
        return bundle["model"]
    return bundle


def baseline_reference_from_artifact(
    *,
    path: Path,
    frame: pd.DataFrame,
    model_config: ModelConfig,
) -> BaselineReference:
    model = load_model_bundle(path)
    if model is None:
        return BaselineReference(None, None, None, None)
    x_val, y_val, _ = split_xy(frame, "validation", model_config)
    x_test, y_test, _ = split_xy(frame, "test", model_config)
    val_metrics = evaluate_model(model, x_val, y_val)
    test_metrics = evaluate_model(model, x_test, y_test)
    val_pc = per_class_metrics(y_val, model.predict(x_val), labels=model_config.valid_classes)
    test_pc = per_class_metrics(y_test, model.predict(x_test), labels=model_config.valid_classes)
    return BaselineReference(
        validation_f1_macro=val_metrics.get("f1_macro"),
        test_f1_macro=test_metrics.get("f1_macro"),
        validation_down_recall=class_recall(val_pc, DOWN_CLASS),
        test_down_recall=class_recall(test_pc, DOWN_CLASS),
    )


def feature_signal_summary(frame: pd.DataFrame, features: list[str], target_column: str) -> pd.DataFrame:
    direction_score = frame[target_column].astype(str).str.upper().map(
        {"DOWN": -1.0, "FLAT": 0.0, "UP": 1.0}
    )
    rows = []
    for feature in features:
        values = pd.to_numeric(frame[feature], errors="coerce")
        valid = values.notna() & direction_score.notna()
        corr = None
        if valid.sum() >= 10 and values.loc[valid].nunique() > 1:
            corr_value = values.loc[valid].corr(direction_score.loc[valid])
            corr = None if pd.isna(corr_value) else float(corr_value)
        rows.append(
            {
                "feature": feature,
                "target_corr": corr,
                "abs_target_corr": None if corr is None else abs(corr),
                "missing_rate": float(values.isna().mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["abs_target_corr", "feature"],
        ascending=[False, True],
        na_position="last",
    )


def markdown_table(frame: pd.DataFrame, columns: Optional[list[str]] = None, max_rows: int = 30) -> str:
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


def write_outputs(
    *,
    artifact_dir: Path,
    results: list[FeatureCandidateResult],
    best: Optional[FeatureCandidateResult],
    baseline_reference: BaselineReference,
    feature_signal: pd.DataFrame,
    engineered_features: list[str],
    input_source: str,
    input_cache_path: Path,
    dry_run: bool,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    leaderboard = pd.DataFrame([result.to_row() for result in results])
    leaderboard.to_csv(DEFAULT_LEADERBOARD_PATH, index=False)

    best_row = best.to_row() if best else None
    best_validation_down_delta = (
        best.validation_down_recall - baseline_reference.validation_down_recall
        if best and best.validation_down_recall is not None and baseline_reference.validation_down_recall is not None
        else None
    )
    best_test_down_delta = (
        best.test_down_recall - baseline_reference.test_down_recall
        if best and best.test_down_recall is not None and baseline_reference.test_down_recall is not None
        else None
    )
    best_validation_f1_delta = (
        best.validation_f1_macro - baseline_reference.validation_f1_macro
        if best and best.validation_f1_macro is not None and baseline_reference.validation_f1_macro is not None
        else None
    )
    best_test_f1_delta = (
        best.test_f1_macro - baseline_reference.test_f1_macro
        if best and best.test_f1_macro is not None and baseline_reference.test_f1_macro is not None
        else None
    )

    threshold_rows = [
        {
            "candidate_name": result.candidate_name,
            **(result.threshold_policy or {}),
        }
        for result in results
        if result.threshold_policy
    ]
    threshold_frame = pd.DataFrame(threshold_rows)

    summary = {
        "created_at": utc_now_iso(),
        "dry_run": dry_run,
        "input_source": input_source,
        "input_cache_path": str(input_cache_path),
        "artifact_dir": str(artifact_dir),
        "leaderboard_path": str(DEFAULT_LEADERBOARD_PATH),
        "report_path": str(DEFAULT_REPORT_PATH),
        "engineered_parquet_path": str(DEFAULT_ENGINEERED_PARQUET_PATH),
        "candidate_names": [result.candidate_name for result in results],
        "engineered_feature_count": len(engineered_features),
        "engineered_features": engineered_features,
        "best_model": best_row,
        "baseline_reference": asdict(baseline_reference),
        "best_validation_down_recall_delta": best_validation_down_delta,
        "best_test_down_recall_delta": best_test_down_delta,
        "best_validation_f1_macro_delta": best_validation_f1_delta,
        "best_test_f1_macro_delta": best_test_f1_delta,
        **LOCAL_ONLY_WRITES,
    }
    DEFAULT_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    report = f"""# Local Feature Engineering Research V1

## Safety

- GCS output written: `false`
- BigQuery output written: `false`
- Registry updated: `false`
- Production predict behavior changed: `false`
- Dry run flag: `{dry_run}`
- Input source: `{input_source}`
- Input cache: `{input_cache_path}`

## Feature Set

- Engineered feature count: `{len(engineered_features)}`
- Engineered parquet: `{DEFAULT_ENGINEERED_PARQUET_PATH}`

{markdown_table(pd.DataFrame({"engineered_feature": engineered_features}), max_rows=80)}

## Candidate Leaderboard

Selection uses validation macro F1 first, then validation DOWN recall, then minimum per-class recall. Test metrics are final evaluation only.

{markdown_table(leaderboard, columns=[
    "candidate_name",
    "status",
    "selection_score",
    "validation_f1_macro",
    "test_f1_macro",
    "validation_down_recall",
    "test_down_recall",
    "per_class_recall_min",
    "log_loss",
    "brier_score",
    "validation_test_gap",
    "overfit_flag",
], max_rows=20)}

## Baseline Comparison

- Previous logistic validation F1: `{baseline_reference.validation_f1_macro}`
- Previous logistic test F1: `{baseline_reference.test_f1_macro}`
- Previous logistic validation DOWN recall: `{baseline_reference.validation_down_recall}`
- Previous logistic test DOWN recall: `{baseline_reference.test_down_recall}`
- Best V1 model: `{best.candidate_name if best else "N/A"}`
- Best validation DOWN recall delta: `{best_validation_down_delta}`
- Best test DOWN recall delta: `{best_test_down_delta}`
- Best validation macro F1 delta: `{best_validation_f1_delta}`
- Best test macro F1 delta: `{best_test_f1_delta}`

## Research Threshold Policy

This policy is validation-selected and research-only. It does not change production predict behavior.

{markdown_table(threshold_frame, max_rows=10)}

## Top Engineered Feature Signal

Target proxy: DOWN=-1, FLAT=0, UP=1. This is diagnostic only.

{markdown_table(feature_signal, max_rows=30)}

## Recommendation

- Promote nothing from this local research run automatically.
- If DOWN recall improves without a large macro F1 drop, productionize only the corresponding feature family through dbt after review.
- If DOWN recall improves mainly through threshold policy, treat it as a separate decision-policy experiment and validate on later time windows before production.
- If macro F1 drops while DOWN recall rises, document the trade-off instead of promoting the model.
- Run a larger sprint only after this smoke report is reviewed.
"""
    DEFAULT_REPORT_PATH.write_text(report, encoding="utf-8")


def log_local_mlflow(
    *,
    best: Optional[FeatureCandidateResult],
    artifact_paths: list[Path],
    engineered_feature_count: int,
) -> None:
    tracking_uri = str(__import__("os").environ.get("MLFLOW_TRACKING_URI", ""))
    if not is_mlflow_enabled() or not (
        tracking_uri.startswith("sqlite:///") or tracking_uri.startswith("file:")
    ):
        return
    try:
        log_training_run(
            run_name=f"feature_engineering_v1_{utc_now_iso()}",
            params={
                "research_local_only": True,
                "engineered_feature_count": engineered_feature_count,
                "best_candidate": best.candidate_name if best else "",
                **LOCAL_ONLY_WRITES,
            },
            metrics={
                "best.validation_f1_macro": best.validation_f1_macro if best else None,
                "best.test_f1_macro": best.test_f1_macro if best else None,
                "best.validation_down_recall": best.validation_down_recall if best else None,
                "best.test_down_recall": best.test_down_recall if best else None,
            },
            tags={
                "phase": "feature_engineering_v1",
                "local_only": "true",
            },
            artifact_paths=artifact_paths,
        )
    except Exception as exc:
        handle_mlflow_error("Feature engineering V1 MLflow logging failed", exc)


def run_research(args: argparse.Namespace) -> list[FeatureCandidateResult]:
    artifact_dir = ensure_local_research_path(Path(args.artifact_dir))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    config = load_yaml(Path(args.config).resolve())
    raw_df, input_source, cache_path, _, model_config, training_config = load_training_frame(
        config=config,
        input_cache_dir=Path(args.input_cache_dir),
        refresh_cache=args.refresh_cache,
    )
    cleaned_df = clean_features(raw_df, model_config, training_config)
    validate_training_data(cleaned_df, model_config, training_config)

    engineered_df, engineered_features = build_research_features(
        cleaned_df,
        model_config=model_config,
    )
    v1_model_config = research_model_config(model_config, engineered_features)
    validate_training_data(engineered_df, v1_model_config, training_config)

    DEFAULT_ENGINEERED_PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if args.write_engineered_parquet:
        engineered_df.to_parquet(DEFAULT_ENGINEERED_PARQUET_PATH, index=False)

    candidates = select_candidates(args.max_candidates)
    print("[feature-v1] Candidates:")
    for candidate in candidates:
        print(f"  - {candidate.name}")
    print(f"[feature-v1] Engineered features: {len(engineered_features)}")
    print(f"[feature-v1] Input source: {input_source}")

    results = [
        evaluate_candidate(
            candidate,
            frame=engineered_df,
            model_config=v1_model_config,
            training_config=training_config,
            artifact_dir=artifact_dir,
        )
        for candidate in candidates
    ]
    best = choose_best(results)

    baseline_reference = baseline_reference_from_artifact(
        path=Path(args.production_logistic_artifact),
        frame=cleaned_df,
        model_config=model_config,
    )
    feature_signal = feature_signal_summary(
        engineered_df,
        engineered_features,
        model_config.target_name,
    )
    write_outputs(
        artifact_dir=artifact_dir,
        results=results,
        best=best,
        baseline_reference=baseline_reference,
        feature_signal=feature_signal,
        engineered_features=engineered_features,
        input_source=input_source,
        input_cache_path=cache_path,
        dry_run=args.dry_run,
    )
    log_local_mlflow(
        best=best,
        artifact_paths=[DEFAULT_REPORT_PATH, DEFAULT_LEADERBOARD_PATH, DEFAULT_SUMMARY_PATH],
        engineered_feature_count=len(engineered_features),
    )

    print(f"[feature-v1] Leaderboard: {DEFAULT_LEADERBOARD_PATH}")
    print(f"[feature-v1] Summary: {DEFAULT_SUMMARY_PATH}")
    print(f"[feature-v1] Report: {DEFAULT_REPORT_PATH}")
    if best is not None:
        print(f"[feature-v1] Best candidate: {best.candidate_name}")
    return results


def main() -> int:
    args = parse_args()
    run_research(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
