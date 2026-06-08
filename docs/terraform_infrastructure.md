# Terraform Infrastructure

## What this part does

Terraform describes cloud infrastructure for the platform. It helps make GCP resources reviewable, repeatable, and easier to reason about. This documentation work does not run `terraform apply`.

## Where it lives

Terraform files live under `terraform`, `terraform-bootstrap`, and `terraform-grafana`.

## How it fits into the full platform

Terraform supports the infrastructure beneath ingestion, storage, orchestration, runtime execution, monitoring, and CI/CD. It can describe BigQuery datasets, GCS buckets, Artifact Registry, GKE/Kestra infrastructure, Cloud SQL, IAM/service accounts, networking, and Grafana-related resources.

## Main flow

1. Provider configuration sets the GCP/Terraform context.
2. Resource files describe datasets, buckets, registries, IAM, networking, and runtime infrastructure.
3. Bootstrap Terraform supports foundational IAM/service-account setup.
4. Grafana Terraform supports dashboard/infrastructure adjuncts.
5. State and tfvars must be handled outside documentation and commits.

## Important files and folders

| Path | Purpose | Notes |
| --- | --- | --- |
| `terraform/provider.tf` | Main provider config | Review provider/project assumptions carefully. |
| `terraform/main.tf` | Main module entry | Primary resource composition. |
| `terraform/bigquery_datasets.tf` | BigQuery datasets | Warehouse and mart infrastructure. |
| `terraform/gcs_buckets.tf` | GCS buckets | Storage infrastructure. |
| `terraform/artifact_registry.tf` | Artifact Registry | Runtime image registry. |
| `terraform/kestra_gke.tf` | GKE/Kestra infrastructure | Runtime infrastructure definitions. |
| `terraform/kestra_cloudsql.tf` | Cloud SQL for Kestra | Database dependency for Kestra. |
| `terraform/kestra_iam.tf` | Kestra IAM | Identity and access bindings. |
| `terraform/network.tf` | Networking | Network-related resources. |
| `terraform-bootstrap/main.tf` | Bootstrap resources | IAM/service-account bootstrap. |
| `terraform-grafana/main.tf` | Grafana infrastructure | Grafana-related setup. |

## Production boundary

Terraform is descriptive infrastructure code. It does not run unless a human or workflow executes Terraform commands. Do not infer that every resource is currently live, healthy, or complete merely because code exists.

## Safety notes

- Never commit `.tfstate`, `.tfstate.backup`, secret-bearing `.tfvars`, service account keys, or local credentials.
- Do not run `terraform apply` casually.
- Review IAM, networking, Cloud SQL, GKE, and Artifact Registry changes carefully because they can affect cost, access, and runtime availability.
- Terraform docs in this task are descriptive only.

## Read next

- [K8s / GKE Runtime](k8s_gke_runtime.md)
- [CI/CD Gates](ci_cd_gates.md)
- [Repository Map](repository_map.md)
- [Production Boundaries](production_boundaries.md)
