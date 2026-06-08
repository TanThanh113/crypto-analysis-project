# Project Architecture

## What this part does

This document explains the full crypto analytics and ML signal platform at a beginner-friendly level. The project is an analytics and ML signal platform, not a trading bot, not financial advice, and not automated trading infrastructure.

It connects ingestion, storage, dbt modeling, orchestration, runtime infrastructure, CI/CD, monitoring, and conservative ML workflows into one portfolio-grade system.

For a visual tour, open the static [Interactive Project Explorer](interactive/index.html).

## Recommended Reading Path

1. [Project README](https://github.com/TanThanh113/crypto-analysis-project/blob/main/README.md)
2. [Architecture](architecture.md)
3. [Interactive Project Explorer](interactive/index.html)
4. [Batch Pipeline](batch_pipeline.md)
5. [Streaming Pipeline](streaming_pipeline.md)
6. [dbt Models](dbt_models.md)
7. [ML and MLOps](ml_mLOps.md)
8. [Kestra Orchestration](kestra_orchestration.md)
9. [K8s / GKE Runtime](k8s_gke_runtime.md)
10. [Terraform Infrastructure](terraform_infrastructure.md)
11. [CI/CD Gates](ci_cd_gates.md)
12. [Production Boundaries](production_boundaries.md)
13. [Repository Map](repository_map.md)

## Where it lives

The architecture is implemented across the repository rather than in one service. The main areas are `local_scripts/`, `dbt_transform/`, `ml/`, `kestra/`, `docker/`, `k8s/`, `helm/`, `terraform/`, `.github/`, and `docs/`.

## How it fits into the full platform

The platform starts with external market and context data. Batch ingestion is the strongest historical path, while streaming is a lower-latency experimental/freshness path. Curated data lands in cloud storage and BigQuery-oriented layers, dbt builds analytics and ML marts, Kestra orchestrates the workflows, GKE/Kubernetes can run production-style jobs, Terraform describes infrastructure, and CI/CD gates keep runtime changes intentional.

Reliable 5-year backfill is currently strongest for Binance trades, ETF indicators, macro indicators, and funding data. Other sources are partial, experimental, or not fully live-ready.

## Main flow

1. External sources provide market, derivatives, macro, ETF, sentiment, and operational data.
2. Batch and streaming components ingest or prepare source data.
3. Storage and warehouse layers support GCS, BigLake/Iceberg concepts, and BigQuery models.
4. dbt transforms sources into staging, intermediate, core, dashboard, ML, and monitoring marts.
5. Kestra orchestrates raw, dbt, ML, monitoring, quality, preview, and master flows.
6. Docker images and K8s/GKE provide production-style runtime execution.
7. ML jobs train or predict using a conservative feature contract and artifact-first defaults.
8. CI/CD and Terraform keep deployment and infrastructure changes reviewable.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `README.md` | Portfolio-level overview | Start here for scope and current coverage. |
| `docs/interactive/index.html` | Static project explorer | No backend or build step required. |
| `local_scripts/batch` | Batch ingestion | Strongest mature ingestion path. |
| `local_scripts/streaming` | Streaming experiments | Partial freshness-oriented path. |
| `dbt_transform/crypto_dbt` | dbt project | BigQuery-oriented transformations and marts. |
| `ml` | ML and MLOps code | Production defaults plus research-only scripts. |
| `kestra/flows-gke` | Production-style orchestration flows | Runtime details belong in K8s/GKE docs. |
| `docker` | Runtime Dockerfiles | Batch, dbt, and ML images. |
| `k8s` and `helm/kestra/values-gke.yaml` | Kubernetes runtime support | RBAC, secret provider, and Helm values. |
| `terraform` | Main infrastructure definitions | Do not commit secrets, state, or local credentials. |
| `.github/workflows` | CI/CD workflows | Quality, Docker, Kestra deploy, cleanup, and PR gates. |

## Production boundary

The repository demonstrates production-style architecture and conservative production defaults, but it should not be described as a fully automated trading system. MLflow, Optuna, and MLflow Registry are optional and off by default. Research candidates such as subset9 and microstructure features remain manual/research candidates unless promoted through explicit review.

## Safety notes

- Do not run training, backfills, deploys, Docker builds, dbt cloud builds, or Terraform apply as part of documentation work.
- Do not commit service account keys, `.env` files, `.tfstate`, secret-bearing `.tfvars`, local credentials, dbt `target/`, ML artifacts, streaming secrets, or generated logs.
- Treat GCS, BigQuery, Registry, Cloud SQL, and GKE operations as intentional cloud actions with cost and access implications.

## Read next

- [Batch Pipeline](batch_pipeline.md)
- [dbt Models](dbt_models.md)
- [ML and MLOps](ml_mLOps.md)
- [K8s / GKE Runtime](k8s_gke_runtime.md)
- [Terraform Infrastructure](terraform_infrastructure.md)
