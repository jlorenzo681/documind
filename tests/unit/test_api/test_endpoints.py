"""Unit tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from documind.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data

    def test_readiness_check(self, client):
        """Test the readiness probe."""
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_liveness_check(self, client):
        """Test the liveness probe."""
        response = client.get("/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestDocumentEndpoints:
    """Tests for document management endpoints."""

    def test_list_documents_empty(self, client):
        """Test listing documents when none exist."""
        response = client.get("/documents")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_nonexistent_document(self, client):
        """Test getting a document that doesn't exist."""
        response = client.get("/documents/nonexistent-id")
        assert response.status_code == 404

    def test_delete_nonexistent_document(self, client):
        """Test deleting a document that doesn't exist."""
        response = client.delete("/documents/nonexistent-id")
        assert response.status_code == 404


class TestAnalysisEndpoints:
    """Tests for analysis endpoints."""

    def test_analysis_document_not_found(self, client):
        """Test starting analysis for nonexistent document."""
        response = client.post(
            "/analyze",
            json={
                "document_id": "nonexistent-id",
                "tasks": ["summarize"],
            },
        )
        assert response.status_code == 404

    def test_get_nonexistent_task_status(self, client):
        """Test getting status of nonexistent task."""
        response = client.get("/analyze/nonexistent-task/status")
        assert response.status_code == 404


class TestResultsEndpoints:
    """Tests for results endpoints."""

    def test_get_nonexistent_results(self, client):
        """Test getting results for nonexistent task."""
        response = client.get("/results/nonexistent-task")
        assert response.status_code == 404
