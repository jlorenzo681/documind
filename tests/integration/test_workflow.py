import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import documind
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


@pytest.fixture
def sample_pdf():
    """Create a mock PDF file."""
    content = b"%PDF-1.4 test content"
    return io.BytesIO(content)


class TestDocumentWorkflow:
    """Integration tests for complete document workflow."""

    @patch("documind.db.base.get_engine")
    @patch("redis.asyncio.from_url")
    @patch("qdrant_client.QdrantClient")
    def test_health_check(self, _mock_qdrant, mock_redis, mock_get_engine, client):
        """Test API is healthy."""
        # Mock successful checks
        mock_conn = AsyncMock()
        mock_get_engine.return_value.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        mock_redis_client.ping = AsyncMock()
        mock_redis_client.aclose = AsyncMock()
        
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @patch("documind.api.routes.documents.get_storage_service")
    def test_upload_and_retrieve_document(self, mock_get_storage, client, sample_pdf):
        """Test uploading and retrieving a document."""
        mock_db = AsyncMock()
        app.dependency_overrides[documind.api.dependencies.get_db_service] = lambda: mock_db

        mock_storage = AsyncMock()
        mock_get_storage.return_value = mock_storage
        mock_storage.upload_fileobj.return_value = "uploads/test.pdf"

        doc_id = uuid.uuid4()
        mock_db.create_document.return_value = MagicMock(id=doc_id, filename="test.pdf", file_size=100, mime_type="application/pdf")
        mock_db.get_document.return_value = MagicMock(id=doc_id, filename="test.pdf", mime_type="application/pdf", file_size=100, uploaded_at="2026-01-01T00:00:00Z", file_path="uploads/test.pdf", metadata_={})

        # Upload
        response = client.post(
            "/documents",
            files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        )
        assert response.status_code == 201
        data = response.json()
        assert "document_id" in data

        # Retrieve
        response = client.get(f"/documents/{doc_id}")
        assert response.status_code == 200
        assert response.json()["filename"] == "test.pdf"

    def test_list_documents(self, client):
        """Test listing documents."""
        mock_db = AsyncMock()
        app.dependency_overrides[documind.api.dependencies.get_db_service] = lambda: mock_db

        doc_id = uuid.uuid4()
        mock_db.list_documents.return_value = [
            MagicMock(id=doc_id, filename="test.pdf", mime_type="application/pdf", file_size=100, uploaded_at="2026-01-01T00:00:00Z", file_path="uploads/test.pdf", metadata_={})
        ]

        # List
        response = client.get("/documents")
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) >= 1


class TestAnalysisWorkflow:
    """Integration tests for analysis workflow."""

    def test_start_analysis(self, client):
        """Test starting an analysis task."""
        mock_db = AsyncMock()
        app.dependency_overrides[documind.api.dependencies.get_db_service] = lambda: mock_db

        doc_id = uuid.uuid4()
        mock_db.get_document.return_value = MagicMock(id=doc_id, file_path="test.pdf")

        with (
            patch("documind.api.routes.analysis.save_task", new_callable=AsyncMock) as _mock_save,
            patch("documind.api.routes.analysis.update_task", new_callable=AsyncMock) as _mock_update,
        ):
            response = client.post(
                "/analysis",
                json={
                    "document_id": str(doc_id),
                    "tasks": ["summarize"],
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["status"] in ["queued", "processing"]

    @patch("documind.api.routes.analysis.get_task", new_callable=AsyncMock)
    def test_get_analysis_status(self, mock_get_task, client):
        """Test getting analysis task status."""
        mock_get_task.return_value = {
            "task_id": "test-task-id",
            "status": "processing",
            "document_id": "test-doc",
            "tasks": ["summarize"],
            "created_at": "2026-01-01T00:00:00Z"
        }

        response = client.get("/analysis/test-task-id/status")
        assert response.status_code == 200
        assert response.json()["status"] == "processing"


class TestRAGPipeline:
    """Integration tests for RAG pipeline."""

    @pytest.mark.asyncio
    async def test_embedding_service(self):
        """Test embedding service generates vectors."""
        with patch("documind.services.embeddings.get_settings") as mock_settings:
            mock_settings.return_value.llm.embedding_model = "text-embedding-3-large"
            mock_settings.return_value.llm.openai_api_key.get_secret_value.return_value = "test-key"

            with patch("openai.resources.embeddings.AsyncEmbeddings.create", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock(
                    data=[MagicMock(embedding=[0.1] * 3072)]
                )

                from documind.services.embeddings import EmbeddingService

                service = EmbeddingService(provider="openai")

                # Generate embedding
                embedding = await service.embed_text("test query")
                assert len(embedding) == 3072

    @pytest.mark.asyncio
    async def test_cache_service(self):
        """Test cache service stores and retrieves."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client
            mock_client.get.return_value = '{"key": "value"}'

            from documind.services.cache import CacheService

            service = CacheService()

            # Get cached value
            result = await service.get("test-key")
            assert result == {"key": "value"}


class TestAgentExecution:
    """Integration tests for agent execution."""

    @pytest.mark.asyncio
    async def test_parser_agent(self, sample_text, tmp_path):
        """Test parser agent extracts content."""
        from documind.agents.parser import DocumentParserAgent
        from documind.models.state import AgentState

        # Create a temp file
        doc_file = tmp_path / "test.txt"
        doc_file.write_text(sample_text)

        agent = DocumentParserAgent()

        state: AgentState = {
            "document_id": "test-doc",
            "document_path": str(doc_file),
            "document_content": sample_text.encode(),
            "document_type": "text/plain",
            "filename": "test.txt",
            "tasks": ["summarize"],
            "questions": [],
            "raw_text": "",
            "chunks": [],
            "summary": None,
            "qa_results": [],
            "compliance_report": None,
            "embeddings": None,
            "final_report_path": None,
            "errors": [],
            "agent_trace": [],
            "task_id": "test-task",
            "started_at": "2026-01-01T00:00:00Z"
        }

        result = await agent.execute(state)
        assert result["raw_text"] != ""
        assert len(result["chunks"]) > 0

    @pytest.mark.asyncio
    async def test_summarizer_agent(self, sample_text):
        """Test summarizer agent creates summary."""
        with patch("documind.services.llm.get_llm_service") as mock_get_llm:
            mock_llm_service = AsyncMock()
            mock_get_llm.return_value = mock_llm_service
            mock_llm_service.generate.return_value = "This is a summary."

            from documind.agents.summarizer import SummarizationAgent
            from documind.models.state import AgentState

            agent = SummarizationAgent()

            state: AgentState = {
                "document_id": "test-doc",
                "document_path": "test.txt",
                "document_content": b"",
                "document_type": "text/plain",
                "filename": "test.txt",
                "tasks": ["summarize"],
                "questions": [],
                "raw_text": sample_text,
                "chunks": [{"content": sample_text, "metadata": {}, "page": 1, "chunk_index": 0}],
                "summary": None,
                "qa_results": [],
                "compliance_report": None,
                "embeddings": None,
                "final_report_path": None,
                "errors": [],
                "agent_trace": [],
                "task_id": "test-task",
                "started_at": "2026-01-01T00:00:00Z"
            }

            result = await agent.execute(state)
            assert result["summary"] is not None
