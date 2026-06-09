# Repository Map

## What this part does

This document groups the repository by subsystem so a new reviewer can understand where to look, what each area does, and what to edit carefully.

## Where it lives

This is a documentation guide for the full repository. It intentionally avoids exposing secrets, local credentials, generated artifacts, Terraform state, and local outputs as actionable paths.

## How it fits into the full platform

The repository combines data ingestion, transformations, orchestration, runtime infrastructure, infrastructure-as-code, ML, CI/CD, and documentation. The map below helps reviewers move from high-level docs into the relevant subsystem.

## What To Inspect First

<div class="note-card-grid">
  <div class="note-card">
    <strong>Fast orientation</strong>
    <span>Read `README.md`, open `docs/interactive/index.html`, then skim `docs/architecture.md` and this repository map.</span>
  </div>
  <div class="note-card">
    <strong>Data pipeline review</strong>
    <span>Start with `local_scripts/batch`, `dbt_transform/crypto_dbt/models`, and `docs/dbt_models.md` to understand the data path.</span>
  </div>
  <div class="note-card">
    <strong>ML safety review</strong>
    <span>Inspect `ml/feature_list.yml`, `ml/model_loader.py`, `ml/promotion_gate.py`, and `docs/production_boundaries.md` before research scripts.</span>
  </div>
  <div class="note-card">
    <strong>Runtime review</strong>
    <span>Inspect `kestra/flows-gke`, `k8s`, `helm`, `terraform`, and `.github/workflows` to understand deploy gates and cloud-write surfaces.</span>
  </div>
</div>

## Main flow

1. Start with Documentation.
2. Review Batch and Streaming ingestion.
3. Review dbt transforms and ML/MLOps.
4. Review Kestra orchestration and K8s/GKE runtime.
5. Review Terraform infrastructure and Docker images.
6. Review CI/CD, tests, research-only tooling, and generated artifacts to avoid.

## Key Groups And What They Do

### Documentation

