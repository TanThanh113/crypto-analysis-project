const FALLBACK_MAP = {
  "metadata": {
    "project_name": "Crypto Analytics and ML Signal Platform",
    "short_name": "Crypto Analytics Explorer",
    "purpose": "Static visual guide for recruiters and reviewers.",
    "last_curated": "2026-06-07",
    "scope_notes": [
      "This is an analytics and ML signal platform, not a trading bot.",
      "The page is documentation-only and does not run ingestion, training, deployment, or cloud writes.",
      "MLflow, Optuna, and MLflow Registry are optional and off by default.",
      "subset9 and microstructure features are research/manual candidates, not production defaults."
    ],
    "github_repo_url": "https://github.com/TanThanh113/crypto-analysis-project",
    "github_branch": "main"
  },
  "coverage": {
    "summary": "Reliable 5-year backfill coverage is currently strongest for Binance trades, ETF indicators, macro indicators, and funding data. Other sources are partial, experimental, or not fully live-ready.",
    "strongest_backfill": [
      "Binance trades",
      "ETF indicators",
      "Macro indicators",
      "Funding data"
    ],
    "partial_or_experimental": [
      "Stablecoin supply",
      "Liquidation heatmap",
      "Options",
      "Exchange reserves",
      "Reddit and Telegram sentiment",
      "Live taker-pressure and streaming context"
    ]
  },
  "tabs": [
    {
      "id": "overview",
      "label": "Platform Overview",
      "eyebrow": "Project at a glance",
      "title": "Platform Overview",
      "summary": "Guided view of how batch and streaming ingestion, dbt, orchestration, runtime infrastructure, CI/CD, and conservative ML signal workflows fit together.",
      "badges": [
        "Analytics platform",
        "ML signal research",
        "Not a trading bot",
        "Cloud-native design"
      ],
      "flow": [
        "External Sources",
        "Batch + Streaming",
        "GCS / BigQuery",
        "dbt Marts",
        "ML Signals",
        "Monitoring"
      ],
      "cards": [
        {
          "title": "End-to-End Scope",
          "body": "Ingestion, dbt marts, orchestration, MLOps controls, monitoring, CI/CD, and deployment gates are connected in one repo."
        },
        {
          "title": "Conservative Runtime",
          "body": "Production prediction is artifact-first. Registry, Optuna, and research candidates stay opt-in."
        },
        {
          "title": "Explicit Data Coverage",
          "body": "Best historical confidence: Binance trades, ETF, macro, and funding. Other feeds are partial."
        },
        {
          "title": "Optional AI Codebase Map",
          "body": "Understand-Anything can support deeper code exploration after reviewers understand the curated pipeline map; it is optional and not a source of truth.",
          "href": "#ai-codebase-map",
          "link_label": "Open AI Codebase Map"
        }
      ],
      "important_files": [
        {
          "path": "README.md",
          "label": "Project Overview",
          "note": "Top-level project summary and safety notes.",
          "tag": "Docs"
        },
        {
          "path": "docs/architecture.md",
          "label": "Architecture Guide",
          "note": "End-to-end platform architecture and operational boundaries.",
          "tag": "Docs"
        },
        {
          "path": "docs/repository_map.md",
          "label": "Repository Map",
          "note": "Folder-by-folder reviewer guide.",
          "tag": "Docs"
        }
      ],
      "docs": [
        {
          "path": "README.md",
          "label": "Project README",
          "note": "Portfolio-level summary and reading path.",
          "tag": "Docs"
        },
        {
          "path": "docs/architecture.md",
          "label": "Architecture Docs",
          "note": "End-to-end platform architecture and boundaries.",
          "tag": "Docs"
        }
      ],
      "diagram": {
        "label": "High-level architecture",
        "repo_path": "docs/diagrams/overview_architecture.svg",
        "relative_src": "../diagrams/overview_architecture.svg",
        "optional": true
      },
      "warnings": [
        "Do not present the system as automated trading infrastructure.",
        "Do not infer model edge from partial source coverage."
      ]
    },
    {
      "id": "batch",
      "label": "Batch Ingestion",
      "eyebrow": "Most mature ingestion path",
      "title": "Batch Ingestion and Trusted Backfills",
      "summary": "Most mature ingestion path for trusted collectors, selected historical backfills, validation, and downstream analytics/ML preparation.",
      "badges": [
        "Backfill-aware",
        "Validation utilities",
        "Cloud writes only when configured"
      ],
      "flow": [
        "Trusted Sources",
        "Main Collectors",
        "Validation Rules",
        "Raw / Curated Landing",
        "dbt Models",
        "Dashboards / ML"
      ],
      "cards": [
        {
          "title": "Trusted Five-Year Coverage",
          "body": "Reliable 5-year backfill is strongest for Binance trades, ETF indicators, macro indicators, and funding data."
        },
        {
          "title": "Backfill Discipline",
          "body": "Historical loaders can be expensive and may write to cloud targets, so they should run only when intentionally configured."
        },
        {
          "title": "Validation Before Modeling",
          "body": "Rule-based validation and quality audit paths help catch schema, freshness, and data-quality issues before dbt and ML consume the data."
        }
      ],
      "important_files": [
        {
          "path": "local_scripts/batch",
          "label": "Main Collectors",
          "note": "Collectors for trusted and experimental batch sources.",
          "tag": "Pipeline"
        },
        {
          "path": "local_scripts/batch/backfill",
          "label": "Backfill Scripts",
          "note": "Historical loaders for selected trusted sources.",
          "tag": "Pipeline"
        },
        {
          "path": "local_scripts/batch/validation",
          "label": "Validation Rules",
          "note": "Validation engine and YAML rulesets.",
          "tag": "Validation"
        },
        {
          "path": "local_scripts/batch/quality_audit/specs",
          "label": "Quality Audit Specs",
          "note": "Great Expectations-style specs for dashboard, ML, and freshness checks.",
          "tag": "Validation"
        },
        {
          "path": "local_scripts/batch/iceberg_loader.py",
          "label": "Iceberg / BigLake Path",
          "note": "Lakehouse-oriented loader path for curated storage workflows.",
          "tag": "Iceberg"
        }
      ],
      "docs": [
        {
          "path": "docs/batch_pipeline.md",
          "label": "Batch Pipeline Docs",
          "note": "Beginner-friendly guide to collectors, backfills, validation, and safety.",
          "tag": "Docs"
        }
      ],
      "diagram": {
        "label": "Batch pipeline",
        "repo_path": "docs/diagrams/batch_pipeline.svg",
        "relative_src": "../diagrams/batch_pipeline.svg",
        "optional": true
      },
      "warnings": [
        "Do not run backfills casually.",
        "Avoid documenting or linking local .env files, service account keys, local output data, or Terraform state."
      ]
    },
    {
      "id": "streaming",
      "label": "Streaming Pipeline",
      "eyebrow": "Lower-latency path",
      "title": "Streaming Pipeline and Freshness Path",
      "summary": "Lower-latency producer and Flink/Kafka-oriented transformation area for freshness experiments; still partial compared with trusted batch coverage.",
      "badges": [
        "Kafka / Redpanda style",
        "Flink-oriented",
        "Experimental coverage"
      ],
      "flow": [
        "Producers",
        "Kafka / Redpanda",
        "Flink transforms",
        "Streaming sink",
        "Downstream marts"
      ],
      "cards": [
        {
          "title": "Producer Layer",
          "body": "Market, on-chain, and sentiment producers prepare lower-latency context for streaming experiments."
        },
        {
          "title": "Flink Transformations",
          "body": "Transformation modules shape recent signals such as order-flow, breakout, liquidation, and dead-letter handling."
        },
        {
          "title": "Experimental Boundary",
          "body": "Streaming is useful for freshness work, but it is not the primary full-history training coverage path yet."
        }
      ],
      "important_files": [
        {
          "path": "local_scripts/streaming/producer",
          "label": "Streaming Producers",
          "note": "Market, on-chain, and sentiment producers.",
          "tag": "Pipeline"
        },
        {
          "path": "local_scripts/streaming/logic_crypto_streaming/main.py",
          "label": "Streaming Entrypoint",
          "note": "Flink-oriented transformation entrypoint.",
          "tag": "Pipeline"
        },
        {
          "path": "local_scripts/streaming/logic_crypto_streaming/transformations",
          "label": "Transformation Modules",
          "note": "Signal transformation modules and dead-letter handling.",
          "tag": "Pipeline"
        },
        {
          "path": "local_scripts/streaming/scripts",
          "label": "Sink Specs and Helpers",
          "note": "BigQuery sink specs and local deployment helper scripts; avoid secrets.",
          "tag": "Config"
        }
      ],
      "docs": [
        {
          "path": "docs/streaming_pipeline.md",
          "label": "Streaming Pipeline Docs",
          "note": "Beginner-friendly guide to producers, Kafka/Flink concepts, and freshness boundaries.",
          "tag": "Docs"
        }
      ],
      "diagram": {
        "label": "Streaming pipeline",
        "repo_path": "docs/diagrams/streaming_pipeline.svg",
        "relative_src": "../diagrams/streaming_pipeline.svg",
        "optional": true
      },
      "warnings": [
        "Validate topic, connector, sink, and freshness health before tying streaming output to automatic prediction.",
        "Do not expose local connector credentials or key files in documentation."
      ]
    },
    {
      "id": "dbt",
      "label": "dbt Transformation Layers",
      "eyebrow": "Transformation layers",
      "title": "dbt Transformation Layers",
      "summary": "Layered BigQuery models normalize sources, align time-series features, and publish dashboard, ML, and monitoring marts.",
      "badges": [
        "Staging",
        "Intermediate",
        "Core marts",
        "Dashboard marts",
        "ML marts",
        "Monitoring"
      ],
      "flow": [
        "Sources",
        "Staging Models",
        "Intermediate Models",
        "Core Marts",
        "Dashboard / ML Marts",
        "Monitoring Marts"
      ],
      "cards": [
        {
          "title": "Readable Lineage",
          "body": "Staging normalizes sources, intermediate models align features, and marts publish dashboard, ML, and monitoring contracts."
        },
        {
          "title": "ML Contract Boundary",
          "body": "dbt may expose additive research columns, but production training only uses the conservative ml/feature_list.yml contract."
        }
      ],
      "important_files": [
        {
          "path": "dbt_transform/crypto_dbt/dbt_project.yml",
          "label": "dbt Project Config",
          "note": "Project-level model configuration.",
          "tag": "Config"
        },
        {
          "path": "dbt_transform/crypto_dbt/models/staging",
          "label": "Staging Models",
          "note": "Source normalization and type cleanup. Technical prefix: stg_*.",
          "tag": "Docs"
        },
        {
          "path": "dbt_transform/crypto_dbt/models/intermediate",
          "label": "Intermediate Models",
          "note": "Hourly/daily alignment and feature aggregation. Technical prefix: int_*.",
          "tag": "Docs"
        },
        {
          "path": "dbt_transform/crypto_dbt/models/marts/core",
          "label": "Core Marts",
          "note": "Reusable analytics facts.",
          "tag": "Docs"
        },
        {
          "path": "dbt_transform/crypto_dbt/models/marts/dashboard",
          "label": "Dashboard Marts",
          "note": "BI-ready outputs.",
          "tag": "Docs"
        },
        {
          "path": "dbt_transform/crypto_dbt/models/marts/ml",
          "label": "ML Marts",
          "note": "Training dataset and prediction input.",
          "tag": "Production"
        },
        {
          "path": "dbt_transform/crypto_dbt/models/marts/monitoring",
          "label": "Monitoring Marts",
          "note": "Freshness, quality, and pipeline health.",
          "tag": "Validation"
        }
      ],
      "docs": [
        {
          "path": "docs/dbt_models.md",
          "label": "dbt Model Docs",
          "note": "Layer-by-layer guide to staging, intermediate, marts, ML, and monitoring models.",
          "tag": "Docs"
        }
      ],
      "diagram": {
        "label": "dbt transformation layers",
        "repo_path": "docs/diagrams/dbt_layers.svg",
        "relative_src": "../diagrams/dbt_layers.svg",
        "optional": true
      },
      "warnings": [
        "Avoid label leakage when changing ML marts.",
        "Inspect partitioning, clustering, and materialization before cloud-backed builds."
      ]
    },
    {
      "id": "ml",
      "label": "ML and MLOps Lifecycle",
      "eyebrow": "Conservative signal workflow",
      "title": "ML and MLOps Lifecycle",
      "summary": "Conservative artifact-first training and prediction with feature contracts, promotion gates, optional MLflow/Optuna/Registry, and research-only scripts kept separate.",
      "badges": [
        "Artifact-first",
        "Feature contract",
        "Optional MLflow",
        "Optional Optuna",
        "Optional Registry"
      ],
      "flow": [
        "Training dataset",
        "Feature contract",
        "Train strategies",
        "MLflow / Optuna",
        "Promotion gate",
        "Artifact prediction"
      ],
      "cards": [
        {
          "title": "Default Production Posture",
          "body": "Prediction loads artifacts by default. Registry loading is optional and only used when explicitly configured."
        },
        {
          "title": "Research Separation",
          "body": "local_*.py scripts support diagnostics, AutoML, ablation, keeper validation, and microstructure experiments without becoming production serving paths."
        },
        {
          "title": "subset9 / Microstructure",
          "body": "These features are research/manual candidates and have not replaced the baseline production contract."
        }
      ],
      "important_files": [
        {
          "path": "ml/train_model.py",
          "label": "Training Entrypoint",
          "note": "Trains models and writes artifacts when configured.",
          "tag": "Production"
        },
        {
          "path": "ml/predict_latest.py",
          "label": "Prediction Entrypoint",
          "note": "Loads latest artifact or optional registry model.",
          "tag": "Production"
        },
        {
          "path": "ml/feature_list.yml",
          "label": "Production Feature Contract",
          "note": "Conservative default contract; do not change casually.",
          "tag": "Config"
        },
        {
          "path": "ml/feature_contract.py",
          "label": "Contract Hashing",
          "note": "Stable metadata for lineage.",
          "tag": "Production"
        },
        {
          "path": "ml/promotion_gate.py",
          "label": "Promotion Gate",
          "note": "Prevents automatic promotion of worse candidates.",
          "tag": "Production"
        },
        {
          "path": "ml/model_loader.py",
          "label": "Model Loader",
          "note": "Artifact-first and optional registry loading.",
          "tag": "Production"
        },
        {
          "path": "ml/local_automl_research.py",
          "label": "Local AutoML Research",
          "note": "Research-only local tooling.",
          "tag": "Research"
        },
        {
          "path": "ml/local_microstructure_subset_contract_trial.py",
          "label": "Microstructure Contract Trial",
          "note": "Manual research candidate workflow.",
          "tag": "Research"
        }
      ],
      "docs": [
        {
          "path": "docs/ml_mLOps.md",
          "label": "ML/MLOps Docs",
          "note": "Beginner-friendly guide to training, prediction, optional MLOps, and research boundaries.",
          "tag": "Docs"
        }
      ],
      "diagram": {
        "label": "ML and MLOps workflow",
        "repo_path": "docs/diagrams/ml_mLOps_workflow.svg",
        "relative_src": "../diagrams/ml_mLOps_workflow.svg",
        "optional": true
      },
      "warnings": [
        "MLflow, Optuna, and Registry are optional/off by default.",
        "Do not modify ml/feature_list.yml as part of documentation polish.",
        "Do not run training during documentation-only review."
      ]
    },
    {
      "id": "kestra",
      "label": "Kestra Orchestration",
      "eyebrow": "Orchestration",
      "title": "Kestra Orchestration",
      "summary": "Flow grouping and orchestration logic for raw, dbt, ML, streaming, monitoring, quality, preview, and master flows. Kubernetes runtime details live in the K8s/GKE tab.",
      "badges": [
        "Raw Flows",
        "dbt Flows",
        "ML Gated",
        "Monitoring",
        "Preview Flows"
      ],
      "flow": [
        "Raw Flows",
        "dbt Flows",
        "Quality Checks",
        "ML Flows",
        "Master Flow",
        "PR Previews"
      ],
      "cards": [
        {
          "title": "Flow Grouping",
          "body": "Flows are grouped by workflow intent: raw ingestion, dbt transforms, ML, streaming, monitoring, quality, preview, and master overview."
        },
        {
          "title": "Schedules and Preconditions",
          "body": "Production-style flows encode orchestration timing and dependencies, while PR preview flows avoid production triggers."
        },
        {
          "title": "ML Deploy Gate",
          "body": "ML flow deployment remains separately gated so ML runtime changes are intentional."
        }
      ],
      "important_files": [
        {
          "path": "kestra/flows-gke/raw",
          "label": "Raw Flows",
          "note": "Batch ingestion snapshots and intraday refresh flow definitions.",
          "tag": "Orchestration"
        },
        {
          "path": "kestra/flows-gke/dbt",
          "label": "dbt Flows",
          "note": "Hourly, intraday, daily market, macro, and ETF transform flows.",
          "tag": "Orchestration"
        },
        {
          "path": "kestra/flows-gke/ml",
          "label": "ML Flows",
          "note": "Training, prediction, and strategy matrix flow definitions.",
          "tag": "Orchestration"
        },
        {
          "path": "kestra/flows-gke/preview",
          "label": "Preview Flows",
          "note": "PR validation flows without production triggers.",
          "tag": "Orchestration"
        },
        {
          "path": "kestra/flows-gke/master",
          "label": "Master Flow",
          "note": "Overview orchestration flow.",
          "tag": "Orchestration"
        }
      ],
      "docs": [
        {
          "path": "docs/kestra_orchestration.md",
          "label": "Kestra Orchestration Docs",
          "note": "Beginner-friendly guide to flow grouping, gates, and orchestration boundaries.",
          "tag": "Docs"
        }
      ],
      "diagram": {
        "label": "CI/CD and Kestra gating",
        "repo_path": "docs/diagrams/ci_cd_kestra_gating.svg",
        "relative_src": "../diagrams/ci_cd_kestra_gating.svg",
        "optional": true
      },
      "warnings": [
        "Do not enable ML deploy simply to make checks green.",
        "Do not add triggers to PR preview flows."
      ]
    },
    {
      "id": "k8s-gke",
      "label": "K8s / GKE Runtime",
      "eyebrow": "Runtime infrastructure",
      "title": "K8s / GKE Runtime",
      "summary": "Runtime layer for production-style jobs and Kestra task execution using GKE Autopilot, Kubernetes pods, Artifact Registry images, Workload Identity, Helm values, and Kubernetes manifests.",
      "badges": [
        "GKE Autopilot",
        "Kubernetes Pods",
        "Artifact Registry",
        "Workload Identity",
        "Cloud SQL"
      ],
      "flow": [
        "Docker Images",
        "Artifact Registry",
        "GKE Cluster",
        "Kestra Runtime",
        "Task Pods",
        "Runtime Safety"
      ],
      "cards": [
        {
          "title": "GKE Runtime Layer",
          "body": "GKE provides the Kubernetes runtime where production-style jobs and Kestra task pods can execute."
        },
        {
          "title": "Kubernetes Pod Execution",
          "body": "Kestra task execution is separated into pods so batch, dbt, ML, and streaming work can use purpose-built images."
        },
        {
          "title": "Artifact Registry Images",
          "body": "Batch, dbt, and ML images are built separately and referenced by orchestration/runtime layers."
        },
        {
          "title": "Workload Identity",
          "body": "Cloud access should use Workload Identity and service account bindings instead of committed keys."
        },
        {
          "title": "Cloud SQL Dependency for Kestra",
          "body": "Kestra webserver, executor, and worker components may fail if Cloud SQL, required secrets, or identity bindings are not ready."
        },
        {
          "title": "Runtime Safety",
          "body": "This runtime layer is infrastructure. It does not define model logic or prove model quality."
        }
      ],
      "important_files": [
        {
          "path": "k8s",
          "label": "Kubernetes Manifests",
          "note": "RBAC and secret-provider support manifests for Kestra runtime.",
          "tag": "Runtime"
        },
        {
          "path": "helm/kestra/values-gke.yaml",
          "label": "Kestra Helm Values",
          "note": "GKE-oriented Helm values for Kestra components.",
          "tag": "Runtime"
        },
        {
          "path": "docker",
          "label": "Runtime Docker Images",
          "note": "Batch, dbt, and ML Dockerfiles used by runtime jobs.",
          "tag": "Runtime"
        },
        {
          "path": "kestra/flows-gke",
          "label": "GKE Flow Definitions",
          "note": "Kestra flows intended for GKE-oriented execution.",
          "tag": "Orchestration"
        },
        {
          "path": ".github/workflows/kestra-deploy-gke.yml",
          "label": "Kestra Deploy Workflow",
          "note": "CI workflow that plans and deploys selected GKE flows.",
          "tag": "CI/CD"
        },
        {
          "path": ".github/scripts/kestra_deploy_plan.py",
          "label": "Deploy Plan Helper",
          "note": "Computes deployment/build gating decisions.",
          "tag": "CI/CD"
        },
        {
          "path": ".github/scripts/deploy_kestra_flows.py",
          "label": "Flow Deploy Helper",
          "note": "Deploys selected flows from CI when gates allow it.",
          "tag": "CI/CD"
        }
      ],
      "docs": [
        {
          "path": "docs/k8s_gke_runtime.md",
          "label": "K8s / GKE Runtime Docs",
          "note": "Runtime guide for Kubernetes, GKE, Helm, images, identity, and Cloud SQL dependencies.",
          "tag": "Docs"
        }
      ],
      "warnings": [
        "Do not deploy GKE flows just to make PR checks green.",
        "Kestra components may fail if Cloud SQL, required secrets, or identity bindings are not ready.",
        "ML Kestra deploy remains gated.",
        "GKE runtime is infrastructure/runtime, not model logic."
      ]
    },
    {
      "id": "terraform",
      "label": "Terraform Infrastructure",
      "eyebrow": "Infrastructure as code",
      "title": "Terraform Infrastructure",
      "summary": "Terraform describes cloud infrastructure such as BigQuery datasets, GCS buckets, Artifact Registry, GKE/Kestra resources, Cloud SQL, IAM, networking, and Grafana support. This docs task does not run terraform apply.",
      "badges": [
        "GCP Resources",
        "IAM",
        "Cloud SQL",
        "Artifact Registry",
        "State Safety"
      ],
      "flow": [
        "Providers",
        "GCP Resources",
        "IAM Bindings",
        "Runtime Infra",
        "State Safety",
        "Review Only"
      ],
      "cards": [
        {
          "title": "Infrastructure as Code",
          "body": "Terraform keeps cloud resources described in code so infra can be reviewed instead of configured by memory."
        },
        {
          "title": "GCP Resources",
          "body": "The repo includes Terraform for BigQuery, GCS, Artifact Registry, GKE/Kestra, Cloud SQL, networking, and monitoring support."
        },
        {
          "title": "IAM and Service Accounts",
          "body": "IAM and service-account definitions support Workload Identity and CI/CD access patterns."
        },
        {
          "title": "Cloud SQL for Kestra",
          "body": "Kestra infrastructure includes Cloud SQL-related resources and secrets wiring."
        },
        {
          "title": "Artifact Registry",
          "body": "Artifact Registry stores runtime images for batch, dbt, and ML jobs."
        },
        {
          "title": "State and Secrets Safety",
          "body": "State files, tfvars with secrets, service account keys, and local credentials must never be committed or exposed."
        }
      ],
      "important_files": [
        {
          "path": "terraform",
          "label": "Main Terraform Module",
          "note": "Primary GCP infrastructure definitions.",
          "tag": "Infra"
        },
        {
          "path": "terraform/provider.tf",
          "label": "Terraform Provider Config",
          "note": "Provider configuration for the main Terraform module.",
          "tag": "Infra"
        },
        {
          "path": "terraform/main.tf",
          "label": "Main Infrastructure Entry",
          "note": "Main resource composition entrypoint.",
          "tag": "Infra"
        },
        {
          "path": "terraform/artifact_registry.tf",
          "label": "Artifact Registry Resources",
          "note": "Container image registry resources.",
          "tag": "Infra"
        },
        {
          "path": "terraform/kestra_gke.tf",
          "label": "Kestra GKE Resources",
          "note": "GKE-oriented Kestra runtime infrastructure.",
          "tag": "Infra"
        },
        {
          "path": "terraform/kestra_cloudsql.tf",
          "label": "Cloud SQL for Kestra",
          "note": "Cloud SQL resources used by Kestra.",
          "tag": "Infra"
        },
        {
          "path": "terraform-bootstrap/main.tf",
          "label": "Bootstrap Terraform",
          "note": "Bootstrap IAM/service-account setup.",
          "tag": "Infra"
        },
        {
          "path": "terraform-grafana/main.tf",
          "label": "Grafana Terraform",
          "note": "Grafana-related infrastructure support.",
          "tag": "Infra"
        }
      ],
      "docs": [
        {
          "path": "docs/terraform_infrastructure.md",
          "label": "Terraform Infrastructure Docs",
          "note": "Beginner-friendly guide to infra modules, resources, and safety boundaries.",
          "tag": "Docs"
        }
      ],
      "warnings": [
        "Never commit .tfstate, .tfvars with secrets, service account keys, or local credentials.",
        "Do not run terraform apply casually.",
        "Terraform docs are descriptive in this PR only."
      ]
    },
    {
      "id": "cicd",
      "label": "CI/CD and Deployment Gates",
      "eyebrow": "Deployment gates",
      "title": "CI/CD and Deployment Gates",
      "summary": "GitHub Actions, repo guard, Docker gate, Kestra deploy plan, and PR required gate keep docs-only and runtime PRs separated.",
      "badges": [
        "Repo guard",
        "Docker build gate",
        "Kestra deploy plan",
        "PR required gate"
      ],
      "flow": [
        "PR changes",
        "Quality checks",
        "Deploy plan",
        "Docker gate",
        "Kestra gate",
        "Required gate"
      ],
      "cards": [
        {
          "title": "GitHub Actions Gatekeeping",
          "body": "Workflows run quality checks, plan deploy needs, and aggregate required status for PRs."
        },
        {
          "title": "Docker Gate",
          "body": "Docker image work is gated so docs-only PRs do not build runtime images unnecessarily."
        },
        {
          "title": "Kestra Deploy Plan",
          "body": "Deploy planning decides which flow groups and runtime checks are relevant without explaining Kubernetes runtime internals."
        },
        {
          "title": "Docs-Only Safety",
          "body": "Documentation changes should not trigger training, backfills, deploys, cloud writes, or Docker builds."
        }
      ],
      "important_files": [
        {
          "path": ".github/workflows/quality-check.yml",
          "label": "Quality Checks",
          "note": "Tests, repo guard, and static validation workflow.",
          "tag": "CI/CD"
        },
        {
          "path": ".github/workflows/docker-build-push.yml",
          "label": "Docker Build Gate",
          "note": "Gated Docker build and smoke workflow.",
          "tag": "CI/CD"
        },
        {
          "path": ".github/workflows/kestra-deploy-gke.yml",
          "label": "Kestra Deploy Gate",
          "note": "Deploys selected flows only when plan allows it.",
          "tag": "CI/CD"
        },
        {
          "path": ".github/workflows/pr-required-gate.yml",
          "label": "PR Required Gate",
          "note": "Aggregates required PR check status.",
          "tag": "CI/CD"
        },
        {
          "path": ".github/scripts/kestra_deploy_plan.py",
          "label": "Kestra Deploy Plan",
          "note": "Computes deploy/build gating outputs.",
          "tag": "CI/CD"
        },
        {
          "path": "scripts/repo_guard.py",
          "label": "Repository Guard",
          "note": "Checks repository safety rules.",
          "tag": "Validation"
        }
      ],
      "docs": [
        {
          "path": "docs/ci_cd_gates.md",
          "label": "CI/CD Gates Docs",
          "note": "Beginner-friendly guide to workflows, gating, and docs-only safety.",
          "tag": "Docs"
        }
      ],
      "diagram": {
        "label": "CI/CD and Kestra gating",
        "repo_path": "docs/diagrams/ci_cd_kestra_gating.svg",
        "relative_src": "../diagrams/ci_cd_kestra_gating.svg",
        "optional": true
      },
      "warnings": [
        "Docs-only changes should not require training, backfills, deploys, or cloud writes.",
        "Secrets, local artifacts, and Terraform state must stay out of docs and commits."
      ]
    },
    {
      "id": "repo-map",
      "label": "Repository Map",
      "eyebrow": "Where to look",
      "title": "Repository Map",
      "summary": "Quick map for ingestion, streaming, dbt, orchestration, ML, infrastructure, CI/CD, Docker, tests, and docs.",
      "badges": [
        "Reviewer guide",
        "Safe paths only",
        "No secret paths"
      ],
      "flow": [
        "Docs",
        "Ingestion",
        "Transform",
        "Orchestrate",
        "ML",
        "Operate"
      ],
      "cards": [
        {
          "title": "Fast Review Path",
          "body": "Start with README.md, docs/architecture.md, docs/repository_map.md, then use this explorer to understand subsystem boundaries."
        },
        {
          "title": "Sensitive Files Omitted",
          "body": "Local env files, key files, Terraform state, logs, generated outputs, and local artifacts are intentionally excluded from this explorer."
        }
      ],
      "repo_groups": [
        {
          "name": "Documentation",
          "paths": [
            "README.md",
            "docs/architecture.md",
            "docs/batch_pipeline.md",
            "docs/streaming_pipeline.md",
            "docs/dbt_models.md",
            "docs/ml_mLOps.md",
            "docs/kestra_orchestration.md",
            "docs/k8s_gke_runtime.md",
            "docs/terraform_infrastructure.md",
            "docs/ci_cd_gates.md",
            "docs/production_boundaries.md",
            "docs/repository_map.md",
            "docs/codebase_knowledge_graph.md"
          ]
        },
        {
          "name": "Batch + Streaming Ingestion",
          "paths": [
            "local_scripts/batch",
            "local_scripts/batch/backfill",
            "local_scripts/batch/validation",
            "local_scripts/streaming/producer",
            "local_scripts/streaming/logic_crypto_streaming"
          ]
        },
        {
          "name": "dbt and Analytics Marts",
          "paths": [
            "dbt_transform/crypto_dbt/models/staging",
            "dbt_transform/crypto_dbt/models/intermediate",
            "dbt_transform/crypto_dbt/models/marts/core",
            "dbt_transform/crypto_dbt/models/marts/dashboard",
            "dbt_transform/crypto_dbt/models/marts/ml",
            "dbt_transform/crypto_dbt/models/marts/monitoring"
          ]
        },
        {
          "name": "Orchestration and Deployment",
          "paths": [
            "kestra/flows-gke",
            ".github/workflows",
            ".github/scripts",
            "docker"
          ]
        },
        {
          "name": "K8s / GKE Runtime",
          "paths": [
            "k8s",
            "helm/kestra/values-gke.yaml",
            "kestra/flows-gke",
            "docker"
          ]
        },
        {
          "name": "Terraform Infrastructure",
          "paths": [
            "terraform",
            "terraform-bootstrap",
            "terraform-grafana"
          ]
        },
        {
          "name": "ML and Research",
          "paths": [
            "ml/train_model.py",
            "ml/predict_latest.py",
            "ml/feature_contract.py",
            "ml/promotion_gate.py",
            "ml/model_loader.py",
            "ml/local_automl_research.py",
            "ml/research/configs"
          ]
        }
      ],
      "important_files": [
        {
          "path": "docs/repository_map.md",
          "label": "Full Repository Map",
          "note": "Canonical folder-by-folder description.",
          "tag": "Docs"
        },
        {
          "path": "scripts/repo_guard.py",
          "label": "Repo Guard",
          "note": "Safety checks for repository hygiene.",
          "tag": "Validation"
        }
      ],
      "docs": [
        {
          "path": "docs/repository_map.md",
          "label": "Repository Map Docs",
          "note": "Grouped repo guide by subsystem, purpose, type, and caution.",
          "tag": "Docs"
        }
      ],
      "warnings": [
        "Avoid linking secret-like files or local generated artifacts.",
        "Treat Terraform state and tfvars as sensitive operational files."
      ]
    },
    {
      "id": "research-production",
      "label": "Production Boundaries",
      "eyebrow": "Operational boundary",
      "title": "Production Boundaries",
      "summary": "Production entrypoints and feature contracts stay separate from local research scripts, experimental features, and optional MLOps.",
      "badges": [
        "Conservative defaults",
        "Research isolated",
        "No auto trading",
        "No auto promotion"
      ],
      "flow": [
        "Production Contract",
        "Train / Predict",
        "Promotion Gate",
        "Artifact Fallback",
        "Optional Registry",
        "Research Stays Manual"
      ],
      "cards": [
        {
          "title": "Production Default Files",
          "body": "The production side stays conservative: explicit feature list, contract hashing, training/prediction entrypoints, promotion gate, and artifact-first loading."
        },
        {
          "title": "Research-Only Files",
          "body": "Local research scripts support exploration, diagnostics, ablation, recall focus, and keeper validation without becoming serving paths."
        },
        {
          "title": "MLOps Optionality",
          "body": "MLflow logging, Optuna tuning, and MLflow Registry integration require explicit configuration and are off by default."
        }
      ],
      "production_files": [
        {
          "path": "ml/train_model.py",
          "label": "Training Entrypoint",
          "note": "Trains models and writes local/GCS artifacts only when explicitly configured.",
          "tag": "Production"
        },
        {
          "path": "ml/predict_latest.py",
          "label": "Prediction Entrypoint",
          "note": "Loads the latest artifact or optional registry model for signal prediction.",
          "tag": "Production"
        },
        {
          "path": "ml/feature_list.yml",
          "label": "Feature List",
          "note": "Conservative production feature contract; not changed by docs work.",
          "tag": "Production"
        },
        {
          "path": "ml/feature_contract.py",
          "label": "Feature Contract",
          "note": "Hashes and validates the feature contract for reproducible lineage.",
          "tag": "Production"
        },
        {
          "path": "ml/promotion_gate.py",
          "label": "Promotion Gate",
          "note": "Prevents automatic promotion of weaker candidate models.",
          "tag": "Production"
        },
        {
          "path": "ml/model_loader.py",
          "label": "Model Loader",
          "note": "Artifact-first model loading with optional registry support.",
          "tag": "Production"
        }
      ],
      "research_files": [
        {
          "path": "ml/local_automl_research.py",
          "label": "Local AutoML Research",
          "note": "Local AutoML exploration and candidate discovery.",
          "tag": "Research"
        },
        {
          "path": "ml/local_feature_label_diagnostics.py",
          "label": "Feature Label Diagnostics",
          "note": "Feature/label diagnostics for model readiness review.",
          "tag": "Research"
        },
        {
          "path": "ml/local_feature_engineering_research.py",
          "label": "Feature Engineering Research",
          "note": "Manual feature exploration outside production defaults.",
          "tag": "Research"
        },
        {
          "path": "ml/local_feature_ablation_research.py",
          "label": "Feature Ablation Research",
          "note": "Ablation experiments for understanding feature contribution.",
          "tag": "Research"
        },
        {
          "path": "ml/local_down_recall_focus_research.py",
          "label": "Down Recall Focus Research",
          "note": "Manual research around downside recall and class behavior.",
          "tag": "Research"
        },
        {
          "path": "ml/local_keeper_candidate_validation.py",
          "label": "Keeper Candidate Validation",
          "note": "Manual validation of keeper candidates before any production consideration.",
          "tag": "Research"
        }
      ],
      "important_files": [
        {
          "path": "ml/feature_list.yml",
          "label": "Production Feature List",
          "note": "Not changed by this documentation work.",
          "tag": "Config"
        },
        {
          "path": "ml/mlflow_utils.py",
          "label": "Optional MLflow Logging",
          "note": "Best-effort unless configured otherwise.",
          "tag": "Research"
        },
        {
          "path": "ml/optuna_tuning.py",
          "label": "Optional Tuning",
          "note": "Off unless explicitly requested.",
          "tag": "Research"
        },
        {
          "path": "ml/mlflow_registry.py",
          "label": "Optional Registry",
          "note": "Alias-based registry integration, not required for prediction.",
          "tag": "Research"
        }
      ],
      "docs": [
        {
          "path": "docs/production_boundaries.md",
          "label": "Production Boundaries Docs",
          "note": "Beginner-friendly guide to production defaults, research-only tooling, and safety boundaries.",
          "tag": "Docs"
        }
      ],
      "warnings": [
        "subset9 and microstructure features are research/manual candidates, not production defaults.",
        "This project should not be described as a trading bot.",
        "Do not run training or promotion as part of docs-only review."
      ]
    },
    {
      "id": "ai-map",
      "label": "AI Codebase Map",
      "eyebrow": "Optional Understand-Anything layer",
      "title": "AI Codebase Map",
      "summary": "Generated by Understand-Anything and published as a static docs asset when available.",
      "badges": [
        "Optional",
        "Static asset",
        "Secondary deep-dive"
      ],
      "flow": [
        "README / docs",
        "Static explorer",
        "Understand-Anything scan",
        "Review / sanitize",
        "Published graph asset",
        "Static viewer"
      ],
      "cards": [
        {
          "title": "What It Is",
          "body": "Understand-Anything is an optional AI-assisted codebase exploration layer. It is not part of the project runtime, pipeline, training workflow, or deployment process."
        },
        {
          "title": "How To Generate Later",
          "body": "Run /understand --language en, then /understand-dashboard only in an environment where Understand-Anything is available and intentionally enabled."
        },
        {
          "title": "Current State",
          "body": "The tab loads a reviewed graph asset from docs/interactive/understand_anything/ when available. If no asset exists, it shows the exact regeneration step."
        },
        {
          "title": "Primary Visual Guide Remains",
          "body": "README, MkDocs pages, production architecture docs, and the curated interactive architecture map remain the source of truth."
        }
      ],
      "commands": [
        "/understand --language en",
        "/understand-dashboard"
      ],
      "important_files": [
        {
          "path": "README.md",
          "label": "Primary Overview",
          "note": "Human-curated documentation remains first.",
          "tag": "Docs"
        },
        {
          "path": "docs/interactive/index.html",
          "label": "Static Explorer",
          "note": "This docs-only page.",
          "tag": "Docs"
        },
        {
          "path": "docs/interactive/understand_anything",
          "label": "Published Graph Asset Folder",
          "note": "Reviewed/sanitized Understand-Anything graph JSON for the static viewer when available.",
          "tag": "Docs"
        }
      ],
      "docs": [
        {
          "path": "docs/codebase_knowledge_graph.md",
          "label": "Codebase Knowledge Graph Docs",
          "note": "Optional Understand-Anything placeholder and future exploration guide.",
          "tag": "Docs"
        }
      ],
      "warnings": [
        "Do not commit raw local cache, secrets, local paths, Terraform state, or oversized generated graph output blindly.",
        "Do not require Understand-Anything for normal project operation."
      ]
    }
  ]
};

