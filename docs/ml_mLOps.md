# ML and MLOps Lifecycle

!!! warning "Conservative production contract"
    Production-style ML defaults are artifact-first and feature-contract driven. MLflow, Optuna, and Registry paths are optional and off unless explicitly configured.

## What this part does

The ML area trains and runs conservative directional signal models for analytics and research. It is <strong>not a trading bot</strong> and does not automate trades. Production defaults are artifact-first and feature-contract driven.

<strong>Optional</strong> MLOps features such as MLflow logging, Optuna tuning, and MLflow Registry loading are available only when explicitly configured.

## Where it lives

ML code lives under `ml`. Production-style entrypoints sit next to optional MLOps helpers and local research scripts.

## How it fits into the full platform

dbt ML marts provide training datasets and prediction inputs. ML training uses a <strong>conservative ML contract</strong> and writes artifacts only when configured. Prediction loads artifacts by default. Research scripts help evaluate candidates, but they are not production serving paths.

<div class="flow-grid">
  <div class="flow-step">
    <strong>Feature contract</strong>
    <span>`ml/feature_list.yml` defines the production feature list and protects serving inputs from casual research drift.</span>
  </div>
  <div class="flow-step">
    <strong>Training entrypoint</strong>
    <span>`ml/train_model.py` trains models and can write artifacts when intentionally configured.</span>
  </div>
  <div class="flow-step">
    <strong>Artifact-first loading</strong>
    <span>`ml/model_loader.py` loads artifacts by default, with registry fallback only when explicitly enabled.</span>
  </div>
  <div class="flow-step">
    <strong>Prediction entrypoint</strong>
    <span>`ml/predict_latest.py` uses the production-style contract and loaded artifacts to produce signals.</span>
  </div>
  <div class="flow-step">
    <strong>Promotion gate</strong>
    <span>`ml/promotion_gate.py` prevents weaker candidates from being promoted automatically.</span>
  </div>
  <div class="flow-step">
    <strong>Research tooling</strong>
    <span>`ml/local_*.py`, subset9, and microstructure work remain manual/research-only candidates.</span>
  </div>
</div>

## Main flow

1. dbt prepares ML marts for training and prediction input.
2. `ml/feature_list.yml` defines the conservative production feature contract.
3. Training creates model artifacts when explicitly configured.
4. Optional MLflow, Optuna, and Registry helpers can be enabled for experiments.
5. Promotion gates prevent weaker candidates from being promoted automatically.
6. Prediction loads artifacts by default, with optional registry loading only when configured.

## Key Files And What They Do

### Base path: `ml`

#### Production-Style Contract And Entrypoints

<div class="file-card-grid">
  <div class="file-card">
    <h4>Production Feature Contract</h4>
    <p><strong>File:</strong> <code>feature_list.yml</code></p>
    <p><strong>Role:</strong> Defines the production feature list for training and prediction.</p>
    <p><strong>Why it matters:</strong> This is the anchor for the <strong>conservative ML contract</strong>; changing it changes serving assumptions.</p>
    <p><strong>Review note:</strong> Do not change casually. Research candidates need explicit promotion review before entering this file.</p>
  </div>
  <div class="file-card">
    <h4>Feature Contract Metadata</h4>
    <p><strong>File:</strong> <code>feature_contract.py</code></p>
    <p><strong>Role:</strong> Builds contract metadata and hashing for feature lineage.</p>
    <p><strong>Why it matters:</strong> Training and prediction can verify they are using the same feature contract.</p>
    <p><strong>Review note:</strong> Contract hashing should stay stable and predictable.</p>
  </div>
  <div class="file-card">
    <h4>Training Entrypoint</h4>
    <p><strong>File:</strong> <code>train_model.py</code></p>
    <p><strong>Role:</strong> Trains models using dbt ML marts and writes artifacts when configured.</p>
    <p><strong>Why it matters:</strong> This connects the data mart layer to model artifacts used later by prediction.</p>
    <p><strong>Review note:</strong> Can write local or <strong>GCS</strong> artifacts; do not run training during docs work.</p>
  </div>
  <div class="file-card">
    <h4>Prediction Entrypoint</h4>
    <p><strong>File:</strong> <code>predict_latest.py</code></p>
    <p><strong>Role:</strong> Loads a model artifact or optional registry model and produces analytics signals.</p>
    <p><strong>Why it matters:</strong> This is the production-style prediction surface, but it is still analytics output, not trading automation.</p>
    <p><strong>Review note:</strong> Keep prediction artifact-first and do not describe outputs as financial advice.</p>
  </div>
