# Repository Map

## What this part does

This document groups the repository by subsystem so a new reviewer can understand where to look, what each area does, and what to edit carefully.

## Where it lives

This is a documentation guide for the full repository. It intentionally avoids exposing secrets, local credentials, generated artifacts, Terraform state, and local outputs as actionable paths.

## How it fits into the full platform

The repository combines data ingestion, transformations, orchestration, runtime infrastructure, infrastructure-as-code, ML, CI/CD, and documentation. The map below helps reviewers move from high-level docs into the relevant subsystem.

## Main flow

1. Start with Documentation.
2. Review Batch and Streaming ingestion.
3. Review dbt transforms and ML/MLOps.
4. Review Kestra orchestration and K8s/GKE runtime.
5. Review Terraform infrastructure and Docker images.
6. Review CI/CD, tests, research-only tooling, and generated artifacts to avoid.

## Important files and folders

| Group | Path | Purpose | Type | Caution |
| --- | --- | --- | --- | --- |
| Documentation | `README.md` | Portfolio overview and reading path | Docs | Keep scope accurate; not a trading bot. |
| Documentation | `docs/interactive/index.html` | Static project explorer | Docs | No backend or build step. |
| Documentation | `docs/architecture.md` | Architecture guide | Docs | Keep links relative and valid. |
| Documentation | `docs/*_pipeline.md`, `docs/*models.md`, `docs/*orchestration.md` | Subsystem docs | Docs | Avoid claims of complete production maturity. |
| Batch ingestion | `local_scripts/batch` | Collectors, validation, monitoring, quality audit | Runtime | Cloud writes and source assumptions can affect cost/data quality. |
| Batch ingestion | `local_scripts/batch/backfill` | Historical loaders | Runtime | Do not run casually. |
| Batch ingestion | `local_scripts/batch/validation/rulesets` | YAML validation rules | Runtime | Keep source-specific expectations accurate. |
| Streaming | `local_scripts/streaming/producer` | Market/on-chain/sentiment producers | Runtime/experimental | Avoid committing `.env` or keys. |
| Streaming | `local_scripts/streaming/logic_crypto_streaming` | Flink/Kafka-oriented logic | Runtime/experimental | Sink schema and freshness need validation. |
| Streaming | `local_scripts/streaming/scripts` | Sink specs and helper scripts | Runtime/config | Do not commit secrets or connector keys. |
| dbt transforms | `dbt_transform/crypto_dbt/models/staging` | Source normalization | Runtime | Source schema changes affect downstream layers. |
| dbt transforms | `dbt_transform/crypto_dbt/models/intermediate` | Time alignment and aggregation | Runtime | Watch joins, timestamp logic, and leakage. |
| dbt transforms | `dbt_transform/crypto_dbt/models/marts/core` | Reusable analytics facts | Runtime | Downstream dependency surface. |
| dbt transforms | `dbt_transform/crypto_dbt/models/marts/dashboard` | BI-ready marts | Runtime | Dashboard contract changes should be intentional. |
| dbt transforms | `dbt_transform/crypto_dbt/models/marts/ml` | ML datasets, inputs, metrics | Runtime/ML | Protect feature contract and label logic. |
| dbt transforms | `dbt_transform/crypto_dbt/models/marts/monitoring` | Freshness and quality marts | Runtime/monitoring | Alert semantics matter. |
| ML and MLOps | `ml/train_model.py` | Training entrypoint | Runtime/ML | Can write artifacts when configured. |
| ML and MLOps | `ml/predict_latest.py` | Prediction entrypoint | Runtime/ML | Artifact/registry loading boundary. |
| ML and MLOps | `ml/feature_list.yml` | Production feature contract | Runtime/ML | Do not change casually. |
| ML and MLOps | `ml/mlflow_utils.py`, `ml/mlflow_registry.py`, `ml/optuna_tuning.py` | Optional MLOps helpers | Optional/ML | Off unless explicitly configured. |
| Kestra orchestration | `kestra/flows-gke` | Production-style flow definitions | Runtime/orchestration | Triggers, namespaces, images, and destinations need review. |
| Kestra orchestration | `kestra/flows` | Local/legacy flow definitions | Runtime/orchestration | Keep aligned only if still referenced. |
| K8s / GKE runtime | `k8s` | Kubernetes support manifests | Infra/runtime | No secrets or key material. |
| K8s / GKE runtime | `helm/kestra/values-gke.yaml` | Kestra Helm values | Infra/runtime | Cloud SQL, identity, and secrets dependencies matter. |
| K8s / GKE runtime | `docker` | Runtime Dockerfiles | Runtime | Builds should stay gated. |
| Terraform infrastructure | `terraform` | Main GCP resources | Infra | Never commit state, secret tfvars, or credentials. |
| Terraform infrastructure | `terraform-bootstrap` | Bootstrap IAM/service-account setup | Infra | IAM changes can affect access. |
| Terraform infrastructure | `terraform-grafana` | Grafana-related infrastructure | Infra | Provider/config changes can affect dashboards. |
| Docker images | `docker/batch.Dockerfile` | Batch runtime image | Runtime | Build only when gated. |
| Docker images | `docker/dbt.Dockerfile` | dbt runtime image | Runtime | Build only when gated. |
| Docker images | `docker/ml.Dockerfile` | ML runtime image | Runtime/ML | Build only when gated. |
| CI/CD | `.github/workflows` | GitHub Actions workflows | CI/CD | Do not loosen gates casually. |
| CI/CD | `.github/scripts` | CI helper scripts | CI/CD | Deploy planning affects runtime behavior. |
| CI/CD | `scripts/repo_guard.py` | Repository guard | CI/CD | Keep safety checks intact. |
| Tests | `ml/tests` | ML tests | Tests | Keep cloud-free. |
| Tests | `dbt_transform/crypto_dbt/tests` | dbt tests folder | Tests | Avoid generated target artifacts. |
| Research-only tooling | `ml/local_*.py` | Local diagnostics, AutoML, ablation, keeper validation | Research | Keep local and manual. |
| Research-only tooling | `ml/research/configs` | Research feature configs | Research | Do not confuse with `ml/feature_list.yml`. |

