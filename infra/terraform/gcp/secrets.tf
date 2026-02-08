# DocuMind Secret Manager Configuration

# OpenAI API Key
resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "${var.app_name}-openai-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  secret      = google_secret_manager_secret.openai_api_key.id
  secret_data = "REPLACE_WITH_ACTUAL_KEY"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Anthropic API Key
resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "${var.app_name}-anthropic-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "anthropic_api_key" {
  secret      = google_secret_manager_secret.anthropic_api_key.id
  secret_data = "REPLACE_WITH_ACTUAL_KEY"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Groq API Key
resource "google_secret_manager_secret" "groq_api_key" {
  secret_id = "${var.app_name}-groq-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "groq_api_key" {
  secret      = google_secret_manager_secret.groq_api_key.id
  secret_data = "REPLACE_WITH_ACTUAL_KEY"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Qdrant API Key
resource "google_secret_manager_secret" "qdrant_api_key" {
  secret_id = "${var.app_name}-qdrant-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "qdrant_api_key" {
  secret      = google_secret_manager_secret.qdrant_api_key.id
  secret_data = "REPLACE_WITH_ACTUAL_KEY"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# LangSmith API Key
resource "google_secret_manager_secret" "langsmith_api_key" {
  secret_id = "${var.app_name}-langsmith-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "langsmith_api_key" {
  secret      = google_secret_manager_secret.langsmith_api_key.id
  secret_data = "REPLACE_WITH_ACTUAL_KEY"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# App Secret Key
resource "google_secret_manager_secret" "app_secret_key" {
  secret_id = "${var.app_name}-secret-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "app_secret_key" {
  secret      = google_secret_manager_secret.app_secret_key.id
  secret_data = "REPLACE_WITH_ACTUAL_KEY"

  lifecycle {
    ignore_changes = [secret_data]
  }
}


