"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from documind import __version__
from documind.api.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestLoggingMiddleware
from documind.api.routes import analysis, documents, health, results
from documind.config import get_settings
from documind.monitoring import LoggerAdapter, setup_logging
from documind.monitoring.metrics import setup_prometheus

logger = LoggerAdapter("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Application lifespan handler."""
    settings = get_settings()
    setup_logging()

    logger.info(
        "Starting DocuMind",
        version=__version__,
        environment=settings.environment,
    )

    yield

    # Shutdown — close connections and flush caches
    logger.info("Shutting down DocuMind...")

    # Close database engine
    try:
        from documind.db.base import _engine

        if _engine is not None:
            await _engine.dispose()
            logger.info("Database engine disposed")
    except Exception as e:
        logger.warning("Error disposing database engine", error=str(e))

    # Close Redis cache
    try:
        from documind.services.cache import _cache_service

        if _cache_service is not None:
            await _cache_service.close()
            logger.info("Cache service closed")
    except Exception as e:
        logger.warning("Error closing cache service", error=str(e))

    # Close Redis task store
    try:
        from documind.api.task_store import _client as _task_store_client

        if _task_store_client is not None:
            await _task_store_client.aclose()
            logger.info("Task store Redis client closed")
    except Exception as e:
        logger.warning("Error closing task store client", error=str(e))

    logger.info("DocuMind shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="DocuMind API",
        description="Intelligent Document Analysis Service",
        version=__version__,
        lifespan=lifespan,
    )

    # Add middleware (applied in reverse stack order — last added = outermost)
    if not settings.debug:
        app.add_middleware(APIKeyMiddleware)

    app.add_middleware(RateLimitMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins if hasattr(settings, "cors_origins") else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # RequestLoggingMiddleware is outermost so it measures total wall-clock time
    app.add_middleware(RequestLoggingMiddleware)
    setup_prometheus(app)

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(documents.router, prefix="/documents", tags=["Documents"])
    app.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
    app.include_router(results.router, prefix="/results", tags=["Results"])

    return app


app = create_app()


def run() -> None:
    """Run the application."""
    settings = get_settings()
    uvicorn.run(
        "documind.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
