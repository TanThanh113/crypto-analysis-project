# --- Create Secret Manager Secret for Kestra DB Password ---

# Create a password box named "kestra-db-password"
resource "google_secret_manager_secret" "kestra_db_password" {
  secret_id = "kestra-db-password"

  # Save the box to multiple locations to avoid data loss in case of power outages.
  replication {
    auto {}
  }

  labels = {
    app        = "kestra"
    managed_by = "terraform"
  }

  depends_on = [
    google_project_service.kestra_required_services
  ]
}

# Put the passwords (database) in that box(kestra_cloudsql.tf creates a random password)
resource "google_secret_manager_secret_version" "kestra_db_password" {
  secret      = google_secret_manager_secret.kestra_db_password.id
  secret_data = random_password.kestra_db_password.result
}

# Use a loop to insert the API keys
locals {
  kestra_runtime_secret_names = [
    "kestra-telegram-api-id",
    "kestra-telegram-api-hash",
    "kestra-telegram-session-string",
    "kestra-tiingo-api-key",
    "kestra-coinalyze-api-key",
    "kestra-coingecko-api-key",
    "kestra-arkham-api-key",

    "kestra-gcp-project-id",
    "kestra-gcp-bucket-name",
    "kestra-gcp-location",

    "kestra-basic-auth-username",
    "kestra-basic-auth-password",

    "kestra-slack-webhook-url",
  ]
}

resource "google_secret_manager_secret" "kestra_runtime_secrets" {
  for_each = toset(local.kestra_runtime_secret_names)

  secret_id = each.value

  replication {
    auto {}
  }

  labels = {
    app        = "kestra"
    managed_by = "terraform"
  }

  depends_on = [
    google_project_service.kestra_required_services
  ]
}

resource "google_secret_manager_secret_iam_member" "kestra_runtime_secrets_accessor" {
  for_each = google_secret_manager_secret.kestra_runtime_secrets

  project   = var.project
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"

  member = "principal://iam.googleapis.com/projects/${data.google_project.current.number}/locations/global/workloadIdentityPools/${var.project}.svc.id.goog/subject/ns/${var.kestra_namespace}/sa/${var.kestra_kubernetes_service_account}"

  depends_on = [
    google_container_cluster.kestra_autopilot
  ]
}