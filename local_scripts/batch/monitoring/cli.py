from __future__ import annotations

import argparse

from monitoring.health_service import PipelineHealthService
from monitoring.settings import load_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run production pipeline health checks.")
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit 1 if any critical health check fails.",
    )
    parser.add_argument(
        "--no-write-results",
        action="store_true",
        help="Do not write health check results to BigQuery.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()

    service = PipelineHealthService(settings)
    return service.run(
        fail_on_critical=args.fail_on_critical,
        write_results=not args.no_write_results,
    )
