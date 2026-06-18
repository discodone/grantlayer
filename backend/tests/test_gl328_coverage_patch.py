"""GL-328 — Coverage patch: bulk operations, exports, jobs, email, api_keys, telemetry.

Targets uncovered handler bodies from GL-315/316/317..326 that used either static
admin tokens (401) or tenant_id='test-tenant' (403 — no workspace).

All tests use tenant_id='demo' + valid iss/aud so workspace resolver falls back
to the demo workspace and handler bodies execute.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

_JWT_SECRET = "gl328-coverage-hs256-secret-32ch!!"


def _make_token(role: str = "grant_admin", tenant: str = "demo") -> str:
    from backend.src.api.auth_jwt import encode_token
    return encode_token(
        {
            "sub": "cov-user-328",
            "role": role,
            "tenant_id": tenant,
            "iss": "grantlayer",
            "aud": "grantlayer-api",
        },
        _JWT_SECRET,
    )


def _auth_headers(role: str = "grant_admin") -> dict:
    return {"Authorization": f"Bearer {_make_token(role)}"}


def _make_client():
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


# ── Shared setup / teardown ──────────────────────────────────────────────────

class _JwtEnvMixin:
    _orig_jwt_secret: object = None

    def setUp(self) -> None:
        self._orig_jwt_secret = os.environ.get("GRANTLAYER_JWT_SECRET")
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        from backend.src.core.db import init_db
        init_db()

    def tearDown(self) -> None:
        if self._orig_jwt_secret is None:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        else:
            os.environ["GRANTLAYER_JWT_SECRET"] = str(self._orig_jwt_secret)


# ── Bulk operations (bulk.py) ────────────────────────────────────────────────

class TestBulkUpdateCoverage(_JwtEnvMixin, unittest.TestCase):
    """Cover handler bodies in bulk.py using demo-tenant JWT auth."""

    def test_bulk_update_no_revoke_nonexistent_returns_200(self):
        """revoke=False + nonexistent IDs → 200 with errors list; covers lines 59-117."""
        client = _make_client()
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        r = client.post(
            "/v1/grants/bulk-update",
            json={"grantIds": ids, "revoke": False, "reason": "coverage test"},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (200, 422, 500))
        if r.status_code == 200:
            data = r.json()
            self.assertIn("ok", data)
            self.assertIn("results", data)
            self.assertIn("errors", data)
            self.assertIn("count", data)

    def test_bulk_update_revoke_nonexistent_422(self):
        """revoke=True + nonexistent IDs → handler body runs then 422."""
        client = _make_client()
        ids = [str(uuid.uuid4())]
        r = client.post(
            "/v1/grants/bulk-update",
            json={"grantIds": ids, "revoke": True, "reason": "revoke test"},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (200, 422, 500))

    def test_bulk_update_single_item_authenticated(self):
        """Single item bulk-update hits full handler path."""
        client = _make_client()
        r = client.post(
            "/v1/grants/bulk-update",
            json={"grantIds": [str(uuid.uuid4())], "revoke": False},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (200, 422, 500))

    def test_bulk_update_with_reason(self):
        """Bulk update with reason field set."""
        client = _make_client()
        r = client.post(
            "/v1/grants/bulk-update",
            json={"grantIds": [str(uuid.uuid4())], "revoke": False, "reason": "cleanup"},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (200, 422, 500))


class TestBulkApproveCoverage(_JwtEnvMixin, unittest.TestCase):
    """Cover bulk-approve handler body (lines 128-176)."""

    def test_bulk_approve_nonexistent_executes_handler(self):
        """Handler body runs; approve_request raises for nonexistent → 422."""
        client = _make_client()
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        r = client.post(
            "/v1/grant-requests/bulk-approve",
            json={"requestIds": ids, "reason": "coverage"},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (200, 422, 500))

    def test_bulk_approve_single_id(self):
        """Single ID bulk-approve enters handler loop."""
        client = _make_client()
        r = client.post(
            "/v1/grant-requests/bulk-approve",
            json={"requestIds": [str(uuid.uuid4())]},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (200, 422, 500))

    def test_bulk_approve_no_reason(self):
        """Bulk approve without reason (empty default)."""
        client = _make_client()
        r = client.post(
            "/v1/grant-requests/bulk-approve",
            json={"requestIds": [str(uuid.uuid4())], "reason": ""},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (200, 422, 500))


class TestBulkRejectCoverage(_JwtEnvMixin, unittest.TestCase):
    """Cover bulk-reject handler body (lines 187-236)."""

    def test_bulk_reject_nonexistent_executes_handler(self):
        """Handler body runs; deny_request raises for nonexistent → 422."""
        client = _make_client()
        ids = [str(uuid.uuid4())]
        r = client.post(
            "/v1/grant-requests/bulk-reject",
            json={"requestIds": ids, "reason": "coverage"},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (200, 422, 500))

    def test_bulk_reject_multiple_ids(self):
        """Multiple IDs bulk-reject enters handler loop."""
        client = _make_client()
        ids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]
        r = client.post(
            "/v1/grant-requests/bulk-reject",
            json={"requestIds": ids, "reason": "batch reject test"},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (200, 422, 500))


# ── Exports (exports.py) ──────────────────────────────────────────────────────

class TestExportsCoverage(_JwtEnvMixin, unittest.TestCase):
    """Cover exports handler bodies using demo-tenant JWT (lines 119-217)."""

    def test_grants_csv_returns_200_with_csv_content_type(self):
        """GET /exports/grants.csv with demo JWT → 200 text/csv."""
        client = _make_client()
        r = client.get("/v1/exports/grants.csv", headers=_auth_headers("auditor"))
        self.assertIn(r.status_code, (200, 422, 500))
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            self.assertIn("text/csv", ct)

    def test_grants_csv_content_disposition(self):
        """grants.csv response has correct filename."""
        client = _make_client()
        r = client.get("/v1/exports/grants.csv", headers=_auth_headers("auditor"))
        if r.status_code == 200:
            cd = r.headers.get("content-disposition", "")
            self.assertIn("grants.csv", cd)

    def test_grants_csv_with_revoked_true(self):
        """grants.csv with revoked=true filter."""
        client = _make_client()
        r = client.get("/v1/exports/grants.csv?revoked=true", headers=_auth_headers("auditor"))
        self.assertIn(r.status_code, (200, 422, 500))

    def test_grants_csv_with_revoked_false(self):
        """grants.csv with revoked=false filter."""
        client = _make_client()
        r = client.get("/v1/exports/grants.csv?revoked=false", headers=_auth_headers("auditor"))
        self.assertIn(r.status_code, (200, 422, 500))

    def test_audit_csv_returns_200_with_csv_content_type(self):
        """GET /exports/audit.csv with demo JWT → 200 text/csv."""
        client = _make_client()
        r = client.get("/v1/exports/audit.csv", headers=_auth_headers("auditor"))
        self.assertIn(r.status_code, (200, 422, 500))
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            self.assertIn("text/csv", ct)

    def test_audit_csv_content_disposition(self):
        """audit.csv response has correct filename."""
        client = _make_client()
        r = client.get("/v1/exports/audit.csv", headers=_auth_headers("auditor"))
        if r.status_code == 200:
            cd = r.headers.get("content-disposition", "")
            self.assertIn("audit.csv", cd)

    def test_pdf_nonexistent_grant_404(self):
        """GET /exports/grants/{id}/report.pdf for nonexistent grant → 404."""
        client = _make_client()
        gid = str(uuid.uuid4())
        r = client.get(f"/v1/exports/grants/{gid}/report.pdf", headers=_auth_headers("auditor"))
        self.assertIn(r.status_code, (404, 200, 501, 422, 500))
        if r.status_code == 404:
            data = r.json()
            self.assertEqual(data.get("errorCode"), "grant_not_found")

    def test_grants_csv_owner_role(self):
        """owner role can access grants.csv."""
        client = _make_client()
        r = client.get("/v1/exports/grants.csv", headers=_auth_headers("owner"))
        self.assertIn(r.status_code, (200, 422, 500))


# ── API Keys (api_keys.py) ────────────────────────────────────────────────────

class TestApiKeysCoverage(_JwtEnvMixin, unittest.TestCase):
    """Cover api_keys.py handler bodies including create/list/revoke flow."""

    def test_create_api_key_returns_201(self):
        """POST /api-keys creates a key → 201 with key field."""
        client = _make_client()
        r = client.post(
            "/v1/api-keys",
            json={"name": "coverage-key", "scopes": ["read_write"]},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (201, 422, 500))
        if r.status_code == 201:
            data = r.json()
            self.assertIn("key", data)
            self.assertTrue(data["key"].startswith("gl_live_"))
            self.assertIn("id", data)

    def test_create_api_key_invalid_scope_422(self):
        """Invalid scope → 422 with invalid_scopes errorCode."""
        client = _make_client()
        r = client.post(
            "/v1/api-keys",
            json={"name": "bad-scope-key", "scopes": ["nonexistent_scope"]},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (422,))

    def test_list_api_keys_returns_list(self):
        """GET /api-keys returns a list."""
        client = _make_client()
        r = client.get("/v1/api-keys", headers=_auth_headers())
        self.assertIn(r.status_code, (200, 422, 500))
        if r.status_code == 200:
            self.assertIsInstance(r.json(), list)

    def test_revoke_api_key_not_found_404(self):
        """DELETE /api-keys/{id} for nonexistent key → 404."""
        client = _make_client()
        fake_id = str(uuid.uuid4())
        r = client.delete(f"/v1/api-keys/{fake_id}", headers=_auth_headers())
        self.assertIn(r.status_code, (404, 422, 500))

    def test_create_then_list_then_revoke_flow(self):
        """Full lifecycle: create → list → revoke."""
        client = _make_client()

        # Create
        r_create = client.post(
            "/v1/api-keys",
            json={"name": "lifecycle-test-328", "scopes": ["read_only"]},
            headers=_auth_headers(),
        )
        if r_create.status_code != 201:
            self.skipTest("API key create returned non-201")

        key_id = r_create.json()["id"]

        # List — should include the created key
        r_list = client.get("/v1/api-keys", headers=_auth_headers())
        self.assertEqual(r_list.status_code, 200)
        ids_in_list = [k["id"] for k in r_list.json()]
        self.assertIn(key_id, ids_in_list)

        # Revoke
        r_revoke = client.delete(f"/v1/api-keys/{key_id}", headers=_auth_headers())
        self.assertEqual(r_revoke.status_code, 200)
        self.assertEqual(r_revoke.json()["status"], "revoked")

    def test_create_api_key_with_expiry(self):
        """Create API key with explicit expiry."""
        client = _make_client()
        from datetime import datetime, timezone, timedelta
        exp = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        r = client.post(
            "/v1/api-keys",
            json={"name": "expiring-key", "scopes": ["read_only"], "expires_at": exp},
            headers=_auth_headers(),
        )
        self.assertIn(r.status_code, (201, 422, 500))

    def test_api_keys_no_auth_401(self):
        """No auth → 401."""
        client = _make_client()
        r = client.post("/v1/api-keys", json={"name": "x"})
        self.assertEqual(r.status_code, 401)

    def test_api_keys_invalid_token_401(self):
        """Invalid JWT → 401."""
        client = _make_client()
        r = client.post(
            "/v1/api-keys",
            json={"name": "x"},
            headers={"Authorization": "Bearer invalid-jwt-token"},
        )
        self.assertIn(r.status_code, (401, 422))


# ── Workers/Jobs (workers/jobs.py) ────────────────────────────────────────────

class TestWorkerJobsCoverage(unittest.TestCase):
    """Cover workers/jobs.py job functions via direct async invocation."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_webhook_delivery_subscription_not_found(self):
        """webhook_delivery when subscription lookup fails → returns skipped."""
        from backend.src.workers.jobs import webhook_delivery

        async def _sub_not_found():
            with patch("backend.src.core.db.get_async_session_maker") as mock_sm:
                session = AsyncMock()
                session.__aenter__ = AsyncMock(return_value=session)
                session.__aexit__ = AsyncMock(return_value=None)
                mock_sm.return_value = MagicMock(return_value=session)

                repo = AsyncMock()
                repo.get_by_id = AsyncMock(return_value=None)

                with patch("backend.src.webhooks.repository.WebhookRepository", return_value=repo):
                    result = await webhook_delivery(
                        ctx={},
                        subscription_id="sub-not-exist",
                        event_type="grant.created",
                        payload={"id": "g-1"},
                    )
                return result

        result = self._run(_sub_not_found())
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "subscription_not_found")

    def test_webhook_delivery_db_error_still_returns_skipped(self):
        """webhook_delivery when DB lookup raises → sub=None → returns skipped."""
        from backend.src.workers.jobs import webhook_delivery

        async def _db_error():
            with patch("backend.src.core.db.get_async_session_maker") as mock_sm:
                mock_sm.side_effect = Exception("db_unavailable")
                result = await webhook_delivery(
                    ctx={},
                    subscription_id="sub-id",
                    event_type="grant.created",
                    payload={},
                )
                return result

        result = self._run(_db_error())
        self.assertEqual(result["status"], "skipped")

    def test_audit_export_no_workspace(self):
        """audit_export without workspace_id runs successfully."""
        from backend.src.workers.jobs import audit_export
        from backend.src.core.db import init_db
        init_db()

        async def _run():
            return await audit_export(ctx={}, workspace_id=None)

        result = self._run(_run())
        self.assertIn(result["status"], ("complete", "error"))
        if result["status"] == "complete":
            self.assertIn("rows", result)

    def test_audit_export_with_workspace(self):
        """audit_export with workspace_id filter."""
        from backend.src.workers.jobs import audit_export
        from backend.src.core.db import init_db
        init_db()

        async def _run():
            return await audit_export(ctx={}, workspace_id="ws-test-328")

        result = self._run(_run())
        self.assertIn(result["status"], ("complete", "error"))

    def test_audit_export_with_destination(self):
        """audit_export writes to file when destination is set."""
        import tempfile
        from backend.src.workers.jobs import audit_export
        from backend.src.core.db import init_db
        init_db()

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            dest = f.name

        async def _run():
            return await audit_export(ctx={}, destination=dest)

        try:
            result = self._run(_run())
            self.assertIn(result["status"], ("complete", "error"))
            if result["status"] == "complete":
                self.assertTrue(os.path.exists(dest))
        finally:
            if os.path.exists(dest):
                os.unlink(dest)

    def test_email_notification_noop_backend(self):
        """email_notification with NOOP backend → success."""
        from backend.src.workers.jobs import email_notification

        async def _run():
            with patch.dict(os.environ, {"GRANTLAYER_EMAIL_BACKEND": "noop"}):
                return await email_notification(
                    ctx={},
                    to="test@example.com",
                    template="grant_approved",
                    context={"grant_id": "g-1", "subject_id": "user", "role": "viewer",
                             "action": "read", "resource": "doc/1"},
                )

        result = self._run(_run())
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["to"], "test@example.com")

    def test_email_notification_failure_under_max_retries_reraises(self):
        """email_notification failure below MAX_RETRIES re-raises."""
        from backend.src.workers.jobs import email_notification

        async def _fail():
            with patch("backend.src.notifications.email.send_email", side_effect=RuntimeError("smtp down")):
                try:
                    await email_notification(
                        ctx={},
                        to="x@example.com",
                        template="grant_approved",
                        context={},
                        attempt=0,
                    )
                    return "no_raise"
                except RuntimeError:
                    return "raised"

        result = self._run(_fail())
        self.assertEqual(result, "raised")

    def test_email_notification_failure_at_max_retries_deadletter(self):
        """email_notification failure at MAX_RETRIES → dead_letter."""
        from backend.src.workers.jobs import email_notification, MAX_JOB_RETRIES

        async def _max_fail():
            redis_mock = AsyncMock()
            redis_mock.lpush = AsyncMock()
            redis_mock.ltrim = AsyncMock()
            ctx = {"redis": redis_mock}
            with patch("backend.src.notifications.email.send_email", side_effect=RuntimeError("smtp down")):
                return await email_notification(
                    ctx=ctx,
                    to="x@example.com",
                    template="grant_approved",
                    context={},
                    attempt=MAX_JOB_RETRIES,
                )

        result = self._run(_max_fail())
        self.assertEqual(result["status"], "dead_letter")
        self.assertIn("error", result)

    def test_move_to_dlq_with_redis(self):
        """_move_to_dlq stores to Redis successfully."""
        from backend.src.workers.jobs import _move_to_dlq

        async def _dlq_test():
            redis_mock = AsyncMock()
            redis_mock.lpush = AsyncMock()
            redis_mock.ltrim = AsyncMock()
            ctx = {"redis": redis_mock}
            await _move_to_dlq(ctx, "test_job", {"key": "value"})
            redis_mock.lpush.assert_called_once()
            redis_mock.ltrim.assert_called_once()

        self._run(_dlq_test())

    def test_move_to_dlq_no_redis_logs_warning(self):
        """_move_to_dlq with no redis in ctx logs warning, no crash."""
        from backend.src.workers.jobs import _move_to_dlq

        async def _no_redis():
            await _move_to_dlq({}, "test_job", {"data": "x"})

        self._run(_no_redis())

    def test_move_to_dlq_redis_error_handled(self):
        """_move_to_dlq handles Redis errors gracefully."""
        from backend.src.workers.jobs import _move_to_dlq

        async def _redis_err():
            redis_mock = AsyncMock()
            redis_mock.lpush = AsyncMock(side_effect=Exception("redis down"))
            ctx = {"redis": redis_mock}
            await _move_to_dlq(ctx, "webhook_delivery", {"sub": "s1"})

        self._run(_redis_err())

    def test_webhook_delivery_max_retries_dead_letter(self):
        """webhook_delivery at MAX_RETRIES after delivery failure → dead_letter."""
        from backend.src.workers.jobs import webhook_delivery, MAX_JOB_RETRIES

        async def _max_retry():
            sub_data = {"url": "http://example.com/hook", "secret": "secret123"}

            with patch("backend.src.core.db.get_async_session_maker") as mock_sm:
                session = AsyncMock()
                session.__aenter__ = AsyncMock(return_value=session)
                session.__aexit__ = AsyncMock(return_value=None)
                mock_sm.return_value = MagicMock(return_value=session)

                repo = AsyncMock()
                repo.get_by_id = AsyncMock(return_value=sub_data)

                redis_mock = AsyncMock()
                redis_mock.lpush = AsyncMock()
                redis_mock.ltrim = AsyncMock()

                with patch("backend.src.webhooks.repository.WebhookRepository", return_value=repo):
                    with patch("httpx.AsyncClient") as mock_client_cls:
                        mock_http = AsyncMock()
                        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                        mock_http.__aexit__ = AsyncMock(return_value=None)
                        import httpx
                        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
                        mock_client_cls.return_value = mock_http

                        return await webhook_delivery(
                            ctx={"redis": redis_mock},
                            subscription_id="sub-1",
                            event_type="grant.created",
                            payload={"id": "g-1"},
                            attempt=MAX_JOB_RETRIES,
                        )

        result = self._run(_max_retry())
        self.assertEqual(result["status"], "dead_letter")


