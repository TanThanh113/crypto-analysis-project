provider "google" {
  project = var.project
  region  = var.region
}

resource "google_service_account" "terraform_sa" {
  account_id   = "terraform-sa"
  display_name = "Terraform Builder SA"
}

resource "google_project_iam_member" "terraform_sa_editor" {
  project = var.project
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.terraform_sa.email}"
}

resource "google_project_iam_member" "terraform_sa_iam_admin" {
  project = var.project
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.terraform_sa.email}"
}

resource "google_project_iam_member" "impersonate_permission" {
  project = var.project
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "user:${var.user_email}"
}