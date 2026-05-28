# =======================================================
# PHẦN 1: GOOGLE CLOUD - TẠO SERVICE ACCOUNT & KEY
# =======================================================

resource "google_service_account" "grafana_reader" {
  account_id   = var.grafana_sa_account_id
  display_name = "Grafana BigQuery Reader SA"
}

resource "google_project_iam_member" "grafana_bq_viewer" {
  project = var.project
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.grafana_reader.email}"
}

resource "google_project_iam_member" "grafana_bq_job_user" {
  project = var.project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.grafana_reader.email}"
}

resource "google_service_account_key" "grafana_key" {
  service_account_id = google_service_account.grafana_reader.name
}

# Bóc tách file JSON Key ngay trong RAM (Không lưu ra ổ cứng để bảo mật)
locals {
  sa_key_json = jsondecode(base64decode(google_service_account_key.grafana_key.private_key))
}


# =======================================================
# PHẦN 2: GRAFANA - TỰ ĐỘNG CÀI DATA SOURCE & DASHBOARD
# =======================================================

# Tự động add BigQuery Data Source bằng Key vừa tạo
resource "grafana_data_source" "bigquery" {
  type = "grafana-bigquery-datasource"
  name = "GCP-BigQuery-Crypto"
  uid  = "gcp_bq_crypto_uid" # ID tĩnh để file JSON dễ dàng nhận diện

  json_data_encoded = jsonencode({
    authenticationType = "jwt"
    clientEmail        = local.sa_key_json.client_email
    defaultProject     = var.project
    tokenUri           = "https://oauth2.googleapis.com/token"
  })

  # Bơm thẳng Private Key vào vùng bảo mật của Grafana
  secure_json_data_encoded = jsonencode({
    privateKey = local.sa_key_json.private_key
  })

  depends_on = [google_project_iam_member.grafana_bq_viewer]
}

# Tạo thư mục chứa Dashboard cho gọn gàng
resource "grafana_folder" "crypto_folder" {
  title = "Crypto Analytics"
}

# Deploy Dashboard JSON
resource "grafana_dashboard" "crypto_main_dashboard" {
  # Đọc nội dung file JSON của bạn
  config_json = file("${path.module}/dashboards/crypto_main.json")
  folder      = grafana_folder.crypto_folder.id
  overwrite   = true

  depends_on = [grafana_data_source.bigquery]
}


# =======================================================
# PHẦN 3: KẾT QUẢ TRẢ VỀ MÀN HÌNH
# =======================================================

output "grafana_dashboard_url" {
  description = "🎉 LINK TRUY CẬP TRỰC TIẾP VÀO DASHBOARD 🎉"
  value       = "${grafana_dashboard.crypto_main_dashboard.url}"
}

output "grafana_datasource_uid" {
  description = "UID của BigQuery Data Source (Dùng để thay vào file JSON nếu bị lỗi No Data)"
  value       = grafana_data_source.bigquery.uid
}