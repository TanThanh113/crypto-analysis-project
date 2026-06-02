# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

from alerting.cli import main

# Run the health alert.
# The goal is to make it return 0 and 1.
if __name__ == "__main__":
    raise SystemExit(main())
