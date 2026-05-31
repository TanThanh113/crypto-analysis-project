from __future__ import annotations

import glob
import os
from pathlib import Path

import pandas as pd


def find_input_files(output_dir: str, file_pattern: str) -> list[Path]:
    """
    Find parquet files recursively under OUTPUT_DIR.

    Recursive search is important because some collectors write:
      output_data/raw/*.parquet
      output_data/summary/*.parquet
    while others write directly:
      output_data/*.parquet
    """
    base = Path(output_dir)

    direct_pattern = str(base / file_pattern)
    recursive_pattern = str(base / "**" / file_pattern)

    files = set(glob.glob(direct_pattern))
    files.update(glob.glob(recursive_pattern, recursive=True))

    return sorted(Path(path) for path in files if Path(path).is_file())


def load_parquet_files(files: list[Path]) -> pd.DataFrame:
    if not files:
        raise FileNotFoundError("No input parquet files found.")

    frames = []
    for file_path in files:
        frames.append(pd.read_parquet(file_path))

    if not frames:
        raise ValueError("No parquet dataframes were loaded.")

    return pd.concat(frames, ignore_index=True)


def get_output_dir() -> str:
    return os.environ.get("OUTPUT_DIR", "output_data")
