"""Job queue helper — enqueue jobs via ARQ (or stub when Redis unavailable)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("grantlayer.workers.queue")

_REDIS_URL = os.environ.get("GRANTLAYER_REDIS_URL", "redis://localhost:6379")


async def enqueue_job(job_name: str, *args: Any, **kwargs: Any) -> Optional[str]:
    """Enqueue a job. Returns job_id or None if ARQ/Redis is unavailable."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        pool = await create_pool(RedisSettings.from_dsn(_REDIS_URL))
        job = await pool.enqueue_job(job_name, *args, **kwargs)
        await pool.close()
        return job.job_id if job else None
    except Exception as exc:
        logger.warning("enqueue_job: ARQ unavailable (%s), job %s dropped", exc, job_name)
        return None


async def get_job_status(job_id: str) -> dict:
    """Get the status of a queued or completed job."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        pool = await create_pool(RedisSettings.from_dsn(_REDIS_URL))
        all_results = await pool.all_job_results()
        await pool.close()
        for job_info in all_results:
            if str(job_info.job_id) == job_id:
                return {
                    "job_id": job_id,
                    "status": "complete" if job_info.success else "failed",
                    "result": job_info.result if job_info.success else None,
                    "error": str(job_info.result) if not job_info.success else None,
                }
        return {"job_id": job_id, "status": "not_found"}
    except Exception as exc:
        logger.warning("get_job_status: ARQ unavailable: %s", exc)
        return {"job_id": job_id, "status": "unknown", "error": str(exc)}


async def get_queue_stats() -> dict:
    """Return queue statistics (length, DLQ length)."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        pool = await create_pool(RedisSettings.from_dsn(_REDIS_URL))
        stats = await pool.queued_jobs()
        await pool.close()
        return {"queued": len(stats), "status": "ok"}
    except Exception:
        return {"queued": 0, "status": "unavailable"}