const FALLBACK_ARCHITECTURE_MAP = {
  metadata: {
    title: "Interactive Architecture Map",
    summary: "A static, data-driven architecture map for recruiter/reviewer orientation."
  },
  flows: [
    { id: "all", label: "All", summary: "Show the full platform architecture." },
    { id: "batch", label: "Batch", summary: "Trusted historical ingestion and validation path." },
    { id: "streaming", label: "Streaming", summary: "Lower-latency freshness path with partial/experimental coverage." },
    { id: "dbt", label: "dbt", summary: "Warehouse transformation path for analytics, monitoring, dashboard, and ML marts." },
    { id: "ml", label: "ML/MLOps", summary: "Artifact-first ML workflow with optional tracking, tuning, and registry helpers." },
    { id: "infra", label: "Infra/Runtime", summary: "Runtime, identity, Terraform, CI/CD, and orchestration gates." }
  ],
  groups: [
    {
      id: "sources",
      title: "Sources",
      summary: "Market, ETF, macro, funding, sentiment, and experimental context inputs.",
      nodes: [
        {
          id: "external_sources",
          title: "External Data Sources",
          summary: "Upstream feeds used by batch collectors and streaming producers.",
          status: "mixed",
          flows: ["batch", "streaming"],
          boundary: "Strongest 5-year backfill: Binance trades, ETF, macro, and funding. Other sources are partial or experimental.",
          paths: ["local_scripts/batch", "local_scripts/streaming/producer"],
          docs: [{ label: "Architecture", href: "../architecture/" }]
        }
      ]
    },
    {
      id: "ingestion",
      title: "Ingestion",
      summary: "Batch collectors, backfills, and validation controls.",
      nodes: [
        {
          id: "batch_collectors",
          title: "Batch Collectors",
          summary: "Primary trusted historical ingestion area.",
          status: "production-style",
          flows: ["batch"],
          boundary: "Backfills and cloud-write collectors should run only when intentionally configured.",
          paths: ["local_scripts/batch", "local_scripts/batch/backfill", "local_scripts/batch/validation"],
          docs: [{ label: "Batch Pipeline", href: "../batch_pipeline/" }]
        }
      ]
    },
    {
      id: "streaming",
      title: "Streaming",
      summary: "Lower-latency freshness path.",
      nodes: [
        {
          id: "streaming_stack",
          title: "Kafka / Redpanda / Flink",
          summary: "Producer, broker, transform, sink, and dead-letter pattern for streaming experiments.",
          status: "experimental",
          flows: ["streaming", "infra"],
          boundary: "Streaming coverage is partial and should not be treated as fully live-ready.",
          paths: ["local_scripts/streaming/producer", "local_scripts/streaming/docker-compose.yaml", "local_scripts/streaming/logic_crypto_streaming"],
          docs: [{ label: "Streaming Pipeline", href: "../streaming_pipeline/" }]
        }
      ]
    },
    {
      id: "storage",
      title: "Storage",
      summary: "Cloud-oriented landing and warehouse surfaces.",
      nodes: [
        {
          id: "storage_targets",
          title: "GCS / BigLake / BigQuery",
          summary: "Landing and warehouse targets for downstream dbt and analytics.",
          status: "infra-defined",
          flows: ["batch", "streaming", "dbt", "infra"],
          boundary: "Do not write to GCS or BigQuery during docs-only work.",
          paths: ["terraform/gcs_buckets.tf", "terraform/bigquery_datasets.tf", "local_scripts/batch/iceberg_loader.py"],
          docs: [{ label: "Terraform Infrastructure", href: "../terraform_infrastructure/" }]
        }
      ]
    },
    {
      id: "transform",
      title: "Transform",
      summary: "dbt layers and marts.",
      nodes: [
        {
          id: "dbt_layers",
          title: "dbt Layers and Marts",
          summary: "Staging, intermediate, marts, dashboard, monitoring, and ML-ready models.",
          status: "production-style",
          flows: ["dbt", "ml"],
          boundary: "dbt outputs inherit upstream source coverage limitations.",
          paths: ["dbt_transform/crypto_dbt", "dbt_transform/crypto_dbt/models/marts"],
          docs: [{ label: "dbt Models", href: "../dbt_models/" }]
        }
      ]
    },
    {
      id: "mlops",
      title: "ML/MLOps",
      summary: "Conservative ML workflow and optional tooling.",
      nodes: [
        {
          id: "ml_workflow",
          title: "Feature Contract, Train, Predict",
          summary: "Artifact-first ML path using an explicit feature contract.",
          status: "production-default",
          flows: ["ml"],
          boundary: "MLflow, Optuna, and Registry are optional/off by default; subset9 and microstructure features are research/manual candidates.",
          paths: ["ml/feature_list.yml", "ml/train_model.py", "ml/predict_latest.py", "ml/mlflow_registry.py"],
          docs: [{ label: "ML and MLOps", href: "../ml_mLOps/" }]
        }
      ]
    },
    {
      id: "orchestration",
      title: "Orchestration",
      summary: "Kestra workflow layer.",
      nodes: [
        {
          id: "kestra_flows",
          title: "Kestra Flows",
          summary: "Raw, dbt, ML, monitoring, quality, preview, and master orchestration flows.",
          status: "production-style",
          flows: ["batch", "streaming", "dbt", "ml", "infra"],
          boundary: "Do not deploy or execute Kestra flows for docs-only work.",
          paths: ["kestra/flows-gke", "kestra/flows"],
          docs: [{ label: "Kestra Orchestration", href: "../kestra_orchestration/" }]
        }
      ]
    },
    {
      id: "runtime",
      title: "Runtime / Infrastructure",
      summary: "GKE, Docker, identity, Terraform, and CI/CD gates.",
      nodes: [
        {
          id: "runtime_infra",
          title: "GKE / Docker / Terraform / CI/CD",
          summary: "Runtime and deployment gates for containerized platform jobs.",
          status: "infra-defined",
          flows: ["infra", "batch", "dbt", "ml"],
          boundary: "Do not build images, push registry artifacts, deploy, or run Terraform apply in docs work.",
          paths: ["k8s", "docker", "terraform/artifact_registry.tf", "terraform/kestra_iam.tf", ".github/workflows", "scripts/repo_guard.py"],
          docs: [{ label: "CI/CD Gates", href: "../ci_cd_gates/" }]
        }
      ]
    },
    {
      id: "monitoring",
      title: "Monitoring / Dashboard",
      summary: "Quality, monitoring, and presentation surfaces.",
      nodes: [
        {
          id: "monitoring_dashboard",
          title: "Monitoring / Dashboard Outputs",
          summary: "dbt monitoring and dashboard marts plus optional dashboard definitions.",
          status: "production-style",
          flows: ["batch", "dbt", "ml", "infra"],
          boundary: "Dashboard and monitoring quality depends on upstream coverage and configured targets.",
          paths: ["dbt_transform/crypto_dbt/models/marts/monitoring", "dbt_transform/crypto_dbt/models/marts/dashboard", "terraform-grafana/dashboards"],
          docs: [{ label: "dbt Models", href: "../dbt_models/" }]
        }
      ]
    }
  ],
  edges: [
    { from: "external_sources", to: "batch_collectors", flows: ["batch"], label: "collector input" },
    { from: "external_sources", to: "streaming_stack", flows: ["streaming"], label: "event input" },
    { from: "batch_collectors", to: "storage_targets", flows: ["batch", "infra"], label: "validated landing" },
    { from: "streaming_stack", to: "storage_targets", flows: ["streaming", "dbt"], label: "sink events" },
    { from: "storage_targets", to: "dbt_layers", flows: ["dbt", "batch", "streaming"], label: "warehouse inputs" },
    { from: "dbt_layers", to: "ml_workflow", flows: ["ml", "dbt"], label: "feature marts" },
    { from: "ml_workflow", to: "monitoring_dashboard", flows: ["ml", "dbt"], label: "signals and monitoring" },
    { from: "kestra_flows", to: "batch_collectors", flows: ["batch", "infra"], label: "orchestrate" },
    { from: "kestra_flows", to: "dbt_layers", flows: ["dbt", "infra"], label: "orchestrate" },
    { from: "kestra_flows", to: "ml_workflow", flows: ["ml", "infra"], label: "orchestrate" },
    { from: "runtime_infra", to: "kestra_flows", flows: ["infra"], label: "runtime support" }
  ],
  limitations: [
    "Documentation-only and static.",
    "This is not a trading bot.",
    "Other sources beyond Binance trades, ETF, macro, and funding are partial/experimental.",
    "MLflow, Optuna, Registry, subset9, and microstructure candidates are not production defaults."
  ]
};

