"""Base repository implementation."""

from typing import Generic, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documind.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """Initialize repository.

        Args:
            model: The SQLAlchemy model class
            session: The database session
        """
        self.model = model
        self.session = session

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Get a record by ID.

        Args:
            id: Record ID

        Returns:
            The record or None
        """
        query = select(self.model).where(self.model.id == id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[ModelType]:
        """List all records.

        Returns:
            List of records
        """
        query = select(self.model)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    def add(self, obj: ModelType) -> None:
        """Add a new record to the session.

        Args:
            obj: The record to add
        """
        self.session.add(obj)

    async def delete(self, id: UUID) -> bool:
        """Delete a record by ID.

        Args:
            id: Record ID

        Returns:
            True if deleted, False if not found
        """
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
            return True
        return False
