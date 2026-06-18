"""Job status API router — GET /jobs/{job_id}."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Header, HTTPException

from ...workers.queue import get_job_status, get_queue_stats
from ..deps import require_admin

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    require_admin(authorization)
    status = await get_job_status(job_id)
    if status.get("status") == "not_found":
        raise HTTPException(
            status_code=404,
            detail={"error": "Job not found", "errorCode": "job_not_found", "reason": f"No job with id {job_id}"},
        )
    return status


@router.get("")
async def list_jobs(
    authorization: Annotated[Optional[str], Header()] = None,
) -> Any:
    require_admin(authorization)
    return await get_queue_stats()
