"""Document management endpoints."""

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from documind.models.schemas import DocumentMetadata, DocumentUploadResponse
from documind.monitoring import LoggerAdapter

router = APIRouter()
logger = LoggerAdapter("api.documents")

# In-memory document store (replace with database in production)
_documents: dict[str, DocumentMetadata] = {}

# Upload directory
UPLOAD_DIR = Path("/tmp/documind/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile) -> DocumentUploadResponse:
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
    doc_id = str(uuid.uuid4())

    # Read file content
    content = await file.read()
    size_bytes = len(content)

    # Validate file size (max 50MB)
    max_size = 50 * 1024 * 1024
    if size_bytes > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {max_size // 1024 // 1024}MB",
        )

    # Save to local storage
    file_ext = Path(file.filename or "document").suffix
    storage_path = UPLOAD_DIR / f"{doc_id}{file_ext}"
    storage_path.write_bytes(content)

    # Store metadata
    metadata = DocumentMetadata(
        id=doc_id,
        filename=file.filename or "document",
        content_type=content_type,
        size_bytes=size_bytes,
        page_count=None,  # Will be updated during parsing
        uploaded_at=datetime.utcnow(),
        storage_path=str(storage_path),
    )
    _documents[doc_id] = metadata

    logger.info(
        "Document uploaded",
        document_id=doc_id,
        filename=file.filename,
        size_bytes=size_bytes,
    )

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=file.filename or "document",
        size_bytes=size_bytes,
        message="Document uploaded successfully",
    )


@router.get("/{document_id}", response_model=DocumentMetadata)
async def get_document(document_id: str) -> DocumentMetadata:
    """Get document metadata by ID."""
    if document_id not in _documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    return _documents[document_id]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str) -> None:
    """Delete a document."""
    if document_id not in _documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Delete file
    metadata = _documents[document_id]
    storage_path = Path(metadata.storage_path)
    if storage_path.exists():
        storage_path.unlink()

    # Remove metadata
    del _documents[document_id]

    logger.info("Document deleted", document_id=document_id)


@router.get("", response_model=list[DocumentMetadata])
async def list_documents() -> list[DocumentMetadata]:
    """List all uploaded documents."""
    return list(_documents.values())


def get_document_path(document_id: str) -> str:
    """Get the file path for a document (internal use)."""
    if document_id not in _documents:
        raise ValueError(f"Document {document_id} not found")
    return _documents[document_id].storage_path