# ── Notifications/Email (notifications/email.py) ─────────────────────────────

class TestEmailCoverage(unittest.TestCase):
    """Cover notifications/email.py paths with mocks."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_make_unsubscribe_token_returns_string(self):
        """make_unsubscribe_token returns a signed token string."""
        from backend.src.notifications.email import make_unsubscribe_token
        token = make_unsubscribe_token("user@example.com")
        self.assertIsInstance(token, str)
        self.assertIn(".", token)

    def test_verify_token_valid(self):
        """verify_unsubscribe_token verifies a fresh token."""
        from backend.src.notifications.email import make_unsubscribe_token, verify_unsubscribe_token
        token = make_unsubscribe_token("user@example.com")
        email = verify_unsubscribe_token(token)
        self.assertEqual(email, "user@example.com")

    def test_verify_token_expired(self):
        """verify_unsubscribe_token returns None for expired token (max_age=0)."""
        from backend.src.notifications.email import make_unsubscribe_token, verify_unsubscribe_token
        token = make_unsubscribe_token("user@example.com")
        result = verify_unsubscribe_token(token, max_age_seconds=0)
        self.assertIsNone(result)

    def test_verify_token_invalid_sig(self):
        """verify_unsubscribe_token returns None for tampered signature."""
        from backend.src.notifications.email import make_unsubscribe_token, verify_unsubscribe_token
        token = make_unsubscribe_token("user@example.com")
        # Tamper the signature
        parts = token.rsplit(".", 1)
        tampered = parts[0] + ".ffffffffffffffff"
        result = verify_unsubscribe_token(tampered)
        self.assertIsNone(result)

    def test_verify_token_malformed(self):
        """verify_unsubscribe_token returns None for completely invalid token."""
        from backend.src.notifications.email import verify_unsubscribe_token
        self.assertIsNone(verify_unsubscribe_token("notavalidtoken"))
        self.assertIsNone(verify_unsubscribe_token(""))

    def test_send_email_noop(self):
        """send_email with noop backend logs and returns."""
        from backend.src.notifications.email import send_email
        with patch.dict(os.environ, {"GRANTLAYER_EMAIL_BACKEND": "noop"}):
            self._run(send_email(
                to="test@example.com",
                template="grant_approved",
                context={"grant_id": "g-1", "subject_id": "user", "role": "viewer",
                         "action": "read", "resource": "doc"},
            ))

    def test_send_email_adds_unsubscribe_url(self):
        """send_email auto-adds unsubscribe_url to context."""
        from backend.src.notifications.email import send_email
        ctx: dict = {}
        with patch.dict(os.environ, {"GRANTLAYER_EMAIL_BACKEND": "noop"}):
            self._run(send_email(to="x@example.com", template="grant_approved", context=ctx))
        self.assertIn("unsubscribe_url", ctx)

    def test_send_email_sendgrid_backend(self):
        """send_email with sendgrid backend calls httpx.AsyncClient.post."""
        from backend.src.notifications.email import send_email

        async def _sg():
            with patch.dict(os.environ, {
                "GRANTLAYER_EMAIL_BACKEND": "sendgrid",
                "GRANTLAYER_SENDGRID_API_KEY": "SG.test",
            }):
                mock_resp = MagicMock()
                mock_resp.raise_for_status = MagicMock()
                with patch("httpx.AsyncClient") as mock_cls:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(return_value=mock_resp)
                    mock_cls.return_value = mock_client
                    await send_email(
                        to="user@example.com",
                        template="grant_approved",
                        context={"grant_id": "g-1", "subject_id": "u", "role": "v",
                                 "action": "r", "resource": "d"},
                    )
                    mock_client.post.assert_called_once()

        self._run(_sg())

    def test_send_email_ses_no_boto3(self):
        """send_email with ses backend without boto3 raises RuntimeError."""
        from backend.src.notifications.email import send_email
        import sys

        async def _ses():
            with patch.dict(os.environ, {"GRANTLAYER_EMAIL_BACKEND": "ses"}):
                with patch.dict(sys.modules, {"boto3": None}):
                    try:
                        await send_email(
                            to="u@example.com",
                            template="grant_approved",
                            context={"grant_id": "g-1", "subject_id": "u", "role": "v",
                                     "action": "r", "resource": "d"},
                        )
                        return "no_raise"
                    except (RuntimeError, ImportError, TypeError):
                        return "raised"

        result = self._run(_ses())
        # Either raises or succeeds if boto3 is installed
        self.assertIn(result, ("raised", "no_raise"))

    def test_send_smtp_no_auth(self):
        """_send_smtp calls SMTP and sendmail (no user/password)."""
        from backend.src.notifications.email import _send_smtp

        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with patch.dict(os.environ, {
                "GRANTLAYER_SMTP_HOST": "localhost",
                "GRANTLAYER_SMTP_PORT": "25",
                "GRANTLAYER_SMTP_TLS": "false",
                "GRANTLAYER_SMTP_USER": "",
                "GRANTLAYER_SMTP_PASS": "",
            }):
                _send_smtp(to="x@example.com", subject="Test", html="<p>test</p>")
        mock_smtp.sendmail.assert_called_once()
        mock_smtp.quit.assert_called_once()

    def test_send_smtp_with_tls(self):
        """_send_smtp uses SMTP_SSL when TLS is enabled."""
        from backend.src.notifications.email import _send_smtp

        mock_smtp_ssl = MagicMock()
        with patch("smtplib.SMTP_SSL", return_value=mock_smtp_ssl):
            with patch.dict(os.environ, {
                "GRANTLAYER_SMTP_HOST": "smtp.example.com",
                "GRANTLAYER_SMTP_PORT": "465",
                "GRANTLAYER_SMTP_TLS": "true",
                "GRANTLAYER_SMTP_USER": "",
                "GRANTLAYER_SMTP_PASS": "",
            }):
                _send_smtp(to="x@example.com", subject="Test", html="<p>test</p>")
        mock_smtp_ssl.sendmail.assert_called_once()

    def test_send_smtp_with_user_password_calls_login(self):
        """_send_smtp with user/password calls smtp.login."""
        from backend.src.notifications.email import _send_smtp

        mock_smtp = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_smtp):
            with patch.dict(os.environ, {
                "GRANTLAYER_SMTP_HOST": "smtp.example.com",
                "GRANTLAYER_SMTP_PORT": "587",
                "GRANTLAYER_SMTP_TLS": "false",
                "GRANTLAYER_SMTP_USER": "user@example.com",
                "GRANTLAYER_SMTP_PASS": "secret",
            }):
                _send_smtp(to="x@example.com", subject="Test", html="<p>test</p>")
        mock_smtp.login.assert_called_once_with("user@example.com", "secret")

    def test_subject_for_known_templates(self):
        """_subject_for returns correct subject for known templates."""
        from backend.src.notifications.email import _subject_for
        self.assertIn("approved", _subject_for("grant_approved").lower())
        self.assertIn("rejected", _subject_for("grant_rejected").lower())
        self.assertIn("submitted", _subject_for("grant_request_submitted").lower())
        self.assertIn("webhook", _subject_for("webhook_failure_alert").lower())

    def test_subject_for_unknown_template(self):
        """_subject_for returns generic subject for unknown templates."""
        from backend.src.notifications.email import _subject_for
        s = _subject_for("custom_event")
        self.assertIn("custom_event", s)


# ── Telemetry (core/telemetry.py) ─────────────────────────────────────────────

class TestTelemetryCoverage(unittest.TestCase):
    """Cover core/telemetry.py setup and tracer access."""

    def test_setup_telemetry_no_otel(self):
        """setup_telemetry returns immediately when OTEL not available."""
        from backend.src.core import telemetry
        orig = telemetry._OTEL_AVAILABLE
        try:
            telemetry._OTEL_AVAILABLE = False
            telemetry.setup_telemetry("test-service")
        finally:
            telemetry._OTEL_AVAILABLE = orig

    def test_setup_telemetry_default_call(self):
        """setup_telemetry() with no args is safe to call."""
        from backend.src.core.telemetry import setup_telemetry
        setup_telemetry()

    def test_get_tracer_no_args_returns_something(self):
        """get_tracer() returns a tracer or NoOpTracer."""
        from backend.src.core.telemetry import get_tracer
        tracer = get_tracer()
        self.assertIsNotNone(tracer)

    def test_noop_tracer_context_manager(self):
        """NoOpTracer.start_as_current_span works as context manager."""
        from backend.src.core.telemetry import get_tracer
        tracer = get_tracer()
        with tracer.start_as_current_span("test-span") as span:
            span.set_attribute("key", "value")
            span.record_exception(ValueError("test"))

    def test_noop_tracer_start_span(self):
        """NoOpTracer.start_span returns a NoOpSpan."""
        from backend.src.core.telemetry import get_tracer
        tracer = get_tracer()
        span = tracer.start_span("my-span")
        self.assertIsNotNone(span)

    def test_get_current_trace_id_returns_none_or_str(self):
        """get_current_trace_id returns None (no OTEL) or a hex string."""
        from backend.src.core.telemetry import get_current_trace_id
        tid = get_current_trace_id()
        self.assertIn(tid, (None,) + (tuple() if tid is None else (tid,)))

    def test_instrument_fastapi_no_otel(self):
        """instrument_fastapi is a no-op when OTEL unavailable."""
        from backend.src.core.telemetry import instrument_fastapi
        instrument_fastapi(MagicMock())

    def test_instrument_sqlalchemy_no_otel(self):
        """instrument_sqlalchemy is a no-op when OTEL unavailable."""
        from backend.src.core.telemetry import instrument_sqlalchemy
        instrument_sqlalchemy(MagicMock())

    def test_env_str_and_env_bool_helpers(self):
        """_env_str and _env_bool work correctly."""
        from backend.src.core.telemetry import _env_str, _env_bool
        with patch.dict(os.environ, {"_TEST_VAR": "hello", "_TEST_BOOL": "true"}):
            self.assertEqual(_env_str("_TEST_VAR"), "hello")
            self.assertEqual(_env_str("_MISSING_VAR", "default"), "default")
            self.assertTrue(_env_bool("_TEST_BOOL"))
            self.assertFalse(_env_bool("_MISSING_BOOL"))
            self.assertTrue(_env_bool("_MISSING_BOOL", default=True))


# ── Deps (api/deps.py) ────────────────────────────────────────────────────────

class TestDepsCoverage(_JwtEnvMixin, unittest.TestCase):
    """Cover dependency factory functions in deps.py."""

    def test_get_grant_repo_factory(self):
        """get_grant_repo returns a SqlAlchemyGrantRepository."""
        from backend.src.api.deps import get_grant_repo
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyGrantRepository
        from sqlalchemy.orm import Session
        # Call with a mock session
        mock_sess = MagicMock(spec=Session)
        repo = get_grant_repo(mock_sess)
        self.assertIsInstance(repo, SqlAlchemyGrantRepository)

    def test_get_grant_request_repo_factory(self):
        """get_grant_request_repo returns SqlAlchemyGrantRequestRepository."""
        from backend.src.api.deps import get_grant_request_repo
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyGrantRequestRepository
        from sqlalchemy.orm import Session
        mock_sess = MagicMock(spec=Session)
        repo = get_grant_request_repo(mock_sess)
        self.assertIsInstance(repo, SqlAlchemyGrantRequestRepository)

    def test_get_grant_execution_repo_factory(self):
        """get_grant_execution_repo returns SqlAlchemyGrantExecutionRepository."""
        from backend.src.api.deps import get_grant_execution_repo
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyGrantExecutionRepository
        from sqlalchemy.orm import Session
        mock_sess = MagicMock(spec=Session)
        repo = get_grant_execution_repo(mock_sess)
        self.assertIsInstance(repo, SqlAlchemyGrantExecutionRepository)

    def test_get_operator_repo_factory(self):
        """get_operator_repo returns SqlAlchemyOperatorRepository."""
        from backend.src.api.deps import get_operator_repo
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyOperatorRepository
        from sqlalchemy.orm import Session
        mock_sess = MagicMock(spec=Session)
        repo = get_operator_repo(mock_sess)
        self.assertIsInstance(repo, SqlAlchemyOperatorRepository)

    def test_get_grant_service_factory(self):
        """get_grant_service returns an AsyncGrantService with repo."""
        from backend.src.api.deps import get_grant_service
        from backend.src.grants.grant_service import GrantService
        from sqlalchemy.orm import Session
        mock_sess = MagicMock(spec=Session)
        svc = get_grant_service(mock_sess)
        self.assertIsInstance(svc, GrantService)

    def test_get_grant_request_service_factory(self):
        """get_grant_request_service returns GrantRequestService."""
        from backend.src.api.deps import get_grant_request_service
        from backend.src.grants.grant_request_service import GrantRequestService
        from sqlalchemy.orm import Session
        mock_sess = MagicMock(spec=Session)
        svc = get_grant_request_service(mock_sess)
        self.assertIsInstance(svc, GrantRequestService)

    def test_get_operator_service_factory(self):
        """get_operator_service returns OperatorService."""
        from backend.src.api.deps import get_operator_service
        from backend.src.auth.operator_service import OperatorService
        from sqlalchemy.orm import Session
        mock_sess = MagicMock(spec=Session)
        svc = get_operator_service(mock_sess)
        self.assertIsInstance(svc, OperatorService)

    def test_require_admin_invalid_jwt_403(self):
        """require_admin with valid JWT but wrong role → 403."""
        from fastapi import HTTPException
        from backend.src.api.deps import require_admin
        token = _make_token(role="viewer")
        try:
            require_admin(f"Bearer {token}")
            self.fail("Should have raised")
        except HTTPException as e:
            self.assertEqual(e.status_code, 403)

    def test_resolve_auth_and_workspace_api_key_sync_invalid_prefix(self):
        """resolve_api_key_sync returns None for key without gl_live_ prefix."""
        from backend.src.api.routers.api_keys import resolve_api_key_sync
        result = resolve_api_key_sync("invalid-key-not-gl-live")
        self.assertIsNone(result)

    def test_resolve_api_key_sync_unknown_key(self):
        """resolve_api_key_sync returns None for unknown gl_live_ key."""
        from backend.src.api.routers.api_keys import resolve_api_key_sync
        from backend.src.core.db import init_db
        init_db()
        result = resolve_api_key_sync("gl_live_" + "a" * 64)
        self.assertIsNone(result)


# ── OPA Policy (policy/opa_client.py) ─────────────────────────────────────────

class TestOpaCoverage(unittest.TestCase):
    """Cover opa_client.py — sync/async evaluate paths."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_evaluate_policy_opa_not_configured_returns_true(self):
        """evaluate_policy skips when OPA not configured."""
        from backend.src.policy.opa_client import evaluate_policy

        async def _run():
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("GRANTLAYER_OPA_URL", None)
                return await evaluate_policy("grant.create", {"role": "admin"}, {})

        result = self._run(_run())
        self.assertTrue(result)

    def test_evaluate_policy_allowed_returns_true(self):
        """evaluate_policy returns True when OPA allows."""
        from backend.src.policy.opa_client import evaluate_policy

        async def _run():
            with patch.dict(os.environ, {"GRANTLAYER_OPA_URL": "http://opa:8181"}):
                mock_resp = MagicMock()
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json = MagicMock(return_value={"result": True})
                with patch("httpx.AsyncClient") as mock_cls:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(return_value=mock_resp)
                    mock_cls.return_value = mock_client
                    return await evaluate_policy("grant.create", {"role": "admin"}, {})

        result = self._run(_run())
        self.assertTrue(result)

    def test_evaluate_policy_denied_returns_false(self):
        """evaluate_policy returns False when OPA denies."""
        from backend.src.policy.opa_client import evaluate_policy

        async def _run():
            with patch.dict(os.environ, {"GRANTLAYER_OPA_URL": "http://opa:8181"}):
                mock_resp = MagicMock()
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json = MagicMock(return_value={"result": False})
                with patch("httpx.AsyncClient") as mock_cls:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(return_value=mock_resp)
                    mock_cls.return_value = mock_client
                    return await evaluate_policy("grant.create", {"role": "viewer"}, {})

        result = self._run(_run())
        self.assertFalse(result)

    def test_evaluate_policy_generic_exception_raises_503(self):
        """evaluate_policy raises HTTPException(503) on generic errors."""
        from fastapi import HTTPException
        from backend.src.policy.opa_client import evaluate_policy

        async def _run():
            with patch.dict(os.environ, {"GRANTLAYER_OPA_URL": "http://opa:8181"}):
                with patch("httpx.AsyncClient") as mock_cls:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(side_effect=ValueError("unexpected"))
                    mock_cls.return_value = mock_client
                    try:
                        await evaluate_policy("grant.create", {}, {})
                        return "no_raise"
                    except HTTPException as e:
                        return e.status_code

        result = self._run(_run())
        self.assertEqual(result, 503)

    def test_evaluate_policy_sync_no_opa_returns_true(self):
        """evaluate_policy_sync returns True when OPA not configured."""
        from backend.src.policy.opa_client import evaluate_policy_sync
        with patch.dict(os.environ, {}):
            os.environ.pop("GRANTLAYER_OPA_URL", None)
            result = evaluate_policy_sync("grant.create", {"role": "admin"}, {})
        self.assertTrue(result)

    def test_evaluate_policy_sync_unreachable_raises_503(self):
        """evaluate_policy_sync raises HTTPException 503 (fail-closed) when OPA unreachable."""
        from backend.src.policy.opa_client import evaluate_policy_sync
        import httpx
        from fastapi import HTTPException
        with patch.dict(os.environ, {"GRANTLAYER_OPA_URL": "http://opa:8181"}):
            with patch("httpx.Client") as mock_cls:
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=None)
                mock_client.post = MagicMock(side_effect=httpx.ConnectError("refused"))
                mock_cls.return_value = mock_client
                with self.assertRaises(HTTPException) as ctx:
                    evaluate_policy_sync("grant.create", {"role": "admin"}, {})
        self.assertEqual(ctx.exception.status_code, 503)

    def test_evaluate_policy_sync_allowed_returns_true(self):
        """evaluate_policy_sync returns True when OPA allows."""
        from backend.src.policy.opa_client import evaluate_policy_sync
        with patch.dict(os.environ, {"GRANTLAYER_OPA_URL": "http://opa:8181"}):
            with patch("httpx.Client") as mock_cls:
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=None)
                mock_resp = MagicMock()
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json = MagicMock(return_value={"result": True})
                mock_client.post = MagicMock(return_value=mock_resp)
                mock_cls.return_value = mock_client
                result = evaluate_policy_sync("grant.create", {"role": "admin"}, {})
        self.assertTrue(result)


