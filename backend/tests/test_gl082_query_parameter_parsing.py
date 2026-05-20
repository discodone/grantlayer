"""Tests for GL-082 Harden Query Parameter Parsing.

Ensures malformed integer query parameters (e.g. limit) return deterministic,
safe HTTP 400 responses instead of unhandled 500 errors from direct int(...)
parsing.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl082(unittest.TestCase):
    """Shared helpers for GL-082 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()

        import src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import src.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import src.server as server_mod
        importlib.reload(server_mod)
        self.server_mod = server_mod
        self.handler_class = server_mod.GrantLayerHandler
        self._qpe = server_mod._QueryParamError

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _make_handler(self, path, method="GET", auth_header=None, body=b""):
        from io import BytesIO
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if body:
            headers["Content-Length"] = str(len(body))
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
        handler.wfile.seek(0)
        response = handler.wfile.read()
        status_line = response.split(b"\r\n")[0]
        status = int(status_line.split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        body = json.loads(parts[1]) if len(parts) > 1 else {}
        return status, body

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


class TestGl082AuditEvents(_BaseGl082):
    """GET /audit-events query parameter safety."""

    def test_valid_limit_returns_200(self):
        handler = self._make_handler("/audit-events?limit=5")
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)

    def test_missing_limit_uses_default(self):
        handler = self._make_handler("/audit-events")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_limit_abc_returns_400(self):
        handler = self._make_handler("/audit-events?limit=abc")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_limit_negative_returns_400(self):
        handler = self._make_handler("/audit-events?limit=-1")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_limit_zero_returns_400(self):
        handler = self._make_handler("/audit-events?limit=0")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_excessive_limit_returns_400(self):
        handler = self._make_handler("/audit-events?limit=1001")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_invalid_limit_response_no_stacktrace(self):
        handler = self._make_handler("/audit-events?limit=abc")
        _, body = self._run_handler(handler)
        body_str = json.dumps(body)
        self.assertNotIn("traceback", body_str.lower())
        self.assertNotIn("ValueError", body_str)
        self.assertNotIn("exception", body_str.lower())
        # Ensure only safe keys are present
        self.assertIn("error", body)
        self.assertIn("errorCode", body)
        self.assertIn("reason", body)

    def test_limit_at_maximum_returns_200(self):
        handler = self._make_handler("/audit-events?limit=1000")
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)

    def test_limit_determinism_repeated_abc(self):
        handler1 = self._make_handler("/audit-events?limit=abc")
        handler2 = self._make_handler("/audit-events?limit=abc")
        status1, body1 = self._run_handler(handler1)
        status2, body2 = self._run_handler(handler2)
        self.assertEqual(status1, status2)
        self.assertEqual(body1, body2)


