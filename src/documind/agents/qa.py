"""QA Agent for question answering over documents using RAG."""

import asyncio
from typing import Any

from documind.agents.base import BaseAgent
from documind.models.state import AgentState
from documind.monitoring import LoggerAdapter, monitor_agent
from documind.services.llm import get_reranker
from documind.services.vectorstore import get_vector_store

logger = LoggerAdapter("agents.qa")

CONFIDENCE_THRESHOLD = 0.3
MAX_RETRIES = 1


class QAAgent(BaseAgent):
    """Agent responsible for answering questions about documents.

    Uses RAG (Retrieval-Augmented Generation) with:
    - Vector similarity search
    - Reranking for improved relevance
    - Source citation
    - Confidence-based retry with broader retrieval
    """

    def __init__(self) -> None:
        super().__init__("qa")

    @monitor_agent("qa")
    async def execute(self, state: AgentState) -> AgentState:
        """Answer questions about the document."""
        questions = state.get("questions", [])

        if not questions:
            self.logger.info(
                "No questions provided, skipping QA",
                document_id=state["document_id"],
            )
            state = self._add_trace(state, "No questions provided, skipping QA")
            return state

        retry_count = state.get("qa_retry_count", 0)
        is_retry = retry_count > 0

        self.logger.info(
            "Starting QA",
            document_id=state["document_id"],
            question_count=len(questions),
            retry=is_retry,
        )

        state = self._add_trace(
            state,
            f"{'Retrying' if is_retry else 'Answering'} {len(questions)} questions"
            + (" with broader retrieval" if is_retry else ""),
        )

        try:
            qa_results = await asyncio.gather(
                *[self._answer_question(q, state, broad=is_retry) for q in questions]
            )

            low_confidence = [r for r in qa_results if r["confidence"] < CONFIDENCE_THRESHOLD]

            self.logger.info(
                "QA completed",
                document_id=state["document_id"],
                results=len(qa_results),
                low_confidence=len(low_confidence),
                retry=is_retry,
            )

            state = self._add_trace(state, f"Answered {len(qa_results)} questions")

            if low_confidence:
                self.logger.warning(
                    "Low confidence answers detected",
                    document_id=state["document_id"],
                    count=len(low_confidence),
                    threshold=CONFIDENCE_THRESHOLD,
                )

            return {**state, "qa_results": list(qa_results)}

        except Exception as e:
            self.logger.exception("QA failed", error=str(e))
            state = self._add_error(state, f"QA failed: {str(e)}")
            return state

    async def _answer_question(
        self, question: str, state: AgentState, broad: bool = False
    ) -> dict[str, Any]:
        """Answer a single question using RAG.

        Args:
            broad: When True, retrieves more candidates with lower diversity
                   (used on confidence-based retry).
        """
        from documind.services.llm import get_llm_service

        llm_service = get_llm_service()

        relevant_chunks = await self._retrieve_chunks(question, state, broad=broad)

        context = "\n\n---\n\n".join(
            f"[Source {i + 1}]\n{chunk['content']}" for i, chunk in enumerate(relevant_chunks)
        )

        system_prompt = """You are a helpful document analyst. Answer the question
            based ONLY on the provided context. If the answer cannot be found in
            the context, say so clearly.

            Provide your answer in a clear, direct manner. Cite your sources using
            [Source N] notation."""

        user_prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        result = await llm_service.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )

        avg_score = sum(c.get("score", 0.5) for c in relevant_chunks) / max(len(relevant_chunks), 1)

        return {
            "question": question,
            "answer": result,
            "confidence": avg_score,
            "low_confidence": avg_score < CONFIDENCE_THRESHOLD,
            "sources": [
                {
                    "chunk_index": c["chunk_index"],
                    "page": c.get("page"),
                    "content_preview": c["content"][:200] + "...",
                }
                for c in relevant_chunks
            ],
        }

    async def _retrieve_chunks(
        self, question: str, state: AgentState, broad: bool = False
    ) -> list[dict[str, Any]]:
        """Retrieve relevant chunks using vector search + reranking.

        Normal mode: top-15 MMR candidates → rerank to top 5.
        Broad mode (retry): top-30 candidates, lower diversity → rerank to top 8.
        Falls back to keyword overlap when vector store is unreachable.
        """
        document_id = state["document_id"]
        limit = 30 if broad else 15
        diversity = 0.1 if broad else 0.3
        top_n = 8 if broad else 5

        try:
            vector_store = get_vector_store()
            candidates = await vector_store.search_mmr(
                query=question,
                document_id=document_id,
                limit=limit,
                diversity=diversity,
            )

            if not candidates:
                raise ValueError("No results from vector store")

            reranker = get_reranker()
            reranked = await reranker.rerank(
                query=question,
                documents=candidates,
                top_n=top_n,
            )

            logger.debug(
                "RAG retrieval complete",
                document_id=document_id,
                candidates=len(candidates),
                returned=len(reranked),
                broad=broad,
            )

            return reranked

        except Exception as e:
            logger.warning(
                "Vector store unavailable, falling back to keyword retrieval",
                error=str(e),
                document_id=document_id,
            )
            question_words = set(question.lower().split())
            scored: list[tuple[float, dict[str, Any]]] = []

            for chunk in state["chunks"]:
                chunk_words = set(chunk["content"].lower().split())
                overlap = len(question_words & chunk_words)
                score = overlap / max(len(question_words), 1)
                scored.append((score, {**chunk, "score": score}))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [chunk for _, chunk in scored[:top_n]]

    def get_tools(self) -> list[Any]:
        """Return tools available to this agent."""
        return []
