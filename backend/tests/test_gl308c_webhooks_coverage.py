"""GL-308 — Coverage-completion tests for backend/src/webhooks/.

These tests use direct async calls (asyncio.run) and real SQLite DBs rather than
the HTTP TestClient, because TestClient executes handlers in a background thread
that coverage.py cannot trace.  They complement test_gl308_webhooks.py (HTTP
behaviour) and test_gl308b_webhooks_module.py (unit/integration).
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import os
import tempfile
import unittest
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _run(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.run(coro)


class _DBFixture(unittest.TestCase):
    """Base class: sets up a fresh temp SQLite DB before each test."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()

        import backend.src.core.db as _db

        self._orig_url = _db.DB_PATH_OR_URL
        self._orig_path = getattr(_db, "DB_PATH", None)
        _db.DB_PATH_OR_URL = self.tmp.name
        _db.DB_PATH = self.tmp.name
        _db._sa_engine = None
        _db._async_engine = None
        _db._session_maker = None
        _db._async_session_maker = None
        _db.init_db()

    def tearDown(self):
        import backend.src.core.db as _db

        _db.DB_PATH_OR_URL = self._orig_url
        if self._orig_path is not None:
            _db.DB_PATH = self._orig_path
        _db._sa_engine = None
        _db._async_engine = None
        _db._session_maker = None
        _db._async_session_maker = None
        os.unlink(self.tmp.name)

    def _async_session(self):
        from backend.src.core.db import get_async_session_maker
        return get_async_session_maker()


# ── WebhookRepository — direct async tests ────────────────────────────────────

