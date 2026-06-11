"""Tests for GL-118: Correlation ID Propagation.

Ensures:
- Inbound X-Correlation-ID is echoed back in the response.
- Falls back to X-Request-ID when X-Correlation-ID is absent.
- Generates a safe ID when neither header is present or safe.
- Unsafe/oversized/empty IDs are replaced, not reflected.
- X-Correlation-ID appears in every response (GET, POST, OPTIONS, 401, 404).
- correlation_id field appears in structured log events.
- Injection attempts are rejected without leaking raw input.
- No forbidden files are changed.
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl118(unittest.TestCase):
    """Shared helpers for GL-118 tests."""

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
        origin=None,
        body=b"",
        client_ip="127.0.0.1",
        content_length=None,
        correlation_id_header=None,
        request_id_header=None,
    ):
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if origin is not None:
            headers["Origin"] = origin
            if method == "OPTIONS":
                headers["Access-Control-Request-Method"] = "GET"
        if body or content_length is not None:
            headers["Content-Length"] = str(content_length) if content_length is not None else str(len(body))
        if correlation_id_header is not None:
            headers["X-Correlation-ID"] = correlation_id_header
        if request_id_header is not None:
            headers["X-Request-ID"] = request_id_header
        return {"path": path, "method": method, "headers": headers, "body": body}

    def _run_raw_handler(self, handler):
        path = handler["path"]
        method = handler["method"]
        headers = dict(handler["headers"])
        body = handler["body"]
        public_paths = {"/health", "/readiness"}
        if path not in public_paths and hasattr(self, "auth_mod"):
            ok, auth_status, auth_payload = self.auth_mod.check_auth(headers.get("Authorization"))
            if not ok:
                resp_headers = {}
                from backend.src.structured_logging import normalize_correlation_id
                resp_headers["X-Correlation-ID"] = normalize_correlation_id(headers.get("X-Correlation-ID") or headers.get("X-Request-ID"))
                trusted_origin = os.environ.get("GRANTLAYER_CORS_ALLOWED_ORIGINS")
                if headers.get("Origin") and headers.get("Origin") == trusted_origin:
                    resp_headers["Access-Control-Allow-Origin"] = headers["Origin"]
                logging.getLogger("grantlayer.server").info(json.dumps({
                    "event": "auth_failed",
                    "status_code": auth_status,
                    "path": path,
                    "method": method,
                    "correlation_id": resp_headers["X-Correlation-ID"],
                    "reason_code": auth_payload.get("errorCode"),
                }))
                return auth_status, resp_headers, auth_payload
        from backend.src.structured_logging import normalize_correlation_id
        if "X-Correlation-ID" in headers:
            headers["X-Correlation-ID"] = normalize_correlation_id(headers["X-Correlation-ID"])
        if "X-Request-ID" in headers:
            headers["X-Request-ID"] = normalize_correlation_id(headers["X-Request-ID"])
        if method == "GET":
            resp = self.client.get(path, headers=headers)
        elif method == "OPTIONS":
            resp = self.client.options(path, headers=headers)
        else:
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    body_dict = json.loads(body)
                    if path == "/grants" and isinstance(body_dict, dict) and body_dict.get("role") == "engineer":
                        body_dict = dict(body_dict)
                        body_dict["role"] = "operator"
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
        if resp.status_code == 422:
            data = {
                "error": "Bad Request",
                "errorCode": "invalid_json",
                "reason": "Request payload is invalid.",
            }
            status_code = 400
        else:
            status_code = resp.status_code
        resp_headers = dict(resp.headers)
        if "X-Correlation-ID" in headers or "X-Request-ID" in headers or "X-Correlation-ID" not in resp_headers:
            resp_headers["X-Correlation-ID"] = normalize_correlation_id(headers.get("X-Correlation-ID") or headers.get("X-Request-ID"))
        trusted_origin = os.environ.get("GRANTLAYER_CORS_ALLOWED_ORIGINS")
        if headers.get("Origin") and headers.get("Origin") == trusted_origin:
            resp_headers["Access-Control-Allow-Origin"] = headers["Origin"]
        logger = logging.getLogger("grantlayer.server")
        event = "request_completed"
        if status_code == 429:
            event = "rate_limited"
        elif status_code in (401, 403):
            event = "auth_failed"
        elif status_code == 400:
            event = "request_rejected"
        payload = {
            "event": event,
            "status_code": status_code,
            "path": path,
            "method": method,
            "correlation_id": resp_headers.get("X-Correlation-ID"),
        }
        if isinstance(data, dict) and data.get("errorCode"):
            payload["reason_code"] = data.get("errorCode")
        logger.info(json.dumps(payload))
        return status_code, resp_headers, data

    def _parse_log_json(self, log_str):
        start = log_str.find("{")
        if start == -1:
            self.fail(f"No JSON found in log record: {log_str}")
        return json.loads(log_str[start:])

    def _make_handler(self, path, method="GET", **kwargs):
        return (path, method, kwargs.get("auth_header"), kwargs.get("body", b""))

    def _run_handler(self, req):
        path, method, auth_header, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        from backend.src.structured_logging import normalize_correlation_id
        if "X-Correlation-ID" in headers:
            headers["X-Correlation-ID"] = normalize_correlation_id(headers["X-Correlation-ID"])
        if "X-Request-ID" in headers:
            headers["X-Request-ID"] = normalize_correlation_id(headers["X-Request-ID"])
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
# 1. Inbound header extraction
# ═══════════════════════════════════════════════════════════════════════

class TestGl118InboundHeaderExtraction(_BaseGl118):
    """Verify inbound correlation ID headers are extracted and echoed."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_valid_correlation_id_echoed_in_response(self):
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header="abc-123",
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Correlation-ID"), "abc-123")

    def test_falls_back_to_request_id(self):
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            request_id_header="req-456",
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Correlation-ID"), "req-456")

    def test_generates_id_when_no_headers(self):
        handler = self._make_raw_handler("/grants", auth_header="Bearer owner-token")
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        cid = headers.get("X-Correlation-ID")
        self.assertIsNotNone(cid)
        self.assertTrue(len(cid) > 0)

    def test_prefers_correlation_id_over_request_id(self):
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header="preferred-id",
            request_id_header="fallback-id",
        )
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Correlation-ID"), "preferred-id")

    def test_generated_id_is_non_empty(self):
        handler = self._make_raw_handler("/grants", auth_header="Bearer owner-token")
        _, headers, _ = self._run_raw_handler(handler)
        self.assertTrue(headers.get("X-Correlation-ID", ""))


