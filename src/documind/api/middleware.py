"""API middleware for authentication and rate limiting."""

import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from documind.config import get_settings
from documind.monitoring import LoggerAdapter

logger = LoggerAdapter("api.middleware")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication.

    Validates API key from header for protected endpoints.
    """

    EXEMPT_PATHS = {"/health", "/ready", "/live", "/docs", "/redoc", "/openapi.json", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and validate API key."""
        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        settings = get_settings()

        # Skip auth in development if no key is configured
        if settings.debug and not settings.secret_key.get_secret_value():
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get(settings.api_key_header)

        if not api_key:
            logger.warning(
                "Missing API key",
                path=request.url.path,
                client=request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # Validate API key (simple validation - in production use database lookup)
        valid_keys = self._get_valid_keys()

        if api_key not in valid_keys:
            logger.warning(
                "Invalid API key",
                path=request.url.path,
                client=request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        # Add user info to request state
        request.state.api_key = api_key
        request.state.user_id = valid_keys.get(api_key, "anonymous")

        return await call_next(request)

    def _get_valid_keys(self) -> dict[str, str]:
        """Get valid API keys.

        In production, fetch from database or secrets manager.
        """
        settings = get_settings()
        secret = settings.secret_key.get_secret_value()

        # For demo, accept the configured secret as a valid key
        return {secret: "admin"} if secret else {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests.

    Uses sliding window algorithm with in-memory storage.
    For production, use Redis-based rate limiting.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
    ) -> None:
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limits and process request."""
        # Get client identifier
        client_id = self._get_client_id(request)

        # Check rate limits
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600

        # Clean old requests
        self._requests[client_id] = [t for t in self._requests[client_id] if t > hour_ago]

        # Count recent requests
        minute_count = sum(1 for t in self._requests[client_id] if t > minute_ago)
        hour_count = len(self._requests[client_id])

        # Check limits
        if minute_count >= self.requests_per_minute:
            retry_after = 60 - (now - min(t for t in self._requests[client_id] if t > minute_ago))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded (per minute)",
                headers={"Retry-After": str(int(retry_after))},
            )

        if hour_count >= self.requests_per_hour:
            retry_after = 3600 - (now - min(self._requests[client_id]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded (per hour)",
                headers={"Retry-After": str(int(retry_after))},
            )

        # Record request
        self._requests[client_id].append(now)

        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            self.requests_per_minute - minute_count - 1
        )
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            self.requests_per_hour - hour_count - 1
        )

        return response

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try API key first
        if hasattr(request.state, "api_key"):
            return f"key:{request.state.api_key}"

        # Fall back to IP
        client = request.client
        return f"ip:{client.host}" if client else "ip:unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log request
        logger.info(
            "Request processed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            client=request.client.host if request.client else "unknown",
        )

        # Add timing header
        response.headers["X-Process-Time"] = str(round(duration * 1000, 2))

        return response
