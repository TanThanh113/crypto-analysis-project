#!/usr/bin/env python3
"""
Local-only AutoML/model research runner for crypto direction.

This runner is intentionally separate from train_model.py production behavior.
It reads training data, caches it locally, evaluates candidate models with
time-ordered walk-forward validation, and writes local-only research artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import joblib
import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

from mlflow_utils import handle_mlflow_error, is_mlflow_enabled, log_training_run
from optuna_tuning import lightgbm_search_space
from time_split import apply_train_window
from train_model import (
    BigQueryConfig,
    ModelConfig,
    TrainingConfig,
    build_configs,
    build_models,
    clean_features,
    evaluate_model,
    get_sample_weight,
    load_yaml,
    make_preprocessor,
    query_training_data,
    split_xy,
    validate_training_data,
)


ML_ROOT = Path(__file__).resolve().parent
LOCAL_RESEARCH_ROOT = ML_ROOT / "artifacts" / "local_research"
INPUT_SNAPSHOT_DIR = LOCAL_RESEARCH_ROOT / "input_snapshot"
DEFAULT_REPORT_PATH = LOCAL_RESEARCH_ROOT / "model_search_report.md"
DEFAULT_LEADERBOARD_PATH = LOCAL_RESEARCH_ROOT / "leaderboard.csv"
DEFAULT_SUMMARY_PATH = LOCAL_RESEARCH_ROOT / "research_summary.json"

OVERFIT_GAP_THRESHOLD = 0.08
FOLD_STD_THRESHOLD = 0.06


@dataclass(frozen=True)
class ResearchCandidate:
    name: str
    model_type: str
    train_window_days: Optional[int]
    tune_with_optuna: bool = False


@dataclass(frozen=True)
class WalkForwardFold:
    fold_name: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    train_df: pd.DataFrame
    validation_df: pd.DataFrame


@dataclass(frozen=True)
class CandidateResult:
    candidate_name: str
    model_type: str
    status: str
    selection_score: Optional[float]
    validation_f1_macro: Optional[float]
    test_f1_macro: Optional[float]
    validation_test_gap: Optional[float]
    log_loss: Optional[float]
    brier_score: Optional[float]
    per_class_recall_min: Optional[float]
    walk_forward_f1_macro_mean: Optional[float]
    walk_forward_f1_macro_std: Optional[float]
    overfit_flag: bool
    artifact_path: Optional[str]
    reasons: list[str]
    optuna_best_params: dict[str, Any]

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


class LabelEncodedClassifier(BaseEstimator, ClassifierMixin):
    """Wrap estimators that require integer labels while exposing string labels."""

    def __init__(self, estimator: Any):
        self.estimator = estimator

    def fit(self, x: Any, y: Iterable[Any], **fit_params: Any) -> "LabelEncodedClassifier":
        self.label_encoder_ = LabelEncoder()
        y_encoded = self.label_encoder_.fit_transform(pd.Series(y).astype(str))
        self.estimator_ = clone(self.estimator)
        self.estimator_.fit(x, y_encoded, **fit_params)
        self.classes_ = self.label_encoder_.classes_
        return self

    def predict(self, x: Any) -> np.ndarray:
        encoded = self.estimator_.predict(x)
        return self.label_encoder_.inverse_transform(np.asarray(encoded, dtype=int))

    def predict_proba(self, x: Any) -> np.ndarray:
        return self.estimator_.predict_proba(x)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_").lower()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local-only AutoML/model research for crypto direction."
    )
    parser.add_argument("--config", default="feature_list.yml")
    parser.add_argument("--artifact-dir", default="artifacts/local_research/smoke")
    parser.add_argument("--artifact-storage", choices=["local", "gcs", "both"], default="local")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--optuna-n-trials", type=int, default=5)
    parser.add_argument("--walk-forward-folds", type=int, default=2)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument(
        "--cache-dir",
        default=str(INPUT_SNAPSHOT_DIR),
        help="Local parquet cache directory for read-only BigQuery training input.",
    )
    return parser.parse_args()


def validate_local_only_args(args: argparse.Namespace) -> None:
    if args.artifact_storage != "local":
        raise ValueError("local_automl_research.py only supports --artifact-storage local.")
    if args.optuna_n_trials < 0:
        raise ValueError("--optuna-n-trials must be >= 0.")
    if args.walk_forward_folds < 1:
        raise ValueError("--walk-forward-folds must be >= 1.")


def build_research_configs(config: dict[str, Any]) -> tuple[BigQueryConfig, ModelConfig, TrainingConfig]:
    try:
        return build_configs(config)
    except ValueError as exc:
        if "GCP_PROJECT_ID" not in str(exc):
            raise

    bq = config.get("bigquery", {})
    os.environ.setdefault("GCP_PROJECT_ID", bq.get("default_project_id", "project-lambda-crypto"))
    return build_configs(config)


def candidate_specs() -> list[ResearchCandidate]:
    return [
        ResearchCandidate("logistic_baseline_all_history", "logistic", None),
        ResearchCandidate("lightgbm_rolling_90d", "lightgbm", 90, tune_with_optuna=True),
        ResearchCandidate("xgboost_rolling_90d", "xgboost", 90, tune_with_optuna=True),
        ResearchCandidate("extratrees_all_history_baseline", "extratrees", None),
        ResearchCandidate("lightgbm_all_history_fixed_params", "lightgbm", None),
        ResearchCandidate("lightgbm_rolling_180d", "lightgbm", 180, tune_with_optuna=True),
        ResearchCandidate("xgboost_rolling_180d", "xgboost", 180, tune_with_optuna=True),
        ResearchCandidate("hist_gradient_boosting_all_history", "hist_gradient_boosting", None),
    ]


def select_candidates(max_candidates: Optional[int]) -> list[ResearchCandidate]:
    candidates = candidate_specs()
    if max_candidates is None:
        return candidates
    return candidates[:max_candidates]


def snapshot_path(cache_dir: Path, bq_config: BigQueryConfig) -> Path:
    filename = f"{slug(bq_config.training_table_fqn)}.parquet"
    return cache_dir / filename


def load_or_query_training_data(
    *,
    cache_dir: Path,
    refresh_cache: bool,
    bq_config: BigQueryConfig,
    model_config: ModelConfig,
) -> pd.DataFrame:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(cache_dir, bq_config)

    if path.exists() and not refresh_cache:
        print(f"[research] Loading cached training input: {path}")
        return pd.read_parquet(path)

    print(f"[research] Reading BigQuery training input (read-only): {bq_config.training_table_fqn}")
    client = bigquery.Client(project=bq_config.project_id)
    df = query_training_data(client, bq_config, model_config)
    df.to_parquet(path, index=False)
    print(f"[research] Cached training input locally: {path}")
    return df


def non_test_frame(df: pd.DataFrame, split_column: str) -> pd.DataFrame:
    return df[df[split_column].astype(str) != "test"].copy()


def make_walk_forward_folds(
    df: pd.DataFrame,
    *,
    model_config: ModelConfig,
    n_folds: int,
    train_window_days: Optional[int],
    timestamp_column: str = "hour_ts",
) -> list[WalkForwardFold]:
    pool = non_test_frame(df, model_config.split_column)
    timestamps = pd.to_datetime(pool[timestamp_column], errors="coerce", utc=True)
    pool = pool.loc[timestamps.notna()].copy()
    pool["_research_ts"] = pd.to_datetime(pool[timestamp_column], errors="coerce", utc=True)
    unique_ts = pd.Index(sorted(pool["_research_ts"].dropna().unique()))

    if len(unique_ts) < 4:
        raise ValueError("Not enough timestamps to create walk-forward folds.")

    min_train_idx = max(1, int(len(unique_ts) * 0.50))
    remaining = len(unique_ts) - min_train_idx
    fold_count = min(n_folds, remaining)
    if fold_count < 1:
        raise ValueError("Not enough remaining timestamps for validation folds.")

    fold_size = max(1, remaining // fold_count)
    folds: list[WalkForwardFold] = []

    for fold_idx in range(fold_count):
        val_start_idx = min_train_idx + fold_idx * fold_size
        val_end_idx = len(unique_ts) if fold_idx == fold_count - 1 else min(
            min_train_idx + (fold_idx + 1) * fold_size,
            len(unique_ts),
        )
        if val_start_idx >= val_end_idx:
            continue

        val_start = pd.Timestamp(unique_ts[val_start_idx])
        val_end = pd.Timestamp(unique_ts[val_end_idx - 1])
        train_mask = pool["_research_ts"] < val_start
        if train_window_days is not None:
            window_start = val_start - pd.Timedelta(days=train_window_days)
            train_mask &= pool["_research_ts"] >= window_start
        val_mask = (pool["_research_ts"] >= val_start) & (pool["_research_ts"] <= val_end)

        train_df = pool.loc[train_mask].drop(columns=["_research_ts"]).copy()
        validation_df = pool.loc[val_mask].drop(columns=["_research_ts"]).copy()
        if train_df.empty or validation_df.empty:
            continue

        train_end = pd.to_datetime(train_df[timestamp_column], errors="coerce", utc=True).max()
        validation_start = pd.to_datetime(
            validation_df[timestamp_column],
            errors="coerce",
            utc=True,
        ).min()
        if train_end >= validation_start:
            raise ValueError(
                f"Walk-forward leakage detected: {train_end} >= {validation_start}"
            )

        folds.append(
            WalkForwardFold(
                fold_name=f"fold_{fold_idx + 1}",
                train_start=pd.to_datetime(
                    train_df[timestamp_column],
                    errors="coerce",
                    utc=True,
                ).min().isoformat(),
                train_end=train_end.isoformat(),
                validation_start=validation_start.isoformat(),
                validation_end=pd.to_datetime(
                    validation_df[timestamp_column],
                    errors="coerce",
                    utc=True,
                ).max().isoformat(),
                train_df=train_df,
                validation_df=validation_df,
            )
        )

    if not folds:
        raise ValueError("No valid walk-forward folds were created.")
    return folds


def make_xgboost_pipeline(model_config: ModelConfig, params: Optional[dict[str, Any]] = None) -> Pipeline:
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise ImportError(
            "xgboost is required for XGBoost research candidates. Install it with: "
            "uv pip install --python .venv/bin/python -r requirements-research.txt"
        ) from exc

    defaults = {
        "objective": "multi:softprob",
        "eval_metric": "mlogloss",
        "tree_method": "hist",
        "n_estimators": 220,
        "max_depth": 4,
        "learning_rate": 0.035,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_alpha": 0.05,
        "reg_lambda": 1.0,
        "random_state": model_config.random_state,
        "n_jobs": -1,
    }
    defaults.update(params or {})
    return Pipeline(
        steps=[
            ("preprocess", make_preprocessor(model_config, scale_numeric=False)),
            ("model", LabelEncodedClassifier(XGBClassifier(**defaults))),
        ]
    )


def make_extratrees_pipeline(model_config: ModelConfig) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", make_preprocessor(model_config, scale_numeric=False)),
            (
                "model",
                ExtraTreesClassifier(
                    n_estimators=350,
                    max_features="sqrt",
                    min_samples_leaf=8,
                    class_weight="balanced",
                    random_state=model_config.random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def make_hist_gradient_boosting_pipeline(model_config: ModelConfig) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocess", make_preprocessor(model_config, scale_numeric=False)),
            (
                "model",
                HistGradientBoostingClassifier(
                    learning_rate=0.04,
                    max_iter=180,
                    l2_regularization=0.05,
                    random_state=model_config.random_state,
                ),
            ),
        ]
    )


def build_candidate_model(
    candidate: ResearchCandidate,
    model_config: ModelConfig,
    params: Optional[dict[str, Any]] = None,
) -> Pipeline:
    if candidate.model_type == "logistic":
        return build_models(model_config)["logistic_regression_baseline"]

    if candidate.model_type == "lightgbm":
        model = build_models(model_config)["lightgbm_classifier"]
        if params:
            model.set_params(**{f"model__{key}": value for key, value in params.items()})
        return model

    if candidate.model_type == "xgboost":
        return make_xgboost_pipeline(model_config, params)

    if candidate.model_type == "extratrees":
        return make_extratrees_pipeline(model_config)

    if candidate.model_type == "hist_gradient_boosting":
        return make_hist_gradient_boosting_pipeline(model_config)

    raise ValueError(f"Unsupported candidate model_type={candidate.model_type}")


def split_frame_xy(
    df: pd.DataFrame,
    model_config: ModelConfig,
) -> tuple[pd.DataFrame, pd.Series, Optional[np.ndarray]]:
    x = df[model_config.all_features]
    y = df[model_config.target_name].astype(str).str.upper()
    weights = get_sample_weight(df, model_config)
    return x, y, weights


def fit_model(
    model: Pipeline,
    x: pd.DataFrame,
    y: pd.Series,
    sample_weight: Optional[np.ndarray],
) -> Pipeline:
    fit_kwargs = {}
    if sample_weight is not None:
        fit_kwargs["model__sample_weight"] = sample_weight
    model.fit(x, y, **fit_kwargs)
    return model


def score_candidate_on_folds(
    candidate: ResearchCandidate,
    model_config: ModelConfig,
    folds: list[WalkForwardFold],
    params: Optional[dict[str, Any]] = None,
) -> list[float]:
    scores: list[float] = []
    for fold in folds:
        model = build_candidate_model(candidate, model_config, params)
        x_train, y_train, w_train = split_frame_xy(fold.train_df, model_config)
        x_val, y_val, _ = split_frame_xy(fold.validation_df, model_config)
        fit_model(model, x_train, y_train, w_train)
        pred = model.predict(x_val)
        scores.append(float(f1_score(y_val, pred, average="macro", zero_division=0)))
    return scores


def tune_candidate_on_folds(
    candidate: ResearchCandidate,
    model_config: ModelConfig,
    folds: list[WalkForwardFold],
    n_trials: int,
) -> dict[str, Any]:
    if n_trials <= 0 or not candidate.tune_with_optuna:
        return {}

    try:
        import optuna
    except ImportError:
        return {}

    def objective(trial: Any) -> float:
        if candidate.model_type == "lightgbm":
            params = lightgbm_search_space(trial)
        elif candidate.model_type == "xgboost":
            params = {
                "max_depth": trial.suggest_int("max_depth", 3, 7),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.08, log=True),
                "n_estimators": trial.suggest_int("n_estimators", 80, 280, step=40),
                "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 12.0),
                "subsample": trial.suggest_float("subsample", 0.65, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.65, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 1.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
            }
        else:
            return float("-inf")

        scores = score_candidate_on_folds(candidate, model_config, folds, params)
        return float(np.mean(scores))

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=model_config.random_state),
    )
    study.optimize(objective, n_trials=n_trials, n_jobs=1, show_progress_bar=False)
    return dict(study.best_params)


def final_evaluate_candidate(
    candidate: ResearchCandidate,
    model_config: ModelConfig,
    candidate_df: pd.DataFrame,
    artifact_dir: Path,
    params: Optional[dict[str, Any]],
) -> tuple[Pipeline, dict[str, dict[str, Any]], Path]:
    model = build_candidate_model(candidate, model_config, params)
    x_train, y_train, w_train = split_xy(candidate_df, "train", model_config)
    x_val, y_val, _ = split_xy(candidate_df, "validation", model_config)
    x_test, y_test, _ = split_xy(candidate_df, "test", model_config)
    fit_model(model, x_train, y_train, w_train)

    metrics = {
        "train": evaluate_model(model, x_train, y_train),
        "validation": evaluate_model(model, x_val, y_val),
        "test": evaluate_model(model, x_test, y_test),
    }

    model_dir = artifact_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = model_dir / f"{candidate.name}.joblib"
    joblib.dump(
        {
            "model": model,
            "candidate": asdict(candidate),
            "metrics": metrics,
            "optuna_best_params": params or {},
            "saved_at": utc_now_iso(),
        },
        artifact_path,
    )
    return model, metrics, artifact_path


def overfit_flag(
    *,
    validation_test_gap: Optional[float],
    fold_std: Optional[float],
) -> bool:
    gap_bad = validation_test_gap is not None and validation_test_gap > OVERFIT_GAP_THRESHOLD
    std_bad = fold_std is not None and fold_std > FOLD_STD_THRESHOLD
    return bool(gap_bad or std_bad)


def evaluate_candidate(
    candidate: ResearchCandidate,
    *,
    df: pd.DataFrame,
    model_config: ModelConfig,
    training_config: TrainingConfig,
    artifact_dir: Path,
    optuna_n_trials: int,
    n_folds: int,
) -> CandidateResult:
    try:
        candidate_df = apply_train_window(
            df,
            split_column=model_config.split_column,
            train_window_days=candidate.train_window_days,
        )
        validate_training_data(candidate_df, model_config, training_config)
        folds = make_walk_forward_folds(
            candidate_df,
            model_config=model_config,
            n_folds=n_folds,
            train_window_days=candidate.train_window_days,
        )

        best_params = tune_candidate_on_folds(
            candidate,
            model_config,
            folds,
            optuna_n_trials,
        )
        fold_scores = score_candidate_on_folds(
            candidate,
            model_config,
            folds,
            best_params,
        )
        _, split_metrics, artifact_path = final_evaluate_candidate(
            candidate,
            model_config,
            candidate_df,
            artifact_dir,
            best_params,
        )

        validation_metrics = split_metrics["validation"]
        test_metrics = split_metrics["test"]
        validation_f1 = validation_metrics.get("f1_macro")
        test_f1 = test_metrics.get("f1_macro")
        validation_test_gap = (
            float(validation_f1) - float(test_f1)
            if validation_f1 is not None and test_f1 is not None
            else None
        )
        fold_mean = float(np.mean(fold_scores)) if fold_scores else None
        fold_std = float(np.std(fold_scores)) if fold_scores else None

        return CandidateResult(
            candidate_name=candidate.name,
            model_type=candidate.model_type,
            status="completed",
            selection_score=fold_mean,
            validation_f1_macro=float(validation_f1) if validation_f1 is not None else None,
            test_f1_macro=float(test_f1) if test_f1 is not None else None,
            validation_test_gap=validation_test_gap,
            log_loss=validation_metrics.get("log_loss"),
            brier_score=validation_metrics.get("brier_score"),
            per_class_recall_min=validation_metrics.get("per_class_recall_min"),
            walk_forward_f1_macro_mean=fold_mean,
            walk_forward_f1_macro_std=fold_std,
            overfit_flag=overfit_flag(
                validation_test_gap=validation_test_gap,
                fold_std=fold_std,
            ),
            artifact_path=str(artifact_path),
            reasons=[],
            optuna_best_params=best_params,
        )
    except Exception as exc:
        return CandidateResult(
            candidate_name=candidate.name,
            model_type=candidate.model_type,
            status="skipped",
            selection_score=None,
            validation_f1_macro=None,
            test_f1_macro=None,
            validation_test_gap=None,
            log_loss=None,
            brier_score=None,
            per_class_recall_min=None,
            walk_forward_f1_macro_mean=None,
            walk_forward_f1_macro_std=None,
            overfit_flag=False,
            artifact_path=None,
            reasons=[str(exc)],
            optuna_best_params={},
        )


def choose_best(results: list[CandidateResult]) -> Optional[CandidateResult]:
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
            result.per_class_recall_min if result.per_class_recall_min is not None else -1.0,
            -(result.log_loss if result.log_loss is not None else 999.0),
        ),
        reverse=True,
    )[0]


def leaderboard_frame(results: list[CandidateResult]) -> pd.DataFrame:
    return pd.DataFrame([result.to_row() for result in results])


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "_No candidates completed._"

    visible = frame[columns].copy()
    headers = list(visible.columns)
    rows = []
    for _, row in visible.iterrows():
        rows.append([
            "" if pd.isna(row[column]) else str(row[column])
            for column in headers
        ])

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_report(
    *,
    results: list[CandidateResult],
    best: Optional[CandidateResult],
    report_path: Path,
    leaderboard_path: Path,
    summary_path: Path,
    artifact_dir: Path,
    bq_config: BigQueryConfig,
    candidates: list[ResearchCandidate],
    run_id: str,
) -> None:
    LOCAL_RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)
    leaderboard = leaderboard_frame(results)
    leaderboard.to_csv(leaderboard_path, index=False)

    completed = [result for result in results if result.status == "completed"]
    logistic = next(
        (result for result in completed if result.candidate_name == "logistic_baseline_all_history"),
        None,
    )
    lightgbm = next(
        (result for result in completed if result.candidate_name.startswith("lightgbm")),
        None,
    )

    summary = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "training_table": bq_config.training_table_fqn,
        "candidate_names": [candidate.name for candidate in candidates],
        "best_model": best.to_row() if best else None,
        "wrote_gcs": False,
        "wrote_bigquery_output": False,
        "updated_registry": False,
        "artifact_dir": str(artifact_dir),
        "leaderboard_path": str(leaderboard_path),
        "report_path": str(report_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    best_name = best.candidate_name if best else "N/A"
    best_overfit = best.overfit_flag if best else "N/A"
    better_than_logistic = (
        bool(best and logistic and best.selection_score and logistic.selection_score and best.selection_score > logistic.selection_score)
    )
    better_than_lightgbm = (
        bool(best and lightgbm and best.selection_score and lightgbm.selection_score and best.selection_score > lightgbm.selection_score)
    )

    report_columns = [
        "candidate_name",
        "status",
        "selection_score",
        "validation_f1_macro",
        "test_f1_macro",
        "validation_test_gap",
        "log_loss",
        "brier_score",
        "per_class_recall_min",
        "walk_forward_f1_macro_std",
        "overfit_flag",
    ]
    table = markdown_table(leaderboard, report_columns)

    report = f"""# Local AutoML Model Search Report

