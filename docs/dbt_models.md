# dbt Transformation Layers

## What this part does

The dbt project transforms raw and intermediate crypto analytics data into layered BigQuery-oriented models. It makes source data easier to understand, aligns time-series features, and publishes marts for dashboards, ML, and monitoring.

## Where it lives

The dbt project lives in `dbt_transform/crypto_dbt`. Model folders live under `dbt_transform/crypto_dbt/models`.

## How it fits into the full platform

Batch and streaming paths prepare data that dbt normalizes and aggregates. dbt outputs then feed dashboards, monitoring, quality checks, and ML training/prediction inputs. The ML feature contract remains conservative, so adding research columns in dbt does not automatically make them production features.

## Main flow

1. Sources enter the dbt project.
2. Staging Models normalize sources and clean types.
3. Intermediate Models align hourly/daily data and aggregate features.
4. Core Marts publish reusable analytics facts.
5. Dashboard / ML Marts prepare BI outputs and model inputs.
6. Monitoring Marts track freshness, quality, and pipeline health.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `dbt_transform/crypto_dbt/dbt_project.yml` | dbt project config | Project-level model configuration. |
| `dbt_transform/crypto_dbt/models/staging` | Staging Models | Source normalization and type cleanup. Technical prefix: `stg_*`. |
| `dbt_transform/crypto_dbt/models/intermediate` | Intermediate Models | Hourly/daily alignment and feature aggregation. Technical prefix: `int_*`. |
| `dbt_transform/crypto_dbt/models/marts/core` | Core Marts | Reusable analytics facts. |
| `dbt_transform/crypto_dbt/models/marts/dashboard` | Dashboard Marts | BI-ready outputs. |
| `dbt_transform/crypto_dbt/models/marts/ml` | ML Marts | Training dataset, labels, prediction inputs, predictions, and model metrics. |
| `dbt_transform/crypto_dbt/models/marts/monitoring` | Monitoring Marts | Freshness, quality, and pipeline health models. |
| `dbt_transform/crypto_dbt/packages.yml` | dbt packages | Dependency configuration. |
| `dbt_transform/crypto_dbt/profiles.yml` | dbt profile template | Treat credentials carefully. |

## Production boundary

dbt models can expose analytics and research columns, but production ML should use the explicit `ml/feature_list.yml` contract. Avoid label leakage, accidental feature changes, and cloud-backed builds unless BigQuery targets are intentionally configured.

## Safety notes

- Do not commit dbt `target/`, logs, local profiles with secrets, or generated artifacts.
- Do not run cloud-backed dbt builds casually.
- Review partitioning, clustering, and materialization choices before expensive builds.

## Read next

- [Batch Pipeline](batch_pipeline.md)
- [ML and MLOps](ml_mLOps.md)
- [CI/CD Gates](ci_cd_gates.md)
- [Production Boundaries](production_boundaries.md)
