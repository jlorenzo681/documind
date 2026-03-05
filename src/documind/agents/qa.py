"""QA Agent for question answering over documents using RAG."""

from typing import Any

from documind.agents.base import BaseAgent
from documind.models.state import AgentState
from documind.monitoring import LoggerAdapter, monitor_agent
from documind.services.llm import get_reranker
from documind.services.vectorstore import get_vector_store

logger = LoggerAdapter("agents.qa")


class QAAgent(BaseAgent):
    """Agent responsible for answering questions about documents.

    Uses RAG (Retrieval-Augmented Generation) with:
    - Vector similarity search
    - Reranking for improved relevance
    - Source citation
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

        self.logger.info(
            "Starting QA",
            document_id=state["document_id"],
            question_count=len(questions),
        )

        state = self._add_trace(state, f"Answering {len(questions)} questions")

        qa_results: list[dict[str, Any]] = []

        try:
            for question in questions:
                result = await self._answer_question(question, state)
                qa_results.append(result)

            self.logger.info(
                "QA completed",
                document_id=state["document_id"],
                results=len(qa_results),
            )

            state = self._add_trace(state, f"Answered {len(qa_results)} questions")

            return {**state, "qa_results": qa_results}

        except Exception as e:
            self.logger.exception("QA failed", error=str(e))
            state = self._add_error(state, f"QA failed: {str(e)}")
            return state

    async def _answer_question(self, question: str, state: AgentState) -> dict[str, Any]:
        """Answer a single question using RAG."""
        from documind.services.llm import get_llm_service

        llm_service = get_llm_service()

        # Retrieve relevant chunks
        relevant_chunks = await self._retrieve_chunks(question, state)

        # Build context from chunks
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

        # Calculate confidence based on chunk relevance scores
        avg_score = sum(c.get("score", 0.5) for c in relevant_chunks) / max(len(relevant_chunks), 1)

        return {
            "question": question,
            "answer": result,
            "confidence": avg_score,
            "sources": [
                {
                    "chunk_index": c["chunk_index"],
                    "page": c.get("page"),
                    "content_preview": c["content"][:200] + "...",
                }
                for c in relevant_chunks
            ],
        }

    async def _retrieve_chunks(self, question: str, state: AgentState) -> list[dict[str, Any]]:
        """Retrieve relevant chunks for a question using vector search + reranking.

        Stage 1: MMR similarity search via Qdrant (diverse top-15 candidates).
        Stage 2: Cross-encoder reranking to the top 5 by exact relevance.
        Falls back to keyword overlap scoring when the vector store is unreachable.
        """
        document_id = state["document_id"]

        try:
            vector_store = get_vector_store()
            candidates = await vector_store.search_mmr(
                query=question,
                document_id=document_id,
                limit=15,
                diversity=0.3,
            )

            if not candidates:
                raise ValueError("No results from vector store")

            # Rerank candidates with cross-encoder for precision
            reranker = get_reranker()
            reranked = await reranker.rerank(
                query=question,
                documents=candidates,
                top_n=5,
            )

            logger.debug(
                "RAG retrieval complete",
                document_id=document_id,
                candidates=len(candidates),
                returned=len(reranked),
            )

            return reranked

        except Exception as e:
            # Graceful fallback: keyword overlap scoring against in-memory chunks
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
            return [chunk for _, chunk in scored[:5]]

    def get_tools(self) -> list[Any]:
        """Return tools available to this agent."""
        return []