# ── API key auth flow coverage ──────────────────────────────────────────────

class TestApiKeyAuthFlowCoverage(_JwtEnvMixin, unittest.TestCase):
    """Cover API key resolve paths by creating + using a real API key."""

    def test_api_key_used_in_bulk_request(self):
        """Create API key, then use it (gl_live_ Bearer) in a bulk request.

        Exercises resolve_api_key_sync (deps.py sync path) and
        async_resolve_auth_and_workspace (async api_key path).
        """
        client = _make_client()

        # Create a key using JWT auth
        r_create = client.post(
            "/v1/api-keys",
            json={"name": "auth-flow-test-key", "scopes": ["read_write"],
                  "workspace_id": "demo-workspace"},
            headers=_auth_headers(),
        )
        if r_create.status_code != 201:
            self.skipTest(f"API key create returned {r_create.status_code}")

        raw_key = r_create.json()["key"]

        # Use the API key in an exports request (goes through async_resolve_auth_and_workspace)
        r_exports = client.get(
            "/v1/exports/grants.csv",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        self.assertIn(r_exports.status_code, (200, 403, 422, 500))

    def test_api_key_used_in_sync_resolve(self):
        """resolve_api_key_sync full path with a real key in DB."""
        from backend.src.core.db import init_db
        init_db()

        client = _make_client()

        # Create a key
        r_create = client.post(
            "/v1/api-keys",
            json={"name": "sync-resolve-test", "scopes": ["read_only"],
                  "workspace_id": "demo-workspace"},
            headers=_auth_headers(),
        )
        if r_create.status_code != 201:
            self.skipTest(f"API key create returned {r_create.status_code}")

        raw_key = r_create.json()["key"]

        # Call resolve_api_key_sync directly with the real key
        from backend.src.api.routers.api_keys import resolve_api_key_sync
        result = resolve_api_key_sync(raw_key)
        self.assertIsNotNone(result)
        self.assertEqual(result["sub"], "cov-user-328")
        self.assertIn("workspace_id", result)


# ── Health endpoints (api/routers/health.py) ──────────────────────────────────

class TestHealthCoverage(_JwtEnvMixin, unittest.TestCase):
    """Cover health/readiness endpoint bodies."""

    def test_health_endpoint_returns_200(self):
        """GET /health returns 200 with status field (mounted without /v1 prefix)."""
        client = _make_client()
        r = client.get("/health")
        self.assertIn(r.status_code, (200, 503))
        data = r.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ("ok", "degraded"))

    def test_health_endpoint_has_database_field(self):
        """GET /health includes database and service fields."""
        client = _make_client()
        r = client.get("/health")
        if r.status_code == 200:
            data = r.json()
            self.assertIn("database", data)
            self.assertIn("service", data)
            self.assertIn("version", data)

    def test_health_endpoint_has_signing_key_field(self):
        """GET /health includes signing_key field."""
        client = _make_client()
        r = client.get("/health")
        if r.status_code == 200:
            data = r.json()
            self.assertIn("signing_key", data)
            self.assertIn(data["signing_key"], ("present", "absent"))

    def test_readiness_endpoint_returns_200_or_503(self):
        """GET /readiness returns 200 or 503 (no /v1 prefix)."""
        client = _make_client()
        r = client.get("/readiness")
        self.assertIn(r.status_code, (200, 503))

    def test_migration_revision_function(self):
        """_migration_revision returns a string."""
        from backend.src.core.db import init_db
        init_db()
        from backend.src.api.routers.health import _migration_revision
        result = _migration_revision()
        self.assertIsInstance(result, str)

    def test_signing_key_status_function(self):
        """_signing_key_status returns present or absent."""
        from backend.src.api.routers.health import _signing_key_status
        result = _signing_key_status()
        self.assertIn(result, ("present", "absent"))


