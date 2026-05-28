# Enable the BigLake API for your project (if not already enabled).
resource "google_project_service" "biglake_api" {
  project            = var.project
  service            = "biglake.googleapis.com"
  disable_on_destroy = false
}

# The "Escape Hatch" trick: Using gcloud to create a new type of catalog.
resource "null_resource" "create_iceberg_catalog" {
  depends_on = [google_project_service.biglake_api]

  # Put ALL necessary variables into triggers.
  triggers = {
    catalog_name = var.catalog_name
    project      = var.project
  }

  # Since using `var` for the command will not be understood, we will use `self` here.
  provisioner "local-exec" {
    command = <<EOT
      gcloud biglake iceberg catalogs create ${self.triggers.catalog_name} \
        --project ${self.triggers.project} \
        --catalog-type gcs-bucket \
        --credential-mode end-user || true
    EOT
  }

  # Option: Automatically clean up (delete) the catalog when you type 'terraform destroy'.
  provisioner "local-exec" {
    when    = destroy
    command = <<EOT
      gcloud biglake iceberg catalogs delete ${self.triggers.catalog_name} \
        --project ${self.triggers.project} \
        --quiet || true
    EOT
  }
}