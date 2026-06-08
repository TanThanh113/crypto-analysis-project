# ML and MLOps Lifecycle

## What this part does

The ML area trains and runs conservative directional signal models for analytics and research. It is not a trading bot and does not automate trades. Production defaults are artifact-first and feature-contract driven.

Optional MLOps features such as MLflow logging, Optuna tuning, and MLflow Registry loading are available only when explicitly configured.

## Where it lives

ML code lives under `ml`. Production-style entrypoints sit next to optional MLOps helpers and local research scripts.

## How it fits into the full platform

dbt ML marts provide training datasets and prediction inputs. ML training uses a conservative feature contract and writes artifacts only when configured. Prediction loads artifacts by default. Research scripts help evaluate candidates, but they are not production serving paths.

## Main flow

1. dbt prepares ML marts for training and prediction input.
2. `ml/feature_list.yml` defines the conservative production feature contract.
3. Training creates model artifacts when explicitly configured.
4. Optional MLflow, Optuna, and Registry helpers can be enabled for experiments.
5. Promotion gates prevent weaker candidates from being promoted automatically.
6. Prediction loads artifacts by default, with optional registry loading only when configured.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `ml/train_model.py` | Training entrypoint | Can write local/GCS artifacts when configured. |
| `ml/predict_latest.py` | Prediction entrypoint | Loads latest artifact or optional registry model. |
| `ml/feature_list.yml` | Production feature list | Conservative default contract; do not change casually. |
| `ml/feature_contract.py` | Feature contract hashing | Stable contract metadata and lineage. |
| `ml/promotion_gate.py` | Promotion gate | Prevents automatic promotion of weaker candidates. |
| `ml/model_loader.py` | Model loader | Artifact-first loading with optional registry support. |
| `ml/mlflow_utils.py` | Optional MLflow logging | Best-effort unless configured otherwise. |
| `ml/mlflow_registry.py` | Optional registry integration | Off unless explicitly configured. |
| `ml/optuna_tuning.py` | Optional tuning | Research/tuning support. |
| `ml/local_*.py` | Local research tools | Diagnostics, AutoML, ablation, recall focus, and keeper validation. |

## Production boundary

Production-style ML defaults are conservative. `ml/feature_list.yml` is the production contract. subset9 and microstructure features are research/manual candidates and have not replaced the baseline production contract. Local research scripts are not serving paths.

## Safety notes

- Do not run training or prediction as part of documentation work.
- Do not write GCS, BigQuery, MLflow Registry, or other remote artifacts unless intentionally configured.
- Do not commit ML artifacts, `.venv`, caches, local MLflow databases, or generated model files.
- Do not describe model output as trading advice or a guaranteed edge.

## Read next

- [dbt Models](dbt_models.md)
- [Production Boundaries](production_boundaries.md)
- [Kestra Orchestration](kestra_orchestration.md)
- [CI/CD Gates](ci_cd_gates.md)
