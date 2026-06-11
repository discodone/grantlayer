"""Tests for GL-114: String-length validation baseline.

Ensures:
1. Validation helper accepts normal strings.
2. Validation helper rejects overlong strings deterministically.
3. Validation helper error messages include field name and max length.
4. Validation helper error messages do not include the full oversized value.
5. Validation helper accepts None for optional fields.
6. Challenge creation rejects oversized inputs.
7. Grant request creation rejects oversized inputs.
8. Grant request revoke rejects oversized reason.
9. Server API boundaries return safe 400 for overlong inputs.
10. Existing valid flows are preserved.
11. No state mutation on validation failure.
12. No OpenAPI/migration/frontend changes.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl114(unittest.TestCase):
    """Shared helpers for GL-114 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin"
        os.environ["GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN"] = "bootstrap-token"

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.challenges as ch_mod
        importlib.reload(ch_mod)
        self.ch_mod = ch_mod

        import backend.src.grant_requests as requests_mod
        importlib.reload(requests_mod)
        self.requests_mod = requests_mod

        import backend.src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod

        self.db_mod = db_mod
        self.handler_class = server_mod.GrantLayerHandler

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_ENABLE_DEMO_ENDPOINTS", self._orig_enable_demo),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _insert_operator(self, op_id, name, role, token):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, datetime('now'))""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _make_handler(self, path, method="GET", auth_header=None, body=b"", content_length=None):
        return (path, method, auth_header, body)

    def _run_handler(self, req):
        path, method, auth_header, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    body_dict = json.loads(body)
                    resp = self.client.post(path, json=body_dict, headers=headers)
                except (ValueError, UnicodeDecodeError):
                    resp = self.client.post(path, content=body, headers=headers)
            else:
                resp = self.client.post(path, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("detail"), dict):
            data = data["detail"]
        return resp.status_code, data

    def _make_raw_handler(self, path, method="GET", auth_header=None, body=b"", content_length=None):
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if body or content_length is not None:
            headers["Content-Length"] = str(content_length) if content_length is not None else str(len(body))
        handler.headers = headers
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        return handler

    def _run_raw_handler(self, handler):
        if handler.command == "GET":
            handler.do_GET()
        elif handler.command == "POST":
            handler.do_POST()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        body = json.loads(parts[1]) if len(parts) > 1 else {}
        return status, body

    def _assert_gl030_full(self, payload):
        self.assertIn("error", payload)
        self.assertIn("errorCode", payload)
        self.assertIn("reason", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)

    def _grant_payload(self, overrides=None):
        base = {
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2099-12-31T23:59:59Z",
            "createdBy": "admin-1",
            "reason": "test",
        }
        if overrides:
            base.update(overrides)
        return base


# ═══════════════════════════════════════════════════════════════════════
# 1. Validation helper unit tests
# ═══════════════════════════════════════════════════════════════════════

class TestGl114ValidationHelper(_BaseGl114):
    """Unit tests for validation.py helpers."""

    def test_validate_string_length_accepts_normal_string(self):
        from backend.src.validation import validate_string_length
        validate_string_length("valid-string", "test_field", 256)

    def test_validate_string_length_accepts_empty_string(self):
        from backend.src.validation import validate_string_length
        validate_string_length("", "test_field", 256)

    def test_validate_string_length_accepts_exact_boundary(self):
        from backend.src.validation import validate_string_length
        validate_string_length("x" * 128, "test_field", 128)

    def test_validate_string_length_rejects_overlong(self):
        from backend.src.validation import validate_string_length, ValidationError
        with self.assertRaises(ValidationError) as ctx:
            validate_string_length("x" * 129, "test_field", 128)
        self.assertIn("test_field", str(ctx.exception))
        self.assertIn("128", str(ctx.exception))

    def test_validate_string_length_error_does_not_echo_full_value(self):
        from backend.src.validation import validate_string_length, ValidationError
        long_val = "x" * 5000
        with self.assertRaises(ValidationError) as ctx:
            validate_string_length(long_val, "test_field", 256)
        msg = str(ctx.exception)
        self.assertNotIn(long_val, msg)

    def test_validate_string_length_rejects_non_string(self):
        from backend.src.validation import validate_string_length, ValidationError
        with self.assertRaises(ValidationError):
            validate_string_length(123, "test_field", 256)

    def test_validate_optional_string_length_accepts_none(self):
        from backend.src.validation import validate_optional_string_length
        validate_optional_string_length(None, "test_field", 256)

    def test_validate_optional_string_length_accepts_normal_string(self):
        from backend.src.validation import validate_optional_string_length
        validate_optional_string_length("valid", "test_field", 256)

    def test_validate_optional_string_length_rejects_overlong(self):
        from backend.src.validation import validate_optional_string_length, ValidationError
        with self.assertRaises(ValidationError):
            validate_optional_string_length("x" * 129, "test_field", 128)

    def test_max_constants_present(self):
        from src import validation as v
        self.assertEqual(v.MAX_SHORT_ID_LENGTH, 128)
        self.assertEqual(v.MAX_ROLE_LENGTH, 64)
        self.assertEqual(v.MAX_NAME_LENGTH, 256)
        self.assertEqual(v.MAX_REASON_LENGTH, 1000)


