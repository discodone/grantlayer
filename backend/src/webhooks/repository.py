"""Repository layer for webhook subscriptions and deliveries."""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


class WebhookRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        tenant_id: str,
        workspace_id: Optional[str],
        url: str,
        events: List[str],
        secret: str,
        created_by: str,
    ) -> Dict[str, Any]:
        webhook_id = str(uuid.uuid4())
        now = _now_utc_iso()
        await self._db.execute(
            text(
                "INSERT INTO webhook_subscriptions "
                "(id, tenant_id, workspace_id, url, events, secret, active, created_at, created_by) "
                "VALUES (:id, :tenant_id, :workspace_id, :url, :events, :secret, 1, :created_at, :created_by)"
            ).bindparams(
                id=webhook_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                url=url,
                events=json.dumps(sorted(events)),
                secret=secret,
                created_at=now,
                created_by=created_by,
            )
        )
        await self._db.commit()
        row = await self.get_by_id(webhook_id, tenant_id)
        if row is None:
            raise RuntimeError("Failed to retrieve created webhook")
        return row

    async def get_by_id(self, webhook_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        result = await self._db.execute(
            text(
                "SELECT id, tenant_id, workspace_id, url, events, active, created_at, created_by "
                "FROM webhook_subscriptions WHERE id = :id AND tenant_id = :tenant_id"
            ).bindparams(id=webhook_id, tenant_id=tenant_id)
        )
        row = result.mappings().fetchone()
        return dict(row) if row is not None else None

    async def list_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        result = await self._db.execute(
            text(
                "SELECT id, tenant_id, workspace_id, url, events, active, created_at, created_by "
                "FROM webhook_subscriptions WHERE tenant_id = :tenant_id "
                "ORDER BY created_at DESC"
            ).bindparams(tenant_id=tenant_id)
        )
        return [dict(r) for r in result.mappings().fetchall()]

    async def deactivate(self, webhook_id: str, tenant_id: str) -> None:
        await self._db.execute(
            text(
                "UPDATE webhook_subscriptions SET active = 0 "
                "WHERE id = :id AND tenant_id = :tenant_id"
            ).bindparams(id=webhook_id, tenant_id=tenant_id)
        )
        await self._db.commit()

    async def create_delivery(
        self,
        *,
        webhook_id: str,
        tenant_id: str,
        event_type: str,
        payload: str,
        status: str,
        http_status: Optional[int] = None,
        error: Optional[str] = None,
        attempt: int = 1,
        delivered_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        delivery_id = str(uuid.uuid4())
        now = _now_utc_iso()
        await self._db.execute(
            text(
                "INSERT INTO webhook_deliveries "
                "(id, webhook_id, tenant_id, event_type, payload, status, http_status, "
                "error, attempt, created_at, delivered_at) "
                "VALUES (:id, :webhook_id, :tenant_id, :event_type, :payload, :status, "
                ":http_status, :error, :attempt, :created_at, :delivered_at)"
            ).bindparams(
                id=delivery_id,
                webhook_id=webhook_id,
                tenant_id=tenant_id,
                event_type=event_type,
                payload=payload,
                status=status,
                http_status=http_status,
                error=error,
                attempt=attempt,
                created_at=now,
                delivered_at=delivered_at,
            )
        )
        await self._db.commit()
        result = await self._db.execute(
            text("SELECT * FROM webhook_deliveries WHERE id = :id").bindparams(id=delivery_id)
        )
        row = result.mappings().fetchone()
        return dict(row) if row is not None else {}

    async def list_deliveries(
        self, webhook_id: str, tenant_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        result = await self._db.execute(
            text(
                "SELECT id, webhook_id, tenant_id, event_type, payload, status, "
                "http_status, error, attempt, created_at, delivered_at "
                "FROM webhook_deliveries "
                "WHERE webhook_id = :webhook_id AND tenant_id = :tenant_id "
                "ORDER BY created_at DESC LIMIT :limit"
            ).bindparams(webhook_id=webhook_id, tenant_id=tenant_id, limit=limit)
        )
        return [dict(r) for r in result.mappings().fetchall()]
