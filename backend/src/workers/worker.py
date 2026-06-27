"""ARQ worker settings and entry point."""

from __future__ import annotations

import os
from typing import Any

from ..anchoring.config import CardanoConfig
from .jobs import (
    anchor_audit_chain,
    audit_export,
    email_notification,
    webhook_delivery,
)

REDIS_URL = os.environ.get("GRANTLAYER_REDIS_URL", "redis://localhost:6379")


def _build_redis_settings() -> Any:
    from arq.connections import RedisSettings  # propagates ImportError if arq not installed
    try:
        return RedisSettings.from_dsn(REDIS_URL)
    except Exception as exc:
        raise RuntimeError(f"ARQ worker: invalid REDIS_URL {REDIS_URL!r}") from exc


def _build_cron_jobs() -> list[Any]:
    """Register the daily Cardano anchor as a cron job at the configured time.

    Read once at worker boot to fix the schedule; the job itself re-reads config
    and self-gates at entry (Gate 4a/4b), so registering unconditionally is safe
    even when anchoring is disabled — a disabled job simply skips on every run.
    """
    from arq import cron  # propagates ImportError if arq not installed

    cfg = CardanoConfig.from_env()
    return [cron(anchor_audit_chain, hour=cfg.cron_hour, minute=cfg.cron_minute)]


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [webhook_delivery, audit_export, email_notification, anchor_audit_chain]
    cron_jobs = _build_cron_jobs()
    redis_settings = _build_redis_settings()
    max_jobs = 10
    job_timeout = 300
    max_tries = 3
    keep_result = 3600  # seconds to keep completed job results
