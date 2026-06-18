"""WebhookService — orchestrates webhook registration, dispatch, and delivery tracking."""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from .events import ALL_WEBHOOK_EVENTS
from .repository import WebhookRepository
from .schemas import _is_ssrf_destination

_logger = logging.getLogger("grantlayer.webhooks.service")

_DELIVERY_TIMEOUT = 5  # seconds (as specified)
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0


def verify_signature(secret: str, payload: bytes, signature: str) -> bool:
    """Verify an incoming X-GrantLayer-Signature header.

    Returns True when the computed HMAC-SHA256 matches the provided signature.
    Comparison is constant-time to prevent timing attacks.
    """
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _sign_payload(secret: str, body: bytes) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


class WebhookService:
    """High-level service for webhook lifecycle management."""

    def __init__(self, repo: WebhookRepository) -> None:
        self._repo = repo

    async def register_endpoint(
        self,
        *,
        tenant_id: str,
        workspace_id: Optional[str],
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        created_by: str,
    ) -> Dict[str, Any]:
        resolved_secret = secret or secrets.token_hex(32)
        return await self._repo.create(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            url=url,
            events=events,
            secret=resolved_secret,
            created_by=created_by,
        )

    async def delete_endpoint(self, webhook_id: str, tenant_id: str) -> None:
        await self._repo.deactivate(webhook_id, tenant_id)

    async def list_endpoints(self, tenant_id: str) -> List[Dict[str, Any]]:
        return await self._repo.list_by_tenant(tenant_id)

    async def list_deliveries(
        self, webhook_id: str, tenant_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        return await self._repo.list_deliveries(webhook_id, tenant_id, limit=limit)

    async def trigger_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        tenant_id: str,
        workspace_id: Optional[str] = None,
    ) -> None:
        """Fan-out event to all matching active webhook endpoints.

        Delivers each endpoint as a background task (fire-and-forget).
        """
        if event_type not in ALL_WEBHOOK_EVENTS:
            return

        envelope = {
            "event": event_type,
            "timestamp": _now_utc_iso(),
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "data": payload,
        }
        body = json.dumps(envelope, separators=(",", ":")).encode()

        endpoints = await self._repo.list_by_tenant(tenant_id)
        for ep in endpoints:
            if not ep.get("active"):
                continue
            try:
                ep_events = (
                    json.loads(ep["events"])
                    if isinstance(ep["events"], str)
                    else ep["events"]
                )
            except (ValueError, TypeError):
                continue
            if event_type not in ep_events:
                continue
            if ep.get("workspace_id") is not None and ep.get("workspace_id") != workspace_id:
                continue

            asyncio.ensure_future(
                self._deliver_with_retry(
                    webhook_id=ep["id"],
                    url=ep["url"],
                    secret=ep.get("secret", ""),
                    event_type=event_type,
                    body=body,
                    tenant_id=tenant_id,
                )
            )

    async def deliver_webhook(
        self,
        *,
        url: str,
        secret: str,
        event_type: str,
        payload: Dict[str, Any],
        webhook_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> int:
        """Deliver a single webhook POST and return HTTP status code.

        Raises httpx.HTTPError on network failures.
        SSRF guard: re-checks destination IP at delivery time (DNS rebinding protection).
        """
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if _is_ssrf_destination(host):
            _logger.error("webhook_ssrf_blocked_at_delivery", extra={"url": url, "host": host})
            raise ValueError(f"Webhook delivery blocked: destination {host!r} is a private address")
        body = json.dumps(payload, separators=(",", ":")).encode()
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
        return resp.status_code

    async def _deliver_with_retry(
        self,
        *,
        webhook_id: str,
        url: str,
        secret: str,
        event_type: str,
        body: bytes,
        tenant_id: str,
    ) -> None:
        # Re-check SSRF at delivery time to defend against DNS rebinding.
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if _is_ssrf_destination(host):
            _logger.error(
                "webhook_ssrf_blocked_at_delivery",
                extra={"webhook_id": webhook_id, "host": host},
            )
            return
        delivery_id = str(uuid.uuid4())
        sig = _sign_payload(secret, body)
        req_headers = {
            "Content-Type": "application/json",
            "X-GrantLayer-Event": event_type,
            "X-GrantLayer-Signature": sig,
            "X-GrantLayer-Delivery": delivery_id,
            "User-Agent": "GrantLayer-Webhooks/1.0",
        }

        delay = _RETRY_BASE_DELAY
        last_error: Optional[str] = None

        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT) as client:
                    resp = await client.post(url, content=body, headers=req_headers)
                if resp.status_code < 500:
                    _logger.info(
                        "webhook_delivered",
                        extra={
                            "webhook_id": webhook_id,
                            "event": event_type,
                            "status": resp.status_code,
                        },
                    )
                    return
                last_error = f"server error {resp.status_code}"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)

            if attempt < _MAX_RETRIES - 1:
                _logger.warning(
                    "webhook_delivery_retrying",
                    extra={
                        "webhook_id": webhook_id,
                        "event": event_type,
                        "attempt": attempt + 1,
                        "delay": delay,
                        "error": last_error,
                    },
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                _logger.warning(
                    "webhook_delivery_failed",
                    extra={
                        "webhook_id": webhook_id,
                        "event": event_type,
                        "error": last_error,
                    },
                )