Generated at: `{utc_now_iso()}`

## Safety

- GCS output written: `false`
- BigQuery output written: `false`
- Registry updated: `false`
- Production predict behavior changed: `false`

## Leaderboard

{table}

## Current Best

- Best model by walk-forward validation mean f1_macro: `{best_name}`
- Overfit flag: `{best_overfit}`
- Better than logistic baseline: `{better_than_logistic}`
- Better than first LightGBM candidate: `{better_than_lightgbm}`

## Recommendation

- Run a larger sprint only after reviewing this smoke report.
- Do not promote a new model to production from smoke results alone.
- Consider more feature/data work if all candidates remain close to the logistic baseline or show high validation-test gap.

## Local Paths

- Artifact dir: `{artifact_dir}`
- Leaderboard: `{leaderboard_path}`
- Summary: `{summary_path}`
- Training input cache: `{INPUT_SNAPSHOT_DIR}`
"""
    report_path.write_text(report, encoding="utf-8")


def log_local_mlflow(
    *,
    results: list[CandidateResult],
    best: Optional[CandidateResult],
    report_path: Path,
    leaderboard_path: Path,
    summary_path: Path,
    run_id: str,
) -> None:
    if not is_mlflow_enabled():
        return

    try:
        metrics = {}
        if best is not None:
            metrics = {
                "best.selection_score": best.selection_score,
                "best.validation_f1_macro": best.validation_f1_macro,
                "best.test_f1_macro": best.test_f1_macro,
                "best.validation_test_gap": best.validation_test_gap,
            }

        log_training_run(
            run_name=f"local_automl_research_{run_id}",
            params={
                "research_local_only": True,
                "candidate_count": len(results),
                "best_candidate": best.candidate_name if best else "",
                "wrote_gcs": False,
                "wrote_bigquery_output": False,
                "updated_registry": False,
            },
            metrics=metrics,
            tags={
                "phase": "local_automl_research",
                "local_only": "true",
            },
            artifact_paths=[report_path, leaderboard_path, summary_path],
        )
    except Exception as exc:
        handle_mlflow_error("Local AutoML MLflow logging failed", exc)


def run_research(args: argparse.Namespace) -> list[CandidateResult]:
    validate_local_only_args(args)
    config_path = Path(args.config).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    LOCAL_RESEARCH_ROOT.mkdir(parents=True, exist_ok=True)

    config = load_yaml(config_path)
    bq_config, model_config, training_config = build_research_configs(config)
    df = load_or_query_training_data(
        cache_dir=Path(args.cache_dir).resolve(),
        refresh_cache=args.refresh_cache,
        bq_config=bq_config,
        model_config=model_config,
    )
    df = clean_features(df, model_config, training_config)
    validate_training_data(df, model_config, training_config)

    run_id = str(uuid.uuid4())
    candidates = select_candidates(args.max_candidates)
    print("[research] Candidates:")
    for candidate in candidates:
        print(f"  - {candidate.name}")

    results = [
        evaluate_candidate(
            candidate,
            df=df,
            model_config=model_config,
            training_config=training_config,
            artifact_dir=artifact_dir,
            optuna_n_trials=args.optuna_n_trials,
            n_folds=args.walk_forward_folds,
        )
        for candidate in candidates
    ]
    best = choose_best(results)

    write_report(
        results=results,
        best=best,
        report_path=DEFAULT_REPORT_PATH,
        leaderboard_path=DEFAULT_LEADERBOARD_PATH,
        summary_path=DEFAULT_SUMMARY_PATH,
        artifact_dir=artifact_dir,
        bq_config=bq_config,
        candidates=candidates,
        run_id=run_id,
    )
    log_local_mlflow(
        results=results,
        best=best,
        report_path=DEFAULT_REPORT_PATH,
        leaderboard_path=DEFAULT_LEADERBOARD_PATH,
        summary_path=DEFAULT_SUMMARY_PATH,
        run_id=run_id,
    )

    print(f"[research] Leaderboard: {DEFAULT_LEADERBOARD_PATH}")
    print(f"[research] Summary: {DEFAULT_SUMMARY_PATH}")
    print(f"[research] Report: {DEFAULT_REPORT_PATH}")
    if best is not None:
        print(f"[research] Best candidate: {best.candidate_name}")
    return results


def main() -> int:
    args = parse_args()
    run_research(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[research][ERROR] {exc}", file=sys.stderr)
        raise
