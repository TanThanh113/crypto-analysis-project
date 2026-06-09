# Project Architecture

<div class="scope-note">
  <strong>This is not a trading bot.</strong> The project is an analytics and ML signal platform for portfolio-grade data engineering, orchestration, and conservative ML workflows.
</div>

<div class="coverage-note">
  <strong>Current data coverage:</strong> reliable 5-year backfill is strongest for Binance trades, ETF indicators, macro indicators, and funding data. Other sources are partial, experimental, or not fully live-ready.
</div>

## Platform Purpose

This document explains the full crypto analytics and ML signal platform at a beginner-friendly level. The project is an analytics and ML signal platform, <strong>not a trading bot</strong>, not financial advice, and not automated trading infrastructure.

It connects ingestion, storage, dbt modeling, orchestration, runtime infrastructure, CI/CD, monitoring, and <strong>conservative ML contract</strong> workflows into one portfolio-grade system.

For a visual tour, open the static [Interactive Project Explorer](../interactive/), including the pipeline-oriented architecture map on the Overview tab.

## Recommended Reading Path

For the full curated path, start from the [Docs Home](index.md). The highest-signal next reads are:

<div class="doc-card-grid">
  <a class="doc-card" href="../interactive/">
    <strong>Interactive Explorer</strong>
    <span>Visual system map with tabs, flows, file links, and production boundaries.</span>
  </a>
  <a class="doc-card" href="../batch_pipeline/">
    <strong>Batch Pipeline</strong>
    <span>Trusted collectors, backfills, validation, and current coverage notes.</span>
  </a>
  <a class="doc-card" href="../dbt_models/">
    <strong>dbt Models</strong>
    <span>Transformation layers and model lineage for analytics and ML marts.</span>
  </a>
  <a class="doc-card" href="../ml_mLOps/">
    <strong>ML and MLOps</strong>
    <span>Feature contract, artifact-first prediction, optional registry and tuning tools.</span>
  </a>
</div>

## Where it lives

The architecture is implemented across the repository rather than in one service. The main areas are `local_scripts/`, `dbt_transform/`, `ml/`, `kestra/`, `docker/`, `k8s/`, `helm/`, `terraform/`, `.github/`, and `docs/`.

## End-to-End Platform Flow

The platform starts with external market and context data. Batch ingestion is the strongest historical path, while streaming is a lower-latency experimental/freshness path. Curated data lands in cloud storage and BigQuery-oriented layers, dbt builds analytics and ML marts, Kestra orchestrates the workflows, GKE/Kubernetes can run <strong>production-style</strong> jobs, Terraform describes infrastructure, and CI/CD gates keep runtime changes intentional.

Reliable 5-year backfill is currently strongest for Binance trades, ETF indicators, macro indicators, and funding data. Other sources are partial, experimental, or not fully live-ready.

<div class="flow-grid">
  <div class="flow-step">
    <strong>External data sources</strong>
    <span>Market, derivatives, ETF, macro, funding, sentiment, and operational context enter through collectors or producers.</span>
  </div>
  <div class="flow-step">
    <strong>Batch and streaming ingestion</strong>
    <span>Batch provides the strongest trusted history; streaming adds freshness experiments and should be validated before ML use.</span>
  </div>
  <div class="flow-step">
    <strong>Storage landing</strong>
    <span>Cloud-oriented landing zones and warehouse tables make raw and curated data available to dbt and monitoring paths.</span>
  </div>
  <div class="flow-step">
    <strong>dbt transformation</strong>
    <span>dbt normalizes sources, aligns time-series features, and publishes dashboard, monitoring, and ML marts.</span>
  </div>
  <div class="flow-step">
    <strong>ML train and predict</strong>
    <span>Training and prediction use explicit artifacts and `ml/feature_list.yml`; registry and tuning paths are optional.</span>
  </div>
  <div class="flow-step">
    <strong>Orchestration and runtime</strong>
    <span>Kestra schedules work, GKE can execute task pods, Terraform describes infra, and CI/CD gates runtime changes.</span>
  </div>
</div>

## Main Flow

1. External sources provide market, derivatives, macro, ETF, sentiment, and operational data.
2. Batch and streaming components ingest or prepare source data.
3. Storage and warehouse layers support GCS, BigLake/Iceberg concepts, and BigQuery models.
4. dbt transforms sources into staging, intermediate, core, dashboard, ML, and monitoring marts.
5. Kestra orchestrates raw, dbt, ML, monitoring, quality, preview, and master flows.
6. Docker images and K8s/GKE provide production-style runtime execution.
7. ML jobs train or predict using a conservative feature contract and artifact-first defaults.
8. CI/CD and Terraform keep deployment and infrastructure changes reviewable.

