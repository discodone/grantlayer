"""Webhook dispatcher for GrantLayer lifecycle events.

Dispatches signed HTTP POST requests to registered webhook endpoints when
grant lifecycle events occur (grant.created, grant.revoked,
grant_request.created, grant_request.approved, grant_request.denied).

Delivery is best-effort / fire-and-forget: failures are logged but do not
affect the originating request.  Signatures follow the GitHub-style
`sha256=<hex>` format in the `X-GrantLayer-Signature` header.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

_logger = logging.getLogger("grantlayer.webhooks")

# Import canonical event set from the webhooks module; fall back to a minimal
# set if the module is not yet importable (e.g. during migration bootstrap).
try:
    from ..webhooks.events import ALL_WEBHOOK_EVENTS as _ALL
    WEBHOOK_EVENTS: frozenset = _ALL
except ImportError:  # pragma: no cover
    WEBHOOK_EVENTS = frozenset(
        {
            "grant.created",
            "grant.revoked",
            "grant_request.created",
            "grant_request.approved",
            "grant_request.denied",
        }
    )

_DELIVERY_TIMEOUT = 10  # seconds
_MAX_WEBHOOK_RETRIES = 3
_RETRY_BASE_DELAY = 1.0  # seconds; doubles on each attempt


def _sign_payload(secret: str, body: bytes) -> str:
    """Return `sha256=<hex>` HMAC-SHA256 signature."""
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


async def _post_once(url: str, secret: str, event_type: str, body: bytes) -> None:
    """POST *body* to *url* with signature headers.  Raises on network errors or 5xx responses."""
    import httpx

    delivery_id = str(uuid.uuid4())
    sig = _sign_payload(secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-GrantLayer-Event": event_type,
        "X-GrantLayer-Signature": sig,
        "X-GrantLayer-Delivery": delivery_id,
        "User-Agent": "GrantLayer-Webhooks/1.0",
    }
    async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT) as client:
        resp = await client.post(url, content=body, headers=headers)
    _logger.info(
        "webhook_delivered",
        extra={
            "url": url,
            "event": event_type,
            "delivery_id": delivery_id,
            "status": resp.status_code,
        },
    )
    if resp.status_code >= 500:
        raise RuntimeError(f"webhook server error {resp.status_code}")


async def _deliver_with_retry(url: str, secret: str, event_type: str, body: bytes) -> None:
    """Deliver with exponential backoff retry.  Swallows all exceptions after max retries."""
    delay = _RETRY_BASE_DELAY
    for attempt in range(_MAX_WEBHOOK_RETRIES):
        try:
            await _post_once(url, secret, event_type, body)
            return
        except Exception as exc:  # noqa: BLE001
            if attempt < _MAX_WEBHOOK_RETRIES - 1:
                _logger.warning(
                    "webhook_delivery_retrying",
                    extra={
                        "url": url,
                        "event": event_type,
                        "attempt": attempt + 1,
                        "delay": delay,
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                _logger.warning(
                    "webhook_delivery_failed",
                    extra={"url": url, "event": event_type, "error": str(exc)},
                )


def _load_subscriptions(
    tenant_id: str, workspace_id: Optional[str], event_type: str
) -> List[Dict[str, Any]]:
    """Fetch active webhook subscriptions that match this event from the DB."""
    from .db import DB_BACKEND, DB_PATH_OR_URL

    results: List[Dict[str, Any]] = []
    try:
        if DB_BACKEND == "postgres":
            import psycopg2

            conn = psycopg2.connect(DB_PATH_OR_URL)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, url, events, secret, workspace_id
                FROM webhook_subscriptions
                WHERE tenant_id = %s AND active = 1
                """,
                (tenant_id,),
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
        else:
            import sqlite3

            conn = sqlite3.connect(DB_PATH_OR_URL)
            cur = conn.execute(
                """
                SELECT id, url, events, secret, workspace_id
                FROM webhook_subscriptions
                WHERE tenant_id = ? AND active = 1
                """,
                (tenant_id,),
            )
            rows = cur.fetchall()
            conn.close()

        for row in rows:
            sub_id, url, events_json, secret, sub_workspace_id = row
            try:
                events = json.loads(events_json)
            except (ValueError, TypeError):
                continue
            if event_type not in events:
                continue
            # workspace_id filter: None means "all workspaces"
            if sub_workspace_id is not None and sub_workspace_id != workspace_id:
                continue
            results.append({"id": sub_id, "url": url, "secret": secret})
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "webhook_subscription_load_failed",
            extra={"event": event_type, "error": str(exc)},
        )
    return results


async def dispatch(
    event_type: str,
    payload: Dict[str, Any],
    tenant_id: str,
    workspace_id: Optional[str] = None,
) -> None:
    """Dispatch *event_type* to all matching webhook subscriptions.

    Runs each delivery as a fire-and-forget background task.
    """
    if event_type not in WEBHOOK_EVENTS:
        return

    envelope = {
        "event": event_type,
        "timestamp": _now_utc_iso(),
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "data": payload,
    }
    body = json.dumps(envelope, separators=(",", ":")).encode()

    subscriptions = _load_subscriptions(tenant_id, workspace_id, event_type)
    for sub in subscriptions:
        asyncio.ensure_future(
            _deliver_with_retry(sub["url"], sub["secret"], event_type, body)
        )


def dispatch_sync(
    event_type: str,
    payload: Dict[str, Any],
    tenant_id: str,
    workspace_id: Optional[str] = None,
) -> None:
    """Synchronous wrapper — schedules dispatch in the running event loop if one exists."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(dispatch(event_type, payload, tenant_id, workspace_id))
    except RuntimeError:
        pass  # no event loop — skip (e.g. sync unit tests)
