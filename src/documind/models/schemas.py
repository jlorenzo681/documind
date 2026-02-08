"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AnalysisTask(StrEnum):
    """Available analysis tasks."""

    SUMMARIZE = "summarize"
    QA = "qa"
    COMPLIANCE = "compliance"
    FULL = "full"


class AnalysisStatus(StrEnum):
    """Status of an analysis job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DocumentMetadata(BaseModel):
    """Metadata for an uploaded document."""

    id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type of the document")
    size_bytes: int = Field(..., description="File size in bytes")
    page_count: int | None = Field(None, description="Number of pages (for PDFs)")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, description="Upload timestamp")
    storage_path: str = Field(..., description="Path in object storage")


class DocumentUploadResponse(BaseModel):
    """Response for document upload."""

    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    size_bytes: int = Field(..., description="File size in bytes")
    message: str = Field(default="Document uploaded successfully")


class AnalysisRequest(BaseModel):
    """Request for document analysis."""

    document_id: str = Field(..., description="ID of the document to analyze")
    tasks: list[AnalysisTask] = Field(
        default=[AnalysisTask.FULL],
        description="Analysis tasks to perform",
    )
    questions: list[str] | None = Field(None, description="Questions to answer (for QA task)")
    priority: str = Field(
        default="normal",
        description="Priority level: low, normal, high",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional options for analysis",
    )


class AnalysisResponse(BaseModel):
    """Response for analysis request."""

    task_id: str = Field(..., description="Unique task identifier")
    document_id: str = Field(..., description="Document being analyzed")
    status: AnalysisStatus = Field(..., description="Current status")
    tasks: list[AnalysisTask] = Field(..., description="Requested tasks")
    estimated_time_seconds: int = Field(..., description="Estimated completion time")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Task creation time")


class SummaryResult(BaseModel):
    """Result of summarization task."""

    executive_summary: str = Field(..., description="Brief executive summary")
    detailed_summary: str = Field(..., description="Detailed summary")
    key_points: list[str] = Field(..., description="Key points extracted")
    document_type: str | None = Field(None, description="Detected document type")


class QAResult(BaseModel):
    """Result of Q&A task."""

    question: str = Field(..., description="The question asked")
    answer: str = Field(..., description="Generated answer")
    confidence: float = Field(..., description="Confidence score 0-1")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="Source chunks used")


class ComplianceResult(BaseModel):
    """Result of compliance check."""

    overall_risk_score: float = Field(..., description="Overall risk score 0-100")
    risk_level: str = Field(..., description="Risk level: low, medium, high")
    issues: list[dict[str, Any]] = Field(
        default_factory=list, description="Compliance issues found"
    )
    recommendations: list[str] = Field(default_factory=list, description="Recommendations")
    clauses_analyzed: int = Field(..., description="Number of clauses analyzed")


class FullAnalysisResult(BaseModel):
    """Complete analysis result."""

    task_id: str = Field(..., description="Task identifier")
    document_id: str = Field(..., description="Document identifier")
    status: AnalysisStatus = Field(..., description="Final status")
    summary: SummaryResult | None = Field(None, description="Summary results")
    qa_results: list[QAResult] | None = Field(None, description="Q&A results")
    compliance: ComplianceResult | None = Field(None, description="Compliance results")
    report_url: str | None = Field(None, description="URL to generated report")
    processing_time_seconds: float = Field(..., description="Total processing time")
    completed_at: datetime = Field(
        default_factory=datetime.utcnow, description="Completion timestamp"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="Application version")
    services: dict[str, bool] = Field(default_factory=dict, description="Individual service health")