const app = document.getElementById("app");
const tabList = document.getElementById("tabList");
const dataMode = document.getElementById("dataMode");
const serveModeNote = document.getElementById("serveModeNote");
const appShell = document.getElementById("appShell");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");

const DIRECT_MODE_NOTE = "Use repo-root preview for parent docs.";
const SIDEBAR_STORAGE_KEY = "cryptoExplorerSidebarCollapsed";

let projectMap = FALLBACK_MAP;
let architectureMap = FALLBACK_ARCHITECTURE_MAP;
const HASH_ALIASES = {
  "ai-codebase-map": "ai-map"
};
const AI_GRAPH_ASSET_CANDIDATES = [
  "understand_anything/knowledge-graph.public.json",
  "understand_anything/knowledge-graph.json"
];

function normalizeHashTabId(value = "") {
  const id = String(value).replace(/^#/, "") || "overview";
  return HASH_ALIASES[id] || id;
}

let activeTabId = normalizeHashTabId(window.location.hash);
let activeArchitectureFlowId = "all";
let selectedArchitectureNodeId = "";
let architectureDetailsHidden = false;
let aiGraphState = { status: "missing", graph: null, source: "", error: "" };
let aiGraphQuery = "";
let activeAiGraphFilter = "all";
let aiGraphLimit = 120;
let selectedAiNodeId = "";

function setSidebarCollapsed(collapsed) {
  if (!appShell || !sidebar || !sidebarToggle) return;
  appShell.classList.toggle("sidebar-collapsed", collapsed);
  sidebar.classList.toggle("is-collapsed", collapsed);
  sidebarToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  const label = sidebarToggle.querySelector(".sidebar-toggle-text");
  if (label) label.textContent = collapsed ? "Expand" : "Collapse";
  try {
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? "true" : "false");
  } catch (error) {
    // localStorage may be unavailable in some file:// previews.
  }
}

