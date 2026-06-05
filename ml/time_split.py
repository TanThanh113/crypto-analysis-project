from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TimeSplitBounds:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp | None = None
    test_end: pd.Timestamp | None = None


def _timestamps_for_split(
    df: pd.DataFrame,
    *,
    split_column: str,
    timestamp_column: str,
    split_name: str,
) -> pd.Series:
    if split_column not in df.columns:
        raise ValueError(f"Missing split column: {split_column}")

    if timestamp_column not in df.columns:
        raise ValueError(f"Missing timestamp column: {timestamp_column}")

    timestamps = pd.to_datetime(
        df.loc[df[split_column] == split_name, timestamp_column],
        errors="coerce",
        utc=True,
    ).dropna()

    if timestamps.empty:
        raise ValueError(f"Split '{split_name}' has no valid {timestamp_column} values")

    return timestamps


def validate_time_split_order(
    df: pd.DataFrame,
    *,
    split_column: str,
    timestamp_column: str = "hour_ts",
) -> TimeSplitBounds:
    train_ts = _timestamps_for_split(
        df,
        split_column=split_column,
        timestamp_column=timestamp_column,
        split_name="train",
    )
    validation_ts = _timestamps_for_split(
        df,
        split_column=split_column,
        timestamp_column=timestamp_column,
        split_name="validation",
    )

    bounds = TimeSplitBounds(
        train_start=train_ts.min(),
        train_end=train_ts.max(),
        validation_start=validation_ts.min(),
        validation_end=validation_ts.max(),
        test_start=None,
        test_end=None,
    )

    if bounds.train_end >= bounds.validation_start:
        raise ValueError(
            "Time split leakage detected: train_end must be before validation_start "
            f"({bounds.train_end} >= {bounds.validation_start})."
        )

    if bounds.validation_start > bounds.validation_end:
        raise ValueError(
            "Invalid validation split: validation_start must be before or equal to validation_end."
        )

    if "test" not in set(df[split_column].dropna().astype(str)):
        return bounds

    test_ts = _timestamps_for_split(
        df,
        split_column=split_column,
        timestamp_column=timestamp_column,
        split_name="test",
    )

    return TimeSplitBounds(
        train_start=bounds.train_start,
        train_end=bounds.train_end,
        validation_start=bounds.validation_start,
        validation_end=bounds.validation_end,
        test_start=test_ts.min(),
        test_end=test_ts.max(),
    )


def select_rolling_training_window(
    df: pd.DataFrame,
    *,
    split_column: str,
    train_window_days: int,
    timestamp_column: str = "hour_ts",
) -> pd.DataFrame:
    if train_window_days <= 0:
        raise ValueError("train_window_days must be positive")

    validation_ts = _timestamps_for_split(
        df,
        split_column=split_column,
        timestamp_column=timestamp_column,
        split_name="validation",
    )
    validation_start = validation_ts.min()
    window_start = validation_start - pd.Timedelta(days=train_window_days)

    timestamps = pd.to_datetime(df[timestamp_column], errors="coerce", utc=True)
    is_train = df[split_column] == "train"
    keep_train = is_train & (timestamps >= window_start) & (timestamps < validation_start)

    filtered = df.loc[(~is_train) | keep_train].copy()
    validate_time_split_order(
        filtered,
        split_column=split_column,
        timestamp_column=timestamp_column,
    )
    return filtered


def apply_train_window(
    df: pd.DataFrame,
    *,
    split_column: str,
    train_window_days: int | None,
    timestamp_column: str = "hour_ts",
) -> pd.DataFrame:
    if train_window_days is None:
        validate_time_split_order(
            df,
            split_column=split_column,
            timestamp_column=timestamp_column,
        )
        return df.copy()

    return select_rolling_training_window(
        df,
        split_column=split_column,
        train_window_days=train_window_days,
        timestamp_column=timestamp_column,
    )
