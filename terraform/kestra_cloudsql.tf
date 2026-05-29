# --- Create Cloud SQL instance for Kestra ---

# Automatically create a private random password for the Cloud SQL instance
resource "random_password" "kestra_db_password" {
  length  = 32
  special = true
}

# Create a private network for the Cloud SQL instance(16 IPs)
resource "google_compute_global_address" "kestra_private_service_range" {
  name          = "kestra-private-service-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.crypto_vpc.id

  depends_on = [
    google_project_service.kestra_required_services
  ]
}

# Set up VPC Peering
resource "google_service_networking_connection" "kestra_private_vpc_connection" {
  network                 = google_compute_network.crypto_vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.kestra_private_service_range.name]

  depends_on = [
    google_project_service.kestra_required_services
  ]
}

# Create a Cloud SQL instance
resource "google_sql_database_instance" "kestra_postgres" {
  name             = var.kestra_cloudsql_instance_name
  database_version = "POSTGRES_15"
  region           = var.region

  deletion_protection = true # Prevent accidental deletion of the instance

  settings {
    tier              = var.kestra_cloudsql_tier
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = 20
    disk_autoresize   = true # If Kestra runs heavily and the data usage exceeds 20GB, Google will automatically expand the hard drive.

    # Auto save backups every day at 18:00
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "18:00"
    }

    # Enable IPv4 access
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.crypto_vpc.id
    }

    # The maximum number of connections that the database allows to be opened simultaneously.
    database_flags {
      name  = "max_connections"
      value = "200"
    }
  }

  depends_on = [
    google_service_networking_connection.kestra_private_vpc_connection
  ]
}

# Create a Cloud SQL database
resource "google_sql_database" "kestra_database" {
  name     = var.kestra_cloudsql_database_name
  instance = google_sql_database_instance.kestra_postgres.name
}

# Auto password rotation for the Cloud SQL database
resource "google_sql_user" "kestra_user" {
  name     = var.kestra_cloudsql_user_name
  instance = google_sql_database_instance.kestra_postgres.name
  password = random_password.kestra_db_password.result
}
