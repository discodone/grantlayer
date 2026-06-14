"""Tests for GL-140: ThreadingHTTPServer Enablement.

Ensures:
1. ThreadingHTTPServer is imported in server.py.
2. ThreadingHTTPServer is used in run() — plain HTTPServer is not.
3. GL-139 audit hash-chain write lock is preserved (regression guard).
4. ThreadingHTTPServer inherits from ThreadingMixIn (stdlib guarantee).
5. Branch-scope guard: diff limited to allowed files, no OpenAPI/migration/dependency changes.
"""

import os
import pathlib
import subprocess
import sys
import socketserver
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════════════
# 1. ThreadingHTTPServer imported
# ═══════════════════════════════════════════════════════════════════════

@unittest.skip("server.py deleted in GL-240")
class TestGl140ThreadingImported(unittest.TestCase):
    """server.py must import ThreadingHTTPServer."""

    def _server_source(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        return (repo_root / "backend" / "src" / "server.py").read_text(encoding="utf-8")

    def test_threading_http_server_in_source(self):
        self.assertIn("ThreadingHTTPServer", self._server_source())

    def test_threading_http_server_in_import_line(self):
        for line in self._server_source().splitlines():
            if "from http.server import" in line:
                self.assertIn(
                    "ThreadingHTTPServer",
                    line,
                    "ThreadingHTTPServer must appear on the http.server import line",
                )
                return
        self.fail("No 'from http.server import' line found in server.py")


# ═══════════════════════════════════════════════════════════════════════
# 2. ThreadingHTTPServer used in run()
# ═══════════════════════════════════════════════════════════════════════

@unittest.skip("server.py deleted in GL-240")
class TestGl140ThreadingUsedInRun(unittest.TestCase):
    """run() must instantiate ThreadingHTTPServer, not plain HTTPServer."""

    def _run_function_source(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        source = (repo_root / "backend" / "src" / "server.py").read_text(encoding="utf-8")
        # Extract lines from def run( onward
        lines = source.splitlines()
        start = None
        for i, line in enumerate(lines):
            if line.startswith("def run("):
                start = i
                break
        self.assertIsNotNone(start, "def run( not found in server.py")
        return "\n".join(lines[start:])

    def test_threading_http_server_instantiated(self):
        run_src = self._run_function_source()
        self.assertIn(
            "ThreadingHTTPServer(",
            run_src,
            "run() must instantiate ThreadingHTTPServer",
        )

    def test_plain_http_server_not_instantiated_in_run(self):
        run_src = self._run_function_source()
        # Allow 'HTTPServer' as part of 'ThreadingHTTPServer' — check for bare instantiation
        import re
        # Match 'HTTPServer(' not preceded by 'Threading'
        bare_instantiation = re.search(r'(?<!Threading)HTTPServer\(', run_src)
        self.assertIsNone(
            bare_instantiation,
            "run() must not instantiate plain HTTPServer — use ThreadingHTTPServer",
        )


# ═══════════════════════════════════════════════════════════════════════
# 3. GL-139 audit lock preserved
# ═══════════════════════════════════════════════════════════════════════

class TestGl140Gl139LockPreserved(unittest.TestCase):
    """_AUDIT_HASH_CHAIN_WRITE_LOCK must still exist in audit_log (GL-139 regression)."""

    def test_audit_lock_still_present(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        audit_path = repo_root / "backend" / "src" / "audit" / "audit_log.py"
        source = audit_path.read_text(encoding="utf-8")
        self.assertIn(
            "_AUDIT_HASH_CHAIN_WRITE_LOCK",
            source,
            "GL-139 _AUDIT_HASH_CHAIN_WRITE_LOCK must not be removed by GL-140",
        )

    def test_audit_lock_is_rlock_in_source(self):
        repo_root = pathlib.Path(__file__).with_suffix("").parent.parent.parent
        audit_path = repo_root / "backend" / "src" / "audit" / "audit_log.py"
        source = audit_path.read_text(encoding="utf-8")
        self.assertIn(
            "RLock",
            source,
            "audit_log.py must still contain an RLock for the hash-chain write lock",
        )


# ═══════════════════════════════════════════════════════════════════════
# 4. ThreadingHTTPServer stdlib guarantee
# ═══════════════════════════════════════════════════════════════════════

class TestGl140ConcurrentHandlerInstantiation(unittest.TestCase):
    """ThreadingHTTPServer must inherit from socketserver.ThreadingMixIn."""

    def test_threading_http_server_is_threading_mixin(self):
        from http.server import ThreadingHTTPServer
        self.assertTrue(
            issubclass(ThreadingHTTPServer, socketserver.ThreadingMixIn),
            "ThreadingHTTPServer must subclass socketserver.ThreadingMixIn",
        )

    def test_threading_http_server_daemon_threads(self):
        from http.server import ThreadingHTTPServer
        # daemon_threads=True means child threads exit when main thread exits
        self.assertTrue(
            getattr(ThreadingHTTPServer, "daemon_threads", False),
            "ThreadingHTTPServer.daemon_threads should be True",
        )


# ═══════════════════════════════════════════════════════════════════════
# 5. Scope guard
# ═══════════════════════════════════════════════════════════════════════

class TestGl140ScopeGuard(unittest.TestCase):
    """Diff scope limited to allowed files; branch-aware skip."""

    def _repo_root(self):
        return pathlib.Path(__file__).with_suffix("").parent.parent.parent

    def _current_branch(self):
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self._repo_root(),
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _changed_files(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=self._repo_root(),
            capture_output=True,
            text=True,
        )
        return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]

    def setUp(self):
        if self._current_branch() != "gl-140-threading-http-server-enablement":
            self.skipTest("Scope guard only valid on GL-140 feature branch")

    def test_git_diff_limited_to_allowed_files(self):
        allowed = {
            "backend/src/server.py",
            "backend/tests/test_gl140_threading_http_server_enablement.py",
            "backend/tests/test_gl139_audit_hash_chain_write_lock.py",
            "backend/tests/test_security_boundary_regression.py",
            "docs/threading_http_server_enablement.md",
            "docs/examples/gl140/threading_http_server_enablement.json",
            "docs/security_remediation_intake_2026_05_26.md",
        }
        for path in self._changed_files():
            self.assertIn(path, allowed, f"GL-140 changed a forbidden file: {path}")

    def test_no_openapi_change(self):
        openapi_path = self._repo_root() / "docs" / "openapi.yaml"
        self.assertTrue(openapi_path.exists(), "openapi.yaml missing")
        content = openapi_path.read_text()
        self.assertNotIn("threadinghttpserver", content.lower())

    def test_no_new_migration(self):
        migrations_dir = self._repo_root() / "backend" / "src" / "migrations"
        scripts = sorted(migrations_dir.glob("0*.py"))
        self.assertEqual(len(scripts), 9, f"Expected 9 migration scripts, got {len(scripts)}")

    def test_no_dependency_files_changed(self):
        if self._current_branch() != "gl-140-threading-http-server-enablement":
            self.skipTest("Branch-wide diff check only valid on GL-140 feature branch")
        forbidden = {
            "requirements.txt",
            "requirements-dev.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "poetry.lock",
        }
        for path in self._changed_files():
            self.assertNotIn(path, forbidden, f"GL-140 must not change dependency file: {path}")

    def test_no_frontend_files_changed(self):
        if self._current_branch() != "gl-140-threading-http-server-enablement":
            self.skipTest("Branch-wide diff check only valid on GL-140 feature branch")
        for path in self._changed_files():
            self.assertFalse(
                path.startswith("frontend/") or path.startswith("website/"),
                f"GL-140 must not change frontend/website file: {path}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
