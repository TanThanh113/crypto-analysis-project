from __future__ import annotations

from argparse import Namespace

import pandas as pd
import pytest

from time_split import select_rolling_training_window, validate_time_split_order
from train_model import resolve_requested_strategies


def _sample_split_df() -> pd.DataFrame:
    rows = []
    for day in range(1, 11):
        rows.append({"hour_ts": f"2024-01-{day:02d}T00:00:00Z", "split_name": "train"})
    for day in range(11, 14):
        rows.append({"hour_ts": f"2024-01-{day:02d}T00:00:00Z", "split_name": "validation"})
    for day in range(14, 16):
        rows.append({"hour_ts": f"2024-01-{day:02d}T00:00:00Z", "split_name": "test"})
    return pd.DataFrame(rows)


def test_rolling_window_selects_expected_train_range():
    df = _sample_split_df()

    rolled = select_rolling_training_window(
        df,
        split_column="split_name",
        train_window_days=5,
    )
    train_dates = pd.to_datetime(
        rolled.loc[rolled["split_name"] == "train", "hour_ts"],
        utc=True,
    )

    assert train_dates.min() == pd.Timestamp("2024-01-06T00:00:00Z")
    assert train_dates.max() == pd.Timestamp("2024-01-10T00:00:00Z")
    assert len(train_dates) == 5
    assert len(rolled[rolled["split_name"] == "validation"]) == 3
    assert len(rolled[rolled["split_name"] == "test"]) == 2


def test_time_split_order_has_no_leakage():
    bounds = validate_time_split_order(
        _sample_split_df(),
        split_column="split_name",
    )

    assert bounds.train_end < bounds.validation_start <= bounds.validation_end


def test_time_split_order_rejects_train_validation_overlap():
    df = pd.DataFrame(
        [
            {"hour_ts": "2024-01-11T00:00:00Z", "split_name": "train"},
            {"hour_ts": "2024-01-10T00:00:00Z", "split_name": "validation"},
        ]
    )

    with pytest.raises(ValueError, match="Time split leakage"):
        validate_time_split_order(df, split_column="split_name")


def test_default_behavior_does_not_request_strategy():
    args = Namespace(strategy=None, strategy_matrix=False)

    assert resolve_requested_strategies(args) == []
