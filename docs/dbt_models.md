# dbt Transformation Layers

## What this part does

The dbt project transforms raw and intermediate crypto analytics data into layered BigQuery-oriented models. It makes source data easier to understand, aligns time-series features, and publishes <strong>dbt marts</strong> for dashboards, ML, and monitoring.

## Where it lives

The dbt project lives in `dbt_transform/crypto_dbt`. Model folders live under `dbt_transform/crypto_dbt/models`.

## How it fits into the full platform

Batch and streaming paths prepare data that dbt normalizes and aggregates. dbt outputs then feed dashboards, monitoring, quality checks, and ML training/prediction inputs. The ML feature contract remains conservative, so adding research columns in dbt does not automatically make them production features.

<div class="flow-grid">
  <div class="flow-step">
    <strong>Staging Models</strong>
    <span>Normalize source columns, clean types, and make raw inputs consistent. Technical prefix: `stg_*`.</span>
  </div>
  <div class="flow-step">
    <strong>Intermediate Models</strong>
    <span>Align hourly/daily aggregates, join context, and prepare reusable feature components. Technical prefix: `int_*`.</span>
  </div>
  <div class="flow-step">
    <strong>Core Marts</strong>
    <span>Publish reusable analytics facts that dashboard, monitoring, and ML layers can share.</span>
  </div>
  <div class="flow-step">
    <strong>Dashboard Marts</strong>
    <span>Produce BI-ready outputs for reviewer-friendly metrics and analytics views.</span>
  </div>
  <div class="flow-step">
    <strong>ML Marts</strong>
    <span>Prepare training, prediction, label, prediction-output, and model metric surfaces.</span>
  </div>
  <div class="flow-step">
    <strong>Monitoring Marts</strong>
    <span>Track freshness, quality, and pipeline health so downstream use has visible checks.</span>
  </div>
</div>

## Main flow

1. Sources enter the dbt project.
2. Staging Models normalize sources and clean types.
3. Intermediate Models align hourly/daily data and aggregate features.
4. Core Marts publish reusable analytics facts.
5. Dashboard / ML Marts prepare BI outputs and model inputs.
6. Monitoring Marts track freshness, quality, and pipeline health.

## Key Files And What They Do

### Base path: `dbt_transform/crypto_dbt`

#### Project Config

<div class="file-card-grid">
  <div class="file-card">
    <h4>dbt Project Config</h4>
    <p><strong>File:</strong> <code>dbt_project.yml</code></p>
    <p><strong>Role:</strong> Controls model paths, materialization defaults, and project-level dbt behavior.</p>
    <p><strong>Why it matters:</strong> Reviewers should inspect this before changing build behavior because it affects how every model group runs.</p>
    <p><strong>Review note:</strong> Config changes can alter cost and warehouse behavior when BigQuery targets are used.</p>
  </div>
</div>

#### Transformation Layers

<div class="file-card-grid">
  <div class="file-card">
    <h4>Staging Models</h4>
    <p><strong>Folder:</strong> <code>models/staging</code></p>
    <p><strong>Role:</strong> Normalize source columns, clean types, and make raw inputs consistent. Technical prefix: <code>stg_*</code>.</p>
    <p><strong>Why it matters:</strong> Good staging models stop downstream marts from repeatedly reinterpreting raw schemas.</p>
    <p><strong>Review note:</strong> Source schema changes should be reflected here before they reach analytics or ML.</p>
  </div>
  <div class="file-card">
    <h4>Intermediate Models</h4>
    <p><strong>Folder:</strong> <code>models/intermediate</code></p>
    <p><strong>Role:</strong> Align hourly/daily aggregates and prepare reusable feature components. Technical prefix: <code>int_*</code>.</p>
    <p><strong>Why it matters:</strong> This is where timestamp joins, aggregation windows, and leakage risk become visible.</p>
    <p><strong>Review note:</strong> Inspect time alignment carefully before ML marts consume intermediate outputs.</p>
  </div>
  <div class="file-card">
    <h4>Core Marts</h4>
    <p><strong>Folder:</strong> <code>models/marts/core</code></p>
    <p><strong>Role:</strong> Publish reusable analytics facts that downstream marts can share.</p>
    <p><strong>Why it matters:</strong> Core marts reduce duplicated logic and make analytics behavior easier to audit.</p>
    <p><strong>Review note:</strong> Changes here have a broad downstream dependency surface.</p>
  </div>