function initSidebarToggle() {
  if (!appShell || !sidebar || !sidebarToggle) return;
  let collapsed = true;
  try {
    const stored = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (stored !== null) collapsed = stored === "true";
  } catch (error) {
    collapsed = true;
  }
  setSidebarCollapsed(collapsed);
  sidebarToggle.addEventListener("click", () => {
    setSidebarCollapsed(!sidebar.classList.contains("is-collapsed"));
  });
}

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

async function loadArchitectureMap() {
  try {
    const response = await fetch("architecture_map.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return { data: await response.json(), mode: "json" };
  } catch (error) {
    return { data: FALLBACK_ARCHITECTURE_MAP, mode: "fallback", error };
  }
}

function isRepoRootMode() {
  if (window.location.protocol === "file:") return true;
  const pagePath = window.location.pathname.replace(/\/index\.html$/, "/");
  return pagePath.includes("/docs/interactive/");
}

function normalizePath(path = "") {
  return String(path).replace(/^\/+/, "");
}

function isRepoRootReadme(path) {
  return normalizePath(path) === "README.md";
}

function markdownPathToMkDocsHref(path) {
  const normalized = normalizePath(path);
  if (normalized === "README.md") return "../";
  if (normalized.startsWith("docs/") && normalized.endsWith(".md")) {
    const name = normalized.replace(/^docs\//, "").replace(/\.md$/, "");
    return `../${name}/`;
  }
  return null;
}

function isDocsPath(path) {
  const normalized = normalizePath(path);
  return Boolean(markdownPathToMkDocsHref(normalized))
    || normalized === "project_map.json"
    || normalized === "architecture_map.json"
    || normalized === "docs/interactive/project_map.json"
    || normalized === "docs/interactive/architecture_map.json";
}

function isInteractiveLocalPath(path) {
  const normalized = normalizePath(path);
  return normalized === "project_map.json" || normalized === "architecture_map.json" || normalized.startsWith("docs/interactive/");
}

function isSourcePath(path) {
  const normalized = normalizePath(path);
  return Boolean(normalized) && !normalized.startsWith("http") && !isDocsPath(normalized);
}

function repoRootHref(path) {
  const normalized = normalizePath(path);
  if (!normalized) return "#";
  if (normalized.startsWith("http")) return normalized;
  if (normalized === "project_map.json" || normalized === "docs/interactive/project_map.json") return "project_map.json";
  if (normalized === "architecture_map.json" || normalized === "docs/interactive/architecture_map.json") return "architecture_map.json";
  const mkDocsHref = markdownPathToMkDocsHref(normalized);
  if (mkDocsHref) return mkDocsHref;
  return "#";
}

function githubRepoUrl() {
  return (projectMap.metadata?.github_repo_url || FALLBACK_MAP.metadata?.github_repo_url || "").replace(/\/+$/, "");
}

function githubBranch() {
  return projectMap.metadata?.github_branch || FALLBACK_MAP.metadata?.github_branch || "main";
}

function githubPath(path) {
  return normalizePath(path).split("/").map(encodeURIComponent).join("/");
}

function isLikelyFilePath(path) {
  const lastPart = normalizePath(path).split("/").pop() || "";
  return /\.[A-Za-z0-9]+$/.test(lastPart) || lastPart === "Dockerfile" || lastPart === "Makefile" || lastPart.endsWith(".Dockerfile");
}

function resolveDocsHref(path, { allowGithubFallback = true } = {}) {
  const normalized = normalizePath(path);
  if (!normalized) return { available: false, href: "#", note: DIRECT_MODE_NOTE };
  if (normalized.startsWith("http")) return { available: true, href: normalized, external: true, kind: "GitHub" };
  if (!isDocsPath(normalized)) return { available: false, href: "#", note: "Not a docs path." };

  if (normalized === "project_map.json" || normalized === "docs/interactive/project_map.json") {
    return { available: true, href: "project_map.json", external: false, kind: "Local" };
  }

  if (normalized === "architecture_map.json" || normalized === "docs/interactive/architecture_map.json") {
    return { available: true, href: "architecture_map.json", external: false, kind: "Local" };
  }

  const mkDocsHref = markdownPathToMkDocsHref(normalized);
  if (mkDocsHref) {
    return { available: true, href: mkDocsHref, external: false, kind: "MkDocs" };
  }

  if (allowGithubFallback) {
    const repo = githubRepoUrl();
    if (repo) {
      const githubTarget = normalized === "project_map.json" ? "docs/interactive/project_map.json" : normalized;
      return {
        available: true,
        href: `${repo}/blob/${encodeURIComponent(githubBranch())}/${githubPath(githubTarget)}`,
        external: true,
        kind: "GitHub"
      };
    }
  }
  return { available: false, href: "#", note: DIRECT_MODE_NOTE };
}

function resolveSourceHref(path) {
  const normalized = normalizePath(path);
  if (!isSourcePath(normalized)) return { available: false, href: "#", note: "Not a source path." };
  const repo = githubRepoUrl();
  if (!repo) return { available: false, href: "#", note: "GitHub repository URL is not configured." };
  const mode = isLikelyFilePath(normalized) ? "blob" : "tree";
  return {
    available: true,
    href: `${repo}/${mode}/${encodeURIComponent(githubBranch())}/${githubPath(normalized)}`,
    external: true,
    kind: "GitHub"
  };
}

function resolvePathHref(path, options = {}) {
  const normalized = normalizePath(path);
  if (!normalized) return { available: false, href: "#", note: "No path configured." };
  if (normalized.startsWith("http")) return { available: true, href: normalized, external: true, kind: "External" };
  if (isDocsPath(normalized)) return resolveDocsHref(normalized, options);
  return resolveSourceHref(normalized);
}

function makePathPill(path, options = {}) {
  const normalized = normalizePath(path);
  if (!normalized) return "";
  const target = resolvePathHref(normalized, options);
  const classes = [
    "path-pill",
    options.extraClass || "",
    target.available ? "is-clickable" : "is-muted",
    target.external ? "is-external" : "is-local"
  ].filter(Boolean).join(" ");
  const dataKind = options.dataKind ? ` data-kind="${escapeHtml(options.dataKind)}"` : "";
  const linkKind = target.available ? ` data-link-kind="${escapeHtml(target.kind || (target.external ? "GitHub" : "Local"))}"` : "";
  const title = target.available
    ? `${target.external ? "Open on GitHub" : target.kind === "MkDocs" ? "Open MkDocs route" : "Open local file"}: ${normalized}`
    : (target.note || "Path is shown for reference only.");

  if (!target.available) {
    return `<span class="${classes}"${dataKind} title="${escapeHtml(title)}">${escapeHtml(normalized)}</span>`;
  }

  const targetAttrs = target.external ? ` target="_blank" rel="noopener noreferrer"` : "";
  return `<a class="${classes}"${dataKind}${linkKind} href="${escapeHtml(target.href)}"${targetAttrs} title="${escapeHtml(title)}">${escapeHtml(normalized)}</a>`;
}

function pathKind(path) {
  if (!path) return "default";
  if (path.includes("local_") || path.includes("/research") || path.includes("tests/research")) return "research";
  if (path.startsWith("terraform") || path.startsWith("helm") || path.startsWith("k8s") || path.startsWith("docker") || path.startsWith(".github")) return "infra";
  if (path.startsWith("ml/") || path.startsWith("kestra/flows-gke") || path.includes("marts/ml")) return "production";
  return "default";
}

function titleFromPath(path = "") {
  const base = path.split("/").filter(Boolean).pop() || path;
  return base
    .replace(/\.(py|sql|ya?ml|md|json)$/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function tagForPath(path = "", fallback = "Reference") {
  if (path === "README.md" || path.startsWith("docs/")) return "Docs";
  if (path.includes("/validation")) return "Validation";
  if (path.includes("iceberg") || path.includes("biglake")) return "Iceberg";
  if (path.includes("flows-gke") || path.includes(".github")) return "GKE";
  if (path.includes("feature_list") || path.includes("dbt_project") || path.includes("configs")) return "Config";
  if (path.includes("local_") || path.includes("/research")) return "Research";
  if (path.startsWith("ml/") || path.includes("marts/ml")) return "Production";
  if (path.includes("batch") || path.includes("streaming")) return "Pipeline";
  return fallback;
}

function normalizeReference(item, fallbackTag = "Reference") {
  if (typeof item === "string") {
    return {
      path: item,
      label: titleFromPath(item),
      note: "",
      tag: fallbackTag
    };
  }
  return {
    path: item.path || "",
    label: item.label || titleFromPath(item.path || ""),
    note: item.note || item.body || "",
    tag: item.tag || tagForPath(item.path || "", fallbackTag)
  };
}

function renderMeta(path, tag = "Reference") {
  return `
    <div class="meta-row">
      ${tag ? `<span class="tag">${escapeHtml(tag)}</span>` : ""}
      ${makePathPill(path)}
    </div>
  `;
}

function renderPathChip(path) {
  return makePathPill(path, { extraClass: "file-chip", dataKind: pathKind(path) });
}

function configureHeroLinks() {
  const directMode = !isRepoRootMode();
  if (serveModeNote) {
    serveModeNote.hidden = !directMode;
  }

  document.querySelectorAll("#heroActions [data-project-path]").forEach((link) => {
    const target = resolveDocsHref(link.dataset.projectPath || "", { allowGithubFallback: false });
    link.classList.toggle("is-disabled", !target.available);
    if (target.available) {
      link.href = target.href;
      link.removeAttribute("aria-disabled");
      link.removeAttribute("title");
      link.removeAttribute("tabindex");
      return;
    }
    link.removeAttribute("href");
    link.setAttribute("aria-disabled", "true");
    link.setAttribute("tabindex", "-1");
    link.setAttribute("title", target.note);
  });
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

function flowTitle(tabId) {
  const titles = {
    overview: "Visual architecture flow",
    batch: "Batch pipeline flow",
    streaming: "Streaming pipeline flow",
    dbt: "Transformation flow",
    ml: "MLOps lifecycle",
    kestra: "Orchestration flow",
    "k8s-gke": "Runtime flow",
    terraform: "Infrastructure flow",
    cicd: "Deployment gate flow",
    "repo-map": "Repository navigation flow",
    "research-production": "Production boundary flow",
    "ai-map": "Optional exploration flow"
  };
  return titles[tabId] || "Platform flow";
}

function flowKicker(tabId) {
  return tabId === "overview" ? "How the platform fits together" : "How it works";
}

function renderFlow(items = [], tabId = "") {
  if (!items.length) return "";
  const steps = items.map((item, index) => `
    <div class="flow-step">
      <span class="flow-index">${index + 1}</span>
      <strong>${escapeHtml(item)}</strong>
    </div>
  `).join("");

  return `
    <section class="section-card flow-section">
      <p class="section-kicker">${escapeHtml(flowKicker(tabId))}</p>
      <h3>${escapeHtml(flowTitle(tabId))}</h3>
      <div class="flow-wrap">
        <div class="flow">${steps}</div>
      </div>
    </section>
  `;
}

function renderCards(cards = []) {
  if (!cards.length) return "";
  return `
    <section class="section-card">
      <p class="section-kicker">Review notes</p>
      <h3>What reviewers should notice</h3>
      <div class="card-grid">
        ${cards.map((card) => `
          <article class="info-card">
            <h4>${escapeHtml(card.title)}</h4>
            <p>${escapeHtml(card.body)}</p>
            ${card.href ? `<a class="card-link" href="${escapeHtml(card.href)}" data-tab-link="${escapeHtml(card.href.replace(/^#/, ""))}">${escapeHtml(card.link_label || "Open related view")}</a>` : ""}
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderFileList(title, files = []) {
  if (!files.length) return "";
  return `
    <section class="section-card balanced-section">
      <p class="section-kicker">Where to look</p>
      <h3>${escapeHtml(title)}</h3>
      <ul class="file-list balanced-card-grid">
        ${files.map((rawFile) => {
          const file = normalizeReference(rawFile);
          return `
          <li class="file-item">
            <strong>${escapeHtml(file.label)}</strong>
            ${file.note ? `<p class="card-role">${escapeHtml(file.note)}</p>` : ""}
            ${renderMeta(file.path, file.tag)}
          </li>
        `;
        }).join("")}
      </ul>
    </section>
  `;
}

function renderDocs(docs = []) {
  if (!docs.length) return "";
  return `
    <section class="section-card read-next-compact">
      <p class="section-kicker">Related documentation</p>
      <h3>Read next</h3>
      <ul class="doc-list read-next-grid">
        ${docs.map((rawDoc) => {
          const doc = normalizeReference(rawDoc, "Docs");
          return `
          <li class="doc-item">
            <strong>${escapeHtml(doc.label)}</strong>
            ${doc.note ? `<p class="card-role">${escapeHtml(doc.note)}</p>` : ""}
            ${renderMeta(doc.path, doc.tag)}
          </li>
        `;
        }).join("")}
      </ul>
    </section>
  `;
}

function renderWarnings(warnings = []) {
  if (!warnings.length) return "";
  return `
    <section class="warning-panel">
      <p class="section-kicker">Production boundary</p>
      <h3>Boundaries and cautions</h3>
      <ul class="warning-list">
        ${warnings.map((warning) => `<li class="warning-item">${escapeHtml(warning)}</li>`).join("")}
      </ul>
    </section>
  `;
}

function renderRepoGroups(groups = []) {
  if (!groups.length) return "";
  return `
    <section class="section-card">
      <p class="section-kicker">Repository map</p>
      <h3>Repository groups</h3>
      <div class="repo-groups">
        ${groups.map((group) => `
          <article class="repo-group">
            <h4>${escapeHtml(group.name)}</h4>
            <div class="chip-row">
              ${group.paths.map((path) => renderPathChip(path)).join("")}
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
    <section class="section-card production-card">
      <p class="section-kicker">Production runtime</p>
      <h3>Production default files</h3>
      <ul class="split-list">
        ${tab.production_files.map((rawFile) => {
          const file = normalizeReference(rawFile, "Production");
          return `<li class="split-item"><strong>${escapeHtml(file.label || file.path)}</strong>${file.note ? `<p class="card-role">${escapeHtml(file.note)}</p>` : ""}${renderMeta(file.path, file.tag || "Production")}</li>`;
        }).join("")}
      </ul>
    </section>
  ` : "";
  const research = tab.research_files ? `
    <section class="section-card research-card">
      <p class="section-kicker">Research/manual only</p>
      <h3>Research/manual files</h3>
      <ul class="split-list">
        ${tab.research_files.map((rawFile) => {
          const file = normalizeReference(rawFile, "Research");
          return `<li class="split-item"><strong>${escapeHtml(file.label || file.path)}</strong>${file.note ? `<p class="card-role">${escapeHtml(file.note)}</p>` : ""}${renderMeta(file.path, file.tag || "Research")}</li>`;
        }).join("")}
      </ul>
    </section>
  ` : "";
  const commands = tab.commands ? `
    <section class="section-card optional-card">
      <p class="section-kicker">Optional helper</p>
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

function architectureNodes() {
  return (architectureMap.groups || []).flatMap((group) =>
    (group.nodes || []).map((node) => ({
      ...node,
      groupId: group.id,
      groupTitle: group.title
    }))
  );
}

function architectureNodeById(id) {
  return architectureNodes().find((node) => node.id === id);
}

function architectureFlowById(id = activeArchitectureFlowId) {
  return (architectureMap.flows || []).find((flow) => flow.id === id)
    || (architectureMap.flows || []).find((flow) => flow.id === "all")
    || { id: "all", label: "All", summary: "Show the full platform architecture." };
}

function architecturePipelineConfig() {
  if (architectureMap.pipeline?.rows?.length) {
    return architectureMap.pipeline;
  }

  const nodeIds = new Set(architectureNodes().map((node) => node.id));
  const hasFullMap = nodeIds.has("batch_collectors") && nodeIds.has("dbt_marts");
  const stages = [
    { id: "sources", label: "Sources" },
    { id: "ingestion", label: "Ingestion" },
    { id: "storage", label: "Storage" },
    { id: "transform", label: "Transform" },
    { id: "ml_outputs", label: "ML / Outputs" },
    { id: "monitoring", label: "Monitoring / Dashboard" }
  ];

  if (!hasFullMap) {
    return {
      stages,
      rows: [
        {
          id: "primary",
          label: "Primary data flow",
          summary: "Condensed fallback architecture path.",
          columns: [
            ["external_sources"],
            ["batch_collectors", "streaming_stack"].filter((id) => nodeIds.has(id)),
            ["storage_targets"].filter((id) => nodeIds.has(id)),
            ["dbt_layers"].filter((id) => nodeIds.has(id)),
            ["ml_workflow"].filter((id) => nodeIds.has(id)),
            ["monitoring_dashboard"].filter((id) => nodeIds.has(id))
          ]
        }
      ],
      control_plane: {
        label: "Operational control plane",
        summary: "Runtime and orchestration support.",
        nodes: ["kestra_flows", "runtime_infra"].filter((id) => nodeIds.has(id))
      },
      short_titles: {},
      flow_paths: {}
    };
  }

  return {
    stages,
    rows: [
      {
        id: "primary",
        label: "Primary data flow",
        summary: "Trusted batch path from sources through validation, storage, dbt, ML, and outputs.",
        columns: [
          ["external_sources"],
          ["batch_collectors", "backfill_scripts", "validation_rules"],
          ["gcs_raw", "iceberg_biglake", "bigquery_tables"],
          ["dbt_layers", "dbt_marts"],
          ["feature_contract", "ml_training", "ml_prediction"],
          ["monitoring_quality", "dashboard_outputs"]
        ]
      },
      {
        id: "streaming",
        label: "Streaming branch",
        summary: "Lower-latency freshness branch that rejoins warehouse/dbt and monitoring.",
        columns: [
          ["external_sources"],
          ["streaming_producers", "kafka_redpanda", "flink_transforms"],
          ["dead_letter", "bigquery_tables"],
          ["dbt_layers"],
          [],
          ["monitoring_quality"]
        ]
      }
    ],
    control_plane: {
      label: "Operational control plane",
      summary: "Orchestration, runtime, identity, infrastructure, and deployment gates that support the data flow.",
      nodes: ["terraform_infra", "gke_runtime", "docker_images", "workload_identity", "kestra_flows", "cicd_gates"]
    },
    short_titles: {},
    flow_paths: {}
  };
}

function architectureFlowPath(flowId = activeArchitectureFlowId) {
  if (flowId === "all") return null;
  const path = architectureFlowPathIds(flowId);
  return Array.isArray(path) ? new Set(path) : null;
}

function architectureFlowPathIds(flowId = activeArchitectureFlowId) {
  if (flowId === "all") return null;
  const path = architecturePipelineConfig().flow_paths?.[flowId];
  return Array.isArray(path) ? path : null;
}

function nodeMatchesArchitectureFlow(node, flowId = activeArchitectureFlowId) {
  if (flowId === "all") return true;
  const path = architectureFlowPath(flowId);
  if (path) return path.has(node.id);
  return (node.flows || []).includes(flowId);
}

function edgeMatchesArchitectureFlow(edge, flowId = activeArchitectureFlowId) {
  if (flowId === "all") return true;
  const path = architectureFlowPath(flowId);
  if (path) return path.has(edge.from) && path.has(edge.to) && (edge.flows || []).includes(flowId);
  return (edge.flows || []).includes(flowId);
}

function architectureNodeCardTitle(node) {
  return node.shortTitle || architecturePipelineConfig().short_titles?.[node.id] || node.title;
}

function architectureNodeIdsFromEdges(nodeId, direction = "upstream") {
  const edges = architectureMap.edges || [];
  const related = direction === "upstream"
    ? edges.filter((edge) => edge.to === nodeId).map((edge) => edge.from)
    : edges.filter((edge) => edge.from === nodeId).map((edge) => edge.to);
  return [...new Set(related)];
}

function currentArchitectureNode() {
  const nodes = architectureNodes();
  const selected = architectureNodeById(selectedArchitectureNodeId);
  if (selected && nodeMatchesArchitectureFlow(selected)) {
    return selected;
  }
  return nodes.find((node) => nodeMatchesArchitectureFlow(node)) || nodes[0] || null;
}

function architectureStatusClass(status = "") {
  return normalizePath(status)
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase() || "default";
}

function renderStatusBadge(status = "reference") {
  return `<span class="status-badge status-${escapeHtml(architectureStatusClass(status))}">${escapeHtml(status)}</span>`;
}

function renderFlowBadges(flows = []) {
  if (!flows.length) return "";
  return flows
    .map((flowId) => {
      const flow = architectureFlowById(flowId);
      return `<span class="flow-badge">${escapeHtml(flow.label || flowId)}</span>`;
    })
    .join("");
}

function renderArchitectureDocs(docs = []) {
  if (!docs.length) return "";
  return `
    <div class="architecture-detail-group">
      <h4>Open docs</h4>
      <div class="architecture-doc-links">
        ${docs.map((doc) => {
          const rawHref = doc.href || resolveDocsHref(doc.path || "", { allowGithubFallback: false }).href;
          const href = rawHref || "#";
          const isExternal = href.startsWith("http");
          const targetAttrs = isExternal ? ` target="_blank" rel="noopener noreferrer"` : "";
          return `<a href="${escapeHtml(href)}"${targetAttrs}>${escapeHtml(doc.label || doc.path || href)}</a>`;
        }).join("")}
      </div>
    </div>
  `;
}

function renderArchitecturePaths(paths = []) {
  if (!paths.length) return "";
  return `
    <div class="architecture-detail-group">
      <h4>Open source path</h4>
      <div class="architecture-paths">
        ${paths.map((path) => makePathPill(path)).join("")}
      </div>
    </div>
  `;
}

function renderArchitectureReferenceAssets() {
  const assets = architectureMap.reference_assets || [];
  const jsonLinks = [
    { label: "architecture_map.json", path: "architecture_map.json" },
    { label: "project_map.json", path: "project_map.json" }
  ];
  if (!assets.length) {
    return `
      <details class="compact-reference">
        <summary>Reference assets and data source</summary>
        <div class="architecture-paths">
          ${jsonLinks.map((asset) => makePathPill(asset.path)).join("")}
        </div>
      </details>
    `;
  }
  return `
    <details class="compact-reference">
      <summary>Reference assets and data source</summary>
      <p>draw.io and SVG exports are reference wireframes only. The main map is rendered from curated JSON as HTML/CSS/JS.</p>
      <div class="architecture-paths">
        ${jsonLinks.map((asset) => makePathPill(asset.path)).join("")}
        ${assets.map((asset) => makePathPill(asset.path)).join("")}
      </div>
    </details>
  `;
}

function renderArchitectureRelatedNodes(node, direction = "upstream") {
  const ids = architectureNodeIdsFromEdges(node.id, direction);
  if (!ids.length) {
    return `<span class="empty-connection">None in the curated edge map.</span>`;
  }
  return ids.map((id) => {
    const related = architectureNodeById(id);
    const label = related ? architectureNodeCardTitle(related) : id;
    return `
      <button class="mini-node-link" type="button" data-architecture-node-id="${escapeHtml(id)}">
        ${escapeHtml(label)}
      </button>
    `;
  }).join("");
}

function renderArchitectureDetail(node) {
  if (!node) {
    return `
      <aside class="architecture-detail-panel">
        <p class="section-kicker">Node details</p>
        <h3>Select a node</h3>
        <p class="panel-summary">No architecture nodes are available.</p>
      </aside>
    `;
  }

  const relatedEdges = (architectureMap.edges || [])
    .filter((edge) => edgeMatchesArchitectureFlow(edge) && (edge.from === node.id || edge.to === node.id))
    .slice(0, 6);

  return `
    <aside class="architecture-detail-panel" aria-label="Selected architecture node details">
      <p class="section-kicker">Selected node</p>
      <div class="architecture-detail-heading">
        <div>
          <h3>${escapeHtml(node.title)}</h3>
          <p>${escapeHtml(node.summary || "")}</p>
        </div>
        ${renderStatusBadge(node.status || "reference")}
      </div>
      <div class="architecture-flow-tags">${renderFlowBadges(node.flows || [])}</div>
      <div class="architecture-detail-grid">
        <div class="architecture-detail-group">
          <h4>What it does</h4>
          <p>${escapeHtml(node.what_it_does || node.summary || "Curated project architecture component.")}</p>
        </div>
        <div class="architecture-detail-group">
          <h4>Why it matters</h4>
          <p>${escapeHtml(node.why_it_matters || "It helps reviewers understand the project boundary and data flow.")}</p>
        </div>
        <div class="architecture-detail-group">
          <h4>Production / research boundary</h4>
          <p>${escapeHtml(node.boundary || "Inspect this component through the docs before running any operational command.")}</p>
        </div>
        <div class="architecture-detail-group">
          <h4>Where it lives</h4>
          <p>${escapeHtml(node.where_it_lives || `Grouped under ${node.groupTitle || "Architecture"}.`)}</p>
        </div>
      </div>
      ${renderArchitecturePaths(node.paths || [])}
      ${renderArchitectureDocs(node.docs || [])}
      <div class="upstream-downstream">
        <div class="architecture-detail-group">
          <h4>Upstream</h4>
          <div class="architecture-mini-edges">
            ${renderArchitectureRelatedNodes(node, "upstream")}
          </div>
        </div>
        <div class="architecture-detail-group">
          <h4>Downstream</h4>
          <div class="architecture-mini-edges">
            ${renderArchitectureRelatedNodes(node, "downstream")}
          </div>
        </div>
      </div>
      ${relatedEdges.length ? `
        <div class="architecture-detail-group">
          <h4>Connected flow</h4>
          <div class="architecture-mini-edges">
            ${relatedEdges.map((edge) => `
              <span>${escapeHtml((architectureNodeById(edge.from) || {}).title || edge.from)} <strong>&rarr;</strong> ${escapeHtml((architectureNodeById(edge.to) || {}).title || edge.to)}</span>
            `).join("")}
          </div>
        </div>
      ` : ""}
    </aside>
  `;
}

function renderArchitectureEdges(selectedNode) {
  const nodesById = new Map(architectureNodes().map((node) => [node.id, node]));
  const edges = architectureMap.edges || [];
  if (!edges.length) return "";
  return `
    <div class="architecture-edge-section" aria-label="Architecture connections">
      <p class="section-kicker">Flow connections</p>
      <div class="architecture-edge-list">
        ${edges.map((edge) => {
          const flowMatch = edgeMatchesArchitectureFlow(edge);
          const connected = selectedNode && (edge.from === selectedNode.id || edge.to === selectedNode.id);
          const classes = [
            "architecture-edge",
            flowMatch ? "is-visible" : "is-dimmed",
            connected && flowMatch ? "is-connected" : ""
          ].filter(Boolean).join(" ");
          const fromTitle = (nodesById.get(edge.from) || {}).title || edge.from;
          const toTitle = (nodesById.get(edge.to) || {}).title || edge.to;
          return `
            <div class="${classes}">
              <span>${escapeHtml(fromTitle)}</span>
              <strong>&rarr;</strong>
              <span>${escapeHtml(toTitle)}</span>
              ${edge.label ? `<em>${escapeHtml(edge.label)}</em>` : ""}
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function architectureNodeSummary(node) {
  const summary = node.canvasSummary || node.summary || "";
  if (summary.length <= 92) return summary;
  return `${summary.slice(0, 89).trim()}...`;
}

function renderPipelineNode(nodeId, options = {}) {
  const node = architectureNodeById(nodeId);
  if (!node) return "";
  const selectedNode = currentArchitectureNode();
  const flowMatch = nodeMatchesArchitectureFlow(node);
  const active = selectedNode && selectedNode.id === node.id;
  const classes = [
    "pipeline-node",
    options.control ? "is-control-node" : "",
    flowMatch ? "is-visible" : "is-dimmed",
    active ? "is-active" : ""
  ].filter(Boolean).join(" ");

  return `
    <button
      class="${classes}"
      type="button"
      data-architecture-node-id="${escapeHtml(node.id)}"
      aria-pressed="${active ? "true" : "false"}"
    >
      <span class="pipeline-node-title">${escapeHtml(architectureNodeCardTitle(node))}</span>
      <span class="pipeline-node-summary">${escapeHtml(architectureNodeSummary(node))}</span>
      <span class="pipeline-node-footer">
        ${renderStatusBadge(node.status || "reference")}
        <span class="flow-chip-row">${renderFlowBadges(node.flows || [])}</span>
      </span>
    </button>
  `;
}

function renderPipelineStage(ids = []) {
  const nodes = ids.map((id) => renderPipelineNode(id)).filter(Boolean);
  return `
    <div class="pipeline-stage ${nodes.length ? "" : "is-empty"}">
      ${nodes.length ? nodes.join("") : `<span class="pipeline-empty">No node in this stage</span>`}
    </div>
  `;
}

function renderPipelineCanvas() {
  const pipeline = architecturePipelineConfig();
  const stages = pipeline.stages || [];
  const rows = pipeline.rows || [];
  if (!stages.length || !rows.length) return "";

  return `
    <div class="pipeline-map" aria-label="Pipeline architecture canvas">
      <div class="pipeline-stage-header-row">
        <span class="pipeline-row-spacer"></span>
        ${stages.map((stage) => `<span>${escapeHtml(stage.label)}</span>`).join("")}
      </div>
      ${rows.map((row) => `
        <section class="pipeline-stage-row pipeline-row-${escapeHtml(row.id || "default")}">
          <div class="pipeline-row-label">
            <strong>${escapeHtml(row.label || "Pipeline row")}</strong>
            ${row.summary ? `<span>${escapeHtml(row.summary)}</span>` : ""}
          </div>
          ${stages.map((stage, index) => renderPipelineStage((row.columns || [])[index] || [])).join("")}
        </section>
      `).join("")}
    </div>
  `;
}

function renderControlPlane() {
  const control = architecturePipelineConfig().control_plane || {};
  const nodeIds = control.nodes || [];
  if (!nodeIds.length) return "";

  return `
    <section class="control-plane" aria-label="Operational control plane">
      <div class="control-plane-head">
        <div>
          <p class="section-kicker">Support / control plane</p>
          <h4>${escapeHtml(control.label || "Operational control plane")}</h4>
        </div>
        ${control.summary ? `<p>${escapeHtml(control.summary)}</p>` : ""}
      </div>
      <div class="control-plane-rail">
        ${nodeIds.map((id, index) => `
          ${renderPipelineNode(id, { control: true })}
          ${index < nodeIds.length - 1 ? `<span class="pipeline-arrow" aria-hidden="true">&rarr;</span>` : ""}
        `).join("")}
      </div>
    </section>
  `;
}

function renderArchitectureMap() {
  if (!architectureMap || !(architectureMap.groups || []).length) return "";
  const activeFlow = architectureFlowById();
  const selectedNode = currentArchitectureNode();
  const flowButtons = (architectureMap.flows || []).map((flow) => `
    <button
      class="flow-filter ${flow.id === activeArchitectureFlowId ? "is-active" : ""}"
      type="button"
      data-architecture-flow="${escapeHtml(flow.id)}"
      aria-pressed="${flow.id === activeArchitectureFlowId ? "true" : "false"}"
    >
      ${escapeHtml(flow.label)}
    </button>
  `).join("");

  return `
    <section class="section-card architecture-map" id="architectureMap">
      <div class="architecture-map-head">
        <div>
          <p class="section-kicker">Interactive architecture map</p>
          <h3>${escapeHtml(architectureMap.metadata?.title || "Interactive Architecture Map")}</h3>
          <p class="panel-summary">${escapeHtml(architectureMap.metadata?.summary || "")}</p>
        </div>
      </div>
      <div class="architecture-toolbar" role="group" aria-label="Filter architecture map by flow">
        ${flowButtons}
        <button class="detail-toggle" type="button" data-detail-toggle aria-pressed="${architectureDetailsHidden ? "true" : "false"}">
          ${architectureDetailsHidden ? "Show details" : "Hide details"}
        </button>
      </div>
      <div class="architecture-flow-summary">
        <strong>${escapeHtml(activeFlow.label)}</strong>
        <span>${escapeHtml(activeFlow.summary || "")}</span>
      </div>
      <div class="architecture-layout ${architectureDetailsHidden ? "is-detail-hidden" : ""}">
        <div class="pipeline-workspace">
          <div class="pipeline-scroll">
            ${renderPipelineCanvas()}
          </div>
          ${renderControlPlane()}
          ${architectureMap.limitations?.length ? `
            <div class="architecture-limitations">
              ${architectureMap.limitations.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
            </div>
          ` : ""}
          ${renderArchitectureReferenceAssets()}
        </div>
        ${architectureDetailsHidden ? "" : renderArchitectureDetail(selectedNode)}
      </div>
    </section>
  `;
}

function firstPresent(source, fields = []) {
  if (!source || typeof source !== "object") return "";
  for (const field of fields) {
    const value = source[field];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return "";
}

function arrayValue(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return [value].filter(Boolean);
}

function graphNodesFromRaw(raw) {
  return arrayValue(raw?.nodes || raw?.graph?.nodes || raw?.data?.nodes);
}

function graphEdgesFromRaw(raw) {
  return arrayValue(raw?.edges || raw?.graph?.edges || raw?.data?.edges);
}

function normalizeAiNode(rawNode, index) {
  const rawId = firstPresent(rawNode, ["id", "nodeId", "path", "name", "label"]) || `node-${index + 1}`;
  const path = normalizePath(firstPresent(rawNode, ["path", "filePath", "relativePath", "sourcePath", "repoPath"]));
  const title = firstPresent(rawNode, ["title", "name", "label", "path"]) || path || rawId;
  const summary = firstPresent(rawNode, ["summary", "description", "plainEnglishSummary", "explanation", "purpose", "body"]) || "";
  const layer = firstPresent(rawNode, ["layer", "domain", "category", "fileCategory", "group"]) || "";
  const type = firstPresent(rawNode, ["type", "kind", "language", "nodeType"]) || layer || "reference";
  const tags = [
    ...arrayValue(rawNode.tags),
    ...arrayValue(rawNode.frameworks),
    ...arrayValue(rawNode.domains),
    layer,
    type
  ].filter(Boolean).map(String);

  return {
    id: String(rawId),
    title: String(title),
    path,
    summary: String(summary),
    layer: String(layer || type || "Uncategorized"),
    type: String(type || layer || "reference"),
    tags: [...new Set(tags)],
    raw: rawNode
  };
}

function normalizeAiEdge(rawEdge, index) {
  const from = firstPresent(rawEdge, ["source", "from", "sourceId", "sourceNodeId"]);
  const to = firstPresent(rawEdge, ["target", "to", "targetId", "targetNodeId"]);
  const label = firstPresent(rawEdge, ["label", "type", "relationship", "kind"]) || "related";
  return {
    id: String(firstPresent(rawEdge, ["id"]) || `edge-${index + 1}`),
    from: from !== undefined && from !== null ? String(from) : "",
    to: to !== undefined && to !== null ? String(to) : "",
    label: String(label)
  };
}

function normalizeAiGraph(raw, source) {
  const nodes = graphNodesFromRaw(raw).map(normalizeAiNode);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const pathToId = new Map(nodes.filter((node) => node.path).map((node) => [node.path, node.id]));
  const edges = graphEdgesFromRaw(raw)
    .map(normalizeAiEdge)
    .map((edge) => ({
      ...edge,
      from: nodeIds.has(edge.from) ? edge.from : (pathToId.get(normalizePath(edge.from)) || edge.from),
      to: nodeIds.has(edge.to) ? edge.to : (pathToId.get(normalizePath(edge.to)) || edge.to)
    }))
    .filter((edge) => edge.from && edge.to);

  if (!nodes.length) {
    throw new Error("Graph JSON parsed, but no nodes were found under nodes, graph.nodes, or data.nodes.");
  }

  const meta = raw.metadata || raw.meta || raw.graph?.metadata || raw.data?.metadata || {};
  return {
    source,
    nodes,
    edges,
    generatedAt: firstPresent(meta, ["generatedAt", "generated_at", "createdAt", "created_at"]) || firstPresent(raw, ["generatedAt", "generated_at"]),
    raw
  };
}

async function loadAiGraphAsset() {
  let lastFetchError = "";
  for (const source of AI_GRAPH_ASSET_CANDIDATES) {
    try {
      const response = await fetch(source, { cache: "no-store" });
      if (!response.ok) continue;
      try {
        const raw = await response.json();
        return { status: "loaded", graph: normalizeAiGraph(raw, source), source, error: "" };
      } catch (error) {
        return { status: "error", graph: null, source, error: error.message || String(error) };
      }
    } catch (error) {
      lastFetchError = error.message || String(error);
    }
  }
  return { status: "missing", graph: null, source: "", error: lastFetchError || "No published graph asset found." };
}

function aiNodeSearchText(node) {
  return [node.title, node.path, node.summary, node.layer, node.type, ...(node.tags || [])]
    .join(" ")
    .toLowerCase();
}

function aiNodeKindText(node) {
  return aiNodeSearchText(node);
}

function nodeMatchesAiFixedFilter(node, filter) {
  const text = aiNodeKindText(node);
  const path = node.path || "";
  if (filter === "all") return true;
  if (filter === "code") return text.includes("code") || /\.(py|js|ts|sql|sh|mjs|tsx|jsx)$/i.test(path);
  if (filter === "config") return text.includes("config") || /\.(ya?ml|json|toml|tfvars|ini|cfg)$/i.test(path) || /(^|\/)(Dockerfile|Makefile)$/i.test(path);
  if (filter === "docs") return text.includes("docs") || path.startsWith("docs/") || path === "README.md" || /\.md$/i.test(path);
  if (filter === "infra") return text.includes("infra") || text.includes("terraform") || text.includes("kubernetes") || /^(terraform|terraform-bootstrap|terraform-grafana|k8s|helm|docker|\.github)\b/.test(path);
  if (filter === "data") return text.includes("data") || text.includes("dbt") || text.includes("bigquery") || text.includes("gcs") || path.startsWith("dbt_transform/") || path.includes("/batch/");
  if (filter === "ml") return text.includes("ml") || text.includes("machine learning") || path.startsWith("ml/") || path.includes("/marts/ml/");
  return false;
}

function nodeMatchesAiFilter(node) {
  const query = aiGraphQuery.trim().toLowerCase();
  if (query && !aiNodeSearchText(node).includes(query)) return false;
  if (nodeMatchesAiFixedFilter(node, activeAiGraphFilter)) return true;
  const layerType = [node.layer, node.type, ...(node.tags || [])]
    .map((value) => String(value).toLowerCase())
    .filter(Boolean);
  return layerType.includes(activeAiGraphFilter);
}

function aiGraphFilterOptions(graph) {
  const fixed = [
    { id: "all", label: "All" },
    { id: "code", label: "Code" },
    { id: "config", label: "Config" },
    { id: "docs", label: "Docs" },
    { id: "infra", label: "Infra" },
    { id: "data", label: "Data" },
    { id: "ml", label: "ML" }
  ];
  const seen = new Set(fixed.map((item) => item.id));
  const dynamic = [...new Set((graph.nodes || []).flatMap((node) => [node.layer, node.type]).filter(Boolean))]
    .map((label) => ({ id: String(label).toLowerCase(), label: String(label) }))
    .filter((item) => !seen.has(item.id))
    .slice(0, 8);
  return [...fixed, ...dynamic];
}

function selectedAiNode(graph, filteredNodes) {
  const selected = graph.nodes.find((node) => node.id === selectedAiNodeId);
  if (selected && filteredNodes.some((node) => node.id === selected.id)) return selected;
  return filteredNodes[0] || graph.nodes[0] || null;
}

function aiRelatedEdges(graph, node) {
  if (!node) return [];
  return (graph.edges || []).filter((edge) => edge.from === node.id || edge.to === node.id).slice(0, 12);
}

function aiNodeById(graph, id) {
  return (graph.nodes || []).find((node) => node.id === id);
}

function renderAiGraphDetail(graph, node) {
  if (!node) {
    return `
      <aside class="ai-graph-detail">
        <p class="section-kicker">Node detail</p>
        <h3>Select a node</h3>
        <p>No graph nodes match the current search/filter.</p>
      </aside>
    `;
  }
  const edges = aiRelatedEdges(graph, node);
  return `
    <aside class="ai-graph-detail">
      <p class="section-kicker">Selected node</p>
      <h3>${escapeHtml(node.title)}</h3>
      <div class="ai-node-meta">
        <span>${escapeHtml(node.layer || "Uncategorized")}</span>
        <span>${escapeHtml(node.type || "reference")}</span>
      </div>
      ${node.summary ? `<p>${escapeHtml(node.summary)}</p>` : `<p>No summary field was present for this node.</p>`}
      ${node.path ? `<div class="architecture-paths">${makePathPill(node.path)}</div>` : ""}
      <div class="ai-graph-related">
        <h4>Related nodes</h4>
        ${edges.length ? edges.map((edge) => {
          const relatedId = edge.from === node.id ? edge.to : edge.from;
          const related = aiNodeById(graph, relatedId);
          return `
            <button type="button" class="mini-node-link" data-ai-node-id="${escapeHtml(relatedId)}">
              ${escapeHtml(edge.label)}: ${escapeHtml(related?.title || relatedId)}
            </button>
          `;
        }).join("") : `<span class="empty-connection">No direct edges in the published graph.</span>`}
      </div>
    </aside>
  `;
}

function renderAiGraphPanel() {
  if (aiGraphState.status === "missing") {
    return `
      <section class="section-card ai-graph-panel">
        <div class="ai-graph-warning">
          <p class="section-kicker">AI Codebase Map</p>
          <h3>No published graph asset found yet.</h3>
          <p>Run <code>/understand --language en</code>, review the graph, then publish the sanitized JSON under <code>docs/interactive/understand_anything/</code>.</p>
        </div>
      </section>
    `;
  }

  if (aiGraphState.status === "error") {
    return `
      <section class="section-card ai-graph-panel">
        <div class="ai-graph-warning">
          <p class="section-kicker">AI Codebase Map</p>
          <h3>Graph asset could not be loaded.</h3>
          <p>${escapeHtml(aiGraphState.error || "Unknown graph parsing error.")}</p>
        </div>
      </section>
    `;
  }

  const graph = aiGraphState.graph;
  const filteredNodes = graph.nodes.filter(nodeMatchesAiFilter);
  const visibleNodes = filteredNodes.slice(0, aiGraphLimit);
  const currentNode = selectedAiNode(graph, filteredNodes);
  const layerCount = new Set(graph.nodes.map((node) => node.layer || node.type).filter(Boolean)).size;
  const filters = aiGraphFilterOptions(graph);

  return `
    <section class="section-card ai-graph-panel" id="aiGraphPanel">
      <div class="ai-graph-head">
        <div>
          <p class="section-kicker">AI Codebase Map</p>
          <h3>Generated by Understand-Anything and published as a static docs asset when available.</h3>
          <p class="panel-summary">Loaded <code>${escapeHtml(graph.source)}</code>. The curated architecture map remains the primary guide; this graph is a secondary deep-dive.</p>
        </div>
      </div>
      <div class="ai-graph-stats">
        <span><strong>${graph.nodes.length}</strong> nodes</span>
        <span><strong>${graph.edges.length}</strong> edges</span>
        <span><strong>${layerCount}</strong> layers/types</span>
        ${graph.generatedAt ? `<span>Generated ${escapeHtml(graph.generatedAt)}</span>` : ""}
      </div>
      <div class="ai-graph-toolbar">
        <label>
          <span>Search nodes</span>
          <input type="search" data-ai-search value="${escapeHtml(aiGraphQuery)}" placeholder="Search name, path, summary..." />
        </label>
        <div class="ai-filter-chips" role="group" aria-label="Filter AI graph nodes">
          ${filters.map((filter) => `
            <button type="button" class="flow-filter ${filter.id === activeAiGraphFilter ? "is-active" : ""}" data-ai-filter="${escapeHtml(filter.id)}" aria-pressed="${filter.id === activeAiGraphFilter ? "true" : "false"}">
              ${escapeHtml(filter.label)}
            </button>
          `).join("")}
        </div>
      </div>
      <div class="ai-graph-layout">
        <div>
          ${filteredNodes.length ? `
            <div class="ai-graph-grid">
              ${visibleNodes.map((node) => `
                <button type="button" class="ai-graph-node ${currentNode?.id === node.id ? "is-active" : ""}" data-ai-node-id="${escapeHtml(node.id)}">
                  <span class="ai-node-title">${escapeHtml(node.title)}</span>
                  <span class="ai-node-path">${escapeHtml(node.path || node.id)}</span>
                  <span class="ai-node-summary">${escapeHtml(node.summary || "No summary available.")}</span>
                  <span class="ai-node-meta"><em>${escapeHtml(node.layer)}</em><em>${escapeHtml(node.type)}</em></span>
                </button>
              `).join("")}
            </div>
            ${filteredNodes.length > visibleNodes.length ? `
              <button type="button" class="show-more-button" data-ai-show-more>Show more (${filteredNodes.length - visibleNodes.length} remaining)</button>
            ` : ""}
          ` : `
            <div class="ai-graph-empty">
              <h3>No nodes match the current search/filter.</h3>
              <p>Try clearing the search box or switching back to All.</p>
            </div>
          `}
        </div>
        ${renderAiGraphDetail(graph, currentNode)}
      </div>
    </section>
  `;
}

function wireAiGraphInteractions() {
  const root = document.getElementById("aiGraphPanel");
  if (!root) return;

  const search = root.querySelector("[data-ai-search]");
  if (search) {
    search.addEventListener("input", () => {
      aiGraphQuery = search.value || "";
      aiGraphLimit = 120;
      renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId) || projectMap.tabs[0]);
    });
  }

  root.querySelectorAll("[data-ai-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      activeAiGraphFilter = button.dataset.aiFilter || "all";
      aiGraphLimit = 120;
      renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId) || projectMap.tabs[0]);
    });
  });

  root.querySelectorAll("[data-ai-node-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectedAiNodeId = button.dataset.aiNodeId || "";
      renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId) || projectMap.tabs[0]);
    });
  });

  root.querySelectorAll("[data-ai-show-more]").forEach((button) => {
    button.addEventListener("click", () => {
      aiGraphLimit += 120;
      renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId) || projectMap.tabs[0]);
    });
  });
}

