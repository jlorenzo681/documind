"""Document repository."""

from sqlalchemy import select

from documind.db.models import Document
from documind.db.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document model."""

    def __init__(self, session):
        """Initialize repository."""
        super().__init__(Document, session)

    async def get_by_filename(self, filename: str) -> Document | None:
        """Get document by filename.

        Args:
            filename: Document filename

        Returns:
            Document or None
        """
        query = select(self.model).where(self.model.filename == filename)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 50, offset: int = 0) -> list[Document]:
        """List documents ordered by upload time with pagination.

        Args:
            limit: Maximum number of documents to return (default 50)
            offset: Number of documents to skip (default 0)

        Returns:
            List of documents
        """
        query = (
            select(self.model).order_by(self.model.uploaded_at.desc()).limit(limit).offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
