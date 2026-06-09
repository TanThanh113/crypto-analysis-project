<section class="doc-hero">
  <p class="eyebrow">Portfolio documentation</p>
  <h1>Crypto Analytics and ML Signal Platform</h1>
  <p class="subtitle">
    <strong>Production-style</strong> data engineering and MLOps portfolio project for crypto market analytics,
    batch and streaming pipelines, dbt modeling, orchestration, and conservative ML signals.
  </p>
  <div class="scope-note">
    This is an analytics and ML signal platform, <strong>not a trading bot</strong>. It does not place orders or provide financial advice.
  </div>
  <div class="hero-actions">
    <a href="architecture/">Read Architecture</a>
    <a href="interactive/">Open Interactive Explorer</a>
    <a href="../dbt/">Open dbt Docs</a>
  </div>
</section>

## Quick Review

<div class="doc-link-grid">
  <a class="doc-link-card" href="architecture/">
    <strong>Architecture</strong>
    <span>How ingestion, storage, dbt, Kestra, infrastructure, CI/CD, and ML fit together.</span>
  </a>
  <a class="doc-link-card" href="interactive/">
    <strong>Interactive Project Explorer</strong>
    <span>Recruiter-friendly pipeline architecture map, flow filters, repo links, and production boundary notes.</span>
  </a>
  <a class="doc-link-card" href="../dbt/">
    <strong>dbt Docs</strong>
    <span>Generated model lineage, sources, columns, and transformation metadata.</span>
  </a>
  <a class="doc-link-card" href="production_boundaries/">
    <strong>Production Boundaries</strong>
    <span>What is production-style, what is optional, and what remains research-only.</span>
  </a>
  <a class="doc-link-card" href="codebase_knowledge_graph/">
    <strong>AI Codebase Map</strong>
    <span>Understand-Anything-powered deep-dive when a reviewed graph asset is available; secondary to the curated architecture map.</span>
  </a>
</div>

## Platform Flow

<div class="flow-grid">
  <div class="flow-step">
    <strong>External data</strong>
    <span>Market, ETF, macro, funding, sentiment, and experimental context sources enter the platform.</span>
  </div>
  <div class="flow-step">
    <strong>Batch and streaming</strong>
    <span>Batch is the strongest historical path; streaming is a lower-latency freshness path with partial coverage.</span>
  </div>
  <div class="flow-step">
    <strong>Storage landing</strong>
    <span>Cloud-oriented storage and warehouse layers prepare data for dbt, monitoring, and ML workflows.</span>
  </div>
  <div class="flow-step">
    <strong>dbt marts</strong>
    <span>dbt normalizes sources and publishes analytics, dashboard, monitoring, and ML marts.</span>
  </div>
  <div class="flow-step">
    <strong>ML lifecycle</strong>
    <span>Training and prediction use a <strong>conservative ML contract</strong>; optional MLOps tools stay off by default.</span>
  </div>
  <div class="flow-step">
    <strong>Orchestration and gates</strong>
    <span>Kestra, GKE, Terraform, and CI/CD gates keep runtime work explicit and reviewable.</span>
  </div>
</div>

## How To Read This Project

<div class="note-card-grid">
  <div class="note-card">
    <strong>Recruiter path</strong>
    <span>Start with the README, open the Interactive Explorer, skim Architecture, then read Production Boundaries to understand scope and safety.</span>
  </div>
  <div class="note-card">
    <strong>Technical reviewer path</strong>
    <span>Read Architecture, Batch, dbt, ML/MLOps, Kestra, GKE/Terraform, then CI/CD to inspect the full platform design.</span>
  </div>
  <div class="note-card">
    <strong>What to verify</strong>
    <span>Look for separation between production defaults, <strong>optional</strong> MLOps controls, <strong>research-only</strong> candidates, and cloud-write risks.</span>
  </div>
</div>

## Start Here

