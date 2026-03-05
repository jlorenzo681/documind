"""Redis-backed task store for analysis jobs."""

import json
from typing import Any

import redis.asyncio as aioredis

from documind.config import get_settings
from documind.monitoring import LoggerAdapter

logger = LoggerAdapter("api.task_store")

_client: aioredis.Redis | None = None
_TASK_TTL = 86400  # 24 hours


async def _get_client() -> aioredis.Redis:
    """Get or create the Redis client for task storage."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = aioredis.from_url(
            settings.redis.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def save_task(task_id: str, data: dict[str, Any]) -> None:
    """Save or update a task in Redis."""
    client = await _get_client()
    await client.set(f"task:{task_id}", json.dumps(data, default=str), ex=_TASK_TTL)


async def get_task(task_id: str) -> dict[str, Any] | None:
    """Retrieve a task from Redis."""
    client = await _get_client()
    raw = await client.get(f"task:{task_id}")
    return json.loads(raw) if raw else None


async def update_task(task_id: str, **fields: Any) -> None:
    """Update specific fields of a task."""
    task = await get_task(task_id)
    if task:
        task.update(fields)
        await save_task(task_id, task)
