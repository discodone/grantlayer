"""GrantLayer FastAPI application."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from ..core import config
from ..core.db import init_db
from ..core.logging_utils import get_logger, reset_correlation_id, set_correlation_id
from ..core.rate_limiter import RateLimiter
from ..core.structured_logging import normalize_correlation_id
from .routers import (
    auth,
    health,
    grants,
    grant_requests,
    audit_events,
    executions,
    evidence,
    provenance,
    auditor,
    compliance,
    operators_me,
    admin,
    challenges,
    agent_permissions,
    approvals,
    decision_provenance,
    policy_requirements,
    demo,
)

_logger = get_logger("grantlayer.fastapi")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Initialize DB on startup."""
    app.state.start_time = time.time()
    init_db()
    _logger.info("GrantLayer FastAPI layer started (Phase 2)")
    yield
    _logger.info("GrantLayer FastAPI layer shutting down")


def create_app() -> FastAPI:
    """Factory so tests can create isolated app instances."""
    app = FastAPI(
        title="GrantLayer",
        description="Secure AI Agent Grant Management — FastAPI layer (Phase 1)",
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Per-app rate limiter — created here so each create_app() call (and each
    # test) gets an isolated instance with no shared state.
    app.state.auth_rate_limiter = RateLimiter(
        auth_limit=config.GRANTLAYER_RATE_LIMIT_AUTH,
        window_seconds=60,
    )

    # CORS — exact-match allowlist, no reflection
    if config.CORS_ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.CORS_ALLOWED_ORIGINS),
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-Correlation-ID"],
        )

    # Request logging and correlation ID propagation
    @app.middleware("http")
    async def _request_logging(request: Request, call_next):
        correlation_id = normalize_correlation_id(request.headers.get("X-Correlation-ID"))
        token = set_correlation_id(correlation_id)
        started = time.perf_counter()
        status_code = 500
        had_exception = False

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        except Exception:
            had_exception = True
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            _logger.error(
                "api_request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "correlation_id": correlation_id,
                },
                exc_info=True,
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            if not had_exception:
                _logger.info(
                    "api_request",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "correlation_id": correlation_id,
                    },
                )
            reset_correlation_id(token)

    # Security headers on every response
    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers[key] = value
        return response

    # Exception handler: pass through dict details from routers; use generic for unmatched routes
    @app.exception_handler(404)
    async def _not_found(request: Request, exc):
        if isinstance(getattr(exc, "detail", None), dict):
            return JSONResponse(status_code=404, content=exc.detail)
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "errorCode": "not_found",
                "reason": "The requested resource does not exist.",
            },
        )

    # Pass through dict details for other 4xx/5xx HTTPExceptions too
    @app.exception_handler(401)
    async def _unauthorized(request: Request, exc):
        if isinstance(getattr(exc, "detail", None), dict):
            return JSONResponse(status_code=401, content=exc.detail)
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "errorCode": "unauthorized", "reason": "Authentication required."},
        )

    @app.exception_handler(403)
    async def _forbidden(request: Request, exc):
        if isinstance(getattr(exc, "detail", None), dict):
            return JSONResponse(status_code=403, content=exc.detail)
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden", "errorCode": "forbidden", "reason": "Access denied."},
        )

    @app.exception_handler(422)
    async def _unprocessable(request: Request, exc):
        if isinstance(getattr(exc, "detail", None), dict):
            return JSONResponse(status_code=422, content=exc.detail)
        return JSONResponse(
            status_code=422,
            content={"error": "Unprocessable Entity", "errorCode": "unprocessable_entity", "reason": "The request could not be processed."},
        )

    @app.exception_handler(501)
    async def _not_implemented(request: Request, exc):
        if isinstance(getattr(exc, "detail", None), dict):
            return JSONResponse(status_code=501, content=exc.detail)
        return JSONResponse(
            status_code=501,
            content={"error": "Not Implemented", "errorCode": "not_implemented", "reason": "Feature not available."},
        )

    # Health endpoints — no versioning (infrastructure checks must be stable)
    app.include_router(health.router)

    # All API routers under /v1/
    app.include_router(auth.router, prefix="/v1")
    app.include_router(grants.router, prefix="/v1")
    app.include_router(grant_requests.router, prefix="/v1")
    app.include_router(audit_events.router, prefix="/v1")
    app.include_router(executions.router, prefix="/v1")
    app.include_router(evidence.router, prefix="/v1")
    app.include_router(provenance.router, prefix="/v1")
    app.include_router(auditor.router, prefix="/v1")
    app.include_router(compliance.router, prefix="/v1")
    app.include_router(operators_me.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")
    app.include_router(challenges.router, prefix="/v1")
    app.include_router(agent_permissions.router, prefix="/v1")
    app.include_router(approvals.router, prefix="/v1")
    app.include_router(decision_provenance.router, prefix="/v1")
    app.include_router(policy_requirements.router, prefix="/v1")
    app.include_router(demo.router, prefix="/v1")
    if config.ENABLE_DEMO_ENDPOINTS:
        app.include_router(demo.tamper_router, prefix="/v1")

    # Backward-compat redirects: unversioned paths → /v1/ (307 Temporary Redirect)
    _COMPAT_PREFIXES = [
        "/auth", "/grants", "/grant-requests", "/grant-executions", "/audit-events",
        "/evidence", "/provenance", "/auditor", "/compliance", "/operators",
        "/admin", "/challenges", "/agent-permissions", "/approvals",
        "/decision-provenance", "/policy-requirements", "/demo", "/demo-action",
    ]

    def _make_redirect_handler():
        async def _redirect(request: Request) -> RedirectResponse:
            url = f"/v1{request.url.path}"
            if request.url.query:
                url += f"?{request.url.query}"
            return RedirectResponse(url=url, status_code=307)
        return _redirect

    _methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    for _pfx in _COMPAT_PREFIXES:
        _h = _make_redirect_handler()
        app.add_api_route(_pfx, _h, methods=_methods, include_in_schema=False)
        app.add_api_route(f"{_pfx}/{{path:path}}", _h, methods=_methods, include_in_schema=False)

    return app


# Module-level app instance for ASGI servers (uvicorn, gunicorn+uvicorn workers)
app = create_app()
