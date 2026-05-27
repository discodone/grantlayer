"""GL-138 — Remove Duplicate check_admin_token Stub.

Ensures:
1. Exactly one top-level check_admin_token function exists in auth.py.
2. The function is importable and behavior is preserved.
3. Valid admin token behavior works.
4. Missing/invalid admin token fails closed.
5. Raw token is never exposed in results.
6. No duplicate compatibility stub remains.
"""

import ast
import os
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestGl138CheckAdminTokenCleanup(unittest.TestCase):
    """GL-138 targeted cleanup tests."""

    def setUp(self):
        self._orig_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_require = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

    def tearDown(self):
        for key, orig in [
            ("GRANTLAYER_ADMIN_TOKEN", self._orig_token),
            ("GRANTLAYER_REQUIRE_ADMIN_TOKEN", self._orig_require),
        ]:
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _auth_py_path(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        return repo_root / "backend" / "src" / "auth.py"

    # ──────────────────────────────────────────────
    # 1. AST: exactly one check_admin_token function
    # ──────────────────────────────────────────────
    def test_exactly_one_check_admin_token_function(self):
        source = self._auth_py_path().read_text(encoding="utf-8")
        tree = ast.parse(source)
        funcs = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "check_admin_token"
        ]
        self.assertEqual(
            len(funcs),
            1,
            f"Expected exactly one check_admin_token function, found {len(funcs)}",
        )

    # ──────────────────────────────────────────────
    # 2. Importable
    # ──────────────────────────────────────────────
    def test_check_admin_token_is_importable(self):
        from backend.src.auth import check_admin_token
        self.assertTrue(callable(check_admin_token))

    # ──────────────────────────────────────────────
    # 3. Valid admin token behavior preserved
    # ──────────────────────────────────────────────
    def test_valid_admin_token_allows(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "valid-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        from backend.src.auth import check_admin_token
        ok, status, payload = check_admin_token("Bearer valid-token")
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {})

    # ──────────────────────────────────────────────
    # 4. Missing admin token fails closed
    # ──────────────────────────────────────────────
    def test_missing_admin_token_fails_closed(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "valid-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        from backend.src.auth import check_admin_token
        ok, status, payload = check_admin_token(None)
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload.get("errorCode"), "admin_token_required")

    # ──────────────────────────────────────────────
    # 5. Invalid admin token fails closed
    # ──────────────────────────────────────────────
    def test_invalid_admin_token_fails_closed(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "valid-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        from backend.src.auth import check_admin_token
        ok, status, payload = check_admin_token("Bearer wrong-token")
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(payload.get("errorCode"), "admin_token_invalid")

    # ──────────────────────────────────────────────
    # 6. Raw token not exposed in results
    # ──────────────────────────────────────────────
    def test_raw_token_not_exposed(self):
        secret = "super-secret-token-138"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = secret
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        from backend.src.auth import check_admin_token
        for header in [None, "Bearer wrong-token"]:
            ok, status, payload = check_admin_token(header)
            result_str = str(payload)
            self.assertNotIn(secret, result_str)
            self.assertNotIn("super-secret", result_str)

    # ──────────────────────────────────────────────
    # 7. No duplicate compatibility stub remains
    # ──────────────────────────────────────────────
    def test_no_stub_body_with_ellipsis(self):
        source = self._auth_py_path().read_text(encoding="utf-8")
        tree = ast.parse(source)
        funcs = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "check_admin_token"
        ]
        self.assertEqual(len(funcs), 1)
        body = funcs[0].body
        # A stub would have only Expr(Constant(Ellipsis)) or Pass
        if len(body) == 1 and isinstance(body[0], ast.Expr):
            value = body[0].value
            if isinstance(value, ast.Constant) and value.value is ...:
                self.fail("check_admin_token is still a stub (ellipsis body)")

    # ──────────────────────────────────────────────
    # 8. Scope guard: branch diff limited to allowed files
    # ──────────────────────────────────────────────
    def test_git_diff_limited_to_allowed_files(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        if branch != "gl-138-check-admin-token-cleanup":
            self.skipTest(
                "Branch-wide diff check only valid on GL-138 feature branch"
            )
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        changed = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        allowed = {
            "backend/src/auth.py",
            "backend/tests/test_gl138_check_admin_token_cleanup.py",
            "backend/tests/test_security_boundary_regression.py",
            "backend/tests/test_gl120_auth_failure_structured_events.py",
            "backend/tests/test_gl109_operators_me.py",
            "backend/tests/test_gl087_auth_error_response_consistency.py",
            "docs/examples/gl138/check_admin_token_cleanup.json",
            "docs/check_admin_token_cleanup.md",
            "docs/security_remediation_intake_2026_05_26.md",
        }
        for path in changed:
            self.assertIn(
                path,
                allowed,
                f"GL-138 changed a forbidden file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