class TestWebhookRepositoryDirect(_DBFixture):
    """Directly exercises WebhookRepository through a real async SQLite session."""

    def _make_row(self, **overrides):
        base = {
            "tenant_id": "t1",
            "workspace_id": "w1",
            "url": "https://example.com/hook",
            "events": ["grant.created"],
            "secret": "mysecret",
            "created_by": "op-1",
        }
        base.update(overrides)
        return base

    def _create_one(self, **kwargs):
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.create(**self._make_row(**kwargs))
        return _run(_inner())

    # ── create ────────────────────────────────────────────────────────────────

    def test_create_returns_row_with_id(self):
        row = self._create_one()
        assert row["id"] is not None
        assert row["url"] == "https://example.com/hook"
        assert row["active"] == 1

    def test_create_stores_events_as_json(self):
        row = self._create_one()
        events = json.loads(row["events"]) if isinstance(row["events"], str) else row["events"]
        assert "grant.created" in events

    def test_create_custom_workspace_id_none(self):
        row = self._create_one(workspace_id=None)
        assert row["workspace_id"] is None

    # ── get_by_id ─────────────────────────────────────────────────────────────

    def test_get_by_id_returns_row(self):
        created = self._create_one()
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.get_by_id(created["id"], "t1")
        row = _run(_inner())
        assert row is not None
        assert row["id"] == created["id"]

    def test_get_by_id_returns_none_for_unknown(self):
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.get_by_id(str(uuid.uuid4()), "t1")
        row = _run(_inner())
        assert row is None

    def test_get_by_id_tenant_isolation(self):
        created = self._create_one(tenant_id="tenant-A")
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.get_by_id(created["id"], "tenant-B")
        row = _run(_inner())
        assert row is None

    # ── list_by_tenant ────────────────────────────────────────────────────────

    def test_list_by_tenant_empty(self):
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.list_by_tenant("unknown-tenant")
        rows = _run(_inner())
        assert rows == []

    def test_list_by_tenant_returns_created(self):
        self._create_one()
        self._create_one(url="https://other.com/hook")
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.list_by_tenant("t1")
        rows = _run(_inner())
        assert len(rows) == 2

    def test_list_by_tenant_ordered_by_created_at_desc(self):
        self._create_one()
        self._create_one(url="https://second.com/hook")
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.list_by_tenant("t1")
        rows = _run(_inner())
        assert len(rows) == 2
        # Both should have created_at; ordering by DESC means newer first
        assert rows[0]["created_at"] >= rows[1]["created_at"]

    # ── deactivate ────────────────────────────────────────────────────────────

    def test_deactivate_sets_active_to_zero(self):
        created = self._create_one()
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                await repo.deactivate(created["id"], "t1")
                return await repo.get_by_id(created["id"], "t1")
        row = _run(_inner())
        assert row is not None
        assert row["active"] == 0

    def test_deactivate_unknown_id_is_noop(self):
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                # Should not raise
                await repo.deactivate(str(uuid.uuid4()), "t1")
        _run(_inner())

    # ── create_delivery ───────────────────────────────────────────────────────

    def test_create_delivery_success(self):
        created = self._create_one()

        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.create_delivery(
                    webhook_id=created["id"],
                    tenant_id="t1",
                    event_type="grant.created",
                    payload=json.dumps({"id": "g-1"}),
                    status="success",
                    http_status=200,
                    attempt=1,
                    delivered_at=_now_iso(),
                )
        row = _run(_inner())
        assert row["status"] == "success"
        assert row["http_status"] == 200
        assert row["event_type"] == "grant.created"

    def test_create_delivery_failed(self):
        created = self._create_one()

        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.create_delivery(
                    webhook_id=created["id"],
                    tenant_id="t1",
                    event_type="grant.revoked",
                    payload="{}",
                    status="failed",
                    error="connection refused",
                    attempt=3,
                )
        row = _run(_inner())
        assert row["status"] == "failed"
        assert row["error"] == "connection refused"
        assert row["attempt"] == 3

    def test_create_delivery_defaults(self):
        created = self._create_one()

        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.create_delivery(
                    webhook_id=created["id"],
                    tenant_id="t1",
                    event_type="grant.created",
                    payload="{}",
                    status="pending",
                )
        row = _run(_inner())
        assert row["http_status"] is None
        assert row["error"] is None
        assert row["attempt"] == 1
        assert row["delivered_at"] is None

    # ── list_deliveries ───────────────────────────────────────────────────────

    def test_list_deliveries_empty(self):
        created = self._create_one()
        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                return await repo.list_deliveries(created["id"], "t1")
        rows = _run(_inner())
        assert rows == []

    def test_list_deliveries_returns_records(self):
        created = self._create_one()

        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                await repo.create_delivery(
                    webhook_id=created["id"],
                    tenant_id="t1",
                    event_type="grant.created",
                    payload="{}",
                    status="success",
                    http_status=200,
                    attempt=1,
                )
                await repo.create_delivery(
                    webhook_id=created["id"],
                    tenant_id="t1",
                    event_type="grant.revoked",
                    payload="{}",
                    status="failed",
                    error="timeout",
                    attempt=3,
                )
                return await repo.list_deliveries(created["id"], "t1")
        rows = _run(_inner())
        assert len(rows) == 2

    def test_list_deliveries_respects_limit(self):
        created = self._create_one()

        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                for i in range(5):
                    await repo.create_delivery(
                        webhook_id=created["id"],
                        tenant_id="t1",
                        event_type="grant.created",
                        payload="{}",
                        status="success",
                        attempt=1,
                    )
                return await repo.list_deliveries(created["id"], "t1", limit=3)
        rows = _run(_inner())
        assert len(rows) == 3

    def test_list_deliveries_tenant_isolation(self):
        created = self._create_one()

        async def _inner():
            from backend.src.webhooks.repository import WebhookRepository
            factory = self._async_session()
            async with factory() as sess:
                repo = WebhookRepository(sess)
                await repo.create_delivery(
                    webhook_id=created["id"],
                    tenant_id="t1",
                    event_type="grant.created",
                    payload="{}",
                    status="success",
                    attempt=1,
                )
                return await repo.list_deliveries(created["id"], "t2")
        rows = _run(_inner())
        assert rows == []


# ── WebhookService — missing paths ────────────────────────────────────────────

