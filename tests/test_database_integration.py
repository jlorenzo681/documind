"""Integration tests for database service."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from documind.db.base import Base
from documind.services.database import DatabaseService


@pytest.fixture
async def db_session():
    """Create a temporary database session for testing."""
    # Use in-memory SQLite for speed and isolation
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, connect_args={"check_same_thread": False}
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_document_lifecycle(db_session):
    """Test full document lifecycle."""
    service = DatabaseService(db_session)

    # 1. Create document
    doc_id = uuid.uuid4()
    filename = "test.pdf"
    file_path = "uploads/test.pdf"
    file_size = 1024
    mime_type = "application/pdf"

    doc = await service.create_document(
        filename=filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=mime_type,
        id=doc_id,
        metadata={"author": "me"},
    )

    assert doc.id == doc_id
    assert doc.filename == filename
    assert doc.metadata_ == {"author": "me"}

    # 2. Get document
    fetched_doc = await service.get_document(doc_id)
    assert fetched_doc is not None
    assert fetched_doc.id == doc_id
    assert fetched_doc.filename == filename

    # 3. List documents
    docs = await service.list_documents()
    assert len(docs) == 1
    assert docs[0].id == doc_id

    # 4. Create analysis
    analysis = await service.create_analysis(doc_id, "summary")
    assert analysis.document_id == doc_id
    assert analysis.task_type == "summary"
    assert analysis.status == "pending"

    # 5. Update analysis status
    await service.update_analysis_status(analysis.id, "processing")

    # Refresh logic not exposed in service but we can re-fetch or use session refresh if model attached
    # Since we are in same session...
    await db_session.refresh(analysis)
    assert analysis.status == "processing"

    # 6. Save result
    result_content = {"summary": "A good text."}
    result = await service.save_analysis_result(analysis.id, "summary", result_content)
    assert result.analysis_id == analysis.id
    assert result.content == result_content

    await service.update_analysis_status(analysis.id, "completed")
    await db_session.refresh(analysis)
    assert analysis.status == "completed"
    assert analysis.completed_at is not None

    # 7. Delete document
    await service.delete_document(doc_id)

    fetched_doc = await service.get_document(doc_id)
    assert fetched_doc is None

    docs = await service.list_documents()
    assert len(docs) == 0