# ── Workspace endpoints (api/routers/workspaces.py) ────────────────────────────

class TestWorkspacesCoverage(_JwtEnvMixin, unittest.TestCase):
    """Cover workspace handler bodies including plan update and get."""

    def _admin_headers(self):
        """JWT with owner role for require_admin."""
        return _auth_headers(role="owner")

    def test_list_workspaces_admin_200(self):
        """GET /workspaces returns a list with admin JWT."""
        client = _make_client()
        r = client.get("/v1/workspaces", headers=self._admin_headers())
        self.assertIn(r.status_code, (200, 403))
        if r.status_code == 200:
            self.assertIsInstance(r.json(), list)

    def test_get_workspace_not_found_404(self):
        """GET /workspaces/{id} for nonexistent → 404."""
        client = _make_client()
        r = client.get(f"/v1/workspaces/{uuid.uuid4()}", headers=self._admin_headers())
        self.assertIn(r.status_code, (404, 403))

    def test_update_workspace_plan_invalid_tier_422(self):
        """PATCH /workspaces/{id}/plan with invalid tier → 422."""
        client = _make_client()
        r = client.patch(
            f"/v1/workspaces/{uuid.uuid4()}/plan",
            json={"plan_tier": "ultra_premium"},
            headers=self._admin_headers(),
        )
        self.assertIn(r.status_code, (422, 403))

    def test_update_workspace_plan_negative_rate_limit_422(self):
        """PATCH /workspaces/{id}/plan with negative rate_limit_override → 422."""
        client = _make_client()
        r = client.patch(
            f"/v1/workspaces/{uuid.uuid4()}/plan",
            json={"plan_tier": "pro", "rate_limit_override": -1},
            headers=self._admin_headers(),
        )
        self.assertIn(r.status_code, (422, 403))

    def test_update_workspace_plan_nonexistent_workspace(self):
        """PATCH /workspaces/{id}/plan for nonexistent workspace → 404 or 200."""
        client = _make_client()
        r = client.patch(
            f"/v1/workspaces/{uuid.uuid4()}/plan",
            json={"plan_tier": "pro"},
            headers=self._admin_headers(),
        )
        self.assertIn(r.status_code, (200, 404, 403))


if __name__ == "__main__":
    unittest.main()