## Local/generated artifacts to avoid committing

| Path pattern | Why to avoid it |
| --- | --- |
| `.env` files | May contain credentials or local config. |
| `local_scripts/streaming/secrets` | May contain connector keys or secret material. |
| `terraform/*.tfstate`, `terraform*/*.tfvars` | State and tfvars can expose resource state or secrets. |
| `dbt_transform/crypto_dbt/target`, `dbt_transform/crypto_dbt/logs` | Generated dbt artifacts and logs. |
| `ml/artifacts`, `ml/.venv`, `ml/__pycache__`, `ml/.pytest_cache` | Local artifacts, environments, caches, and generated files. |
| `local_scripts/**/__pycache__`, `local_scripts/streaming/logs` | Generated caches and logs. |

## Production boundary

The repo demonstrates production-style architecture and conservative production defaults. It is not automated trading infrastructure. Research-only tooling, optional MLOps, partial streaming coverage, and experimental data sources should stay clearly separated from production defaults.

## Safety notes

- Do not run backfills, training, deploys, Docker builds, dbt cloud builds, or Terraform apply for docs-only work.
- Do not commit secrets, state, keys, local credentials, generated artifacts, or local output data.
- Treat GCS, BigQuery, Registry, GKE, Cloud SQL, and Terraform actions as intentional cloud operations.

## Read next

- [Architecture](architecture.md)
- [K8s / GKE Runtime](k8s_gke_runtime.md)
- [Terraform Infrastructure](terraform_infrastructure.md)
- [CI/CD Gates](ci_cd_gates.md)
- [Production Boundaries](production_boundaries.md)
