"""DocuMind FastAPI Application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from documind import __version__
from documind.api.routes import analysis, documents, health, results
from documind.config import get_settings
from documind.monitoring import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Application lifespan handler for startup/shutdown."""
    # Startup
    setup_logging()

    get_settings()

    # Initialize services if needed
    # e.g., connect to databases, warm up caches

    yield

    # Shutdown
    # e.g., close database connections, flush caches


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="DocuMind API",
        description="Multi-Agent Document Analysis System",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount Prometheus metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(documents.router, prefix="/documents", tags=["Documents"])
    app.include_router(analysis.router, prefix="/analyze", tags=["Analysis"])
    app.include_router(results.router, prefix="/results", tags=["Results"])

    return app


# Create app instance
app = create_app()


def run() -> None:
    """Run the application with uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "documind.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
