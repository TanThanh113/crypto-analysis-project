# ========================================================
# PART 1: GOOGLE CLOUD - CREATING A SERVICE ACCOUNT & KEY
# ========================================================

resource "google_service_account" "grafana_reader" {
  account_id   = var.grafana_sa_account_id
  display_name = "Grafana BigQuery Reader SA"
}

resource "google_project_iam_member" "grafana_bq_viewer" {
  project = var.project
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.grafana_reader.email}"
}

resource "google_project_iam_member" "grafana_bq_job_user" {
  project = var.project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.grafana_reader.email}"
}

resource "google_service_account_key" "grafana_key" {
  service_account_id = google_service_account.grafana_reader.name
}

Extract JSON Key files directly from RAM (Do not save to hard drive for security purposes)
locals {
  sa_key_json = jsondecode(base64decode(google_service_account_key.grafana_key.private_key))
}


# ===================================================================
# PART 2: GRAFANA - AUTOMATICALLY INSTALLING DATA SOURCE & DASHBOARD
# ===================================================================

# Automatically add BigQuery Data Source using the newly generated Key
resource "grafana_data_source" "bigquery" {
  type = "grafana-bigquery-datasource"
  name = "GCP-BigQuery-Crypto"
  uid  = "gcp_bq_crypto_uid" Static ID for easy identification of JSON files.

  json_data_encoded = jsonencode({
    authenticationType = "jwt"
    clientEmail        = local.sa_key_json.client_email
    defaultProject     = var.project
    tokenUri           = "https://oauth2.googleapis.com/token"
  })

  # Directly inject the Private Key into Grafana's secure area
  secure_json_data_encoded = jsonencode({
    privateKey = local.sa_key_json.private_key
  })

  depends_on = [google_project_iam_member.grafana_bq_viewer]
}

# Create a folder to keep your Dashboard organized
resource "grafana_folder" "crypto_folder" {
  title = "Crypto Analytics"
}

# Deploy Dashboard JSON
resource "grafana_dashboard" "crypto_main_dashboard" {
  # Read the contents of your JSON file
  config_json = file("${path.module}/dashboards/crypto_main.json")
  folder      = grafana_folder.crypto_folder.id
  overwrite   = true

  depends_on = [grafana_data_source.bigquery]
}


# =======================================================
# PART 3: RESULTS RETURNED TO THE SCREEN
# =======================================================

output "grafana_dashboard_url" {
  description = "🎉 DIRECT ACCESS LINK TO DASHBOARD 🎉"
  value       = "${grafana_dashboard.crypto_main_dashboard.url}"
}

output "grafana_datasource_uid" {
  description = "UID của BigQuery Data Source (Used to replace the JSON file if you get a "No Data" error)"
  value       = grafana_data_source.bigquery.uid
}