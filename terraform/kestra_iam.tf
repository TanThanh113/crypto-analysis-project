# --- Create IAM Roles for Kestra(Service Account) ---
resource "google_service_account" "kestra_gke_sa" {
  account_id   = var.kestra_gcp_service_account_id
  display_name = "Kestra GKE Service Account"
  description  = "Google service account used by Kestra on GKE through Workload Identity."
}

locals {
  kestra_project_roles = [
    "roles/artifactregistry.reader",
    "roles/cloudsql.client", # VPC Peering
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
    "roles/bigquery.jobUser",
    "roles/bigquery.dataViewer",
    "roles/bigquery.dataEditor"
  ]
}

# Assign the above permissions
resource "google_project_iam_member" "kestra_project_roles" {
  for_each = toset(local.kestra_project_roles)

  project = var.project
  role    = each.value
  member  = "serviceAccount:${google_service_account.kestra_gke_sa.email}"
}

# Grant top privileges to the storage.
resource "google_storage_bucket_iam_member" "kestra_internal_storage_object_admin" {
  bucket = google_storage_bucket.kestra_internal_storage.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.kestra_gke_sa.email}"
}

# Grant the service account the Workload Identity User role
resource "google_service_account_iam_member" "kestra_workload_identity_binding" {
  service_account_id = google_service_account.kestra_gke_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project}.svc.id.goog[${var.kestra_namespace}/${var.kestra_kubernetes_service_account}]"

  depends_on = [
    google_container_cluster.kestra_autopilot
  ]
}
