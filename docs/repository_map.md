# Repository Map

This map groups the repository by function so reviewers can understand where to look and what to edit carefully.

## Batch Ingestion

| Path | Purpose | Edit carefully |
| --- | --- | --- |
| `local_scripts/batch` | Batch collectors, loaders, validators, health checks, alerting, quality audit | Source-specific collectors and cloud writes can affect cost and data quality |
| `local_scripts/batch/backfill` | Historical backfill scripts | Backfills can be expensive and should be run intentionally |
| `local_scripts/batch/common` | Shared BigQuery/io helpers | Changes can affect many collectors |

## Streaming

| Path | Purpose | Edit carefully |
| --- | --- | --- |
| `local_scripts/streaming/producer` | Local market/on-chain/sentiment producers | Live source assumptions and credentials |
| `local_scripts/streaming/logic_crypto_streaming` | Flink/Kafka-oriented transformation code | Sink schema and timestamp alignment |
| `local_scripts/streaming/scripts` | Sink specs and deployment helpers | Avoid committing secrets or local key files |

## Orchestration

| Path | Purpose | Edit carefully |
| --- | --- | --- |
| `kestra/flows-gke` | GKE-oriented production/preview Kestra flows | Flow triggers, namespaces, images, and cloud outputs |
| `kestra/flows` | Legacy/local Kestra flows | Keep behavior aligned if still referenced |
| `.github/scripts/deploy_kestra_flows.py` | Flow deployment helper | Deploy filtering and namespace behavior |
| `.github/scripts/kestra_deploy_plan.py` | PR deploy/build planning | CI gates and skip behavior |

## dbt Transformations

| Path | Purpose | Edit carefully |
| --- | --- | --- |
| `dbt_transform/crypto_dbt/models/staging` | Source normalization | Source schema changes |
| `dbt_transform/crypto_dbt/models/intermediate` | Aggregation and feature preparation | Time alignment and joins |
| `dbt_transform/crypto_dbt/models/marts/core` | Shared facts and dimensions | Downstream dashboard/ML dependencies |
| `dbt_transform/crypto_dbt/models/marts/dashboard` | BI-ready marts | Dashboard contracts |
| `dbt_transform/crypto_dbt/models/marts/ml` | ML features, labels, training, prediction, metrics | Label leakage and feature contract compatibility |
| `dbt_transform/crypto_dbt/models/marts/monitoring` | Pipeline health and audit marts | Operational alert semantics |

## ML Training and Prediction

| Path | Purpose | Edit carefully |
| --- | --- | --- |
| `ml/train_model.py` | Training entrypoint | BigQuery writes, GCS artifacts, promotion, optional MLflow/Registry |
| `ml/predict_latest.py` | Prediction entrypoint | Prediction schema and artifact/registry loading |
| `ml/feature_list.yml` | Production feature contract | Do not casually enable research features |
| `ml/model_loader.py` | Artifact/registry loading | Fallback behavior |

## MLOps Utilities

| Path | Purpose | Edit carefully |
| --- | --- | --- |
| `ml/mlflow_utils.py` | Optional MLflow experiment logging | Must remain best-effort unless fail-on-error is explicit |
| `ml/mlflow_registry.py` | Optional registry integration | Avoid deprecated stages and accidental remote updates |
| `ml/optuna_tuning.py` | Optional tuning | Do not tune on test set |
| `ml/promotion_gate.py` | Candidate promotion controls | Keep conservative defaults |
| `ml/strategy_config.py` | Strategy matrix definitions | Backward compatibility with `--model-choice auto` |
| `ml/time_split.py` | Time-series split helpers | Anti-leakage behavior |

## Local Research Tools

| Path | Purpose | Edit carefully |
| --- | --- | --- |
| `ml/local_*.py` | Local AutoML, diagnostics, ablation, keeper validation, readiness review | Keep artifacts local and avoid production writes |
| `ml/research/configs` | Research-only feature contracts | Do not confuse with production `feature_list.yml` |
| `ml/tests` | Cloud-free tests for ML utilities and research tooling | Keep tests isolated from GCS/BigQuery writes |

## Infrastructure

| Path | Purpose | Edit carefully |
| --- | --- | --- |
| `terraform` | Main GCP infrastructure | State, IAM, datasets, buckets, GKE, Cloud SQL |
| `terraform-bootstrap` | Bootstrap setup | IAM/service account changes |
| `terraform-grafana` | Grafana-related infrastructure | Dashboard/provider config |
| `helm` and `k8s` | Kestra runtime support | Runtime services and namespaces |

## CI/CD

| Path | Purpose | Edit carefully |
| --- | --- | --- |
| `.github/workflows/quality-check.yml` | Main quality/test checks | Required validation coverage |
| `.github/workflows/docker-build-push.yml` | Docker build/smoke/push workflow | Build gates and cloud auth |
| `.github/workflows/kestra-deploy-gke.yml` | Kestra deploy workflow | Port-forward/deploy gating |
| `.github/workflows/pr-required-gate.yml` | Required-check aggregation | Required/skipped check semantics |

## Docker Images

| Path | Purpose |
| --- | --- |
| `docker/batch.Dockerfile` | Production batch image |
| `docker/dbt.Dockerfile` | Production dbt image |
| `docker/ml.Dockerfile` | Production ML image |

## Tests and Guards

| Path | Purpose |
| --- | --- |
| `ml/tests` | ML utility and local research tests |
| `scripts/repo_guard.py` | Production repository guard |
| `dbt_transform/crypto_dbt/tests` | dbt test folder |

## Documentation

| Path | Purpose |
| --- | --- |
| `README.md` | Portfolio-level overview |
| `docs/architecture.md` | Architecture diagrams and flow descriptions |
| `docs/*_pipeline.md`, `docs/*models.md`, `docs/*orchestration.md` | Module-specific documentation |
| `docs/runbook.md`, `docs/production-runbook.md` | Operational runbooks |
