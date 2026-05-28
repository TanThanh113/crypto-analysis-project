# Enable the Artifact Registry API for your project (if not already enabled).
resource "google_project_service" "artifact_registry" {
  project            = var.project
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

# Create a Docker image repository.
resource "google_artifact_registry_repository" "crypto_docker" {
  project       = var.project
  location      = var.location
  repository_id = var.artifact_registry_repo_id
  description   = "Docker images for crypto analytics batch, dbt, and ML workloads."
  format        = "DOCKER"

  cleanup_policy_dry_run = false

  # Always KEEP the 10 most recent versions of the images.
  cleanup_policies {
    id     = "keep-recent-images"
    action = "KEEP"

    most_recent_versions {
      keep_count = 10
    }
  }

  # Automatically DELETE "untagged" images (old images that are overwritten by new images when you push duplicates) if they are older than 14 days.
  cleanup_policies {
    id     = "delete-old-untagged-images"
    action = "DELETE"

    condition {
      tag_state  = "UNTAGGED"
      older_than = "1209600s" # 14 days
    }
  }

  # You must enable the service in step 1 before proceeding to create this storage.
  depends_on = [
    google_project_service.artifact_registry
  ]
}

# Output the Artifact Registry repository ID.
output "artifact_registry_repository_id" {
  value = google_artifact_registry_repository.crypto_docker.repository_id
}

# Output the Artifact Registry location(Data Center)
output "artifact_registry_location" {
  value = google_artifact_registry_repository.crypto_docker.location
}

# Output the Artifact Registry Docker submission path
output "artifact_registry_docker_base_url" {
  value = "${var.location}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.crypto_docker.repository_id}"
}

# Output the Artifact Registry Docker batch image URI
output "crypto_batch_image_uri" {
  value = "${var.location}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.crypto_docker.repository_id}/crypto-batch:latest"
}

# Output the Artifact Registry Docker dbt image URI
output "crypto_dbt_image_uri" {
  value = "${var.location}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.crypto_docker.repository_id}/crypto-dbt:latest"
}

# Output the Artifact Registry Docker ML image URI
output "crypto_ml_image_uri" {
  value = "${var.location}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.crypto_docker.repository_id}/crypto-ml:latest"
}