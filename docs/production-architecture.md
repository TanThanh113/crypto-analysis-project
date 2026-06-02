# Crypto Intelligence Platform — Production Architecture

## 1. Overview

Crypto Intelligence Platform is a production-style Data Engineering and Machine Learning system for crypto market analytics.

The platform collects multiple types of crypto-related data, transforms them into curated analytical marts, trains and serves ML outputs, monitors production health, and sends operational alerts when failures occur.

The project demonstrates modern production practices:

* Cloud-native orchestration with Kestra on GKE Autopilot
* Infrastructure as Code with Terraform
* Containerized workloads with Docker and Artifact Registry
* Keyless authentication with Workload Identity
* Data transformation with dbt
* Data quality audit with Great Expectations
* Health monitoring with BigQuery operational tables
* Slack alerting for pipeline failures
* Pull Request preview images and preview Kestra flows before production merge

---

## 2. System Objectives

The platform is designed around six main objectives:

### Reliable data ingestion

Collect raw crypto, sentiment, macro, ETF, liquidation, funding, options, and stablecoin data from multiple sources.

### Scalable transformation

Transform raw data into staging, intermediate, core, dashboard, ML, and monitoring marts using dbt.

### Machine learning readiness

Produce ML training datasets, model metrics, prediction inputs, prediction outputs, and model artifacts.

### Production observability

Track pipeline health, data freshness, GE audit results, failed checks, and prediction freshness.

### Safe deployment

Validate Docker images and Kestra flow definitions in Pull Requests before merging to production.

### Operational recovery

Provide clear monitoring, alerting, runbook, rollback, and debugging procedures.

---

## 3. Main Architecture Layers

### Source Layer

External data sources provide market, sentiment, macro, ETF, and derivatives-related data.

Examples include:

* Binance market data
* Funding and basis data
* Liquidation data
* Options data
* Stablecoin supply data
* Reddit and Telegram sentiment
* Macro and ETF indicators

### Raw Layer

Raw extracted files and raw source tables are stored for traceability and reproducibility.

This layer preserves source-level records before business transformations.

### Staging Layer

Staging models normalize data types, timestamps, symbols, column names, and deduplicate records.

This layer prepares raw data for reliable downstream transformation.

### Intermediate Layer

Intermediate models aggregate and reshape source-level data into useful hourly or daily structures.

This layer contains source-specific feature preparation logic.

### Core and Dashboard Marts

Core marts provide curated business-level facts and features.

Dashboard marts expose optimized tables for analytical dashboards.

### ML Layer

ML marts and outputs support model training, model evaluation, prediction input, prediction output, and model monitoring.

### Monitoring Layer

Monitoring tables and marts track operational health, data freshness, GE audit status, and failed checks.

---

## 4. Core Cloud Components

### GKE Autopilot

Runs Kestra services and workload pods.

It provides managed Kubernetes execution without manually managing nodes.

### Kestra

Orchestrates ingestion, dbt transformation, ML training, prediction, GE audit, monitoring, and alerting workflows.

### Cloud SQL PostgreSQL

Stores Kestra metadata, execution state, and orchestration history.

### Google Cloud Storage

Stores raw data files, Kestra internal storage, and ML artifacts.

### Artifact Registry

Stores Docker images for batch, dbt, and ML workloads.

The main images are:

* `crypto-batch`
* `crypto-dbt`
* `crypto-ml`

### BigQuery

Stores analytics marts, ML outputs, monitoring results, and audit logs.

### Secret Manager

Stores runtime secrets such as API keys, Slack webhook URL, and application credentials.

### Workload Identity

Enables keyless authentication for GKE workloads and GitHub Actions.

### GitHub Actions

Runs CI/CD workflows for quality checks, Docker builds, Kestra flow deployment, and cleanup tasks.

### Slack

Receives operational alerts from the production health check system.

### Looker Studio

Visualizes production monitoring status, failed checks, data freshness, and GE audit summaries.

---

## 5. Data Platform Design

The data platform follows a layered architecture:

* Raw data is collected and stored for traceability.
* Staging models clean and standardize source data.
* Intermediate models aggregate and prepare source-specific features.
* Core marts expose curated business facts and ML-ready features.
* Dashboard marts support BI reporting.
* ML marts support model training and prediction workflows.
* Monitoring marts support production observability.

This separation keeps the system easier to debug, test, scale, and maintain.

---

## 6. Kestra Runtime Design

Kestra runs on GKE Autopilot using separated runtime services:

