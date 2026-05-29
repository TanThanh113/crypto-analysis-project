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
    "roles/bigquery.dataEditor",
    "roles/bigquery.readSessionUser"
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
# This is used for storing Kestra's internal data.
resource "google_storage_bucket_iam_member" "kestra_internal_storage_object_admin" {
  bucket = google_storage_bucket.kestra_internal_storage.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.kestra_gke_sa.email}"
}
# This is used for storing crypto raw data.
resource "google_storage_bucket_iam_member" "kestra_crypto_raw_bucket_object_admin" {
  bucket = var.gcs_bucket_name
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

# --- Grant GKE Service Account the Artifact Registry Reader Role ---
# Get the project number
data "google_project" "current" {
  project_id = var.project
}

# Create a list of the service accounts that can pull images from Artifact Registry
locals {
  gke_artifact_registry_pullers = [
    # On the GKE Autopilot cluster, the virtual machines (nodes) running in the background, managed by Google, will bear the identity of this account.
    "${data.google_project.current.number}-compute@developer.gserviceaccount.com",

    # It handles all background tasks related to coordinating and communicating within the cluster's systems.
    "service-${data.google_project.current.number}@container-engine-robot.iam.gserviceaccount.com"
  ]
}

# Grant the GKE Service Account the Artifact Registry Reader Role
resource "google_project_iam_member" "gke_artifact_registry_reader" {
  for_each = toset(local.gke_artifact_registry_pullers)

  project = var.project
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${each.value}"
}