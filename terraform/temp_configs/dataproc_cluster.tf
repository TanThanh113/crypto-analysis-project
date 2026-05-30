resource "google_storage_bucket_object" "init_script" {
  name   = "scripts/init-script.sh"
  source = "${path.module}/../local_scripts/streaming/scripts/init-scripts.sh"
  bucket = google_storage_bucket.crypto_bucket.name
}

resource "google_dataproc_cluster" "crypto_cluster" {
  name   = var.dataproc_cluster_name
  region = var.region

  cluster_config {
    gce_cluster_config {
      tags             = ["flink-node"]
      subnetwork       = google_compute_subnetwork.crypto_subnet.id
      service_account  = google_service_account.flink_sa.email
      internal_ip_only = true

      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    }

    staging_bucket = google_storage_bucket.crypto_bucket.name
    temp_bucket    = google_storage_bucket.crypto_bucket.name

    initialization_action {
      script      = "gs://${google_storage_bucket.crypto_bucket.name}/${google_storage_bucket_object.init_script.name}"
      timeout_sec = 900
    }

    software_config {
      image_version = "2.2-debian12"

      override_properties = {
        "dataproc:dataproc.allow.zero.workers"        = "true"
        "dataproc:dataproc.conscrypt.provider.enable" = "false"

        "flink:taskmanager.memory.process.size"       = "20480m"
        "flink:jobmanager.memory.process.size"        = "2048m"
        "flink:taskmanager.memory.task.off-heap.size" = "6144m"
        "flink:taskmanager.memory.managed.fraction"   = "0.1"

        "flink:env.java.opts.all" = "--add-opens=java.base/sun.security.ssl=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.net=ALL-UNNAMED"

        "flink:taskmanager.numberOfTaskSlots" = "4"
      }
      optional_components = ["FLINK"]
    }

    master_config {
      num_instances = 1
      machine_type  = "e2-standard-8"
      disk_config {
        boot_disk_type    = "pd-standard"
        boot_disk_size_gb = 250
      }
    }

    endpoint_config {
      enable_http_port_access = true
    }

    lifecycle_config {
      idle_delete_ttl = "3600s"
    }
  }

  depends_on = [
    google_storage_bucket_object.init_script,
    google_storage_bucket_object.upload_jars,
    google_compute_router_nat.nat,
    google_project_iam_member.flink_sa_roles
  ]

  labels = {
    project = "crypto-analytics"
    env     = "dev"
  }
}