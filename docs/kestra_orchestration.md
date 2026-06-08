# Kestra Orchestration

Kestra orchestrates ingestion, dbt transformations, monitoring, quality checks, ML training, prediction, and PR preview validation. Production-style GKE flows live under `kestra/flows-gke`.

![CI/CD and Kestra gating](diagrams/ci_cd_kestra_gating.svg)

## Flow Groups

| Group | Path | Purpose |
| --- | --- | --- |
| Raw | `kestra/flows-gke/raw` | Batch ingestion snapshots and intraday/hourly raw refreshes |
| dbt | `kestra/flows-gke/dbt` | dbt daily, hourly, intraday, macro, market, and ETF transforms |
| ML | `kestra/flows-gke/ml` | ML training, prediction, and manual strategy matrix training |
| Streaming | `kestra/flows-gke/streaming` | Streaming hourly transform orchestration |
| Monitoring | `kestra/flows-gke/monitoring` | Pipeline health checks |
| Quality | `kestra/flows-gke/quality` | Great Expectations quality audit |
| Preview | `kestra/flows-gke/preview` | Safe PR validation flows |
| Master | `kestra/flows-gke/master` | Pipeline overview/master flow |

Legacy/local Kestra flows also exist under `kestra/flows`.

## ML Deploy Gate

ML flows are gated by:

```text
ENABLE_ML_KESTRA_DEPLOY
```

Default behavior on Pull Requests is conservative:

- Batch/dbt/non-ML flows can still deploy when they are deployable.
- ML flows are skipped unless the ML deploy flag is explicitly enabled in the appropriate workflow context.
- PRs with only skipped ML flows should not require a live Kestra server or Cloud SQL dependency.

## PR Deploy Plan

The workflow computes a deploy plan before GCP auth, GKE credentials, port-forward, or flow deploy.

Important outputs:

- `has_non_ml_flows_to_deploy`
- `has_ml_flows_to_deploy`
- `should_deploy_ml_flows`
- `has_any_flows_to_deploy`
- `has_docker_relevant_changes`
- `should_build_docker`

If `has_any_flows_to_deploy=false`, Kestra port-forward/deploy is skipped.

## Docker Build Gate

Docker build/smoke checks run only when they are useful:

- Docker/runtime/dependency files changed, or
- there are deployable Kestra flows after ML gating.

If neither condition is true, the workflow logs:

```text
Skipping Docker build: no Docker/runtime changes and no deployable Kestra flows.
```

This keeps PR validation cheaper without disabling pytest, repo guard, or diff checks.

## Cloud SQL and GKE Dependency

Kestra production deployment depends on GKE and the Kestra webserver being reachable. Kestra metadata/state is backed by Cloud SQL PostgreSQL in the production-style architecture. If the webserver is not reachable, check Kubernetes and database connectivity before retrying deploy.

## Debug Commands

Use these only when intentionally debugging a live cluster:

```bash
kubectl get pods -n kestra
kubectl logs -n kestra deployment/kestra-webserver
kubectl port-forward -n kestra deployment/kestra-webserver 8080:8080
```

Common failure areas:

- GKE credentials or Workload Identity are not configured.
- Kestra webserver is not ready.
- Cloud SQL connectivity is broken.
- Port-forward is attempted even though no deployable flows exist.
- Flow deploy includes ML flows while ML infrastructure is intentionally disabled.

## Safety Notes

- Do not enable ML deploy just to make PR checks green.
- Keep batch/dbt deploy independent from the ML flag.
- Do not add triggers to PR preview flows.
- Do not run full production flows in preview namespaces unless outputs are isolated.
