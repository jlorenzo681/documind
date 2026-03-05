"""Health check endpoints."""

from fastapi import APIRouter

from documind import __version__
from documind.config import get_settings
from documind.models.schemas import HealthResponse
from documind.monitoring import LoggerAdapter

router = APIRouter()
logger = LoggerAdapter("api.health")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check the health of the application and its dependencies."""
    services: dict[str, bool] = {"api": True}

    # Check database
    try:
        from sqlalchemy import text

        from documind.db.base import get_engine

        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["database"] = True
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        services["database"] = False

    # Check Redis
    try:
        import redis.asyncio as aioredis

        settings = get_settings()
        r = aioredis.from_url(settings.redis.redis_url)
        await r.ping()
        await r.aclose()
        services["cache"] = True
    except Exception as e:
        logger.warning("Redis health check failed", error=str(e))
        services["cache"] = False

    # Check Qdrant
    try:
        from qdrant_client import QdrantClient

        settings = get_settings()
        client = QdrantClient(url=settings.vectorstore.url)
        client.get_collections()
        services["vectorstore"] = True
    except Exception as e:
        logger.warning("Qdrant health check failed", error=str(e))
        services["vectorstore"] = False

    all_healthy = all(services.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version=__version__,
        services=services,
    )


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Kubernetes readiness probe."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Kubernetes liveness probe."""
    return {"status": "alive"}
