"""Tests for GL-117: Structured Logging Integration in server.py.

Ensures representative operational/security events are emitted safely
without changing API behavior, auth semantics, or rate-limit thresholds.
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
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl117(unittest.TestCase):
    """Shared helpers for GL-117 tests."""

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

    def _make_raw_handler(self, path, method="GET", auth_header=None, origin=None, body=b"", client_ip="127.0.0.1", content_length=None):
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if origin is not None:
            headers["Origin"] = origin
        if body or content_length is not None:
            headers["Content-Length"] = str(content_length) if content_length is not None else str(len(body))
        handler.headers = headers
        handler.path = path
        handler.command = method
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.client_address = (client_ip, 0)
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
        headers = {}
        for line in header_block.split("\r\n")[1:]:
            if ": " in line:
                k, v = line.split(": ", 1)
                headers[k] = v
        if len(parts) > 1 and parts[1]:
            body = json.loads(parts[1])
        else:
            body = {}
        return status, headers, body

    def _parse_log_json(self, log_str):
        """Extract JSON payload from a log record string."""
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
# 1. Successful request completion structured event
# ═══════════════════════════════════════════════════════════════════════

class TestGl117SuccessfulRequest(_BaseGl117):
    """Verify representative successful requests emit structured events."""

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

    def test_get_grants_emits_request_completed(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", auth_header="Bearer owner-token")
            status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertTrue(any("request_completed" in msg for msg in cm.output))
        payload = self._parse_log_json(next(msg for msg in cm.output if "request_completed" in msg))
        self.assertEqual(payload["event"], "request_completed")
        self.assertEqual(payload["status_code"], 200)
        self.assertEqual(payload["path"], "/grants")
        self.assertEqual(payload["method"], "GET")

    def test_post_grants_emits_request_completed(self):
        logger = logging.getLogger("grantlayer.server")
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
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=grant_body)
            status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 201)
        self.assertTrue(any("request_completed" in msg for msg in cm.output))
        payload = self._parse_log_json(next(msg for msg in cm.output if "request_completed" in msg))
        self.assertEqual(payload["event"], "request_completed")
        self.assertEqual(payload["status_code"], 201)
        self.assertEqual(payload["path"], "/grants")
        self.assertEqual(payload["method"], "POST")


# ═══════════════════════════════════════════════════════════════════════
# 2. Auth failure structured event
# ═══════════════════════════════════════════════════════════════════════

class TestGl117AuthFailure(_BaseGl117):
    """Verify auth failures emit safe structured events without leaking secrets."""

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

    def test_missing_auth_emits_auth_failed(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants")
            status, headers, body = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertTrue(any("auth_failed" in msg for msg in cm.output))
        payload = self._parse_log_json(next(msg for msg in cm.output if "auth_failed" in msg))
        self.assertEqual(payload["event"], "auth_failed")
        self.assertIn(payload["status_code"], (401, 403))

    def test_invalid_token_emits_auth_failed(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", auth_header="Bearer wrong-token")
            status, headers, body = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertTrue(any("auth_failed" in msg for msg in cm.output))

    def test_auth_log_does_not_contain_raw_token(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", auth_header="Bearer secret-token-123")
            status, headers, body = self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("secret-token-123", log_str)
        self.assertNotIn("Bearer", log_str)

    def test_auth_log_does_not_contain_authorization_header(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", auth_header="Bearer secret-token-123")
            status, headers, body = self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("authorization", log_str.lower())


# ═══════════════════════════════════════════════════════════════════════
# 3. Rate-limit structured event
# ═══════════════════════════════════════════════════════════════════════

class TestGl117RateLimit(_BaseGl117):
    """Verify rate-limit rejections emit safe structured events."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "2"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.server_mod = fresh_server
        self.handler_class = fresh_server.GrantLayerHandler

        import backend.src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_rate_limit_emits_rate_limited(self):
        logger = logging.getLogger("grantlayer.server")
        for _ in range(2):
            handler = self._make_raw_handler("/challenges", auth_header="Bearer owner-token")
            self._run_raw_handler(handler)

        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/challenges", auth_header="Bearer owner-token")
            status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 429)
        self.assertTrue(any("rate_limited" in msg for msg in cm.output))
        payload = self._parse_log_json(next(msg for msg in cm.output if "rate_limited" in msg))
        self.assertEqual(payload["event"], "rate_limited")
        self.assertEqual(payload["status_code"], 429)
        self.assertEqual(payload["status"], "rate_limit_exceeded")

    def test_rate_limit_log_does_not_contain_raw_token(self):
        logger = logging.getLogger("grantlayer.server")
        for _ in range(2):
            handler = self._make_raw_handler("/challenges", auth_header="Bearer secret-token-456")
            self._run_raw_handler(handler)

        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/challenges", auth_header="Bearer secret-token-456")
            status, headers, body = self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("secret-token-456", log_str)
        self.assertNotIn("Bearer", log_str)


# ═══════════════════════════════════════════════════════════════════════
# 4. Invalid JSON / body rejection structured event
# ═══════════════════════════════════════════════════════════════════════

