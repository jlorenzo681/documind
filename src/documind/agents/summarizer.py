"""Summarization Agent for generating document summaries."""

from typing import Any

from documind.agents.base import BaseAgent
from documind.models.state import AgentState
from documind.monitoring import monitor_agent


class SummarizationAgent(BaseAgent):
    """Agent responsible for generating multi-level document summaries.

    Produces:
    - Executive summary (1-2 paragraphs)
    - Detailed summary (structured sections)
    - Key points extraction
    """

    def __init__(self) -> None:
        super().__init__("summarizer")

    @monitor_agent("summarizer")
    async def execute(self, state: AgentState) -> AgentState:
        """Generate summaries from the parsed document."""
        self.logger.info(
            "Starting summarization",
            document_id=state["document_id"],
            chunk_count=len(state["chunks"]),
        )

        state = self._add_trace(state, "Starting summarization")

        try:
            # For long documents, use map-reduce approach
            if len(state["chunks"]) > 10:
                summary = await self._map_reduce_summarize(state)
            else:
                summary = await self._direct_summarize(state)

            self.logger.info(
                "Summarization completed",
                document_id=state["document_id"],
            )

            state = self._add_trace(state, "Summarization completed")

            return {**state, "summary": summary}

        except Exception as e:
            self.logger.exception("Summarization failed", error=str(e))
            state = self._add_error(state, f"Summarization failed: {str(e)}")
            return state

    async def _direct_summarize(self, state: AgentState) -> dict[str, Any]:
        """Directly summarize all content at once."""
        from documind.services.llm import get_llm_service

        llm_service = get_llm_service()

        # Combine all chunks
        full_text = "\n\n".join(chunk["content"] for chunk in state["chunks"])

        # Generate executive summary
        executive_system = """You are an expert document analyst. Provide a concise
            executive summary of the document in 2-3 paragraphs. Focus on the
            most important information that a busy executive would need to know."""

        executive_result = await llm_service.generate(
            prompt=full_text,
            system_prompt=executive_system,
            temperature=0.3,
        )

        # Generate detailed summary with key points
        detailed_system = """You are an expert document analyst. Analyze the document
            and provide:
            1. A detailed summary organized by topic/section
            2. A list of key points (bullet points)
            3. The detected document type (e.g., contract, report, policy, etc.)

            Format your response as JSON with keys:
            'detailed_summary', 'key_points' (list), 'document_type'"""

        detailed_result = await llm_service.generate(
            prompt=full_text,
            system_prompt=detailed_system,
            temperature=0.3,
        )

        # Parse results
        import json

        try:
            details = json.loads(detailed_result)
        except json.JSONDecodeError:
            details = {
                "detailed_summary": detailed_result,
                "key_points": [],
                "document_type": "unknown",
            }

        return {
            "executive_summary": executive_result,
            "detailed_summary": details.get("detailed_summary", ""),
            "key_points": details.get("key_points", []),
            "document_type": details.get("document_type", "unknown"),
        }

    async def _map_reduce_summarize(self, state: AgentState) -> dict[str, Any]:
        """Use map-reduce for long documents."""
        from documind.services.llm import get_llm_service

        llm_service = get_llm_service()

        # Map phase: summarize each chunk
        chunk_system = """Summarize the following section of a document.
            Extract the main points and key information."""

        chunk_summaries = []
        for chunk in state["chunks"]:
            result = await llm_service.generate(
                prompt=chunk["content"],
                system_prompt=chunk_system,
                temperature=0.3,
            )
            chunk_summaries.append(result)

        # Reduce phase: combine chunk summaries
        combined = "\n\n---\n\n".join(chunk_summaries)

        # Now use direct summarization on the combined summaries
        temp_state = {**state, "chunks": [{"content": combined}]}
        return await self._direct_summarize(temp_state)

    def get_tools(self) -> list[Any]:
        """Return tools available to this agent."""
        return []
