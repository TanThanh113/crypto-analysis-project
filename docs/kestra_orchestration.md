# Kestra Orchestration

## What this part does

Kestra organizes platform workflows into flow groups. It describes when and how raw ingestion, dbt transforms, ML jobs, streaming transforms, monitoring, quality checks, preview validation, and master overview flows should run.

This page focuses on orchestration logic. Kestra is the scheduler/orchestrator, not the compute runtime. Kubernetes/GKE runtime details live in [K8s / GKE Runtime](k8s_gke_runtime.md).

## Where it lives

Production-style flow definitions live under `kestra/flows-gke`. Legacy/local flow definitions also exist under `kestra/flows`.

## How it fits into the full platform

Kestra connects subsystem work without embedding business logic in CI/CD. It can orchestrate batch ingestion, dbt transformations, ML training/prediction, monitoring, and quality checks. GKE runtime execution and Helm/Kubernetes details are separate runtime concerns.

<div class="flow-grid">
  <div class="flow-step">
    <strong>raw</strong>
    <span>Runs batch snapshots and intraday refresh flows that prepare source data.</span>
  </div>
  <div class="flow-step">
    <strong>dbt</strong>
    <span>Runs hourly, intraday, daily market, macro, and ETF transformation groups.</span>
  </div>
  <div class="flow-step">
    <strong>ml</strong>
    <span>Orchestrates training and prediction only when ML deploy gates intentionally allow it.</span>
  </div>
  <div class="flow-step">
    <strong>streaming</strong>
    <span>Coordinates streaming transform work, which remains more experimental than batch coverage.</span>
  </div>
  <div class="flow-step">
    <strong>monitoring and quality</strong>
    <span>Runs freshness, pipeline health, and quality-audit checks so bad inputs are visible.</span>
  </div>
  <div class="flow-step">
    <strong>preview and master</strong>
    <span>Preview validates PR changes without production triggers; master gives a high-level orchestration view.</span>
  </div>
</div>

## Main flow

1. Raw flows run batch snapshots and intraday refreshes.
2. dbt flows run hourly, intraday, daily market, macro, and ETF transforms.
3. ML flows run training, prediction, and strategy matrix workflows only when intentionally enabled.
4. Streaming flows can orchestrate streaming transforms.
5. Monitoring and quality flows check freshness and quality.
6. Preview flows validate PR changes without production triggers.
7. Master flows summarize the broader platform orchestration.

## Batch and Kestra on GKE runbook

!!! warning "Operational runbook"
    This workflow can create or update cloud infrastructure. Secrets must never be committed. Use the correct GCP project, Kubernetes context, namespace, and credentials before running any command. Do not run these commands during documentation validation.

This repository contains GKE-oriented Kestra assets under `kestra/flows-gke`, Helm values under `helm/kestra`, Kubernetes manifests under `k8s/kestra`, and the secret sync helper at `scripts/sync_kestra_k8s_secrets.sh`.

### 1. Provision or update cloud infrastructure

From the Terraform module that owns the relevant GKE/Kestra infrastructure, review the plan and apply only when intentionally operating the environment:

```bash
terraform apply
```

See [Terraform Infrastructure](terraform_infrastructure.md) before changing cloud infrastructure.

### 2. Add required secrets in cloud secret storage

Create or update the required secrets in the approved cloud secret storage path for the active environment. Keep `.env` files, service account keys, local credential files, Terraform state, and `.tfvars` out of Git.

See [Production Boundaries](production_boundaries.md) for the project safety posture.

### 3. Prepare Kubernetes and Helm access

Install and authenticate the required Kubernetes and Helm tooling for the target cluster. Confirm that your local `kubectl` context points at the intended GKE cluster before syncing secrets or inspecting pods.

See [K8s / GKE Runtime](k8s_gke_runtime.md) for runtime details.

### 4. Sync Kestra/Kubernetes secrets

Sync the reviewed cloud secrets into Kubernetes for Kestra:

```bash
uv run scripts/sync_kestra_k8s_secrets.sh
```

This command should be run only by an operator with the correct cloud and Kubernetes credentials.

### 5. Check pod health

Check the active namespace. If the deployment uses the default `kestra` namespace, the command is:

```bash
kubectl get pods -n kestra
```

For another environment, replace the namespace:

```bash
kubectl get pods -n <namespace>
```

### 6. Open the Kestra webserver locally

Port-forward the Kestra webserver only when you intend to inspect the live UI:

```bash
kubectl port-forward deployment/kestra-webserver 8080:8080 -n kestra
```

If the deployment uses another namespace, replace it:

```bash
kubectl port-forward deployment/kestra-webserver 8080:8080 -n <namespace>
```

Then open `http://localhost:8080` and log in with the correct credentials.

### 7. Review flows and executions

From the Kestra UI, inspect flows, executions, logs, failed tasks, schedules, and namespace-specific configuration. Treat failed tasks as operational signals to investigate rather than issues to bypass.

## Key Files And What They Do

### Base path: `kestra/flows-gke`

