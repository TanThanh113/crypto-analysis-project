# Terraform Infrastructure

## What this part does

Terraform describes cloud infrastructure for the platform. It helps make GCP resources reviewable, repeatable, and easier to reason about. This documentation work does not run `terraform apply`.

## Where it lives

Terraform files live under `terraform`, `terraform-bootstrap`, and `terraform-grafana`.

## How it fits into the full platform

Terraform supports the infrastructure beneath ingestion, storage, orchestration, runtime execution, monitoring, and CI/CD. It can describe BigQuery datasets, GCS buckets, <strong>Artifact Registry</strong>, GKE/Kestra infrastructure, Cloud SQL, IAM/service accounts, networking, and Grafana-related resources.

<div class="flow-grid">
  <div class="flow-step">
    <strong>BigQuery</strong>
    <span>Defines warehouse datasets that dbt, monitoring, dashboards, and ML marts can target.</span>
  </div>
  <div class="flow-step">
    <strong>GCS</strong>
    <span>Defines storage buckets for landing zones, artifacts, and cloud-oriented data paths.</span>
  </div>
  <div class="flow-step">
    <strong>Artifact Registry</strong>
    <span>Hosts batch, dbt, and ML runtime images when Docker build gates intentionally publish them.</span>
  </div>
  <div class="flow-step">
    <strong>GKE and Cloud SQL</strong>
    <span>Supports Kestra runtime infrastructure and database dependencies for orchestration components.</span>
  </div>
  <div class="flow-step">
    <strong>IAM and service accounts</strong>
    <span>Controls cloud access for CI/CD, Kestra, task pods, and runtime jobs; review permissions carefully.</span>
  </div>
  <div class="flow-step">
    <strong>Monitoring / Grafana</strong>
    <span>Describes adjacent observability resources when present; dashboards should not hide runtime failures.</span>
  </div>
</div>

## Main flow

1. Provider configuration sets the GCP/Terraform context.
2. Resource files describe datasets, buckets, registries, IAM, networking, and runtime infrastructure.
3. Bootstrap Terraform supports foundational IAM/service-account setup.
4. Grafana Terraform supports dashboard/infrastructure adjuncts.
5. State and tfvars must be handled outside documentation and commits.

## Key Files And What They Do

### Base path: `terraform`

