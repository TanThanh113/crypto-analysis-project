# Create a VPC
resource "google_compute_network" "crypto_vpc" {
  name                    = "crypto-analysis-vpc"
  auto_create_subnetworks = false
}

# Create a subnet private network
resource "google_compute_subnetwork" "crypto_subnet" {
  name                     = "crypto-analysis-subnet"
  ip_cidr_range            = "10.0.1.0/24"
  region                   = var.region
  network                  = google_compute_network.crypto_vpc.id
  private_ip_google_access = true
}

# Create a Router Cloud NAT
resource "google_compute_router" "router" {
  name    = "crypto-router"
  region  = var.region
  network = google_compute_network.crypto_vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "crypto-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}