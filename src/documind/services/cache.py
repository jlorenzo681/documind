"""Caching service using Redis."""

import json
from typing import Any

from documind.config import get_settings
from documind.monitoring import LoggerAdapter, get_metrics_collector

logger = LoggerAdapter("services.cache")


class CacheService:
    """Service for caching using Redis.

    Provides:
    - Key-value caching with TTL
    - JSON serialization
    - Embedding cache
    - Query result cache
    """

    def __init__(self) -> None:
        """Initialize the cache service."""
        self.settings = get_settings()
        self.metrics = get_metrics_collector()
        self._client: Any = None
        self.default_ttl = self.settings.redis.cache_ttl

    async def _get_client(self) -> Any:
        """Get or create Redis client."""
        if self._client is None:
            import redis.asyncio as redis

            self._client = redis.from_url(
                self.settings.redis.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def get(self, key: str) -> Any | None:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        try:
            client = await self._get_client()
            value = await client.get(key)

            if value is not None:
                self.metrics.cache_hits.inc()
                return json.loads(value)

            self.metrics.cache_misses.inc()
            return None

        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        try:
            client = await self._get_client()
            serialized = json.dumps(value)

            await client.set(
                key,
                serialized,
                ex=ttl or self.default_ttl,
            )
            return True

        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted
        """
        try:
            client = await self._get_client()
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False

    async def get_embedding(self, text_hash: str) -> list[float] | None:
        """Get cached embedding.

        Args:
            text_hash: Hash of the text

        Returns:
            Cached embedding or None
        """
        key = f"embedding:{text_hash}"
        return await self.get(key)

    async def set_embedding(
        self,
        text_hash: str,
        embedding: list[float],
        ttl: int = 86400,  # 24 hours
    ) -> bool:
        """Cache an embedding.

        Args:
            text_hash: Hash of the text
            embedding: Embedding vector
            ttl: Time to live

        Returns:
            True if successful
        """
        key = f"embedding:{text_hash}"
        return await self.set(key, embedding, ttl)

    async def get_query_result(self, query_hash: str) -> dict | None:
        """Get cached query result.

        Args:
            query_hash: Hash of the query

        Returns:
            Cached result or None
        """
        key = f"query:{query_hash}"
        return await self.get(key)

    async def set_query_result(
        self,
        query_hash: str,
        result: dict,
        ttl: int = 3600,  # 1 hour
    ) -> bool:
        """Cache a query result.

        Args:
            query_hash: Hash of the query
            result: Query result
            ttl: Time to live

        Returns:
            True if successful
        """
        key = f"query:{query_hash}"
        return await self.set(key, result, ttl)

    async def invalidate_document(self, document_id: str) -> int:
        """Invalidate all cache entries for a document.

        Args:
            document_id: Document ID

        Returns:
            Number of keys deleted
        """
        try:
            client = await self._get_client()
            pattern = f"*:{document_id}:*"
            keys = []

            async for key in client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await client.delete(*keys)
            return 0

        except Exception as e:
            logger.warning(
                "Cache invalidation failed",
                document_id=document_id,
                error=str(e),
            )
            return 0

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


# Default cache instance
_cache_service: CacheService | None = None


async def get_cache_service() -> CacheService:
    """Get the default cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