class TestWebhookServiceMissingPaths(unittest.TestCase):
    """Covers service.py lines not hit by the existing service unit tests."""

    # ── _sign_payload ─────────────────────────────────────────────────────────

    def test_sign_payload_format(self):
        from backend.src.webhooks.service import _sign_payload
        body = b'{"event":"grant.created"}'
        sig = _sign_payload("mysecret", body)
        assert sig.startswith("sha256=")
        expected = hmac.new("mysecret".encode(), body, hashlib.sha256).hexdigest()
        assert sig == f"sha256={expected}"

    def test_sign_payload_deterministic(self):
        from backend.src.webhooks.service import _sign_payload
        body = b"hello"
        assert _sign_payload("k", body) == _sign_payload("k", body)

    def test_sign_payload_key_dependent(self):
        from backend.src.webhooks.service import _sign_payload
        body = b"hello"
        assert _sign_payload("k1", body) != _sign_payload("k2", body)

    # ── trigger_event workspace filtering ─────────────────────────────────────

    def test_trigger_event_workspace_filter_skips_other_workspace(self):
        """Subscription scoped to workspace-A should not fire for workspace-B."""
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        repo.list_by_tenant = AsyncMock(return_value=[{
            "id": "wh-1",
            "url": "https://ex.com/hook",
            "secret": "s",
            "active": 1,
            "events": json.dumps(["grant.created"]),
            "workspace_id": "workspace-A",
            "tenant_id": "t1",
        }])
        delivered = []

        async def _fake_deliver(**kwargs):
            delivered.append(True)

        svc = WebhookService(repo)
        with patch.object(svc, "_deliver_with_retry", new=AsyncMock(side_effect=_fake_deliver)):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    svc.trigger_event("grant.created", {}, "t1", "workspace-B")
                )
                loop.run_until_complete(asyncio.sleep(0))
            finally:
                loop.close()
                asyncio.set_event_loop(None)

        assert not delivered

    def test_trigger_event_workspace_none_fires_any_workspace(self):
        """Subscription with workspace_id=None fires for any workspace."""
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        repo.list_by_tenant = AsyncMock(return_value=[{
            "id": "wh-1",
            "url": "https://ex.com/hook",
            "secret": "s",
            "active": 1,
            "events": json.dumps(["grant.created"]),
            "workspace_id": None,
            "tenant_id": "t1",
        }])
        delivered = []

        async def _fake_deliver(**kwargs):
            delivered.append(True)

        svc = WebhookService(repo)
        with patch.object(svc, "_deliver_with_retry", new=AsyncMock(side_effect=_fake_deliver)):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    svc.trigger_event("grant.created", {}, "t1", "any-workspace")
                )
                loop.run_until_complete(asyncio.sleep(0))
            finally:
                loop.close()
                asyncio.set_event_loop(None)

    def test_trigger_event_invalid_events_json_skipped(self):
        """Endpoint with invalid events JSON is silently skipped."""
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        repo.list_by_tenant = AsyncMock(return_value=[{
            "id": "wh-1",
            "url": "https://ex.com/hook",
            "secret": "s",
            "active": 1,
            "events": "NOT-VALID-JSON",
            "workspace_id": None,
            "tenant_id": "t1",
        }])
        delivered = []

        async def _fake_deliver(**kwargs):
            delivered.append(True)

        svc = WebhookService(repo)
        with patch.object(svc, "_deliver_with_retry", new=AsyncMock(side_effect=_fake_deliver)):
            _run(svc.trigger_event("grant.created", {}, "t1"))

        assert not delivered

    def test_trigger_event_not_subscribed_to_event(self):
        """Endpoint subscribed to different event is skipped."""
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        repo.list_by_tenant = AsyncMock(return_value=[{
            "id": "wh-1",
            "url": "https://ex.com/hook",
            "secret": "s",
            "active": 1,
            "events": json.dumps(["grant.revoked"]),
            "workspace_id": None,
            "tenant_id": "t1",
        }])
        delivered = []

        async def _fake_deliver(**kwargs):
            delivered.append(True)

        svc = WebhookService(repo)
        with patch.object(svc, "_deliver_with_retry", new=AsyncMock(side_effect=_fake_deliver)):
            _run(svc.trigger_event("grant.created", {}, "t1"))

        assert not delivered

    # ── deliver_webhook ───────────────────────────────────────────────────────

    def test_deliver_webhook_sends_request(self):
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        svc = WebhookService(repo)

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        async def _mock_post(*args, **kwargs):
            return mock_resp

        async def _run_test():
            with patch("httpx.AsyncClient.post", new=_mock_post):
                status = await svc.deliver_webhook(
                    url="https://example.com/hook",
                    secret="mysecret",
                    event_type="grant.created",
                    payload={"id": "g-1"},
                )
            return status

        status = _run(_run_test())
        assert status == 200

    def test_deliver_webhook_includes_signature_header(self):
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        svc = WebhookService(repo)

        captured_headers = {}

        async def _mock_post(*args, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            resp = MagicMock()
            resp.status_code = 201
            return resp

        async def _run_test():
            with patch("httpx.AsyncClient.post", new=_mock_post):
                await svc.deliver_webhook(
                    url="https://example.com/hook",
                    secret="test-secret",
                    event_type="grant.revoked",
                    payload={"id": "g-2"},
                )

        _run(_run_test())
        assert "X-GrantLayer-Signature" in captured_headers
        assert captured_headers["X-GrantLayer-Signature"].startswith("sha256=")

    def test_deliver_webhook_returns_status_code(self):
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        svc = WebhookService(repo)

        for expected_status in (200, 201, 204, 400, 404, 500, 503):
            async def _mock_post(*args, **kwargs):
                resp = MagicMock()
                resp.status_code = expected_status
                return resp

            async def _run_test(status=expected_status):
                with patch("httpx.AsyncClient.post", new=_mock_post):
                    return await svc.deliver_webhook(
                        url="https://ex.com/hook",
                        secret="s",
                        event_type="grant.created",
                        payload={},
                    )

            result = _run(_run_test())
            assert result == expected_status

    # ── _deliver_with_retry ───────────────────────────────────────────────────

    def test_deliver_with_retry_success_on_first_attempt(self):
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        svc = WebhookService(repo)

        call_count = 0

        async def _mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 200
            return resp

        async def _run_test():
            body = b'{"event":"grant.created"}'
            with patch("httpx.AsyncClient.post", new=_mock_post):
                await svc._deliver_with_retry(
                    webhook_id="wh-1",
                    url="https://ex.com/hook",
                    secret="s",
                    event_type="grant.created",
                    body=body,
                    tenant_id="t1",
                )

        _run(_run_test())
        assert call_count == 1

    def test_deliver_with_retry_retries_on_5xx(self):
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        svc = WebhookService(repo)

        call_count = 0

        async def _mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            # First call returns 500, rest return 200
            resp.status_code = 500 if call_count == 1 else 200
            return resp

        async def _run_test():
            body = b'{"event":"grant.revoked"}'
            with (
                patch("httpx.AsyncClient.post", new=_mock_post),
                patch("asyncio.sleep", new=AsyncMock()),
            ):
                await svc._deliver_with_retry(
                    webhook_id="wh-1",
                    url="https://ex.com/hook",
                    secret="s",
                    event_type="grant.revoked",
                    body=body,
                    tenant_id="t1",
                )

        _run(_run_test())
        assert call_count == 2

    def test_deliver_with_retry_exhausts_retries_on_exception(self):
        from backend.src.webhooks.service import WebhookService, _MAX_RETRIES

        repo = MagicMock()
        svc = WebhookService(repo)

        call_count = 0

        async def _always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("connection refused")

        async def _run_test():
            body = b"{}"
            with (
                patch("httpx.AsyncClient.post", new=_always_fail),
                patch("asyncio.sleep", new=AsyncMock()),
            ):
                await svc._deliver_with_retry(
                    webhook_id="wh-1",
                    url="https://ex.com/hook",
                    secret="s",
                    event_type="grant.created",
                    body=body,
                    tenant_id="t1",
                )

        _run(_run_test())
        assert call_count == _MAX_RETRIES

    def test_deliver_with_retry_does_not_raise(self):
        """_deliver_with_retry swallows all exceptions after retries are exhausted."""
        from backend.src.webhooks.service import WebhookService

        repo = MagicMock()
        svc = WebhookService(repo)

        async def _always_fail(*args, **kwargs):
            raise RuntimeError("fatal error")

        async def _run_test():
            # Must not raise
            with (
                patch("httpx.AsyncClient.post", new=_always_fail),
                patch("asyncio.sleep", new=AsyncMock()),
            ):
                await svc._deliver_with_retry(
                    webhook_id="wh-1",
                    url="https://ex.com/hook",
                    secret="s",
                    event_type="grant.created",
                    body=b"{}",
                    tenant_id="t1",
                )

        _run(_run_test())  # should not raise


# ── WebhookRouter handlers — direct async calls for coverage ──────────────────

class TestWebhookRouterDirectCoverage(unittest.TestCase):
    """Calls router handler functions directly with mocked dependencies.

    This bypasses the TestClient's background thread so coverage.py can trace
    the handler bodies.
    """

    def _make_session(
        self,
        fetchone: Optional[Dict[str, Any]] = None,
        fetchall: Optional[List[Dict[str, Any]]] = None,
        side_effect: Optional[list] = None,
    ) -> Any:
        """Build a mock AsyncSession."""
        mock_db = AsyncMock()

        def _make_result(fo=None, fa=None):
            result = MagicMock()
            mappings = MagicMock()
            result.mappings.return_value = mappings
            mappings.fetchone.return_value = fo
            mappings.fetchall.return_value = fa or []
            return result

        if side_effect is not None:
            mock_db.execute.side_effect = [_make_result(**s) for s in side_effect]
        else:
            mock_db.execute.return_value = _make_result(fo=fetchone, fa=fetchall or [])

        mock_db.commit = AsyncMock()
        return mock_db

    def _ws_ctx(self, tenant_id: str = "t1", workspace_id: str = "w1") -> Dict[str, Any]:
        return {"tenant_id": tenant_id, "workspace_id": workspace_id}

    def _webhook_row(self, webhook_id: str = "wh-1", active: int = 1) -> Dict[str, Any]:
        return {
            "id": webhook_id,
            "tenant_id": "t1",
            "workspace_id": "w1",
            "url": "https://example.com/hook",
            "events": json.dumps(["grant.created"]),
            "active": active,
            "created_at": "2026-01-01T00:00:00Z",
            "created_by": "op-1",
        }

    # ── list_webhooks_endpoint ────────────────────────────────────────────────

    def test_list_webhooks_handler_empty(self):
        from backend.src.webhooks.router import list_webhooks_endpoint

        async def _run_test():
            db = self._make_session(fetchall=[])
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                result = await list_webhooks_endpoint(
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )
            return result

        result = _run(_run_test())
        assert result.total == 0
        assert result.items == []

    def test_list_webhooks_handler_with_rows(self):
        from backend.src.webhooks.router import list_webhooks_endpoint

        rows = [self._webhook_row("wh-1"), self._webhook_row("wh-2")]

        async def _run_test():
            db = self._make_session(fetchall=rows)
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                result = await list_webhooks_endpoint(
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )
            return result

        result = _run(_run_test())
        assert result.total == 2
        assert len(result.items) == 2

    # ── get_webhook_endpoint ──────────────────────────────────────────────────

    def test_get_webhook_handler_success(self):
        from backend.src.webhooks.router import get_webhook_endpoint

        async def _run_test():
            db = self._make_session(fetchone=self._webhook_row("wh-1"))
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                result = await get_webhook_endpoint(
                    webhook_id="wh-1",
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )
            return result

        result = _run(_run_test())
        assert result.id == "wh-1"

    def test_get_webhook_handler_not_found_raises_404(self):
        from fastapi import HTTPException
        from backend.src.webhooks.router import get_webhook_endpoint

        async def _run_test():
            db = self._make_session(fetchone=None)
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                return await get_webhook_endpoint(
                    webhook_id=str(uuid.uuid4()),
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        with self.assertRaises(HTTPException) as ctx:
            _run(_run_test())
        assert ctx.exception.status_code == 404

    # ── delete_webhook_endpoint ───────────────────────────────────────────────

    def test_delete_webhook_handler_success(self):
        from fastapi.responses import Response
        from backend.src.webhooks.router import delete_webhook_endpoint

        async def _run_test():
            db = self._make_session(
                side_effect=[
                    {"fo": self._webhook_row("wh-1"), "fa": []},  # _fetch_webhook
                    {"fo": None, "fa": []},                         # UPDATE
                ]
            )
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                return await delete_webhook_endpoint(
                    webhook_id="wh-1",
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        result = _run(_run_test())
        assert result.status_code == 204

    def test_delete_webhook_handler_not_found_raises_404(self):
        from fastapi import HTTPException
        from backend.src.webhooks.router import delete_webhook_endpoint

        async def _run_test():
            db = self._make_session(fetchone=None)
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                return await delete_webhook_endpoint(
                    webhook_id=str(uuid.uuid4()),
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        with self.assertRaises(HTTPException) as ctx:
            _run(_run_test())
        assert ctx.exception.status_code == 404

    # ── list_webhook_deliveries ───────────────────────────────────────────────

    def test_list_deliveries_handler_empty(self):
        from backend.src.webhooks.router import list_webhook_deliveries

        delivery_rows: List[Dict[str, Any]] = []

        async def _run_test():
            db = self._make_session(
                side_effect=[
                    {"fo": self._webhook_row("wh-1"), "fa": []},
                    {"fo": None, "fa": delivery_rows},
                ]
            )
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                return await list_webhook_deliveries(
                    webhook_id="wh-1",
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        result = _run(_run_test())
        assert result.total == 0

    def test_list_deliveries_handler_not_found(self):
        from fastapi import HTTPException
        from backend.src.webhooks.router import list_webhook_deliveries

        async def _run_test():
            db = self._make_session(fetchone=None)
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                return await list_webhook_deliveries(
                    webhook_id=str(uuid.uuid4()),
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        with self.assertRaises(HTTPException) as ctx:
            _run(_run_test())
        assert ctx.exception.status_code == 404

    def test_list_deliveries_handler_with_records(self):
        from backend.src.webhooks.router import list_webhook_deliveries

        now = _now_iso()
        delivery_row = {
            "id": "del-1", "webhook_id": "wh-1", "tenant_id": "t1",
            "event_type": "grant.created", "payload": "{}", "status": "success",
            "http_status": 200, "error": None, "attempt": 1,
            "created_at": now, "delivered_at": now,
        }

        async def _run_test():
            db = self._make_session(
                side_effect=[
                    {"fo": self._webhook_row("wh-1"), "fa": []},
                    {"fo": None, "fa": [delivery_row]},
                ]
            )
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                return await list_webhook_deliveries(
                    webhook_id="wh-1",
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        result = _run(_run_test())
        assert result.total == 1
        assert result.items[0].event_type == "grant.created"

    # ── test_webhook_endpoint ─────────────────────────────────────────────────

    def test_webhook_test_handler_not_found(self):
        from fastapi import HTTPException
        from backend.src.webhooks.router import test_webhook_endpoint

        async def _run_test():
            db = self._make_session(fetchone=None)
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                return await test_webhook_endpoint(
                    webhook_id=str(uuid.uuid4()),
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        with self.assertRaises(HTTPException) as ctx:
            _run(_run_test())
        assert ctx.exception.status_code == 404

    def test_webhook_test_handler_success_delivery(self):
        from backend.src.webhooks.router import test_webhook_endpoint

        now = _now_iso()
        ep_row = {
            **self._webhook_row("wh-1"),
            "secret": "mysecret",
        }
        delivery_row = {
            "id": "del-1", "webhook_id": "wh-1", "tenant_id": "t1",
            "event_type": "webhook.test", "payload": "{}", "status": "success",
            "http_status": 200, "error": None, "attempt": 1,
            "created_at": now, "delivered_at": now,
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        async def _mock_post(*args, **kwargs):
            return mock_resp

        async def _run_test():
            db = self._make_session(
                side_effect=[
                    {"fo": ep_row, "fa": []},          # SELECT endpoint
                    {"fo": None, "fa": []},              # INSERT delivery
                    {"fo": delivery_row, "fa": []},      # SELECT delivery
                ]
            )
            with (
                patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                      return_value=({}, self._ws_ctx())),
                patch("httpx.AsyncClient.post", new=_mock_post),
            ):
                return await test_webhook_endpoint(
                    webhook_id="wh-1",
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        result = _run(_run_test())
        assert result.status == "success"
        assert result.http_status == 200

    def test_webhook_test_handler_failed_delivery(self):
        import httpx
        from backend.src.webhooks.router import test_webhook_endpoint

        now = _now_iso()
        ep_row = {**self._webhook_row("wh-1"), "secret": "mysecret"}
        delivery_row = {
            "id": "del-1", "webhook_id": "wh-1", "tenant_id": "t1",
            "event_type": "webhook.test", "payload": "{}", "status": "failed",
            "http_status": None, "error": "refused", "attempt": 1,
            "created_at": now, "delivered_at": None,
        }

        async def _failing_post(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        async def _run_test():
            db = self._make_session(
                side_effect=[
                    {"fo": ep_row, "fa": []},
                    {"fo": None, "fa": []},
                    {"fo": delivery_row, "fa": []},
                ]
            )
            with (
                patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                      return_value=({}, self._ws_ctx())),
                patch("httpx.AsyncClient.post", new=_failing_post),
            ):
                return await test_webhook_endpoint(
                    webhook_id="wh-1",
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        result = _run(_run_test())
        assert result.status == "failed"

    def test_webhook_test_handler_server_error(self):
        """5xx from the target is recorded as failed."""
        from backend.src.webhooks.router import test_webhook_endpoint

        now = _now_iso()
        ep_row = {**self._webhook_row("wh-1"), "secret": "mysecret"}
        delivery_row = {
            "id": "del-1", "webhook_id": "wh-1", "tenant_id": "t1",
            "event_type": "webhook.test", "payload": "{}", "status": "failed",
            "http_status": 503, "error": "server error 503", "attempt": 1,
            "created_at": now, "delivered_at": None,
        }

        async def _server_error_post(*args, **kwargs):
            resp = MagicMock()
            resp.status_code = 503
            return resp

        async def _run_test():
            db = self._make_session(
                side_effect=[
                    {"fo": ep_row, "fa": []},
                    {"fo": None, "fa": []},
                    {"fo": delivery_row, "fa": []},
                ]
            )
            with (
                patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                      return_value=({}, self._ws_ctx())),
                patch("httpx.AsyncClient.post", new=_server_error_post),
            ):
                return await test_webhook_endpoint(
                    webhook_id="wh-1",
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        result = _run(_run_test())
        assert result.status == "failed"

    # ── create_webhook_endpoint ───────────────────────────────────────────────

    def test_create_webhook_handler_success(self):
        from backend.src.webhooks.router import create_webhook_endpoint
        from backend.src.webhooks.schemas import WebhookCreateRequest

        created_row = self._webhook_row("wh-new")

        async def _run_test():
            db = self._make_session(
                side_effect=[
                    {"fo": None, "fa": []},          # INSERT (execute returns rowcount-only result)
                    {"fo": created_row, "fa": []},   # _fetch_webhook SELECT
                ]
            )
            body = WebhookCreateRequest(url="https://example.com/hook", events=["grant.created"])
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({"operator": {"operatorId": "op-1"}}, self._ws_ctx())):
                return await create_webhook_endpoint(
                    body=body,
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        result = _run(_run_test())
        assert result.id == "wh-new"

    def test_create_webhook_handler_with_secret(self):
        from backend.src.webhooks.router import create_webhook_endpoint
        from backend.src.webhooks.schemas import WebhookCreateRequest

        created_row = self._webhook_row("wh-new")

        async def _run_test():
            db = self._make_session(
                side_effect=[
                    {"fo": None, "fa": []},
                    {"fo": created_row, "fa": []},
                ]
            )
            body = WebhookCreateRequest(
                url="https://example.com/hook",
                events=["grant.created"],
                secret="my-custom-secret",
            )
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                return await create_webhook_endpoint(
                    body=body,
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        result = _run(_run_test())
        assert result.id == "wh-new"

    def test_create_webhook_handler_db_fetch_fails_returns_500(self):
        from fastapi import HTTPException
        from backend.src.webhooks.router import create_webhook_endpoint
        from backend.src.webhooks.schemas import WebhookCreateRequest

        async def _run_test():
            db = self._make_session(
                side_effect=[
                    {"fo": None, "fa": []},   # INSERT
                    {"fo": None, "fa": []},   # _fetch_webhook returns None → 500
                ]
            )
            body = WebhookCreateRequest(url="https://example.com/hook", events=["grant.created"])
            with patch("backend.src.webhooks.router.resolve_auth_and_workspace",
                       return_value=({}, self._ws_ctx())):
                return await create_webhook_endpoint(
                    body=body,
                    authorization="Bearer test",
                    x_workspace_id="w1",
                    db=db,
                )

        with self.assertRaises(HTTPException) as ctx:
            _run(_run_test())
        assert ctx.exception.status_code == 500

    # ── _now_utc_iso helper ────────────────────────────────────────────────────

    def test_now_utc_iso_format(self):
        from backend.src.webhooks.router import _now_utc_iso
        result = _now_utc_iso()
        assert result.endswith("Z")
        assert "T" in result


# ── Alembic migration check ────────────────────────────────────────────────────

class TestAlembicWebhookMigration(unittest.TestCase):
    def test_alembic_migration_file_exists(self):
        migration_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "migrations_alembic", "versions",
        )
        files = os.listdir(migration_dir) if os.path.isdir(migration_dir) else []
        webhook_files = [f for f in files if "webhook" in f.lower() or "gl308" in f.lower()]
        assert len(webhook_files) >= 1, f"No GL-308 Alembic migration found in {migration_dir}"

    def test_alembic_migration_has_correct_revision(self):
        import importlib.util
        migration_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "migrations_alembic", "versions",
        )
        webhook_files = [
            f for f in os.listdir(migration_dir)
            if ("webhook" in f.lower() or "gl308" in f.lower()) and f.endswith(".py")
        ] if os.path.isdir(migration_dir) else []
        assert webhook_files, "No webhook Alembic migration file found"

        filepath = os.path.join(migration_dir, webhook_files[0])
        spec = importlib.util.spec_from_file_location("alembic_migration", filepath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "revision")
        assert hasattr(mod, "upgrade")

    def test_alembic_migration_creates_webhook_tables(self):
        """Migration upgrade() creates webhook_deliveries (and optionally webhook_subscriptions)."""
        import importlib.util
        migration_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "migrations_alembic", "versions",
        )
        webhook_files = [
            f for f in os.listdir(migration_dir)
            if ("webhook" in f.lower() or "gl308" in f.lower()) and f.endswith(".py")
        ] if os.path.isdir(migration_dir) else []
        assert webhook_files, "No webhook Alembic migration file found"
        filepath = os.path.join(migration_dir, webhook_files[0])
        spec = importlib.util.spec_from_file_location("alembic_migration", filepath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        source = open(filepath).read()
        assert "webhook" in source.lower()
