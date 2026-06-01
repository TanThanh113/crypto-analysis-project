# --- BigQuery Table for Pipeline Health Check Results ---
# This table is written by:
# local_scripts/batch/pipeline_health_check.py
#
# It is intentionally managed by Terraform instead of being auto-created by Python.

resource "google_bigquery_table" "pipeline_health_check_results" {
  project    = var.project
  dataset_id = google_bigquery_dataset.ml_outputs.dataset_id
  table_id   = "pipeline_health_check_results"

  # Keep consistent with the current project style.
  # For a strict production environment, set this to true.
  deletion_protection = false

  description = "Append-only pipeline health check results written by the GKE monitoring flow."

  time_partitioning {
    type          = "DAY"
    field         = "check_ts"
    expiration_ms = 15552000000
  }

  clustering = [
    "severity",
    "success",
    "check_id"
  ]

  schema = <<EOF
[
  {
    "name": "check_ts",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "UTC timestamp when the pipeline health check was executed."
  },
  {
    "name": "check_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Unique health check identifier, for example dashboard_data_freshness."
  },
  {
    "name": "check_type",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Health check type, for example data_freshness_mart, table_non_empty, ge_latest_audit, prediction_freshness."
  },
  {
    "name": "severity",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Failure severity: critical or warning."
  },
  {
    "name": "success",
    "type": "BOOLEAN",
    "mode": "REQUIRED",
    "description": "Whether the health check passed."
  },
  {
    "name": "metric_value",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Actual measured value at check time."
  },
  {
    "name": "threshold",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Expected threshold used for comparison."
  },
  {
    "name": "message",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Human-readable health check result message."
  },
  {
    "name": "details_json",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Structured JSON metadata for debugging."
  }
]
EOF
}