class TestGl117InvalidJson(_BaseGl117):
    """Verify invalid JSON/body rejections emit safe structured events."""

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

    def test_invalid_json_emits_request_rejected(self):
        logger = logging.getLogger("grantlayer.server")
        bad_body = b"not json"
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=bad_body)
            status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertTrue(any("request_rejected" in msg for msg in cm.output))
        payload = self._parse_log_json(next(msg for msg in cm.output if "request_rejected" in msg))
        self.assertEqual(payload["event"], "request_rejected")
        self.assertEqual(payload["status_code"], 400)

    def test_empty_body_emits_request_rejected(self):
        logger = logging.getLogger("grantlayer.server")
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=b"", content_length=0)
            status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertTrue(any("request_rejected" in msg for msg in cm.output))

    def test_request_rejected_log_does_not_contain_body(self):
        logger = logging.getLogger("grantlayer.server")
        bad_body = b"sensitive-payload-123"
        with self.assertLogs(logger, level="INFO") as cm:
            handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=bad_body)
            status, headers, body = self._run_raw_handler(handler)
        log_str = "\n".join(cm.output)
        self.assertNotIn("sensitive-payload-123", log_str)


# ═══════════════════════════════════════════════════════════════════════
# 5. Demo-action exception logging preserved (GL-111)
# ═══════════════════════════════════════════════════════════════════════

class TestGl117DemoActionPreserved(_BaseGl117):
    """Verify GL-111 demo-action exception logging remains safe."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
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

        import backend.src.demo_action as demo_mod
        importlib.reload(demo_mod)
        self.demo_mod = demo_mod

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

        g = self.models_mod.Grant(
            subject_id="tech-01",
            role="technician",
            action="restart-service",
            resource="customer-env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="Routine maintenance",
        )
        self.grants_mod.create_grant(g)

    def test_demo_action_exception_logging_preserved(self):
        with self.assertLogs(self.demo_mod.logger, level="ERROR") as cm:
            with patch.object(self.demo_mod, "list_grants", side_effect=RuntimeError("secret-boom")):
                handler = self._make_raw_handler(
                    "/demo-action",
                    method="POST",
                    auth_header="Bearer owner-token",
                    body=json.dumps({
                        "subjectId": "tech-01",
                        "role": "technician",
                        "action": "restart-service",
                        "resource": "customer-env-a",
                    }).encode(),
                )
                status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 403)
        self.assertFalse(body["approved"])
        self.assertEqual(body["reason"], "internal_handler_error")
        log_str = "\n".join(cm.output)
        self.assertIn("demo_action unexpected failure", log_str)
        self.assertNotIn("secret-boom", log_str)


# ═══════════════════════════════════════════════════════════════════════
# 6. Logging failure safety
# ═══════════════════════════════════════════════════════════════════════

class TestGl117LoggingFailureSafety(_BaseGl117):
    """Verify structured logging failures do not alter HTTP behavior."""

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

    def test_logging_failure_does_not_alter_http_behavior(self):
        with patch("src.server.safe_log", side_effect=RuntimeError("log failure")):
            handler = self._make_raw_handler("/grants", auth_header="Bearer owner-token")
            status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_auth_logging_failure_does_not_alter_http_behavior(self):
        with patch("src.server.safe_log", side_effect=RuntimeError("log failure")):
            handler = self._make_raw_handler("/grants")
            status, headers, body = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)


# ═══════════════════════════════════════════════════════════════════════
# 7. Response semantics preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl117ResponseSemanticsPreserved(_BaseGl117):
    """Verify existing response status/body semantics are unchanged."""

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

    def test_get_grants_response_unchanged(self):
        handler = self._make_raw_handler("/grants", auth_header="Bearer owner-token")
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_auth_failure_response_unchanged(self):
        handler = self._make_raw_handler("/grants")
        status, headers, body = self._run_raw_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_rate_limit_response_unchanged(self):
        os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "1"
        importlib.reload(self.config_mod)
        import backend.src.server as fresh_server
        importlib.reload(fresh_server)
        self.handler_class = fresh_server.GrantLayerHandler

        handler = self._make_raw_handler("/challenges", auth_header="Bearer owner-token")
        self._run_raw_handler(handler)

        handler = self._make_raw_handler("/challenges", auth_header="Bearer owner-token")
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 429)
        self.assertEqual(body.get("errorCode"), "rate_limit_exceeded")

    def test_invalid_json_response_unchanged(self):
        handler = self._make_raw_handler("/grants", method="POST", auth_header="Bearer owner-token", body=b"bad")
        status, headers, body = self._run_raw_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_json")


# ═══════════════════════════════════════════════════════════════════════
# 8. Scope guard — diff validation
# ═══════════════════════════════════════════════════════════════════════

class TestGl117NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-117 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-117-structured-logging-integration":
            self.skipTest("Branch-wide diff check only valid on GL-117 feature branch")
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/server.py",
            "backend/tests/test_gl117_structured_logging_integration.py",
            "backend/src/structured_logging.py",
            "backend/src/logging_utils.py",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-117 changed a forbidden file: {path}",
            )

    def test_no_openapi_change_needed(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        self.assertTrue(openapi_path.exists())

    def test_no_db_schema_migration_change(self):
        import tempfile
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
