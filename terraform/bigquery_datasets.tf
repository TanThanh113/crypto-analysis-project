resource "google_bigquery_dataset" "crypto_bigquery" {
  project                    = var.project
  dataset_id                 = var.bq_dataset_name
  location                   = var.location
  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "candlestick_1min" {
  dataset_id          = google_bigquery_dataset.crypto_bigquery.dataset_id
  table_id            = "candlestick_1min"
  project             = var.project
  deletion_protection = false

  time_partitioning {
    type          = "DAY"
    field         = "window_start"
    expiration_ms = 2592000000 # 30 days partition retention
  }

  clustering = ["symbol"]

  schema = <<EOF
[
  {"name": "window_start", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "window_end", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "symbol", "type": "STRING", "mode": "NULLABLE"},
  {"name": "trade_id", "type": "INT64", "mode": "NULLABLE"},
  {"name": "open_price", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "high_price", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "low_price", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "close_price", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "volume", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "VWAP", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "sma20", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "upper_band", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "lower_band", "type": "FLOAT64", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_table" "market_alerts" {
  dataset_id          = google_bigquery_dataset.crypto_bigquery.dataset_id
  table_id            = "market_alerts"
  project             = var.project
  deletion_protection = false

  time_partitioning {
    type          = "DAY"
    field         = "event_time"
    expiration_ms = 2592000000
  }

  clustering = ["symbol", "alert_type"]

  schema = <<EOF
[
  {"name": "alert_type", "type": "STRING", "mode": "NULLABLE"},
  {"name": "symbol", "type": "STRING", "mode": "NULLABLE"},
  {"name": "alert_message", "type": "STRING", "mode": "NULLABLE"},
  {"name": "event_time", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_table" "market_macro" {
  dataset_id          = google_bigquery_dataset.crypto_bigquery.dataset_id
  table_id            = "market_macro"
  project             = var.project
  deletion_protection = false

  time_partitioning {
    type          = "DAY"
    field         = "timestamp"
    expiration_ms = 2592000000
  }

  clustering = ["symbol"]

  schema = <<EOF
[
  {"name": "symbol", "type": "STRING", "mode": "NULLABLE"},
  {"name": "fear_greed_index", "type": "INT64", "mode": "NULLABLE"},
  {"name": "fear_greed_label", "type": "STRING", "mode": "NULLABLE"},
  {"name": "btc_dominance_pct", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_dataset" "dbt_quants_dev" {
  project                    = var.project
  dataset_id                 = "dbt_quants_dev"
  location                   = var.location
  delete_contents_on_destroy = true
}

resource "google_bigquery_dataset" "ml_outputs" {
  project                    = var.project
  dataset_id                 = "ml_outputs"
  location                   = var.location
  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "model_predictions" {
  dataset_id          = google_bigquery_dataset.ml_outputs.dataset_id
  table_id            = "model_predictions"
  project             = var.project
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "predicted_at"
  }

  clustering = ["symbol", "target_name", "model_name"]

  schema = <<EOF
[
  {"name": "prediction_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "model_name", "type": "STRING", "mode": "REQUIRED"},
  {"name": "model_version", "type": "STRING", "mode": "REQUIRED"},
  {"name": "predicted_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "hour_ts", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "symbol", "type": "STRING", "mode": "REQUIRED"},
  {"name": "target_name", "type": "STRING", "mode": "REQUIRED"},
  {"name": "predicted_class", "type": "STRING", "mode": "NULLABLE"},
  {"name": "prob_up", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "prob_down", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "prob_flat", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "predicted_return_4h", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "confidence_score", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "signal", "type": "STRING", "mode": "NULLABLE"},
  {"name": "model_artifact_uri", "type": "STRING", "mode": "NULLABLE"},
  {"name": "feature_available_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF
}

resource "google_bigquery_table" "model_metrics" {
  dataset_id          = google_bigquery_dataset.ml_outputs.dataset_id
  table_id            = "model_metrics"
  project             = var.project
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "evaluated_at"
  }

  clustering = ["model_name", "target_name", "split_name"]

  schema = <<EOF
[
  {"name": "model_name", "type": "STRING", "mode": "REQUIRED"},
  {"name": "model_version", "type": "STRING", "mode": "REQUIRED"},
  {"name": "trained_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "evaluated_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "target_name", "type": "STRING", "mode": "REQUIRED"},
  {"name": "split_name", "type": "STRING", "mode": "REQUIRED"},

  {"name": "row_count", "type": "INT64", "mode": "NULLABLE"},
  {"name": "accuracy", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "precision_macro", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "recall_macro", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "f1_macro", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "auc_ovr", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "log_loss", "type": "FLOAT64", "mode": "NULLABLE"},
  {"name": "brier_score", "type": "FLOAT64", "mode": "NULLABLE"},

  {"name": "feature_table", "type": "STRING", "mode": "NULLABLE"},
  {"name": "training_table", "type": "STRING", "mode": "NULLABLE"},
  {"name": "model_artifact_uri", "type": "STRING", "mode": "NULLABLE"},
  {"name": "git_sha", "type": "STRING", "mode": "NULLABLE"},
  {"name": "run_id", "type": "STRING", "mode": "NULLABLE"},

  {"name": "model_key", "type": "STRING", "mode": "NULLABLE"},
  {"name": "model_family", "type": "STRING", "mode": "NULLABLE"},
  {"name": "algorithm", "type": "STRING", "mode": "NULLABLE"},
  {"name": "problem_type", "type": "STRING", "mode": "NULLABLE"}
]
EOF
}