# ═══════════════════════════════════════════════════════════════════════
# 2. Challenge creation length validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl114ChallengeLengthValidation(_BaseGl114):
    """Tests for challenge creation string length validation."""

    def test_create_challenge_accepts_normal_strings(self):
        ch = self.ch_mod.create_challenge("sub-1", "read", "repo-a")
        self.assertEqual(ch.subject_id, "sub-1")
        self.assertEqual(ch.action, "read")
        self.assertEqual(ch.resource, "repo-a")

    def test_create_challenge_rejects_overlong_subject_id(self):
        from backend.src.validation import ValidationError
        with self.assertRaises(ValidationError) as ctx:
            self.ch_mod.create_challenge("x" * 129, "read", "repo-a")
        self.assertIn("subject_id", str(ctx.exception))

    def test_create_challenge_rejects_overlong_action(self):
        from backend.src.validation import ValidationError
        with self.assertRaises(ValidationError):
            self.ch_mod.create_challenge("sub-1", "x" * 257, "repo-a")

    def test_create_challenge_rejects_overlong_resource(self):
        from backend.src.validation import ValidationError
        with self.assertRaises(ValidationError):
            self.ch_mod.create_challenge("sub-1", "read", "x" * 257)

    def test_create_challenge_boundary_length_accepted(self):
        ch = self.ch_mod.create_challenge("x" * 128, "x" * 256, "x" * 256)
        self.assertEqual(ch.subject_id, "x" * 128)


# ═══════════════════════════════════════════════════════════════════════
# 3. Grant request module length validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl114GrantRequestModuleValidation(_BaseGl114):
    """Tests for grant_requests.py string length validation."""

    def test_create_grant_request_accepts_normal_strings(self):
        req = self.models_mod.GrantRequest(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="test",
        )
        created = self.requests_mod.create_grant_request(req)
        self.assertEqual(created.subject_id, "sub-1")

    def test_create_grant_request_rejects_overlong_subject_id(self):
        from backend.src.validation import ValidationError
        req = self.models_mod.GrantRequest(
            subject_id="x" * 129,
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="test",
        )
        with self.assertRaises(ValidationError) as ctx:
            self.requests_mod.create_grant_request(req)
        self.assertIn("subject_id", str(ctx.exception))

    def test_create_grant_request_rejects_overlong_role(self):
        from backend.src.validation import ValidationError
        req = self.models_mod.GrantRequest(
            subject_id="sub-1",
            role="x" * 65,
            action="read",
            resource="repo-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="test",
        )
        with self.assertRaises(ValidationError):
            self.requests_mod.create_grant_request(req)

    def test_create_grant_request_rejects_overlong_action(self):
        from backend.src.validation import ValidationError
        req = self.models_mod.GrantRequest(
            subject_id="sub-1",
            role="engineer",
            action="x" * 257,
            resource="repo-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="test",
        )
        with self.assertRaises(ValidationError):
            self.requests_mod.create_grant_request(req)

    def test_create_grant_request_rejects_overlong_resource(self):
        from backend.src.validation import ValidationError
        req = self.models_mod.GrantRequest(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="x" * 257,
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="test",
        )
        with self.assertRaises(ValidationError):
            self.requests_mod.create_grant_request(req)

    def test_create_grant_request_rejects_overlong_reason(self):
        from backend.src.validation import ValidationError
        req = self.models_mod.GrantRequest(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="x" * 1001,
        )
        with self.assertRaises(ValidationError):
            self.requests_mod.create_grant_request(req)

    def test_create_grant_request_boundary_length_accepted(self):
        req = self.models_mod.GrantRequest(
            subject_id="x" * 128,
            role="x" * 64,
            action="x" * 256,
            resource="x" * 256,
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="x" * 1000,
        )
        created = self.requests_mod.create_grant_request(req)
        self.assertEqual(created.reason, "x" * 1000)

    def test_revoke_grant_request_rejects_overlong_reason(self):
        from backend.src.validation import ValidationError
        req = self.models_mod.GrantRequest(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="test",
            status="approved",
        )
        created = self.requests_mod.create_grant_request(req)
        with self.assertRaises(ValidationError) as ctx:
            self.requests_mod.revoke_grant_request(created.id, "admin-1", "x" * 1001)
        self.assertIn("reason", str(ctx.exception))

    def test_revoke_grant_request_boundary_reason_accepted(self):
        req = self.models_mod.GrantRequest(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="admin-1",
            reason="test",
            status="approved",
        )
        created = self.requests_mod.create_grant_request(req)
        result = self.requests_mod.revoke_grant_request(created.id, "admin-1", "x" * 1000)
        self.assertEqual(result.revoked_reason, "x" * 1000)


