"""GL-228/GL-229: FastAPI application (strangler fig pattern).

server.py continues to run in parallel.  This module provides a FastAPI
app that can be mounted or run alongside server.py during the migration.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import config
from ..db import init_db
from ..logging_utils import get_logger
from .routers import (
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
    init_db()
    _logger.info("GrantLayer FastAPI layer started (GL-229 Phase 2)")
    yield
    _logger.info("GrantLayer FastAPI layer shutting down")


def create_app() -> FastAPI:
    """Factory so tests can create isolated app instances."""
    app = FastAPI(
        title="GrantLayer",
        description="Secure AI Agent Grant Management — FastAPI layer (GL-228 Phase 1)",
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS — same policy as server.py (exact-match allowlist, no reflection)
    if config.CORS_ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.CORS_ALLOWED_ORIGINS),
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
        )

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
    @app.exception_handler(403)
    async def _forbidden(request: Request, exc):
        if isinstance(getattr(exc, "detail", None), dict):
            return JSONResponse(status_code=403, content=exc.detail)
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden", "errorCode": "forbidden", "reason": "Access denied."},
        )

    # Routers
    app.include_router(health.router)
    app.include_router(grants.router)
    app.include_router(grant_requests.router)
    app.include_router(audit_events.router)
    app.include_router(executions.router)
    app.include_router(evidence.router)
    app.include_router(provenance.router)
    app.include_router(auditor.router)
    app.include_router(compliance.router)
    app.include_router(operators_me.router)
    app.include_router(admin.router)
    app.include_router(challenges.router)
    app.include_router(agent_permissions.router)
    app.include_router(approvals.router)
    app.include_router(decision_provenance.router)
    app.include_router(policy_requirements.router)
    app.include_router(demo.router)

    return app


# Module-level app instance for ASGI servers (uvicorn, gunicorn+uvicorn workers)
app = create_app()
