"""Optional Optuna tuning helpers for training candidates.

Optuna is off by default and currently targets LightGBM candidates. Tuning uses
validation data for model selection and must not tune directly on the test set.
Failures are best-effort unless fail-on-error is explicitly enabled.
"""

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

# OptunaTuningSettings contains the configuration settings for Optuna.
@dataclass(frozen=True)
class OptunaTuningSettings:
    enabled: bool # Whether to enable Optuna tuning.
    n_trials: int # Number of trials to run.
    timeout_seconds: Optional[int] # Timeout in seconds.

    study_name: Optional[str] # Name of this experiment
    storage_uri: Optional[str] # The database storage location of Optuna(SQLite, MySQL, PostgreSQL, etc.)

    direction: str # Direction of the optimization.
    metric_name: str # Metric to optimize.

    strategy_name: Optional[str] # What strategic limits are allowed for optimization?
    fail_on_error: bool # Fail the training run if Optuna fails?

# OptunaTuningResult contains the results of the Optuna tuning process.
@dataclass(frozen=True)
class OptunaTuningResult:
    enabled: bool # Whether to enable Optuna tuning.
    study_name: Optional[str] # Name of this experiment

    best_params: dict[str, Any] # Dictionary contains a set of top knob configurations that produce the highest scores.
    best_value: Optional[float] # The best value found during tuning.
    best_trial_number: Optional[int]  # The trial number corresponding to the best value.

    n_trials: int # Number of trials to run.
    timeout: Optional[int] # Timeout in seconds.
    metric_name: str # Metric to optimize.
    reasons: list[str] # Reasons for Optuna tuning.

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self) # Convert to a dictionary

        payload["best_params"] = dict(self.best_params or {}) # Convert best_params to a dictionary
        payload["reasons"] = list(self.reasons or []) # Convert reasons to a list
        return payload

# Check if the environment variable is true.
def env_bool(name: str, default: bool = False, env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env # Get the environment variables
    value = source.get(name)
    if value is None: # If the value is not found, return the default value
        return default
    return value.strip().lower() in TRUE_VALUES

# Get the environment variable as an integer.
def env_int(name: str, default: Optional[int], env: Mapping[str, str] | None = None) -> Optional[int]:
    source = os.environ if env is None else env # Get the environment variables
    value = source.get(name)
    if value is None or value.strip() == "": # If the value is not found or empty, return the default value
        return default
    return int(value)

# Get the Optuna tuning settings from the environment variables.
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
    """Resolve Optuna settings from CLI overrides and environment variables."""
    # Get the environment variables
    source = os.environ if env is None else env
    active_direction = (direction or source.get("ML_OPTUNA_DIRECTION") or "maximize").lower()
    active_metric = (metric_name or source.get("ML_OPTUNA_METRIC") or "f1_macro").lower()

    # Create a OptunaTuningSettings object
    settings = OptunaTuningSettings(
        # Get the enabled value(use env_bool to convert to bool)
        enabled=env_bool("ML_OPTUNA_ENABLED", False, source) if enabled is None else enabled,

        # Get the n_trials and timeout_seconds values(use env_int to convert to int)
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

        # Get the fail_on_error value(use env_bool to convert to bool)
        fail_on_error=(
            env_bool("ML_OPTUNA_FAIL_ON_ERROR", False, source)
            if fail_on_error is None
            else fail_on_error
        ),
    )
    # Validate the settings
    validate_settings(settings)
    return settings

# Validate the settings.
def validate_settings(settings: OptunaTuningSettings) -> None:
    # Check if the n_trials is greater than or equal to 1
    if settings.n_trials < 1:
        raise ValueError("Optuna n_trials must be >= 1.")

    # Check if the timeout_seconds is greater than or equal to 1
    if settings.timeout_seconds is not None and settings.timeout_seconds < 1:
        raise ValueError("Optuna timeout_seconds must be >= 1 when provided.")

    # Check if the direction is either 'maximize' or 'minimize'
    if settings.direction not in {"maximize", "minimize"}:
        raise ValueError("Optuna direction must be 'maximize' or 'minimize'.")

    # Check if the metric_name is supported
    if settings.metric_name not in SUPPORTED_METRICS:
        valid = ", ".join(sorted(SUPPORTED_METRICS))
        raise ValueError(f"Unsupported Optuna metric '{settings.metric_name}'. Valid: {valid}.")

# Create a search space for LightGBM.
# This function tells Optina where the LightGBM configuration knobs can be turned (within a certain range).

# Note: For microscopic parameters such as penalty coefficients or learning rates, conventional arithmetic (linear)
# search would be very poor, so logarithms must be used instead.
def lightgbm_search_space(trial: Any) -> dict[str, Any]:
    """Define the conservative LightGBM search space used by Optuna."""
    return {
        "num_leaves": trial.suggest_int("num_leaves", 15, 63),
        "max_depth": trial.suggest_categorical("max_depth", [-1, 3, 5, 7, 9]),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.08, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 80, 360, step=40), # Step=40 means Optuna will only test numbers that are multiples of 40.
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 80),
        "subsample": trial.suggest_float("subsample", 0.65, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.65, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 1.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
    }