# ═══════════════════════════════════════════════════════════════════════
# 4. Server API boundary length validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl114ServerApiBoundaryValidation(_BaseGl114):
    """Tests for server.py API boundary string length validation."""

    def test_post_grant_rejects_overlong_subject_id(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"subjectId": "x" * 129})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self._assert_gl030_full(data)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("subjectId", data["reason"])
        self.assertIn("128", data["reason"])

    def test_post_grant_rejects_overlong_role(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"role": "x" * 65})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("role", data["reason"])

    def test_post_grant_rejects_overlong_action(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"action": "x" * 257})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("action", data["reason"])

    def test_post_grant_rejects_overlong_resource(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"resource": "x" * 257})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("resource", data["reason"])

    def test_post_grant_rejects_overlong_created_by(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"createdBy": "x" * 129})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("createdBy", data["reason"])

    def test_post_grant_rejects_overlong_reason(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({"reason": "x" * 1001})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("reason", data["reason"])

    def test_post_grant_boundary_lengths_accepted(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload({
            "subjectId": "x" * 128,
            "role": "x" * 64,
            "action": "x" * 256,
            "resource": "x" * 256,
            "createdBy": "x" * 128,
            "reason": "x" * 1000,
        })
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 201)
        self.assertEqual(data["subject_id"], "x" * 128)

    def test_error_response_does_not_echo_full_overlong_value(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        long_val = "x" * 5000
        payload = self._grant_payload({"subjectId": long_val})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        raw = json.dumps(data)
        self.assertNotIn(long_val, raw)

    def test_post_challenge_rejects_overlong_subject_id(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {"subjectId": "x" * 129, "action": "read", "resource": "repo-a"}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/challenges", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("subjectId", data["reason"])

    def test_post_challenge_rejects_overlong_action(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {"subjectId": "sub-1", "action": "x" * 257, "resource": "repo-a"}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/challenges", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("action", data["reason"])

    def test_post_challenge_rejects_overlong_resource(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {"subjectId": "sub-1", "action": "read", "resource": "x" * 257}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/challenges", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("resource", data["reason"])

    def test_post_challenge_boundary_accepted(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {"subjectId": "x" * 128, "action": "x" * 256, "resource": "x" * 256}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/challenges", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 201)
        self.assertEqual(data["subjectId"], "x" * 128)

    def test_post_demo_action_rejects_overlong_subject_id(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        payload = {"subjectId": "x" * 129, "role": "engineer", "action": "read", "resource": "repo-a"}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/demo-action", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("subjectId", data["reason"])

    def test_post_demo_action_rejects_overlong_challenge_id(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        payload = {"subjectId": "sub-1", "role": "engineer", "action": "read", "resource": "repo-a", "challengeId": "x" * 129}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/demo-action", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("challengeId", data["reason"])

    def test_post_demo_action_boundary_accepted(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.handler_class = fresh_server.GrantLayerHandler
        payload = {"subjectId": "x" * 128, "role": "x" * 64, "action": "x" * 256, "resource": "x" * 256}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/demo-action", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertIn(status, (200, 403))  # no matching grant expected, but validated

    def test_post_grant_request_rejects_overlong_reason(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {
            "subjectId": "sub-1",
            "role": "reviewer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-02T00:00:00Z",
            "reason": "x" * 1001,
        }
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grant-requests", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("reason", data["reason"])

    def test_post_grant_request_boundary_accepted(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {
            "subjectId": "x" * 128,
            "role": "reviewer",
            "action": "x" * 256,
            "resource": "x" * 256,
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-02T00:00:00Z",
            "reason": "x" * 1000,
        }
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grant-requests", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 201)
        self.assertEqual(data["reason"], "x" * 1000)

    def test_post_grant_revoke_rejects_overlong_reason(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        g = self.models_mod.Grant(
            subject_id="sub-1", role="engineer", action="read", resource="repo-a",
            valid_from="2026-01-01T00:00:00Z", valid_until="2099-12-31T23:59:59Z",
            created_by="admin-1", reason="test",
        )
        self.grants_mod.create_grant(g)
        payload = {"revokedBy": "admin-1", "reason": "x" * 1001}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler(f"/grants/{g.id}/revoke", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("reason", data["reason"])

    def test_post_grant_revoke_boundary_accepted(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        g = self.models_mod.Grant(
            subject_id="sub-1", role="engineer", action="read", resource="repo-a",
            valid_from="2026-01-01T00:00:00Z", valid_until="2099-12-31T23:59:59Z",
            created_by="admin-1", reason="test",
        )
        self.grants_mod.create_grant(g)
        payload = {"revokedBy": "admin-1", "reason": "x" * 1000}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler(f"/grants/{g.id}/revoke", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 200)

    def test_post_grant_request_deny_rejects_overlong_reason(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("approver-1", "Approver", "owner", "approver-token")
        req = self.models_mod.GrantRequest(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-01-02T00:00:00Z",
            requested_by="owner-1",
            reason="test",
        )
        created = self.requests_mod.create_grant_request(req)
        payload = {"reason": "x" * 1001}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler(
            f"/grant-requests/{created.id}/deny",
            method="POST",
            auth_header="Bearer approver-token",
            body=body,
        )
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(data["errorCode"], "invalid_field")
        self.assertIn("reason", data["reason"])

    def test_post_grant_request_deny_boundary_accepted(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._insert_operator("approver-1", "Approver", "owner", "approver-token")
        req = self.models_mod.GrantRequest(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-01-02T00:00:00Z",
            requested_by="owner-1",
            reason="test",
        )
        created = self.requests_mod.create_grant_request(req)
        payload = {"reason": "x" * 1000}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler(
            f"/grant-requests/{created.id}/deny",
            method="POST",
            auth_header="Bearer approver-token",
            body=body,
        )
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(data["request"]["denial_reason"], "x" * 1000)


# ═══════════════════════════════════════════════════════════════════════
# 5. No state mutation on validation failure
# ═══════════════════════════════════════════════════════════════════════

class TestGl114NoStateMutationOnFailure(_BaseGl114):
    """Verify validation failures do not mutate state."""

    def test_overlong_grant_does_not_create_grant(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        before = len(self.grants_mod.list_grants())
        payload = self._grant_payload({"subjectId": "x" * 129})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        after = len(self.grants_mod.list_grants())
        self.assertEqual(before, after)

    def test_overlong_challenge_does_not_create_challenge(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        before = len(self.ch_mod.list_challenges())
        payload = {"subjectId": "x" * 129, "action": "read", "resource": "repo-a"}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/challenges", method="POST", auth_header="Bearer owner-token", body=body)
        status, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        after = len(self.ch_mod.list_challenges())
        self.assertEqual(before, after)

    def test_overlong_grant_request_does_not_create_request(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        before = len(self.requests_mod.list_grant_requests())
        payload = {
            "subjectId": "sub-1",
            "role": "reviewer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-02T00:00:00Z",
            "reason": "x" * 1001,
        }
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grant-requests", method="POST", auth_header="Bearer owner-token", body=body)
        status, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        after = len(self.requests_mod.list_grant_requests())
        self.assertEqual(before, after)


# ═══════════════════════════════════════════════════════════════════════
# 6. Existing valid behavior preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl114ExistingBehaviorPreserved(_BaseGl114):
    """Regression tests: existing valid flows remain accepted."""

    def test_valid_grant_creation_still_works(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = self._grant_payload()
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 201)
        self.assertEqual(data["subject_id"], "sub-1")

    def test_valid_challenge_creation_still_works(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {"subjectId": "sub-1", "action": "read", "resource": "repo-a"}
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/challenges", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 201)
        self.assertEqual(data["subjectId"], "sub-1")

    def test_valid_grant_request_creation_still_works(self):
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        payload = {
            "subjectId": "sub-1",
            "role": "reviewer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2026-01-01T00:00:00Z",
            "validUntil": "2026-01-02T00:00:00Z",
            "reason": "Routine maintenance",
        }
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler("/grant-requests", method="POST", auth_header="Bearer owner-token", body=body)
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 201)
        self.assertEqual(data["status"], "requested")

    def test_health_endpoint_still_public(self):
        handler = self._make_raw_handler("/health")
        status, data = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_readiness_endpoint_still_public(self):
        handler = self._make_raw_handler("/readiness")
        status, data = self._run_raw_handler(handler)
        self.assertIn(status, (200, 503))


# ═══════════════════════════════════════════════════════════════════════
# 7. Scope guard — diff validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl114NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-114 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-114-string-length-validation":
            self.skipTest(
                "Branch-wide diff check only valid on GL-114 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/validation.py",
            "backend/src/server.py",
            "backend/src/challenges.py",
            "backend/src/grant_requests.py",
            "backend/tests/test_gl114_string_length_validation.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-114 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
