# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

import argparse

from alerting.health_alert_service import HealthAlertService
from alerting.settings import load_settings

# Parse command-line arguments.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send Slack alerts for pipeline health checks.")
    parser.add_argument( # Add recent-minutes argument.
        "--recent-minutes",
        type=int,
        default=30,
        help="Lookback window for recent health check rows.",
    )
    parser.add_argument( # only send errors
        "--only-on-failure",
        action="store_true",
        help="Only send Slack message if there is at least one failed check.",
    )
    parser.add_argument(  # fail on critical
        "--fail-on-critical",
        action="store_true",
        help="Exit 1 if critical failures exist.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    service = HealthAlertService(settings)

    # Run the health alert.
    return service.run(
        recent_minutes=args.recent_minutes,
        only_on_failure=args.only_on_failure,
        fail_on_critical=args.fail_on_critical,
    )
