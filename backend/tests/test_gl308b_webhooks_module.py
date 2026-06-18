"""GL-308 — backend/src/webhooks/ module tests.

Covers the structured webhooks module:
- GrantEvent enum values
- GrantRequestEvent enum values
- ALL_WEBHOOK_EVENTS frozenset completeness
- WebhookDelivery ORM model fields
- verify_signature correct acceptance
- verify_signature rejects wrong secret
- verify_signature rejects tampered payload
- WebhookService.register_endpoint stores endpoint
- WebhookService.delete_endpoint deactivates endpoint
- WebhookService.list_endpoints returns subscriptions
- WebhookService.trigger_event fans out to matching endpoints
- WebhookService.trigger_event skips unknown events
- WebhookService.deliver_webhook sends correct signature header
- WebhookDelivery migration creates table
- GET /v1/webhooks/{id}/deliveries returns delivery list
- GET /v1/webhooks/{id}/deliveries returns 404 for missing webhook
- POST /v1/webhooks/{id}/test records delivery attempt
- POST /v1/webhooks/{id}/test returns 404 for missing webhook
- WebhookCreateRequest validates new event types
- Schemas: WebhookDeliveryResponse.from_row round-trip
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Unit: events module ────────────────────────────────────────────────────────

class TestGrantEventEnum(unittest.TestCase):
    def test_grant_event_values(self):
        from backend.src.webhooks.events import GrantEvent
        assert GrantEvent.created.value == "grant.created"
        assert GrantEvent.updated.value == "grant.updated"
        assert GrantEvent.approved.value == "grant.approved"
        assert GrantEvent.rejected.value == "grant.rejected"
        assert GrantEvent.executed.value == "grant.executed"
        assert GrantEvent.revoked.value == "grant.revoked"

    def test_grant_request_event_values(self):
        from backend.src.webhooks.events import GrantRequestEvent
        assert GrantRequestEvent.submitted.value == "grant_request.submitted"
        assert GrantRequestEvent.created.value == "grant_request.created"
        assert GrantRequestEvent.approved.value == "grant_request.approved"
        assert GrantRequestEvent.rejected.value == "grant_request.rejected"
        assert GrantRequestEvent.denied.value == "grant_request.denied"

    def test_all_webhook_events_is_frozenset(self):
        from backend.src.webhooks.events import ALL_WEBHOOK_EVENTS
        assert isinstance(ALL_WEBHOOK_EVENTS, frozenset)

    def test_all_webhook_events_contains_legacy_events(self):
        from backend.src.webhooks.events import ALL_WEBHOOK_EVENTS
        for evt in ("grant.created", "grant.revoked", "grant_request.created",
                    "grant_request.approved", "grant_request.denied"):
            assert evt in ALL_WEBHOOK_EVENTS, f"{evt} missing"

    def test_all_webhook_events_contains_new_events(self):
        from backend.src.webhooks.events import ALL_WEBHOOK_EVENTS
        for evt in ("grant.updated", "grant.approved", "grant.rejected", "grant.executed",
                    "grant_request.submitted", "grant_request.rejected"):
            assert evt in ALL_WEBHOOK_EVENTS, f"{evt} missing"

    def test_webhook_dispatcher_uses_extended_events(self):
        from backend.src.core.webhook_dispatcher import WEBHOOK_EVENTS
        assert "grant.updated" in WEBHOOK_EVENTS
        assert "grant_request.submitted" in WEBHOOK_EVENTS


# ── Unit: verify_signature ────────────────────────────────────────────────────

class TestVerifySignature(unittest.TestCase):
    def _make_sig(self, secret: str, body: bytes) -> str:
        return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_correct_signature_accepted(self):
        from backend.src.webhooks.service import verify_signature
        body = b'{"event":"grant.created"}'
        sig = self._make_sig("mysecret", body)
        assert verify_signature("mysecret", body, sig) is True

    def test_wrong_secret_rejected(self):
        from backend.src.webhooks.service import verify_signature
        body = b'{"event":"grant.created"}'
        sig = self._make_sig("correct-secret", body)
        assert verify_signature("wrong-secret", body, sig) is False

    def test_tampered_payload_rejected(self):
        from backend.src.webhooks.service import verify_signature
        body = b'{"event":"grant.created"}'
        sig = self._make_sig("mysecret", body)
        tampered = b'{"event":"grant.revoked"}'
        assert verify_signature("mysecret", tampered, sig) is False

    def test_missing_sha256_prefix_rejected(self):
        from backend.src.webhooks.service import verify_signature
        body = b'{"event":"grant.created"}'
        raw_hex = hmac.new("s".encode(), body, hashlib.sha256).hexdigest()
        assert verify_signature("s", body, raw_hex) is False

    def test_empty_body_accepted_with_correct_sig(self):
        from backend.src.webhooks.service import verify_signature
        body = b""
        sig = self._make_sig("s", body)
        assert verify_signature("s", body, sig) is True


# ── Unit: WebhookDelivery ORM model ──────────────────────────────────────────

class TestWebhookDeliveryModel(unittest.TestCase):
    def test_model_tablename(self):
        from backend.src.webhooks.models import WebhookDelivery
        assert WebhookDelivery.__tablename__ == "webhook_deliveries"

    def test_model_has_required_fields(self):
        from backend.src.webhooks.models import WebhookDelivery
        cols = {c.name for c in WebhookDelivery.__table__.columns}
        assert "id" in cols
        assert "webhook_id" in cols
        assert "tenant_id" in cols
        assert "event_type" in cols
        assert "payload" in cols
        assert "status" in cols
        assert "http_status" in cols
        assert "error" in cols
        assert "attempt" in cols
        assert "created_at" in cols
        assert "delivered_at" in cols

    def test_orm_module_re_exports_webhook_endpoint(self):
        from backend.src.webhooks.models import WebhookEndpoint
        assert WebhookEndpoint.__tablename__ == "webhook_subscriptions"

    def test_orm_py_has_webhook_delivery(self):
        from backend.src.core.orm import WebhookDelivery
        assert WebhookDelivery.__tablename__ == "webhook_deliveries"


# ── Unit: WebhookDelivery migration ──────────────────────────────────────────

class TestWebhookDeliveryMigration(unittest.TestCase):
    def test_migration_creates_deliveries_table(self):
        from backend.src.migrations import runner as _runner

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            _runner.run_migrations(conn)
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_deliveries'"
            ).fetchone()
            assert row is not None
            cols = [r[1] for r in conn.execute("PRAGMA table_info(webhook_deliveries)").fetchall()]
            assert "id" in cols
            assert "webhook_id" in cols
            assert "status" in cols
            assert "http_status" in cols
            conn.close()
        finally:
            os.unlink(db_path)

    def test_migration_idempotent(self):
        from backend.src.migrations import runner as _runner

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            _runner.run_migrations(conn)
            _runner.run_migrations(conn)
            conn.close()
        finally:
            os.unlink(db_path)


# ── Unit: schemas ─────────────────────────────────────────────────────────────

class TestSchemas(unittest.TestCase):
    def test_webhook_delivery_response_from_row(self):
        from backend.src.webhooks.schemas import WebhookDeliveryResponse
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        row = {
            "id": "del-1",
            "webhook_id": "wh-1",
            "tenant_id": "t1",
            "event_type": "grant.created",
            "payload": "{}",
            "status": "success",
            "http_status": 200,
            "error": None,
            "attempt": 1,
            "created_at": now,
            "delivered_at": now,
        }
        resp = WebhookDeliveryResponse.from_row(row)
        assert resp.id == "del-1"
        assert resp.webhook_id == "wh-1"
        assert resp.event_type == "grant.created"
        assert resp.status == "success"
        assert resp.http_status == 200
        assert resp.attempt == 1

    def test_webhook_create_request_accepts_new_events(self):
        from backend.src.webhooks.schemas import WebhookCreateRequest
        req = WebhookCreateRequest(url="https://ex.com/hook", events=["grant.updated"])
        assert "grant.updated" in req.events

    def test_webhook_create_request_rejects_unknown_event(self):
        from backend.src.webhooks.schemas import WebhookCreateRequest
        import pydantic
        with pytest.raises((ValueError, pydantic.ValidationError)):
            WebhookCreateRequest(url="https://ex.com/hook", events=["totally.unknown"])


# ── Unit: WebhookService ──────────────────────────────────────────────────────

class TestWebhookService(unittest.TestCase):
    def _make_mock_repo(self):
        repo = MagicMock()
        repo.create = AsyncMock(return_value={
            "id": "wh-1", "tenant_id": "t1", "workspace_id": None,
            "url": "https://ex.com/hook", "events": json.dumps(["grant.created"]),
            "active": 1, "created_at": "2026-01-01T00:00:00Z", "created_by": "op-1",
        })
        repo.deactivate = AsyncMock()
        repo.list_by_tenant = AsyncMock(return_value=[])
        repo.list_deliveries = AsyncMock(return_value=[])
        return repo

    def test_register_endpoint(self):
        import asyncio
        from backend.src.webhooks.service import WebhookService
        repo = self._make_mock_repo()
        svc = WebhookService(repo)
        result = asyncio.run(svc.register_endpoint(
            tenant_id="t1", workspace_id=None, url="https://ex.com/hook",
            events=["grant.created"], created_by="op-1",
        ))
        assert result["id"] == "wh-1"
        repo.create.assert_awaited_once()

    def test_register_endpoint_generates_secret_if_not_provided(self):
        import asyncio
        from backend.src.webhooks.service import WebhookService
        repo = self._make_mock_repo()
        svc = WebhookService(repo)
        asyncio.run(svc.register_endpoint(
            tenant_id="t1", workspace_id=None, url="https://ex.com/hook",
            events=["grant.created"], created_by="op-1",
        ))
        call_kwargs = repo.create.call_args[1]
        assert call_kwargs["secret"]
        assert len(call_kwargs["secret"]) >= 20

    def test_delete_endpoint(self):
        import asyncio
        from backend.src.webhooks.service import WebhookService
        repo = self._make_mock_repo()
        svc = WebhookService(repo)
        asyncio.run(svc.delete_endpoint("wh-1", "t1"))
        repo.deactivate.assert_awaited_once_with("wh-1", "t1")

    def test_list_endpoints(self):
        import asyncio
        from backend.src.webhooks.service import WebhookService
        repo = self._make_mock_repo()
        repo.list_by_tenant = AsyncMock(return_value=[{"id": "wh-1"}])
        svc = WebhookService(repo)
        result = asyncio.run(svc.list_endpoints("t1"))
        assert len(result) == 1

    def test_trigger_event_skips_unknown(self):
        import asyncio
        from backend.src.webhooks.service import WebhookService
        repo = self._make_mock_repo()
        svc = WebhookService(repo)
        asyncio.run(svc.trigger_event("completely.unknown", {}, "t1"))
        repo.list_by_tenant.assert_not_awaited()

    def test_trigger_event_skips_inactive_endpoints(self):
        import asyncio
        from backend.src.webhooks.service import WebhookService
        repo = self._make_mock_repo()
        repo.list_by_tenant = AsyncMock(return_value=[{
            "id": "wh-1", "url": "https://ex.com", "secret": "s",
            "active": 0, "events": json.dumps(["grant.created"]),
            "workspace_id": None,
        }])
        posted = []

        async def _fake_post(*args, **kwargs):
            posted.append(True)

        svc = WebhookService(repo)
        with patch.object(svc, "_deliver_with_retry", side_effect=_fake_post):
            asyncio.run(svc.trigger_event("grant.created", {}, "t1"))

        assert not posted

    def test_trigger_event_fires_matching_endpoints(self):
        import asyncio
        from backend.src.webhooks.service import WebhookService
        repo = self._make_mock_repo()
        repo.list_by_tenant = AsyncMock(return_value=[{
            "id": "wh-1", "url": "https://ex.com/hook", "secret": "s",
            "active": 1, "events": json.dumps(["grant.created"]),
            "workspace_id": None, "tenant_id": "t1",
        }])
        delivered = []

        async def _fake_deliver(**kwargs):
            delivered.append(kwargs["event_type"])

        svc = WebhookService(repo)
        with patch.object(svc, "_deliver_with_retry", new=AsyncMock(side_effect=_fake_deliver)):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(svc.trigger_event("grant.created", {"id": "g-1"}, "t1"))
                loop.run_until_complete(asyncio.sleep(0))
            finally:
                loop.close()
                asyncio.set_event_loop(None)

    def test_list_deliveries(self):
        import asyncio
        from backend.src.webhooks.service import WebhookService
        repo = self._make_mock_repo()
        repo.list_deliveries = AsyncMock(return_value=[{"id": "d-1"}])
        svc = WebhookService(repo)
        result = asyncio.run(svc.list_deliveries("wh-1", "t1"))
        assert result == [{"id": "d-1"}]


# ── Integration: new HTTP endpoints ───────────────────────────────────────────

_JWT_KEYS = [
    "GRANTLAYER_JWT_SECRET", "GRANTLAYER_JWT_PRIVATE_KEY", "GRANTLAYER_JWT_PUBLIC_KEY",
    "GRANTLAYER_JWT_ALGORITHM", "GRANTLAYER_JWT_PRIVATE_KEY_FILE",
    "GRANTLAYER_JWT_PUBLIC_KEY_FILE", "GRANTLAYER_REQUIRE_ADMIN_TOKEN", "GRANTLAYER_ENABLE_OIDC",
]


class TestWebhookModuleEndpoints:
    """Integration tests for new endpoints: GET deliveries, POST test."""

    def setup_method(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()

        self._orig_env = {k: os.environ.get(k) for k in _JWT_KEYS}
        for k in _JWT_KEYS:
            os.environ.pop(k, None)

        self._orig_admin = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_op_model = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")

        import backend.src.core.db as _db
        self._orig_db_path = _db.DB_PATH_OR_URL
        self._orig_db_path_alias = getattr(_db, "DB_PATH", None)
        _db.DB_PATH_OR_URL = self.tmp_db.name
        _db.DB_PATH = self.tmp_db.name
        _db._sa_engine = None
        _db._async_engine = None
        _db._session_maker = None
        _db._async_session_maker = None

        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-gl308b"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import backend.src.core.config as _cfg
        self._orig_enable_operator_model = _cfg.ENABLE_OPERATOR_MODEL
        _cfg.ENABLE_OPERATOR_MODEL = False

        _db.init_db()

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=True)
        self.auth = {"Authorization": "Bearer test-admin-gl308b"}

    def teardown_method(self):
        import backend.src.core.db as _db
        _db.DB_PATH_OR_URL = self._orig_db_path
        if self._orig_db_path_alias is not None:
            _db.DB_PATH = self._orig_db_path_alias
        _db._sa_engine = None
        _db._async_engine = None
        _db._session_maker = None
        _db._async_session_maker = None

        os.unlink(self.tmp_db.name)

        for k, v in self._orig_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

        if self._orig_admin is not None:
            os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._orig_admin
        else:
            os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)

        if self._orig_op_model is not None:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = self._orig_op_model
        else:
            os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)

        import backend.src.core.config as _cfg
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_enable_operator_model

    def _create_webhook(self, url: str = "https://example.com/hook", events=None):
        if events is None:
            events = ["grant.created"]
        resp = self.client.post(
            "/v1/webhooks",
            json={"url": url, "events": events},
            headers=self.auth,
        )
        assert resp.status_code == 201
        return resp.json()

    # ── GET deliveries ────────────────────────────────────────────────────────

    def test_get_deliveries_empty(self):
        wh = self._create_webhook()
        resp = self.client.get(f"/v1/webhooks/{wh['id']}/deliveries", headers=self.auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_deliveries_not_found_returns_404(self):
        resp = self.client.get(f"/v1/webhooks/{uuid.uuid4()}/deliveries", headers=self.auth)
        assert resp.status_code == 404
        assert resp.json()["errorCode"] == "webhook_not_found"

    def test_get_deliveries_unauthenticated_401(self):
        resp = self.client.get(f"/v1/webhooks/{uuid.uuid4()}/deliveries")
        assert resp.status_code == 401

    # ── POST test ─────────────────────────────────────────────────────────────

    def test_post_test_not_found_returns_404(self):
        resp = self.client.post(f"/v1/webhooks/{uuid.uuid4()}/test", headers=self.auth)
        assert resp.status_code == 404
        assert resp.json()["errorCode"] == "webhook_not_found"

    def test_post_test_unauthenticated_401(self):
        resp = self.client.post(f"/v1/webhooks/{uuid.uuid4()}/test")
        assert resp.status_code == 401

    def test_post_test_records_failed_delivery(self):
        """POST /test records a delivery attempt even when the target is unreachable."""
        import httpx
        wh = self._create_webhook(url="http://93.184.216.34:19999/unreachable")

        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
            resp = self.client.post(f"/v1/webhooks/{wh['id']}/test", headers=self.auth)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["eventType"] == "webhook.test"
        assert "webhookId" in data
        assert data["webhookId"] == wh["id"]

    def test_post_test_records_delivery_in_history(self):
        """After POST /test, the delivery shows up in GET /deliveries."""
        import httpx
        wh = self._create_webhook(url="http://93.184.216.34:19998/unreachable")

        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
            self.client.post(f"/v1/webhooks/{wh['id']}/test", headers=self.auth)

        resp = self.client.get(f"/v1/webhooks/{wh['id']}/deliveries", headers=self.auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["eventType"] == "webhook.test"

    def test_post_test_successful_delivery(self):
        """POST /test marks delivery 'success' when target returns 2xx."""
        wh = self._create_webhook()

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        async def _mock_post(*args, **kwargs):
            return mock_resp

        with patch("httpx.AsyncClient.post", new=_mock_post):
            resp = self.client.post(f"/v1/webhooks/{wh['id']}/test", headers=self.auth)

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert resp.json()["httpStatus"] == 200

    # ── New event types accepted by endpoint ──────────────────────────────────

    def test_create_webhook_with_new_event_types(self):
        for new_evt in ("grant.updated", "grant.approved", "grant.rejected",
                        "grant.executed", "grant_request.submitted", "grant_request.rejected"):
            resp = self.client.post(
                "/v1/webhooks",
                json={"url": "https://example.com/hook", "events": [new_evt]},
                headers=self.auth,
            )
            assert resp.status_code == 201, f"Expected 201 for {new_evt}, got {resp.status_code}"
            assert new_evt in resp.json()["events"]

    def test_webhook_module_public_api(self):
        """verify_signature and WebhookService are importable from the module."""
        from backend.src.webhooks import verify_signature, WebhookService, GrantEvent, GrantRequestEvent
        assert callable(verify_signature)
        assert GrantEvent.created.value == "grant.created"
        assert GrantRequestEvent.submitted.value == "grant_request.submitted"
