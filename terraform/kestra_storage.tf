# --- Create GCS Bucket for Kestra internal storage ---
resource "google_storage_bucket" "kestra_internal_storage" {
  name          = var.kestra_internal_storage_bucket_name
  location      = var.region
  force_destroy = false
  storage_class = "STANDARD"

  # Enable uniform bucket level access so that all users can access the bucket
  uniform_bucket_level_access = true

  # Enable versioning so that we can see the old versions of our data
  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30 # Automatically delete objects older than 30 days
    }

    action {
      type = "Delete"
    }
  }

  labels = {
    app         = "kestra"
    environment = "production"
    managed_by  = "terraform"
  }
}
