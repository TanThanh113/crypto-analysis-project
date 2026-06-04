from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import yaml


def load_feature_contract(path: str | Path) -> Dict[str, Any]:
    contract_path = Path(path)
    with contract_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid feature contract: {contract_path}")

    return data


def compute_feature_contract_hash(path: str | Path) -> str:
    data = load_feature_contract(path)
    normalized = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_feature_contract_metadata(path: str | Path) -> Dict[str, Any]:
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
