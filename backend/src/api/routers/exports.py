"""Data export endpoints — CSV and PDF downloads."""

from __future__ import annotations

import csv
import io
import time
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit.audit_log import append_event
from ...core.models import AuditEvent
from ..deps import get_async_db, resolve_auth_and_workspace

router = APIRouter(prefix="/exports", tags=["exports"])

_LARGE_EXPORT_THRESHOLD = 10_000


async def _fetch_grants(db: AsyncSession, workspace_id: str, tenant_id: str, revoked: Optional[bool] = None) -> list[dict]:
    from sqlalchemy import text
    query = "SELECT id, subject_id, action, resource, role, valid_from, valid_until, revoked, created_at, reason FROM grants WHERE tenant_id = :tid"
    params: dict[str, Any] = {"tid": tenant_id}
    if workspace_id:
        query += " AND workspace_id = :wid"
        params["wid"] = workspace_id
    if revoked is not None:
        query += " AND revoked = :rev"
        params["rev"] = 1 if revoked else 0
    query += " ORDER BY created_at DESC LIMIT 50000"

    def _run(sync_sess: Any) -> list[dict]:
        rows = sync_sess.execute(text(query).bindparams(**params)).fetchall()
        return [dict(r._mapping) for r in rows]

    return await db.run_sync(_run)


async def _fetch_audit_events(db: AsyncSession, workspace_id: str, tenant_id: str) -> list[dict]:
    from sqlalchemy import text
    query = (
        "SELECT timestamp, subject_id, action, resource, approved, reason, scope "
        "FROM audit_events WHERE tenant_id = :tid"
    )
    params: dict[str, Any] = {"tid": tenant_id}
    if workspace_id:
        query += " AND workspace_id = :wid"
        params["wid"] = workspace_id
    query += " ORDER BY seq DESC LIMIT 100000"

    def _run(sync_sess: Any) -> list[dict]:
        rows = sync_sess.execute(text(query).bindparams(**params)).fetchall()
        return [dict(r._mapping) for r in rows]

    return await db.run_sync(_run)


def _rows_to_csv(rows: list[dict], fields: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _generate_pdf(grant: dict) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("GrantLayer — Grant Report", styles["Title"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}", styles["Normal"]))
        story.append(Spacer(1, 12))

        data = [["Field", "Value"]]
        for key in ("id", "subject_id", "action", "resource", "role", "valid_from", "valid_until", "revoked", "reason", "created_at"):
            val = str(grant.get(key, ""))
            data.append([key, val])

        t = Table(data, colWidths=[150, 330])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        doc.build(story)
        return buf.getvalue()
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail={"error": "PDF generation not available", "errorCode": "pdf_unavailable",
                    "reason": "reportlab is not installed."},
        )


@router.get("/grants.csv")
async def export_grants_csv(
    authorization: Annotated[Optional[str], Header()] = None,
    revoked: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    auth_ctx, ws_ctx = resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin", "auditor"])
    tenant_id: str = ws_ctx.get("tenant_id") or "demo"
    workspace_id: str = ws_ctx.get("workspace_id") or ""

    rows = await _fetch_grants(db, workspace_id=workspace_id, tenant_id=tenant_id, revoked=revoked)

    event = AuditEvent(
        subject_id=auth_ctx.get("sub", "export"),
        role=auth_ctx.get("role", "auditor"),
        action="export_grants_csv",
        resource="grants",
        approved=True,
        reason="Data export",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        scope="export",
    )
    await db.run_sync(lambda s: append_event(event, conn=s.connection()))

    fields = ["id", "subject_id", "action", "resource", "role", "valid_from", "valid_until", "revoked", "created_at", "reason"]
    csv_content = _rows_to_csv(rows, fields)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=grants.csv"},
    )


@router.get("/audit.csv")
async def export_audit_csv(
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    auth_ctx, ws_ctx = resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin", "auditor"])
    tenant_id: str = ws_ctx.get("tenant_id") or "demo"
    workspace_id: str = ws_ctx.get("workspace_id") or ""

    rows = await _fetch_audit_events(db, workspace_id=workspace_id, tenant_id=tenant_id)

    event = AuditEvent(
        subject_id=auth_ctx.get("sub", "export"),
        role=auth_ctx.get("role", "auditor"),
        action="export_audit_csv",
        resource="audit_events",
        approved=True,
        reason="Data export",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        scope="export",
    )
    await db.run_sync(lambda s: append_event(event, conn=s.connection()))

    fields = ["timestamp", "subject_id", "action", "resource", "approved", "reason", "scope"]
    csv_content = _rows_to_csv(rows, fields)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit.csv"},
    )


@router.get("/grants/{grant_id}/report.pdf")
async def export_grant_pdf(
    grant_id: str,
    authorization: Annotated[Optional[str], Header()] = None,
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    auth_ctx, ws_ctx = resolve_auth_and_workspace(authorization, required_roles=["owner", "grant_admin", "auditor"])
    tenant_id: str = ws_ctx.get("tenant_id") or "demo"
    workspace_id: str = ws_ctx.get("workspace_id") or ""

    from sqlalchemy import text as sa_text

    def _fetch_grant(sync_sess: Any) -> Optional[dict]:
        row = sync_sess.execute(
            sa_text("SELECT * FROM grants WHERE id = :gid AND tenant_id = :tid").bindparams(gid=grant_id, tid=tenant_id)
        ).fetchone()
        return dict(row._mapping) if row else None

    grant = await db.run_sync(_fetch_grant)
    if grant is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Grant not found", "errorCode": "grant_not_found",
                    "reason": f"No grant with id {grant_id}"},
        )

    event = AuditEvent(
        subject_id=auth_ctx.get("sub", "export"),
        role=auth_ctx.get("role", "auditor"),
        action="export_grant_pdf",
        resource=f"grants/{grant_id}",
        approved=True,
        reason="PDF report export",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        scope="export",
    )
    await db.run_sync(lambda s: append_event(event, conn=s.connection()))

    pdf_bytes = _generate_pdf(grant)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=grant-{grant_id}.pdf"},
    )