## Key Files And What They Do

<div class="file-card-grid">
  <div class="file-card">
    <h4>Docs And Explorer</h4>
    <p><strong>Paths:</strong> <code>README.md</code>, <code>docs/interactive/index.html</code></p>
    <p><strong>Role:</strong> Give reviewers the project scope, safety boundaries, and fast visual map.</p>
    <p><strong>Why it matters:</strong> These are the quickest way to understand the platform before inspecting source files.</p>
    <p><strong>Review note:</strong> Keep the project framed as analytics and ML signals, <strong>not a trading bot</strong>.</p>
  </div>
  <div class="file-card">
    <h4>Ingestion</h4>
    <p><strong>Paths:</strong> <code>local_scripts/batch</code>, <code>local_scripts/streaming</code></p>
    <p><strong>Role:</strong> Batch collects trusted history; streaming provides lower-latency freshness experiments.</p>
    <p><strong>Why it matters:</strong> Ingestion quality controls what downstream dbt, monitoring, and ML can trust.</p>
    <p><strong>Review note:</strong> Batch is strongest for Binance trades, ETF, Macro, and Funding; streaming remains partial.</p>
  </div>
  <div class="file-card">
    <h4>Transformations And ML</h4>
    <p><strong>Paths:</strong> <code>dbt_transform/crypto_dbt</code>, <code>ml</code></p>
    <p><strong>Role:</strong> dbt publishes analytics and ML marts; ML uses the production-style feature contract and artifacts.</p>
    <p><strong>Why it matters:</strong> This is where source data becomes reviewer-friendly analytics and model inputs.</p>
    <p><strong>Review note:</strong> Keep research candidates separate from the <strong>conservative ML contract</strong>.</p>
  </div>
  <div class="file-card">
    <h4>Orchestration And Runtime</h4>
    <p><strong>Paths:</strong> <code>kestra/flows-gke</code>, <code>docker</code>, <code>k8s</code>, <code>helm/kestra/values-gke.yaml</code></p>
    <p><strong>Role:</strong> Kestra describes workflows, Docker packages jobs, and GKE/K8s provides runtime support.</p>
    <p><strong>Why it matters:</strong> This layer turns reviewed pipeline definitions into production-style execution surfaces.</p>
    <p><strong>Review note:</strong> Runtime actions can involve <strong>cloud writes</strong>, image pulls, and identity bindings.</p>
  </div>
  <div class="file-card">
    <h4>Infrastructure And Gates</h4>
    <p><strong>Paths:</strong> <code>terraform</code>, <code>.github/workflows</code></p>
    <p><strong>Role:</strong> Terraform describes cloud resources; CI/CD gates tests, deploy planning, Docker builds, Kestra deploys, and docs Pages.</p>
    <p><strong>Why it matters:</strong> These files define the review boundary between documentation/source changes and operational cloud work.</p>
    <p><strong>Review note:</strong> Never commit state, secret tfvars, keys, generated artifacts, or local credentials.</p>
  </div>
</div>

## Production Boundary

The repository demonstrates <strong>production-style</strong> architecture and conservative production defaults, but it should not be described as a fully automated trading system. MLflow, Optuna, and MLflow Registry are <strong>optional</strong> and off by default. Research candidates such as subset9 and microstructure features remain <strong>research-only</strong> / manual candidates unless promoted through explicit review.

## Safety Notes

- Do not run training, backfills, deploys, Docker builds, dbt cloud builds, or Terraform apply as part of documentation work.
- Do not commit service account keys, `.env` files, `.tfstate`, secret-bearing `.tfvars`, local credentials, dbt `target/`, ML artifacts, streaming secrets, or generated logs.
- Treat GCS, BigQuery, Registry, Cloud SQL, and GKE operations as intentional cloud actions with cost and access implications.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../batch_pipeline/">Batch Pipeline</a>
<a class="read-next-card" href="../dbt_models/">dbt Models</a>
<a class="read-next-card" href="../ml_mLOps/">ML and MLOps</a>
<a class="read-next-card" href="../k8s_gke_runtime/">K8s / GKE Runtime</a>
<a class="read-next-card" href="../terraform_infrastructure/">Terraform Infrastructure</a>
</div>
</div>
