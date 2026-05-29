output "kestra_gke_cluster_name" {
  value = google_container_cluster.kestra_autopilot.name
}

output "kestra_gke_cluster_location" {
  value = google_container_cluster.kestra_autopilot.location
}

output "kestra_gcp_service_account_email" {
  value = google_service_account.kestra_gke_sa.email
}

output "kestra_internal_storage_bucket" {
  value = google_storage_bucket.kestra_internal_storage.name
}

output "kestra_cloudsql_instance_connection_name" {
  value = google_sql_database_instance.kestra_postgres.connection_name
}

output "kestra_cloudsql_private_ip" {
  value = google_sql_database_instance.kestra_postgres.private_ip_address
}

output "kestra_cloudsql_database" {
  value = google_sql_database.kestra_database.name
}

output "kestra_cloudsql_user" {
  value = google_sql_user.kestra_user.name
}
