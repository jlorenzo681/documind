"""Orchestrator Agent using LangGraph for workflow coordination."""

from typing import Literal

from langgraph.graph import END, StateGraph

from documind.agents.compliance import ComplianceAgent
from documind.agents.parser import DocumentParserAgent
from documind.agents.qa import QAAgent
from documind.agents.reporter import ReportGeneratorAgent
from documind.agents.summarizer import SummarizationAgent
from documind.models.state import AgentState
from documind.monitoring import LoggerAdapter

logger = LoggerAdapter("orchestrator")


# Agent instances
parser_agent = DocumentParserAgent()
summarizer_agent = SummarizationAgent()
qa_agent = QAAgent()
compliance_agent = ComplianceAgent()
reporter_agent = ReportGeneratorAgent()


async def parse_node(state: AgentState) -> AgentState:
    """Node for document parsing."""
    return await parser_agent.execute(state)


async def summarize_node(state: AgentState) -> AgentState:
    """Node for document summarization."""
    return await summarizer_agent.execute(state)


async def qa_node(state: AgentState) -> AgentState:
    """Node for question answering."""
    return await qa_agent.execute(state)


async def compliance_node(state: AgentState) -> AgentState:
    """Node for compliance checking."""
    return await compliance_agent.execute(state)


async def report_node(state: AgentState) -> AgentState:
    """Node for report generation."""
    return await reporter_agent.execute(state)


def should_continue(state: AgentState) -> Literal["summarize", "end"]:
    """Determine if processing should continue after parsing."""
    # Check for critical errors
    if state.get("errors") and len(state["errors"]) > 0:
        # Check if parsing failed completely
        if not state.get("chunks"):
            logger.error("Parsing failed, no chunks extracted")
            return "end"

    return "summarize"


def after_summary(state: AgentState) -> Literal["qa", "compliance"]:
    """Determine next step after summarization."""
    # If there are questions, go to QA first
    if state.get("questions"):
        return "qa"
    return "compliance"


def after_qa(state: AgentState) -> Literal["compliance"]:
    """Always proceed to compliance after QA."""
    return "compliance"


def create_orchestrator() -> StateGraph:
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
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "summarize",
        after_summary,
        {
            "qa": "qa",
            "compliance": "compliance",
        },
    )

    workflow.add_edge("qa", "compliance")
    workflow.add_edge("compliance", "report")
    workflow.add_edge("report", END)

    return workflow.compile()


# Create compiled workflow
orchestrator = create_orchestrator()


async def run_analysis(
    document_id: str,
    document_path: str,
    task_id: str,
    questions: list[str] | None = None,
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
    )

    logger.info(
        "Starting document analysis",
        document_id=document_id,
        task_id=task_id,
    )

    # Run the workflow
    final_state = await orchestrator.ainvoke(initial_state)

    logger.info(
        "Document analysis completed",
        document_id=document_id,
        task_id=task_id,
        has_errors=bool(final_state.get("errors")),
    )

    return final_state
