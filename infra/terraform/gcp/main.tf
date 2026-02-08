# GCP Infrastructure for DocuMind
# Terraform configuration for Cloud Run deployment

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "gcs" {
    bucket = "documind-terraform-state-jesuslorenzo-5127d"
    prefix = "prod/terraform.tfstate"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Variables
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "documind"
}

variable "container_port" {
  description = "Container port"
  type        = number
  default     = 8000
}

variable "domain_name" {
  description = "Custom domain name"
  type        = string
  default     = "api.documind.example.com"
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "secretmanager.googleapis.com",
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "vpcaccess.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# VPC Network
resource "google_compute_network" "main" {
  name                    = "${var.app_name}-vpc"
  auto_create_subnetworks = false

  depends_on = [google_project_service.required_apis]
}

resource "google_compute_subnetwork" "main" {
  name          = "${var.app_name}-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.main.id

  private_ip_google_access = true
}

# VPC Access Connector for Cloud Run
resource "google_vpc_access_connector" "main" {
  name          = "${var.app_name}-connector"
  region        = var.region
  network       = google_compute_network.main.name
  ip_cidr_range = "10.8.0.0/28"

  depends_on = [google_project_service.required_apis]
}

# Artifact Registry Repository
resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = var.app_name
  description   = "Docker repository for DocuMind"
  format        = "DOCKER"

  depends_on = [google_project_service.required_apis]
}

# Service Account for Cloud Run
resource "google_service_account" "cloudrun" {
  account_id   = "${var.app_name}-cloudrun"
  display_name = "Cloud Run Service Account"
}

# IAM bindings for service account
resource "google_project_iam_member" "cloudrun_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

resource "google_project_iam_member" "cloudrun_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

resource "google_storage_bucket_iam_member" "cloudrun_storage" {
  bucket = google_storage_bucket.documents.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloudrun.email}"
}

# Cloud Run Service
resource "google_cloud_run_v2_service" "main" {
  name     = "${var.app_name}-api"
  location = var.region

  template {
    service_account = google_service_account.cloudrun.email

    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    scaling {
      min_instance_count = var.environment == "prod" ? 1 : 0
      max_instance_count = var.environment == "prod" ? 10 : 3
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}/${var.app_name}:latest"

      ports {
        container_port = var.container_port
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      env {
        name = "OPENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_keys.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}"
      }

      startup_probe {
        http_get {
          path = "/health"
          port = var.container_port
        }
        initial_delay_seconds = 10
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = var.container_port
        }
        initial_delay_seconds = 30
        timeout_seconds       = 5
        period_seconds        = 30
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.required_apis,
    google_sql_database_instance.main,
    google_redis_instance.main
  ]
}

# Allow unauthenticated access (configure as needed)
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.main.name
  location = google_cloud_run_v2_service.main.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Load Balancer components
resource "google_compute_global_address" "main" {
  name = "${var.app_name}-lb-ip"
}

resource "google_compute_region_network_endpoint_group" "main" {
  name                  = "${var.app_name}-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = google_cloud_run_v2_service.main.name
  }
}

resource "google_compute_backend_service" "main" {
  name = "${var.app_name}-backend"

  backend {
    group = google_compute_region_network_endpoint_group.main.id
  }

  log_config {
    enable = true
  }
}

resource "google_compute_url_map" "main" {
  name            = "${var.app_name}-lb"
  default_service = google_compute_backend_service.main.id
}

resource "google_compute_target_https_proxy" "main" {
  name             = "${var.app_name}-https-proxy"
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.main.id]
}

resource "google_compute_global_forwarding_rule" "https" {
  name       = "${var.app_name}-https"
  target     = google_compute_target_https_proxy.main.id
  port_range = "443"
  ip_address = google_compute_global_address.main.address
}

resource "google_compute_target_http_proxy" "main" {
  name    = "${var.app_name}-http-proxy"
  url_map = google_compute_url_map.main.id
}

resource "google_compute_global_forwarding_rule" "http" {
  name       = "${var.app_name}-http"
  target     = google_compute_target_http_proxy.main.id
  port_range = "80"
  ip_address = google_compute_global_address.main.address
}

# SSL Certificate
resource "google_compute_managed_ssl_certificate" "main" {
  name = "${var.app_name}-cert"

  managed {
    domains = [var.domain_name]
  }
}

# Outputs
output "cloud_run_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.main.uri
}

output "load_balancer_ip" {
  description = "Load Balancer IP address"
  value       = google_compute_global_address.main.address
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
}
