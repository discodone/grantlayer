"""Tests for GL-141: Operator Model Default True / Legacy Deprecation.

Ensures:
1. Unset GRANTLAYER_ENABLE_OPERATOR_MODEL defaults to True (operator model on).
2. Explicit true-like values enable operator model.
3. Explicit false-like values disable operator model (deprecated legacy compatibility).
4. Invalid values are handled safely (fail-closed to False).
5. Health endpoint does not expose the operator model config value.
6. Missing token fails closed when operator model is default-on.
7. Invalid token fails closed when operator model is default-on.
8. Valid operator auth succeeds under explicit true; legacy admin succeeds under explicit false.
9. GL-138: exactly one check_admin_token function preserved.
10. GL-140: ThreadingHTTPServer is still the server class.
11. GL-139: _AUDIT_HASH_CHAIN_WRITE_LOCK is still present in audit_log.
12. Scope guard: no forbidden file types changed.
13. Branch scope guard: diff limited to allowed files (skipped on non-GL-141 branches).
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import pathlib
import socketserver
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).with_suffix("").parent.parent.parent


# ══════════════════════════════════════════════════════════════════════
# Shared base: env capture/restore + config reload helper
# ══════════════════════════════════════════════════════════════════════

class _BaseGl141Config(unittest.TestCase):
    """Env capture/restore and config reload for config-only tests."""

    def setUp(self):
        self._orig_enable = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        import src.config as config_mod
        self.config_mod = config_mod

    def tearDown(self):
        if self._orig_enable is None:
            os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        else:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = self._orig_enable
        importlib.reload(self.config_mod)

    def _reload_config(self):
        importlib.reload(self.config_mod)
        return self.config_mod


class _BaseGl141Endpoint(unittest.TestCase):
    """Base for endpoint tests: tempfile DB, handler setup, env restore."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_enable = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        self._orig_admin = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        self._orig_bootstrap = os.environ.get("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN")

        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)

        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        self.db_mod = db_mod

        import src.config as config_mod
        importlib.reload(config_mod)
        self.config_mod = config_mod

        import src.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import src.auth as auth_mod
        importlib.reload(auth_mod)

        import src.server as server_mod
        importlib.reload(server_mod)
        self.handler_class = server_mod.GrantLayerHandler

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in [
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_enable),
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_admin),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require),
            ("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", self._orig_bootstrap),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _insert_operator(self, op_id, name, role, token):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators
                   (id, name, role, token_hash, token_lookup_hash, active, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, datetime('now'))""",
                (
                    op_id, name, role,
                    self.ops_mod.hash_token(token),
                    self.ops_mod.derive_token_lookup_hash(token),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _reload_server(self):
        import src.config as cfg
        importlib.reload(cfg)
        import src.auth as auth
        importlib.reload(auth)
        import src.server as srv
        importlib.reload(srv)
        self.handler_class = srv.GrantLayerHandler

    def _make_handler(self, path, method="GET", auth_header=None, body=b""):
        handler = self.handler_class.__new__(self.handler_class)
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        headers: dict = {}
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
        status = int(response.split(b"\r\n")[0].split(b" ")[1])
        parts = response.split(b"\r\n\r\n", 1)
        body = json.loads(parts[1]) if len(parts) > 1 and parts[1] else {}
        return status, body


# ══════════════════════════════════════════════════════════════════════
# 1. Unset defaults to True
# ══════════════════════════════════════════════════════════════════════

class TestGl141DefaultUnset(_BaseGl141Config):

    def test_unset_defaults_to_true(self):
        os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        cfg = self._reload_config()
        self.assertTrue(
            cfg.ENABLE_OPERATOR_MODEL,
            "Unset GRANTLAYER_ENABLE_OPERATOR_MODEL must default to True (GL-141)",
        )

    def test_empty_string_defaults_to_true(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = ""
        cfg = self._reload_config()
        self.assertTrue(
            cfg.ENABLE_OPERATOR_MODEL,
            "Empty GRANTLAYER_ENABLE_OPERATOR_MODEL must default to True",
        )

    def test_whitespace_only_defaults_to_true(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "   "
        cfg = self._reload_config()
        self.assertTrue(
            cfg.ENABLE_OPERATOR_MODEL,
            "Whitespace-only GRANTLAYER_ENABLE_OPERATOR_MODEL must default to True",
        )


# ══════════════════════════════════════════════════════════════════════
# 2. Explicit true-like values enable operator model
# ══════════════════════════════════════════════════════════════════════

class TestGl141TrueLikeValues(_BaseGl141Config):

    def _assert_enabled(self, value: str):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = value
        cfg = self._reload_config()
        self.assertTrue(
            cfg.ENABLE_OPERATOR_MODEL,
            f"GRANTLAYER_ENABLE_OPERATOR_MODEL={value!r} must enable operator model",
        )

    def test_value_1(self):          self._assert_enabled("1")
    def test_value_true(self):       self._assert_enabled("true")
    def test_value_TRUE(self):       self._assert_enabled("TRUE")
    def test_value_True(self):       self._assert_enabled("True")
    def test_value_yes(self):        self._assert_enabled("yes")
    def test_value_on(self):         self._assert_enabled("on")


# ══════════════════════════════════════════════════════════════════════
# 3. Explicit false-like values disable (deprecated legacy mode)
# ══════════════════════════════════════════════════════════════════════

class TestGl141FalseLikeValues(_BaseGl141Config):

    def _assert_disabled(self, value: str):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = value
        cfg = self._reload_config()
        self.assertFalse(
            cfg.ENABLE_OPERATOR_MODEL,
            f"GRANTLAYER_ENABLE_OPERATOR_MODEL={value!r} must disable operator model",
        )

    def test_value_0(self):          self._assert_disabled("0")
    def test_value_false(self):      self._assert_disabled("false")
    def test_value_FALSE(self):      self._assert_disabled("FALSE")
    def test_value_False(self):      self._assert_disabled("False")
    def test_value_no(self):         self._assert_disabled("no")
    def test_value_off(self):        self._assert_disabled("off")


# ══════════════════════════════════════════════════════════════════════
# 4. Invalid values fail-closed (return False)
# ══════════════════════════════════════════════════════════════════════

class TestGl141InvalidValueFailsClosed(_BaseGl141Config):

    def _assert_fails_closed(self, value: str):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = value
        cfg = self._reload_config()
        self.assertFalse(
            cfg.ENABLE_OPERATOR_MODEL,
            f"Invalid value {value!r} must fail-closed (False), not enable operator model",
        )

    def test_garbage_value(self):    self._assert_fails_closed("garbage")
    def test_maybe_value(self):      self._assert_fails_closed("maybe")
    def test_enabled_word(self):     self._assert_fails_closed("enabled")


# ══════════════════════════════════════════════════════════════════════
# 5. Health/readiness endpoint does not expose operator model config
# ══════════════════════════════════════════════════════════════════════

class TestGl141HealthEndpointSafe(_BaseGl141Endpoint):

    def test_health_returns_200(self):
        handler = self._make_handler("/health")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")

    def test_health_does_not_expose_operator_model_flag(self):
        handler = self._make_handler("/health")
        status, body = self._run_handler(handler)
        body_str = json.dumps(body).lower()
        self.assertNotIn("enable_operator_model", body_str)
        self.assertNotIn("operator_model", body_str)

    def test_readiness_does_not_expose_operator_model_flag(self):
        handler = self._make_handler("/readiness")
        status, body = self._run_handler(handler)
        self.assertIn(status, (200, 503))
        body_str = json.dumps(body).lower()
        self.assertNotIn("enable_operator_model", body_str)


# ══════════════════════════════════════════════════════════════════════
# 6. Missing token fails closed (default-on)
# ══════════════════════════════════════════════════════════════════════

class TestGl141FailClosedMissingToken(_BaseGl141Endpoint):

    def setUp(self):
        super().setUp()
        os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        self._reload_server()

    def test_missing_token_grants_returns_401(self):
        handler = self._make_handler("/grants")
        status, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_missing_token_operators_me_returns_401(self):
        handler = self._make_handler("/operators/me")
        status, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_missing_token_does_not_expose_raw_config(self):
        handler = self._make_handler("/grants")
        _, body = self._run_handler(handler)
        body_str = json.dumps(body).lower()
        self.assertNotIn("enable_operator_model", body_str)
        self.assertNotIn("grantlayer_", body_str)


# ══════════════════════════════════════════════════════════════════════
# 7. Invalid token fails closed (default-on)
# ══════════════════════════════════════════════════════════════════════

class TestGl141FailClosedInvalidToken(_BaseGl141Endpoint):

    def setUp(self):
        super().setUp()
        os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        self._insert_operator("op-1", "Alice", "owner", "real-token-gl141")
        self._reload_server()

    def test_invalid_token_grants_returns_401(self):
        handler = self._make_handler("/grants", auth_header="Bearer totally-wrong-token")
        status, body = self._run_handler(handler)
        self.assertIn(status, (401, 403))
        self.assertIn("errorCode", body)

    def test_invalid_token_does_not_expose_real_token(self):
        handler = self._make_handler("/grants", auth_header="Bearer totally-wrong-token")
        _, body = self._run_handler(handler)
        body_str = json.dumps(body)
        self.assertNotIn("real-token-gl141", body_str)
        self.assertNotIn("totally-wrong-token", body_str)


# ══════════════════════════════════════════════════════════════════════
# 8. Valid behavior preserved under explicit settings
# ══════════════════════════════════════════════════════════════════════

class TestGl141ValidBehaviorPreserved(_BaseGl141Endpoint):

    def test_explicit_true_valid_operator_succeeds(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        self._insert_operator("op-owner", "Owner", "owner", "owner-tok-gl141")
        self._reload_server()
        handler = self._make_handler("/operators/me", auth_header="Bearer owner-tok-gl141")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertEqual(body.get("role"), "owner")

    def test_explicit_false_legacy_admin_succeeds(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-admin-gl141"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        self._reload_server()
        handler = self._make_handler("/grants", auth_header="Bearer legacy-admin-gl141")
        status, body = self._run_handler(handler)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_explicit_true_missing_token_fails_closed(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        self._reload_server()
        handler = self._make_handler("/grants")
        status, _ = self._run_handler(handler)
        self.assertIn(status, (401, 403))

    def test_explicit_false_missing_token_fails_closed(self):
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "legacy-admin-gl141"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        self._reload_server()
        handler = self._make_handler("/grants")
        status, _ = self._run_handler(handler)
        self.assertIn(status, (401, 403))


# ══════════════════════════════════════════════════════════════════════
# 9. GL-138: exactly one check_admin_token preserved
# ══════════════════════════════════════════════════════════════════════

class TestGl141Gl138Preserved(unittest.TestCase):

    def test_exactly_one_check_admin_token_function(self):
        auth_path = _repo_root() / "backend" / "src" / "auth.py"
        source = auth_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        funcs = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "check_admin_token"
        ]
        self.assertEqual(
            len(funcs), 1,
            f"GL-138: expected exactly one check_admin_token, found {len(funcs)}",
        )


# ══════════════════════════════════════════════════════════════════════
# 10. GL-140: ThreadingHTTPServer preserved
# ══════════════════════════════════════════════════════════════════════

class TestGl141Gl140Preserved(unittest.TestCase):

    def _server_source(self):
        return (_repo_root() / "backend" / "src" / "server.py").read_text(encoding="utf-8")

    def test_threading_http_server_in_server_source(self):
        self.assertIn(
            "ThreadingHTTPServer",
            self._server_source(),
            "GL-140: ThreadingHTTPServer must still be present in server.py",
        )

    def test_threading_http_server_stdlib_mixin(self):
        from http.server import ThreadingHTTPServer
        self.assertTrue(
            issubclass(ThreadingHTTPServer, socketserver.ThreadingMixIn),
            "GL-140: ThreadingHTTPServer must subclass socketserver.ThreadingMixIn",
        )


# ══════════════════════════════════════════════════════════════════════
# 11. GL-139: audit hash-chain lock preserved
# ══════════════════════════════════════════════════════════════════════

class TestGl141Gl139Preserved(unittest.TestCase):

    def _audit_source(self):
        return (_repo_root() / "backend" / "src" / "audit_log.py").read_text(encoding="utf-8")

    def test_audit_lock_still_present(self):
        self.assertIn(
            "_AUDIT_HASH_CHAIN_WRITE_LOCK",
            self._audit_source(),
            "GL-139: _AUDIT_HASH_CHAIN_WRITE_LOCK must not be removed by GL-141",
        )

    def test_audit_lock_is_rlock(self):
        self.assertIn(
            "RLock",
            self._audit_source(),
            "GL-139: audit_log.py must still contain an RLock for the hash-chain write lock",
        )


# ══════════════════════════════════════════════════════════════════════
# 12 + 13. Scope guard
# ══════════════════════════════════════════════════════════════════════

class TestGl141ScopeGuard(unittest.TestCase):

    def _current_branch(self):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=_repo_root(), capture_output=True, text=True,
        )
        return result.stdout.strip()

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=_repo_root(), capture_output=True, text=True,
        )
        return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]

    def test_no_openapi_change(self):
        openapi_path = _repo_root() / "docs" / "openapi.yaml"
        self.assertTrue(openapi_path.exists(), "openapi.yaml missing")
        content = openapi_path.read_text()
        self.assertNotIn("gl141", content.lower())
        self.assertNotIn("operator_model_default", content.lower())

    def test_no_new_migration(self):
        migrations_dir = _repo_root() / "backend" / "src" / "migrations"
        scripts = sorted(migrations_dir.glob("0*.py"))
        self.assertEqual(
            len(scripts), 11,
            f"GL-141 must not add migrations (expected 11, got {len(scripts)})",
        )

    def test_no_dependency_files_changed(self):
        if self._current_branch() != "gl-141-operator-model-default":
            self.skipTest("Branch diff check only valid on GL-141 feature branch")
        forbidden = {
            "requirements.txt", "requirements-dev.txt",
            "pyproject.toml", "setup.py", "Pipfile", "poetry.lock",
        }
        for path in self._changed_files():
            self.assertNotIn(path, forbidden, f"GL-141 must not change dependency file: {path}")

    def test_no_frontend_files_changed(self):
        if self._current_branch() != "gl-141-operator-model-default":
            self.skipTest("Branch diff check only valid on GL-141 feature branch")
        for path in self._changed_files():
            self.assertFalse(
                path.startswith("frontend/") or path.startswith("website/"),
                f"GL-141 must not change frontend/website file: {path}",
            )

    def test_git_diff_limited_to_allowed_files(self):
        if self._current_branch() != "gl-141-operator-model-default":
            self.skipTest("Branch diff check only valid on GL-141 feature branch")
        allowed = {
            "backend/src/config.py",
            "backend/tests/test_gl141_operator_model_default.py",
            "backend/tests/test_gl087_auth_error_response_consistency.py",
            "backend/tests/test_gl076_runtime_configuration_enforcement.py",
            "backend/tests/test_gl109_operators_me_authentication.py",
            "backend/tests/test_gl138_check_admin_token_cleanup.py",
            ".env.example",
            "docs/operator_model_default.md",
            "docs/examples/gl141/operator_model_default.json",
            "docs/security_remediation_intake_2026_05_26.md",
        }
        for path in self._changed_files():
            self.assertIn(path, allowed, f"GL-141 changed a forbidden file: {path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
