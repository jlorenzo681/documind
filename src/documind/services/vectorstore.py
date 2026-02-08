"""Vector store service for document retrieval."""

from typing import Any
from uuid import uuid4

from documind.config import get_settings
from documind.monitoring import LoggerAdapter, get_metrics_collector
from documind.services.embeddings import get_embedding_service

logger = LoggerAdapter("services.vectorstore")


class VectorStoreService:
    """Service for vector storage and retrieval using Qdrant.

    Provides:
    - Document chunk storage with embeddings
    - Similarity search with MMR
    - Metadata filtering
    - Batch operations
    """

    def __init__(self, collection_name: str | None = None) -> None:
        """Initialize the vector store service.

        Args:
            collection_name: Name of the Qdrant collection
        """
        self.settings = get_settings()
        self.collection_name = collection_name or self.settings.vectorstore.collection_name
        self.metrics = get_metrics_collector()
        self._client: Any = None
        self._embedding_service = get_embedding_service()

    def _get_client(self) -> Any:
        """Get or create Qdrant client."""
        if self._client is None:
            from qdrant_client import QdrantClient

            api_key = self.settings.vectorstore.api_key.get_secret_value()

            self._client = QdrantClient(
                url=self.settings.vectorstore.url,
                api_key=api_key if api_key else None,
            )

            # Ensure collection exists
            self._ensure_collection()

        return self._client

    def _ensure_collection(self) -> None:
        """Ensure the collection exists, create if not."""
        from qdrant_client.models import Distance, VectorParams

        client = self._client
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            logger.info(
                "Creating collection",
                name=self.collection_name,
                dimension=self._embedding_service.dimension,
            )

            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self._embedding_service.dimension,
                    distance=Distance.COSINE,
                ),
            )

    async def add_documents(
        self,
        documents: list[dict[str, Any]],
        document_id: str,
    ) -> list[str]:
        """Add document chunks to the vector store.

        Args:
            documents: List of document chunks with content and metadata
            document_id: Parent document ID

        Returns:
            List of chunk IDs
        """
        from qdrant_client.models import PointStruct

        if not documents:
            return []

        client = self._get_client()

        # Generate embeddings
        texts = [doc["content"] for doc in documents]
        embeddings = await self._embedding_service.embed_batch(texts)

        # Create points
        points: list[PointStruct] = []
        chunk_ids: list[str] = []

        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            chunk_id = str(uuid4())
            chunk_ids.append(chunk_id)

            points.append(
                PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload={
                        "content": doc["content"],
                        "document_id": document_id,
                        "chunk_index": doc.get("chunk_index", i),
                        "page": doc.get("page"),
                        "metadata": doc.get("metadata", {}),
                    },
                )
            )

        # Upsert points
        client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        self.metrics.vector_operations.labels(operation="upsert", status="success").inc(len(points))

        logger.info(
            "Documents added to vector store",
            document_id=document_id,
            chunk_count=len(points),
        )

        return chunk_ids

    async def search(
        self,
        query: str,
        document_id: str | None = None,
        limit: int = 5,
        score_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search for similar documents.

        Args:
            query: Search query
            document_id: Optional filter by document ID
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of matching documents with scores
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = self._get_client()

        # Generate query embedding
        query_embedding = await self._embedding_service.embed_text(query)

        # Build filter
        query_filter = None
        if document_id:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            )

        # Search
        results = client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )

        self.metrics.vector_operations.labels(operation="search", status="success").inc()

        # Format results
        return [
            {
                "chunk_id": str(hit.id),
                "content": hit.payload.get("content", ""),
                "document_id": hit.payload.get("document_id"),
                "chunk_index": hit.payload.get("chunk_index"),
                "page": hit.payload.get("page"),
                "score": hit.score,
                "metadata": hit.payload.get("metadata", {}),
            }
            for hit in results
        ]

    async def search_mmr(
        self,
        query: str,
        document_id: str | None = None,
        limit: int = 5,
        diversity: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search using Maximum Marginal Relevance for diversity.

        Args:
            query: Search query
            document_id: Optional filter by document ID
            limit: Maximum number of results
            diversity: Diversity factor (0 = pure similarity, 1 = pure diversity)

        Returns:
            List of diverse matching documents
        """
        # Get more candidates for MMR selection
        candidates = await self.search(
            query=query,
            document_id=document_id,
            limit=limit * 3,
            score_threshold=0.3,
        )

        if not candidates:
            return []

        # Simple MMR implementation
        selected: list[dict[str, Any]] = []
        remaining = candidates.copy()

        # Select first by score
        selected.append(remaining.pop(0))

        # Select remaining with diversity
        while len(selected) < limit and remaining:
            best_idx = 0
            best_score = -1.0

            for i, candidate in enumerate(remaining):
                # Score = relevance - diversity * max_similarity_to_selected
                relevance = candidate["score"]

                # Simple content overlap as similarity proxy
                max_sim = max(
                    self._content_similarity(candidate["content"], s["content"]) for s in selected
                )

                mmr_score = relevance - diversity * max_sim

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected

    def _content_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple content similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    async def delete_document(self, document_id: str) -> int:
        """Delete all chunks for a document.

        Args:
            document_id: Document ID to delete

        Returns:
            Number of chunks deleted
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = self._get_client()

        # Count before delete
        count_before = client.count(
            collection_name=self.collection_name,
            count_filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        ).count

        # Delete
        client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )

        logger.info(
            "Document chunks deleted",
            document_id=document_id,
            count=count_before,
        )

        return count_before


# Default vector store instance
_vector_store: VectorStoreService | None = None


def get_vector_store() -> VectorStoreService:
    """Get the default vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStoreService()
    return _vector_store
