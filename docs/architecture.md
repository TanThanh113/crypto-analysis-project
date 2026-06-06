# Project Architecture

This document describes the main architecture of the crypto analytics and ML signal platform. It is intentionally scoped as an analytics and MLOps system, not a trading bot or financial-advice product.

The platform combines batch ingestion, experimental streaming components, GCS/BigLake/BigQuery storage, dbt transformations, Kestra orchestration, Docker/Artifact Registry images, Terraform/GKE infrastructure, ML training/prediction, optional MLflow/Optuna/Registry integration, and monitoring/dashboard marts.

## Current Coverage Note

The most reliable 5-year backfill coverage currently comes from Binance trades, ETF indicators, macro indicators, and funding data. Other sources such as stablecoin, liquidation, options, exchange reserve, Reddit/Telegram sentiment, and live taker-pressure context may be partial, experimental, or not fully live-ready. Model conclusions should be interpreted with this source-coverage limitation in mind.

## High-Level End-to-End Architecture

```mermaid
flowchart LR
  subgraph Sources["Sources"]
    S1["Binance trades"]
    S2["Funding"]
    S3["ETF"]
    S4["Macro"]
    S5["Options / liquidation"]
    S6["Stablecoin / reserve"]
    S7["Reddit / Telegram"]
  end

  subgraph Ingestion["Ingestion"]
    B1["Batch collectors"]
    B2["Backfill helpers"]
    ST1["Streaming producers"]
    ST2["Flink / Kafka path"]
  end

  subgraph Storage["Lakehouse and Warehouse"]
    GCS["GCS raw/intermediate files"]
    Iceberg["BigLake / Iceberg"]
    BQRaw["BigQuery raw/external tables"]
    BQMart["BigQuery marts"]
  end

  subgraph Transform["Transformation"]
    Staging["dbt staging"]
    Intermediate["dbt intermediate"]
    Marts["Core, dashboard, ML, monitoring marts"]
  end

  subgraph ML["ML and MLOps"]
    Train["train_model.py"]
    Contract["feature_list.yml + contract hash"]
    MLflow["MLflow logging optional"]
    Optuna["Optuna optional"]
    Registry["MLflow Registry optional"]
    Predict["predict_latest.py"]
    Artifacts["Local/GCS model artifacts + latest_model.json"]
  end

  subgraph Serving["Analytics and Monitoring"]
    Dash["Dashboard marts / Looker Studio"]
    Monitor["Health, freshness, GE audit, ML quality"]
  end

  Sources --> B1
  Sources --> ST1
  B2 --> B1
  B1 --> GCS --> Iceberg --> BQRaw
  ST1 --> ST2 --> BQRaw
  BQRaw --> Staging --> Intermediate --> Marts --> BQMart
  BQMart --> Dash
  BQMart --> Monitor
  BQMart --> Contract --> Train
  Train --> Artifacts
  Train -. optional .-> MLflow
  Train -. optional .-> Optuna
  Train -. optional .-> Registry
  Artifacts --> Predict
  Registry -. optional source .-> Predict
  Predict --> BQMart
```

## Batch Pipeline

```mermaid
flowchart TD
  subgraph BatchSources["Batch Sources"]
    Binance["Binance trades"]
    Funding["Funding rates"]
    ETF["ETF indicators"]
    Macro["Macro indicators"]
    Partial["Options, liquidation, stablecoin, reserve, sentiment"]
  end

  subgraph Scripts["local_scripts/batch"]
    Collectors["Collectors"]
    Backfill["Backfill loaders"]
    Validation["Validation and quality utilities"]
    Monitoring["Health check and alerting"]
  end

  subgraph CloudOutputs["Cloud Outputs"]
    Files["GCS / parquet"]
    RawBQ["BigQuery raw or intermediate tables"]
    Iceberg["BigLake / Iceberg tables"]
  end

  subgraph KestraBatch["Kestra raw flows"]
    Daily["Daily snapshots"]
    Hourly["Hourly snapshots"]
    Intraday["Intraday shift"]
  end

  BatchSources --> Collectors
  Collectors --> Validation
  Backfill --> RawBQ
  Validation --> Files
  Validation --> RawBQ
  Files --> Iceberg
  KestraBatch --> Collectors
  Monitoring --> RawBQ
```

The batch path is the most mature ingestion path. Backfill and daily snapshot behavior are intentionally documented separately in [batch_pipeline.md](batch_pipeline.md).

## Streaming Pipeline

