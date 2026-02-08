"""Analysis repository."""

from uuid import UUID

from sqlalchemy import select

from documind.db.models import Analysis, AnalysisResult
from documind.db.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository[Analysis]):
    """Repository for Analysis model."""

    def __init__(self, session):
        """Initialize repository."""
        super().__init__(Analysis, session)

    async def get_by_document_id(self, document_id: UUID) -> list[Analysis]:
        """Get analyses for a document.

        Args:
            document_id: Document ID

        Returns:
            List of analyses
        """
        query = select(self.model).where(self.model.document_id == document_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self, analysis_id: UUID, status: str, error_message: str | None = None
    ) -> None:
        """Update analysis status.

        Args:
            analysis_id: Analysis ID
            status: New status
            error_message: Optional error message
        """
        from datetime import datetime
        from sqlalchemy import update

        values = {"status": status}
        if status in ("completed", "failed"):
            values["completed_at"] = datetime.utcnow()

        if error_message:
            values["error_message"] = error_message

        query = update(self.model).where(self.model.id == analysis_id).values(**values)
        await self.session.execute(query)
        await self.session.execute(query)
        await self.session.commit()

    def add_result(self, result: AnalysisResult) -> None:
        """Add an analysis result.

        Args:
            result: The result to add
        """
        self.session.add(result)

        """Add an analysis result.

        Args:
            result: The result to add
        """
        self.session.add(result)