<div class="file-card-grid">
  <div class="file-card">
    <h4>Raw Flows</h4>
    <p><strong>Folder:</strong> <code>raw</code></p>
    <p><strong>Role:</strong> Orchestrates batch snapshots and intraday refreshes.</p>
    <p><strong>Why it matters:</strong> These flows sit near the beginning of the platform and can prepare data that later feeds dbt and ML.</p>
    <p><strong>Review note:</strong> They can lead to <strong>cloud writes</strong>; review triggers and destinations carefully.</p>
  </div>
  <div class="file-card">
    <h4>dbt Flows</h4>
    <p><strong>Folder:</strong> <code>dbt</code></p>
    <p><strong>Role:</strong> Runs transformation groups for hourly, intraday, daily market, macro, and ETF models.</p>
    <p><strong>Why it matters:</strong> This is where orchestration connects ingestion outputs to <strong>dbt marts</strong>.</p>
    <p><strong>Review note:</strong> Cloud-backed dbt runs can affect <strong>BigQuery</strong> cost and warehouse state.</p>
  </div>
  <div class="file-card">
    <h4>ML Flows</h4>
    <p><strong>Folder:</strong> <code>ml</code></p>
    <p><strong>Role:</strong> Orchestrates training, prediction, and strategy matrix workflows.</p>
    <p><strong>Why it matters:</strong> ML flows connect the feature contract and artifacts to scheduled operation.</p>
    <p><strong>Review note:</strong> ML deployment remains gated because training/prediction can write artifacts or use cloud resources.</p>
  </div>
  <div class="file-card">
    <h4>Streaming Flows</h4>
    <p><strong>Folder:</strong> <code>streaming</code></p>
    <p><strong>Role:</strong> Coordinates streaming transform work.</p>
    <p><strong>Why it matters:</strong> It links lower-latency context to orchestration without making streaming the trusted full-history path.</p>
    <p><strong>Review note:</strong> Keep this marked as freshness/experimental until coverage and sinks are proven.</p>
  </div>
  <div class="file-card">
    <h4>Monitoring, Quality, And Preview</h4>
    <p><strong>Folders:</strong> <code>monitoring</code>, <code>quality</code>, <code>preview</code></p>
    <p><strong>Role:</strong> Runs pipeline health checks, quality audit expectations, and PR preview validation.</p>
    <p><strong>Why it matters:</strong> These flows show whether data and workflow changes are healthy before production-style work expands.</p>
    <p><strong>Review note:</strong> Preview flows should stay validation-only and should not gain production triggers.</p>
  </div>
  <div class="file-card">
    <h4>Master Flows</h4>
    <p><strong>Folder:</strong> <code>master</code></p>
    <p><strong>Role:</strong> Provides high-level orchestration overview across flow groups.</p>
    <p><strong>Why it matters:</strong> Useful for reviewers who want the big orchestration picture before inspecting individual flows.</p>
    <p><strong>Review note:</strong> Treat it as a map of orchestration, not as compute runtime implementation.</p>
  </div>
</div>

### Base path: `.github/scripts`

<div class="file-card-grid">
  <div class="file-card">
    <h4>Kestra Deploy Plan</h4>
    <p><strong>File:</strong> <code>kestra_deploy_plan.py</code></p>
    <p><strong>Role:</strong> Decides which flow groups are deployable and whether runtime work is needed.</p>
    <p><strong>Why it matters:</strong> It keeps docs-only or unrelated changes from triggering unnecessary deploy work.</p>
    <p><strong>Review note:</strong> Do not loosen gates just to make checks green.</p>
  </div>
  <div class="file-card">
    <h4>Kestra Flow Deploy Helper</h4>
    <p><strong>File:</strong> <code>deploy_kestra_flows.py</code></p>
    <p><strong>Role:</strong> Deploys selected flows when CI gates and configuration allow it.</p>
    <p><strong>Why it matters:</strong> This helper is the bridge between reviewed workflow decisions and Kestra flow deployment.</p>
    <p><strong>Review note:</strong> Do not run deploys casually; deployment is operational work.</p>
  </div>
</div>

## Production boundary

Kestra orchestration can trigger <strong>production-style</strong> work, so flow triggers, namespaces, images, and destinations must be reviewed carefully. ML flow deployment remains gated separately. PR preview flows should not gain production triggers.

## Safety notes

- Do not deploy Kestra/GKE flows just to make checks green.
- Do not enable ML deploy casually.
- Do not put secrets, keys, or local credentials into flow YAML.
- Runtime failures can come from infrastructure dependencies such as Cloud SQL or identity bindings; see [K8s / GKE Runtime](k8s_gke_runtime.md).

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../k8s_gke_runtime/">K8s / GKE Runtime</a>
<a class="read-next-card" href="../ci_cd_gates/">CI/CD Gates</a>
<a class="read-next-card" href="../batch_pipeline/">Batch Pipeline</a>
<a class="read-next-card" href="../ml_mLOps/">ML and MLOps</a>
</div>
</div>
