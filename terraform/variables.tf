# --- General GCP Configuration ---
variable "project" {
  type        = string
  description = "The Google Cloud Project ID"
}

variable "region" {
  type        = string
  default     = "asia-southeast1"
  description = "The deployment region for resources (Singapore is recommended to minimize latency)"
}

# --- Kestra VM Configuration ---
variable "kestra_name" {
  type        = string
  default     = "kestra-orchestrator-vm"
  description = "The name of the Virtual Machine running Kestra"
}

# --- Storage Configuration (GCS) ---
variable "gcs_bucket_name" {
  type        = string
  description = "Globally unique name for the GCS Bucket"
}

variable "gcs_storage_class" {
  type        = string
  default     = "STANDARD"
  description = "The storage class for GCS (STANDARD is used for data requiring immediate processing)"
}

variable "location" {
  type        = string
  default     = "asia-southeast1"
  description = "The geographic location for GCS and BigQuery resources"
}

# --- Warehouse Configuration (BigQuery) ---
variable "bq_dataset_name" {
  type        = string
  description = "The name of the BigQuery Dataset for the Crypto project"
}

# --- Dataproc Configuration ---
variable "dataproc_cluster_name" {
  type        = string
  description = "The name of the Dataproc cluster used for processing streaming data"
}

# --- Terraform Configuration ---
variable "service_account" {
  type        = string
  description = "The Service Account used for Terraform"
}

# --- BigLake Configuration ---
variable "user_email" {
  type        = string
  description = "The email address of the user used for impersonation"
}

variable "catalog_name" {
  type        = string
  description = "The name of the Iceberg Catalog used for the crypto project"
}

# --- Artifact Registry Configuration ---
variable "artifact_registry_repo_id" {
  description = "Artifact Registry Docker repository ID for crypto analytics images."
  type        = string
}

#-- GitHub Actions Configuration --
variable "github_owner" {
  description = "GitHub owner or organization name."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name."
  type        = string
}

# --- Kestra on GKE Configuration ---

variable "kestra_cluster_name" {
  description = "GKE Autopilot cluster name for Kestra."
  type        = string
}

variable "kestra_namespace" {
  description = "Kubernetes namespace for Kestra."
  type        = string
}

variable "kestra_kubernetes_service_account" {
  description = "Kubernetes service account name used by Kestra pods."
  type        = string
}

variable "kestra_gcp_service_account_id" {
  description = "Google service account ID used by Kestra through Workload Identity."
  type        = string
}

variable "kestra_internal_storage_bucket_name" {
  description = "GCS bucket for Kestra internal storage."
  type        = string
}

variable "kestra_cloudsql_instance_name" {
  description = "Cloud SQL PostgreSQL instance name for Kestra."
  type        = string
}

variable "kestra_cloudsql_database_name" {
  description = "Cloud SQL database name for Kestra."
  type        = string
}

variable "kestra_cloudsql_user_name" {
  description = "Cloud SQL username for Kestra."
  type        = string
}

variable "kestra_cloudsql_tier" {
  description = "Cloud SQL machine tier for Kestra PostgreSQL."
  type        = string
}
