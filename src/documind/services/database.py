"""Database service for CRUD operations."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from documind.db.models import Analysis, AnalysisResult, Document
from documind.monitoring import LoggerAdapter

logger = LoggerAdapter("services.database")


class DatabaseService:
    """Service for database interactions."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize database service.

        Args:
            session: Database session
        """
        self.session = session

    async def create_document(
        self,
        filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        metadata: dict[str, Any] | None = None,
        id: uuid.UUID | None = None,
    ) -> Document:
        """Create a new document record.

        Args:
            filename: Original filename
            file_path: Storage path
            file_size: File size in bytes
            mime_type: MIME type
            metadata: Optional metadata
            id: Optional document ID

        Returns:
            Created document
        """
        document = Document(
            id=id or uuid.uuid4(),
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            metadata_=metadata or {},
        )
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)

        logger.info(
            "Created document record",
            document_id=str(document.id),
            filename=filename,
        )
        return document

    async def get_document(self, document_id: uuid.UUID) -> Document | None:
        """Get document by ID.

        Args:
            document_id: Document ID

        Returns:
            Document or None
        """
        query = select(Document).where(Document.id == document_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_analysis(
        self,
        document_id: uuid.UUID,
        task_type: str,
    ) -> Analysis:
        """Create a new analysis task.

        Args:
            document_id: Document ID
            task_type: Type of analysis task

        Returns:
            Created analysis
        """
        analysis = Analysis(
            document_id=document_id,
            task_type=task_type,
            status="pending",
        )
        self.session.add(analysis)
        await self.session.commit()
        await self.session.refresh(analysis)

        logger.info(
            "Created analysis task",
            analysis_id=str(analysis.id),
            document_id=str(document_id),
            task_type=task_type,
        )
        return analysis

    async def update_analysis_status(
        self,
        analysis_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update analysis status.

        Args:
            analysis_id: Analysis ID
            status: New status
            error_message: Optional error message
        """
        values = {
            "status": status,
        }
        if status in ("completed", "failed"):
            values["completed_at"] = datetime.now()  # type: ignore

        if error_message:
            values["error_message"] = error_message

        query = update(Analysis).where(Analysis.id == analysis_id).values(**values)
        await self.session.execute(query)
        await self.session.commit()

        logger.info(
            "Updated analysis status",
            analysis_id=str(analysis_id),
            status=status,
        )

    async def save_analysis_result(
        self,
        analysis_id: uuid.UUID,
        result_type: str,
        content: dict[str, Any],
    ) -> AnalysisResult:
        """Save analysis result.

        Args:
            analysis_id: Analysis ID
            result_type: Type of result
            content: Result content

        Returns:
            Created result
        """
        result = AnalysisResult(
            analysis_id=analysis_id,
            result_type=result_type,
            content=content,
        )
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)

        logger.info(
            "Saved analysis result",
            result_id=str(result.id),
            analysis_id=str(analysis_id),
            result_type=result_type,
        )
        return result

    async def list_documents(self) -> list[Document]:
        """List all documents.

        Returns:
            List of documents
        """
        query = select(Document).order_by(Document.uploaded_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_document(self, document_id: uuid.UUID) -> None:
        """Delete a document.

        Args:
            document_id: Document ID
        """
        query = select(Document).where(Document.id == document_id)
        result = await self.session.execute(query)
        document = result.scalar_one_or_none()

        if document:
            await self.session.delete(document)
            await self.session.commit()

            logger.info(
                "Deleted document record",
                document_id=str(document_id),
            )
