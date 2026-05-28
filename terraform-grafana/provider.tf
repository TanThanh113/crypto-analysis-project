terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"

    }
    grafana = {
      source  = "grafana/grafana"
      version = "~> 2.9"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
  
  impersonate_service_account = "terraform-sa@${var.project}.iam.gserviceaccount.com"
}

provider "grafana" {
  url  = var.grafana_url
  auth = var.grafana_auth
}