</div>

#### Loading And Promotion Controls

<div class="file-card-grid">
  <div class="file-card">
    <h4>Model Loader</h4>
    <p><strong>File:</strong> <code>model_loader.py</code></p>
    <p><strong>Role:</strong> Loads model artifacts by default, with optional registry fallback only when configured.</p>
    <p><strong>Why it matters:</strong> Artifact-first loading keeps local review possible without requiring MLflow Registry.</p>
    <p><strong>Review note:</strong> Registry loading is <strong>optional</strong> and should not become an implicit dependency.</p>
  </div>
  <div class="file-card">
    <h4>Promotion Gate</h4>
    <p><strong>File:</strong> <code>promotion_gate.py</code></p>
    <p><strong>Role:</strong> Applies local promotion decisions so weaker candidates are not promoted automatically.</p>
    <p><strong>Why it matters:</strong> It keeps model changes reviewable and prevents accidental promotion of worse candidates.</p>
    <p><strong>Review note:</strong> Promotion logic should remain conservative and transparent.</p>
  </div>
</div>

#### Optional MLOps Controls

<div class="file-card-grid">
  <div class="file-card">
    <h4>MLflow Logging</h4>
    <p><strong>File:</strong> <code>mlflow_utils.py</code></p>
    <p><strong>Role:</strong> Supports experiment logging when MLflow is configured.</p>
    <p><strong>Why it matters:</strong> It can improve experiment traceability without being required for local documentation review.</p>
    <p><strong>Review note:</strong> <strong>Optional</strong> and off by default; do not require it for basic project understanding.</p>
  </div>
  <div class="file-card">
    <h4>MLflow Registry</h4>
    <p><strong>File:</strong> <code>mlflow_registry.py</code></p>
    <p><strong>Role:</strong> Supports optional registry integration and model loading.</p>
    <p><strong>Why it matters:</strong> It documents a possible MLOps path while keeping artifact-first defaults intact.</p>
    <p><strong>Review note:</strong> Registry operations can write remote state; keep them intentionally configured.</p>
  </div>
  <div class="file-card">
    <h4>Optuna Tuning</h4>
    <p><strong>File:</strong> <code>optuna_tuning.py</code></p>
    <p><strong>Role:</strong> Supports tuning experiments for candidate models.</p>
    <p><strong>Why it matters:</strong> It helps explore model settings without changing production defaults.</p>
    <p><strong>Review note:</strong> Research/tuning support only; not a serving path.</p>
  </div>
</div>

#### Research-Only Work

<div class="file-card-grid">
  <div class="file-card">
    <h4>Local Research Scripts</h4>
    <p><strong>Pattern:</strong> <code>local_*.py</code></p>
    <p><strong>Role:</strong> Local diagnostics, AutoML, ablation, recall focus, and keeper validation scripts.</p>
    <p><strong>Why it matters:</strong> They help evaluate candidates before promotion but do not become runtime serving paths.</p>
    <p><strong>Review note:</strong> Keep this work <strong>research-only</strong> and manual unless explicitly promoted.</p>
  </div>
  <div class="file-card">
    <h4>Research Configs</h4>
    <p><strong>Folder:</strong> <code>research/configs</code></p>
    <p><strong>Role:</strong> Stores research feature configurations and candidate sets.</p>
    <p><strong>Why it matters:</strong> This is where subset9 and microstructure candidates can be explored without changing production defaults.</p>
    <p><strong>Review note:</strong> Do not confuse research configs with <code>feature_list.yml</code>.</p>
  </div>
</div>

## Production boundary

Production-style ML defaults are conservative. `ml/feature_list.yml` is the production contract. subset9 and microstructure features are <strong>research-only</strong> / manual candidates and have not replaced the baseline production contract. Local research scripts are not serving paths.

## Safety notes

- Do not run training or prediction as part of documentation work.
- Do not write GCS, BigQuery, MLflow Registry, or other remote artifacts unless intentionally configured.
- Do not commit ML artifacts, `.venv`, caches, local MLflow databases, or generated model files.
- Do not describe model output as trading advice or a guaranteed edge.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../dbt_models/">dbt Models</a>
<a class="read-next-card" href="../production_boundaries/">Production Boundaries</a>
<a class="read-next-card" href="../kestra_orchestration/">Kestra Orchestration</a>
<a class="read-next-card" href="../ci_cd_gates/">CI/CD Gates</a>
</div>
</div>
