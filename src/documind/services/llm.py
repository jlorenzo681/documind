"""LLM service with model routing and optimization."""

import re
from typing import Any

from documind.config import get_settings
from documind.monitoring import LoggerAdapter, get_metrics_collector

logger = LoggerAdapter("services.llm")


class ModelRouter:
    """Routes requests to optimal models based on complexity.

    Analyzes query complexity and routes to:
    - Simple queries → gpt-4o-mini (fast, cheap)
    - Standard queries → gpt-4o (balanced)
    - Complex queries → claude-3-5-sonnet (high quality)
    """

    def __init__(self) -> None:
        """Initialize the model router."""
        self.settings = get_settings()
        self.metrics = get_metrics_collector()

        self.models = {
            "simple": self.settings.llm.simple_model,
            "standard": self.settings.llm.default_model,
            "complex": self.settings.llm.complex_model,
        }

    def route(self, query: str, context_length: int = 0) -> str:
        """Route a query to the optimal model.

        Args:
            query: The query text
            context_length: Length of context in characters

        Returns:
            Model identifier
        """
        complexity = self._analyze_complexity(query, context_length)

        if complexity < 0.3:
            model_tier = "simple"
        elif complexity < 0.7:
            model_tier = "standard"
        else:
            model_tier = "complex"

        model = self.models[model_tier]

        logger.debug(
            "Routed query to model",
            complexity=complexity,
            tier=model_tier,
            model=model,
        )

        return model

    def _analyze_complexity(self, query: str, context_length: int) -> float:
        """Analyze query complexity (0-1 scale).

        Factors:
        - Query length
        - Presence of complex instructions
        - Context size
        - Technical terms
        - Multi-step reasoning indicators
        """
        score = 0.0

        # Query length factor
        if len(query) > 500:
            score += 0.2
        elif len(query) > 200:
            score += 0.1

        # Context length factor
        if context_length > 10000:
            score += 0.3
        elif context_length > 5000:
            score += 0.2
        elif context_length > 2000:
            score += 0.1

        # Complex instruction patterns
        complex_patterns = [
            r"compare.*and.*",
            r"analyze.*in detail",
            r"step by step",
            r"explain.*why",
            r"summarize.*and.*recommend",
            r"identify.*all",
            r"what are the implications",
            r"legal.*implications",
            r"compliance.*with",
        ]

        for pattern in complex_patterns:
            if re.search(pattern, query.lower()):
                score += 0.1

        # Technical terms
        technical_terms = [
            "liability",
            "indemnification",
            "jurisdiction",
            "confidentiality",
            "intellectual property",
            "fiduciary",
            "compliance",
            "regulatory",
            "statutory",
        ]

        term_count = sum(1 for term in technical_terms if term in query.lower())
        score += min(term_count * 0.05, 0.2)

        return min(score, 1.0)


class LLMService:
    """Service for LLM interactions with optimization.

    Provides:
    - Unified interface for multiple LLM providers
    - Model routing based on complexity
    - Token usage tracking
    - Retry logic with fallbacks
    """

    def __init__(self) -> None:
        """Initialize the LLM service."""
        self.settings = get_settings()
        self.metrics = get_metrics_collector()
        self.router = ModelRouter()
        self._clients: dict[str, Any] = {}

    def _get_openai_client(self) -> Any:
        """Get or create OpenAI client."""
        if "openai" not in self._clients:
            from openai import AsyncOpenAI

            self._clients["openai"] = AsyncOpenAI(
                api_key=self.settings.llm.openai_api_key.get_secret_value()
            )
        return self._clients["openai"]

    def _get_anthropic_client(self) -> Any:
        """Get or create Anthropic client."""
        if "anthropic" not in self._clients:
            from anthropic import AsyncAnthropic

            self._clients["anthropic"] = AsyncAnthropic(
                api_key=self.settings.llm.anthropic_api_key.get_secret_value()
            )
        return self._clients["anthropic"]

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        auto_route: bool = True,
    ) -> str:
        """Generate a response using the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Specific model to use (None for auto-routing)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            auto_route: Whether to auto-route based on complexity

        Returns:
            Generated response text
        """
        import time

        # Select model
        if model is None and auto_route:
            model = self.router.route(prompt, len(system_prompt or ""))
        elif model is None:
            model = self.settings.llm.default_model

        start_time = time.time()

        try:
            if "claude" in model.lower():
                response = await self._generate_anthropic(
                    prompt, system_prompt, model, temperature, max_tokens
                )
            else:
                response = await self._generate_openai(
                    prompt, system_prompt, model, temperature, max_tokens
                )

            latency = time.time() - start_time
            self.metrics.record_llm_call(model, "success", latency)

            return response

        except Exception as e:
            latency = time.time() - start_time
            self.metrics.record_llm_call(model, "error", latency)
            logger.exception("LLM generation failed", model=model, error=str(e))
            raise

    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate using OpenAI."""
        client = self._get_openai_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Track tokens
        usage = response.usage
        if usage:
            self.metrics.record_token_usage(model, usage.prompt_tokens, usage.completion_tokens)

        return response.choices[0].message.content or ""

    async def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate using Anthropic."""
        client = self._get_anthropic_client()

        message = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
        )

        # Track tokens
        self.metrics.record_token_usage(
            model, message.usage.input_tokens, message.usage.output_tokens
        )

        return message.content[0].text


class Reranker:
    """Reranks search results for improved relevance.

    Uses Cohere rerank API or cross-encoder models.
    """

    def __init__(self, provider: str = "cohere") -> None:
        """Initialize the reranker.

        Args:
            provider: Reranking provider ("cohere" or "cross-encoder")
        """
        self.provider = provider
        self.settings = get_settings()
        self._client: Any = None

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: Documents with "content" field
            top_n: Number of top results to return

        Returns:
            Reranked documents with scores
        """
        if not documents:
            return []

        if self.provider == "cohere":
            return await self._rerank_cohere(query, documents, top_n)
        else:
            return await self._rerank_cross_encoder(query, documents, top_n)

    async def _rerank_cohere(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_n: int,
    ) -> list[dict[str, Any]]:
        """Rerank using Cohere."""
        import cohere

        if self._client is None:
            self._client = cohere.AsyncClient(
                api_key=self.settings.llm.cohere_api_key.get_secret_value()
            )

        # Extract document texts
        texts = [doc.get("content", "") for doc in documents]

        response = await self._client.rerank(
            query=query,
            documents=texts,
            top_n=top_n,
            model="rerank-english-v3.0",
        )

        # Map back to original documents with new scores
        reranked = []
        for result in response.results:
            doc = documents[result.index].copy()
            doc["rerank_score"] = result.relevance_score
            reranked.append(doc)

        return reranked

    async def _rerank_cross_encoder(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_n: int,
    ) -> list[dict[str, Any]]:
        """Rerank using cross-encoder model."""
        import asyncio
        from sentence_transformers import CrossEncoder

        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

        # Prepare pairs
        pairs = [(query, doc.get("content", "")) for doc in documents]

        def _score():
            return model.predict(pairs)

        scores = await asyncio.to_thread(_score)

        # Sort by score
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        reranked = []
        for doc, score in scored_docs[:top_n]:
            doc_copy = doc.copy()
            doc_copy["rerank_score"] = float(score)
            reranked.append(doc_copy)

        return reranked


# Default instances
_llm_service: LLMService | None = None
_reranker: Reranker | None = None


def get_llm_service() -> LLMService:
    """Get the default LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def get_reranker() -> Reranker:
    """Get the default reranker instance."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker
