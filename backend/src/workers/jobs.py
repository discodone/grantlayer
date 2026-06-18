"""ARQ job definitions: webhook_delivery, audit_export, email_notification."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("grantlayer.workers")

# Maximum retry attempts before moving to dead-letter queue
MAX_JOB_RETRIES = 3


async def webhook_delivery(
    ctx: dict,
    subscription_id: str,
    event_type: str,
    payload: dict,
    attempt: int = 0,
) -> dict:
    """Deliver a webhook payload to a subscription URL (async, with retry)."""
    import httpx

    try:
        from ..core.db import get_async_session_maker
        from ..webhooks.repository import WebhookRepository
        session_maker = get_async_session_maker()
        async with session_maker() as session:
            repo = WebhookRepository(session)
            sub = await repo.get_by_id(subscription_id, tenant_id="")
    except Exception as e:
        logger.warning("webhook_delivery: could not load subscription %s: %s", subscription_id, e)
        sub = None

    if sub is None:
        return {"status": "skipped", "reason": "subscription_not_found"}

    try:
        import hashlib
        import hmac
        import json
        sub_url = sub.get("url", "") if isinstance(sub, dict) else getattr(sub, "url", "")
        sub_secret = sub.get("secret", "") if isinstance(sub, dict) else getattr(sub, "secret", "")
        body_bytes = json.dumps(payload).encode()
        secret = (sub_secret or "").encode()
        sig = "sha256=" + hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                sub_url,
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-GrantLayer-Signature": sig,
                    "X-GrantLayer-Event": event_type,
                },
            )
            r.raise_for_status()
        logger.info("webhook_delivery: delivered %s to %s (status %d)", event_type, sub_url, r.status_code)
        return {"status": "delivered", "http_status": r.status_code}
    except Exception as exc:
        if attempt >= MAX_JOB_RETRIES:
            await _move_to_dlq(ctx, "webhook_delivery", {
                "subscription_id": subscription_id,
                "event_type": event_type,
                "payload": payload,
                "error": str(exc),
            })
            return {"status": "dead_letter", "error": str(exc)}
        raise


async def audit_export(
    ctx: dict,
    workspace_id: Optional[str] = None,
    format: str = "csv",
    destination: Optional[str] = None,
) -> dict:
    """Export audit events to CSV (async ARQ job)."""
    try:
        from sqlalchemy import text

        from ..core.db import get_async_engine

        engine = get_async_engine()
        async with engine.connect() as conn:
            query = "SELECT * FROM audit_events"
            params: dict = {}
            if workspace_id:
                query += " WHERE workspace_id = :ws"
                params["ws"] = workspace_id
            query += " ORDER BY seq DESC LIMIT 50000"
            rows = (await conn.execute(text(query).bindparams(**params))).fetchall()

        lines = ["timestamp,subject_id,action,resource,approved"]
        for row in rows:
            row_dict = dict(row._mapping)
            lines.append(",".join([
                str(row_dict.get("timestamp", "")),
                str(row_dict.get("subject_id", "")),
                str(row_dict.get("action", "")),
                str(row_dict.get("resource", "")),
                str(row_dict.get("approved", "")),
            ]))

        csv_content = "\n".join(lines)
        if destination:
            with open(destination, "w") as f:
                f.write(csv_content)

        logger.info("audit_export: exported %d rows", len(rows))
        return {"status": "complete", "rows": len(rows), "destination": destination}
    except Exception as exc:
        logger.error("audit_export: failed: %s", exc)
        return {"status": "error", "error": str(exc)}


async def email_notification(
    ctx: dict,
    to: str,
    template: str,
    context: dict,
    attempt: int = 0,
) -> dict:
    """Send an email notification using the configured SMTP backend (async ARQ job)."""
    try:
        from ..notifications.email import send_email
        await send_email(to=to, template=template, context=context)
        logger.info("email_notification: sent %s to %s", template, to)
        return {"status": "sent", "to": to, "template": template}
    except Exception as exc:
        if attempt >= MAX_JOB_RETRIES:
            await _move_to_dlq(ctx, "email_notification", {
                "to": to, "template": template, "error": str(exc)
            })
            return {"status": "dead_letter", "error": str(exc)}
        raise


async def _move_to_dlq(ctx: dict, job_name: str, data: dict) -> None:
    """Store a failed job in the dead-letter queue (Redis hash)."""
    import json
    import time
    redis = ctx.get("redis")
    if redis is None:
        logger.warning("_move_to_dlq: no redis in ctx")
        return
    dlq_key = f"grantlayer:dlq:{job_name}"
    entry = json.dumps({"job": job_name, "data": data, "failed_at": time.time()})
    try:
        await redis.lpush(dlq_key, entry)
        await redis.ltrim(dlq_key, 0, 999)
        logger.warning("_move_to_dlq: %s → DLQ", job_name)
    except Exception as e:
        logger.error("_move_to_dlq: redis error: %s", e)
