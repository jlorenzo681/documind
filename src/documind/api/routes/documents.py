"""Document management endpoints."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from documind.api.dependencies import get_db_service
from documind.models.schemas import DocumentMetadata, DocumentUploadResponse
from documind.monitoring import LoggerAdapter
from documind.services.database import DatabaseService
from documind.services.storage import get_storage_service

router = APIRouter()
logger = LoggerAdapter("api.documents")

# Upload directory - kept for reference or temporary local storage if needed
UPLOAD_DIR = Path("/tmp/documind/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    db: Annotated[DatabaseService, Depends(get_db_service)],
) -> DocumentUploadResponse:
    """Upload a document for analysis.

    Supports PDF, DOCX, TXT, and image files.
    """
    # Validate file type
    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "image/png",
        "image/jpeg",
    }

    content_type = file.content_type or "application/octet-stream"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type {content_type} not supported",
        )

    # Generate document ID
    doc_id = uuid.uuid4()

    # Read file content for size check
    # Note: For large files in production, we might stream directly
    # but for now we read to check size
    content = await file.read()
    size_bytes = len(content)

    # Reset file cursor for uploading
    await file.seek(0)

    # Validate file size (max 50MB)
    max_size = 50 * 1024 * 1024
    if size_bytes > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {max_size // 1024 // 1024}MB",
        )

    # Use file.size if available, otherwise use read size
    size_bytes = file.size if file.size is not None else size_bytes

    # Upload to cloud storage
    storage = get_storage_service()
    object_name = f"uploads/{doc_id}/{file.filename}"

    # Use upload_fileobj instead of saving locally first
    storage_path = await storage.upload_fileobj(file.file, object_name)

    # Save to database
    document = await db.create_document(
        filename=file.filename or "document",
        file_path=storage_path,
        file_size=size_bytes,
        mime_type=content_type,
        metadata={
            "original_filename": file.filename,
            "uploaded_at": datetime.isoformat(datetime.utcnow()),
        },
    )

    logger.info(
        "Document uploaded",
        document_id=str(document.id),
        filename=file.filename,
        size_bytes=size_bytes,
    )

    return DocumentUploadResponse(
        document_id=str(document.id),
        filename=document.filename,
        size_bytes=document.file_size,
        message="Document uploaded successfully",
    )


@router.get("/{document_id}", response_model=DocumentMetadata)
async def get_document(
    document_id: str,
    db: Annotated[DatabaseService, Depends(get_db_service)],
) -> DocumentMetadata:
    """Get document metadata by ID."""
    try:
        doc_uuid = uuid.UUID(document_id)
        document = await db.get_document(doc_uuid)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format",
        ) from e

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    return DocumentMetadata(
        id=str(document.id),
        filename=document.filename,
        content_type=document.mime_type,
        size_bytes=document.file_size,
        uploaded_at=document.uploaded_at,
        storage_path=document.file_path,
        page_count=document.metadata_.get("page_count"),
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: Annotated[DatabaseService, Depends(get_db_service)],
) -> None:
    """Delete a document."""
    try:
        doc_uuid = uuid.UUID(document_id)
        document = await db.get_document(doc_uuid)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format",
        ) from e

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Delete from storage
    storage = get_storage_service()
    object_name = f"uploads/{document.id}/{document.filename}"
    try:
        await storage.delete_file(object_name)
    except Exception as e:
        logger.error(
            "Failed to delete file from storage",
            error=str(e),
            document_id=document_id,
        )
        # Continue to delete from DB even if storage deletion fails

    # Delete from database
    await db.delete_document(doc_uuid)

    logger.info("Document deleted", document_id=document_id)


@router.get("", response_model=list[DocumentMetadata])
async def list_documents(
    db: Annotated[DatabaseService, Depends(get_db_service)],
) -> list[DocumentMetadata]:
    """List all uploaded documents."""
    documents = await db.list_documents()

    return [
        DocumentMetadata(
            id=str(doc.id),
            filename=doc.filename,
            content_type=doc.mime_type,
            size_bytes=doc.file_size,
            uploaded_at=doc.uploaded_at,
            storage_path=doc.file_path,
            page_count=doc.metadata_.get("page_count"),
        )
        for doc in documents
    ]


def get_document_path(document_id: str) -> str:
    """Get the file path for a document (internal use).

    DEPRECATED: Use DatabaseService.get_document() instead.
    """
    raise NotImplementedError(
        "get_document_path is deprecated. Use DatabaseService.get_document() to retrieve file path."
    )
