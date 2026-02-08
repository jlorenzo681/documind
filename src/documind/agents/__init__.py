"""Agent package for DocuMind."""

from documind.agents.base import AgentResult, BaseAgent
from documind.agents.orchestrator import create_orchestrator

__all__ = [
    "AgentResult",
    "BaseAgent",
    "create_orchestrator",
]
