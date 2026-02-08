"""Analysis endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from documind.agents.orchestrator import run_analysis
from documind.api.routes.documents import get_document_path
from documind.models.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisStatus,
    AnalysisTask,
)
from documind.monitoring import LoggerAdapter

router = APIRouter()
logger = LoggerAdapter("api.analysis")

# In-memory task store (replace with Redis in production)
_tasks: dict[str, dict] = {}


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

    _tasks[task_id]["status"] = AnalysisStatus.PROCESSING.value

    try:
        result = await run_analysis(
            document_id=document_id,
            document_path=document_path,
            task_id=task_id,
            questions=questions,
        )

        _tasks[task_id]["status"] = AnalysisStatus.COMPLETED.value
        _tasks[task_id]["result"] = result
        _tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()

        logger.info(
            "Analysis completed",
            task_id=task_id,
            has_errors=bool(result.get("errors")),
        )

    except Exception as e:
        logger.exception("Analysis failed", task_id=task_id, error=str(e))
        _tasks[task_id]["status"] = AnalysisStatus.FAILED.value
        _tasks[task_id]["error"] = str(e)


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
) -> AnalysisResponse:
    """Start document analysis.

    The analysis runs asynchronously. Use the returned task_id to check
    status and retrieve results.
    """
    # Validate document exists
    try:
        document_path = get_document_path(request.document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {request.document_id} not found",
        )

    # Create task
    task_id = str(uuid.uuid4())
    estimated_time = _estimate_time(request.tasks)

    _tasks[task_id] = {
        "task_id": task_id,
        "document_id": request.document_id,
        "tasks": [t.value for t in request.tasks],
        "status": AnalysisStatus.QUEUED.value,
        "created_at": datetime.utcnow().isoformat(),
        "result": None,
        "error": None,
    }

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
        created_at=datetime.utcnow(),
    )


@router.get("/{task_id}/status", response_model=AnalysisResponse)
async def get_analysis_status(task_id: str) -> AnalysisResponse:
    """Get the status of an analysis task."""
    if task_id not in _tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    task = _tasks[task_id]

    return AnalysisResponse(
        task_id=task["task_id"],
        document_id=task["document_id"],
        status=AnalysisStatus(task["status"]),
        tasks=[AnalysisTask(t) for t in task["tasks"]],
        estimated_time_seconds=0,  # Already computed
        created_at=datetime.fromisoformat(task["created_at"]),
    )


@router.post("/{task_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_analysis(task_id: str) -> dict[str, str]:
    """Cancel a running analysis (if possible)."""
    if task_id not in _tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    task = _tasks[task_id]

    if task["status"] in {
        AnalysisStatus.COMPLETED.value,
        AnalysisStatus.FAILED.value,
        AnalysisStatus.CANCELLED.value,
    }:
        return {"message": f"Task already {task['status']}"}

    _tasks[task_id]["status"] = AnalysisStatus.CANCELLED.value
    logger.info("Analysis cancelled", task_id=task_id)

    return {"message": "Analysis cancelled"}


def get_task_result(task_id: str) -> dict | None:
    """Get the result of an analysis task (internal use)."""
    if task_id not in _tasks:
        return None
    return _tasks[task_id].get("result")
