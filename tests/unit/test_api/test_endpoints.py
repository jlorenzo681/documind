import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import documind.api.dependencies
from documind.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Cleanup dependency overrides after each test."""
    yield
    app.dependency_overrides = {}


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @patch("documind.db.base.get_engine")
    @patch("redis.asyncio.from_url")
    @patch("qdrant_client.QdrantClient")
    def test_health_check(self, _mock_qdrant, mock_redis, mock_get_engine, client):
        """Test the health check endpoint."""
        # Mock successful checks
        mock_conn = AsyncMock()
        mock_get_engine.return_value.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        mock_redis_client.ping = AsyncMock()
        mock_redis_client.aclose = AsyncMock()
        
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
        mock_db = AsyncMock()
        app.dependency_overrides[documind.api.dependencies.get_db_service] = lambda: mock_db
        mock_db.list_documents.return_value = []

        response = client.get("/documents")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_nonexistent_document(self, client):
        """Test getting a document that doesn't exist."""
        # Invalid format should be 400
        response = client.get("/documents/nonexistent-id")
        assert response.status_code == 400

        # Valid format but missing should be 404
        mock_db = AsyncMock()
        app.dependency_overrides[documind.api.dependencies.get_db_service] = lambda: mock_db
        mock_db.get_document.return_value = None

        response = client.get(f"/documents/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_delete_nonexistent_document(self, client):
        """Test deleting a document that doesn't exist."""
        # Invalid format should be 400
        response = client.delete("/documents/nonexistent-id")
        assert response.status_code == 400

        # Valid format but missing should be 404
        mock_db = AsyncMock()
        app.dependency_overrides[documind.api.dependencies.get_db_service] = lambda: mock_db
        mock_db.get_document.return_value = None

        response = client.delete(f"/documents/{uuid.uuid4()}")
        assert response.status_code == 404


class TestAnalysisEndpoints:
    """Tests for analysis endpoints."""

    def test_analysis_document_not_found(self, client):
        """Test starting analysis for nonexistent document."""
        mock_db = AsyncMock()
        app.dependency_overrides[documind.api.dependencies.get_db_service] = lambda: mock_db
        mock_db.get_document.return_value = None
        
        response = client.post(
            "/analysis",
            json={
                "document_id": str(uuid.uuid4()),
                "tasks": ["summarize"],
            },
        )
        assert response.status_code == 404

    def test_get_nonexistent_task_status(self, client):
        """Test getting status of nonexistent task."""
        mock_get_task = AsyncMock(return_value=None)
        with patch("documind.api.routes.analysis.get_task", mock_get_task):
            response = client.get("/analysis/nonexistent-task/status")
            assert response.status_code == 404


class TestResultsEndpoints:
    """Tests for results endpoints."""

    @patch("documind.api.routes.results.get_task", new_callable=AsyncMock)
    def test_get_nonexistent_results(self, mock_get_task, client):
        """Test getting results for nonexistent task."""
        mock_get_task.return_value = None
        response = client.get("/results/nonexistent-task")
        assert response.status_code == 404
