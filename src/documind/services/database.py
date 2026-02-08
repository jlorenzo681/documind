"""Database service for CRUD operations."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from documind.db.models import Analysis, AnalysisResult, Document
from documind.db.repositories.analysis import AnalysisRepository
from documind.db.repositories.document import DocumentRepository
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
        self.documents = DocumentRepository(session)
        self.analyses = AnalysisRepository(session)

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
        self.documents.add(document)
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
        return await self.documents.get_by_id(document_id)

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
        self.analyses.add(analysis)
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
        await self.analyses.update_status(analysis_id, status, error_message)

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
        self.analyses.add_result(result)
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
        return await self.documents.list_recent()

    async def delete_document(self, document_id: uuid.UUID) -> None:
        """Delete a document.

        Args:
            document_id: Document ID
        """
        deleted = await self.documents.delete(document_id)
        if deleted:
            await self.session.commit()
            logger.info(
                "Deleted document record",
                document_id=str(document_id),
            )