</div>

#### Dashboard, ML, And Monitoring Marts

<div class="file-card-grid">
  <div class="file-card">
    <h4>Dashboard Marts</h4>
    <p><strong>Folder:</strong> <code>models/marts/dashboard</code></p>
    <p><strong>Role:</strong> Provide BI-ready outputs that can be read without digging into raw source tables.</p>
    <p><strong>Why it matters:</strong> They make reviewer-facing analytics easier to understand and validate.</p>
    <p><strong>Review note:</strong> Dashboard contract changes should be intentional because they affect presentation and monitoring.</p>
  </div>
  <div class="file-card">
    <h4>ML Marts</h4>
    <p><strong>Folder:</strong> <code>models/marts/ml</code></p>
    <p><strong>Role:</strong> Prepare training datasets, labels, prediction inputs, predictions, and model metrics.</p>
    <p><strong>Why it matters:</strong> These marts connect dbt to ML while the production feature list stays in <code>ml/feature_list.yml</code>.</p>
    <p><strong>Review note:</strong> Watch label leakage and keep research columns separate from the <strong>conservative ML contract</strong>.</p>
  </div>
  <div class="file-card">
    <h4>Monitoring Marts</h4>
    <p><strong>Folder:</strong> <code>models/marts/monitoring</code></p>
    <p><strong>Role:</strong> Track freshness, quality, and pipeline health.</p>
    <p><strong>Why it matters:</strong> Monitoring marts expose broken sources before they quietly feed dashboards or models.</p>
    <p><strong>Review note:</strong> Alert semantics matter; avoid changing thresholds just to hide problems.</p>
  </div>
</div>

#### Packages And Profiles

<div class="file-card-grid">
  <div class="file-card">
    <h4>dbt Packages</h4>
    <p><strong>File:</strong> <code>packages.yml</code></p>
    <p><strong>Role:</strong> Documents dbt dependency configuration.</p>
    <p><strong>Why it matters:</strong> Dependencies should stay lightweight and reviewable for docs and CI reliability.</p>
    <p><strong>Review note:</strong> Do not add dependencies unless they are actually needed.</p>
  </div>
  <div class="file-card">
    <h4>Profile Template</h4>
    <p><strong>File:</strong> <code>profiles.yml</code></p>
    <p><strong>Role:</strong> Shows target structure for dbt execution.</p>
    <p><strong>Why it matters:</strong> It helps reviewers understand BigQuery-oriented targets without exposing credentials.</p>
    <p><strong>Review note:</strong> Never commit local profiles with secrets or service-account keys.</p>
  </div>
</div>

## Production boundary

dbt models can expose analytics and research columns, but production ML should use the explicit `ml/feature_list.yml` contract. Avoid label leakage, accidental feature changes, and cloud-backed builds unless BigQuery targets are intentionally configured.

## Safety notes

- Do not commit dbt `target/`, logs, local profiles with secrets, or generated artifacts.
- Do not run cloud-backed dbt builds casually.
- Review partitioning, clustering, and materialization choices before expensive builds.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../batch_pipeline/">Batch Pipeline</a>
<a class="read-next-card" href="../ml_mLOps/">ML and MLOps</a>
<a class="read-next-card" href="../ci_cd_gates/">CI/CD Gates</a>
<a class="read-next-card" href="../production_boundaries/">Production Boundaries</a>
</div>
</div>