<div class="file-card-grid">
  <div class="file-card">
    <h4>Provider Context</h4>
    <p><strong>File:</strong> <code>provider.tf</code></p>
    <p><strong>Role:</strong> Defines Terraform's GCP provider context.</p>
    <p><strong>Why it matters:</strong> Project, region, and provider assumptions decide where infrastructure changes would land.</p>
    <p><strong>Review note:</strong> Wrong context can affect real cloud resources.</p>
  </div>
  <div class="file-card">
    <h4>Main Resource Composition</h4>
    <p><strong>File:</strong> <code>main.tf</code></p>
    <p><strong>Role:</strong> Connects the primary infrastructure resources and modules.</p>
    <p><strong>Why it matters:</strong> This is the first place to inspect the overall Terraform shape.</p>
    <p><strong>Review note:</strong> Descriptive code does not mean every resource is live or healthy.</p>
  </div>
  <div class="file-card">
    <h4>BigQuery Datasets</h4>
    <p><strong>File:</strong> <code>bigquery_datasets.tf</code></p>
    <p><strong>Role:</strong> Defines <strong>BigQuery</strong> dataset infrastructure for warehouse, marts, monitoring, and ML output surfaces.</p>
    <p><strong>Why it matters:</strong> These datasets are where dbt and analytics outputs can land.</p>
    <p><strong>Review note:</strong> Dataset changes can affect cost, access, and downstream contracts.</p>
  </div>
  <div class="file-card">
    <h4>GCS Buckets</h4>
    <p><strong>File:</strong> <code>gcs_buckets.tf</code></p>
    <p><strong>Role:</strong> Defines <strong>GCS</strong> bucket infrastructure for landing zones, curated storage, or artifacts.</p>
    <p><strong>Why it matters:</strong> Storage policy controls how ingestion and artifacts move through the platform.</p>
    <p><strong>Review note:</strong> Bucket changes can affect data access and cost.</p>
  </div>
  <div class="file-card">
    <h4>Artifact Registry</h4>
    <p><strong>File:</strong> <code>artifact_registry.tf</code></p>
    <p><strong>Role:</strong> Defines <strong>Artifact Registry</strong> repositories for runtime Docker images.</p>
    <p><strong>Why it matters:</strong> Batch, dbt, and ML task pods depend on published images when runtime gates allow them.</p>
    <p><strong>Review note:</strong> Registry writes should happen only through gated build/push workflows.</p>
  </div>
  <div class="file-card">
    <h4>GKE And Kestra</h4>
    <p><strong>File:</strong> <code>kestra_gke.tf</code></p>
    <p><strong>Role:</strong> Describes GKE/Kestra runtime infrastructure.</p>
    <p><strong>Why it matters:</strong> This supports KubernetesPod task execution for production-style workflows.</p>
    <p><strong>Review note:</strong> GKE changes can affect runtime availability and cloud cost.</p>
  </div>
  <div class="file-card">
    <h4>Cloud SQL For Kestra</h4>
    <p><strong>File:</strong> <code>kestra_cloudsql.tf</code></p>
    <p><strong>Role:</strong> Defines <strong>Cloud SQL</strong> dependency for Kestra components.</p>
    <p><strong>Why it matters:</strong> Kestra webserver/executor/worker health can depend on this database being ready.</p>
    <p><strong>Review note:</strong> Cloud SQL affects cost, access, and runtime stability.</p>
  </div>
  <div class="file-card">
    <h4>Kestra IAM</h4>
    <p><strong>File:</strong> <code>kestra_iam.tf</code></p>
    <p><strong>Role:</strong> Defines identity and access bindings for Kestra runtime paths.</p>
    <p><strong>Why it matters:</strong> IAM controls whether jobs can read/write cloud resources.</p>
    <p><strong>Review note:</strong> Prefer <strong>Workload Identity</strong> and scoped access over key files.</p>
  </div>
  <div class="file-card">
    <h4>Networking</h4>
    <p><strong>File:</strong> <code>network.tf</code></p>
    <p><strong>Role:</strong> Defines network-related resources.</p>
    <p><strong>Why it matters:</strong> Networking controls connectivity, security, and runtime availability.</p>
    <p><strong>Review note:</strong> Network changes should be reviewed for access and blast radius.</p>
  </div>
</div>

### Bootstrap And Observability

<div class="file-card-grid">
  <div class="file-card">
    <h4>Bootstrap Resources</h4>
    <p><strong>Full path:</strong> <code>terraform-bootstrap/main.tf</code></p>
    <p><strong>Role:</strong> Sets up foundational IAM and service-account resources.</p>
    <p><strong>Why it matters:</strong> Bootstrap identity decisions affect CI/CD, Kestra, and runtime access across the platform.</p>
    <p><strong>Review note:</strong> Avoid casual IAM changes; never commit keys or secret tfvars.</p>
  </div>
  <div class="file-card">
    <h4>Grafana Infrastructure</h4>
    <p><strong>Full path:</strong> <code>terraform-grafana/main.tf</code></p>
    <p><strong>Role:</strong> Describes Grafana-related infrastructure where configured.</p>
    <p><strong>Why it matters:</strong> Observability resources help reviewers understand monitoring and dashboard context.</p>
    <p><strong>Review note:</strong> Provider/config changes can affect dashboards and credentials.</p>
  </div>
</div>

## Production boundary

Terraform is descriptive infrastructure code. It does not run unless a human or workflow executes Terraform commands. Do not infer that every resource is currently live, healthy, or complete merely because code exists.

## Safety notes

- Never commit `.tfstate`, `.tfstate.backup`, secret-bearing `.tfvars`, service account keys, or local credentials.
- Do not run `terraform apply` casually.
- Review IAM, networking, Cloud SQL, GKE, and Artifact Registry changes carefully because they can affect cost, access, and runtime availability.
- Terraform docs in this task are descriptive only.

<div class="read-next">
<strong>Read next</strong>
<div class="read-next-card-grid">
<a class="read-next-card" href="../k8s_gke_runtime/">K8s / GKE Runtime</a>
<a class="read-next-card" href="../ci_cd_gates/">CI/CD Gates</a>
<a class="read-next-card" href="../repository_map/">Repository Map</a>
<a class="read-next-card" href="../production_boundaries/">Production Boundaries</a>
</div>
</div>