function wireArchitectureInteractions() {
  const root = document.getElementById("architectureMap");
  if (!root) return;

  root.querySelectorAll("[data-architecture-flow]").forEach((button) => {
    button.addEventListener("click", () => {
      activeArchitectureFlowId = button.dataset.architectureFlow || "all";
      const selected = architectureNodeById(selectedArchitectureNodeId);
      if (!selected || !nodeMatchesArchitectureFlow(selected)) {
        const preferredPath = architectureFlowPathIds(activeArchitectureFlowId) || [];
        selectedArchitectureNodeId = preferredPath.find((id) => architectureNodeById(id))
          || (architectureNodes().find((node) => nodeMatchesArchitectureFlow(node)) || {}).id
          || "";
      }
      renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId) || projectMap.tabs[0]);
    });
  });

  root.querySelectorAll("[data-architecture-node-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectedArchitectureNodeId = button.dataset.architectureNodeId || "";
      architectureDetailsHidden = false;
      renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId) || projectMap.tabs[0]);
    });
  });

  root.querySelectorAll("[data-detail-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      architectureDetailsHidden = !architectureDetailsHidden;
      renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId) || projectMap.tabs[0]);
    });
  });
}

function renderCoverage() {
  const coverage = projectMap.coverage;
  if (!coverage) return "";
  const coverageNotes = {
    "Binance trades": "Trusted market trade history for core price and hourly marts.",
    "ETF indicators": "Reliable daily external market context.",
    "Macro indicators": "Daily macro context for broader market regime features.",
    "Funding data": "Derivatives funding context with reliable historical coverage.",
    "Stablecoin supply": "Useful context, but not yet strongest 5-year production coverage.",
    "Liquidation heatmap": "Risk context that remains partial or experimental.",
    "Options": "Options risk context that is not fully live-ready.",
    "Exchange reserves": "Reserve context with partial coverage boundaries.",
    "Reddit and Telegram sentiment": "Experimental sentiment inputs for research exploration.",
    "Live taker-pressure and streaming context": "Freshness-oriented signals, not primary trusted history."
  };
  const coverageCard = (item, tone = "strong") => `
    <li class="coverage-card coverage-${tone}">
      <strong>${escapeHtml(item)}</strong>
      <span>${escapeHtml(coverageNotes[item] || (tone === "strong" ? "Reliable source in the strongest historical coverage set." : "Useful context, but partial or experimental today."))}</span>
    </li>
  `;
  return `
    <section class="section-card coverage-section">
      <div class="coverage-head">
        <p class="section-kicker">Data confidence</p>
        <h3>Current data coverage</h3>
        <p class="panel-summary">${escapeHtml(coverage.summary)}</p>
      </div>
      <div class="coverage-columns">
        <div class="coverage-group">
          <h4>Strongest 5-year backfill</h4>
          <ul class="coverage-card-grid">
            ${coverage.strongest_backfill.map((item) => coverageCard(item, "strong")).join("")}
          </ul>
        </div>
        <div class="coverage-group">
          <h4>Partial / experimental</h4>
          <ul class="coverage-card-grid">
            ${coverage.partial_or_experimental.map((item) => coverageCard(item, "partial")).join("")}
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
        <div>
          <p class="eyebrow">${escapeHtml(tab.eyebrow)}</p>
          <h2>${escapeHtml(tab.title)}</h2>
        </div>
        <p class="panel-summary">${escapeHtml(tab.summary)}</p>
        ${renderPills(tab.badges)}
      </section>
      ${tab.id === "overview" ? renderArchitectureMap() : ""}
      ${renderFlow(tab.flow, tab.id)}
      ${renderCards(tab.cards)}
      ${tab.id === "ai-map" ? renderAiGraphPanel() : ""}
      ${tab.id === "overview" ? renderCoverage() : ""}
      ${renderRepoGroups(tab.repo_groups)}
      ${renderSplitLists(tab)}
      ${renderFileList("Important files", tab.important_files)}
      ${renderDocs(tab.docs)}
      ${renderWarnings(tab.warnings)}
    </article>
  `;
  if (tab.id === "overview") {
    wireArchitectureInteractions();
  }
  if (tab.id === "ai-map") {
    wireAiGraphInteractions();
  }
  app.querySelectorAll("[data-tab-link]").forEach((link) => {
    link.addEventListener("click", (event) => {
      const targetId = normalizeHashTabId(link.dataset.tabLink || "");
      const targetTab = projectMap.tabs.find((candidate) => candidate.id === targetId);
      if (!targetTab) return;
      event.preventDefault();
      activeTabId = targetId;
      window.location.hash = link.dataset.tabLink || targetId;
      renderTabs();
      renderTab(targetTab);
    });
  });
}

