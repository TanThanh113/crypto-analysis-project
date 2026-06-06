"""Named training strategies for the ML strategy matrix.

Strategies describe which base model to train, whether to use all history or a
rolling training window, and which validation policy is being tested. The
default train_model.py behavior remains backward compatible when no strategy
flag is provided.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# This file contains the training strategy configuration.
@dataclass(frozen=True)
class TrainingStrategy:
    name: str
    model_type: str
    base_model_key: str
    train_window_days: int | None
    validation_policy: str

    # This is the model choice for the strategy.
    @property
    def model_choice(self) -> str:
        return self.model_type

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy_name": self.name,
            "strategy_model_type": self.model_type,
            "strategy_train_window_days": (
                self.train_window_days
                if self.train_window_days is not None
                else "all_history"
            ),
            "strategy_validation_policy": self.validation_policy,
            "model_choice": self.model_choice,
        }

# The training strategies.
_STRATEGIES = (
    TrainingStrategy(
        name="logistic_baseline_all_history",
        model_type="logistic",
        base_model_key="logistic_regression_baseline",
        train_window_days=None,
        validation_policy="fixed_split_all_history",
    ),
    TrainingStrategy(
        name="lightgbm_all_history_fixed_params",
        model_type="lightgbm",
        base_model_key="lightgbm_classifier",
        train_window_days=None,
        validation_policy="fixed_split_all_history",
    ),
    TrainingStrategy(
        name="lightgbm_rolling_180d",
        model_type="lightgbm",
        base_model_key="lightgbm_classifier",
        train_window_days=180,
        validation_policy="rolling_window_before_validation",
    ),
    TrainingStrategy(
        name="lightgbm_rolling_90d",
        model_type="lightgbm",
        base_model_key="lightgbm_classifier",
        train_window_days=90,
        validation_policy="rolling_window_before_validation",
    ),
)

_STRATEGIES_BY_NAME = {strategy.name: strategy for strategy in _STRATEGIES}

# Returns a raw list of all four strategic entities as a list array.
def list_strategies() -> list[TrainingStrategy]:
    """Return all configured training strategies in deterministic order."""
    return list(_STRATEGIES)

# Returns a list containing only the strings containing the strategy names
# (["logistic_baseline_all_history", "lightgbm_all_history_fixed_params", ...])
def list_strategy_names() -> list[str]:
    """Return valid CLI choices for --strategy."""
    return [strategy.name for strategy in _STRATEGIES]

# The strategic plan involves a tight defense.
def get_strategy(name: str) -> TrainingStrategy:
    """Look up a named strategy or raise a clear KeyError."""
    try:
        return _STRATEGIES_BY_NAME[name]
    except KeyError as exc:
        valid_names = ", ".join(list_strategy_names())
        raise KeyError(f"Unknown training strategy '{name}'. Valid strategies: {valid_names}") from exc
