# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

import argparse

from quality_audit.audit_service import QualityAuditService
from quality_audit.settings import load_settings

# Function to parse the command-line arguments.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Great Expectations audit for curated marts."
    )
    # Select the running mode
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit 1 if any critical expectation fails.",
    )
    return parser.parse_args()

# Run the audit service.
def main() -> int:
    args = parse_args()
    settings = load_settings()

    service = QualityAuditService(settings)
    return service.run(fail_on_critical=args.fail_on_critical)
