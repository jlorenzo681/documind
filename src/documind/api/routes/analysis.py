"""Analysis endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from documind.agents.orchestrator import run_analysis
from documind.api.dependencies import get_db_service
from documind.api.task_store import get_task, save_task, update_task
from documind.models.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisStatus,
    AnalysisTask,
)
from documind.monitoring import LoggerAdapter
from documind.services.database import DatabaseService

router = APIRouter()
logger = LoggerAdapter("api.analysis")


def _estimate_time(tasks: list[AnalysisTask]) -> int:
    """Estimate processing time in seconds."""
    base_time = 10
    task_times = {
        AnalysisTask.SUMMARIZE: 15,
        AnalysisTask.QA: 20,
        AnalysisTask.COMPLIANCE: 15,
        AnalysisTask.FULL: 45,
    }
    return base_time + sum(task_times.get(t, 10) for t in tasks)


async def _run_analysis_task(
    task_id: str,
    document_id: str,
    document_path: str,
    questions: list[str] | None,
) -> None:
    """Background task to run document analysis."""
    logger.info("Starting background analysis", task_id=task_id)

    await update_task(task_id, status=AnalysisStatus.PROCESSING.value)

    try:
        result = await run_analysis(
            document_id=document_id,
            document_path=document_path,
            task_id=task_id,
            questions=questions,
        )

        await update_task(
            task_id,
            status=AnalysisStatus.COMPLETED.value,
            result=result,
            completed_at=datetime.now(UTC).isoformat(),
        )

        logger.info(
            "Analysis completed",
            task_id=task_id,
            has_errors=bool(result.get("errors")),
        )

    except Exception as e:
        logger.exception("Analysis failed", task_id=task_id, error=str(e))
        await update_task(
            task_id,
            status=AnalysisStatus.FAILED.value,
            error=str(e),
        )


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[DatabaseService, Depends(get_db_service)],
) -> AnalysisResponse:
    """Start document analysis.

    The analysis runs asynchronously. Use the returned task_id to check
    status and retrieve results.
    """
    # Validate document exists
    try:
        doc_uuid = uuid.UUID(request.document_id)
        document = await db.get_document(doc_uuid)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID format",
        ) from None

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {request.document_id} not found",
        )

    document_path = document.file_path

    # Create task
    task_id = str(uuid.uuid4())
    estimated_time = _estimate_time(request.tasks)
    now = datetime.now(UTC)

    await save_task(
        task_id,
        {
            "task_id": task_id,
            "document_id": request.document_id,
            "tasks": [t.value for t in request.tasks],
            "status": AnalysisStatus.QUEUED.value,
            "created_at": now.isoformat(),
            "result": None,
            "error": None,
        },
    )

    # Queue background task
    background_tasks.add_task(
        _run_analysis_task,
        task_id=task_id,
        document_id=request.document_id,
        document_path=document_path,
        questions=request.questions,
    )

    logger.info(
        "Analysis queued",
        task_id=task_id,
        document_id=request.document_id,
        tasks=[t.value for t in request.tasks],
    )

    return AnalysisResponse(
        task_id=task_id,
        document_id=request.document_id,
        status=AnalysisStatus.QUEUED,
        tasks=request.tasks,
        estimated_time_seconds=estimated_time,
        created_at=now,
    )


@router.get("/{task_id}/status", response_model=AnalysisResponse)
async def get_analysis_status(task_id: str) -> AnalysisResponse:
    """Get the status of an analysis task."""
    task = await get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return AnalysisResponse(
        task_id=task["task_id"],
        document_id=task["document_id"],
        status=AnalysisStatus(task["status"]),
        tasks=[AnalysisTask(t) for t in task["tasks"]],
        estimated_time_seconds=0,
        created_at=datetime.fromisoformat(task["created_at"]),
    )


@router.post("/{task_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_analysis(task_id: str) -> dict[str, str]:
    """Cancel a running analysis (if possible)."""
    task = await get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    if task["status"] in {
        AnalysisStatus.COMPLETED.value,
        AnalysisStatus.FAILED.value,
        AnalysisStatus.CANCELLED.value,
    }:
        return {"message": f"Task already {task['status']}"}

    await update_task(task_id, status=AnalysisStatus.CANCELLED.value)
    logger.info("Analysis cancelled", task_id=task_id)

    return {"message": "Analysis cancelled"}


async def get_task_result(task_id: str) -> dict | None:
    """Get the result of an analysis task (internal use)."""
    task = await get_task(task_id)
    if not task:
        return None
    return task.get("result")
