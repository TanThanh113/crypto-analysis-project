# K8s / GKE Runtime

## What this part does

K8s/GKE is the runtime layer for production-style job execution. It supports GKE Autopilot or Kubernetes runtime concepts, Kestra task execution with Kubernetes pods, Docker images from Artifact Registry, Workload Identity, service-account access, Helm values, and Kubernetes manifests.

This layer is runtime infrastructure, not model logic.

## Where it lives

Runtime support files live under `k8s`, `helm`, `docker`, `kestra/flows-gke`, `.github/workflows`, and `.github/scripts`.

## How it fits into the full platform

Kestra describes orchestration, Docker images package runtime code, Terraform provisions cloud infrastructure, and K8s/GKE provides the execution environment. Batch, dbt, ML, and streaming jobs can be separated into purpose-built images and pods.

## Main flow

1. Dockerfiles define batch, dbt, and ML runtime images.
2. CI/CD can build and push images to Artifact Registry when gates allow it.
3. Terraform provisions or describes the GKE/Kestra infrastructure.
4. Helm values configure Kestra components for GKE.
5. Kubernetes manifests support RBAC and secret provider integration.
6. Kestra launches task pods for selected flow work.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `k8s/kestra/github-actions-rbac.yaml` | GitHub Actions RBAC | Supports CI/CD runtime access. |
| `k8s/kestra/task-pod-rbac.yaml` | Task pod RBAC | Supports Kestra task pod permissions. |
| `k8s/kestra/secret-provider-class-batch.yml` | Secret provider class | Secret integration support; do not commit secret values. |
| `helm/kestra/values-gke.yaml` | Kestra Helm values | GKE-oriented Kestra configuration. |
| `docker/batch.Dockerfile` | Batch image | Runtime image for batch utilities. |
| `docker/dbt.Dockerfile` | dbt image | Runtime image for dbt transformations. |
| `docker/ml.Dockerfile` | ML image | Runtime image for ML jobs. |
| `kestra/flows-gke` | GKE-oriented flow definitions | Orchestration definitions for runtime jobs. |
| `.github/workflows/kestra-deploy-gke.yml` | Kestra deploy workflow | Deploy gate and flow deployment workflow. |
| `.github/scripts/kestra_deploy_plan.py` | Deploy plan helper | Computes gating decisions. |
| `.github/scripts/deploy_kestra_flows.py` | Flow deploy helper | Deploys selected flows when allowed. |

## Production boundary

GKE runtime is infrastructure. It does not prove model quality, source coverage, or trading edge. ML Kestra deploy remains gated. Kestra webserver, executor, or worker components may fail if Cloud SQL, required secrets, identity bindings, or service accounts are not ready.

## Safety notes

- Do not deploy GKE flows just to make PR checks green.
- Do not commit Kubernetes secrets, service account keys, or local credentials.
- Prefer Workload Identity and service-account bindings over key files.
- Treat Cloud SQL, Artifact Registry, and GKE operations as cloud/runtime actions with cost and access implications.

## Read next

- [Kestra Orchestration](kestra_orchestration.md)
- [Terraform Infrastructure](terraform_infrastructure.md)
- [CI/CD Gates](ci_cd_gates.md)
- [Production Boundaries](production_boundaries.md)
