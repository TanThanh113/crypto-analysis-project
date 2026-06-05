from __future__ import annotations

import pytest

from strategy_config import get_strategy, list_strategy_names, list_strategies


def test_strategy_list_contains_initial_matrix():
    assert list_strategy_names() == [
        "logistic_baseline_all_history",
        "lightgbm_all_history_fixed_params",
        "lightgbm_rolling_180d",
        "lightgbm_rolling_90d",
    ]

    assert len(list_strategies()) == 4


def test_get_strategy_returns_metadata():
    strategy = get_strategy("lightgbm_rolling_90d")

    assert strategy.model_type == "lightgbm"
    assert strategy.base_model_key == "lightgbm_classifier"
    assert strategy.train_window_days == 90
    assert strategy.validation_policy == "rolling_window_before_validation"
    assert strategy.metadata() == {
        "strategy_name": "lightgbm_rolling_90d",
        "strategy_model_type": "lightgbm",
        "strategy_train_window_days": 90,
        "strategy_validation_policy": "rolling_window_before_validation",
        "model_choice": "lightgbm",
    }


def test_get_strategy_rejects_unknown_name():
    with pytest.raises(KeyError):
        get_strategy("unknown_strategy")
