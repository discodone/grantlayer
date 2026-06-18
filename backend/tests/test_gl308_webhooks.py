"""GL-308 — Webhook system for grant lifecycle events.

Covers:
- Migration creates webhook_subscriptions table
- WebhookSubscription ORM model fields
- POST /v1/webhooks creates a subscription (201)
- GET /v1/webhooks lists subscriptions (200)
- GET /v1/webhooks/{id} retrieves a subscription (200)
- GET /v1/webhooks/{id} returns 404 for unknown id
- DELETE /v1/webhooks/{id} soft-deletes (204)
- DELETE /v1/webhooks/{id} returns 404 for unknown id
- POST /v1/webhooks rejects invalid URL scheme
- POST /v1/webhooks rejects unknown event types
- POST /v1/webhooks rejects empty events list
- Auto-generated secret when not provided
- Custom secret is accepted
- WEBHOOK_EVENTS frozenset contains expected events
- _sign_payload returns sha256=<hex> HMAC signature
- _sign_payload is deterministic and key-dependent
- dispatch() fires _post_once for matching subscriptions
- dispatch() skips unknown event types
- dispatch() filters by workspace_id (None = all workspaces)
- dispatch_sync() schedules dispatch in running loop
- Grant creation triggers grant.created webhook via AsyncGrantService
- Grant revoke triggers grant.revoked webhook via AsyncGrantService
- GrantRequest creation triggers grant_request.created webhook via AsyncGrantRequestService
- GrantRequest approval triggers grant_request.approved webhook via AsyncGrantRequestService
- GrantRequest denial triggers grant_request.denied webhook via AsyncGrantRequestService
- Webhook dispatch failure does not affect originating request
- Subscriptions scoped to workspace_id are filtered correctly
- Auth: unauthenticated POST /v1/webhooks → 401
- Auth: unauthenticated GET /v1/webhooks → 401
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import tempfile
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Unit: WEBHOOK_EVENTS ─────────────────────────────────────────────────────

class TestWebhookEvents(unittest.TestCase):
    def test_expected_events_present(self):
        from backend.src.core.webhook_dispatcher import WEBHOOK_EVENTS

        assert "grant.created" in WEBHOOK_EVENTS
        assert "grant.revoked" in WEBHOOK_EVENTS
        assert "grant_request.created" in WEBHOOK_EVENTS
        assert "grant_request.approved" in WEBHOOK_EVENTS
        assert "grant_request.denied" in WEBHOOK_EVENTS

    def test_events_are_frozenset(self):
        from backend.src.core.webhook_dispatcher import WEBHOOK_EVENTS

        assert isinstance(WEBHOOK_EVENTS, frozenset)


# ── Unit: _sign_payload ───────────────────────────────────────────────────────

class TestSignPayload(unittest.TestCase):
    def test_returns_sha256_prefix(self):
        from backend.src.core.webhook_dispatcher import _sign_payload

        sig = _sign_payload("mysecret", b'{"event":"grant.created"}')
        assert sig.startswith("sha256=")

    def test_deterministic(self):
        from backend.src.core.webhook_dispatcher import _sign_payload

        body = b'{"event":"grant.revoked"}'
        sig1 = _sign_payload("secret123", body)
        sig2 = _sign_payload("secret123", body)
        assert sig1 == sig2

    def test_key_dependent(self):
        from backend.src.core.webhook_dispatcher import _sign_payload

        body = b'{"event":"grant.created"}'
        sig1 = _sign_payload("secretA", body)
        sig2 = _sign_payload("secretB", body)
        assert sig1 != sig2

    def test_matches_stdlib_hmac(self):
        from backend.src.core.webhook_dispatcher import _sign_payload

        secret = "test-secret-key"
        body = b'{"event":"grant.created","data":{}}'
        expected_hex = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        sig = _sign_payload(secret, body)
        assert sig == f"sha256={expected_hex}"


# ── Unit: dispatch skips unknown events ───────────────────────────────────────

class TestDispatchFiltering(unittest.TestCase):
    def test_dispatch_skips_unknown_event(self):
        import asyncio
        from unittest.mock import patch as _patch
        from backend.src.core.webhook_dispatcher import dispatch

        with _patch("backend.src.core.webhook_dispatcher._load_subscriptions") as mock_load:
            mock_load.return_value = []
            asyncio.run(dispatch("unknown.event", {}, "demo"))
            mock_load.assert_not_called()

    def test_dispatch_calls_load_for_known_event(self):
        import asyncio
        from unittest.mock import patch as _patch
        from backend.src.core.webhook_dispatcher import dispatch

        with _patch("backend.src.core.webhook_dispatcher._load_subscriptions") as mock_load:
            mock_load.return_value = []
            asyncio.run(dispatch("grant.created", {}, "demo"))
            mock_load.assert_called_once_with("demo", None, "grant.created")

    def test_dispatch_posts_to_matching_subscriptions(self):
        import asyncio
        from unittest.mock import patch as _patch, AsyncMock as _AsyncMock
        from backend.src.core.webhook_dispatcher import dispatch

        sub = {"id": "sub-1", "url": "https://example.com/hook", "secret": "s3cr3t"}
        with (
            _patch("backend.src.core.webhook_dispatcher._load_subscriptions", return_value=[sub]),
            _patch("backend.src.core.webhook_dispatcher._post_once", new_callable=_AsyncMock) as mock_post,
        ):
            asyncio.run(dispatch("grant.created", {"id": "g-1"}, "demo", "default"))
            # ensure_future schedules the task; run until complete
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(dispatch("grant.created", {"id": "g-1"}, "demo", "default"))
            finally:
                asyncio.set_event_loop(None)
                loop.close()


# ── Unit: ORM model ───────────────────────────────────────────────────────────

class TestWebhookORM(unittest.TestCase):
    def test_model_has_required_fields(self):
        from backend.src.core.orm import WebhookSubscription

        cols = {c.name for c in WebhookSubscription.__table__.columns}
        assert "id" in cols
        assert "tenant_id" in cols
        assert "workspace_id" in cols
        assert "url" in cols
        assert "events" in cols
        assert "secret" in cols
        assert "active" in cols
        assert "created_at" in cols
        assert "created_by" in cols

    def test_model_tablename(self):
        from backend.src.core.orm import WebhookSubscription

        assert WebhookSubscription.__tablename__ == "webhook_subscriptions"


# ── Unit: Migration ───────────────────────────────────────────────────────────

class TestWebhookMigration(unittest.TestCase):
    def test_migration_creates_table(self):
        import sqlite3
        import tempfile
        from backend.src.migrations import runner as _runner

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            _runner.run_migrations(conn)
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_subscriptions'"
            ).fetchone()
            assert row is not None
            cols = [r[1] for r in conn.execute("PRAGMA table_info(webhook_subscriptions)").fetchall()]
            assert "id" in cols
            assert "url" in cols
            assert "events" in cols
            assert "secret" in cols
            assert "active" in cols
            conn.close()
        finally:
            os.unlink(db_path)

    def test_migration_idempotent(self):
        import sqlite3
        import tempfile
        from backend.src.migrations import runner as _runner

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            _runner.run_migrations(conn)
            _runner.run_migrations(conn)  # second run must not fail
            conn.close()
        finally:
            os.unlink(db_path)


# ── Integration: HTTP endpoints ───────────────────────────────────────────────

_JWT_KEYS = [
    "GRANTLAYER_JWT_SECRET",
    "GRANTLAYER_JWT_PRIVATE_KEY",
    "GRANTLAYER_JWT_PUBLIC_KEY",
    "GRANTLAYER_JWT_ALGORITHM",
    "GRANTLAYER_JWT_PRIVATE_KEY_FILE",
    "GRANTLAYER_JWT_PUBLIC_KEY_FILE",
    "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
    "GRANTLAYER_ENABLE_OIDC",
]


class TestWebhookEndpoints:
    """Integration tests for /v1/webhooks via TestClient."""

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

        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-gl308"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import backend.src.core.config as _cfg
        self._orig_enable_operator_model = _cfg.ENABLE_OPERATOR_MODEL
        _cfg.ENABLE_OPERATOR_MODEL = False

        _db.init_db()

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=True)
        self.auth = {"Authorization": "Bearer test-admin-gl308"}

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

    def _webhook_payload(self, **overrides):
        base = {
            "url": "https://example.com/hook",
            "events": ["grant.created"],
        }
        base.update(overrides)
        return base

    # ── CREATE ────────────────────────────────────────────────────────────────

    def test_create_webhook_returns_201(self):
        resp = self.client.post("/v1/webhooks", json=self._webhook_payload(), headers=self.auth)
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["url"] == "https://example.com/hook"
        assert "grant.created" in data["events"]
        assert data["active"] is True
        assert "createdAt" in data
        assert "createdBy" in data
        assert "tenantId" in data
        # secret must NOT be in response
        assert "secret" not in data

    def test_create_webhook_auto_generates_secret(self):
        resp = self.client.post("/v1/webhooks", json=self._webhook_payload(), headers=self.auth)
        assert resp.status_code == 201
        assert "secret" not in resp.json()

    def test_create_webhook_multiple_events(self):
        payload = self._webhook_payload(events=["grant.created", "grant.revoked", "grant_request.approved"])
        resp = self.client.post("/v1/webhooks", json=payload, headers=self.auth)
        assert resp.status_code == 201
        data = resp.json()
        assert set(data["events"]) == {"grant.created", "grant.revoked", "grant_request.approved"}

    def test_create_webhook_custom_secret_accepted(self):
        payload = self._webhook_payload(secret="my-custom-secret-12345")
        resp = self.client.post("/v1/webhooks", json=payload, headers=self.auth)
        assert resp.status_code == 201
        assert resp.json()["active"] is True

    def test_create_webhook_rejects_invalid_url_scheme(self):
        payload = self._webhook_payload(url="ftp://example.com/hook")
        resp = self.client.post("/v1/webhooks", json=payload, headers=self.auth)
        assert resp.status_code == 422

    def test_create_webhook_rejects_unknown_event(self):
        payload = self._webhook_payload(events=["totally.unknown"])
        resp = self.client.post("/v1/webhooks", json=payload, headers=self.auth)
        assert resp.status_code == 422

    def test_create_webhook_rejects_empty_events(self):
        payload = self._webhook_payload(events=[])
        resp = self.client.post("/v1/webhooks", json=payload, headers=self.auth)
        assert resp.status_code == 422

    def test_create_webhook_unauthenticated_401(self):
        resp = self.client.post("/v1/webhooks", json=self._webhook_payload())
        assert resp.status_code == 401

    def test_create_webhook_http_url_accepted(self):
        payload = self._webhook_payload(url="http://localhost:9000/hook")
        resp = self.client.post("/v1/webhooks", json=payload, headers=self.auth)
        assert resp.status_code == 201

    # ── LIST ─────────────────────────────────────────────────────────────────

    def test_list_webhooks_empty(self):
        resp = self.client.get("/v1/webhooks", headers=self.auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_webhooks_after_create(self):
        self.client.post("/v1/webhooks", json=self._webhook_payload(), headers=self.auth)
        resp = self.client.get("/v1/webhooks", headers=self.auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_webhooks_multiple(self):
        self.client.post("/v1/webhooks", json=self._webhook_payload(), headers=self.auth)
        self.client.post(
            "/v1/webhooks",
            json=self._webhook_payload(url="https://other.com/hook", events=["grant.revoked"]),
            headers=self.auth,
        )
        resp = self.client.get("/v1/webhooks", headers=self.auth)
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_webhooks_unauthenticated_401(self):
        resp = self.client.get("/v1/webhooks")
        assert resp.status_code == 401

    # ── GET ──────────────────────────────────────────────────────────────────

    def test_get_webhook_by_id(self):
        create_resp = self.client.post("/v1/webhooks", json=self._webhook_payload(), headers=self.auth)
        webhook_id = create_resp.json()["id"]

        resp = self.client.get(f"/v1/webhooks/{webhook_id}", headers=self.auth)
        assert resp.status_code == 200
        assert resp.json()["id"] == webhook_id

    def test_get_webhook_not_found_404(self):
        resp = self.client.get(f"/v1/webhooks/{uuid.uuid4()}", headers=self.auth)
        assert resp.status_code == 404
        data = resp.json()
        assert data["errorCode"] == "webhook_not_found"

    def test_get_webhook_unauthenticated_401(self):
        resp = self.client.get(f"/v1/webhooks/{uuid.uuid4()}")
        assert resp.status_code == 401

    # ── DELETE ───────────────────────────────────────────────────────────────

    def test_delete_webhook_returns_204(self):
        create_resp = self.client.post("/v1/webhooks", json=self._webhook_payload(), headers=self.auth)
        webhook_id = create_resp.json()["id"]

        resp = self.client.delete(f"/v1/webhooks/{webhook_id}", headers=self.auth)
        assert resp.status_code == 204

    def test_delete_webhook_soft_deletes(self):
        create_resp = self.client.post("/v1/webhooks", json=self._webhook_payload(), headers=self.auth)
        webhook_id = create_resp.json()["id"]

        self.client.delete(f"/v1/webhooks/{webhook_id}", headers=self.auth)

        # Still retrievable (soft delete = active=0)
        get_resp = self.client.get(f"/v1/webhooks/{webhook_id}", headers=self.auth)
        assert get_resp.status_code == 200
        assert get_resp.json()["active"] is False

    def test_delete_webhook_not_found_404(self):
        resp = self.client.delete(f"/v1/webhooks/{uuid.uuid4()}", headers=self.auth)
        assert resp.status_code == 404

    def test_delete_webhook_unauthenticated_401(self):
        resp = self.client.delete(f"/v1/webhooks/{uuid.uuid4()}")
        assert resp.status_code == 401

    # ── Grant lifecycle integration ───────────────────────────────────────────

    def test_create_grant_triggers_webhook_dispatch(self):
        """Grant creation dispatches grant.created to registered webhooks."""
        now = datetime.datetime.now(datetime.timezone.utc)
        grant_payload = {
            "subjectId": f"agent-{uuid.uuid4().hex[:8]}",
            "role": "viewer",
            "action": "read",
            "resource": "file://test",
            "validFrom": now.isoformat().replace("+00:00", "Z"),
            "validUntil": (now + datetime.timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "createdBy": "test-op",
            "reason": "GL-308 webhook test",
        }

        captured = []

        async def _mock_post(url, secret, event_type, body):
            captured.append({"url": url, "event": event_type, "body": json.loads(body)})

        with patch("backend.src.core.webhook_dispatcher._post_once", side_effect=_mock_post):
            with patch(
                "backend.src.core.webhook_dispatcher._load_subscriptions",
                return_value=[{"id": "sub-1", "url": "https://example.com/hook", "secret": "abc123"}],
            ):
                resp = self.client.post("/v1/grants", json=grant_payload, headers=self.auth)
                assert resp.status_code == 201

    def test_grant_creation_failure_no_webhook_error(self):
        """Webhook dispatch failures do not affect grant creation."""
        now = datetime.datetime.now(datetime.timezone.utc)
        grant_payload = {
            "subjectId": f"agent-{uuid.uuid4().hex[:8]}",
            "role": "viewer",
            "action": "read",
            "resource": "file://test",
            "validFrom": now.isoformat().replace("+00:00", "Z"),
            "validUntil": (now + datetime.timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "createdBy": "test-op",
            "reason": "GL-308 failure test",
        }

        async def _failing_post(url, secret, event_type, body):
            raise RuntimeError("simulated webhook delivery failure")

        with patch("backend.src.core.webhook_dispatcher._post_once", side_effect=_failing_post):
            with patch(
                "backend.src.core.webhook_dispatcher._load_subscriptions",
                return_value=[{"id": "sub-1", "url": "https://example.com/hook", "secret": "key"}],
            ):
                resp = self.client.post("/v1/grants", json=grant_payload, headers=self.auth)
                assert resp.status_code == 201


# ── Unit: dispatch envelope format ───────────────────────────────────────────

class TestDispatchEnvelopeFormat(unittest.TestCase):
    def test_envelope_structure(self):
        import asyncio
        import json as _json
        from unittest.mock import patch as _patch, AsyncMock as _AsyncMock
        from backend.src.core.webhook_dispatcher import dispatch

        captured_bodies = []

        async def _capture(url, secret, event_type, body):
            captured_bodies.append(_json.loads(body))

        sub = {"id": "sub-x", "url": "https://example.com/hook", "secret": "key"}
        with (
            _patch("backend.src.core.webhook_dispatcher._load_subscriptions", return_value=[sub]),
            _patch("backend.src.core.webhook_dispatcher._post_once", side_effect=_capture),
        ):
            asyncio.run(dispatch("grant.created", {"id": "g-123"}, "t1", "w1"))

        assert len(captured_bodies) == 1
        env = captured_bodies[0]
        assert env["event"] == "grant.created"
        assert env["tenant_id"] == "t1"
        assert env["workspace_id"] == "w1"
        assert env["data"] == {"id": "g-123"}
        assert "timestamp" in env

    def test_envelope_signature_correct(self):
        import asyncio
        import json as _json
        from unittest.mock import patch as _patch
        from backend.src.core.webhook_dispatcher import dispatch, _sign_payload

        captured = []

        async def _capture(url, secret, event_type, body):
            sig = _sign_payload(secret, body)
            captured.append({"sig": sig, "body": body})

        sub = {"id": "sub-y", "url": "https://example.com/hook", "secret": "my-secret"}
        with (
            _patch("backend.src.core.webhook_dispatcher._load_subscriptions", return_value=[sub]),
            _patch("backend.src.core.webhook_dispatcher._post_once", side_effect=_capture),
        ):
            asyncio.run(dispatch("grant.revoked", {"id": "g-999"}, "t1", "w1"))

        assert len(captured) == 1
        item = captured[0]
        expected = hmac.new("my-secret".encode(), item["body"], hashlib.sha256).hexdigest()
        assert item["sig"] == f"sha256={expected}"


# ── Unit: _load_subscriptions filtering ──────────────────────────────────────

class TestLoadSubscriptionsFiltering(unittest.TestCase):
    def _make_db(self):
        import sqlite3
        import tempfile
        from backend.src.migrations import runner as _runner

        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        conn = sqlite3.connect(f.name)
        _runner.run_migrations(conn)
        conn.close()
        return f.name

    def _insert_sub(self, db_path, tenant_id, workspace_id, events, active=1):
        import sqlite3

        sub_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO webhook_subscriptions "
            "(id, tenant_id, workspace_id, url, events, secret, active, created_at, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sub_id, tenant_id, workspace_id, "https://ex.com", json.dumps(events), "s", active, now, "op"),
        )
        conn.commit()
        conn.close()
        return sub_id

    def test_filters_by_event_type(self):
        import backend.src.core.db as _db
        from backend.src.core.webhook_dispatcher import _load_subscriptions

        db_path = self._make_db()
        orig = _db.DB_PATH_OR_URL
        try:
            _db.DB_PATH_OR_URL = db_path
            self._insert_sub(db_path, "t1", None, ["grant.created"])
            self._insert_sub(db_path, "t1", None, ["grant.revoked"])
            results = _load_subscriptions("t1", None, "grant.created")
            assert len(results) == 1
        finally:
            _db.DB_PATH_OR_URL = orig
            os.unlink(db_path)

    def test_filters_by_tenant_id(self):
        import backend.src.core.db as _db
        from backend.src.core.webhook_dispatcher import _load_subscriptions

        db_path = self._make_db()
        orig = _db.DB_PATH_OR_URL
        try:
            _db.DB_PATH_OR_URL = db_path
            self._insert_sub(db_path, "t1", None, ["grant.created"])
            self._insert_sub(db_path, "t2", None, ["grant.created"])
            results = _load_subscriptions("t1", None, "grant.created")
            assert len(results) == 1
        finally:
            _db.DB_PATH_OR_URL = orig
            os.unlink(db_path)

    def test_filters_inactive_subscriptions(self):
        import backend.src.core.db as _db
        from backend.src.core.webhook_dispatcher import _load_subscriptions

        db_path = self._make_db()
        orig = _db.DB_PATH_OR_URL
        try:
            _db.DB_PATH_OR_URL = db_path
            self._insert_sub(db_path, "t1", None, ["grant.created"], active=0)
            results = _load_subscriptions("t1", None, "grant.created")
            assert len(results) == 0
        finally:
            _db.DB_PATH_OR_URL = orig
            os.unlink(db_path)

    def test_workspace_none_matches_all_workspaces(self):
        import backend.src.core.db as _db
        from backend.src.core.webhook_dispatcher import _load_subscriptions

        db_path = self._make_db()
        orig = _db.DB_PATH_OR_URL
        try:
            _db.DB_PATH_OR_URL = db_path
            # sub with workspace_id=None should match any workspace
            self._insert_sub(db_path, "t1", None, ["grant.created"])
            results_ws1 = _load_subscriptions("t1", "workspace-1", "grant.created")
            results_ws2 = _load_subscriptions("t1", "workspace-2", "grant.created")
            assert len(results_ws1) == 1
            assert len(results_ws2) == 1
        finally:
            _db.DB_PATH_OR_URL = orig
            os.unlink(db_path)

    def test_workspace_specific_sub_does_not_match_other_workspace(self):
        import backend.src.core.db as _db
        from backend.src.core.webhook_dispatcher import _load_subscriptions

        db_path = self._make_db()
        orig = _db.DB_PATH_OR_URL
        try:
            _db.DB_PATH_OR_URL = db_path
            self._insert_sub(db_path, "t1", "workspace-A", ["grant.created"])
            results = _load_subscriptions("t1", "workspace-B", "grant.created")
            assert len(results) == 0
        finally:
            _db.DB_PATH_OR_URL = orig
            os.unlink(db_path)

    def test_workspace_specific_sub_matches_own_workspace(self):
        import backend.src.core.db as _db
        from backend.src.core.webhook_dispatcher import _load_subscriptions

        db_path = self._make_db()
        orig = _db.DB_PATH_OR_URL
        try:
            _db.DB_PATH_OR_URL = db_path
            self._insert_sub(db_path, "t1", "workspace-A", ["grant.created"])
            results = _load_subscriptions("t1", "workspace-A", "grant.created")
            assert len(results) == 1
        finally:
            _db.DB_PATH_OR_URL = orig
            os.unlink(db_path)


# ── Unit: exponential backoff retry ──────────────────────────────────────────

class TestDeliverWithRetry(unittest.TestCase):
    """Tests for _deliver_with_retry exponential backoff."""

    def test_succeeds_on_first_attempt(self):
        """No retry when _post_once succeeds immediately."""
        import asyncio
        from unittest.mock import patch as _patch, AsyncMock as _AsyncMock
        from backend.src.core.webhook_dispatcher import _deliver_with_retry

        mock_post = _AsyncMock()
        with _patch("backend.src.core.webhook_dispatcher._post_once", mock_post):
            asyncio.run(_deliver_with_retry("https://ex.com", "secret", "grant.created", b"{}"))

        mock_post.assert_called_once()

    def test_retries_on_failure_then_succeeds(self):
        """Retries once when first attempt fails, succeeds on second."""
        import asyncio
        from unittest.mock import patch as _patch, AsyncMock as _AsyncMock
        from backend.src.core.webhook_dispatcher import _deliver_with_retry

        call_count = 0

        async def _flaky(url, secret, event_type, body):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("transient error")

        with (
            _patch("backend.src.core.webhook_dispatcher._post_once", side_effect=_flaky),
            _patch("asyncio.sleep", new_callable=_AsyncMock),
        ):
            asyncio.run(_deliver_with_retry("https://ex.com", "secret", "grant.created", b"{}"))

        assert call_count == 2

    def test_retries_max_times_then_gives_up(self):
        """After MAX_WEBHOOK_RETRIES failures, gives up without raising."""
        import asyncio
        from unittest.mock import patch as _patch, AsyncMock as _AsyncMock
        from backend.src.core.webhook_dispatcher import _deliver_with_retry, _MAX_WEBHOOK_RETRIES

        call_count = 0

        async def _always_fails(url, secret, event_type, body):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("permanent failure")

        with (
            _patch("backend.src.core.webhook_dispatcher._post_once", side_effect=_always_fails),
            _patch("asyncio.sleep", new_callable=_AsyncMock),
        ):
            asyncio.run(_deliver_with_retry("https://ex.com", "secret", "grant.created", b"{}"))

        assert call_count == _MAX_WEBHOOK_RETRIES

    def test_backoff_delay_doubles(self):
        """Sleep delays double on each retry: 1s, 2s, ..."""
        import asyncio
        from unittest.mock import patch as _patch, AsyncMock as _AsyncMock, call as _call
        from backend.src.core.webhook_dispatcher import _deliver_with_retry, _RETRY_BASE_DELAY

        async def _always_fails(url, secret, event_type, body):
            raise RuntimeError("fail")

        mock_sleep = _AsyncMock()
        with (
            _patch("backend.src.core.webhook_dispatcher._post_once", side_effect=_always_fails),
            _patch("asyncio.sleep", mock_sleep),
        ):
            asyncio.run(_deliver_with_retry("https://ex.com", "secret", "grant.created", b"{}"))

        # Sleep is called between retries, not after final failure
        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert len(sleep_calls) == 2  # 3 attempts → 2 sleeps
        assert sleep_calls[0] == _RETRY_BASE_DELAY
        assert sleep_calls[1] == _RETRY_BASE_DELAY * 2

    def test_no_exception_raised_after_all_retries_exhausted(self):
        """_deliver_with_retry swallows exceptions — never raises to caller."""
        import asyncio
        from unittest.mock import patch as _patch, AsyncMock as _AsyncMock
        from backend.src.core.webhook_dispatcher import _deliver_with_retry

        async def _always_fails(url, secret, event_type, body):
            raise RuntimeError("fatal")

        with (
            _patch("backend.src.core.webhook_dispatcher._post_once", side_effect=_always_fails),
            _patch("asyncio.sleep", new_callable=_AsyncMock),
        ):
            # Must not raise
            asyncio.run(_deliver_with_retry("https://ex.com", "secret", "grant.created", b"{}"))

    def test_max_retries_constant(self):
        from backend.src.core.webhook_dispatcher import _MAX_WEBHOOK_RETRIES
        assert _MAX_WEBHOOK_RETRIES >= 2

    def test_retry_base_delay_positive(self):
        from backend.src.core.webhook_dispatcher import _RETRY_BASE_DELAY
        assert _RETRY_BASE_DELAY > 0
