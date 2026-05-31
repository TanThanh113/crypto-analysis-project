from __future__ import annotations

import pandas as pd


def require_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    errors = []
    missing = [column for column in columns if column not in df.columns]

    if missing:
        errors.append(f"Missing required columns: {missing}")

    return errors


def min_rows(df: pd.DataFrame, count: int) -> list[str]:
    if len(df) < count:
        return [f"Expected at least {count} rows, got {len(df)}"]

    return []


def not_null(df: pd.DataFrame, columns: list[str]) -> list[str]:
    errors = []

    for column in columns:
        if column not in df.columns:
            errors.append(f"Column '{column}' does not exist for not_null check.")
            continue

        null_count = int(df[column].isna().sum())
        if null_count > 0:
            errors.append(f"Column '{column}' has {null_count} null values.")

    return errors


def accepted_values(df: pd.DataFrame, column: str, values: list) -> list[str]:
    if column not in df.columns:
        return [f"Column '{column}' does not exist for accepted_values check."]

    actual_values = set(df[column].dropna().unique().tolist())
    allowed_values = set(values)
    invalid_values = sorted(actual_values - allowed_values)

    if invalid_values:
        return [f"Column '{column}' has invalid values: {invalid_values[:20]}"]

    return []


def unique_key(df: pd.DataFrame, columns: list[str]) -> list[str]:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        return [f"Unique key columns missing: {missing}"]

    duplicate_count = int(df.duplicated(subset=columns).sum())
    if duplicate_count > 0:
        return [f"Unique key {columns} has {duplicate_count} duplicate rows."]

    return []


def numeric_range(
    df: pd.DataFrame,
    column: str,
    min_value: float | None = None,
    max_value: float | None = None,
) -> list[str]:
    if column not in df.columns:
        return [f"Column '{column}' does not exist for numeric_range check."]

    series = pd.to_numeric(df[column], errors="coerce")
    errors = []

    if min_value is not None:
        bad_count = int((series < min_value).sum())
        if bad_count > 0:
            errors.append(f"Column '{column}' has {bad_count} values < {min_value}.")

    if max_value is not None:
        bad_count = int((series > max_value).sum())
        if bad_count > 0:
            errors.append(f"Column '{column}' has {bad_count} values > {max_value}.")

    return errors