class TestGl082GrantExecutions(_BaseGl082):
    """GET /grant-executions query parameter safety."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

    def test_valid_limit_returns_200(self):
        handler = self._make_handler(
            "/grant-executions?limit=5",
            auth_header="Bearer owner-token",
        )
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)

    def test_missing_limit_returns_200(self):
        handler = self._make_handler(
            "/grant-executions",
            auth_header="Bearer owner-token",
        )
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)

    def test_limit_abc_returns_400(self):
        handler = self._make_handler(
            "/grant-executions?limit=abc",
            auth_header="Bearer owner-token",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_limit_negative_returns_400(self):
        handler = self._make_handler(
            "/grant-executions?limit=-1",
            auth_header="Bearer owner-token",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_limit_zero_returns_400(self):
        handler = self._make_handler(
            "/grant-executions?limit=0",
            auth_header="Bearer owner-token",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_excessive_limit_returns_400(self):
        handler = self._make_handler(
            "/grant-executions?limit=10001",
            auth_header="Bearer owner-token",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")


class TestGl082GrantExecutionsForGrant(_BaseGl082):
    """GET /grants/{id}/executions query parameter safety."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        importlib.reload(self.config_mod)
        import src.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth
        self._insert_operator("owner-1", "Owner", "owner", "owner-token")

        import src.grants as grants_mod
        importlib.reload(grants_mod)
        from src.models import Grant
        g = Grant(
            subject_id="s-01",
            role="tech",
            action="restart",
            resource="env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            created_by="admin",
            reason="test",
        )
        self.grant = grants_mod.create_grant(g)

    def test_valid_limit_returns_200(self):
        handler = self._make_handler(
            f"/grants/{self.grant.id}/executions?limit=5",
            auth_header="Bearer owner-token",
        )
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)

    def test_missing_limit_returns_200(self):
        handler = self._make_handler(
            f"/grants/{self.grant.id}/executions",
            auth_header="Bearer owner-token",
        )
        status, _ = self._run_handler(handler)
        self.assertEqual(status, 200)

    def test_limit_abc_returns_400(self):
        handler = self._make_handler(
            f"/grants/{self.grant.id}/executions?limit=abc",
            auth_header="Bearer owner-token",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_limit_negative_returns_400(self):
        handler = self._make_handler(
            f"/grants/{self.grant.id}/executions?limit=-1",
            auth_header="Bearer owner-token",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_limit_zero_returns_400(self):
        handler = self._make_handler(
            f"/grants/{self.grant.id}/executions?limit=0",
            auth_header="Bearer owner-token",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")

    def test_excessive_limit_returns_400(self):
        handler = self._make_handler(
            f"/grants/{self.grant.id}/executions?limit=10001",
            auth_header="Bearer owner-token",
        )
        status, body = self._run_handler(handler)
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "INVALID_QUERY_PARAMETER")


class TestGl082ParserDirectly(_BaseGl082):
    """Direct unit tests for _parse_int_query_param behavior."""

    def test_parser_returns_default_for_missing(self):
        handler = self._make_handler("/audit-events")
        from urllib.parse import parse_qs
        qs = parse_qs("")
        result = handler._parse_int_query_param(qs, "limit", default=200, minimum=1, maximum=1000)
        self.assertEqual(result, 200)

    def test_parser_returns_int_for_valid(self):
        handler = self._make_handler("/audit-events")
        from urllib.parse import parse_qs
        qs = parse_qs("limit=42")
        result = handler._parse_int_query_param(qs, "limit", default=200, minimum=1, maximum=1000)
        self.assertEqual(result, 42)

    def test_parser_raises_for_abc(self):
        handler = self._make_handler("/audit-events")
        from urllib.parse import parse_qs
        qs = parse_qs("limit=abc")
        with self.assertRaises(self._qpe):
            handler._parse_int_query_param(qs, "limit", default=200, minimum=1, maximum=1000)

    def test_parser_raises_for_below_minimum(self):
        handler = self._make_handler("/audit-events")
        from urllib.parse import parse_qs
        qs = parse_qs("limit=0")
        with self.assertRaises(self._qpe):
            handler._parse_int_query_param(qs, "limit", default=200, minimum=1, maximum=1000)

    def test_parser_raises_for_above_maximum(self):
        handler = self._make_handler("/audit-events")
        from urllib.parse import parse_qs
        qs = parse_qs("limit=1001")
        with self.assertRaises(self._qpe):
            handler._parse_int_query_param(qs, "limit", default=200, minimum=1, maximum=1000)

    def test_parser_respects_custom_min_max(self):
        handler = self._make_handler("/audit-events")
        from urllib.parse import parse_qs
        qs = parse_qs("limit=5")
        result = handler._parse_int_query_param(qs, "limit", default=10, minimum=1, maximum=10)
        self.assertEqual(result, 5)


class TestGl082OpenAPIContract(_BaseGl082):
    """Verify OpenAPI contract includes 400 responses and integer types."""

    def _openapi_text(self):
        import pathlib
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        openapi_path = repo_root / "docs" / "openapi.yaml"
        return openapi_path.read_text(encoding="utf-8")

    def test_openapi_includes_400_for_audit_events(self):
        text = self._openapi_text()
        section = text[text.find("/audit-events:"):text.find("/evidence/")]
        self.assertIn('"400"', section)

    def test_openapi_includes_400_for_grant_executions(self):
        text = self._openapi_text()
        section = text[text.find("/grant-executions:"):text.find("/grant-executions/{id}:")]
        self.assertIn('"400"', section)

    def test_openapi_includes_400_for_grant_executions_for_grant(self):
        text = self._openapi_text()
        section = text[text.find("/grants/{id}/executions:"):text.find("/evidence/")]
        self.assertIn('"400"', section)

    def test_openapi_documents_limit_as_integer(self):
        text = self._openapi_text()
        matches = re.findall(r"name:\s*limit[\s\S]*?schema:\s*\{\s*type:\s*integer", text)
        self.assertGreaterEqual(len(matches), 1)


class TestGl082NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-082 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-082-harden-query-parameter-parsing":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-082 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/server.py",
            "backend/tests/test_gl082_query_parameter_parsing.py",
            "docs/openapi.yaml",
            "docs/product_foundation_implementation_cut.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-082 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
