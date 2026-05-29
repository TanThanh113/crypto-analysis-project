# GitHub Actions CI/CD Service Account
resource "google_service_account" "github_cicd_sa" {
  account_id   = "github-cicd-sa"
  display_name = "GitHub CI/CD Service Account"
  description  = "Service account used by GitHub Actions to build and push Docker images."
}

locals {
  github_cicd_roles = [
    "roles/artifactregistry.writer",
    "roles/container.developer"
  ]
}

resource "google_project_iam_member" "github_cicd_sa_roles" {
  for_each = toset(local.github_cicd_roles)

  project = var.project
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_cicd_sa.email}"
}

# Workload Identity Pool for GitHub Actions
resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Workload Identity Pool for GitHub Actions."
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Provider"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "assertion.repository == '${var.github_owner}/${var.github_repo}' && assertion.ref == 'refs/heads/main'"
}

# Allow only this GitHub repo to impersonate github-cicd-sa
resource "google_service_account_iam_member" "github_cicd_wif_binding" {
  service_account_id = google_service_account.github_cicd_sa.name
  role               = "roles/iam.workloadIdentityUser"

  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_owner}/${var.github_repo}"
}

output "github_workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github_provider.name
  description = "Use this value as workload_identity_provider in GitHub Actions."
}

output "github_cicd_service_account_email" {
  value       = google_service_account.github_cicd_sa.email
  description = "Use this value as service_account in GitHub Actions."
}
