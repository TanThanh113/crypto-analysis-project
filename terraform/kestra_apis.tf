# --- Enable required GKE Autopilot(K8s) APIs ---
locals {
  kestra_required_services = [
    "container.googleapis.com",         # API for running GKE (Google Kubernetes Engine)
    "sqladmin.googleapis.com",          # API for managing Cloud SQL
    "secretmanager.googleapis.com",     # API for managing Secret Manager
    "servicenetworking.googleapis.com", # API for connecting to the local network.
    "iamcredentials.googleapis.com"     # Identity management API
  ]
}

resource "google_project_service" "kestra_required_services" {
  for_each = toset(local.kestra_required_services)

  project            = var.project
  service            = each.value
  disable_on_destroy = false
}
