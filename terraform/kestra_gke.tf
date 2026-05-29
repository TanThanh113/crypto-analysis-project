# --- Create GKE Autopilot Cluster for Kestra ---
resource "google_container_cluster" "kestra_autopilot" {
  name     = var.kestra_cluster_name
  location = var.region

  # This involves managing nodes, automated scaling, and operational costs for Google.
  enable_autopilot = true

  # Put it into the VPC and subnetwork
  network    = google_compute_network.crypto_vpc.id
  subnetwork = google_compute_subnetwork.crypto_subnet.id

  # This helps prevent accidental deletion of clusters.
  deletion_protection = true

  # Subscribe to the automatic update channel for GKE.
  release_channel {
    channel = "REGULAR"
  }

  # Enable the "VPC-native" routing feature. When left blank, Google will automatically allocate secondary IP ranges to Pods and Services.
  ip_allocation_policy {}

  # Enable Workload Identity
  workload_identity_config {
    workload_pool = "${var.project}.svc.id.goog"
  }

  private_cluster_config {
    enable_private_nodes    = true  # Ensure that the servers running your application (Worker Nodes) do not have public IP addresses.
    enable_private_endpoint = false # The central server managing the cluster (Control Plane) is still allowed to have a public IP address.
  }

  addons_config {
    gcs_fuse_csi_driver_config {
      enabled = true # Allows direct mounting of Google Cloud Storage buckets into Pods.
    }

    gce_persistent_disk_csi_driver_config {
      enabled = true # Enable the standard driver (CSI) so Kubernetes can automatically create and manage virtual hard drives (Google Persistent Disks).
    }
  }

  depends_on = [
    google_project_service.kestra_required_services
  ]
}
