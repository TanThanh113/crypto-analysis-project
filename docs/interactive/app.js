const FALLBACK_MAP = {
  metadata: {
    project_name: "Crypto Analytics and ML Signal Platform",
    short_name: "Crypto Analytics Explorer",
    purpose: "Static visual guide for recruiters and reviewers.",
    last_curated: "2026-06-07",
    scope_notes: [
      "This is an analytics and ML signal platform, not a trading bot.",
      "The page is documentation-only and does not run ingestion, training, deployment, or cloud writes.",
      "MLflow, Optuna, and MLflow Registry are optional and off by default.",
      "subset9 and microstructure features are research/manual candidates, not production defaults."
    ]
  },
  coverage: {
    summary: "Reliable 5-year backfill coverage is currently strongest for Binance trades, ETF indicators, macro indicators, and funding data. Other sources are partial, experimental, or not fully live-ready.",
    strongest_backfill: ["Binance trades", "ETF indicators", "Macro indicators", "Funding data"],
    partial_or_experimental: [
      "Stablecoin supply",
      "Liquidation heatmap",
      "Options",
      "Exchange reserves",
      "Reddit and Telegram sentiment",
      "Live taker-pressure and streaming context"
    ]
  },
  tabs: [
    {
      id: "overview",
      label: "Overview",
      eyebrow: "Portfolio view",
      title: "End-to-end crypto analytics and conservative ML signal platform",
      summary: "The project demonstrates batch ingestion, experimental streaming, BigQuery/dbt modeling, Kestra orchestration, Terraform-managed cloud infrastructure, Dockerized runtimes, monitoring marts, and conservative ML signal workflows.",
      badges: ["Analytics platform", "ML signal research", "Not a trading bot", "Cloud-native design"],
      flow: ["External data sources", "Batch and streaming ingestion", "GCS / BigLake / BigQuery", "dbt marts", "ML training and prediction", "Monitoring and dashboards"],
      cards: [
        { title: "What reviewers should notice", body: "The repository ties together data engineering, analytics modeling, orchestration, MLOps controls, and CI/CD gates while documenting source-coverage limits explicitly." },
        { title: "Production boundary", body: "The default ML contract remains conservative. Research scripts and feature candidates are separated from production entrypoints and are not auto-promoted." },
        { title: "Current data confidence", body: "The strongest historical coverage is Binance trades, ETF, macro, and funding. Other feeds can be useful analytically but should be treated as partial or experimental." }
      ],
      important_files: [
        { path: "README.md", label: "Portfolio overview", note: "Top-level project summary and safety notes." },
        { path: "docs/architecture.md", label: "Architecture guide", note: "End-to-end platform architecture and operational boundaries." },
        { path: "docs/repository_map.md", label: "Repository map", note: "Folder-by-folder reviewer guide." }
      ],
      docs: [
        { path: "docs/architecture.md", label: "Architecture docs" },
        { path: "docs/repository_map.md", label: "Repository map" },
        { path: "docs/production-runbook.md", label: "Production runbook" }
      ],
      diagram: { label: "High-level architecture", repo_path: "docs/diagrams/overview_architecture.svg", relative_src: "../diagrams/overview_architecture.svg", optional: true },
      warnings: ["Do not present the system as automated trading infrastructure.", "Do not infer model edge from partial source coverage."]
    },
    {
      id: "batch",
      label: "Batch",
      eyebrow: "Most mature ingestion path",
      title: "Batch collectors, backfills, validation, and cloud landing tables",
      summary: "Batch ingestion is the trusted historical path for this project. It supports collectors, selected 5-year backfills, quality checks, monitoring, and downstream dbt/ML preparation.",
      badges: ["Backfill-aware", "Validation utilities", "Cloud writes only when configured"],
      flow: ["Collectors", "Backfill or snapshot mode", "Validation and quality audit", "GCS / BigQuery landing", "dbt transformations", "Dashboard and ML marts"],
      cards: [
        { title: "Strongest sources", body: "Binance trades, ETF indicators, macro indicators, and funding data are the most reliable 5-year backfill set." },
        { title: "Partial sources", body: "Options, liquidation, stablecoin, exchange reserve, and sentiment feeds are useful but source-dependent and not uniformly live-ready." },
        { title: "Operational caution", body: "Backfills can read and write large volumes, so they should only run with intentional cloud targets and cost expectations." }
      ],
      important_files: [
        { path: "local_scripts/batch/binance_trade_collector.py", label: "Binance trade collector", note: "Core market trade collection." },
        { path: "local_scripts/batch/funding_basis_collector.py", label: "Funding collector", note: "Funding and derivatives context." },
        { path: "local_scripts/batch/alpha_vantage_option/etf_flows_collector.py", label: "ETF collector", note: "ETF-related indicators." },
        { path: "local_scripts/batch/alpha_vantage_option/macro_extractor.py", label: "Macro extractor", note: "Macro indicator extraction." },
        { path: "local_scripts/batch/backfill", label: "Backfill scripts", note: "Historical loaders for selected trusted sources." },
        { path: "local_scripts/batch/validation", label: "Validation engine", note: "Reusable rules and validation IO." }
      ],
      docs: [{ path: "docs/batch_pipeline.md", label: "Batch pipeline docs" }, { path: "docs/runbook.md", label: "Runbook" }],
      diagram: { label: "Batch pipeline", repo_path: "docs/diagrams/batch_pipeline.svg", relative_src: "../diagrams/batch_pipeline.svg", optional: true },
      warnings: ["Do not run backfills casually.", "Avoid documenting or linking local .env files, service account keys, local output data, or Terraform state."]
    },
    {
      id: "streaming",
      label: "Streaming",
      eyebrow: "Lower-latency path",
      title: "Experimental streaming producers, Flink logic, and BigQuery sink preparation",
      summary: "Streaming supports freshness experiments and future prediction-input automation, but it is not the primary trusted full-history path yet.",
      badges: ["Kafka / Redpanda style", "Flink-oriented", "Experimental coverage"],
      flow: ["Streaming producers", "Topics", "Flink transformations", "BigQuery sinks", "stg_streaming_candlestick_1min", "Prediction input readiness"],
      cards: [
        { title: "Best use", body: "Recent market/context freshness and future automation once monitoring proves completeness and sink stability." },
        { title: "Current posture", body: "Treat as partial compared with the batch path. It should not be the sole source for historical training coverage." }
      ],
      important_files: [
        { path: "local_scripts/streaming/producer/binance_full_producer.py", label: "Market producer", note: "Produces market stream messages." },
        { path: "local_scripts/streaming/producer/onchain_producer.py", label: "On-chain producer", note: "Produces on-chain context messages." },
        { path: "local_scripts/streaming/producer/sentiment_producer.py", label: "Sentiment producer", note: "Produces sentiment stream messages." },
        { path: "local_scripts/streaming/logic_crypto_streaming/main.py", label: "Flink logic entrypoint", note: "Streaming transformation logic." },
        { path: "kestra/flows-gke/streaming/the_streaming_hourly_transform_gke.yml", label: "Streaming Kestra flow", note: "GKE-oriented orchestration for streaming transforms." }
      ],
      docs: [{ path: "docs/streaming_pipeline.md", label: "Streaming pipeline docs" }, { path: "docs/kafka-connect-keyless-auth.md", label: "Kafka Connect auth note" }],
      diagram: { label: "Streaming pipeline", repo_path: "docs/diagrams/streaming_pipeline.svg", relative_src: "../diagrams/streaming_pipeline.svg", optional: true },
      warnings: ["Validate topic, connector, sink, and freshness health before tying streaming output to automatic prediction.", "Do not expose local connector credentials or key files in documentation."]
    },
    {
      id: "dbt",
      label: "dbt",
      eyebrow: "Transformation layers",
      title: "Layered BigQuery models for analytics, dashboards, ML, and monitoring",
      summary: "The dbt project normalizes raw sources, aligns time-series features, builds reusable facts/dimensions, exposes dashboard marts, prepares ML tables, and monitors health.",
      badges: ["Staging", "Intermediate", "Core marts", "Dashboard marts", "ML marts", "Monitoring"],
      flow: ["Sources", "stg_*", "int_*", "core marts", "dashboard / ML marts", "monitoring marts"],
      cards: [
        { title: "Reviewer lens", body: "The model naming convention makes the data lineage legible: stg for source normalization, int for aligned features, marts for downstream contracts." },
        { title: "ML contract boundary", body: "dbt may expose additive research columns, but production training only uses the conservative ml/feature_list.yml contract." }
      ],
      important_files: [
        { path: "dbt_transform/crypto_dbt/dbt_project.yml", label: "dbt project config", note: "Project-level model configuration." },
        { path: "dbt_transform/crypto_dbt/models/staging", label: "Staging models", note: "Source normalization." },
        { path: "dbt_transform/crypto_dbt/models/intermediate", label: "Intermediate models", note: "Hourly/daily alignment and source-specific aggregates." },
        { path: "dbt_transform/crypto_dbt/models/marts/core", label: "Core marts", note: "Reusable dimensions and facts." },
        { path: "dbt_transform/crypto_dbt/models/marts/dashboard", label: "Dashboard marts", note: "BI-ready outputs." },
        { path: "dbt_transform/crypto_dbt/models/marts/ml", label: "ML marts", note: "Training data, prediction input, labels, metrics, and quality tables." },
        { path: "dbt_transform/crypto_dbt/models/marts/monitoring", label: "Monitoring marts", note: "Pipeline health and audit views." }
      ],
      docs: [{ path: "docs/dbt_models.md", label: "dbt model docs" }, { path: "dbt_transform/crypto_dbt/README.md", label: "dbt project README" }],
      diagram: { label: "dbt transformation layers", repo_path: "docs/diagrams/dbt_layers.svg", relative_src: "../diagrams/dbt_layers.svg", optional: true },
      warnings: ["Avoid label leakage when changing ML marts.", "Inspect partitioning, clustering, and materialization before cloud-backed builds."]
    },
    {
      id: "ml",
      label: "ML/MLOps",
      eyebrow: "Conservative signal workflow",
      title: "Artifact-first training, prediction, optional tracking, and promotion gates",
      summary: "The ML subsystem trains and predicts from dbt ML marts while preserving feature-contract consistency, local-first research, optional MLflow/Optuna/Registry support, and conservative promotion checks.",
      badges: ["Artifact-first", "Feature contract", "Optional MLflow", "Optional Optuna", "Optional Registry"],
      flow: ["mart_ml_training_dataset_hourly", "feature_list.yml", "train_model.py", "promotion_gate.py", "latest_model artifact", "predict_latest.py"],
      cards: [
        { title: "Default production posture", body: "Prediction loads artifacts by default. Registry loading is optional and only used when explicitly configured." },
        { title: "Research separation", body: "local_*.py scripts support diagnostics, AutoML, ablation, keeper validation, and microstructure experiments without becoming production serving paths." },
        { title: "subset9 / microstructure", body: "These features are research/manual candidates and have not replaced the baseline production contract." }
      ],
      important_files: [
        { path: "ml/train_model.py", label: "Training entrypoint", note: "Trains models and writes artifacts when configured." },
        { path: "ml/predict_latest.py", label: "Prediction entrypoint", note: "Loads latest artifact or optional registry model." },
        { path: "ml/feature_list.yml", label: "Production feature contract", note: "Conservative default contract; do not change casually." },
        { path: "ml/feature_contract.py", label: "Contract hashing", note: "Stable metadata for lineage." },
        { path: "ml/promotion_gate.py", label: "Promotion gate", note: "Prevents automatic promotion of worse candidates." },
        { path: "ml/model_loader.py", label: "Model loader", note: "Artifact-first and optional registry loading." },
        { path: "ml/local_automl_research.py", label: "Local AutoML research", note: "Research-only local tooling." },
        { path: "ml/local_microstructure_subset_contract_trial.py", label: "Microstructure contract trial", note: "Manual research candidate workflow." }
      ],
      docs: [{ path: "docs/ml_mLOps.md", label: "ML/MLOps docs" }, { path: "docs/dbt_models.md", label: "ML mart context" }],
      diagram: { label: "ML and MLOps workflow", repo_path: "docs/diagrams/ml_mLOps_workflow.svg", relative_src: "../diagrams/ml_mLOps_workflow.svg", optional: true },
      warnings: ["MLflow, Optuna, and Registry are optional/off by default.", "Do not modify ml/feature_list.yml as part of documentation polish.", "Do not run training during documentation-only review."]
    },
    {
      id: "kestra",
      label: "Kestra",
      eyebrow: "Orchestration",
      title: "GKE-oriented flows for ingestion, dbt, ML, monitoring, quality, and PR previews",
      summary: "Kestra represents the production-style orchestration layer. Flow groups are separated by purpose, with ML deployment gated separately from batch/dbt deployment.",
      badges: ["Raw flows", "dbt flows", "ML gated", "Monitoring", "Preview flows"],
      flow: ["Raw ingestion flows", "dbt transform flows", "Quality and monitoring", "ML train/predict flows", "Master overview", "PR preview validation"],
      cards: [
        { title: "Flow grouping", body: "GKE flows live under kestra/flows-gke and are grouped into raw, dbt, ML, streaming, monitoring, quality, preview, and master directories." },
        { title: "ML deploy gate", body: "ENABLE_ML_KESTRA_DEPLOY controls ML flow deployment. Batch and dbt flow deployment stay independent of that flag." }
      ],
      important_files: [
        { path: "kestra/flows-gke/raw", label: "Raw flows", note: "Batch ingestion snapshots and intraday refresh." },
        { path: "kestra/flows-gke/dbt", label: "dbt flows", note: "Hourly, intraday, daily market, macro, and ETF transforms." },
        { path: "kestra/flows-gke/ml", label: "ML flows", note: "Training, prediction, and strategy matrix flows gated separately." },
        { path: "kestra/flows-gke/preview", label: "Preview flows", note: "PR validation flows." },
        { path: ".github/scripts/kestra_deploy_plan.py", label: "Deploy plan helper", note: "Computes deploy/build gating outputs." },
        { path: ".github/scripts/deploy_kestra_flows.py", label: "Flow deploy helper", note: "Deploys selected flows from CI." }
      ],
      docs: [{ path: "docs/kestra_orchestration.md", label: "Kestra orchestration docs" }, { path: "docs/kestra-gke-rollback.md", label: "GKE rollback note" }],
      diagram: { label: "CI/CD and Kestra gating", repo_path: "docs/diagrams/ci_cd_kestra_gating.svg", relative_src: "../diagrams/ci_cd_kestra_gating.svg", optional: true },
      warnings: ["Do not enable ML deploy simply to make checks green.", "Do not add triggers to PR preview flows."]
    },
    {
      id: "cicd",
      label: "CI/CD",
      eyebrow: "Deployment gates",
      title: "GitHub Actions quality checks, Docker gating, Kestra deploy planning, and PR safety",
      summary: "CI/CD keeps documentation, code quality, Docker builds, and Kestra deployment safer by running targeted checks and skipping expensive work when no deployable runtime changes exist.",
      badges: ["Repo guard", "Docker build gate", "Kestra deploy plan", "PR required gate"],
      flow: ["PR changes", "Quality checks", "Deploy plan", "Docker relevance gate", "Kestra deploy gate", "Required gate summary"],
      cards: [
        { title: "Cost-aware validation", body: "Docker builds and Kestra deploy steps are gated so docs-only or non-runtime PRs avoid unnecessary cloud-adjacent work." },
        { title: "Required checks", body: "The required-gate workflow aggregates expected checks so skipped deploy paths do not incorrectly block safe PRs." }
      ],
      important_files: [
        { path: ".github/workflows/quality-check.yml", label: "Quality checks", note: "Tests, repo guard, and static validation." },
        { path: ".github/workflows/docker-build-push.yml", label: "Docker build/push", note: "Gated image build and smoke workflow." },
        { path: ".github/workflows/kestra-deploy-gke.yml", label: "Kestra deploy", note: "Deploys GKE flows when plan allows it." },
        { path: ".github/workflows/pr-required-gate.yml", label: "Required gate", note: "Aggregates PR check status." },
        { path: "scripts/repo_guard.py", label: "Repository guard", note: "Checks repository safety rules." }
      ],
      docs: [{ path: "docs/kestra_orchestration.md", label: "Kestra gating docs" }, { path: "docs/production-runbook.md", label: "Production runbook" }],
      diagram: { label: "CI/CD and Kestra gating", repo_path: "docs/diagrams/ci_cd_kestra_gating.svg", relative_src: "../diagrams/ci_cd_kestra_gating.svg", optional: true },
      warnings: ["Docs-only changes should not require training, backfills, deploys, or cloud writes.", "Secrets, local artifacts, and Terraform state must stay out of docs and commits."]
    },
    {
      id: "repo-map",
      label: "Repo Map",
      eyebrow: "Where to look",
      title: "Repository areas grouped by reviewer intent",
      summary: "Use this map to quickly find ingestion, streaming, dbt, orchestration, ML, infrastructure, CI/CD, Docker, tests, and documentation areas.",
      badges: ["Reviewer guide", "Safe paths only", "No secret paths"],
      flow: ["Docs", "Ingestion", "Transform", "Orchestrate", "ML", "Operate"],
      cards: [
        { title: "Fast review path", body: "Start with README.md, docs/architecture.md, docs/repository_map.md, then use this explorer to jump into the subsystem files." },
        { title: "Sensitive files omitted", body: "Local env files, key files, Terraform state, logs, generated outputs, and local artifacts are intentionally excluded from this explorer." }
      ],
      repo_groups: [
        { name: "Documentation", paths: ["README.md", "docs/architecture.md", "docs/repository_map.md", "docs/batch_pipeline.md", "docs/streaming_pipeline.md", "docs/dbt_models.md", "docs/ml_mLOps.md", "docs/kestra_orchestration.md"] },
        { name: "Batch and streaming ingestion", paths: ["local_scripts/batch", "local_scripts/batch/backfill", "local_scripts/batch/validation", "local_scripts/streaming/producer", "local_scripts/streaming/logic_crypto_streaming"] },
        { name: "dbt and analytics marts", paths: ["dbt_transform/crypto_dbt/models/staging", "dbt_transform/crypto_dbt/models/intermediate", "dbt_transform/crypto_dbt/models/marts/core", "dbt_transform/crypto_dbt/models/marts/dashboard", "dbt_transform/crypto_dbt/models/marts/ml", "dbt_transform/crypto_dbt/models/marts/monitoring"] },
        { name: "Orchestration and deployment", paths: ["kestra/flows-gke", ".github/workflows", ".github/scripts", "docker", "terraform", "helm", "k8s"] },
        { name: "ML and research", paths: ["ml/train_model.py", "ml/predict_latest.py", "ml/feature_contract.py", "ml/promotion_gate.py", "ml/model_loader.py", "ml/local_*.py"] }
      ],
      important_files: [
        { path: "docs/repository_map.md", label: "Full repository map", note: "Canonical folder-by-folder description." },
        { path: "scripts/repo_guard.py", label: "Repo guard", note: "Safety checks for repository hygiene." }
      ],
      docs: [{ path: "docs/repository_map.md", label: "Repository map docs" }],
      warnings: ["Avoid linking secret-like files or local generated artifacts.", "Treat Terraform state and tfvars as sensitive operational files."]
    },
    {
      id: "research-production",
      label: "Research vs Production",
      eyebrow: "Operational boundary",
      title: "Production defaults are conservative; research candidates remain manual",
      summary: "The project keeps production entrypoints, feature contracts, and deployment gates separate from local research scripts, experimental features, and optional MLOps integrations.",
      badges: ["Conservative defaults", "Research isolated", "No auto trading", "No auto promotion"],
      flow: ["Production contract", "Train/predict entrypoints", "Promotion gate", "Artifact fallback", "Optional registry", "Research candidates stay manual"],
      cards: [
        { title: "Production default files", body: "ml/train_model.py, ml/predict_latest.py, ml/feature_list.yml, ml/model_loader.py, and ml/promotion_gate.py define the conservative production workflow." },
        { title: "Research-only files", body: "ml/local_*.py and research config candidates support local exploration, diagnostics, and model readiness review. They are not production serving paths." },
        { title: "MLOps optionality", body: "MLflow logging, Optuna tuning, and MLflow Registry integration require explicit configuration and are off by default." }
      ],
      production_files: ["ml/train_model.py", "ml/predict_latest.py", "ml/feature_list.yml", "ml/feature_contract.py", "ml/promotion_gate.py", "ml/model_loader.py", "dbt_transform/crypto_dbt/models/marts/ml/mart_ml_training_dataset_hourly.sql", "dbt_transform/crypto_dbt/models/marts/ml/mart_ml_prediction_input_latest.sql", "kestra/flows-gke/ml/the_ml_train_daily_gke.yml", "kestra/flows-gke/ml/the_ml_predict_hourly_gke.yml"],
      research_files: ["ml/local_automl_research.py", "ml/local_feature_label_diagnostics.py", "ml/local_feature_engineering_research.py", "ml/local_feature_ablation_research.py", "ml/local_down_recall_focus_research.py", "ml/local_keeper_candidate_validation.py", "ml/local_microstructure_safe_parity_debug.py", "ml/local_microstructure_subset_contract_trial.py", "dbt_transform/crypto_dbt/tests/research"],
      important_files: [
        { path: "ml/feature_list.yml", label: "Production feature list", note: "Not changed by this documentation work." },
        { path: "ml/mlflow_utils.py", label: "Optional MLflow logging", note: "Best-effort unless configured otherwise." },
        { path: "ml/optuna_tuning.py", label: "Optional tuning", note: "Off unless explicitly requested." },
        { path: "ml/mlflow_registry.py", label: "Optional registry", note: "Alias-based registry integration, not required for prediction." }
      ],
      docs: [{ path: "docs/ml_mLOps.md", label: "ML/MLOps docs" }, { path: "README.md", label: "Safety notes" }],
      warnings: ["subset9 and microstructure features are research/manual candidates, not production defaults.", "This project should not be described as a trading bot.", "Do not run training or promotion as part of docs-only review."]
    },
    {
      id: "ai-map",
      label: "AI codebase map",
      eyebrow: "Optional Understand-Anything layer",
      title: "Optional AI-assisted exploration placeholder",
      summary: "Understand-Anything can be used later as an interactive codebase exploration layer, but it is not required to run, review, or understand this project.",
      badges: ["Optional", "Not required", "Placeholder only"],
      flow: ["README and docs", "Static diagrams", "Interactive explorer", "Optional /understand", "Optional dashboard", "Future graph layer"],
      cards: [
        { title: "What it is", body: "Understand-Anything is optional and is not part of the project runtime, pipeline, training workflow, or deployment process." },
        { title: "How to generate later", body: "Run /understand --language en, then /understand-dashboard in an environment where Understand-Anything is available." },
        { title: "Current state", body: "This repo may not include .understand-anything/knowledge-graph.json. If generated later, it can become an additional exploration layer." },
        { title: "Primary docs remain", body: "README.md, docs/architecture.md, docs/repository_map.md, and this static explorer remain the primary documentation." }
      ],
      commands: ["/understand --language en", "/understand-dashboard"],
      important_files: [
        { path: "README.md", label: "Primary overview", note: "Human-curated documentation remains first." },
        { path: "docs/interactive/index.html", label: "Static explorer", note: "This docs-only page." }
      ],
      docs: [{ path: "docs/interactive/README.md", label: "Interactive explorer README" }],
      warnings: ["No parser for .understand-anything/knowledge-graph.json is implemented in this phase.", "Do not require Understand-Anything for normal project operation."]
    }
  ]
};

