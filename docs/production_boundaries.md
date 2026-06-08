# Production Boundaries

## What this part does

This document separates conservative production defaults from research-only and optional workflows. The project is an analytics and ML signal platform, not a trading bot, and production-style defaults should stay conservative.

## Where it lives

Production and research boundaries are most visible under `ml`, `dbt_transform/crypto_dbt/models/marts/ml`, `kestra/flows-gke/ml`, and `docs`.

## How it fits into the full platform

Batch and dbt prepare data for ML. ML code trains or predicts using a conservative feature contract. Kestra can orchestrate ML jobs, but deployment is gated. Research scripts explore candidates locally and do not become production serving paths by default.

## Main flow

1. Production features are defined by `ml/feature_list.yml`.
2. Training uses `ml/train_model.py` and the feature contract.
3. Prediction uses `ml/predict_latest.py` and artifact-first loading.
4. `ml/promotion_gate.py` prevents weaker candidates from being promoted automatically.
5. Optional MLflow, Optuna, and Registry helpers remain off unless configured.
6. Local research scripts stay manual and local-first.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `ml/train_model.py` | Training entrypoint | Production-style, but run only when intentionally configured. |
| `ml/predict_latest.py` | Prediction entrypoint | Artifact-first prediction path. |
| `ml/feature_list.yml` | Production feature contract | Conservative default; do not change casually. |
| `ml/feature_contract.py` | Contract hashing | Keeps feature contract metadata stable. |
| `ml/promotion_gate.py` | Promotion gate | Prevents automatic promotion of weaker candidates. |
| `ml/model_loader.py` | Model loader | Artifact-first with optional registry support. |
| `ml/local_automl_research.py` | Local AutoML research | Research-only. |
| `ml/local_feature_label_diagnostics.py` | Feature/label diagnostics | Research-only. |
| `ml/local_feature_engineering_research.py` | Feature engineering research | Research-only. |
| `ml/local_feature_ablation_research.py` | Feature ablation research | Research-only. |
| `ml/local_down_recall_focus_research.py` | Down recall research | Research-only. |
| `ml/local_keeper_candidate_validation.py` | Keeper validation | Research-only. |

## Production boundary

Production defaults are conservative production-style defaults, not a claim of complete production maturity. subset9 and microstructure features are research/manual candidates. MLflow, Optuna, and Registry integration are optional and off by default. Prediction should not be described as automated trading.

## Safety notes

- Do not run training, prediction, promotion, or registry updates for documentation work.
- Do not change `ml/feature_list.yml` casually.
- Do not commit model artifacts, local MLflow data, caches, `.venv`, or generated outputs.
- Do not infer model edge from partial data coverage.

## Read next

- [ML and MLOps](ml_mLOps.md)
- [dbt Models](dbt_models.md)
- [Kestra Orchestration](kestra_orchestration.md)
- [Repository Map](repository_map.md)
