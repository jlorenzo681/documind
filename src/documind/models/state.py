"""Agent state definitions for LangGraph orchestration."""

import operator
from typing import Annotated, Any, TypedDict


class DocumentChunk(TypedDict):
    """A chunk of a document with metadata."""

    content: str
    page: int | None
    chunk_index: int
    metadata: dict[str, Any]


class AgentState(TypedDict):
    """State passed between agents in the orchestration graph.

    This TypedDict defines the shared state that flows through
    the LangGraph workflow, updated by each agent.
    """

    # Document information
    document_id: str
    document_path: str
    document_type: str | None

    # Parsed content
    raw_text: str
    chunks: list[DocumentChunk]
    embeddings: list[list[float]] | None

    # Analysis results
    summary: dict[str, Any] | None
    qa_results: list[dict[str, Any]]
    compliance_report: dict[str, Any] | None

    # Questions for QA (if any)
    questions: list[str]

    # Final outputs
    final_report_path: str | None

    # Error tracking (using operator.add for aggregation)
    errors: Annotated[list[str], operator.add]

    # Metadata
    task_id: str
    started_at: str
    agent_trace: Annotated[list[str], operator.add]


def create_initial_state(
    document_id: str,
    document_path: str,
    task_id: str,
    questions: list[str] | None = None,
) -> AgentState:
    """Create an initial state for a new analysis task."""
    from datetime import datetime

    return AgentState(
        document_id=document_id,
        document_path=document_path,
        document_type=None,
        raw_text="",
        chunks=[],
        embeddings=None,
        summary=None,
        qa_results=[],
        compliance_report=None,
        questions=questions or [],
        final_report_path=None,
        errors=[],
        task_id=task_id,
        started_at=datetime.utcnow().isoformat(),
        agent_trace=[],
    )