function renderTabs() {
  tabList.innerHTML = projectMap.tabs.map((tab, index) => `
    <button
      class="tab-button"
      type="button"
      role="tab"
      id="tab-${tab.id}"
      aria-controls="panel-${tab.id}"
      aria-selected="${tab.id === activeTabId ? "true" : "false"}"
      data-tab-id="${tab.id}"
      title="${escapeHtml(tab.label)}"
    >
      <span class="tab-number">${String(index + 1).padStart(2, "0")}</span>
      <span class="tab-label">${escapeHtml(tab.label)}</span>
    </button>
  `).join("");

  tabList.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      activeTabId = button.dataset.tabId;
      window.location.hash = activeTabId === "ai-map" ? "ai-codebase-map" : activeTabId;
      renderTabs();
      renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId) || projectMap.tabs[0]);
    });
  });
}

async function init() {
  initSidebarToggle();
  configureHeroLinks();
  const [result, architectureResult, aiGraphResult] = await Promise.all([
    loadProjectMap(),
    loadArchitectureMap(),
    loadAiGraphAsset()
  ]);
  projectMap = result.data;
  architectureMap = architectureResult.data;
  aiGraphState = aiGraphResult;
  const fallbackMessages = [];
  if (result.mode === "fallback") {
    fallbackMessages.push("Browser blocked project_map.json fetch, so the bundled static fallback is being used.");
  }
  if (architectureResult.mode === "fallback") {
    fallbackMessages.push("Browser blocked architecture_map.json fetch, so the bundled architecture fallback is being used.");
  }
  if (fallbackMessages.length) {
    dataMode.hidden = false;
    dataMode.textContent = `${fallbackMessages.join(" ")} The JSON files are still available next to this page when served through a static file server.`;
  }
  configureHeroLinks();
  if (!projectMap.tabs.some((tab) => tab.id === activeTabId)) {
    activeTabId = projectMap.tabs[0].id;
  }
  renderTabs();
  renderTab(projectMap.tabs.find((tab) => tab.id === activeTabId));
}

init();
