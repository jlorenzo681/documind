"""Prometheus metrics for DocuMind."""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from prometheus_client import Counter, Gauge, Histogram

P = ParamSpec("P")
R = TypeVar("R")


class MetricsCollector:
    """Centralized metrics collector for DocuMind."""

    def __init__(self) -> None:
        # Request metrics
        self.request_count = Counter(
            "documind_requests_total",
            "Total number of requests",
            ["agent", "status"],
        )

        self.request_duration = Histogram(
            "documind_request_duration_seconds",
            "Request duration in seconds",
            ["agent"],
            buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
        )

        # Agent metrics
        self.active_agents = Gauge(
            "documind_active_agents",
            "Number of active agents",
            ["agent_type"],
        )

        # LLM metrics
        self.token_usage = Counter(
            "documind_tokens_total",
            "Total tokens used",
            ["model", "type"],  # metric type: input/output
        )

        self.llm_calls = Counter(
            "documind_llm_calls_total",
            "Total LLM API calls",
            ["model", "status"],
        )

        self.llm_latency = Histogram(
            "documind_llm_latency_seconds",
            "LLM API call latency",
            ["model"],
            buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
        )

        # Document metrics
        self.documents_processed = Counter(
            "documind_documents_processed_total",
            "Total documents processed",
            ["status"],
        )

        self.document_size = Histogram(
            "documind_document_size_bytes",
            "Document size in bytes",
            buckets=(1000, 10000, 100000, 1000000, 10000000),
        )

        # Vector store metrics
        self.vector_operations = Counter(
            "documind_vector_operations_total",
            "Total vector store operations",
            ["operation", "status"],  # operation: upsert/search
        )

        # Cache metrics
        self.cache_hits = Counter(
            "documind_cache_hits_total",
            "Total cache hits",
        )

        self.cache_misses = Counter(
            "documind_cache_misses_total",
            "Total cache misses",
        )

    def record_request(self, agent: str, status: str, duration: float) -> None:
        """Record a request with its status and duration."""
        self.request_count.labels(agent=agent, status=status).inc()
        self.request_duration.labels(agent=agent).observe(duration)

    def record_token_usage(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record LLM token usage."""
        self.token_usage.labels(model=model, type="input").inc(input_tokens)
        self.token_usage.labels(model=model, type="output").inc(output_tokens)

    def record_llm_call(self, model: str, status: str, latency: float) -> None:
        """Record an LLM API call."""
        self.llm_calls.labels(model=model, status=status).inc()
        self.llm_latency.labels(model=model).observe(latency)


# Global metrics collector instance
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def monitor_agent(agent_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to monitor agent execution with Prometheus metrics."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            metrics = get_metrics_collector()
            metrics.active_agents.labels(agent_type=agent_name).inc()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)  # type: ignore
                metrics.request_count.labels(agent=agent_name, status="success").inc()
                return result
            except Exception:
                metrics.request_count.labels(agent=agent_name, status="error").inc()
                raise
            finally:
                duration = time.time() - start_time
                metrics.request_duration.labels(agent=agent_name).observe(duration)
                metrics.active_agents.labels(agent_type=agent_name).dec()

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            metrics = get_metrics_collector()
            metrics.active_agents.labels(agent_type=agent_name).inc()
            start_time = time.time()

            try:
                result: Any = func(*args, **kwargs)
                metrics.request_count.labels(agent=agent_name, status="success").inc()
                return result  # type: ignore
            except Exception:
                metrics.request_count.labels(agent=agent_name, status="error").inc()
                raise
            finally:
                duration = time.time() - start_time
                metrics.request_duration.labels(agent=agent_name).observe(duration)
                metrics.active_agents.labels(agent_type=agent_name).dec()

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper

    return decorator
