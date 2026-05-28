variable "project" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Vùng triển khai (Region)"
  type        = string
  default     = "asia-southeast1"
}

variable "grafana_sa_account_id" {
  description = "Tên Service Account cấp cho Grafana"
  type        = string
  default     = "grafana-bq-reader"
}

variable "grafana_url" {
  description = "Đường dẫn tới Grafana"
  type        = string
  default     = "http://localhost:3000"
}

variable "grafana_auth" {
  description = "Tài khoản đăng nhập Grafana (user:pass)"
  type        = string
  default     = "admin:admin"
}