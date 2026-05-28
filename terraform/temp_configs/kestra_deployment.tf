resource "google_compute_firewall" "kestra_ui_firewall" {
    provider = google.impersonated
    name     = "allow-kestra-ui"
    network  = "default
    allow {
        protocol = "tcp"
        ports    = ["8080"]
    }
    source_ranges = ["0.0.0.0/0"]
    target_tags   = ["kestra-server"]
}
resource "google_compute_instance" "kestra_vm" {
    provider     = google.impersonated
    name         = var.kestra_name
    machine_type = "e2-standard-2" # 2 vCPU, 8GB RAM
    zone         = "${var.region}-a"

    tags = ["kestra-server"]

    boot_disk {
        initialize_params {
            image = "debian-cloud/debian-11"
            size  = 30 # 30GB
        }
    }

    network_interface {
        network = "default"
        access_config {
      
        }
    }

    metadata_startup_script = <<-EOT
        apt-get update
        apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
        curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

        mkdir -p /opt/kestra
        cat <<EOF > /opt/kestra/docker-compose.yml
        version: '3'
        services:
            kestra:
                image: kestra/kestra:latest-full
                command: server standalone
                ports:
                    - "8080:8080"
                environment:
                    KESTRA_CONFIGURATION: |
                        kestra:
                            server:
                                port: 8080
        EOF
        cd /opt/kestra
        docker compose up -d
    EOT

    service_account {
        email  = var.service_account_email
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    }
}