* Webserver
* Scheduler
* Executor
* Workers
* Indexer

Workloads are executed as Kubernetes pods.

This design avoids Docker-in-Docker and makes workloads more compatible with GKE production environments.

Each workload image is responsible for a specific execution domain:

* Batch ingestion and validation
* dbt transformation
* ML training and prediction
* GE audit
* Health check and Slack alerting

---

## 7. CI/CD Design

The CI/CD system separates Pull Request validation from production deployment.

### Pull Request Stage

Pull Requests build preview Docker images using PR-specific tags.

Kestra preview flows are deployed into a PR-specific namespace.

Triggers are removed from preview flows to prevent accidental scheduled execution.

Production image references are rewritten to PR preview image tags.

Safe PR validation flows can then be executed manually in Kestra UI.

### Main Branch Stage

After merge, production images are built and pushed with both immutable SHA tags and `latest`.

Production Kestra flows are deployed to the production namespace.

Preview images and preview Kestra flow definitions are cleaned up.

---

## 8. PR Preview Strategy

PR preview exists to catch deployment and runtime issues before production merge.

It validates:

* Docker image build correctness
* Runtime dependency availability
* Kestra flow deployability
* dbt parse and compile behavior
* Monitoring and alerting code behavior
* Safe smoke tests without full production side effects

Preview namespaces do not automatically isolate BigQuery datasets or GCS buckets.

Therefore, only safe PR validation flows should be executed in preview namespaces unless data outputs are explicitly isolated.

---

## 9. Safe PR Validation Flows

The safe PR validation flows are:

* `the_pr_raw_hourly_test_gke`
* `the_pr_dbt_test_gke`
* `the_pr_ml_predict_test_gke`
* `the_pr_quality_monitoring_test_gke`

These flows validate runtime behavior without intentionally running full production pipelines.

Production-like flows should not be manually executed in preview namespaces unless the output datasets and buckets are separated from production.

---

## 10. Monitoring and Alerting Design

The monitoring system is based on append-only BigQuery operational tables.

The main health check table is:

* `pipeline_health_check_results`

Each health check execution creates a unique `run_id`.

The Slack alert process reads the exact `run_id` from the current execution, so alerts do not accidentally include stale results from older runs.

The health check system monitors:

* Dashboard data freshness
* GE audit freshness and failure status
* ML model metrics availability
* ML training dataset availability
* Prediction output freshness

---

## 11. Great Expectations Usage

Great Expectations is used for curated mart audit.

It is not used as the main raw ingestion validator.

GE audit results are written to:

* `data_quality_audit_results`

These results are consumed by monitoring marts and the Production Monitoring dashboard.

---

## 12. Production Monitoring Dashboard

The dashboard provides operational visibility into the platform.

Main sections:

* Pipeline status
* Latest check time
* Failed critical checks
* Failed warning checks
* GE audit status
* Health run history
* Failed checks table
* Data freshness table
* GE audit summary

The dashboard helps identify whether a failure is caused by stale data, missing ML outputs, failed GE checks, or missing model metrics.

---

## 13. Security Model

The platform avoids long-lived service account JSON keys where possible.

Security practices include:

* Workload Identity for GKE workloads
* GitHub OIDC federation for CI/CD
* Secret Manager for runtime secrets
* Secret Manager CSI mount for selected Kubernetes pods
* No committed `.env` files
* No committed service account keys
* No committed local output files or model artifacts
* PR preview isolation for Kestra flow definitions

---

## 14. Operational Principles

The platform follows these production principles:

* Reproducible deployments
* Infrastructure as Code
* Safe Pull Request validation
* Containerized runtime environments
* Keyless authentication
* Append-only operational logs
* Centralized monitoring
* Alerting before failure escalation
* Manual rollback support
* Clear runbook-driven operations

---

## 15. Current Limitations

Current limitations:

* PR preview namespaces do not isolate BigQuery or GCS outputs by themselves.
* Full production flows should not be run in preview namespaces unless outputs are isolated.
* Prediction freshness may remain a warning while prediction or streaming flows are not fully scheduled.
* Health check scheduling should only be enabled when ingestion and dbt flows are running regularly.
* Model drift and cost monitoring are future improvements.

---

## 16. Future Improvements

Potential future improvements:

* Dedicated PR datasets and buckets
* Dry-run mode for all ingestion flows
* Automated Kestra PR test status callback to GitHub
* Cost monitoring dashboard
* Model drift monitoring
* SLO and SLA tracking
* Automated incident issue creation
* More advanced rollback automation
