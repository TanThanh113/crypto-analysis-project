variable "project" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Deployment Region"
  type        = string
  default     = "asia-southeast1"
}

variable "grafana_sa_account_id" {
  description = "The Service Account name assigned to Grafana"
  type        = string
  default     = "grafana-bq-reader"
}

variable "grafana_url" {
  description = "Directions to Grafana"
  type        = string
  default     = "http://localhost:3000"
}

variable "grafana_auth" {
  description = "Grafana login account (user:pass)"
  type        = string
  default     = "admin:admin"
}