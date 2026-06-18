"""ARQ worker settings and entry point."""

from __future__ import annotations

import os
from typing import Any

from .jobs import audit_export, email_notification, webhook_delivery

REDIS_URL = os.environ.get("GRANTLAYER_REDIS_URL", "redis://localhost:6379")


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [webhook_delivery, audit_export, email_notification]
    redis_settings = None  # Resolved lazily to allow env-var override at runtime
    max_jobs = 10
    job_timeout = 300
    max_tries = 3
    keep_result = 3600  # seconds to keep completed job results

    @classmethod
    def get_redis_settings(cls) -> Any:
        try:
            from arq.connections import RedisSettings
            url = os.environ.get("GRANTLAYER_REDIS_URL", REDIS_URL)
            return RedisSettings.from_dsn(url)
        except Exception:
            return None
