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


async def anchor_audit_chain(ctx: dict, workspace_id: Optional[str] = None) -> dict:
    """Daily fail-closed Cardano anchor of one workspace's audit-export head.

    The worker process bypasses the app boot gates, so this re-checks full
    configuration AND chain reachability at job start, and never leaves a partial
    anchor. The body is synchronous (the anchor read + ORM writes are sync) and is
    run off the event loop via a thread.
    """
    import asyncio

    return await asyncio.to_thread(_anchor_audit_chain_sync, workspace_id)


def _exercise_anchor_grant(config, workspace_id: str, maker) -> dict:
    """Exercise the anchor-writer grant through the standard decision path.

    Challenge mint + consume (single-use, no legacy mode), policy
    evaluation, signature gate, execution row, chain-linked audit event,
    use-count consumption — identical semantics to any /v1/exercise call,
    run in-process. Returns the decision dict; raises when the decision
    path is unavailable (unresolvable workspace/tenant included).
    """
    from ..auth.challenges import create_challenge
    from ..core.orm import Workspace
    from ..demo.demo_action import handle_demo_action

    with maker() as session:
        ws_row = session.get(Workspace, workspace_id)
        tenant_id = ws_row.tenant_id if ws_row is not None else None
    if tenant_id is None:
        raise RuntimeError(
            f"workspace {workspace_id} has no row — cannot resolve tenant"
        )

    subject = "anchor-writer"
    action = "submit_anchor"
    resource = f"cardano/{config.network}"
    challenge = create_challenge(
        subject, action, resource, tenant_id=tenant_id, workspace_id=workspace_id
    )
    return handle_demo_action(
        subject_id=subject,
        role="agent",
        action=action,
        resource=resource,
        challenge_id=challenge.id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )


def _anchor_audit_chain_sync(workspace_id: Optional[str]) -> dict:
    import uuid
    from datetime import datetime, timezone

    from ..anchoring import writer
    from ..anchoring.config import CardanoConfig
    from ..api.routers.audit_compliance import anchor_head
    from ..core.db import get_session_maker
    from ..core.orm import AnchorRecord

    config = CardanoConfig.from_env()
    if workspace_id is None:
        workspace_id = config.workspace_id

    # Gate 4a — re-check full configuration (worker bypasses the boot gates).
    if not config.is_fully_configured():
        logger.warning("anchor_audit_chain: not fully configured — skipping")
        return {"status": "skipped_not_configured"}
    # is_fully_configured() guarantees a workspace_id is present.
    assert workspace_id is not None

    # Gate 4a-bis — production-database guard, MAINNET only. Refuse fail-closed
    # BEFORE any chain read. A mainnet anchor run invoked without
    # GRANTLAYER_DATABASE_URL (e.g. run_anchor.sh called directly instead of
    # through run_with_env.py) silently falls back to the dev SQLite
    # (data/grantlayer.db), which then fails downstream with a misleading
    # "workspace has no row". Name the real cause here — before the idempotency
    # read, the exercise, or any network call. Scoped to mainnet: preprod/dev
    # runs legitimately use SQLite (the whole anchor-job unit suite does), so the
    # guard only protects the one path that spends real money.
    import os

    from ..core.db import get_engine
    database_url = os.environ.get("GRANTLAYER_DATABASE_URL") or os.environ.get("DATABASE_URL")
    engine_name = get_engine().dialect.name
    if config.network == "mainnet" and (not database_url or engine_name == "sqlite"):
        logger.error(
            "anchor_audit_chain: refusing to anchor: no production DATABASE_URL / "
            "engine is SQLite on a mainnet run (database_url_set=%s, engine=%s, network=%s)",
            bool(database_url), engine_name, config.network,
        )
        return {
            "status": "refused_no_production_database",
            "error": "no production DATABASE_URL / SQLite engine on a mainnet run",
        }

    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    maker = get_session_maker()

    # DB-side gates run FIRST — a refused/duplicate run never touches the chain
    # backend at all (no context, no probe, no balance read, no tx build).

    # Idempotency guard — one anchor per (workspace, UTC day). Abort before submit.
    with maker() as session:
        existing = (
            session.query(AnchorRecord)
            .filter(
                AnchorRecord.workspace_id == workspace_id,
                AnchorRecord.status.in_(("submitted", "confirmed")),
                AnchorRecord.anchored_at.like(f"{day}%"),
            )
            .first()
        )
        if existing is not None:
            logger.info("anchor_audit_chain: already anchored today for %s — skipping", workspace_id)
            return {"status": "skipped_already_anchored_today"}

    # The anchor run is itself a granted authority: exercise the
    # anchor-writer grant through the standard decision path BEFORE the head
    # is read, so the exercise event sits inside the anchored range.
    # Fail-closed both ways: a denied exercise or an unavailable decision
    # path refuses the run before any chain machinery — no context, no
    # probe, no submitted row, no network call.
    try:
        decision = _exercise_anchor_grant(config, workspace_id, maker)
    except Exception as exc:
        logger.error(
            "anchor_audit_chain: grant exercise unavailable [%s] — refusing: %s",
            type(exc).__name__,
            exc,
        )
        return {"status": "refused_grant_exercise_unavailable", "error": type(exc).__name__}

    if decision.get("result") == "failed":
        # Internal decision-path failure (no witnessed decision) — treat as
        # unavailable, not as a denial.
        logger.error("anchor_audit_chain: grant exercise failed internally — refusing")
        return {"status": "refused_grant_exercise_unavailable", "error": "internal_handler_error"}
    if not decision.get("approved"):
        logger.error(
            "anchor_audit_chain: grant exercise denied (%s) — refusing",
            decision.get("reasonCode"),
        )
        return {
            "status": "refused_grant_exercise_denied",
            "reason_code": decision.get("reasonCode"),
        }

    # Fail-closed head read: no head ⇒ no anchor (same posture as the
    # balance guard — never proceed blind). Read AFTER the exercise commits
    # so the anchored range covers the exercise event.
    with maker() as session:
        try:
            head = anchor_head(session, workspace_id)
        except Exception as exc:
            logger.error(
                "anchor_audit_chain: audit head unavailable — aborting: %s", exc
            )
            return {"status": "aborted_head_unavailable", "error": str(exc)}

    # Empty/short-chain choke point — refuse BEFORE any transaction machinery.
    try:
        writer.assert_chain_anchorable(head, config)
    except writer.AnchorChainTooShort as exc:
        logger.error("anchor_audit_chain: %s — refusing", exc)
        return {"status": "refused_chain_below_minimum", "error": str(exc)}

    chain = writer.build_chain_context(config)

    # Gate 4b — fail-closed reachability: abort BEFORE writing any 'submitted' row.
    try:
        writer.probe_reachable(chain)
    except Exception as exc:
        logger.warning("anchor_audit_chain: chain unreachable — aborting: %s", exc)
        return {"status": "aborted_unreachable", "error": str(exc)}

    # Gate 4c — wallet-balance ceiling (fail-closed, pre-build). Active only when a
    # cap is configured (REQUIRED on mainnet, optional on preprod). No balance
    # confirmation ⇒ NO submit: a failed/timed-out balance query aborts here.
    if config.max_wallet_lovelace is not None:
        try:
            balance = writer.read_wallet_lovelace(chain, config)
        except Exception as exc:
            logger.warning(
                "anchor_audit_chain: wallet balance unavailable — aborting: %s", exc
            )
            return {"status": "aborted_balance_unavailable", "error": str(exc)}
        if balance > config.max_wallet_lovelace:
            logger.error(
                "anchor_audit_chain: wallet balance %d lovelace exceeds cap %d "
                "— aborting (over-funded or wrong wallet)",
                balance,
                config.max_wallet_lovelace,
            )
            return {"status": "aborted_overfunded_or_wrong_wallet"}

    payload = writer.head_to_payload(head, now)
    record_id = uuid.uuid4().hex

    # Write the 'submitted' row BEFORE submit so a crash mid-submit is recoverable.
    with maker() as session:
        session.add(
            AnchorRecord(
                id=record_id,
                workspace_id=workspace_id,
                final_hash=payload.h,
                entry_count=payload.s,
                anchored_at=now.isoformat(),
                tx_id=None,
                network=config.network,
                anchor_label=config.anchor_label,
                status="submitted",
            )
        )
        session.commit()

    try:
        tx_id = writer.submit_anchor(chain, config, payload)
    except Exception as exc:
        # Log the exception TYPE first; the build/sign span already sanitizes its
        # failures into a key-free AnchorSubmitError, so nothing raw from that path
        # is stringified here.
        logger.error(
            "anchor_audit_chain: submit failed [%s] — marking failed: %s",
            type(exc).__name__,
            exc,
        )
        with maker() as session:
            row = session.get(AnchorRecord, record_id)
            if row is not None:
                row.status = "failed"
                session.commit()
        return {"status": "submit_failed", "error": type(exc).__name__}

    # Confirm only after the chain acknowledges the submission.
    with maker() as session:
        row = session.get(AnchorRecord, record_id)
        if row is not None:
            row.status = "confirmed"
            row.tx_id = tx_id
            session.commit()
    logger.info("anchor_audit_chain: confirmed %s tx=%s", workspace_id, tx_id)
    return {"status": "confirmed", "tx_id": tx_id, "record_id": record_id}


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
