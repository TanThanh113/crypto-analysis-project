from __future__ import annotations

import argparse
import sys
from pathlib import Path


# Allow running this file directly from /app/batch inside Docker.
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from validation.engine import run_validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate raw parquet dataset before Iceberg upload.")
    parser.add_argument("--dataset", required=True, help="Dataset ruleset name, e.g. funding_rates")
    parser.add_argument("--file_pattern", required=True, help="Parquet file pattern, e.g. funding_rates_*.parquet")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        run_validation(dataset=args.dataset, file_pattern=args.file_pattern)
        return 0
    except Exception as exc:
        print(f"[validator] ❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
