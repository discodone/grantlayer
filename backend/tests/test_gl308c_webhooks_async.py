"""GL-308 — Async tests for repository, service, and router handler coverage.

Uses pytest-asyncio to directly test async code paths that FastAPI TestClient
coverage doesn't always capture through the synchronous wrapper.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import tempfile
import uuid

import pytest
import pytest_asyncio


pytestmark = pytest.mark.asyncio


async def _make_async_db(db_path: str):
    """Create an async SQLAlchemy session backed by a migrated SQLite file."""
    import sqlite3
    from backend.src.migrations import runner as _runner
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    # Run sync migrations first
    conn = sqlite3.connect(db_path)
    _runner.run_migrations(conn)
    conn.close()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = async_session()
    return engine, session


# ── Repository tests ──────────────────────────────────────────────────────────

async def test_repository_create_and_get():
    from backend.src.webhooks.repository import WebhookRepository

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    try:
        engine, db = await _make_async_db(f.name)
        try:
            repo = WebhookRepository(db)
            row = await repo.create(
                tenant_id="t1",
                workspace_id="ws1",
                url="https://example.com/hook",
                events=["grant.created"],
                secret="s3cr3t",
                created_by="op-1",
            )
            assert row["url"] == "https://example.com/hook"
            assert row["tenant_id"] == "t1"
            fetched = await repo.get_by_id(row["id"], "t1")
            assert fetched is not None
            assert fetched["id"] == row["id"]
        finally:
            await db.close()
            await engine.dispose()
    finally:
        os.unlink(f.name)


async def test_repository_get_by_id_not_found():
    from backend.src.webhooks.repository import WebhookRepository

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    try:
        engine, db = await _make_async_db(f.name)
        try:
            repo = WebhookRepository(db)
            result = await repo.get_by_id("nonexistent", "t1")
            assert result is None
        finally:
            await db.close()
            await engine.dispose()
    finally:
        os.unlink(f.name)


async def test_repository_list_by_tenant():
    from backend.src.webhooks.repository import WebhookRepository

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    try:
        engine, db = await _make_async_db(f.name)
        try:
            repo = WebhookRepository(db)
            await repo.create(
                tenant_id="t1", workspace_id=None,
                url="https://a.com/hook", events=["grant.created"],
                secret="s", created_by="op",
            )
            await repo.create(
                tenant_id="t1", workspace_id=None,
                url="https://b.com/hook", events=["grant.revoked"],
                secret="s", created_by="op",
            )
            rows = await repo.list_by_tenant("t1")
            assert len(rows) == 2
            # other tenant returns nothing
            empty = await repo.list_by_tenant("t-other")
            assert len(empty) == 0
        finally:
            await db.close()
            await engine.dispose()
    finally:
        os.unlink(f.name)


async def test_repository_deactivate():
    from backend.src.webhooks.repository import WebhookRepository

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    try:
        engine, db = await _make_async_db(f.name)
        try:
            repo = WebhookRepository(db)
            row = await repo.create(
                tenant_id="t1", workspace_id=None,
                url="https://ex.com/hook", events=["grant.created"],
                secret="s", created_by="op",
            )
            await repo.deactivate(row["id"], "t1")
            fetched = await repo.get_by_id(row["id"], "t1")
            assert fetched is not None
            assert fetched["active"] == 0
        finally:
            await db.close()
            await engine.dispose()
    finally:
        os.unlink(f.name)


async def test_repository_create_delivery():
    from backend.src.webhooks.repository import WebhookRepository

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    try:
        engine, db = await _make_async_db(f.name)
        try:
            repo = WebhookRepository(db)
            # Create a webhook first
            wh = await repo.create(
                tenant_id="t1", workspace_id=None,
                url="https://ex.com/hook", events=["grant.created"],
                secret="s", created_by="op",
            )
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            delivery = await repo.create_delivery(
                webhook_id=wh["id"],
                tenant_id="t1",
                event_type="grant.created",
                payload='{"event":"grant.created"}',
                status="success",
                http_status=200,
                delivered_at=now,
            )
            assert delivery["status"] == "success"
            assert delivery["http_status"] == 200
            assert delivery["webhook_id"] == wh["id"]
        finally:
            await db.close()
            await engine.dispose()
    finally:
        os.unlink(f.name)


async def test_repository_list_deliveries():
    from backend.src.webhooks.repository import WebhookRepository

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    try:
        engine, db = await _make_async_db(f.name)
        try:
            repo = WebhookRepository(db)
            wh = await repo.create(
                tenant_id="t1", workspace_id=None,
                url="https://ex.com/hook", events=["grant.created"],
                secret="s", created_by="op",
            )
            await repo.create_delivery(
                webhook_id=wh["id"], tenant_id="t1",
                event_type="grant.created", payload="{}", status="failed",
                error="timeout",
            )
            await repo.create_delivery(
                webhook_id=wh["id"], tenant_id="t1",
                event_type="grant.created", payload="{}", status="success",
                http_status=200,
            )
            deliveries = await repo.list_deliveries(wh["id"], "t1")
            assert len(deliveries) == 2
            # wrong tenant returns nothing
            empty = await repo.list_deliveries(wh["id"], "other-tenant")
            assert len(empty) == 0
        finally:
            await db.close()
            await engine.dispose()
    finally:
        os.unlink(f.name)


async def test_repository_create_delivery_failed():
    from backend.src.webhooks.repository import WebhookRepository

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    try:
        engine, db = await _make_async_db(f.name)
        try:
            repo = WebhookRepository(db)
            wh = await repo.create(
                tenant_id="t1", workspace_id=None,
                url="https://ex.com/hook", events=["grant.created"],
                secret="s", created_by="op",
            )
            delivery = await repo.create_delivery(
                webhook_id=wh["id"],
                tenant_id="t1",
                event_type="grant.created",
                payload="{}",
                status="failed",
                http_status=503,
                error="service unavailable",
                attempt=3,
            )
            assert delivery["status"] == "failed"
            assert delivery["error"] == "service unavailable"
            assert delivery["attempt"] == 3
        finally:
            await db.close()
            await engine.dispose()
    finally:
        os.unlink(f.name)


# ── Service tests ─────────────────────────────────────────────────────────────

async def test_service_deliver_webhook_success():
    """WebhookService.deliver_webhook returns HTTP status code."""
    from backend.src.webhooks.service import WebhookService
    from backend.src.webhooks.repository import WebhookRepository
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    async def _mock_post(*args, **kwargs):
        return mock_resp

    repo = MagicMock()
    svc = WebhookService(repo)

    with patch("httpx.AsyncClient.post", new=_mock_post):
        status = await svc.deliver_webhook(
            url="https://example.com/hook",
            secret="s3cr3t",
            event_type="grant.created",
            payload={"event": "grant.created"},
        )
    assert status == 200


async def test_service_deliver_webhook_raises_on_network_error():
    """deliver_webhook propagates httpx errors to the caller."""
    import httpx
    from backend.src.webhooks.service import WebhookService
    from unittest.mock import MagicMock, patch

    repo = MagicMock()
    svc = WebhookService(repo)

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
        with pytest.raises(httpx.ConnectError):
            await svc.deliver_webhook(
                url="http://localhost:9/unreachable",
                secret="s",
                event_type="grant.created",
                payload={},
            )


async def test_service_trigger_event_workspace_filter():
    """trigger_event only fans out to endpoints matching workspace_id."""
    from backend.src.webhooks.service import WebhookService
    from unittest.mock import AsyncMock, MagicMock, patch

    repo = MagicMock()
    repo.list_by_tenant = AsyncMock(return_value=[
        {
            "id": "wh-A", "url": "https://a.com/hook", "secret": "s",
            "active": 1, "events": json.dumps(["grant.created"]),
            "workspace_id": "ws-1",  # scoped to ws-1
            "tenant_id": "t1",
        },
        {
            "id": "wh-B", "url": "https://b.com/hook", "secret": "s",
            "active": 1, "events": json.dumps(["grant.created"]),
            "workspace_id": None,  # matches all workspaces
            "tenant_id": "t1",
        },
    ])

    delivered_ids = []

    async def _fake_deliver(**kwargs):
        delivered_ids.append(kwargs["webhook_id"])

    svc = WebhookService(repo)
    with patch.object(svc, "_deliver_with_retry", new=AsyncMock(side_effect=_fake_deliver)):
        await svc.trigger_event("grant.created", {}, "t1", workspace_id="ws-2")
        # Let ensure_future tasks run
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    # wh-A is scoped to ws-1, so it should NOT be delivered for ws-2
    # wh-B has no workspace_id, so it SHOULD be delivered
    assert "wh-A" not in delivered_ids
    assert "wh-B" in delivered_ids


async def test_service_deliver_with_retry_success_first_attempt():
    """_deliver_with_retry returns without sleep on immediate success."""
    from backend.src.webhooks.service import WebhookService
    from unittest.mock import AsyncMock, MagicMock, patch

    repo = MagicMock()
    svc = WebhookService(repo)

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    async def _success(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", new=_success):
        await svc._deliver_with_retry(
            webhook_id="wh-1",
            url="https://example.com/hook",
            secret="s",
            event_type="grant.created",
            body=b'{"event":"grant.created"}',
            tenant_id="t1",
        )
    # No exception = success


async def test_service_deliver_with_retry_5xx_retries():
    """_deliver_with_retry retries on 5xx responses."""
    from backend.src.webhooks.service import WebhookService
    from unittest.mock import AsyncMock, MagicMock, patch

    repo = MagicMock()
    svc = WebhookService(repo)

    attempt_count = 0

    async def _flaky(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        m = MagicMock()
        m.status_code = 503 if attempt_count < 3 else 200
        return m

    with (
        patch("httpx.AsyncClient.post", new=_flaky),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await svc._deliver_with_retry(
            webhook_id="wh-1",
            url="https://example.com/hook",
            secret="s",
            event_type="grant.created",
            body=b"{}",
            tenant_id="t1",
        )

    assert attempt_count == 3


async def test_service_deliver_with_retry_all_fail():
    """_deliver_with_retry swallows all failures after max retries."""
    from backend.src.webhooks.service import WebhookService
    from unittest.mock import AsyncMock, MagicMock, patch
    import httpx

    repo = MagicMock()
    svc = WebhookService(repo)

    async def _always_fail(*args, **kwargs):
        raise httpx.ConnectError("refused")

    # Must not raise
    with (
        patch("httpx.AsyncClient.post", new=_always_fail),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        await svc._deliver_with_retry(
            webhook_id="wh-1",
            url="http://localhost:9/unreachable",
            secret="s",
            event_type="grant.created",
            body=b"{}",
            tenant_id="t1",
        )


# ── Router handler unit tests (direct async call) ─────────────────────────────

async def test_router_fetch_webhook_found():
    """_fetch_webhook returns a row when the webhook exists."""
    from backend.src.webhooks.router import _fetch_webhook

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    try:
        engine, db = await _make_async_db(f.name)
        try:
            # Insert a webhook row directly
            from sqlalchemy import text
            wh_id = str(uuid.uuid4())
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            await db.execute(
                text(
                    "INSERT INTO webhook_subscriptions "
                    "(id, tenant_id, workspace_id, url, events, secret, active, created_at, created_by) "
                    "VALUES (:id, :tenant_id, :workspace_id, :url, :events, :secret, 1, :created_at, :created_by)"
                ).bindparams(
                    id=wh_id, tenant_id="t1", workspace_id=None,
                    url="https://ex.com/hook", events='["grant.created"]',
                    secret="s", created_at=now, created_by="op",
                )
            )
            await db.commit()

            row = await _fetch_webhook(db, wh_id, "t1")
            assert row is not None
            assert row["id"] == wh_id

            # Non-existent returns None
            missing = await _fetch_webhook(db, "no-such-id", "t1")
            assert missing is None
        finally:
            await db.close()
            await engine.dispose()
    finally:
        os.unlink(f.name)
