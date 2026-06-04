from __future__ import annotations

import re
from pathlib import Path


ML_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = [
    ML_ROOT / "train_model.py",
    ML_ROOT / "mlflow_utils.py",
    ML_ROOT / "feature_contract.py",
]

FORBIDDEN_PATTERNS = [
    re.compile(r"\bcurrent_stage\b"),
    re.compile(r"\btransition_model_version_stage\b"),
    re.compile(r"\barchive_existing_versions\b"),
    re.compile(r"get_latest_versions\s*\([^)]*\bstages\s*=", re.DOTALL),
    re.compile(r"models:/[^\s'\"]+/Production"),
    re.compile(r"models:/[^\s'\"]+/Staging"),
    re.compile(r"\bregister_model\s*\("),
    re.compile(r"\bcreate_registered_model\s*\("),
    re.compile(r"\bset_registered_model_alias\s*\("),
    re.compile(r"\bget_model_version_by_alias\s*\("),
]


def test_no_deprecated_stage_or_registry_usage_in_phase_1_sources():
    violations = []

    for source_file in SOURCE_FILES:
        content = source_file.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(content):
                violations.append(f"{source_file.name}: {pattern.pattern}")

    assert violations == []
