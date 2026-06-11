"""Tests for GL-125: Operational Smoke Test Bundle.

Compact, fast, deterministic smoke tests for quick post-deployment or
pre-release validation. Covers representative operational, auth, payload
validation, correlation, and logging-safety checks without duplicating
exhaustive GL-117/118/120/124 suites.

No production code changes required.
No external services required.
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


class _BaseGl125(unittest.TestCase):
    """Shared helpers for GL-125 smoke tests."""

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

        import backend.src.db as db_mod
        importlib.reload(db_mod)
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

    def _make_handler(
        self,
        path,
        method="GET",
        auth_header=None,
        body=b"",
        content_length=None,
        correlation_id_header=None,
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
        handler.headers = headers
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = ("127.0.0.1", 0)
        handler.server = None
        return handler

    def _run_handler(self, handler):
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


# ═══════════════════════════════════════════════════════════════════════
# 1. Health / Readiness smoke
# ═══════════════════════════════════════════════════════════════════════

class TestGl125HealthReadiness(_BaseGl125):
    """Verify public health/readiness endpoints are safe and accessible."""

    def test_health_is_public_and_ok(self):
        handler = self._make_handler("/health")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("checkType"), "liveness")

    def test_health_does_not_expose_secrets(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "super-secret-admin-token"
        importlib.reload(self.config_mod)
        handler = self._make_handler("/health")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        body_str = json.dumps(body)
        self.assertNotIn("super-secret-admin-token", body_str)
        self.assertNotIn("GRANTLAYER_ADMIN_TOKEN", body_str)

    def test_readiness_is_public_and_returns_ready_or_not_ready(self):
        handler = self._make_handler("/readiness")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))
        self.assertIn(body.get("status"), ("ready", "not_ready"))
        self.assertEqual(body.get("checkType"), "readiness")


# ═══════════════════════════════════════════════════════════════════════
# 2. Auth boundary smoke
# ═══════════════════════════════════════════════════════════════════════

class TestGl125AuthBoundary(_BaseGl125):
    """Verify protected endpoints reject missing/invalid tokens."""

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

    def test_missing_token_rejected_401(self):
        handler = self._make_handler("/grants")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertIn("errorCode", body)

    def test_invalid_token_rejected(self):
        handler = self._make_handler("/grants", auth_header="Bearer wrong-token")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_authorized_request_succeeds(self):
        handler = self._make_handler("/grants", auth_header="Bearer owner-token")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_multiple_endpoints_require_auth(self):
        endpoints = ["/grants", "/audit-events", "/grant-requests"]
        for endpoint in endpoints:
            handler = self._make_handler(endpoint)
            status, _, _ = self._run_handler(handler)
            self.assertIn(
                status,
                (401, 403),
                f"Endpoint {endpoint} should require auth",
            )


# ═══════════════════════════════════════════════════════════════════════
# 3. Payload validation smoke (GL-124 behavior)
# ═══════════════════════════════════════════════════════════════════════

class TestGl125PayloadValidation(_BaseGl125):
    """Verify representative payload validation safety from GL-124."""

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

    def test_invalid_json_rejected_400(self):
        handler = self._make_handler(
            "/grants", method="POST",
            auth_header="Bearer owner-token", body=b"not json",
        )
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json")

    def test_top_level_array_rejected(self):
        body = json.dumps([{"key": "val"}]).encode()
        handler = self._make_handler(
            "/grants", method="POST",
            auth_header="Bearer owner-token", body=body,
        )
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json_object")

    def test_oversized_body_rejected_413(self):
        handler = self._make_handler(
            "/grants", method="POST",
            auth_header="Bearer owner-token",
            content_length=self.MAX_JSON_BODY_BYTES + 1,
        )
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 413)
        self.assertEqual(body.get("errorCode"), "payload_too_large")

    def test_invalid_payload_not_echoed(self):
        sentinel = "RAW-PAYLOAD-SENTINEL-GL125"
        handler = self._make_handler(
            "/grants", method="POST",
            auth_header="Bearer owner-token", body=sentinel.encode(),
        )
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertNotIn(sentinel, json.dumps(body))


# ═══════════════════════════════════════════════════════════════════════
# 4. Correlation ID smoke (GL-118)
# ═══════════════════════════════════════════════════════════════════════

class TestGl125CorrelationId(_BaseGl125):
    """Verify correlation ID propagation in representative requests."""

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

    def test_correlation_id_preserved_in_successful_response(self):
        handler = self._make_handler(
            "/grants", auth_header="Bearer owner-token",
            correlation_id_header="smoke-cid-ok",
        )
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Correlation-ID"), "smoke-cid-ok")

    def test_correlation_id_preserved_in_rejection_response(self):
        handler = self._make_handler(
            "/grants", method="POST",
            auth_header="Bearer owner-token", body=b"bad json",
            correlation_id_header="smoke-cid-reject",
        )
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(headers.get("X-Correlation-ID"), "smoke-cid-reject")

    def test_rejection_log_includes_correlation_id(self):
        logger = logging.getLogger("grantlayer.server")
        handler = self._make_handler(
            "/grants", method="POST",
            auth_header="Bearer owner-token", body=b"bad json",
            correlation_id_header="smoke-cid-log",
        )
        with self.assertLogs(logger, level="INFO") as cm:
            self._run_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertIn("smoke-cid-log", log_str)


# ═══════════════════════════════════════════════════════════════════════
# 5. Logging safety smoke (GL-117 / GL-120)
# ═══════════════════════════════════════════════════════════════════════

class TestGl125LoggingSafety(_BaseGl125):
    """Verify logs do not leak auth tokens, headers, or request bodies."""

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

    def test_logs_do_not_contain_raw_token(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_handler(
                "/grants", auth_header="Bearer secret-token-abc-123",
            )
            self._run_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("secret-token-abc-123", log_str)

    def test_logs_do_not_contain_authorization_header(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_handler(
                "/grants", auth_header="Bearer secret-token-abc-123",
            )
            self._run_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("authorization", log_str.lower())

    def test_logs_do_not_contain_raw_request_body(self):
        logger = logging.getLogger("grantlayer.server")
        sentinel = "SENSITIVE-BODY-DATA-GL125"
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_handler(
                "/grants", method="POST",
                auth_header="Bearer owner-token", body=sentinel.encode(),
            )
            self._run_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn(sentinel, log_str)

    def test_auth_failed_event_has_correlation_id(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_handler("/grants")
            self._run_handler(handler)
        payload = self._parse_log_json(
            next(msg for msg in cm.output if "auth_failed" in msg)
        )
        self.assertIn("correlation_id", payload)
        self.assertIsNotNone(payload["correlation_id"])
        self.assertGreater(len(payload["correlation_id"]), 0)


# ═══════════════════════════════════════════════════════════════════════
# 6. Scope guard
# ═══════════════════════════════════════════════════════════════════════

class TestGl125ScopeChecks(unittest.TestCase):
    """Verify no forbidden files were changed by GL-125."""

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        return result.stdout.strip()

    def test_no_production_code_changed(self):
        changed = self._changed_files()
        for line in changed.splitlines():
            if line.startswith("backend/src/"):
                self.fail(f"GL-125 changed production code: {line}")

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
    unittest.main(verbosity=2)
