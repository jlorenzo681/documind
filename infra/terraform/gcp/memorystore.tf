# DocuMind Memorystore for Redis Configuration

resource "google_redis_instance" "main" {
  name               = "${var.app_name}-redis"
  tier               = var.environment == "prod" ? "STANDARD_HA" : "BASIC"
  memory_size_gb     = var.environment == "prod" ? 5 : 1
  region             = var.region
  redis_version      = "REDIS_7_0"
  display_name       = "DocuMind Redis Cache"
  authorized_network = google_compute_network.main.id

  # High availability settings (for STANDARD_HA tier)
  replica_count            = var.environment == "prod" ? 1 : 0
  read_replicas_mode       = var.environment == "prod" ? "READ_REPLICAS_ENABLED" : "READ_REPLICAS_DISABLED"
  
  # Security
  auth_enabled       = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  # Maintenance
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 2
        minutes = 0
      }
    }
  }

  # Persistence (for STANDARD_HA tier)
  persistence_config {
    persistence_mode    = var.environment == "prod" ? "RDB" : "DISABLED"
    rdb_snapshot_period = var.environment == "prod" ? "ONE_HOUR" : null
  }

  depends_on = [google_project_service.required_apis]
}

# Outputs
output "redis_host" {
  description = "Redis host"
  value       = google_redis_instance.main.host
}

output "redis_port" {
  description = "Redis port"
  value       = google_redis_instance.main.port
}

output "redis_auth_string" {
  description = "Redis auth string"
  value       = google_redis_instance.main.auth_string
  sensitive   = true
}
