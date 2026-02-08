"""Health check endpoints."""

from fastapi import APIRouter

from documind import __version__
from documind.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check the health of the application and its dependencies."""
    # TODO: Add actual service health checks
    services = {
        "api": True,
        "database": True,  # await check_database()
        "vectorstore": True,  # await check_vectorstore()
        "cache": True,  # await check_redis()
    }

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
