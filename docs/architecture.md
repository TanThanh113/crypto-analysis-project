# Project Architecture

This document describes the main architecture of the crypto analytics and ML signal platform. It is intentionally scoped as an analytics and MLOps system, not a trading bot or financial-advice product.

The platform combines batch ingestion, experimental streaming components, GCS/BigLake/BigQuery storage, dbt transformations, Kestra orchestration, Docker/Artifact Registry images, Terraform/GKE infrastructure, ML training/prediction, optional MLflow/Optuna/Registry integration, and monitoring/dashboard marts.

For a recruiter-friendly visual tour, open the static [Interactive Project Explorer](interactive/index.html). It requires no backend or build step and complements this architecture document.

## Current Coverage Note

The most reliable 5-year backfill coverage currently comes from Binance trades, ETF indicators, macro indicators, and funding data. Other sources such as stablecoin, liquidation, options, exchange reserve, Reddit/Telegram sentiment, and live taker-pressure context may be partial, experimental, or not fully live-ready. Model conclusions should be interpreted with this source-coverage limitation in mind.

## Diagram Assets

Editable Mermaid source files live under `docs/diagrams/src/`. The exported SVG diagrams live under `docs/diagrams/` and are embedded below so GitHub renders a clean visual view without requiring Mermaid rendering.

## High-Level End-to-End Architecture

![High-level project architecture](diagrams/overview_architecture.svg)

The high-level view shows the full path from external sources into ingestion, storage, dbt marts, MLOps, prediction, monitoring, and deployment infrastructure. Optional components are called out explicitly so the diagram does not imply MLflow, Optuna, Registry, or ML deploy is required by default.

## Batch Pipeline

![Batch pipeline](diagrams/batch_pipeline.svg)

The batch path is the most mature ingestion path. It covers daily snapshots, backfills, validation, GCS/BigLake/BigQuery landing, dbt builds, dashboard marts, and ML training datasets. Backfill and daily snapshot behavior are documented in [batch_pipeline.md](batch_pipeline.md).

## Streaming Pipeline

![Streaming pipeline](diagrams/streaming_pipeline.svg)

The streaming path is useful for freshness and future prediction input automation, but it should be treated as partial until it has the same operational coverage as the trusted batch sources.

## dbt Transformation Layers

![dbt transformation layers](diagrams/dbt_layers.svg)

The dbt project lives in `dbt_transform/crypto_dbt`. It separates source normalization, intermediate aggregation/alignment, core marts, dashboard marts, ML marts, and monitoring marts. See [dbt_models.md](dbt_models.md) for layer details and ML mart notes.

## ML and MLOps Workflow

![ML and MLOps workflow](diagrams/ml_mLOps_workflow.svg)

Production prediction defaults to the artifact contract. Registry loading is optional and must be explicitly configured. Research scripts under `ml/local_*.py` are local-only investigation tools.

## CI/CD and Deployment Gates

![CI/CD and Kestra gating](diagrams/ci_cd_kestra_gating.svg)

`ENABLE_ML_KESTRA_DEPLOY` controls ML Kestra flow deployment. Batch and dbt flow deployment do not depend on that flag. Docker build gating prevents PRs from building images when neither runtime/image files nor deployable flows changed.

## Infrastructure

Terraform manages core GCP resources such as BigQuery datasets, GCS buckets, Artifact Registry, GKE/Kestra resources, Cloud SQL-backed Kestra configuration, IAM, networking, and related infrastructure. Kestra runtime manifests and Helm values live under `helm/` and `k8s/`.

## Operational Boundaries

- No service account JSON keys should be committed.
- Workload Identity is preferred for cloud runtime authentication.
- Local research artifacts should stay under ignored artifact folders.
- Backfill, deploy, GCS write, BigQuery write, and registry update paths should be run intentionally, not as casual local checks.
- The platform is for analytics and ML signal research, not financial advice or automated trading.
