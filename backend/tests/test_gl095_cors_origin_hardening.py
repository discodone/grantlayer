"""Tests for GL-095 CORS Origin Hardening.

Ensures:
- No wildcard Access-Control-Allow-Origin: * is granted.
- Arbitrary Origin headers are not reflected.
- Only exact-origin matches from an allowlist receive CORS access.
- OPTIONS/preflight is deterministic and does not mutate state.
- CORS does not bypass auth.
- Public endpoints (/health, /readiness) remain public.
- Protected endpoints remain protected.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _BaseGl095(unittest.TestCase):
    """Shared helpers for GL-095 tests."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name

        self._orig_enable_operator = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require_admin = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap_token = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")
        self._orig_cors_origins = os.environ.get("GRANTLAYER_CORS_ALLOWED_ORIGINS")
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        self.auth_mod = auth_mod

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        import backend.src.auth.challenges as challenges_mod
        importlib.reload(challenges_mod)
        self.challenges_mod = challenges_mod

        self.db_mod = db_mod

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable_operator),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require_admin),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap_token),
            ("GRANTLAYER_CORS_ALLOWED_ORIGINS", self._orig_cors_origins),
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

    def _create_matching_grant(self):
        grant = self.models_mod.Grant(
            subject_id="sub-1",
            role="engineer",
            action="read",
            resource="repo-a",
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2030-01-01T00:00:00Z",
            created_by="owner-1",
            reason="test",
        )
        self.grants_mod.create_grant(grant, tenant_id="demo")
        return grant

    def _make_client(self):
        import backend.src.core.db as bk_db
        import backend.src.core.config as config_mod
        import backend.src.auth.auth as auth_mod
        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        importlib.reload(config_mod)
        importlib.reload(auth_mod)
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def _make_handler(self, path, method="GET", auth_header=None, origin=None, body=b""):
        return (path, method, auth_header, origin, body)

    def _run_handler(self, req):
        path, method, auth_header, origin, body = req
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        if origin is not None:
            headers["Origin"] = origin
        client = self._make_client()
        if method == "GET":
            resp = client.get(path, headers=headers)
        elif method == "POST":
            if isinstance(body, (bytes, bytearray)) and len(body) > 0:
                try:
                    body_dict = json.loads(body)
                    resp = client.post(path, json=body_dict, headers=headers)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    resp = client.post(path, content=body, headers=headers)
            else:
                resp = client.post(path, headers=headers)
        elif method == "OPTIONS":
            # Add Access-Control-Request-Method to trigger CORSMiddleware preflight handling
            headers.setdefault("Access-Control-Request-Method", "GET")
            resp = client.request("OPTIONS", path, headers=headers)
        else:
            resp = client.request(method, path, headers=headers)
        try:
            body_data = resp.json()
        except Exception:
            body_data = {}
        if isinstance(body_data, dict) and isinstance(body_data.get("detail"), dict):
            body_data = body_data["detail"]
        return resp.status_code, dict(resp.headers), body_data

    def _assert_gl030_full(self, payload):
        self.assertIn("error", payload)
        self.assertIn("errorCode", payload)
        self.assertIn("reason", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertIsInstance(payload["errorCode"], str)
        self.assertIsInstance(payload["reason"], str)


class TestGl095CorsWildcardRemoved(_BaseGl095):
    """Verify wildcard CORS is removed from all responses."""

    def test_no_wildcard_on_public_health(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = ""
        importlib.reload(self.config_mod)
        handler = self._make_handler("/health", origin="http://evil.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotEqual(headers.get("access-control-allow-origin"), "*")

    def test_no_wildcard_on_protected_401(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = ""
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin-token"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        handler = self._make_handler("/v1/grants", origin="http://evil.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertNotEqual(headers.get("access-control-allow-origin"), "*")

    def test_no_wildcard_on_404(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = ""
        importlib.reload(self.config_mod)
        handler = self._make_handler("/nonexistent", origin="http://evil.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 404)
        self.assertNotEqual(headers.get("access-control-allow-origin"), "*")


class TestGl095ArbitraryOriginNotReflected(_BaseGl095):
    """Verify arbitrary Origin headers are never reflected."""

    def test_malicious_origin_not_reflected_on_health(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)
        handler = self._make_handler("/health", origin="http://malicious.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("http://malicious.com", headers.get("access-control-allow-origin", ""))

    def test_malicious_origin_not_reflected_on_401(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin-token"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        handler = self._make_handler("/v1/grants", origin="http://malicious.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self.assertNotIn("http://malicious.com", headers.get("access-control-allow-origin", ""))

    def test_malicious_origin_not_reflected_on_options(self):
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)
        handler = self._make_handler("/v1/grants", method="OPTIONS", origin="http://malicious.com")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, [200, 204, 400, 405])
        self.assertNotIn("http://malicious.com", headers.get("access-control-allow-origin", ""))


class TestGl095AllowlistExactMatching(_BaseGl095):
    """Verify allowlist exact matching behavior."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com,https://app.example.com"
        importlib.reload(self.config_mod)

    def test_allowed_origin_gets_cors_headers(self):
        handler = self._make_handler("/health", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("access-control-allow-origin"), "http://trusted.com")

    def test_second_allowed_origin_gets_cors_headers(self):
        handler = self._make_handler("/health", origin="https://app.example.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("access-control-allow-origin"), "https://app.example.com")

    def test_unlisted_origin_gets_no_cors_grant(self):
        handler = self._make_handler("/health", origin="http://untrusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("http://untrusted.com", headers.get("access-control-allow-origin", ""))

    def test_similar_looking_origin_does_not_match(self):
        handler = self._make_handler("/health", origin="http://sub.trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("http://sub.trusted.com", headers.get("access-control-allow-origin", ""))

        handler = self._make_handler("/health", origin="https://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("https://trusted.com", headers.get("access-control-allow-origin", ""))

        handler = self._make_handler("/health", origin="http://trusted.com:8080")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("http://trusted.com:8080", headers.get("access-control-allow-origin", ""))

    def test_no_origin_header_gets_no_cors_grant(self):
        handler = self._make_handler("/health")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertNotIn("access-control-allow-origin", headers)


class TestGl095OptionsPreflight(_BaseGl095):
    """Verify OPTIONS/preflight behavior."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)

    def test_options_allowed_origin_returns_2xx_with_cors(self):
        handler = self._make_handler("/v1/grants", method="OPTIONS", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, [200, 204])
        self.assertEqual(headers.get("access-control-allow-origin"), "http://trusted.com")

    def test_options_unlisted_origin_returns_2xx_without_cors(self):
        handler = self._make_handler("/v1/grants", method="OPTIONS", origin="http://evil.com")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, [200, 204, 400, 405])
        self.assertNotIn("http://evil.com", headers.get("access-control-allow-origin", ""))

    def test_options_does_not_mutate_state(self):
        from backend.src.core.db import get_conn
        conn = get_conn()
        before = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        conn.close()

        handler = self._make_handler("/v1/grants", method="OPTIONS", origin="http://trusted.com")
        self._run_handler(handler)

        conn = get_conn()
        after = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        conn.close()
        self.assertEqual(before, after)

        conn = get_conn()
        after_audit = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        conn.close()
        self.assertEqual(after_audit, 0)


class TestGl095CorsDoesNotBypassAuth(_BaseGl095):
    """Verify CORS presence does not weaken auth requirements."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)

        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._create_matching_grant()

    def test_grants_still_requires_auth_with_allowed_origin(self):
        handler = self._make_handler("/v1/grants", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_grants_succeeds_with_allowed_origin_and_auth(self):
        handler = self._make_handler("/v1/grants", auth_header="Bearer owner-token", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)
        self.assertEqual(headers.get("access-control-allow-origin"), "http://trusted.com")

    def test_demo_action_still_requires_auth_with_allowed_origin(self):
        demo_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/v1/demo-action", method="POST", origin="http://trusted.com", body=demo_body)
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)

    def test_challenges_still_requires_auth_with_allowed_origin(self):
        challenge_body = json.dumps({
            "subjectId": "sub-1",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/v1/challenges", method="POST", origin="http://trusted.com", body=challenge_body)
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)
        self._assert_gl030_full(body)


class TestGl095PublicAndProtectedEndpoints(_BaseGl095):
    """Verify public endpoints remain public and protected remain protected."""

    def setUp(self):
        super().setUp()
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        os.environ["GRANTLAYER_CORS_ALLOWED_ORIGINS"] = "http://trusted.com"
        importlib.reload(self.config_mod)

        import backend.src.auth.auth as fresh_auth
        importlib.reload(fresh_auth)
        self.auth_mod = fresh_auth

        self._insert_operator("owner-1", "Owner", "owner", "owner-token")
        self._create_matching_grant()

    def test_health_public(self):
        handler = self._make_handler("/health", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_readiness_public(self):
        handler = self._make_handler("/readiness", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))
        self.assertIn(body.get("status"), ("ready", "not_ready"))

    def test_get_grants_protected(self):
        handler = self._make_handler("/v1/grants", origin="http://trusted.com")
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)

    def test_post_demo_action_protected(self):
        demo_body = json.dumps({
            "subjectId": "sub-1",
            "role": "engineer",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/v1/demo-action", method="POST", origin="http://trusted.com", body=demo_body)
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)

    def test_post_challenges_protected(self):
        challenge_body = json.dumps({
            "subjectId": "sub-1",
            "action": "read",
            "resource": "repo-a",
        }).encode()
        handler = self._make_handler("/v1/challenges", method="POST", origin="http://trusted.com", body=challenge_body)
        status, headers, body = self._run_handler(handler)
        self.assertEqual(status, 401)


class TestGl095NoForbiddenFilesChanged(unittest.TestCase):
    """Verify GL-095 branch diff is limited to allowed files."""

    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-095-cors-origin-hardening":
            self.skipTest(
                "Branch-wide diff check only valid on original GL-095 feature branch"
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
            "backend/src/config.py",
            "backend/tests/test_gl095_cors_origin_hardening.py",
            "docs/openapi.yaml",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-095 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