const app = document.getElementById("app");
const tabList = document.getElementById("tabList");
const dataMode = document.getElementById("dataMode");

let projectMap = FALLBACK_MAP;
let activeTabId = window.location.hash.replace("#", "") || "overview";

async function loadProjectMap() {
  try {
    const response = await fetch("project_map.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return { data: await response.json(), mode: "json" };
  } catch (error) {
    return { data: FALLBACK_MAP, mode: "fallback", error };
  }
}

function pathToHref(path) {
  if (!path) return "#";
  if (path.startsWith("http")) return path;
  if (path === "README.md") return "../../README.md";
  if (path.startsWith("docs/interactive/")) return path.replace("docs/interactive/", "");
  if (path.startsWith("docs/")) return `../${path.replace("docs/", "")}`;
  return `../../${path}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderPills(items = []) {
  if (!items.length) return "";
  return `<div class="badge-row">${items.map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join("")}</div>`;
}

function renderFlow(items = []) {
  if (!items.length) return "";
  const steps = items.map((item, index) => `
    <div class="flow-step">
      <span class="flow-index">${index + 1}</span>
      <strong>${escapeHtml(item)}</strong>
    </div>
  `).join("");

  return `
    <section class="section-card">
      <h3>Visual flow</h3>
      <div class="flow-wrap">
        <div class="flow">${steps}</div>
      </div>
    </section>
  `;
}

function renderMiniMap(items = []) {
  const visible = items.slice(0, 5);
  if (visible.length < 2) return "";
  const width = 920;
  const y = 62;
  const nodeWidth = 132;
  const gap = (width - nodeWidth * visible.length) / Math.max(visible.length - 1, 1);
  const nodes = visible.map((label, index) => {
    const x = index * (nodeWidth + gap);
    const text = escapeHtml(label.length > 24 ? `${label.slice(0, 22)}...` : label);
    return `
      <g>
        <rect x="${x}" y="25" width="${nodeWidth}" height="74" rx="8" fill="#f8fbfc" stroke="#d9e1ea"></rect>
        <circle cx="${x + 20}" cy="48" r="11" fill="#0d7f8c"></circle>
        <text x="${x + 20}" y="52" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">${index + 1}</text>
        <text x="${x + 14}" y="78" font-size="13" font-weight="700" fill="#16212f">${text}</text>
      </g>
    `;
  }).join("");
  const arrows = visible.slice(0, -1).map((_, index) => {
    const start = index * (nodeWidth + gap) + nodeWidth + 10;
    const end = (index + 1) * (nodeWidth + gap) - 12;
    return `<line x1="${start}" y1="${y}" x2="${end}" y2="${y}" stroke="#0d7f8c" stroke-width="2" marker-end="url(#arrow)"></line>`;
  }).join("");

  return `
    <svg class="mini-map" viewBox="0 0 ${width} 125" role="img" aria-label="Simplified flow diagram">
      <defs>
        <marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
          <path d="M0,0 L9,4.5 L0,9 Z" fill="#0d7f8c"></path>
        </marker>
      </defs>
      ${arrows}
      ${nodes}
    </svg>
  `;
}

function renderCards(cards = []) {
  if (!cards.length) return "";
  return `
    <section class="section-card">
      <h3>What matters</h3>
      <div class="card-grid">
        ${cards.map((card) => `
          <article class="info-card">
            <h4>${escapeHtml(card.title)}</h4>
            <p>${escapeHtml(card.body)}</p>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderFileList(title, files = []) {
  if (!files.length) return "";
  return `
    <section class="section-card">
      <h3>${escapeHtml(title)}</h3>
      <ul class="file-list">
        ${files.map((file) => `
          <li class="file-item">
            <strong><a href="${pathToHref(file.path)}">${escapeHtml(file.label || file.path)}</a></strong>
            ${file.note ? `<span>${escapeHtml(file.note)}</span>` : ""}
            <a class="file-path" href="${pathToHref(file.path)}">${escapeHtml(file.path)}</a>
          </li>
        `).join("")}
      </ul>
    </section>
  `;
}

function renderDocs(docs = []) {
  if (!docs.length) return "";
  return `
    <section class="section-card">
      <h3>Existing docs</h3>
      <ul class="doc-list">
        ${docs.map((doc) => `
          <li class="doc-item">
            <strong><a href="${pathToHref(doc.path)}">${escapeHtml(doc.label)}</a></strong>
            <span>${escapeHtml(doc.path)}</span>
          </li>
        `).join("")}
      </ul>
    </section>
  `;
}

function renderWarnings(warnings = []) {
  if (!warnings.length) return "";
  return `
    <section class="warning-panel">
      <h3>Warnings and limitations</h3>
      <ul class="warning-list">
        ${warnings.map((warning) => `<li class="warning-item">${escapeHtml(warning)}</li>`).join("")}
      </ul>
    </section>
  `;
}

function renderDiagram(tab) {
  const diagram = tab.diagram;
  const miniMap = renderMiniMap(tab.flow);
  if (!diagram && !miniMap) return "";
  const id = `diagram-${tab.id}`;
  const fallback = diagram
    ? `Optional exported SVG was not found in this worktree: <code>${escapeHtml(diagram.repo_path)}</code>. The CSS flow above remains the primary diagram for this static page.`
    : "This tab uses the CSS/SVG flow above as its diagram.";

  requestAnimationFrame(() => {
    if (!diagram) return;
    const slot = document.getElementById(id);
    if (!slot) return;
    const img = new Image();
    img.alt = diagram.label;
    img.onload = () => {
      slot.innerHTML = "";
      slot.appendChild(img);
    };
    img.onerror = () => {
      slot.innerHTML = `<p class="diagram-fallback">${fallback}</p>`;
    };
    img.src = diagram.relative_src;
  });

  return `
    <section class="diagram-panel">
      <h3>${escapeHtml(diagram?.label || "Simplified flow map")}</h3>
      <div class="diagram-frame" id="${id}">
        ${miniMap || `<p class="diagram-fallback">${fallback}</p>`}
      </div>
    </section>
  `;
}

function renderRepoGroups(groups = []) {
  if (!groups.length) return "";
  return `
    <section class="section-card">
      <h3>Repository groups</h3>
      <div class="repo-groups">
        ${groups.map((group) => `
          <article class="repo-group">
            <h4>${escapeHtml(group.name)}</h4>
            <div class="chip-row">
              ${group.paths.map((path) => `<a class="file-chip" href="${pathToHref(path)}">${escapeHtml(path)}</a>`).join("")}
            </div>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderSplitLists(tab) {
  if (!tab.production_files && !tab.research_files && !tab.commands) return "";
  const production = tab.production_files ? `
    <section class="section-card">
      <h3>Production default files</h3>
      <ul class="split-list">
        ${tab.production_files.map((path) => `<li class="split-item"><strong><a href="${pathToHref(path)}">${escapeHtml(path)}</a></strong></li>`).join("")}
      </ul>
    </section>
  ` : "";
  const research = tab.research_files ? `
    <section class="section-card">
      <h3>Research/manual files</h3>
      <ul class="split-list">
        ${tab.research_files.map((path) => `<li class="split-item"><strong><a href="${pathToHref(path)}">${escapeHtml(path)}</a></strong></li>`).join("")}
      </ul>
    </section>
  ` : "";
  const commands = tab.commands ? `
    <section class="section-card">
      <h3>Optional commands</h3>
      <div class="command-row">
        ${tab.commands.map((command) => `<code class="command-chip">${escapeHtml(command)}</code>`).join("")}
      </div>
    </section>
  ` : "";
  const split = production || research
    ? `<div class="split-columns">${production}${research}</div>`
    : "";
  return `${split}${commands}`;
}

function renderCoverage() {
  const coverage = projectMap.coverage;
  if (!coverage) return "";
  return `
    <section class="section-card">
      <h3>Current data coverage</h3>
      <p class="panel-summary">${escapeHtml(coverage.summary)}</p>
      <div class="split-columns">
        <div>
          <h3>Strongest 5-year backfill</h3>
          <ul class="split-list">
            ${coverage.strongest_backfill.map((item) => `<li class="split-item"><strong>${escapeHtml(item)}</strong></li>`).join("")}
          </ul>
        </div>
        <div>
          <h3>Partial or experimental</h3>
          <ul class="split-list">
            ${coverage.partial_or_experimental.map((item) => `<li class="split-item"><strong>${escapeHtml(item)}</strong></li>`).join("")}
          </ul>
        </div>
      </div>
    </section>
  `;
}

function renderTab(tab) {
  app.innerHTML = `
    <article class="tab-panel">
      <section class="panel-head">
        <p class="eyebrow">${escapeHtml(tab.eyebrow)}</p>
        <h2>${escapeHtml(tab.title)}</h2>
        <p class="panel-summary">${escapeHtml(tab.summary)}</p>
        ${renderPills(tab.badges)}
      </section>
      ${renderFlow(tab.flow)}
      ${renderCards(tab.cards)}
      ${tab.id === "overview" ? renderCoverage() : ""}
      ${renderRepoGroups(tab.repo_groups)}
      ${renderSplitLists(tab)}
      <div class="grid-two">
        ${renderFileList("Important files", tab.important_files)}
        ${renderDocs(tab.docs)}
      </div>
      ${renderDiagram(tab)}
      ${renderWarnings(tab.warnings)}
    </article>
  `;
}

function renderTabs() {
  tabList.innerHTML = projectMap.tabs.map((tab) => `
    <button
      class="tab-button"
      type="button"
      role="tab"
      id="tab-${tab.id}"
      aria-controls="panel-${tab.id}"
      aria-selected="${tab.id === activeTabId ? "true" : "false"}"
      data-tab-id="${tab.id}"
    >${escapeHtml(tab.label)}</button>
  `).join("");

  tabList.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      activeTabId = button.dataset.tabId;
      window.location.hash = activeTabId;
      renderTabs();
      renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId) || projectMap.tabs[0]);
    });
  });
}

async function init() {
  const result = await loadProjectMap();
  projectMap = result.data;
  if (result.mode === "fallback") {
    dataMode.hidden = false;
    dataMode.textContent = "Browser blocked project_map.json fetch, so the bundled static fallback is being used. The JSON file is still available next to this page.";
  }
  if (!projectMap.tabs.some((tab) => tab.id === activeTabId)) {
    activeTabId = projectMap.tabs[0].id;
  }
  renderTabs();
  renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId));
}

init();
