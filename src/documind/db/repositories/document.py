"""Document repository."""

from uuid import UUID

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

    async def list_recent(self) -> list[Document]:
        """List documents ordered by upload time.

        Returns:
            List of documents
        """
        query = select(self.model).order_by(self.model.uploaded_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())
