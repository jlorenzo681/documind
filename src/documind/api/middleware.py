"""API middleware for authentication and rate limiting."""

import time
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

        # Skip auth entirely in development mode
        if settings.debug:
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

    Uses sliding window algorithm with Redis sorted sets.
    Falls open if Redis is unavailable (allows requests through).
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
        self._redis = None

    async def _get_redis(self):
        """Get or create async Redis client."""
        if self._redis is None:
            import redis.asyncio as aioredis

            settings = get_settings()
            self._redis = aioredis.from_url(
                settings.redis.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limits and process request."""
        client_id = self._get_client_id(request)
        now = time.time()

        minute_count = 0
        hour_count = 0

        try:
            redis = await self._get_redis()

            minute_key = f"ratelimit:{client_id}:minute"
            hour_key = f"ratelimit:{client_id}:hour"

            # Clean expired entries and count
            await redis.zremrangebyscore(minute_key, 0, now - 60)
            minute_count = await redis.zcard(minute_key)

            if minute_count >= self.requests_per_minute:
                oldest = await redis.zrange(minute_key, 0, 0, withscores=True)
                retry_after = 60 - (now - oldest[0][1]) if oldest else 60
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded (per minute)",
                    headers={"Retry-After": str(int(retry_after))},
                )

            await redis.zremrangebyscore(hour_key, 0, now - 3600)
            hour_count = await redis.zcard(hour_key)

            if hour_count >= self.requests_per_hour:
                oldest = await redis.zrange(hour_key, 0, 0, withscores=True)
                retry_after = 3600 - (now - oldest[0][1]) if oldest else 3600
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded (per hour)",
                    headers={"Retry-After": str(int(retry_after))},
                )

            # Record this request
            member = f"{now}"
            await redis.zadd(minute_key, {member: now})
            await redis.expire(minute_key, 61)
            await redis.zadd(hour_key, {member: now})
            await redis.expire(hour_key, 3601)

        except HTTPException:
            raise
        except Exception as e:
            # Fail open — allow request if Redis is down
            logger.warning("Rate limiter Redis unavailable, allowing request", error=str(e))

        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            max(self.requests_per_minute - minute_count - 1, 0)
        )
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            max(self.requests_per_hour - hour_count - 1, 0)
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
