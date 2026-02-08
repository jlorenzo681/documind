"""Integration tests for DocuMind API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import io

from documind.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_pdf():
    """Create a mock PDF file."""
    content = b"%PDF-1.4 test content"
    return io.BytesIO(content)


class TestDocumentWorkflow:
    """Integration tests for complete document workflow."""

    def test_health_check(self, client):
        """Test API is healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @patch("documind.api.routes.documents._documents_store", {})
    def test_upload_and_retrieve_document(self, client, sample_pdf):
        """Test uploading and retrieving a document."""
        # Upload
        response = client.post(
            "/documents",
            files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        )
        assert response.status_code == 201
        data = response.json()
        assert "document_id" in data
        doc_id = data["document_id"]

        # Retrieve
        response = client.get(f"/documents/{doc_id}")
        assert response.status_code == 200
        assert response.json()["filename"] == "test.pdf"

    @patch("documind.api.routes.documents._documents_store", {})
    def test_list_documents(self, client, sample_pdf):
        """Test listing documents."""
        # Upload a document
        client.post(
            "/documents",
            files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        )

        # List
        response = client.get("/documents")
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) >= 1


class TestAnalysisWorkflow:
    """Integration tests for analysis workflow."""

    @patch("documind.api.routes.documents._documents_store")
    @patch("documind.api.routes.analysis._tasks_store", {})
    def test_start_analysis(self, mock_docs, client):
        """Test starting an analysis task."""
        # Mock document exists
        mock_docs.__contains__ = MagicMock(return_value=True)
        mock_docs.__getitem__ = MagicMock(
            return_value={
                "filename": "test.pdf",
                "content": b"test content",
                "content_type": "application/pdf",
            }
        )

        response = client.post(
            "/analyze",
            json={
                "document_id": "test-doc-id",
                "tasks": ["summarize"],
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["status"] in ["queued", "processing"]

    @patch("documind.api.routes.analysis._tasks_store")
    def test_get_analysis_status(self, mock_tasks, client):
        """Test getting analysis task status."""
        mock_tasks.__contains__ = MagicMock(return_value=True)
        mock_tasks.__getitem__ = MagicMock(
            return_value={
                "status": "processing",
                "document_id": "test-doc",
                "tasks": ["summarize"],
            }
        )

        response = client.get("/analyze/test-task-id/status")
        assert response.status_code == 200
        assert response.json()["status"] == "processing"


class TestRAGPipeline:
    """Integration tests for RAG pipeline."""

    @pytest.mark.asyncio
    async def test_embedding_service(self):
        """Test embedding service generates vectors."""
        with patch("documind.services.embeddings.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.embeddings.create.return_value = MagicMock(
                data=[MagicMock(embedding=[0.1] * 3072)]
            )

            from documind.services.embeddings import EmbeddingService

            service = EmbeddingService()

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
    async def test_parser_agent(self, sample_text):
        """Test parser agent extracts content."""
        from documind.agents.parser import DocumentParserAgent
        from documind.models.state import AgentState

        agent = DocumentParserAgent()

        state: AgentState = {
            "document_id": "test-doc",
            "document_content": sample_text.encode(),
            "document_type": "text/plain",
            "filename": "test.txt",
            "tasks": ["summarize"],
            "questions": [],
            "parsed_text": "",
            "chunks": [],
            "summary": None,
            "qa_results": [],
            "compliance_result": None,
            "report_path": None,
            "errors": [],
            "agent_trace": [],
        }

        result = await agent.execute(state)
        assert result["parsed_text"] != ""
        assert len(result["chunks"]) > 0

    @pytest.mark.asyncio
    async def test_summarizer_agent(self, sample_text):
        """Test summarizer agent creates summary."""
        with patch("documind.agents.summarizer.ChatOpenAI") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(
                return_value=MagicMock(content="This is a summary.")
            )

            from documind.agents.summarizer import SummarizationAgent
            from documind.models.state import AgentState

            agent = SummarizationAgent()

            state: AgentState = {
                "document_id": "test-doc",
                "document_content": b"",
                "document_type": "text/plain",
                "filename": "test.txt",
                "tasks": ["summarize"],
                "questions": [],
                "parsed_text": sample_text,
                "chunks": [{"content": sample_text, "metadata": {}}],
                "summary": None,
                "qa_results": [],
                "compliance_result": None,
                "report_path": None,
                "errors": [],
                "agent_trace": [],
            }

            result = await agent.execute(state)
            assert result["summary"] is not None
