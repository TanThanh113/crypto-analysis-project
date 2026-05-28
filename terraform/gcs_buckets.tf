resource "google_storage_bucket" "crypto_bucket" {
  name          = var.gcs_bucket_name
  location      = var.location
  force_destroy = true
  storage_class = var.gcs_storage_class

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }
}

variable "jar_files" {
  default = [
    "flink-sql-connector-kafka-3.0.1-1.17.jar",
    "flink-1.17-connector-bigquery-1.1.0-shaded.jar",
    "flink-parquet-1.17.2.jar",
    "parquet-hadoop-bundle-1.12.3.jar",
    "iceberg-flink-runtime-1.17-1.5.0.jar"
  ]
}

resource "google_storage_bucket_object" "upload_jars" {
  for_each = toset(var.jar_files)
  name     = "flink-jars/${each.value}"
  source   = "${path.module}/../local_scripts/streaming/lib/${each.value}"
  bucket   = google_storage_bucket.crypto_bucket.name
}

resource "google_storage_bucket_object" "upload_python_dynamic" {
  for_each = fileset("${path.module}/../local_scripts/streaming/logic_crypto_streaming", "**/*")

  name   = "scripts/${each.value}"
  source = "${path.module}/../local_scripts/streaming/logic_crypto_streaming/${each.value}"
  bucket = google_storage_bucket.crypto_bucket.name
}

resource "google_storage_bucket_object" "ml_artifacts_prefix" {
  name    = "ml-artifacts/crypto_direction_lgbm_v1/.keep"
  content = "Reserved prefix for crypto ML model artifacts."
  bucket  = google_storage_bucket.crypto_bucket.name
}

output "ml_artifact_gcs_uri" {
  value = "gs://${google_storage_bucket.crypto_bucket.name}/ml-artifacts/crypto_direction_lgbm_v1"
}