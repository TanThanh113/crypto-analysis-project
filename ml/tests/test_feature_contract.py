from __future__ import annotations

from feature_contract import compute_feature_contract_hash, get_feature_contract_metadata


def test_feature_contract_hash_is_stable_for_equivalent_yaml(tmp_path):
    first = tmp_path / "feature_a.yml"
    second = tmp_path / "feature_b.yml"

    first.write_text(
        """
model:
  model_name: crypto_direction_lgbm_v1
  model_version: v1
  target_name: future_direction_4h
  categorical_features:
    - symbol
  numeric_features:
    - return_1h
    - return_4h
""".strip(),
        encoding="utf-8",
    )
    second.write_text(
        """
model:
  numeric_features:
    - return_1h
    - return_4h
  categorical_features:
    - symbol
  target_name: future_direction_4h
  model_version: v1
  model_name: crypto_direction_lgbm_v1
""".strip(),
        encoding="utf-8",
    )

    assert compute_feature_contract_hash(first) == compute_feature_contract_hash(second)


def test_feature_contract_metadata_extraction(tmp_path):
    contract = tmp_path / "feature.yml"
    contract.write_text(
        """
model:
  model_name: crypto_direction_lgbm_v1
  model_version: v1
  target_name: future_direction_4h
  categorical_features:
    - symbol
  numeric_features:
    - return_1h
    - return_4h
""".strip(),
        encoding="utf-8",
    )

    metadata = get_feature_contract_metadata(contract)

    assert metadata["model_name"] == "crypto_direction_lgbm_v1"
    assert metadata["model_version"] == "v1"
    assert metadata["target_name"] == "future_direction_4h"
    assert metadata["numeric_feature_count"] == 2
    assert metadata["categorical_feature_count"] == 1
    assert metadata["total_feature_count"] == 3
    assert len(metadata["feature_contract_hash"]) == 64
