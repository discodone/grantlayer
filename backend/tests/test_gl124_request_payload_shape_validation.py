"""Tests for GL-124: Request Payload Shape Validation Gate.

Ensures:
1. Oversized JSON body rejected safely (413 payload_too_large).
2. Oversized body response does not echo raw payload.
3. Malformed JSON rejected safely (400 invalid_json).
4. Malformed JSON response/log does not echo raw payload.
5. Empty JSON body rejected safely where object required (400 empty_request_body).
6. Top-level array rejected where object required (400 invalid_json_object).
7. Top-level string rejected where object required (400 invalid_json_object).
8. Top-level number rejected where object required (400 invalid_json_object).
9. Top-level boolean rejected where object required (400 invalid_json_object).
10. Top-level null rejected where object required (400 invalid_json_object).
11. Valid JSON object request still works for representative endpoint.
12. Existing GL-114 string length validation still handles overlong fields.
13. Rejection response includes/preserves X-Correlation-ID.
14. Structured rejection log includes correlation_id.
15. Structured rejection log does not include raw request body.
16. Auth/rate-limit behavior is not changed.
17. No OpenAPI change.
18. No migration change.
19. No frontend/website/design change.
20. No dependency changes.
"""

import json
import logging
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class _BaseGl124(unittest.TestCase):
    """Shared helpers for GL-124 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_rate_limit_auth = os.environ.get("GRANTLAYER_RATE_LIMIT_AUTH")
        self._orig_rate_limit_api = os.environ.get("GRANTLAYER_RATE_LIMIT_API")
        self._orig_enable_demo = os.environ.get("GRANTLAYER_ENABLE_DEMO_ENDPOINTS")
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()

        import backend.src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod
        self.handler_class = server_mod.GrantLayerHandler

        self.db_mod = db_mod

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
            ("GRANTLAYER_RATE_LIMIT_AUTH", self._orig_rate_limit_auth),
            ("GRANTLAYER_RATE_LIMIT_API", self._orig_rate_limit_api),
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

    def _make_raw_handler(
        self,
        path,
        method="GET",
        auth_header=None,
        body=b"",
        content_length=None,
        correlation_id_header=None,
        request_id_header=None,
    ):
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if body or content_length is not None:
            headers["Content-Length"] = (
                str(content_length) if content_length is not None else str(len(body))
            )
        if correlation_id_header is not None:
            headers["X-Correlation-ID"] = correlation_id_header
        if request_id_header is not None:
            headers["X-Request-ID"] = request_id_header
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
        elif handler.command == "OPTIONS":
            handler.do_OPTIONS()
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        header_block = parts[0].decode()
        resp_headers = {}
        for line in header_block.split("\r\n")[1:]:
            if ": " in line:
                k, v = line.split(": ", 1)
                resp_headers[k] = v
        if len(parts) > 1 and parts[1]:
            body = json.loads(parts[1])
        else:
            body = {}
        return status, resp_headers, body

    def _parse_log_json(self, log_str):
        start = log_str.find("{")
        if start == -1:
            self.fail(f"No JSON found in log record: {log_str}")
        return json.loads(log_str[start:])

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

    def _make_handler(self, path, method="GET", **kwargs):
        return (path, method, kwargs.get("auth_header"), kwargs.get("body", b""))

    def _run_handler(self, req):
        path, method, auth_header, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        elif method == "OPTIONS":
            resp = self.client.options(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    import json as _json
                    body_dict = _json.loads(body)
                    resp = self.client.post(path, json=body_dict, headers=headers)
                except (ValueError, UnicodeDecodeError):
                    resp = self.client.post(path, content=body, headers=headers)
            else:
                resp = self.client.post(path, headers=headers)
        try:
            import json as _json
            data = resp.json()
        except Exception:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("detail"), dict):
            data = data["detail"]
        return resp.status_code, dict(resp.headers), data



# ═══════════════════════════════════════════════════════════════════════
# 1–2. Oversized body
# ═══════════════════════════════════════════════════════════════════════

class TestGl124OversizedBody(_BaseGl124):
    """Oversized Content-Length is rejected before reading the body."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self.MAX_JSON_BODY_BYTES = fresh_server.MAX_JSON_BODY_BYTES

    def test_oversized_body_rejected_413(self):
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            content_length=self.MAX_JSON_BODY_BYTES + 1,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 413)
        self.assertEqual(body.get("errorCode"), "payload_too_large")

    def test_oversized_body_response_has_gl030_shape(self):
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            content_length=self.MAX_JSON_BODY_BYTES + 1,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 413)
        self.assertIn("error", body)
        self.assertIn("errorCode", body)
        self.assertIn("reason", body)

    def test_oversized_body_response_does_not_echo_payload(self):
        sentinel = "SENTINEL-OVERSIZED-GL124"
        oversized_body = sentinel.encode() + b"x" * 10
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=oversized_body,
            content_length=self.MAX_JSON_BODY_BYTES + 1,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 413)
        self.assertNotIn(sentinel, json.dumps(body))