# Create an empty result for Optuna tuning(This is used when Optuna is disabled.)
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

# Check if the model_key or the base_model_key matches the strategy_name.
def _target_matches(
    *,
    settings: OptunaTuningSettings,
    model_key: str,
    base_model_key: str,
) -> bool:
    # All LightGBM candidate models participating in this run will undergo parameter optimization.
    if not settings.strategy_name:
        return True
    # If the strategy_name matches the model_key or the base_model_key, the model will be optimized.
    return settings.strategy_name in {model_key, base_model_key}

# Score the model.
def _score_model(
    *,
    model: Pipeline,
    x_val: pd.DataFrame,
    y_val: pd.Series,
    metric_name: str,
) -> float:
    # Calculate the F1 score for the model.
    if metric_name == "f1_macro":
        return float(f1_score(y_val, model.predict(x_val), average="macro", zero_division=0))

    # Calculate the accuracy score for the model.
    if metric_name == "accuracy":
        return float(accuracy_score(y_val, model.predict(x_val)))

    # Calculate the log loss score for the model.
    if metric_name == "log_loss":
        estimator = model.named_steps["model"]
        classes = list(getattr(estimator, "classes_", sorted(pd.Series(y_val).unique())))
        probabilities = model.predict_proba(x_val)
        return float(log_loss(y_val, probabilities, labels=classes))

    # Raise an error for unsupported metrics.
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
    """Tune a LightGBM pipeline on validation data when Optuna is enabled.

    The test split is not passed into this function. Unsupported model types or
    non-targeted strategies return a disabled/skipped result instead of changing
    the training path.
    """
    # Check if Optuna tuning is enabled.
    if not settings.enabled:
        return _empty_result(
            settings=settings,
            enabled=False,
            reasons=["Optuna tuning is disabled."],
        )

    # Check if the base_model_key is LightGBM.
    if base_model_key != LIGHTGBM_BASE_MODEL_KEY:
        return _empty_result(
            settings=settings,
            enabled=False,
            reasons=["Optuna tuning is only enabled for LightGBM candidates."],
        )

    # Check if the model_key or the base_model_key matches the strategy_name.
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

        # Create an Optuna sampler.
        sampler = optuna.samplers.TPESampler(seed=random_state)
        study = optuna.create_study( # Create an Optuna study.
            study_name=study_name,
            storage=settings.storage_uri,
            direction=settings.direction,
            sampler=sampler,
            load_if_exists=bool(settings.storage_uri), # Load the study if it exists.
        )

        def objective(trial: Any) -> float:
            trial_model = clone(model) # Create a copy of the model.
            # Set the search parameters for the trial.
            search_params = lightgbm_search_space(trial)
            trial_model.set_params(
                **{f"model__{key}": value for key, value in search_params.items()}
            )

            # Load sample weights and train the model on the Train set.
            fit_kwargs = {}
            if sample_weight is not None:
                fit_kwargs["model__sample_weight"] = sample_weight

            # Train the model on the Train set.
            trial_model.fit(x_train, y_train, **fit_kwargs)
            return _score_model(
                model=trial_model,
                x_val=x_val,
                y_val=y_val,
                metric_name=settings.metric_name,
            )
        # Optimize the model using the objective function.
        study.optimize(
            objective,
            n_trials=settings.n_trials,
            timeout=settings.timeout_seconds,
            n_jobs=1,
            show_progress_bar=False,
        )

        # Get the best trial.
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

    # Handle exceptions.
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
