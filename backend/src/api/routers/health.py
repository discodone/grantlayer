"""Health and readiness endpoints."""

from __future__ import annotations

import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ...core.db import get_db_health, get_engine
from ...core.runtime_config import describe_runtime_config
from ..schemas import DynamicResponse, ReadinessResponse

router = APIRouter(tags=["health"])

_VERSION = "0.19.0"

_ALEMBIC_INI = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "alembic.ini")
)


def _signing_key_status() -> str:
    from ..auth_jwt import is_jwt_enabled
    return "present" if is_jwt_enabled() else "absent"


def _migration_revision() -> str:
    try:
        with get_engine().connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
        if row is None:
            return "no revision"
        rev = row[0]
        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            cfg = Config(_ALEMBIC_INI)
            scripts = ScriptDirectory.from_config(cfg)
            if rev in scripts.get_heads():
                return f"{rev} (head)"
        except Exception:
            pass
        return rev
    except Exception as e:
        return f"error: {e}"


@router.get("/health", response_model=DynamicResponse)
async def health(request: Request):
    try:
        db_health = get_db_health()
        db_status = "ok" if db_health.get("dbConnected") else "error: unreachable"
    except Exception as e:
        db_status = f"error: {e}"

    try:
        start = request.app.state.start_time
    except AttributeError:
        start = None
    uptime = int(time.time() - start) if start is not None else 0

    limiter = getattr(request.app.state, "auth_rate_limiter", None)
    redis_status = limiter.redis_status if limiter is not None else "disabled"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "service": "grantlayer",
        "checkType": "liveness",
        "version": _VERSION,
        "uptime_seconds": uptime,
        "database": db_status,
        "signing_key": _signing_key_status(),
        "migrations": _migration_revision(),
        "redis": redis_status,
    }


@router.get(
    "/readiness",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readiness(request: Request):
    errors: list[str] = []

    try:
        runtime_info = describe_runtime_config()
    except ValueError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "grantlayer",
                "checkType": "readiness",
                "errorCode": "RUNTIME_CONFIG_INVALID",
            },
        )

    # Probe DB connectivity
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_ok = False
        errors.append(f"db: {exc}")

    # Probe Redis connectivity with a LIVE PING at probe time (not a cached
    # property), so a Redis that dies post-startup flips readiness to 503 on the
    # next probe. A configured-but-unreachable Redis is a hard readiness failure;
    # an unconfigured Redis ("disabled") is not a dependency.
    limiter = getattr(request.app.state, "auth_rate_limiter", None)
    redis_ok = True
    if limiter is not None:
        probe = getattr(limiter, "live_redis_health", None)
        if callable(probe):
            redis_status = probe()
        else:
            redis_status = getattr(limiter, "redis_status", "disabled")
        if redis_status not in ("ok", "connected", "disabled"):
            redis_ok = False
            errors.append(f"redis: {redis_status}")

    if not db_ok or not redis_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "grantlayer",
                "checkType": "readiness",
                "errors": errors,
                "errorCode": "DEPENDENCY_UNAVAILABLE",
            },
        )

    return ReadinessResponse(
        status="ready",
        service="grantlayer",
        checkType="readiness",
        runtimeMode=runtime_info.get("runtimeMode"),
        isProductionLike=runtime_info.get("isProductionLike"),
    )