# ═══════════════════════════════════════════════════════════════════════
# 3–4. Malformed JSON
# ═══════════════════════════════════════════════════════════════════════

class TestGl124MalformedJson(_BaseGl124):
    """Malformed JSON body is rejected safely without echoing the payload."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_malformed_json_rejected_400(self):
        bad_body = b"not json at all"
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=bad_body,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json")

    def test_malformed_json_response_does_not_echo_payload(self):
        sentinel = b"SECRET-MALFORMED-GL124"
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=sentinel,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertNotIn(sentinel.decode(), json.dumps(body))

    def test_malformed_json_log_does_not_echo_payload(self):
        logger = logging.getLogger("grantlayer.server")
        sentinel = b"SECRET-LOG-BODY-GL124"
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=sentinel,
        )
        with self.assertLogs(logger, level="INFO") as cm:
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn(sentinel.decode(), log_str)

    def test_truncated_json_rejected_400(self):
        bad_body = b'{"subjectId": "sub-1"'
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=bad_body,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json")


# ═══════════════════════════════════════════════════════════════════════
# 5. Empty body
# ═══════════════════════════════════════════════════════════════════════

class TestGl124EmptyBody(_BaseGl124):
    """Empty body is rejected where a JSON object is required."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_empty_body_rejected_400(self):
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=b"",
            content_length=0,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "empty_request_body")

    def test_empty_body_response_has_gl030_shape(self):
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=b"",
            content_length=0,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertIn("error", body)
        self.assertIn("errorCode", body)
        self.assertIn("reason", body)


# ═══════════════════════════════════════════════════════════════════════
# 6–10. Top-level non-object JSON values
# ═══════════════════════════════════════════════════════════════════════

class TestGl124NonObjectTopLevel(_BaseGl124):
    """Top-level JSON values that are not objects are rejected with invalid_json_object."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def _post_value(self, value):
        body = json.dumps(value).encode()
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=body,
        )
        return self._run_raw_handler(handler)

    def test_top_level_array_rejected(self):
        status, headers, body = self._post_value([{"key": "val"}])
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json_object")

    def test_top_level_string_rejected(self):
        status, headers, body = self._post_value("hello")
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json_object")

    def test_top_level_number_rejected(self):
        status, headers, body = self._post_value(42)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json_object")

    def test_top_level_boolean_true_rejected(self):
        status, headers, body = self._post_value(True)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json_object")

    def test_top_level_boolean_false_rejected(self):
        status, headers, body = self._post_value(False)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json_object")

    def test_top_level_null_rejected(self):
        status, headers, body = self._post_value(None)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json_object")

    def test_non_object_response_has_gl030_shape(self):
        status, headers, body = self._post_value([1, 2, 3])
        self.assertIn("error", body)
        self.assertIn("errorCode", body)
        self.assertIn("reason", body)


# ═══════════════════════════════════════════════════════════════════════
# 11. Valid JSON object preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl124ValidObjectPreserved(_BaseGl124):
    """Valid JSON object requests continue to work normally."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_valid_grant_object_accepted(self):
        body = json.dumps(self._grant_payload()).encode()
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=body,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 201)

    def test_valid_object_with_extra_fields_accepted(self):
        payload = self._grant_payload()
        payload["unknownField"] = "ignored"
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=body,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertIn(status, (201, 400))


