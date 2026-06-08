# Kestra Orchestration

## What this part does

Kestra organizes platform workflows into flow groups. It describes when and how raw ingestion, dbt transforms, ML jobs, streaming transforms, monitoring, quality checks, preview validation, and master overview flows should run.

This page focuses on orchestration logic. Kubernetes/GKE runtime details live in [K8s / GKE Runtime](k8s_gke_runtime.md).

## Where it lives

Production-style flow definitions live under `kestra/flows-gke`. Legacy/local flow definitions also exist under `kestra/flows`.

## How it fits into the full platform

Kestra connects subsystem work without embedding business logic in CI/CD. It can orchestrate batch ingestion, dbt transformations, ML training/prediction, monitoring, and quality checks. GKE runtime execution and Helm/Kubernetes details are separate runtime concerns.

## Main flow

1. Raw flows run batch snapshots and intraday refreshes.
2. dbt flows run hourly, intraday, daily market, macro, and ETF transforms.
3. ML flows run training, prediction, and strategy matrix workflows only when intentionally enabled.
4. Streaming flows can orchestrate streaming transforms.
5. Monitoring and quality flows check freshness and quality.
6. Preview flows validate PR changes without production triggers.
7. Master flows summarize the broader platform orchestration.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `kestra/flows-gke/raw` | Raw ingestion flows | Batch snapshots and intraday refresh. |
| `kestra/flows-gke/dbt` | dbt flows | Hourly, intraday, daily market, macro, and ETF transforms. |
| `kestra/flows-gke/ml` | ML flows | Training, prediction, and strategy matrix flows. |
| `kestra/flows-gke/streaming` | Streaming flow | Streaming transform orchestration. |
| `kestra/flows-gke/monitoring` | Monitoring flows | Pipeline health checks. |
| `kestra/flows-gke/quality` | Quality flows | Great Expectations-style quality audit. |
| `kestra/flows-gke/preview` | PR preview flows | Validation-only flows without production triggers. |
| `kestra/flows-gke/master` | Master overview flow | High-level orchestration overview. |
| `.github/scripts/kestra_deploy_plan.py` | Deploy planning | Decides which flow groups are deployable. |
| `.github/scripts/deploy_kestra_flows.py` | Flow deploy helper | Deploys selected flows when gates allow it. |

## Production boundary

Kestra orchestration can trigger production-style work, so flow triggers, namespaces, images, and destinations must be reviewed carefully. ML flow deployment remains gated separately. PR preview flows should not gain production triggers.

## Safety notes

- Do not deploy Kestra/GKE flows just to make checks green.
- Do not enable ML deploy casually.
- Do not put secrets, keys, or local credentials into flow YAML.
- Runtime failures can come from infrastructure dependencies such as Cloud SQL or identity bindings; see [K8s / GKE Runtime](k8s_gke_runtime.md).

## Read next

- [K8s / GKE Runtime](k8s_gke_runtime.md)
- [CI/CD Gates](ci_cd_gates.md)
- [Batch Pipeline](batch_pipeline.md)
- [ML and MLOps](ml_mLOps.md)
