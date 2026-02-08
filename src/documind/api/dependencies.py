"""API dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from documind.db.base import get_db
from documind.services.database import DatabaseService


async def get_db_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DatabaseService:
    """Get database service instance.

    Args:
        session: Database session

    Returns:
        Database service
    """
    return DatabaseService(session)
