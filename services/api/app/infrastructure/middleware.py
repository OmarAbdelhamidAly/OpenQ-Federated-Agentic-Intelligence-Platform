"""CORS, security headers, rate limiting, and request logging middleware."""

from __future__ import annotations

import time
import uuid
from typing import Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.infrastructure.config import settings

logger = structlog.get_logger(__name__)

# ── Rate Limiter (shared instance — imported by routers) ──────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


def setup_middleware(app: FastAPI) -> None:
    """Attach all middleware to the FastAPI application."""

    # ── Rate Limiter ───────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── CORS ──────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Security Headers ──────────────────────────────────────
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next: Callable) -> Response:
        """Add security-hardening HTTP response headers to every response."""
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Prevent sensitive API responses from being cached by browsers/proxies
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # ── Request Logging ───────────────────────────────────────
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next: Callable) -> Response:
        """Trace request execution and log results with contextual data."""
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Bind request-id so all logs in this task have it automatically
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        request.state.request_id = request_id

        try:
            response: Response = await call_next(request)
            
            # Record metrics or additional response info here if needed
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=request.client.host if request.client else "unknown",
            )
            
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                error=str(exc),
                duration_ms=duration_ms,
                exc_info=True,
            )
            # Re-raise so FastAPI's exception handlers can catch it
            raise exc
