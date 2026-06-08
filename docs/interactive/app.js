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
      "label": "Optional AI Codebase Map",
      "eyebrow": "Optional Understand-Anything layer",
      "title": "Optional AI Codebase Map",
      "summary": "Optional future exploration layer; not required to run, review, or understand the project.",
      "badges": [
        "Optional",
        "Not required",
        "Placeholder only"
      ],
      "flow": [
        "README / docs",
        "Static explorer",
        "Optional scan",
        "Optional dashboard",
        "Future graph"
      ],
      "cards": [
        {
          "title": "What It Is",
          "body": "Understand-Anything is optional and is not part of the project runtime, pipeline, training workflow, or deployment process."
        },
        {
          "title": "How To Generate Later",
          "body": "Run /understand --language en, then /understand-dashboard in an environment where Understand-Anything is available."
        },
        {
          "title": "Current State",
          "body": "This repo may not include .understand-anything/knowledge-graph.json. If generated later, it can become an additional exploration layer."
        },
        {
          "title": "Primary Docs Remain",
          "body": "README.md, docs/architecture.md, docs/repository_map.md, and this static explorer remain the primary documentation."
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
        "No parser for .understand-anything/knowledge-graph.json is implemented in this phase.",
        "Do not require Understand-Anything for normal project operation."
      ]
    }
  ]
};

const app = document.getElementById("app");
const tabList = document.getElementById("tabList");
const dataMode = document.getElementById("dataMode");
const serveModeNote = document.getElementById("serveModeNote");

const DIRECT_MODE_NOTE = "Use repo-root preview for parent docs.";

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

function isDocsPath(path) {
  const normalized = normalizePath(path);
  return isRepoRootReadme(normalized) || normalized === "project_map.json" || normalized.startsWith("docs/");
}

function isInteractiveLocalPath(path) {
  const normalized = normalizePath(path);
  return normalized === "project_map.json" || normalized.startsWith("docs/interactive/");
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
  if (normalized === "README.md") return "../../README.md";
  if (normalized.startsWith("docs/interactive/")) return normalized.replace("docs/interactive/", "");
  if (normalized.startsWith("docs/")) return `../${normalized.replace("docs/", "")}`;
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

  if (isRepoRootMode() || isInteractiveLocalPath(normalized)) {
    return { available: true, href: repoRootHref(normalized), external: false, kind: "Local" };
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
    ? `${target.external ? "Open on GitHub" : "Open local file"}: ${normalized}`
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
      <p class="section-kicker">Where to look</p>
      <h3>${escapeHtml(title)}</h3>
      <ul class="file-list">
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
    <section class="section-card">
      <p class="section-kicker">Related documentation</p>
      <h3>Read next</h3>
      <ul class="doc-list">
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

function renderCoverage() {
  const coverage = projectMap.coverage;
  if (!coverage) return "";
  return `
    <section class="section-card">
      <p class="section-kicker">Data confidence</p>
      <h3>Current data coverage</h3>
      <div class="coverage-grid">
        <div class="coverage-summary">
          <p class="panel-summary">${escapeHtml(coverage.summary)}</p>
        </div>
        <div>
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
      ${renderFlow(tab.flow, tab.id)}
      ${renderCards(tab.cards)}
      ${tab.id === "overview" ? renderCoverage() : ""}
      ${renderRepoGroups(tab.repo_groups)}
      ${renderSplitLists(tab)}
      <div class="grid-two">
        ${renderFileList("Important files", tab.important_files)}
        ${renderDocs(tab.docs)}
      </div>
      ${renderWarnings(tab.warnings)}
    </article>
  `;
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
    >
      <span class="tab-number">${String(index + 1).padStart(2, "0")}</span>
      <span class="tab-label">${escapeHtml(tab.label)}</span>
    </button>
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
  configureHeroLinks();
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
