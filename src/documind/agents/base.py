"""Base agent class for all DocuMind agents."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from documind.models.state import AgentState
from documind.monitoring import LoggerAdapter


class AgentResult(BaseModel):
    """Result returned by an agent execution."""

    success: bool = Field(..., description="Whether the agent succeeded")
    data: Any = Field(default=None, description="Result data")
    errors: list[str] = Field(default_factory=list, description="Error messages")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BaseAgent(ABC):
    """Abstract base class for all DocuMind agents.

    All agents inherit from this class and implement the execute method
    to perform their specialized task. Agents receive the current state
    and return an updated state.
    """

    def __init__(self, name: str) -> None:
        """Initialize the agent with a name."""
        self.name = name
        self.logger = LoggerAdapter(f"agent.{name}")

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState:
        """Execute the agent's primary task.

        Args:
            state: Current workflow state

        Returns:
            Updated workflow state
        """
        pass

    @abstractmethod
    def get_tools(self) -> list[Any]:
        """Return tools available to this agent.

        Returns:
            List of tools (functions or LangChain tools)
        """
        pass

    def _add_trace(self, state: AgentState, message: str) -> AgentState:
        """Add a trace message to the state."""
        from datetime import datetime

        trace_entry = f"[{datetime.utcnow().isoformat()}] {self.name}: {message}"
        return {**state, "agent_trace": state["agent_trace"] + [trace_entry]}

    def _add_error(self, state: AgentState, error: str) -> AgentState:
        """Add an error message to the state."""
        self.logger.error(error)
        return {**state, "errors": state["errors"] + [f"{self.name}: {error}"]}
