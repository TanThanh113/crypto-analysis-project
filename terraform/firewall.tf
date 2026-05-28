resource "google_compute_firewall" "allow_iap_ssh" {
  name    = "allow-iap-ssh"
  network = google_compute_network.crypto_vpc.name

  # Google IAP's fixed IP
  source_ranges = ["35.235.240.0/20"]

  allow {
    protocol = "tcp"
  }
  allow {
    protocol = "udp"
  }
  allow {
    protocol = "icmp"
  }

  target_tags = ["flink-node"]
}