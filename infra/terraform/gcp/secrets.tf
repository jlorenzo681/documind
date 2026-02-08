# DocuMind Secret Manager Configuration

# API Keys Secret
resource "google_secret_manager_secret" "api_keys" {
  secret_id = "${var.app_name}-api-keys"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

# Placeholder secret version (update manually or via CI/CD)
resource "google_secret_manager_secret_version" "api_keys" {
  secret = google_secret_manager_secret.api_keys.id
  secret_data = jsonencode({
    openai_api_key     = "REPLACE_WITH_ACTUAL_KEY"
    anthropic_api_key  = "REPLACE_WITH_ACTUAL_KEY"
  })

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Outputs
output "secret_manager_api_keys_id" {
  description = "Secret Manager API keys secret ID"
  value       = google_secret_manager_secret.api_keys.secret_id
}
