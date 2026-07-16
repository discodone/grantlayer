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


def _validate_anchor_startup() -> None:
    """Fail-closed worker boot gate for Cardano anchoring.

    The ARQ worker is the process that actually spends ADA, yet it bypasses the
    FastAPI app boot gate. Re-run CardanoConfig.startup_errors() here so the worker
    REFUSES TO BOOT when anchoring is enabled but misconfigured — missing spend
    caps on mainnet, or a signing key that does not derive to the pinned
    GRANTLAYER_CARDANO_EXPECTED_ADDRESS (wrong key / preprod-under-mainnet
    collision). When anchoring is disabled (default) this is a no-op.
    """
    errs = CardanoConfig.from_env().startup_errors()
    if errs:
        raise RuntimeError(
            "ARQ worker refuses to boot — Cardano anchoring is misconfigured:\n"
            + "\n".join(errs)
        )


def _build_cron_jobs() -> list[Any]:
    """Register the daily Cardano anchor as a cron job at the configured time.

    Read once at worker boot to fix the schedule; the job itself re-reads config
    and self-gates at entry (Gate 4a/4b), so registering unconditionally is safe
    even when anchoring is disabled — a disabled job simply skips on every run.
    """
    from arq import cron  # propagates ImportError if arq not installed

    _validate_anchor_startup()  # refuse to boot on a misconfigured anchor setup
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
