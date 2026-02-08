"""Embedding service for generating vector representations."""

from typing import Any

from documind.config import get_settings
from documind.monitoring import LoggerAdapter, get_metrics_collector

logger = LoggerAdapter("services.embeddings")


class EmbeddingService:
    """Service for generating text embeddings.

    Supports multiple providers:
    - OpenAI (text-embedding-3-large, text-embedding-3-small)
    - Cohere (embed-english-v3.0)
    - Local (sentence-transformers)
    """

    def __init__(self, provider: str = "openai") -> None:
        """Initialize the embedding service.

        Args:
            provider: Embedding provider ("openai", "cohere", "local")
        """
        self.provider = provider
        self.settings = get_settings()
        self.metrics = get_metrics_collector()
        self._client: Any = None
        self._dimension: int = 3072  # Default for text-embedding-3-large

    def _get_openai_client(self) -> Any:
        """Get or create OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.settings.llm.openai_api_key.get_secret_value())
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        logger.debug("Generating embeddings", count=len(texts))

        if self.provider == "openai":
            return await self._embed_openai(texts)
        elif self.provider == "cohere":
            return await self._embed_cohere(texts)
        elif self.provider == "local":
            return await self._embed_local(texts)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI."""
        import asyncio

        client = self._get_openai_client()
        model = self.settings.llm.embedding_model

        # Run in thread pool since OpenAI client is sync
        def _embed() -> list[list[float]]:
            response = client.embeddings.create(
                model=model,
                input=texts,
            )
            return [item.embedding for item in response.data]

        embeddings = await asyncio.to_thread(_embed)
        self._dimension = len(embeddings[0]) if embeddings else 3072

        logger.debug(
            "OpenAI embeddings generated",
            count=len(embeddings),
            dimension=self._dimension,
        )

        return embeddings

    async def _embed_cohere(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Cohere."""
        import cohere

        client = cohere.AsyncClient(api_key=self.settings.llm.cohere_api_key.get_secret_value())

        response = await client.embed(
            texts=texts,
            model="embed-english-v3.0",
            input_type="search_document",
        )

        self._dimension = len(response.embeddings[0])
        return response.embeddings

    async def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local sentence-transformers."""
        import asyncio

        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")

        def _embed() -> list[list[float]]:
            embeddings = model.encode(texts)
            return embeddings.tolist()

        embeddings = await asyncio.to_thread(_embed)
        self._dimension = len(embeddings[0]) if embeddings else 384

        return embeddings

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return self._dimension


# Default embedding service instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get the default embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
