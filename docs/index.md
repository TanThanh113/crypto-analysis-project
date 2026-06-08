# Crypto Analytics Project Documentation

Welcome to the documentation site for the Crypto Analytics and ML signal platform.
This project is an analytics, orchestration, and machine learning signal platform for crypto market research and operational data pipelines. It is not a trading bot and it does not place orders.

## Start Here

Use this page as the reviewer-friendly entry point:

- [Interactive Project Explorer](interactive/): a static visual guide with tabs, cards, flows, repo links, and production boundary notes.
- [Architecture Guide](architecture.md): the beginner-friendly system overview.
- [Repository Map](repository_map.md): where the important source files live and how they fit together.
- [Production Boundaries](production_boundaries.md): what is production-facing, what is research-only, and what is intentionally optional.
- [Generated dbt Docs](../dbt/): model lineage, sources, columns, and dbt metadata generated during the Pages workflow.

## What This Site Covers

The docs are grouped around the main platform surfaces:

- Batch ingestion and 5-year backfill coverage.
- Streaming ingestion and Kafka Connect boundaries.
- dbt staging, marts, tests, and analytics layers.
- ML/MLOps workflow, including optional MLflow, Optuna, and model registry integration.
- Kestra orchestration and CI/CD deployment gates.
- K8s/GKE, Terraform, and production runbook material.
- Repository structure and research-vs-production boundaries.

## Data Coverage Notes

Reliable 5-year backfill is currently strongest for:

- Binance trades.
- ETF data.
- Macro data.
- Funding data.

Other sources are partial, experimental, or not fully live-ready. The platform intentionally separates production defaults from research/manual candidates. In particular, `subset9` and microstructure features are research/manual candidates, not production defaults.

## Safety Notes

This documentation site is static. Opening it does not run training, prediction, backfill, deployment, Docker build, Terraform apply, or cloud writes to GCS, BigQuery, MLflow, or any registry.

MLflow, Optuna, and registry workflows are optional and off by default. They are documented so reviewers can understand the intended MLOps design without assuming those services are required for local documentation review.

## Published Layout

The GitHub Pages deployment is organized as:

- `/` - root landing page.
- `/docs/` - this MkDocs-rendered documentation site.
- `/docs/interactive/` - static interactive project explorer.
- `/dbt/` - generated dbt documentation.
