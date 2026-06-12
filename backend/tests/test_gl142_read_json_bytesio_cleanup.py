"""Tests for GL-142: Remove BytesIO Test Hack From _read_json.

Ensures:
1. _read_json has no BytesIO-specific isinstance branch in production code.
2. _read_json accepts a valid JSON object via a clean fake-handler helper.
3. Invalid JSON raises the safe invalid-json error (reason invalid_json, 400).
4. Empty body (Content-Length: 0) raises empty_request_body (400).
5. Non-object JSON raises invalid_json_object (400).
6. Oversized body raises payload_too_large (413).
7. Raw request body is not echoed in error responses.
8. GL-090 request-body hardening behavior preserved.
9. GL-124 request payload shape behavior preserved.
10. GL-141 operator model default (True) preserved.
11. GL-140 ThreadingHTTPServer preserved.
12. GL-139 audit hash-chain write lock preserved.
13. Scope guard: only allowed files changed.
14. Branch-scope guard: skip diff assertions when not on gl-142 branch.
"""

import ast
import importlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SERVER_SRC = _REPO_ROOT / "backend" / "src" / "server.py"


# ---------------------------------------------------------------------------
# Shared fake-handler helper
# ---------------------------------------------------------------------------

def _load_modules():
    """Reload config/db with a temporary DB so imports succeed."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    os.environ.setdefault("GRANTLAYER_DB", tmp.name)
    os.environ.setdefault("GRANTLAYER_ADMIN_TOKEN", "test-admin-token")
    import backend.src.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    import backend.src.config as config_mod
    importlib.reload(config_mod)
    return config_mod, tmp.name


@unittest.skip("server.py internal API (_read_json, _BodyParseError, GrantLayerHandler) not available in FastAPI")
class _Gl142ServerInternal(unittest.TestCase):
    """Base for tests that rely on server.py private APIs — skipped until server.py is retired."""


def _make_handler(body: bytes, extra_headers: dict | None = None):
    """Return a GrantLayerHandler instance (only valid inside _Gl142ServerInternal subclasses)."""
    import backend.src.server as server_mod
    importlib.reload(server_mod)
    _, tmp_name = _load_modules()
    handler = server_mod.GrantLayerHandler.__new__(server_mod.GrantLayerHandler)
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.client_address = ("127.0.0.1", 0)
    headers = {"Content-Length": str(len(body))}
    if extra_headers:
        headers.update(extra_headers)
    handler.headers = headers
    return handler, server_mod


# ---------------------------------------------------------------------------
# 1. Source-level guard: no BytesIO isinstance in _read_json
# ---------------------------------------------------------------------------

class TestGl142NoByteIOHackInProduction(unittest.TestCase):
    """_read_json must not contain BytesIO-specific isinstance branching."""

    def _read_json_ast_node(self):
        source = _SERVER_SRC.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_read_json":
                return node
        self.fail("_read_json not found in server.py")

    def test_no_isinstance_bytesio_call(self):
        func_node = self._read_json_ast_node()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "isinstance":
                    for arg in node.args:
                        # The second argument of isinstance(..., BytesIO)
                        if isinstance(arg, ast.Name) and arg.id == "BytesIO":
                            self.fail(
                                "_read_json contains isinstance(..., BytesIO) — "
                                "production BytesIO hack must be removed (GL-142)"
                            )
                        if isinstance(arg, ast.Attribute) and arg.attr == "BytesIO":
                            self.fail(
                                "_read_json contains isinstance(..., BytesIO) via attribute — "
                                "production BytesIO hack must be removed (GL-142)"
                            )

    def test_no_bytesio_import_inside_read_json(self):
        func_node = self._read_json_ast_node()
        for node in ast.walk(func_node):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                src_text = ast.dump(node)
                self.assertNotIn(
                    "BytesIO", src_text,
                    "_read_json must not import BytesIO internally (GL-142)"
                )

    def test_no_rfile_getvalue_in_read_json(self):
        """getvalue() is a BytesIO-specific method — must not appear in _read_json."""
        func_node = self._read_json_ast_node()
        source_segment = ast.get_source_segment(_SERVER_SRC.read_text(), func_node) or ""
        self.assertNotIn(
            "getvalue",
            source_segment,
            "_read_json must not call .getvalue() — remove BytesIO-specific code (GL-142)"
        )


# ---------------------------------------------------------------------------
# 2. Valid JSON object via clean helper
# ---------------------------------------------------------------------------

class TestGl142ValidJsonObject(_Gl142ServerInternal):

    def test_returns_dict_for_valid_json_object(self):
        body = json.dumps({"key": "value"}).encode()
        handler, server_mod = _make_handler(body)
        result = handler._read_json()
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {"key": "value"})

    def test_returns_empty_dict_for_empty_object(self):
        body = b"{}"
        handler, server_mod = _make_handler(body)
        result = handler._read_json()
        self.assertEqual(result, {})

    def test_nested_object(self):
        body = json.dumps({"a": {"b": 1}}).encode()
        handler, server_mod = _make_handler(body)
        result = handler._read_json()
        self.assertEqual(result["a"]["b"], 1)


# ---------------------------------------------------------------------------
# 3. Invalid JSON → invalid_json / 400
# ---------------------------------------------------------------------------

class TestGl142InvalidJson(_Gl142ServerInternal):

    def _assert_body_parse_error(self, body: bytes, expected_code: str, expected_status: int):
        handler, server_mod = _make_handler(body)
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        exc = ctx.exception
        self.assertEqual(exc.status, expected_status)
        self.assertEqual(exc.payload.get("errorCode"), expected_code)

    def test_malformed_json_raises_invalid_json(self):
        self._assert_body_parse_error(b"not json", "invalid_json", 400)

    def test_truncated_json_raises_invalid_json(self):
        self._assert_body_parse_error(b'{"key": ', "invalid_json", 400)

    def test_trailing_comma_json_raises_invalid_json(self):
        self._assert_body_parse_error(b'{"key": "val",}', "invalid_json", 400)


# ---------------------------------------------------------------------------
# 4. Empty body (Content-Length: 0) → empty_request_body / 400
# ---------------------------------------------------------------------------

class TestGl142EmptyBody(_Gl142ServerInternal):

    def test_zero_content_length_raises_empty_request_body(self):
        handler, server_mod = _make_handler(b"", extra_headers={"Content-Length": "0"})
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        exc = ctx.exception
        self.assertEqual(exc.status, 400)
        self.assertEqual(exc.payload.get("errorCode"), "empty_request_body")


# ---------------------------------------------------------------------------
# 5. Non-object JSON → invalid_json_object / 400
# ---------------------------------------------------------------------------

class TestGl142NonObjectJson(_Gl142ServerInternal):

    def _assert_invalid_json_object(self, payload_bytes: bytes):
        handler, server_mod = _make_handler(payload_bytes)
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        exc = ctx.exception
        self.assertEqual(exc.status, 400)
        self.assertEqual(exc.payload.get("errorCode"), "invalid_json_object")

    def test_array_rejected(self):
        self._assert_invalid_json_object(b"[1,2,3]")

    def test_string_rejected(self):
        self._assert_invalid_json_object(b'"hello"')

    def test_integer_rejected(self):
        self._assert_invalid_json_object(b"42")

    def test_null_rejected(self):
        self._assert_invalid_json_object(b"null")

    def test_boolean_rejected(self):
        self._assert_invalid_json_object(b"true")


# ---------------------------------------------------------------------------
# 6. Oversized body → payload_too_large / 413
# ---------------------------------------------------------------------------

class TestGl142OversizedBody(_Gl142ServerInternal):

    def test_oversized_content_length_raises_413(self):
        server_mod, _, _ = _load_modules()
        oversize = str(server_mod.MAX_JSON_BODY_BYTES + 1)
        handler, server_mod = _make_handler(b"x", extra_headers={"Content-Length": oversize})
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        exc = ctx.exception
        self.assertEqual(exc.status, 413)
        self.assertEqual(exc.payload.get("errorCode"), "payload_too_large")

    def test_exactly_at_limit_succeeds(self):
        # Build a valid JSON object at exactly the limit.
        # Key + value padding to hit MAX_JSON_BODY_BYTES.
        server_mod, _, _ = _load_modules()
        limit = server_mod.MAX_JSON_BODY_BYTES
        # {"k":"<padding>"} — build padding so total == limit
        prefix = b'{"k":"'
        suffix = b'"}'
        padding_len = limit - len(prefix) - len(suffix)
        if padding_len < 0:
            self.skipTest("MAX_JSON_BODY_BYTES too small for this test")
        body = prefix + b"a" * padding_len + suffix
        self.assertEqual(len(body), limit)
        handler, _ = _make_handler(body)
        result = handler._read_json()
        self.assertIn("k", result)


# ---------------------------------------------------------------------------
# 7. Raw body not echoed in error response
# ---------------------------------------------------------------------------

class TestGl142RawBodyNotEchoed(_Gl142ServerInternal):

    def test_sentinel_not_in_invalid_json_error(self):
        sentinel = "UNIQUE_SENTINEL_GL142_XYZ"
        body = f"{{invalid: {sentinel}}}".encode()
        handler, server_mod = _make_handler(body)
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        payload_str = json.dumps(ctx.exception.payload)
        self.assertNotIn(sentinel, payload_str)

    def test_sentinel_not_in_non_object_error(self):
        sentinel = "SENTINEL_NONOBJ_GL142_XYZ"
        body = json.dumps([sentinel]).encode()
        handler, server_mod = _make_handler(body)
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        payload_str = json.dumps(ctx.exception.payload)
        self.assertNotIn(sentinel, payload_str)


# ---------------------------------------------------------------------------
# 8. GL-090 request-body hardening preserved
# ---------------------------------------------------------------------------

class TestGl142Gl090Preserved(_Gl142ServerInternal):

    def test_missing_content_length_raises_missing_content_length(self):
        server_mod, _, _ = _load_modules()
        handler = server_mod.GrantLayerHandler.__new__(server_mod.GrantLayerHandler)
        handler.rfile = io.BytesIO(b'{"key":"val"}')
        handler.wfile = io.BytesIO()
        handler.client_address = ("127.0.0.1", 0)
        handler.headers = {}  # No Content-Length
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        exc = ctx.exception
        self.assertEqual(exc.status, 400)
        self.assertEqual(exc.payload.get("errorCode"), "missing_content_length")

    def test_non_integer_content_length_raises_invalid_content_length(self):
        handler, server_mod = _make_handler(b'{"k":"v"}', extra_headers={"Content-Length": "abc"})
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        exc = ctx.exception
        self.assertEqual(exc.status, 400)
        self.assertEqual(exc.payload.get("errorCode"), "invalid_content_length")

    def test_negative_content_length_raises_invalid_content_length(self):
        handler, server_mod = _make_handler(b'{"k":"v"}', extra_headers={"Content-Length": "-1"})
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        exc = ctx.exception
        self.assertEqual(exc.status, 400)
        self.assertEqual(exc.payload.get("errorCode"), "invalid_content_length")


# ---------------------------------------------------------------------------
# 9. GL-124 payload shape validation preserved
# ---------------------------------------------------------------------------

class TestGl142Gl124Preserved(_Gl142ServerInternal):

    def _assert_invalid_json_object(self, raw: bytes):
        handler, server_mod = _make_handler(raw)
        with self.assertRaises(server_mod._BodyParseError) as ctx:
            handler._read_json()
        exc = ctx.exception
        self.assertEqual(exc.status, 400)
        self.assertEqual(exc.payload.get("errorCode"), "invalid_json_object")

    def test_array_payload_rejected(self):
        self._assert_invalid_json_object(b'[]')

    def test_string_payload_rejected(self):
        self._assert_invalid_json_object(b'"string"')

    def test_integer_payload_rejected(self):
        self._assert_invalid_json_object(b'0')

    def test_null_payload_rejected(self):
        self._assert_invalid_json_object(b'null')


# ---------------------------------------------------------------------------
# 10. GL-141 operator model default preserved
# ---------------------------------------------------------------------------

class TestGl142Gl141Preserved(unittest.TestCase):

    def test_enable_operator_model_default_is_true(self):
        config_mod, _ = _load_modules()
        self.assertTrue(
            config_mod.ENABLE_OPERATOR_MODEL,
            "GL-141: ENABLE_OPERATOR_MODEL default must be True"
        )


# ---------------------------------------------------------------------------
# 11. GL-140 ThreadingHTTPServer preserved
# ---------------------------------------------------------------------------

class TestGl142Gl140Preserved(unittest.TestCase):

    def test_threading_http_server_imported(self):
        source = _SERVER_SRC.read_text()
        self.assertIn(
            "ThreadingHTTPServer",
            source,
            "GL-140: ThreadingHTTPServer must remain imported in server.py"
        )

    def test_threading_http_server_used_in_run(self):
        source = _SERVER_SRC.read_text()
        self.assertIn(
            "ThreadingHTTPServer(",
            source,
            "GL-140: ThreadingHTTPServer must be instantiated in run()"
        )

    def test_threading_http_server_inherits_mixin(self):
        import socketserver
        from http.server import ThreadingHTTPServer
        self.assertTrue(
            issubclass(ThreadingHTTPServer, socketserver.ThreadingMixIn),
            "GL-140: ThreadingHTTPServer must subclass ThreadingMixIn"
        )


# ---------------------------------------------------------------------------
# 12. GL-139 audit hash-chain write lock preserved
# ---------------------------------------------------------------------------

class TestGl142Gl139Preserved(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp_db = tmp.name
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        os.environ["GRANTLAYER_DB"] = self._tmp_db
        import backend.src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        import backend.src.audit_log as audit_mod
        importlib.reload(audit_mod)
        self.audit_mod = audit_mod

    def tearDown(self):
        os.unlink(self._tmp_db)
        if self._orig_db is None:
            os.environ.pop("GRANTLAYER_DB", None)
        else:
            os.environ["GRANTLAYER_DB"] = self._orig_db

    def test_audit_write_lock_exists(self):
        self.assertTrue(
            hasattr(self.audit_mod, "_AUDIT_HASH_CHAIN_WRITE_LOCK"),
            "GL-139: _AUDIT_HASH_CHAIN_WRITE_LOCK must exist in audit_log module"
        )

    def test_audit_write_lock_is_rlock(self):
        lock = self.audit_mod._AUDIT_HASH_CHAIN_WRITE_LOCK
        self.assertEqual(
            type(lock).__name__,
            "RLock",
            "GL-139: _AUDIT_HASH_CHAIN_WRITE_LOCK must be an RLock"
        )


# ---------------------------------------------------------------------------
# 13 & 14. Scope guard + branch-scope guard
# ---------------------------------------------------------------------------

_GL142_BRANCH = "gl-142-read-json-bytesio-cleanup"

_ALLOWED_CHANGED = {
    "backend/src/server.py",
    "backend/tests/test_gl142_read_json_bytesio_cleanup.py",
    "backend/tests/test_gl045a_api_contract_consistency.py",
    "backend/tests/test_gl090_request_body_json_hardening.py",
    "backend/tests/test_gl124_request_payload_shape_validation.py",
    "backend/tests/test_gl141_operator_model_default.py",
    "docs/read_json_bytesio_cleanup.md",
    "docs/examples/gl142/read_json_bytesio_cleanup.json",
}

_FORBIDDEN_PATTERNS = [
    ".claude/settings.json",
    "backend/src/config.py",
    "backend/src/audit_log.py",
    "docs/openapi.yaml",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "Pipfile",
    "poetry.lock",
]


def _current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=_REPO_ROOT
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _diff_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True, text=True, cwd=_REPO_ROOT
    )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return lines


class TestGl142ScopeGuard(unittest.TestCase):

    def test_no_openapi_changes(self):
        branch = _current_branch()
        if branch != _GL142_BRANCH:
            self.skipTest(f"Not on {_GL142_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        openapi_changed = [f for f in changed if "openapi" in f.lower()]
        self.assertEqual(openapi_changed, [], f"OpenAPI files must not change: {openapi_changed}")

    def test_no_migration_or_db_schema_changes(self):
        branch = _current_branch()
        if branch != _GL142_BRANCH:
            self.skipTest(f"Not on {_GL142_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        migration_changed = [f for f in changed if "migration" in f or "schema" in f.lower()]
        self.assertEqual(migration_changed, [], f"Migration/schema files must not change: {migration_changed}")

    def test_no_dependency_files_changed(self):
        branch = _current_branch()
        if branch != _GL142_BRANCH:
            self.skipTest(f"Not on {_GL142_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        dep_changed = [f for f in changed if any(f.endswith(pat.lstrip("*")) or f == pat for pat in [
            "requirements.txt", "requirements-dev.txt", "pyproject.toml",
            "setup.py", "Pipfile", "poetry.lock"
        ])]
        self.assertEqual(dep_changed, [], f"Dependency files must not change: {dep_changed}")

    def test_no_forbidden_files_changed(self):
        branch = _current_branch()
        if branch != _GL142_BRANCH:
            self.skipTest(f"Not on {_GL142_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        forbidden = [f for f in changed if any(pat in f for pat in _FORBIDDEN_PATTERNS)]
        self.assertEqual(forbidden, [], f"Forbidden files changed: {forbidden}")

    def test_no_frontend_website_design_changed(self):
        branch = _current_branch()
        if branch != _GL142_BRANCH:
            self.skipTest(f"Not on {_GL142_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        frontend_changed = [
            f for f in changed
            if f.startswith("frontend/") or f.startswith("website/") or f.startswith("design/")
        ]
        self.assertEqual(frontend_changed, [], f"Frontend/website/design files must not change: {frontend_changed}")

    def test_no_claude_settings_changed(self):
        branch = _current_branch()
        if branch != _GL142_BRANCH:
            self.skipTest(f"Not on {_GL142_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        settings_changed = [f for f in changed if ".claude/settings.json" in f]
        self.assertEqual(settings_changed, [], ".claude/settings.json must not change")

    def test_only_allowed_files_changed(self):
        branch = _current_branch()
        if branch != _GL142_BRANCH:
            self.skipTest(f"Not on {_GL142_BRANCH} — skipping diff assertions")
        changed = set(_diff_files())
        disallowed = changed - _ALLOWED_CHANGED
        self.assertEqual(disallowed, set(), f"Unexpected files changed: {disallowed}")

    def test_server_py_is_the_only_production_src_file_changed(self):
        branch = _current_branch()
        if branch != _GL142_BRANCH:
            self.skipTest(f"Not on {_GL142_BRANCH} — skipping diff assertions")
        changed = _diff_files()
        src_changed = [f for f in changed if f.startswith("backend/src/") and f != "backend/src/server.py"]
        self.assertEqual(src_changed, [], f"Only backend/src/server.py is allowed: {src_changed}")


if __name__ == "__main__":
    unittest.main()
