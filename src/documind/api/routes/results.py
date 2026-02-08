"""Results retrieval endpoints."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from documind.api.routes.analysis import _tasks, get_task_result
from documind.models.schemas import (
    AnalysisStatus,
    ComplianceResult,
    FullAnalysisResult,
    SummaryResult,
    QAResult,
)
from documind.monitoring import LoggerAdapter
from pathlib import Path

router = APIRouter()
logger = LoggerAdapter("api.results")


@router.get("/{task_id}", response_model=FullAnalysisResult)
async def get_results(task_id: str) -> FullAnalysisResult:
    """Get the full results of an analysis task."""
    if task_id not in _tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    task = _tasks[task_id]

    if task["status"] == AnalysisStatus.QUEUED.value:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Analysis is still queued",
        )

    if task["status"] == AnalysisStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Analysis is still processing",
        )

    if task["status"] == AnalysisStatus.FAILED.value:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {task.get('error', 'Unknown error')}",
        )

    if task["status"] == AnalysisStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Analysis was cancelled",
        )

    result = task.get("result", {})

    # Parse summary
    summary_data = result.get("summary")
    summary = None
    if summary_data:
        summary = SummaryResult(
            executive_summary=summary_data.get("executive_summary", ""),
            detailed_summary=summary_data.get("detailed_summary", ""),
            key_points=summary_data.get("key_points", []),
            document_type=summary_data.get("document_type"),
        )

    # Parse QA results
    qa_results = None
    qa_data = result.get("qa_results", [])
    if qa_data:
        qa_results = [
            QAResult(
                question=qa.get("question", ""),
                answer=qa.get("answer", ""),
                confidence=qa.get("confidence", 0.0),
                sources=qa.get("sources", []),
            )
            for qa in qa_data
        ]

    # Parse compliance
    compliance = None
    compliance_data = result.get("compliance_report")
    if compliance_data:
        compliance = ComplianceResult(
            overall_risk_score=compliance_data.get("overall_risk_score", 0.0),
            risk_level=compliance_data.get("risk_level", "unknown"),
            issues=compliance_data.get("issues", []),
            recommendations=compliance_data.get("recommendations", []),
            clauses_analyzed=compliance_data.get("clauses_analyzed", 0),
        )

    from datetime import datetime

    return FullAnalysisResult(
        task_id=task_id,
        document_id=task["document_id"],
        status=AnalysisStatus.COMPLETED,
        summary=summary,
        qa_results=qa_results,
        compliance=compliance,
        report_url=f"/results/{task_id}/report" if result.get("final_report_path") else None,
        processing_time_seconds=0.0,  # TODO: Calculate actual time
        completed_at=datetime.fromisoformat(
            task.get("completed_at", datetime.utcnow().isoformat())
        ),
    )


@router.get("/{task_id}/summary", response_model=SummaryResult)
async def get_summary(task_id: str) -> SummaryResult:
    """Get only the summary from an analysis."""
    result = get_task_result(task_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Results for task {task_id} not found",
        )

    summary_data = result.get("summary")
    if not summary_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summary available for this task",
        )

    return SummaryResult(
        executive_summary=summary_data.get("executive_summary", ""),
        detailed_summary=summary_data.get("detailed_summary", ""),
        key_points=summary_data.get("key_points", []),
        document_type=summary_data.get("document_type"),
    )


@router.get("/{task_id}/report")
async def download_report(task_id: str) -> FileResponse:
    """Download the generated PDF report."""
    result = get_task_result(task_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Results for task {task_id} not found",
        )

    report_path = result.get("final_report_path")
    if not report_path or not Path(report_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not available",
        )

    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        filename=f"documind_report_{task_id}.pdf",
    )
