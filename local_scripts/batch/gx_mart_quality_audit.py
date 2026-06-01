# This allows you to use advanced type hinting without errors, unlike older Python versions.
from __future__ import annotations

import sys
from pathlib import Path

# Add the current directory to the system path.
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from quality_audit.cli import main

# Run the main function(return 0 if success, 1 if failure)
if __name__ == "__main__":
    raise SystemExit(main())