```mermaid
flowchart LR
  subgraph StreamingSources["Live-ish Sources"]
    Market["Market producer"]
    Onchain["On-chain producer"]
    Sentiment["Sentiment producer"]
  end

  subgraph StreamRuntime["Streaming Runtime"]
    Kafka["Kafka / Redpanda-compatible topics"]
    Flink["Flink transformations"]
    Sinks["BigQuery sinks"]
  end

  subgraph Downstream["Downstream Consumers"]
    IntModel["int_streaming_market_hourly"]
    MLInput["mart_ml_prediction_input_latest"]
    Monitoring["Freshness monitoring"]
  end

  Market --> Kafka
  Onchain --> Kafka
  Sentiment --> Kafka
  Kafka --> Flink --> Sinks --> IntModel --> MLInput
  Sinks --> Monitoring
```

The streaming path is useful for freshness and prediction input experiments, but it should be treated as partial until it has the same operational coverage as the trusted batch sources.

## dbt Transformation Layers

```mermaid
flowchart TD
  Raw["Raw/external BigQuery tables"]
  Stg["staging: normalized source tables"]
  Int["intermediate: hourly/daily aggregation and alignment"]
  Core["marts/core: reusable facts and dimensions"]
  Dash["marts/dashboard: BI-ready tables"]
  ML["marts/ml: features, labels, training, prediction, metrics"]
  Mon["marts/monitoring: health and audit marts"]

  Raw --> Stg --> Int
  Int --> Core
  Core --> Dash
  Core --> ML
  Core --> Mon
```

The dbt project lives in `dbt_transform/crypto_dbt`. See [dbt_models.md](dbt_models.md) for layer details and ML mart notes.

## ML and MLOps Workflow

```mermaid
flowchart LR
  subgraph Inputs["ML Inputs"]
    Dataset["mart_ml_training_dataset_hourly"]
    Contract["feature_list.yml"]
    Split["time_split.py"]
  end

  subgraph Training["Training"]
    Strategies["strategy_config.py"]
    Train["train_model.py"]
    Optuna["Optuna tuning optional"]
    Gate["promotion_gate.py"]
  end

  subgraph Artifacts["Artifacts and Lineage"]
    Joblib["model .joblib"]
    Manifest["latest_model.json"]
    Metrics["BigQuery model_metrics unless dry-run"]
    MLflow["MLflow experiment logging optional"]
    Registry["MLflow Registry optional"]
  end

  subgraph Prediction["Prediction"]
    Loader["model_loader.py"]
    Predict["predict_latest.py"]
    Output["BigQuery model_predictions"]
    Latest["mart_ml_predictions_latest"]
  end

  Dataset --> Train
  Contract --> Train
  Split --> Train
  Strategies --> Train
  Optuna -. optional .-> Train
  Train --> Gate
  Gate --> Joblib
  Gate --> Manifest
  Train --> Metrics
  Train -. optional .-> MLflow
  Gate -. optional accepted model .-> Registry
  Manifest --> Loader
  Registry -. optional source .-> Loader
  Loader --> Predict --> Output --> Latest
```

Production prediction defaults to the artifact contract. Registry loading is optional and must be explicitly configured. Research scripts under `ml/local_*.py` are local-only investigation tools.

## CI/CD and Deployment Gates

```mermaid
flowchart TD
  PR["Pull Request"]
  Quality["Quality checks and tests"]
  Plan["Deploy/build plan"]
  DockerGate{"Docker/runtime change or deployable flow?"}
  KestraGate{"Deployable Kestra flows after ML gate?"}
  Docker["Build and smoke Docker images"]
  SkipDocker["Skip Docker build"]
  PortForward["Kestra port-forward/deploy"]
  SkipKestra["Skip Kestra deploy"]
  Gate["PR Required Gate"]

  PR --> Quality
  PR --> Plan
  Plan --> DockerGate
  Plan --> KestraGate
  DockerGate -->|yes| Docker
  DockerGate -->|no| SkipDocker
  KestraGate -->|yes| PortForward
  KestraGate -->|no| SkipKestra
  Quality --> Gate
  Docker --> Gate
  SkipDocker --> Gate
  PortForward --> Gate
  SkipKestra --> Gate
```

`ENABLE_ML_KESTRA_DEPLOY` controls ML Kestra flow deployment. Batch and dbt flow deployment do not depend on that flag. Docker build gating prevents PRs from building images when neither runtime/image files nor deployable flows changed.

## Infrastructure

Terraform manages core GCP resources such as BigQuery datasets, GCS buckets, Artifact Registry, GKE/Kestra resources, Cloud SQL-backed Kestra configuration, IAM, networking, and related infrastructure. Kestra runtime manifests and Helm values live under `helm/` and `k8s/`.

## Operational Boundaries

- No service account JSON keys should be committed.
- Workload Identity is preferred for cloud runtime authentication.
- Local research artifacts should stay under ignored artifact folders.
- Backfill, deploy, GCS write, BigQuery write, and registry update paths should be run intentionally, not as casual local checks.
