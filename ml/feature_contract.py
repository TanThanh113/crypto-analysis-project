"""Feature-contract helpers for training and prediction lineage.

The production feature contract lives in feature_list.yml. This module loads
that YAML, computes a stable hash from normalized content, and exposes summary
metadata for MLflow/artifact logging. It has no side effects and does not change
train or predict behavior.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import yaml


def load_feature_contract(path: str | Path) -> Dict[str, Any]:
    """Load feature_list.yml as a dictionary.

    Raises ValueError if the YAML root is not a mapping. The function is
    read-only and does not validate BigQuery schemas or mutate config values.
    """
    contract_path = Path(path)
    with contract_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid feature contract: {contract_path}")

    return data


def compute_feature_contract_hash(path: str | Path) -> str:
    """Return a stable SHA-256 hash for a feature contract file.

    The YAML is parsed and JSON-normalized with sorted keys before hashing so
    semantically equivalent key ordering produces the same lineage hash.
    """
    data = load_feature_contract(path)
    normalized = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_feature_contract_metadata(path: str | Path) -> Dict[str, Any]:
    """Return feature-contract metadata for logging and artifacts."""
    data = load_feature_contract(path)
    model = data.get("model", {})

    categorical_features = list(model.get("categorical_features", []) or [])
    numeric_features = list(model.get("numeric_features", []) or [])

    return {
        "feature_contract_hash": compute_feature_contract_hash(path),
        "model_name": model.get("model_name"),
        "model_version": model.get("model_version"),
        "target_name": model.get("target_name"),
        "numeric_feature_count": len(numeric_features),
        "categorical_feature_count": len(categorical_features),
        "total_feature_count": len(numeric_features) + len(categorical_features),
    }
