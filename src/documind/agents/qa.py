"""QA Agent for question answering over documents using RAG."""

from typing import Any

from documind.agents.base import BaseAgent
from documind.models.state import AgentState
from documind.monitoring import monitor_agent


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
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from langchain_core.prompts import ChatPromptTemplate

        from documind.config import get_settings

        settings = get_settings()

        # Retrieve relevant chunks
        relevant_chunks = await self._retrieve_chunks(question, state)

        # Build context from chunks
        context = "\n\n---\n\n".join(
            f"[Source {i + 1}]\n{chunk['content']}" for i, chunk in enumerate(relevant_chunks)
        )

        # Generate answer
        llm = ChatOpenAI(
            model=settings.llm.default_model,
            api_key=settings.llm.openai_api_key.get_secret_value(),
            temperature=0.2,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a helpful document analyst. Answer the question 
            based ONLY on the provided context. If the answer cannot be found in 
            the context, say so clearly.
            
            Provide your answer in a clear, direct manner. Cite your sources using 
            [Source N] notation.""",
                ),
                (
                    "user",
                    """Context:
{context}

Question: {question}

Answer:""",
                ),
            ]
        )

        chain = prompt | llm
        result = await chain.ainvoke(
            {
                "context": context,
                "question": question,
            }
        )

        # Calculate confidence based on chunk relevance scores
        avg_score = sum(c.get("score", 0.5) for c in relevant_chunks) / max(len(relevant_chunks), 1)

        return {
            "question": question,
            "answer": str(result.content),
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
        """Retrieve relevant chunks for a question.

        For now, uses simple keyword matching. In production, this would
        use the vector store with embeddings.
        """
        # Simple relevance scoring based on word overlap
        # TODO: Replace with actual vector store retrieval
        question_words = set(question.lower().split())

        scored_chunks: list[tuple[float, dict[str, Any]]] = []

        for chunk in state["chunks"]:
            chunk_words = set(chunk["content"].lower().split())
            overlap = len(question_words & chunk_words)
            score = overlap / max(len(question_words), 1)

            scored_chunks.append(
                (
                    score,
                    {**chunk, "score": score},
                )
            )

        # Sort by score and return top 5
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:5]]

    def get_tools(self) -> list[Any]:
        """Return tools available to this agent."""
        return []
