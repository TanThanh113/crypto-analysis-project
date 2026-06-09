# Production Boundaries

!!! danger "Do not blur production and research"
    `ml/feature_list.yml` is the conservative production feature contract. subset9 and microstructure features remain manual/research candidates unless explicitly promoted through review.

## What this part does

This document separates conservative production defaults from <strong>research-only</strong> and <strong>optional</strong> workflows. The project is an analytics and ML signal platform, <strong>not a trading bot</strong>, and production-style defaults should stay conservative.

## Where it lives

Production and research boundaries are most visible under `ml`, `dbt_transform/crypto_dbt/models/marts/ml`, `kestra/flows-gke/ml`, and `docs`.

## How it fits into the full platform

Batch and dbt prepare data for ML. ML code trains or predicts using a <strong>conservative ML contract</strong>. Kestra can orchestrate ML jobs, but deployment is gated. Research scripts explore candidates locally and do not become production serving paths by default.

<div class="note-card-grid">
  <div class="note-card">
    <strong>Production runtime</strong>
    <span>Artifact-first prediction, `ml/feature_list.yml`, gated Kestra flows, and reviewed Docker/GKE paths are the conservative defaults.</span>
  </div>
  <div class="note-card">
    <strong>Research-only scripts</strong>
    <span>`ml/local_*.py`, subset9, microstructure candidates, and ablation/AutoML work stay manual until explicitly promoted.</span>
  </div>
  <div class="note-card">
    <strong>Optional MLOps controls</strong>
    <span>MLflow, Optuna, and Registry integration are useful controls but remain off unless configured.</span>
  </div>
  <div class="note-card">
    <strong>Cloud write risks</strong>
    <span>Training, backfills, dbt builds, GCS/BigQuery writes, Registry updates, Docker pushes, and deploys are intentional operations.</span>
  </div>
</div>

## Main flow

1. Production features are defined by `ml/feature_list.yml`.
2. Training uses `ml/train_model.py` and the feature contract.
3. Prediction uses `ml/predict_latest.py` and artifact-first loading.
4. `ml/promotion_gate.py` prevents weaker candidates from being promoted automatically.
5. Optional MLflow, Optuna, and Registry helpers remain off unless configured.
6. Local research scripts stay manual and local-first.

## Key Files And What They Do

### Production Defaults

<div class="file-card-grid">
  <div class="file-card">
    <h4>Production Feature Contract</h4>
    <p><strong>File:</strong> <code>ml/feature_list.yml</code></p>
    <p><strong>Role:</strong> Defines the conservative feature list shared by training and prediction.</p>
    <p><strong>Why it matters:</strong> This is the clearest production-vs-research boundary in the ML layer.</p>
    <p><strong>Review note:</strong> Do not change casually; subset9 and microstructure candidates remain <strong>research-only</strong>.</p>
  </div>
  <div class="file-card">
    <h4>Training And Prediction Entrypoints</h4>
    <p><strong>Files:</strong> <code>ml/train_model.py</code>, <code>ml/predict_latest.py</code></p>
    <p><strong>Role:</strong> Train models and produce latest analytics signals when intentionally configured.</p>
    <p><strong>Why it matters:</strong> These files are production-style entrypoints but still do not automate trades.</p>
    <p><strong>Review note:</strong> Training can write artifacts and prediction should remain artifact-first.</p>
  </div>
  <div class="file-card">
    <h4>Contract, Loader, And Promotion</h4>
    <p><strong>Files:</strong> <code>ml/feature_contract.py</code>, <code>ml/model_loader.py</code>, <code>ml/promotion_gate.py</code></p>
    <p><strong>Role:</strong> Keep feature metadata stable, load artifacts by default, and prevent weak candidates from being promoted automatically.</p>
    <p><strong>Why it matters:</strong> These controls keep production-style ML conservative and reviewable.</p>
    <p><strong>Review note:</strong> Registry fallback and promotion decisions should stay explicit.</p>
  </div>
</div>

### Optional Controls And Research-Only Work

<div class="file-card-grid">
  <div class="file-card">
    <h4>Optional MLOps Controls</h4>
    <p><strong>Files:</strong> <code>ml/mlflow_utils.py</code>, <code>ml/mlflow_registry.py</code>, <code>ml/optuna_tuning.py</code></p>
    <p><strong>Role:</strong> Support experiment tracking, registry workflows, and tuning when explicitly configured.</p>
    <p><strong>Why it matters:</strong> They document a fuller MLOps path without making MLflow, Registry, or Optuna required.</p>
    <p><strong>Review note:</strong> These are <strong>optional</strong> and off by default; registry writes are remote-state operations.</p>
  </div>
  <div class="file-card">
    <h4>Local Research Scripts</h4>
    <p><strong>Files:</strong> <code>ml/local_*.py</code></p>
    <p><strong>Role:</strong> AutoML, feature/label diagnostics, feature engineering, ablation, down-recall focus, and keeper validation.</p>
    <p><strong>Why it matters:</strong> They help explore candidates manually without changing production defaults.</p>
    <p><strong>Review note:</strong> Keep them <strong>research-only</strong> unless explicitly promoted through review.</p>
  </div>
</div>

## Production boundary

Production defaults are conservative production-style defaults, not a claim of complete production maturity. subset9 and microstructure features are <strong>research-only</strong> / manual candidates. MLflow, Optuna, and Registry integration are <strong>optional</strong> and off by default. Prediction should not be described as automated trading.

## Data Coverage Caveats

The strongest reliable 5-year backfill coverage is currently Binance trades, ETF indicators, macro indicators, and funding data. Other feeds are partial, experimental, or not fully live-ready. Do not infer model edge from source coverage that is incomplete or still being researched.

## Safety notes

- Do not run training, prediction, promotion, or registry updates for documentation work.
- Do not change `ml/feature_list.yml` casually.
- Do not commit model artifacts, local MLflow data, caches, `.venv`, or generated outputs.
- Do not infer model edge from partial data coverage.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../ml_mLOps/">ML and MLOps</a>
<a class="read-next-card" href="../dbt_models/">dbt Models</a>
<a class="read-next-card" href="../kestra_orchestration/">Kestra Orchestration</a>
<a class="read-next-card" href="../repository_map/">Repository Map</a>
</div>
</div>