<div class="file-card-grid">
  <div class="file-card">
    <h4>Project README</h4>
    <p><strong>Path:</strong> <code>README.md</code></p>
    <p><strong>Role:</strong> Portfolio overview and reading path.</p>
    <p><strong>Why it matters:</strong> Sets scope before reviewers inspect subsystem internals.</p>
    <p><strong>Review note:</strong> Keep scope accurate: <strong>not a trading bot</strong>.</p>
  </div>
  <div class="file-card">
    <h4>Interactive Explorer</h4>
    <p><strong>Path:</strong> <code>docs/interactive/index.html</code></p>
    <p><strong>Role:</strong> Static visual guide for architecture, repo map, and production boundaries.</p>
    <p><strong>Why it matters:</strong> Gives recruiters and reviewers fast orientation without backend or build steps.</p>
    <p><strong>Review note:</strong> Keep links compatible with MkDocs clean routes.</p>
  </div>
  <div class="file-card">
    <h4>Subsystem Docs</h4>
    <p><strong>Path:</strong> <code>docs/*.md</code></p>
    <p><strong>Role:</strong> Explain architecture, pipelines, dbt, ML/MLOps, Kestra, GKE, Terraform, CI/CD, and boundaries.</p>
    <p><strong>Why it matters:</strong> Lets reviewers understand each subsystem before reading source code.</p>
    <p><strong>Review note:</strong> Avoid claims of complete production maturity.</p>
  </div>
</div>

### Batch And Streaming

<div class="file-card-grid">
  <div class="file-card">
    <h4>Batch Ingestion</h4>
    <p><strong>Path:</strong> <code>local_scripts/batch</code></p>
    <p><strong>Role:</strong> Collectors, validation, monitoring, quality audit, and selected backfills.</p>
    <p><strong>Why it matters:</strong> Strongest mature historical path; feeds <strong>dbt marts</strong> and ML datasets.</p>
    <p><strong>Review note:</strong> Backfills can create large <strong>cloud writes</strong>.</p>
  </div>
  <div class="file-card">
    <h4>Streaming Producers</h4>
    <p><strong>Path:</strong> <code>local_scripts/streaming/producer</code></p>
    <p><strong>Role:</strong> Market, on-chain, and sentiment producers for freshness experiments.</p>
    <p><strong>Why it matters:</strong> Adds lower-latency context without replacing batch history.</p>
    <p><strong>Review note:</strong> Avoid committing `.env` files, keys, or connector secrets.</p>
  </div>
  <div class="file-card">
    <h4>Streaming Transform Logic</h4>
    <p><strong>Path:</strong> <code>local_scripts/streaming/logic_crypto_streaming</code></p>
    <p><strong>Role:</strong> Flink/Kafka-oriented signal transformation logic.</p>
    <p><strong>Why it matters:</strong> Turns events into streaming signals and exposes schema/dead-letter assumptions.</p>
    <p><strong>Review note:</strong> Streaming remains experimental until freshness and sinks are validated.</p>
  </div>
</div>

### dbt And ML

<div class="file-card-grid">
  <div class="file-card">
    <h4>dbt Transformations</h4>
    <p><strong>Path:</strong> <code>dbt_transform/crypto_dbt/models</code></p>
    <p><strong>Role:</strong> Staging, intermediate, core, dashboard, ML, and monitoring model layers.</p>
    <p><strong>Why it matters:</strong> Converts source data into reusable analytics and ML-ready surfaces.</p>
    <p><strong>Review note:</strong> Watch timestamp joins, label leakage, and cloud-backed build cost.</p>
  </div>
  <div class="file-card">
    <h4>Production Feature Contract</h4>
    <p><strong>Path:</strong> <code>ml/feature_list.yml</code></p>
    <p><strong>Role:</strong> Defines the conservative production feature list.</p>
    <p><strong>Why it matters:</strong> Anchors train/predict consistency.</p>
    <p><strong>Review note:</strong> Do not change casually; research configs are separate.</p>
  </div>
  <div class="file-card">
    <h4>ML Entrypoints and Optional Controls</h4>
    <p><strong>Path:</strong> <code>ml</code></p>
    <p><strong>Role:</strong> Training, prediction, artifact loading, promotion gates, optional MLflow/Optuna/Registry, and local research.</p>
    <p><strong>Why it matters:</strong> Separates production-style defaults from <strong>optional</strong> and <strong>research-only</strong> work.</p>
    <p><strong>Review note:</strong> Training, prediction, and registry operations can write artifacts or remote state.</p>
  </div>
</div>

### Orchestration, Runtime, And Infrastructure

<div class="file-card-grid">
  <div class="file-card">
    <h4>Kestra GKE Flows</h4>
    <p><strong>Path:</strong> <code>kestra/flows-gke</code></p>
    <p><strong>Role:</strong> Production-style orchestration flow definitions.</p>
    <p><strong>Why it matters:</strong> Describes raw, dbt, ML, streaming, monitoring, quality, preview, and master flow groups.</p>
    <p><strong>Review note:</strong> Triggers, namespaces, images, and destinations need review.</p>
  </div>
  <div class="file-card">
    <h4>Kubernetes And Helm</h4>
    <p><strong>Path:</strong> <code>k8s</code>, <code>helm/kestra/values-gke.yaml</code></p>
    <p><strong>Role:</strong> Runtime support for RBAC, secret provider integration, and Kestra Helm values.</p>
    <p><strong>Why it matters:</strong> GKE task pods need scoped permissions, secrets integration, and healthy Kestra config.</p>
    <p><strong>Review note:</strong> No secrets or key material; prefer <strong>Workload Identity</strong>.</p>
  </div>
  <div class="file-card">
    <h4>Terraform Infrastructure</h4>
    <p><strong>Path:</strong> <code>terraform</code>, <code>terraform-bootstrap</code>, <code>terraform-grafana</code></p>
    <p><strong>Role:</strong> Describes BigQuery, GCS, Artifact Registry, GKE, Cloud SQL, IAM, networking, and observability resources.</p>
    <p><strong>Why it matters:</strong> Shows the cloud substrate beneath ingestion, dbt, ML, Kestra, and CI/CD.</p>
    <p><strong>Review note:</strong> Never commit tfstate, secret tfvars, service-account keys, or local credentials.</p>
  </div>
</div>

### Docker, CI/CD, Tests, And Research

<div class="file-card-grid">
  <div class="file-card">
    <h4>Runtime Images</h4>
    <p><strong>Path:</strong> <code>docker</code></p>
    <p><strong>Role:</strong> Batch, dbt, and ML Dockerfiles for gated runtime images.</p>
    <p><strong>Why it matters:</strong> Task pods can pull purpose-built images from <strong>Artifact Registry</strong>.</p>
    <p><strong>Review note:</strong> Builds should stay gated and should not run for docs-only work.</p>
  </div>
  <div class="file-card">
    <h4>CI/CD</h4>
    <p><strong>Path:</strong> <code>.github/workflows</code>, <code>.github/scripts</code>, <code>scripts/repo_guard.py</code></p>
    <p><strong>Role:</strong> GitHub Actions workflows, deploy planning, flow deploy helpers, cleanup, and repository guard.</p>
    <p><strong>Why it matters:</strong> Keeps quality checks and runtime work explicit and reviewable.</p>
    <p><strong>Review note:</strong> Do not loosen gates casually.</p>
  </div>
  <div class="file-card">
    <h4>Tests And Research-Only Tooling</h4>
    <p><strong>Path:</strong> <code>ml/tests</code>, <code>dbt_transform/crypto_dbt/tests</code>, <code>ml/local_*.py</code>, <code>ml/research/configs</code></p>
    <p><strong>Role:</strong> Cloud-free tests plus manual research tools for diagnostics, ablation, AutoML, and candidate validation.</p>
    <p><strong>Why it matters:</strong> Lets reviewers distinguish testable production-style behavior from exploratory work.</p>
    <p><strong>Review note:</strong> Research configs are not the same as <code>ml/feature_list.yml</code>.</p>
  </div>
</div>

## Local/generated artifacts to avoid committing

<div class="file-card-grid">
  <div class="file-card">
    <h4>Environment And Secret Files</h4>
    <p><strong>Patterns:</strong> <code>.env</code>, <code>local_scripts/streaming/secrets</code></p>
    <p><strong>Why to avoid:</strong> These may contain credentials, connector keys, or local configuration.</p>
    <p><strong>Review note:</strong> Secrets belong in managed secret stores or local untracked files, not in docs or commits.</p>
  </div>
  <div class="file-card">
    <h4>Terraform State And tfvars</h4>
    <p><strong>Patterns:</strong> <code>terraform/*.tfstate</code>, <code>terraform*/*.tfvars</code></p>
    <p><strong>Why to avoid:</strong> State and tfvars can expose resource state, identifiers, or secret-bearing values.</p>
    <p><strong>Review note:</strong> Do not commit state, secret tfvars, service-account keys, or local credentials.</p>
  </div>
  <div class="file-card">
    <h4>Generated dbt Artifacts</h4>
    <p><strong>Patterns:</strong> <code>dbt_transform/crypto_dbt/target</code>, <code>dbt_transform/crypto_dbt/logs</code></p>
    <p><strong>Why to avoid:</strong> These are generated build artifacts and logs, not source documentation or model code.</p>
    <p><strong>Review note:</strong> dbt docs are generated in CI for Pages; do not commit local target output.</p>
  </div>
  <div class="file-card">
    <h4>ML And Python Caches</h4>
    <p><strong>Patterns:</strong> <code>ml/artifacts</code>, <code>ml/.venv</code>, <code>__pycache__</code>, <code>.pytest_cache</code></p>
    <p><strong>Why to avoid:</strong> These are local artifacts, environments, caches, and generated files.</p>
    <p><strong>Review note:</strong> Model artifacts and local MLflow data should stay out of source control.</p>
  </div>
  <div class="file-card">
    <h4>Local Logs</h4>
    <p><strong>Patterns:</strong> <code>local_scripts/streaming/logs</code>, generated collector logs</p>
    <p><strong>Why to avoid:</strong> Logs can include local paths, operational details, or noisy generated output.</p>
    <p><strong>Review note:</strong> Keep source docs focused on stable behavior, not local runtime traces.</p>
  </div>
</div>

## Production boundary

The repo demonstrates production-style architecture and conservative production defaults. It is not automated trading infrastructure. Research-only tooling, optional MLOps, partial streaming coverage, and experimental data sources should stay clearly separated from production defaults.

## Safety notes

- Do not run backfills, training, deploys, Docker builds, dbt cloud builds, or Terraform apply for docs-only work.
- Do not commit secrets, state, keys, local credentials, generated artifacts, or local output data.
- Treat GCS, BigQuery, Registry, GKE, Cloud SQL, and Terraform actions as intentional cloud operations.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../architecture/">Architecture</a>
<a class="read-next-card" href="../k8s_gke_runtime/">K8s / GKE Runtime</a>
<a class="read-next-card" href="../terraform_infrastructure/">Terraform Infrastructure</a>
<a class="read-next-card" href="../ci_cd_gates/">CI/CD Gates</a>
<a class="read-next-card" href="../production_boundaries/">Production Boundaries</a>
</div>
</div>
