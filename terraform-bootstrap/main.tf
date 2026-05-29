provider "google" {
  project = var.project
  region  = var.region
}

resource "google_service_account" "terraform_sa" {
  account_id   = "terraform-sa"
  display_name = "Terraform Builder SA"
}

locals {
  terraform_sa_roles = [
    "roles/editor",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/compute.networkAdmin",
    "roles/servicenetworking.networksAdmin",
    "roles/secretmanager.secretAccessor",
    "roles/container.clusterAdmin",
    "roles/container.admin"
  ]
}

# Cấp tất cả quyền bằng một block duy nhất
resource "google_project_iam_member" "terraform_sa_roles" {
  for_each = toset(local.terraform_sa_roles)
  project  = var.project
  role     = each.value
  member   = "serviceAccount:${google_service_account.terraform_sa.email}"
}

resource "google_project_iam_member" "impersonate_permission" {
  project = var.project
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "user:${var.user_email}"
}