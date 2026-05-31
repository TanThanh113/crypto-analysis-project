from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from validation.io import find_input_files, get_output_dir, load_parquet_files
from validation.rules import (
    accepted_values,
    min_rows,
    not_null,
    numeric_range,
    require_columns,
    unique_key,
)


RULESET_DIR = Path(__file__).resolve().parent / "rulesets"


def load_ruleset(dataset: str) -> dict[str, Any]:
    path = RULESET_DIR / f"{dataset}.yml"

    if not path.exists():
        raise FileNotFoundError(f"Ruleset not found for dataset '{dataset}': {path}")

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_validation(dataset: str, file_pattern: str) -> None:
    output_dir = get_output_dir()
    ruleset = load_ruleset(dataset)

    files = find_input_files(output_dir=output_dir, file_pattern=file_pattern)
    if not files:
        raise FileNotFoundError(
            f"No files found for dataset='{dataset}', pattern='{file_pattern}', output_dir='{output_dir}'"
        )

    print(f"[validator] Dataset: {dataset}")
    print(f"[validator] Output dir: {output_dir}")
    print(f"[validator] File pattern: {file_pattern}")
    for file_path in files:
        print(f"[validator] Input file: {file_path}")

    df = load_parquet_files(files)
    print(f"[validator] Loaded rows: {len(df)}")
    print(f"[validator] Loaded columns: {len(df.columns)}")

    errors: list[str] = []

    required_columns = ruleset.get("required_columns", [])
    if required_columns:
        errors.extend(require_columns(df, required_columns))

    min_row_count = ruleset.get("min_rows")
    if min_row_count is not None:
        errors.extend(min_rows(df, int(min_row_count)))

    not_null_columns = ruleset.get("not_null", [])
    if not_null_columns:
        errors.extend(not_null(df, not_null_columns))

    for check in ruleset.get("accepted_values", []):
        errors.extend(
            accepted_values(
                df,
                column=check["column"],
                values=check["values"],
            )
        )

    for key_columns in ruleset.get("unique_keys", []):
        errors.extend(unique_key(df, key_columns))

    for check in ruleset.get("numeric_ranges", []):
        errors.extend(
            numeric_range(
                df,
                column=check["column"],
                min_value=check.get("min"),
                max_value=check.get("max"),
            )
        )

    if errors:
        print("\n[validator] ❌ Validation failed:")
        for error in errors:
            print(f"  - {error}")
        raise RuntimeError(f"Validation failed for dataset '{dataset}' with {len(errors)} error(s).")

    print(f"[validator] ✅ Dataset '{dataset}' passed validation.")
