# K8s / GKE Runtime

## What this part does

K8s/GKE is the runtime layer for <strong>production-style</strong> job execution. It supports GKE Autopilot or Kubernetes runtime concepts, Kestra task execution with Kubernetes pods, Docker images from <strong>Artifact Registry</strong>, <strong>Workload Identity</strong>, service-account access, Helm values, and Kubernetes manifests.

This layer is runtime infrastructure, not model logic.

## Where it lives

Runtime support files live under `k8s`, `helm`, `docker`, `kestra/flows-gke`, `.github/workflows`, and `.github/scripts`.

## How it fits into the full platform

Kestra describes orchestration, Docker images package runtime code, Terraform provisions cloud infrastructure, and K8s/GKE provides the execution environment. Batch, dbt, ML, and streaming jobs can be separated into purpose-built images and pods.

<div class="flow-grid">
  <div class="flow-step">
    <strong>GKE Autopilot</strong>
    <span>Provides the managed Kubernetes runtime where Kestra task pods can execute production-style jobs.</span>
  </div>
  <div class="flow-step">
    <strong>KubernetesPod tasks</strong>
    <span>Kestra can launch task pods for batch, dbt, ML, and selected streaming work instead of running everything inside CI.</span>
  </div>
  <div class="flow-step">
    <strong>Artifact Registry pulls</strong>
    <span>Runtime pods pull gated Docker images from Artifact Registry; image builds should remain CI/CD-gated.</span>
  </div>
  <div class="flow-step">
    <strong>Workload Identity</strong>
    <span>Preferred identity model for cloud access without committing key files or long-lived credentials.</span>
  </div>
  <div class="flow-step">
    <strong>Cloud SQL dependency</strong>
    <span>Kestra components may depend on Cloud SQL readiness, identity bindings, and secret/provider configuration.</span>
  </div>
  <div class="flow-step">
    <strong>Runtime safety</strong>
    <span>Do not deploy flows, images, or infrastructure just to make checks green; runtime work can affect cost and access.</span>
  </div>
</div>

## Main flow

1. Dockerfiles define batch, dbt, and ML runtime images.
2. CI/CD can build and push images to Artifact Registry when gates allow it.
3. Terraform provisions or describes the GKE/Kestra infrastructure.
4. Helm values configure Kestra components for GKE.
5. Kubernetes manifests support RBAC and secret provider integration.
6. Kestra launches task pods for selected flow work.

## Key Files And What They Do

### Base path: `k8s/kestra`

<div class="file-card-grid">
  <div class="file-card">
    <h4>GitHub Actions RBAC</h4>
    <p><strong>File:</strong> <code>github-actions-rbac.yaml</code></p>
    <p><strong>Role:</strong> Gives CI/CD the runtime permissions it needs to interact with Kubernetes.</p>
    <p><strong>Why it matters:</strong> RBAC scope controls how much a workflow can affect GKE resources.</p>
    <p><strong>Review note:</strong> Keep permissions narrow and avoid broad access just to make deploys easier.</p>
  </div>
  <div class="file-card">
    <h4>Task Pod RBAC</h4>
    <p><strong>File:</strong> <code>task-pod-rbac.yaml</code></p>
    <p><strong>Role:</strong> Defines permissions for Kestra task pods launched through KubernetesPod execution.</p>
    <p><strong>Why it matters:</strong> This controls what runtime jobs can read, write, or manage inside the cluster.</p>
    <p><strong>Review note:</strong> Runtime safety depends on keeping task permissions scoped.</p>
  </div>
  <div class="file-card">
    <h4>Secret Provider Class</h4>
    <p><strong>File:</strong> <code>secret-provider-class-batch.yml</code></p>
    <p><strong>Role:</strong> Describes secret integration support for batch/runtime pods.</p>
    <p><strong>Why it matters:</strong> It is part of the safer path for cloud/runtime access without committing secret values.</p>
    <p><strong>Review note:</strong> Never commit secret values, key files, or local credentials.</p>
  </div>
</div>

### Runtime Configuration And Images