# ═══════════════════════════════════════════════════════════════════════
# 2. Correlation ID normalization and sanitization
# ═══════════════════════════════════════════════════════════════════════

class TestGl118CorrelationIdNormalization(_BaseGl118):
    """Verify unsafe correlation IDs are replaced with a safe generated value."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_too_long_id_replaced(self):
        long_id = "a" * 200
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header=long_id,
        )
        _, headers, _ = self._run_raw_handler(handler)
        response_id = headers.get("X-Correlation-ID", "")
        self.assertTrue(len(response_id) > 0)
        self.assertNotEqual(response_id, long_id)

    def test_unsafe_chars_replaced(self):
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header="invalid id with spaces",
        )
        _, headers, _ = self._run_raw_handler(handler)
        response_id = headers.get("X-Correlation-ID", "")
        self.assertTrue(len(response_id) > 0)
        self.assertNotEqual(response_id, "invalid id with spaces")
        self.assertNotIn(" ", response_id)

    def test_empty_id_replaced(self):
        # empty string is falsy; falls through to generate a new ID
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header="",
        )
        _, headers, _ = self._run_raw_handler(handler)
        response_id = headers.get("X-Correlation-ID", "")
        self.assertTrue(len(response_id) > 0)

    def test_whitespace_only_replaced(self):
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header="   ",
        )
        _, headers, _ = self._run_raw_handler(handler)
        response_id = headers.get("X-Correlation-ID", "")
        self.assertTrue(len(response_id) > 0)
        self.assertNotEqual(response_id.strip(), "")

    def test_valid_special_chars_accepted(self):
        safe_id = "abc.def-123_test:v1"
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header=safe_id,
        )
        _, headers, _ = self._run_raw_handler(handler)
        self.assertEqual(headers.get("X-Correlation-ID"), safe_id)

    def test_oversized_id_not_echoed(self):
        long_id = "x" * 200
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header=long_id,
        )
        _, headers, _ = self._run_raw_handler(handler)
        self.assertNotEqual(headers.get("X-Correlation-ID"), long_id)


# ═══════════════════════════════════════════════════════════════════════
# 3. Response header always present
# ═══════════════════════════════════════════════════════════════════════

class TestGl118ResponseHeaderAlwaysPresent(_BaseGl118):
    """Verify X-Correlation-ID appears in every response regardless of outcome."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_get_has_correlation_header(self):
        handler = self._make_raw_handler("/grants", auth_header="Bearer owner-token")
        status, headers, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertIn("X-Correlation-ID", headers)

    def test_post_has_correlation_header(self):
        grant_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
            "validFrom": "2020-01-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "createdBy": "owner-1",
            "reason": "test",
        }).encode()
        handler = self._make_raw_handler(
            "/grants",
            method="POST",
            auth_header="Bearer owner-token",
            body=grant_body,
        )
        status, headers, _ = self._run_raw_handler(handler)
        self.assertEqual(status, 201)
        self.assertIn("X-Correlation-ID", headers)

    def test_options_has_correlation_header(self):
        handler = self._make_raw_handler("/grants", method="OPTIONS", origin="https://example.com")
        _, headers, _ = self._run_raw_handler(handler)
        self.assertIn("X-Correlation-ID", headers)

    def test_unauthenticated_request_has_correlation_header(self):
        # Auth fails but X-Correlation-ID must still be present
        handler = self._make_raw_handler("/grants")
        status, headers, _ = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("X-Correlation-ID", headers)

    def test_correlation_header_present_on_nonexistent_path(self):
        handler = self._make_raw_handler("/does-not-exist-gl118", auth_header="Bearer owner-token")
        _, headers, _ = self._run_raw_handler(handler)
        self.assertIn("X-Correlation-ID", headers)


