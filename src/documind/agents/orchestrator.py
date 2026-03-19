"""Orchestrator Agent using LangGraph for workflow coordination."""

from functools import lru_cache
from typing import Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from documind.agents.compliance import ComplianceAgent
from documind.agents.parser import DocumentParserAgent
from documind.agents.qa import QAAgent
from documind.agents.reporter import ReportGeneratorAgent
from documind.agents.summarizer import SummarizationAgent
from documind.models.state import AgentState
from documind.monitoring import LoggerAdapter

logger = LoggerAdapter("orchestrator")


# Lazy agent getters — avoids import-time instantiation
@lru_cache
def _get_parser() -> DocumentParserAgent:
    return DocumentParserAgent()


@lru_cache
def _get_summarizer() -> SummarizationAgent:
    return SummarizationAgent()


@lru_cache
def _get_qa() -> QAAgent:
    return QAAgent()


@lru_cache
def _get_compliance() -> ComplianceAgent:
    return ComplianceAgent()


@lru_cache
def _get_reporter() -> ReportGeneratorAgent:
    return ReportGeneratorAgent()


async def parse_node(state: AgentState) -> AgentState:
    """Node for document parsing."""
    return await _get_parser().execute(state)


async def summarize_node(state: AgentState) -> AgentState:
    """Node for document summarization."""
    return await _get_summarizer().execute(state)


async def qa_node(state: AgentState) -> AgentState:
    """Node for question answering."""
    return await _get_qa().execute(state)


async def compliance_node(state: AgentState) -> AgentState:
    """Node for compliance checking."""
    return await _get_compliance().execute(state)


async def report_node(state: AgentState) -> AgentState:
    """Node for report generation."""
    return await _get_reporter().execute(state)


def _wants(state: AgentState, task: str) -> bool:
    """Check if a task was requested."""
    enabled = state.get("enabled_tasks", [])
    return task in enabled or "full" in enabled


def should_continue(state: AgentState) -> Literal["summarize", "qa", "end"]:
    """Determine next step after parsing."""
    if state.get("errors") and len(state["errors"]) > 0 and not state.get("chunks"):
        logger.error("Parsing failed, no chunks extracted")
        return "end"

    if _wants(state, "summarize"):
        return "summarize"

    # Skip summarize — go straight to qa if needed
    if _wants(state, "qa") and state.get("questions"):
        return "qa"

    return "end"


def after_summary(state: AgentState) -> Literal["qa", "compliance", "report", "end"]:
    """Determine next step after summarization."""
    if _wants(state, "qa") and state.get("questions"):
        return "qa"
    if _wants(state, "compliance"):
        return "compliance"
    if _wants(state, "report"):
        return "report"
    return "end"


def after_qa(state: AgentState) -> Literal["compliance", "report", "end"]:
    """Determine next step after QA."""
    if _wants(state, "compliance"):
        return "compliance"
    if _wants(state, "report"):
        return "report"
    return "end"


def after_compliance(state: AgentState) -> Literal["report", "end"]:
    """Determine next step after compliance."""
    if _wants(state, "report"):
        return "report"
    return "end"


@lru_cache
def create_orchestrator() -> CompiledStateGraph:
    """Create the LangGraph workflow for document analysis.

    The workflow follows this pattern:
    1. Parse document
    2. Summarize content
    3. Answer questions (if any)
    4. Check compliance
    5. Generate report

    Returns:
        Compiled LangGraph workflow
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("parse", parse_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("qa", qa_node)
    workflow.add_node("compliance", compliance_node)
    workflow.add_node("report", report_node)

    # Set entry point
    workflow.set_entry_point("parse")

    # Add conditional edges
    workflow.add_conditional_edges(
        "parse",
        should_continue,
        {
            "summarize": "summarize",
            "qa": "qa",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "summarize",
        after_summary,
        {
            "qa": "qa",
            "compliance": "compliance",
            "report": "report",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "qa",
        after_qa,
        {
            "compliance": "compliance",
            "report": "report",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "compliance",
        after_compliance,
        {
            "report": "report",
            "end": END,
        },
    )

    workflow.add_edge("report", END)

    return workflow.compile()


async def run_analysis(
    document_id: str,
    document_path: str,
    task_id: str,
    questions: list[str] | None = None,
    enabled_tasks: list[str] | None = None,
) -> AgentState:
    """Run the complete document analysis workflow.

    Args:
        document_id: Unique identifier for the document
        document_path: Path to the document file
        task_id: Unique identifier for this analysis task
        questions: Optional list of questions to answer

    Returns:
        Final state with all analysis results
    """
    from documind.models.state import create_initial_state

    initial_state = create_initial_state(
        document_id=document_id,
        document_path=document_path,
        task_id=task_id,
        questions=questions,
        enabled_tasks=enabled_tasks,
    )

    logger.info(
        "Starting document analysis",
        document_id=document_id,
        task_id=task_id,
    )

    # Lazy — compiled graph cached by lru_cache
    orchestrator = create_orchestrator()
    final_state = await orchestrator.ainvoke(initial_state)

    logger.info(
        "Document analysis completed",
        document_id=document_id,
        task_id=task_id,
        has_errors=bool(final_state.get("errors")),
    )

    return final_state
