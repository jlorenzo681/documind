# DocuMind Cloud Storage Configuration

# Storage bucket for documents
resource "google_storage_bucket" "documents" {
  name          = "${var.app_name}-documents-${var.environment}"
  location      = var.region
  force_destroy = var.environment != "prod"

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 3
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  encryption {
    default_kms_key_name = null # Uses Google-managed encryption by default
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# IAM for bucket
resource "google_storage_bucket_iam_binding" "documents_private" {
  bucket = google_storage_bucket.documents.name
  role   = "roles/storage.objectViewer"
  members = [
    "serviceAccount:${google_service_account.cloudrun.email}",
  ]
}

# Outputs
output "storage_bucket_name" {
  description = "Cloud Storage bucket name"
  value       = google_storage_bucket.documents.name
}

output "storage_bucket_url" {
  description = "Cloud Storage bucket URL"
  value       = google_storage_bucket.documents.url
}
