from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.pipeline import Pipeline


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
LIGHTGBM_BASE_MODEL_KEY = "lightgbm_classifier"
SUPPORTED_METRICS = {"f1_macro", "accuracy", "log_loss"}


@dataclass(frozen=True)
class OptunaTuningSettings:
    enabled: bool
    n_trials: int
    timeout_seconds: Optional[int]
    study_name: Optional[str]
    storage_uri: Optional[str]
    direction: str
    metric_name: str
    strategy_name: Optional[str]
    fail_on_error: bool


@dataclass(frozen=True)
class OptunaTuningResult:
    enabled: bool
    study_name: Optional[str]
    best_params: dict[str, Any]
    best_value: Optional[float]
    best_trial_number: Optional[int]
    n_trials: int
    timeout: Optional[int]
    metric_name: str
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["best_params"] = dict(self.best_params or {})
        payload["reasons"] = list(self.reasons or [])
        return payload


def env_bool(name: str, default: bool = False, env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    value = source.get(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def env_int(name: str, default: Optional[int], env: Mapping[str, str] | None = None) -> Optional[int]:
    source = os.environ if env is None else env
    value = source.get(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def get_optuna_settings(
    *,
    enabled: bool | None = None,
    n_trials: int | None = None,
    timeout_seconds: Optional[int] = None,
    study_name: Optional[str] = None,
    storage_uri: Optional[str] = None,
    direction: Optional[str] = None,
    metric_name: Optional[str] = None,
    strategy_name: Optional[str] = None,
    fail_on_error: bool | None = None,
    env: Mapping[str, str] | None = None,
) -> OptunaTuningSettings:
    source = os.environ if env is None else env
    active_direction = (direction or source.get("ML_OPTUNA_DIRECTION") or "maximize").lower()
    active_metric = (metric_name or source.get("ML_OPTUNA_METRIC") or "f1_macro").lower()

    settings = OptunaTuningSettings(
        enabled=env_bool("ML_OPTUNA_ENABLED", False, source) if enabled is None else enabled,
        n_trials=int(n_trials if n_trials is not None else env_int("ML_OPTUNA_N_TRIALS", 20, source)),
        timeout_seconds=(
            timeout_seconds
            if timeout_seconds is not None
            else env_int("ML_OPTUNA_TIMEOUT_SECONDS", None, source)
        ),
        study_name=study_name or source.get("ML_OPTUNA_STUDY_NAME") or None,
        storage_uri=storage_uri or source.get("ML_OPTUNA_STORAGE_URI") or None,
        direction=active_direction,
        metric_name=active_metric,
        strategy_name=strategy_name or source.get("ML_OPTUNA_STRATEGY") or None,
        fail_on_error=(
            env_bool("ML_OPTUNA_FAIL_ON_ERROR", False, source)
            if fail_on_error is None
            else fail_on_error
        ),
    )
    validate_settings(settings)
    return settings


def validate_settings(settings: OptunaTuningSettings) -> None:
    if settings.n_trials < 1:
        raise ValueError("Optuna n_trials must be >= 1.")
    if settings.timeout_seconds is not None and settings.timeout_seconds < 1:
        raise ValueError("Optuna timeout_seconds must be >= 1 when provided.")
    if settings.direction not in {"maximize", "minimize"}:
        raise ValueError("Optuna direction must be 'maximize' or 'minimize'.")
    if settings.metric_name not in SUPPORTED_METRICS:
        valid = ", ".join(sorted(SUPPORTED_METRICS))
        raise ValueError(f"Unsupported Optuna metric '{settings.metric_name}'. Valid: {valid}.")


def lightgbm_search_space(trial: Any) -> dict[str, Any]:
    return {
        "num_leaves": trial.suggest_int("num_leaves", 15, 63),
        "max_depth": trial.suggest_categorical("max_depth", [-1, 3, 5, 7, 9]),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.08, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 80, 360, step=40),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 80),
        "subsample": trial.suggest_float("subsample", 0.65, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.65, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 1.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
    }


def _empty_result(
    *,
    settings: OptunaTuningSettings,
    enabled: bool,
    reasons: list[str],
    study_name: Optional[str] = None,
) -> OptunaTuningResult:
    return OptunaTuningResult(
        enabled=enabled,
        study_name=study_name or settings.study_name,
        best_params={},
        best_value=None,
        best_trial_number=None,
        n_trials=settings.n_trials,
        timeout=settings.timeout_seconds,
        metric_name=settings.metric_name,
        reasons=reasons,
    )


def _target_matches(
    *,
    settings: OptunaTuningSettings,
    model_key: str,
    base_model_key: str,
) -> bool:
    if not settings.strategy_name:
        return True
    return settings.strategy_name in {model_key, base_model_key}


def _score_model(
    *,
    model: Pipeline,
    x_val: pd.DataFrame,
    y_val: pd.Series,
    metric_name: str,
) -> float:
    if metric_name == "f1_macro":
        return float(f1_score(y_val, model.predict(x_val), average="macro", zero_division=0))

    if metric_name == "accuracy":
        return float(accuracy_score(y_val, model.predict(x_val)))

    if metric_name == "log_loss":
        estimator = model.named_steps["model"]
        classes = list(getattr(estimator, "classes_", sorted(pd.Series(y_val).unique())))
        probabilities = model.predict_proba(x_val)
        return float(log_loss(y_val, probabilities, labels=classes))

    raise ValueError(f"Unsupported Optuna metric: {metric_name}")


def tune_lightgbm_pipeline(
    *,
    model_key: str,
    base_model_key: str,
    model: Pipeline,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_val: pd.DataFrame,
    y_val: pd.Series,
    sample_weight: Optional[np.ndarray],
    settings: OptunaTuningSettings,
    random_state: int,
) -> OptunaTuningResult:
    if not settings.enabled:
        return _empty_result(
            settings=settings,
            enabled=False,
            reasons=["Optuna tuning is disabled."],
        )

    if base_model_key != LIGHTGBM_BASE_MODEL_KEY:
        return _empty_result(
            settings=settings,
            enabled=False,
            reasons=["Optuna tuning is only enabled for LightGBM candidates."],
        )

    if not _target_matches(
        settings=settings,
        model_key=model_key,
        base_model_key=base_model_key,
    ):
        return _empty_result(
            settings=settings,
            enabled=False,
            reasons=[f"Optuna tuning target is {settings.strategy_name}; skipped {model_key}."],
        )

    study_name = settings.study_name or f"crypto_direction_optuna_{model_key}"

    try:
        import optuna

        sampler = optuna.samplers.TPESampler(seed=random_state)
        study = optuna.create_study(
            study_name=study_name,
            storage=settings.storage_uri,
            direction=settings.direction,
            sampler=sampler,
            load_if_exists=bool(settings.storage_uri),
        )

        def objective(trial: Any) -> float:
            trial_model = clone(model)
            search_params = lightgbm_search_space(trial)
            trial_model.set_params(
                **{f"model__{key}": value for key, value in search_params.items()}
            )

            fit_kwargs = {}
            if sample_weight is not None:
                fit_kwargs["model__sample_weight"] = sample_weight

            trial_model.fit(x_train, y_train, **fit_kwargs)
            return _score_model(
                model=trial_model,
                x_val=x_val,
                y_val=y_val,
                metric_name=settings.metric_name,
            )

        study.optimize(
            objective,
            n_trials=settings.n_trials,
            timeout=settings.timeout_seconds,
            n_jobs=1,
            show_progress_bar=False,
        )

        best_trial = study.best_trial
        return OptunaTuningResult(
            enabled=True,
            study_name=study.study_name,
            best_params=dict(best_trial.params),
            best_value=float(best_trial.value),
            best_trial_number=int(best_trial.number),
            n_trials=len(study.trials),
            timeout=settings.timeout_seconds,
            metric_name=settings.metric_name,
            reasons=["Optuna tuning completed."],
        )

    except Exception as exc:
        if settings.fail_on_error:
            raise

        print(f"[optuna][WARN] Tuning skipped after error: {exc}", file=sys.stderr)
        return _empty_result(
            settings=settings,
            enabled=True,
            study_name=study_name,
            reasons=[f"Optuna tuning failed: {exc}"],
        )
