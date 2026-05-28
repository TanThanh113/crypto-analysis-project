# Crypto Analytics & ML Pipeline

An end-to-end data engineering and machine learning project for crypto market analytics, risk monitoring, and directional signal modeling.

This project builds a production-style pipeline that collects crypto market, derivatives, liquidity, macro, ETF, and sentiment data; transforms it with dbt on BigQuery; orchestrates workloads with Kestra; stores Docker images in Google Artifact Registry; trains ML models; stores model artifacts in GCS; and powers dashboards in Looker Studio.

> This project is for data engineering, analytics, and ML system design demonstration purposes only. It is not financial advice.

---

## Project Highlights

* Batch data ingestion for crypto trades, funding, options, liquidation heatmaps, macro, ETF, stablecoin, exchange reserve, Reddit, and Telegram data.
* BigQuery/dbt transformation layer with staging, intermediate, mart, dashboard, and ML-ready models.
* Kestra orchestration for daily, hourly, intraday, dbt, and ML workflows.
* Dockerized batch, dbt, and ML workloads.
* Google Artifact Registry for production Docker image storage.
* GCS-based ML model artifact registry using `latest_model.json`.
* ML training pipeline with metrics written to BigQuery.
* Looker Studio dashboard for executive overview, market risk, derivatives, liquidity, macro, and ML monitoring.
* Infrastructure as Code with Terraform for GCP resources.

---

## Tech Stack

| Layer                 | Tools                                          |
| --------------------- | ---------------------------------------------- |
| Cloud                 | Google Cloud Platform                          |
| Storage               | GCS, BigLake/Iceberg, BigQuery                 |
| Transformation        | dbt, BigQuery SQL                              |
| Orchestration         | Kestra                                         |
| Containerization      | Docker                                         |
| Image Registry        | Google Artifact Registry                       |
| ML                    | Python, scikit-learn, LightGBM-ready structure |
| Dashboard             | Looker Studio                                  |
| Infrastructure        | Terraform                                      |
| Dependency Management | uv                                             |

---

## Repository Structure

```text
crypto-analysis-project/
├── dbt_transform/              # dbt project and BigQuery transformation models
├── local_scripts/              # batch ingestion scripts
├── ml/                         # ML training, prediction, and feature contract
├── docker/                     # production Dockerfile copies
├── kestra/flows/               # Kestra production flow YAML files
├── terraform/                  # main GCP infrastructure
├── terraform-bootstrap/        # bootstrap service account / IAM setup
├── terraform-grafana/          # Grafana-related infrastructure
├── docs/                       # architecture and operations documentation
└── README.md
```

---

## Data Pipeline Overview

```text
Raw data collectors
  -> GCS / BigLake / Iceberg
  -> BigQuery staging models
  -> dbt intermediate models
  -> dbt marts
  -> Looker Studio dashboard
```

Main dbt layers:

```text
staging      -> source normalization
intermediate -> feature engineering and hourly/daily aggregation
marts/core   -> reusable analytical facts and dimensions
marts/dashboard -> dashboard-ready tables
marts/ml     -> ML feature, label, training, prediction, and monitoring tables
```

---

## ML Pipeline Overview

```text
mart_ml_training_dataset_hourly
  -> train_model.py
  -> model_metrics table in BigQuery
  -> model artifact uploaded to GCS
  -> latest_model.json points to the active model artifact
```

Prediction flow:

```text
mart_ml_prediction_input_latest
  -> predict_latest.py
  -> model_predictions table in BigQuery
  -> mart_ml_predictions_latest
  -> dashboard monitoring
```

Current ML setup includes:

* Explicit feature contract in `ml/feature_list.yml`
* Consistent feature list for training and prediction
* GCS model artifact storage
* BigQuery model metrics
* dbt mart for model monitoring
* Baseline classification model for 4-hour direction prediction

---

## Docker Images

Production images are stored in Google Artifact Registry:

```text
asia-southeast1-docker.pkg.dev/project-lambda-crypto/crypto-docker/crypto-batch:latest
asia-southeast1-docker.pkg.dev/project-lambda-crypto/crypto-docker/crypto-dbt:latest
asia-southeast1-docker.pkg.dev/project-lambda-crypto/crypto-docker/crypto-ml:latest
```

Local build commands:

```bash
docker build -t crypto-batch:local -f docker/batch.Dockerfile local_scripts
docker build -t crypto-dbt:local -f docker/dbt.Dockerfile dbt_transform
docker build -t crypto-ml:local -f docker/ml.Dockerfile ml
```

---

## Kestra Workflows

The project uses Kestra for orchestration.

Main workflow groups:

```text
raw/
  the_daily_snapshot_binance
  the_daily_snapshot_macro
  the_daily_snapshot_etf
  the_hourly_snapshot
  the_intraday_shift

dbt/
  the_dbt_daily_market_transform
  the_dbt_daily_macro_transform
  the_dbt_daily_etf_transform
  the_dbt_hourly_transform
  the_dbt_intraday_transform

ml/
  the_ml_train_daily
  the_ml_predict_hourly

master/
  the_crypto_pipeline_overview
```

The production Kestra flows use Artifact Registry images instead of local Docker images.

---

## Dashboard

The Looker Studio dashboard includes:

1. Executive Overview
2. Market Overview
3. Derivatives Risk
4. Social, Liquidity, Macro, and ETF Risk
5. ML Quality and Model Monitoring
6. Pipeline and MLOps Overview

Dashboard metrics include:

* BTC and ETH price and returns
* Market regime and core signal
* Derivatives risk score
* Liquidity risk score
* Social sentiment score
* Macro risk score
* Data freshness
* Feature completeness
* Label distribution
* Model F1, accuracy, and quality label
* Latest model artifact metadata

---

## Current Status

Completed:

* GitHub repository initialized
* Secret and artifact files ignored
* Docker images built and pushed to Artifact Registry
* Terraform Artifact Registry resource added
* Kestra flows synchronized into the repository
* ML training flow tested through Kestra using Artifact Registry image
* Model artifacts uploaded to GCS
* Model metrics written to BigQuery
* Looker Studio dashboard created

Pending or future improvements:

* Productionize streaming pipeline
* Enable hourly ML prediction after streaming input is available
* Add GitHub Actions for CI/CD
* Add automated Kestra flow deployment from GitHub
* Improve model quality beyond baseline
* Add monitoring and alerting for pipeline failures

---

## Security Notes

This repository intentionally excludes:

* `.env` files
* Terraform state files
* Terraform variable files
* Service account JSON keys
* Local ML artifacts
* Local output data
* Backfill state files
* Streaming secrets

Secrets are expected to be managed through Kestra secrets, environment variables, or GCP IAM.

---

## Disclaimer

This project is intended for portfolio, data engineering, and ML system design demonstration. It should not be used as financial advice or as a live trading system without further validation, risk controls, and compliance review.