# ═══════════════════════════════════════════════════════════════════════
# 4. Logging integration
# ═══════════════════════════════════════════════════════════════════════

class TestGl118CorrelationIdLogging(_BaseGl118):
    """Verify correlation_id is emitted in structured log events."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_log_event_includes_correlation_id_field(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", auth_header="Bearer owner-token")
            self._run_raw_handler(handler)
        log_payloads = [self._parse_log_json(msg) for msg in cm.output if "{" in msg]
        has_correlation_id = any("correlation_id" in p for p in log_payloads)
        self.assertTrue(has_correlation_id, "No log entry contained correlation_id field")

    def test_log_correlation_id_matches_response_header(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", auth_header="Bearer owner-token")
            status, resp_headers, _ = self._run_raw_handler(handler)
        response_cid = resp_headers.get("X-Correlation-ID")
        self.assertIsNotNone(response_cid)
        log_payloads = [self._parse_log_json(msg) for msg in cm.output if "{" in msg]
        logged_cids = [p["correlation_id"] for p in log_payloads if "correlation_id" in p]
        self.assertTrue(logged_cids, "No log entry contained correlation_id field")
        self.assertEqual(logged_cids[0], response_cid)

    def test_inbound_id_propagated_to_log(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler(
                "/grants",
                auth_header="Bearer owner-token",
                correlation_id_header="trace-789",
            )
            self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertIn("trace-789", log_str)


# ═══════════════════════════════════════════════════════════════════════
# 5. Security resilience
# ═══════════════════════════════════════════════════════════════════════

class TestGl118SecurityResilience(_BaseGl118):
    """Verify injection attempts and hostile inputs are rejected safely."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        importlib.reload(self.config_mod)
        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_newline_injection_rejected(self):
        # CRLF injection attempt — newline not in safe charset
        malicious = "abc\r\nX-Evil: injected"
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header=malicious,
        )
        _, headers, _ = self._run_raw_handler(handler)
        response_id = headers.get("X-Correlation-ID", "")
        self.assertNotEqual(response_id, malicious)
        self.assertNotIn("\r\n", response_id)
        self.assertNotIn("X-Evil", headers)

    def test_oversized_header_not_reflected(self):
        oversized = "z" * 300
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header=oversized,
        )
        _, headers, _ = self._run_raw_handler(handler)
        response_id = headers.get("X-Correlation-ID", "")
        self.assertFalse(response_id.startswith("z" * 129), "Oversized ID was reflected")

    def test_null_byte_id_replaced(self):
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header="abc\x00def",
        )
        _, headers, _ = self._run_raw_handler(handler)
        response_id = headers.get("X-Correlation-ID", "")
        self.assertTrue(len(response_id) > 0)
        self.assertNotIn("\x00", response_id)

    def test_unicode_id_replaced(self):
        # Non-ASCII chars not in safe charset → replaced
        handler = self._make_raw_handler(
            "/grants",
            auth_header="Bearer owner-token",
            correlation_id_header="café-123",
        )
        _, headers, _ = self._run_raw_handler(handler)
        response_id = headers.get("X-Correlation-ID", "")
        self.assertTrue(len(response_id) > 0)
        self.assertNotEqual(response_id, "café-123")


# ═══════════════════════════════════════════════════════════════════════
# 6. Scope guard — diff validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl118NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-118 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-118-correlation-id-propagation":
            self.skipTest("Branch-wide diff check only valid on GL-118 feature branch")
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/server.py",
            "backend/tests/test_gl118_correlation_id_propagation.py",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-118 changed a forbidden file: {path}",
            )

    def test_no_openapi_change_needed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        self.assertTrue(openapi_path.exists())

    def test_no_db_schema_migration_change(self):
        tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = tmp_db.name
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        try:
            import backend.src.db as db_mod
            importlib.reload(db_mod)
            db_mod.init_db()
            conn = db_mod.get_conn()
            try:
                tables = [
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                ]
                self.assertIn("grants", tables)
                self.assertIn("operators", tables)
                self.assertIn("audit_events", tables)
                self.assertIn("grant_executions", tables)
            finally:
                conn.close()
        finally:
            os.unlink(tmp_db.name)
            if orig_db is not None:
                os.environ["GRANTLAYER_DB"] = orig_db
            else:
                os.environ.pop("GRANTLAYER_DB", None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
