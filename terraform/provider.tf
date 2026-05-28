provider "google" {
  project                     = var.project
  region                      = var.region
  impersonate_service_account = "terraform-sa@${var.project}.iam.gserviceaccount.com"
}

# Flink Service Account
resource "google_service_account" "flink_sa" {
  account_id   = var.service_account
  display_name = "Flink Service Account"
}

locals {
  flink_roles = [
    "roles/bigquery.readSessionUser",
    "roles/bigquery.dataEditor",
    "roles/bigquery.dataViewer",
    "roles/bigquery.metadataViewer",
    "roles/bigquery.jobUser",
    "roles/bigquery.dataOwner",
    "roles/storage.objectAdmin",
    "roles/dataproc.worker",
    "roles/logging.logWriter",
    "roles/biglake.admin"
  ]
}

resource "google_project_iam_member" "flink_sa_roles" {
  for_each = toset(local.flink_roles)
  project  = var.project
  role     = each.value
  member   = "serviceAccount:${google_service_account.flink_sa.email}"
}

resource "google_service_account_key" "kafka_connect_key" {
  service_account_id = google_service_account.flink_sa.name
}

resource "local_file" "kafka_connect_key_key_json" {
  content  = base64decode(google_service_account_key.kafka_connect_key.private_key)
  filename = "${path.module}/../local_scripts/streaming/secrets/kafka_connect_key.json"
}