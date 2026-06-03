# Architecture

## Overview

This project implements a production-style crypto analytics and ML pipeline on Google Cloud.

The architecture combines batch data ingestion, BigQuery/dbt transformation, Kestra orchestration, Docker-based execution, ML training and prediction, GCS model artifact storage, and Looker Studio dashboarding.

---

## High-Level Architecture

```text
External Data Sources
  |
  |-- Binance trades
  |-- Funding and basis data
  |-- Deribit options data
  |-- Liquidation heatmap data
  |-- Stablecoin supply data
  |-- Exchange reserve data
  |-- Macro indicators
  |-- ETF indicators
  |-- Reddit and Telegram sentiment
  |
  v
Batch Collectors
  |
  v
GCS / BigLake / Iceberg
  |
  v
BigQuery External / Raw Tables
  |
  v
dbt Staging Models
  |
  v
dbt Intermediate Models
  |
  v
Core, Dashboard, and ML Marts
  |
  |-- Looker Studio Dashboard
  |-- ML Training Dataset
  |-- ML Prediction Input
```

---

## Orchestration Layer

Kestra is used as the workflow orchestration layer.

Main responsibilities:

* Run daily market ingestion
* Run macro and ETF ingestion
* Run hourly and intraday snapshots
* Trigger dbt transformations
* Run ML training
* Run ML prediction when real-time input is available
* Provide a manual overview flow for demo and controlled execution

Production Kestra tasks use Docker images stored in Google Artifact Registry.

---

## Container Layer

The project uses three main Docker images:

```text
crypto-batch -> batch extraction and loading scripts
crypto-dbt   -> dbt BigQuery transformations
crypto-ml    -> ML training and prediction scripts
```

Artifact Registry repository:

```text
${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/crypto-docker
```

Image URIs:

```text
${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/crypto-docker/crypto-batch:latest
${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/crypto-docker/crypto-dbt:latest
${GCP_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/crypto-docker/crypto-ml:latest
```

---

## dbt Model Layers

### Staging

The staging layer normalizes raw source data.

Examples:

```text
stg_binance_trades
stg_funding_rates
stg_deribit_options
stg_liquidation_map
stg_macro_indicators
stg_etf_indicators
stg_stablecoin_supply
stg_exchange_reserve
stg_reddit_raw
stg_telegram_raw
```

### Intermediate

The intermediate layer performs aggregation, feature engineering, and time alignment.

Examples:

```text
int_market_trades_hourly
int_funding_hourly
int_options_hourly
int_liquidation_hourly
int_macro_daily
int_etf_daily
int_social_sentiment_hourly
int_stablecoin_hourly
int_exchange_reserve_hourly
```

### Core Marts

The core mart layer provides reusable analytical models.

Examples:

```text
dim_symbols
dim_exchanges
dim_time
fact_crypto_features_hourly
```

### Dashboard Marts

The dashboard mart layer provides Looker-ready datasets.

Examples:

```text
mart_dashboard_kpi_latest
mart_dashboard_ai_signal_hourly
mart_dashboard_market_overview_hourly
mart_dashboard_derivatives_risk_hourly
mart_dashboard_liquidity_risk_daily
mart_dashboard_macro_etf_daily
mart_dashboard_data_freshness
```

### ML Marts

The ML mart layer provides model-ready features, labels, training datasets, prediction inputs, and monitoring tables.

Examples:

```text
mart_ml_features_hourly
mart_ml_labels_hourly
mart_ml_training_dataset_hourly
mart_ml_prediction_input_latest
mart_ml_predictions_latest
mart_ml_model_metrics
mart_ml_feature_quality_daily
mart_ml_label_distribution_daily
mart_ml_naive_baseline_metrics
```

---

## ML Architecture

### Training

```text
mart_ml_training_dataset_hourly
  -> train_model.py
  -> model metrics written to BigQuery
  -> model artifact written to GCS
  -> latest_model.json updated
```

The model training process uses an explicit feature contract:

```text
ml/feature_list.yml
```

This file defines:

* BigQuery source tables
* Target column
* Valid target classes
* Numeric features
* Categorical features
* Training rules
* Prediction rules
* Artifact storage configuration

### Model Artifact Storage

Model artifacts are stored in GCS:

```text
gs://<bucket>/ml-artifacts/crypto_direction_lgbm_v1/
```

The latest model is tracked by:

```text
latest_model.json
```

This manifest points to the active `.joblib` model artifact.

### Prediction

```text
mart_ml_prediction_input_latest
  -> predict_latest.py
  -> download latest model from GCS
  -> generate predictions
  -> write to ml_outputs.model_predictions
  -> dbt mart_ml_predictions_latest
```

Prediction is designed to run after streaming/hourly input becomes available.

---

## Dashboard Architecture

Looker Studio reads from BigQuery marts.

Dashboard pages:

1. Executive Overview
2. Market Overview
3. Derivatives Risk
4. Social, Liquidity, Macro, and ETF Risk
5. ML Quality and Model Monitoring
6. Pipeline and MLOps Overview

Key dashboard goals:

* Show current market condition
* Monitor market regime and risk
* Monitor derivatives and liquidity stress
* Track data freshness
* Track ML feature quality
* Track model metrics and active artifact

---

## Infrastructure as Code

Terraform manages core GCP infrastructure, including:

* GCS buckets
* BigQuery datasets
* BigLake/Iceberg-related resources
* Networking resources
* Artifact Registry repository
* Service accounts and IAM resources

Terraform state and variable files are intentionally excluded from Git.
