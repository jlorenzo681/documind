"""Database engine and session configuration."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


# Lazy engine and session factory — created on first access, not at import time.
_engine = None
_async_session_factory = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        from documind.config import get_settings

        settings = get_settings()
        _engine = create_async_engine(
            settings.database.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory():
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    The session is NOT auto-committed — callers (e.g. DatabaseService)
    are responsible for committing their own transactions.

    Yields:
        AsyncSession: Database session
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
