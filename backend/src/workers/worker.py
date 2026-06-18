"""ARQ worker settings and entry point."""

from __future__ import annotations

import os
from typing import Any

from .jobs import audit_export, email_notification, webhook_delivery

REDIS_URL = os.environ.get("GRANTLAYER_REDIS_URL", "redis://localhost:6379")


def _build_redis_settings() -> Any:
    from arq.connections import RedisSettings  # propagates ImportError if arq not installed
    try:
        return RedisSettings.from_dsn(REDIS_URL)
    except Exception as exc:
        raise RuntimeError(f"ARQ worker: invalid REDIS_URL {REDIS_URL!r}") from exc


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [webhook_delivery, audit_export, email_notification]
    redis_settings = _build_redis_settings()
    max_jobs = 10
    job_timeout = 300
    max_tries = 3
    keep_result = 3600  # seconds to keep completed job results
