"""Job status API router — GET /jobs/{job_id}."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...workers.queue import get_job_status, get_queue_stats
from ..deps import AdminScope, require_admin_scope

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    scope: AdminScope = Depends(require_admin_scope),
) -> Any:
    # ARQ jobs carry no tenant dimension, so a tenant-scoped admin's ownership of a
    # job cannot be proven (a job result may hold another tenant's data, e.g. a GDPR
    # export). Restrict to deployment-level admins; tenant-scoped admins get 403.
    scope.require_deployment_admin()
    status = await get_job_status(job_id)
    if status.get("status") == "not_found":
        raise HTTPException(
            status_code=404,
            detail={"error": "Job not found", "errorCode": "job_not_found", "reason": f"No job with id {job_id}"},
        )
    return status


@router.get("")
async def list_jobs(
    scope: AdminScope = Depends(require_admin_scope),
) -> Any:
    # Queue stats are deployment-wide infrastructure metrics, not tenant data.
    scope.require_deployment_admin()
    return await get_queue_stats()