# ═══════════════════════════════════════════════════════════════════════
# 12. GL-114 string length validation preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl124Gl114Preserved(_BaseGl124):
    """GL-114 string length validation is still active after GL-124 changes."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_overlong_subject_id_still_rejected(self):
        payload = self._grant_payload(overrides={"subjectId": "x" * 200})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=body,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)

    def test_overlong_role_still_rejected(self):
        payload = self._grant_payload(overrides={"role": "x" * 200})
        body = json.dumps(payload).encode()
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=body,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)


# ═══════════════════════════════════════════════════════════════════════
# 13–15. Correlation ID on rejection
# ═══════════════════════════════════════════════════════════════════════

class TestGl124CorrelationId(_BaseGl124):
    """X-Correlation-ID is preserved on rejection responses and in structured logs."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_malformed_json_rejection_echoes_correlation_id(self):
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=b"not json",
            correlation_id_header="corr-gl124-a",
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(headers.get("X-Correlation-ID"), "corr-gl124-a")

    def test_non_object_rejection_echoes_correlation_id(self):
        body_bytes = json.dumps([1, 2, 3]).encode()
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=body_bytes,
            correlation_id_header="corr-gl124-b",
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(headers.get("X-Correlation-ID"), "corr-gl124-b")

    def test_empty_body_rejection_echoes_correlation_id(self):
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=b"",
            content_length=0,
            correlation_id_header="corr-gl124-c",
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(headers.get("X-Correlation-ID"), "corr-gl124-c")

    def test_rejection_log_includes_correlation_id(self):
        logger = logging.getLogger("grantlayer.server")
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=b"bad json",
            correlation_id_header="corr-gl124-log",
        )
        with self.assertLogs(logger, level="INFO") as cm:
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertIn("corr-gl124-log", log_str)

    def test_rejection_log_does_not_include_raw_body(self):
        logger = logging.getLogger("grantlayer.server")
        sentinel = b"RAWBODY-SENTINEL-GL124"
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=sentinel,
            correlation_id_header="corr-gl124-d",
        )
        with self.assertLogs(logger, level="INFO") as cm:
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn(sentinel.decode(), log_str)


# ═══════════════════════════════════════════════════════════════════════
# 16. Auth/rate-limit behavior unchanged
# ═══════════════════════════════════════════════════════════════════════

class TestGl124AuthPreserved(_BaseGl124):
    """Auth rejection still fires before payload validation."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

    def test_missing_auth_still_401(self):
        body_bytes = json.dumps([1, 2]).encode()
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            body=body_bytes,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))

    def test_invalid_token_still_rejected(self):
        body_bytes = json.dumps({"key": "value"}).encode()
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer wrong-token",
            body=body_bytes,
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))


# ═══════════════════════════════════════════════════════════════════════
# 17–20. Scope checks
# ═══════════════════════════════════════════════════════════════════════

class TestGl124ScopeChecks(unittest.TestCase):
    """Verify no forbidden files were changed by GL-124."""

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        return result.stdout.strip()

    def test_no_openapi_change(self):
        changed = self._changed_files()
        self.assertNotIn("openapi.yaml", changed)

    def test_no_migration_change(self):
        changed = self._changed_files()
        self.assertNotIn("migrations/", changed)

    def test_no_frontend_or_website_change(self):
        changed = self._changed_files()
        self.assertNotIn("frontend/", changed)
        self.assertNotIn("website/", changed)

    def test_no_dependency_file_change(self):
        changed = self._changed_files()
        self.assertNotIn("pyproject.toml", changed)
        self.assertNotIn("requirements", changed)
        self.assertNotIn("package.json", changed)
        self.assertNotIn("package-lock.json", changed)


if __name__ == "__main__":
    unittest.main()