<div class="doc-card-grid">
  <a class="doc-card" href="architecture/">
    <strong>Architecture</strong>
    <span>Beginner-friendly system overview and platform boundaries.</span>
  </a>
  <a class="doc-card" href="batch_pipeline/">
    <strong>Batch Pipeline</strong>
    <span>Mature historical ingestion, validation, and trusted backfill coverage.</span>
  </a>
  <a class="doc-card" href="streaming_pipeline/">
    <strong>Streaming Pipeline</strong>
    <span>Lower-latency Kafka/Flink-style freshness path and experimental boundaries.</span>
  </a>
  <a class="doc-card" href="dbt_models/">
    <strong>dbt Models</strong>
    <span>Staging, intermediate, marts, ML, dashboard, and monitoring layers.</span>
  </a>
  <a class="doc-card" href="ml_mLOps/">
    <strong>ML and MLOps</strong>
    <span>Artifact-first ML, feature contracts, optional MLflow, Optuna, and registry workflows.</span>
  </a>
  <a class="doc-card" href="kestra_orchestration/">
    <strong>Kestra Orchestration</strong>
    <span>Flow structure, orchestration boundaries, and production-style gates.</span>
  </a>
  <a class="doc-card" href="k8s_gke_runtime/">
    <strong>K8s / GKE Runtime</strong>
    <span>Runtime support for containerized batch, dbt, and ML jobs.</span>
  </a>
  <a class="doc-card" href="terraform_infrastructure/">
    <strong>Terraform Infrastructure</strong>
    <span>Infrastructure definitions and cloud-resource safety boundaries.</span>
  </a>
  <a class="doc-card" href="ci_cd_gates/">
    <strong>CI/CD Gates</strong>
    <span>Review, deployment, and safety gates across docs, dbt, Kestra, images, and infra.</span>
  </a>
  <a class="doc-card" href="repository_map/">
    <strong>Repository Map</strong>
    <span>Folder-by-folder guide for reviewers who want to inspect the source quickly.</span>
  </a>
  <a class="doc-card" href="codebase_knowledge_graph/">
    <strong>AI Codebase Map</strong>
    <span>Optional generated graph integration for technical reviewers after the primary architecture map.</span>
  </a>
</div>

## What This Project Demonstrates

<div class="feature-grid">
  <div class="feature-card">
    <strong>Data Engineering</strong>
    <span>Batch collectors, selected backfills, validation, warehouse modeling, and freshness paths.</span>
  </div>
  <div class="feature-card">
    <strong>Cloud Infrastructure</strong>
    <span>GCS/BigQuery-oriented architecture, K8s/GKE runtime support, and Terraform definitions.</span>
  </div>
  <div class="feature-card">
    <strong>Orchestration</strong>
    <span>Kestra flows for raw ingestion, dbt, ML, monitoring, quality, preview, and master workflows.</span>
  </div>
  <div class="feature-card">
    <strong>MLOps</strong>
    <span>Feature contracts, artifact-first prediction, promotion gates, and optional experiment tooling.</span>
  </div>
  <div class="feature-card">
    <strong>CI/CD</strong>
    <span>Workflow gates that make deployment and infrastructure changes reviewable.</span>
  </div>
  <div class="feature-card">
    <strong>Analytics</strong>
    <span>dbt marts and documentation that help reviewers understand model lineage and data coverage.</span>
  </div>
</div>

## Important Notes

<ul class="note-list">
  <li><strong>Not a trading bot:</strong> the project demonstrates analytics and ML signal workflows, not automated trading.</li>
  <li><strong>Strongest data coverage:</strong> reliable 5-year <strong>backfill</strong> is strongest for Binance trades, ETF, Macro, and Funding.</li>
  <li><strong>Partial sources:</strong> other sources are partial, experimental, or not fully live-ready.</li>
  <li><strong>Conservative ML contract:</strong> <strong>production-style</strong> ML uses `ml/feature_list.yml` and artifact-first defaults.</li>
  <li><strong>Research candidates:</strong> subset9 and microstructure features are <strong>research-only</strong> / manual candidates.</li>
</ul>

## Published Layout

- `/` - root landing page.
- `/docs/` - this MkDocs-rendered documentation site.
- `/docs/interactive/` - static interactive project explorer with a data-driven architecture map.
- `/docs/interactive/#ai-codebase-map` - optional static AI graph viewer when a reviewed Understand-Anything graph asset is available.
- `/dbt/` - generated dbt documentation.