<div class="file-card-grid">
  <div class="file-card">
    <h4>Kestra Helm Values</h4>
    <p><strong>File:</strong> <code>helm/kestra/values-gke.yaml</code></p>
    <p><strong>Role:</strong> Configures GKE-oriented Kestra components and dependencies.</p>
    <p><strong>Why it matters:</strong> Webserver, executor, and worker health can depend on <strong>Cloud SQL</strong>, identity, and secret-provider readiness.</p>
    <p><strong>Review note:</strong> Runtime config changes should not be made just to silence a check.</p>
  </div>
  <div class="file-card">
    <h4>Batch Runtime Image</h4>
    <p><strong>File:</strong> <code>docker/batch.Dockerfile</code></p>
    <p><strong>Role:</strong> Packages batch utilities for task-pod execution.</p>
    <p><strong>Why it matters:</strong> Kestra can run batch work with purpose-built images pulled from <strong>Artifact Registry</strong>.</p>
    <p><strong>Review note:</strong> Build/push should happen only through gated workflows.</p>
  </div>
  <div class="file-card">
    <h4>dbt Runtime Image</h4>
    <p><strong>File:</strong> <code>docker/dbt.Dockerfile</code></p>
    <p><strong>Role:</strong> Packages dbt transformation runtime for task pods.</p>
    <p><strong>Why it matters:</strong> It separates dbt runtime dependencies from CI shell assumptions.</p>
    <p><strong>Review note:</strong> Do not run cloud-backed dbt builds for docs-only work.</p>
  </div>
  <div class="file-card">
    <h4>ML Runtime Image</h4>
    <p><strong>File:</strong> <code>docker/ml.Dockerfile</code></p>
    <p><strong>Role:</strong> Packages ML training and prediction runtime code.</p>
    <p><strong>Why it matters:</strong> It supports gated ML task execution while keeping training/prediction explicit.</p>
    <p><strong>Review note:</strong> Do not run training or prediction just to validate docs.</p>
  </div>
</div>

### Orchestration And Deploy Helpers

<div class="file-card-grid">
  <div class="file-card">
    <h4>GKE Flow Definitions</h4>
    <p><strong>Folder:</strong> <code>kestra/flows-gke</code></p>
    <p><strong>Role:</strong> Points runtime tasks at images, namespaces, schedules, and destinations.</p>
    <p><strong>Why it matters:</strong> This is where orchestration meets Kubernetes runtime behavior.</p>
    <p><strong>Review note:</strong> Flow deploy remains gated and should not be triggered for docs-only changes.</p>
  </div>
  <div class="file-card">
    <h4>Kestra Deploy Workflow</h4>
    <p><strong>File:</strong> <code>.github/workflows/kestra-deploy-gke.yml</code></p>
    <p><strong>Role:</strong> Runs deploy planning and selected GKE flow deployment when gates allow it.</p>
    <p><strong>Why it matters:</strong> It protects runtime changes from accidental deployment.</p>
    <p><strong>Review note:</strong> Do not deploy just to make checks green.</p>
  </div>
  <div class="file-card">
    <h4>Deploy Plan Helpers</h4>
    <p><strong>Files:</strong> <code>.github/scripts/kestra_deploy_plan.py</code>, <code>.github/scripts/deploy_kestra_flows.py</code></p>
    <p><strong>Role:</strong> Compute gating decisions and deploy selected flows when allowed.</p>
    <p><strong>Why it matters:</strong> They keep docs-only and unrelated changes from creating runtime deploy work.</p>
    <p><strong>Review note:</strong> Gating logic affects production-style runtime behavior.</p>
  </div>
</div>

## Production boundary

GKE runtime is infrastructure. It does not prove model quality, source coverage, or trading edge. ML Kestra deploy remains gated. Kestra webserver, executor, or worker components may fail if Cloud SQL, required secrets, identity bindings, or service accounts are not ready.

## Safety notes

- Do not deploy GKE flows just to make PR checks green.
- Do not commit Kubernetes secrets, service account keys, or local credentials.
- Prefer Workload Identity and service-account bindings over key files.
- Treat Cloud SQL, Artifact Registry, and GKE operations as cloud/runtime actions with cost and access implications.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../kestra_orchestration/">Kestra Orchestration</a>
<a class="read-next-card" href="../terraform_infrastructure/">Terraform Infrastructure</a>
<a class="read-next-card" href="../ci_cd_gates/">CI/CD Gates</a>
<a class="read-next-card" href="../production_boundaries/">Production Boundaries</a>
</div>
</div>
