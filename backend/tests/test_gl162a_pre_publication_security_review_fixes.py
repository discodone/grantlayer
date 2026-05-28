"""
GL-162A Validation: Pre-Publication Security Review Fixes.

Covers:
1. Scan gate self-exclusion: scanner does not fail due to its own meta files
2. Scanner still detects real blockers (synthetic hostname / path fixtures)
3. Public-facing docs do not contain forge.hofercloud.eu
4. .gitignore contains .claude/
5. HTTP security headers present on successful and error responses
6. Health and readiness endpoints remain public
7. Rate limiting: fallback IP, CF-Connecting-IP, X-Forwarded-For, malformed headers
8. Grant request role allowlist: valid roles accepted, invalid roles rejected
9. Branch scope guard
"""

import importlib
import io
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SCAN_SCRIPT = _REPO_ROOT / "scripts" / "public-secret-sensitive-scan.sh"
_GITIGNORE = _REPO_ROOT / ".gitignore"
_SCAN_DOCS = _REPO_ROOT / "docs" / "public_secret_sensitive_scan_gate.md"
_GL152_JSON = _REPO_ROOT / "docs" / "examples" / "gl152" / "public_checklist_blocker_fixes.json"

# Scanner meta files that must be excluded from self-scan
_SCANNER_META_FILES = [
    "scripts/public-secret-sensitive-scan.sh",
    "docs/public_secret_sensitive_scan_gate.md",
    "backend/tests/test_gl157_public_secret_sensitive_scan_gate.py",
    "backend/tests/test_gl162a_pre_publication_security_review_fixes.py",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_server():
    """Load server module with a temporary DB."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    os.environ.setdefault("GRANTLAYER_DB", tmp.name)
    os.environ.setdefault("GRANTLAYER_ADMIN_TOKEN", "test-admin-token")
    import src.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    import src.server as server_mod
    importlib.reload(server_mod)
    import src.config as config_mod
    importlib.reload(config_mod)
    return server_mod, config_mod, tmp.name


def _make_capturing_handler(server_mod, path, method="GET", headers=None, body=b""):
    """Return a GrantLayerHandler subclass instance that captures response headers."""

    class CapturingHandler(server_mod.GrantLayerHandler):
        def __init__(self):
            self.command = method
            self.path = path
            self.request_version = "HTTP/1.1"
            self.headers = headers or {}
            self.rfile = io.BytesIO(body)
            self.wfile = io.BytesIO()
            self.client_address = ("127.0.0.1", 0)
            self._response_status = None
            self._response_headers = {}

        def send_response(self, code):
            self._response_status = code

        def send_header(self, key, value):
            self._response_headers[key.lower()] = value

        def end_headers(self):
            pass

        def log_message(self, fmt, *args):
            pass

    return CapturingHandler()


# ---------------------------------------------------------------------------
# 1. Scan gate: scanner meta-file self-exclusion
# ---------------------------------------------------------------------------

class TestGL162AScanGateSelfExclusion(unittest.TestCase):
    """The scanner must not fail solely because of its own script/docs/test files."""

    def test_meta_exclude_list_in_script(self):
        """Scanner script must define the META_EXCLUDE array."""
        content = _SCAN_SCRIPT.read_text()
        self.assertIn("META_EXCLUDE", content,
                      "Script must contain META_EXCLUDE exclusion list")

    def test_scanner_meta_files_in_exclude_list(self):
        """Each known scanner meta file must appear in the META_EXCLUDE array."""
        content = _SCAN_SCRIPT.read_text()
        for path in _SCANNER_META_FILES:
            self.assertIn(path, content,
                          f"META_EXCLUDE must include: {path}")

    def test_meta_excluded_count_reported(self):
        """Scanner output must include a Meta-excluded count line."""
        # Use a synthetic repo so we control what files are present
        tmp = tempfile.mkdtemp(prefix="gl162a_meta_")
        try:
            subprocess.run(["git", "init", tmp], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "t@example.com"],
                           cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"],
                           cwd=tmp, check=True, capture_output=True)
            scripts_dir = os.path.join(tmp, "scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            dest = os.path.join(scripts_dir, "public-secret-sensitive-scan.sh")
            shutil.copy2(str(_SCAN_SCRIPT), dest)
            os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP)
            # Add a completely safe tracked file
            safe_path = os.path.join(tmp, "safe.txt")
            with open(safe_path, "w") as f:
                f.write("Hello, world.\n")
            subprocess.run(["git", "add", "safe.txt", "scripts/public-secret-sensitive-scan.sh"],
                           cwd=tmp, check=True, capture_output=True)
            result = subprocess.run(
                ["bash", os.path.join(tmp, "scripts", "public-secret-sensitive-scan.sh")],
                cwd=tmp, capture_output=True, text=True)
            self.assertIn("Meta-excluded", result.stdout,
                          "Scanner must print 'Meta-excluded' line in summary")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_meta_only_repo_scans_clean(self):
        """A repo containing only scanner meta files (no other blockers) must exit 0."""
        tmp = tempfile.mkdtemp(prefix="gl162a_meta_clean_")
        try:
            subprocess.run(["git", "init", tmp], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "t@example.com"],
                           cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"],
                           cwd=tmp, check=True, capture_output=True)
            # Copy the scanner script itself (which contains internal patterns)
            scripts_dir = os.path.join(tmp, "scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            dest = os.path.join(scripts_dir, "public-secret-sensitive-scan.sh")
            shutil.copy2(str(_SCAN_SCRIPT), dest)
            os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP)
            subprocess.run(["git", "add", "scripts/public-secret-sensitive-scan.sh"],
                           cwd=tmp, check=True, capture_output=True)
            result = subprocess.run(
                ["bash", os.path.join(tmp, "scripts", "public-secret-sensitive-scan.sh")],
                cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0,
                             f"Repo with only the scanner script must exit 0 (meta excluded).\n"
                             f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2. Scanner still detects real blockers (synthetic temp repo)
# ---------------------------------------------------------------------------

class TestGL162AScannerDetectsRealBlockers(unittest.TestCase):
    """Scanner must still detect real blockers despite meta-file exclusion."""

    def _make_repo(self):
        tmp = tempfile.mkdtemp(prefix="gl162a_test_")
        subprocess.run(["git", "init", tmp], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                       cwd=tmp, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"],
                       cwd=tmp, check=True, capture_output=True)
        scripts_dir = os.path.join(tmp, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        dest = os.path.join(scripts_dir, "public-secret-sensitive-scan.sh")
        shutil.copy2(str(_SCAN_SCRIPT), dest)
        os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP)
        return tmp

    def setUp(self):
        self.tmp = self._make_repo()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_and_track(self, filename, content):
        filepath = os.path.join(self.tmp, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.run(["git", "add", filename], cwd=self.tmp,
                       check=True, capture_output=True)
        return filepath

    def _run_scan(self):
        return subprocess.run(
            ["bash", os.path.join(self.tmp, "scripts", "public-secret-sensitive-scan.sh")],
            cwd=self.tmp,
            capture_output=True,
            text=True,
        )

    def test_synthetic_internal_hostname_detected(self):
        """Scanner must detect a synthetic internal hostname in a normal tracked file."""
        # Use a hostname that matches the internal_hostname pattern used by the scanner
        self._write_and_track("normal_config.txt",
            "git_remote: forge.hofercloud.eu/org/repo.git\n")
        result = self._run_scan()
        self.assertNotEqual(result.returncode, 0,
                            f"Expected non-zero for internal hostname blocker.\n"
                            f"STDOUT:\n{result.stdout}")
        self.assertIn("BLOCKER", result.stdout,
                      "Output must contain BLOCKER line for internal hostname")

    def test_synthetic_internal_path_detected(self):
        """Scanner must detect a synthetic internal path in a normal tracked file."""
        self._write_and_track("normal_config.txt",
            "config_dir: /home/adminuser/projects/config\n")
        result = self._run_scan()
        self.assertNotEqual(result.returncode, 0,
                            f"Expected non-zero for internal path blocker.\n"
                            f"STDOUT:\n{result.stdout}")
        self.assertIn("BLOCKER", result.stdout,
                      "Output must contain BLOCKER line for internal path")


# ---------------------------------------------------------------------------
# 3. Public-facing docs must not contain forge.hofercloud.eu
# ---------------------------------------------------------------------------

class TestGL162AForgeHostnameRemovedFromDocs(unittest.TestCase):

    def test_scan_docs_no_forge_hostname(self):
        """docs/public_secret_sensitive_scan_gate.md must not contain forge.hofercloud.eu."""
        content = _SCAN_DOCS.read_text()
        self.assertNotIn("forge.hofercloud.eu", content,
                         "Public scan gate docs must not reference internal forge hostname")

    def test_gl152_json_no_forge_hostname(self):
        """docs/examples/gl152/public_checklist_blocker_fixes.json must not contain forge.hofercloud.eu."""
        content = _GL152_JSON.read_text()
        self.assertNotIn("forge.hofercloud.eu", content,
                         "GL-152 artifact must not reference internal forge hostname")


# ---------------------------------------------------------------------------
# 4. .gitignore must contain .claude/
# ---------------------------------------------------------------------------

class TestGL162AClaudeInGitignore(unittest.TestCase):

    def test_gitignore_contains_claude_dir(self):
        """.gitignore must include a .claude/ entry."""
        content = _GITIGNORE.read_text()
        self.assertIn(".claude/", content,
                      ".gitignore must contain .claude/ entry")


# ---------------------------------------------------------------------------
# 5 & 6. HTTP security headers
# ---------------------------------------------------------------------------

_REQUIRED_SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "cache-control": "no-store",
}
_CSP_HEADER = "content-security-policy"
_CSP_REQUIRED_DIRECTIVE = "default-src 'none'"


class TestGL162ASecurityHeaders(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_mod, cls.config_mod, cls.tmp_db = _load_server()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.tmp_db)
        except OSError:
            pass

    def _get_headers(self, path, method="GET", headers=None, body=b""):
        handler = _make_capturing_handler(
            self.server_mod, path, method, headers or {}, body)
        if method == "GET":
            handler.do_GET()
        else:
            handler.do_POST()
        return handler._response_status, handler._response_headers

    def _assert_security_headers(self, response_headers, label):
        for header, expected_value in _REQUIRED_SECURITY_HEADERS.items():
            self.assertIn(header, response_headers,
                          f"{label}: missing header {header}")
            self.assertEqual(response_headers[header], expected_value,
                             f"{label}: wrong value for {header}")
        self.assertIn(_CSP_HEADER, response_headers,
                      f"{label}: missing Content-Security-Policy header")
        self.assertIn(_CSP_REQUIRED_DIRECTIVE, response_headers[_CSP_HEADER],
                      f"{label}: CSP must include default-src 'none'")

    def test_health_response_has_security_headers(self):
        """GET /health must include all required security headers."""
        status, headers = self._get_headers("/health")
        self.assertEqual(status, 200)
        self._assert_security_headers(headers, "GET /health")

    def test_readiness_response_has_security_headers(self):
        """GET /readiness must include all required security headers."""
        status, headers = self._get_headers("/readiness")
        self.assertIn(status, (200, 503))
        self._assert_security_headers(headers, "GET /readiness")

    def test_error_response_has_security_headers(self):
        """A 404 error response must include all required security headers."""
        status, headers = self._get_headers("/nonexistent-path-12345")
        self.assertEqual(status, 404)
        self._assert_security_headers(headers, "GET /nonexistent-path 404")

    def test_health_endpoint_public_no_auth_required(self):
        """GET /health must return 200 without authentication."""
        status, headers = self._get_headers("/health")
        self.assertEqual(status, 200,
                         "Health endpoint must be publicly accessible without auth")

    def test_readiness_endpoint_public_no_auth_required(self):
        """GET /readiness must return 2xx or 503 without authentication."""
        status, headers = self._get_headers("/readiness")
        self.assertIn(status, (200, 503),
                      "Readiness endpoint must be accessible without auth")


# ---------------------------------------------------------------------------
# 7. Rate limiting: reverse-proxy-aware IP resolution
# ---------------------------------------------------------------------------

class TestGL162ARateLimitProxyAware(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_mod, cls.config_mod, cls.tmp_db = _load_server()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.tmp_db)
        except OSError:
            pass

    def _make_handler_with_headers(self, headers, client_ip="10.0.0.1"):
        handler = _make_capturing_handler(
            self.server_mod, "/health", "GET", headers)
        handler.client_address = (client_ip, 0)
        return handler

    def test_fallback_to_client_address(self):
        """Without proxy headers, _resolve_client_ip returns client_address IP."""
        handler = self._make_handler_with_headers({})
        ip = handler._resolve_client_ip()
        self.assertEqual(ip, "10.0.0.1",
                         "Fallback must use client_address[0] when no proxy headers")

    def test_cf_connecting_ip_used_when_valid(self):
        """Valid CF-Connecting-IP must be preferred over client_address."""
        handler = self._make_handler_with_headers(
            {"CF-Connecting-IP": "203.0.113.45"}, client_ip="10.0.0.1")
        ip = handler._resolve_client_ip()
        self.assertEqual(ip, "203.0.113.45",
                         "CF-Connecting-IP must be used when present and valid")

    def test_xff_first_ip_used_when_valid(self):
        """Valid first IP in X-Forwarded-For must be used when CF-Connecting-IP absent."""
        handler = self._make_handler_with_headers(
            {"X-Forwarded-For": "198.51.100.7, 10.0.0.1"}, client_ip="10.0.0.2")
        ip = handler._resolve_client_ip()
        self.assertEqual(ip, "198.51.100.7",
                         "First valid IP in X-Forwarded-For must be used")

    def test_malformed_cf_connecting_ip_falls_back(self):
        """Malformed CF-Connecting-IP must be ignored; fallback to client_address."""
        handler = self._make_handler_with_headers(
            {"CF-Connecting-IP": "not-an-ip"}, client_ip="10.0.0.3")
        ip = handler._resolve_client_ip()
        self.assertEqual(ip, "10.0.0.3",
                         "Malformed CF-Connecting-IP must be ignored")

    def test_malformed_xff_falls_back(self):
        """Malformed X-Forwarded-For must be ignored; fallback to client_address."""
        handler = self._make_handler_with_headers(
            {"X-Forwarded-For": "not-an-ip, garbage"}, client_ip="10.0.0.4")
        ip = handler._resolve_client_ip()
        self.assertEqual(ip, "10.0.0.4",
                         "Malformed X-Forwarded-For first entry must be ignored")

    def test_no_client_address_returns_none(self):
        """When client_address is not set, _resolve_client_ip returns None."""
        handler = _make_capturing_handler(self.server_mod, "/health", "GET", {})
        handler.client_address = None
        ip = handler._resolve_client_ip()
        self.assertIsNone(ip,
                          "Must return None when client_address is unavailable")

    def test_cf_ip_with_whitespace_stripped(self):
        """CF-Connecting-IP with surrounding whitespace must be accepted."""
        handler = self._make_handler_with_headers(
            {"CF-Connecting-IP": "  203.0.113.99  "}, client_ip="10.0.0.5")
        ip = handler._resolve_client_ip()
        self.assertEqual(ip, "203.0.113.99",
                         "IP with surrounding whitespace must be stripped and accepted")


# ---------------------------------------------------------------------------
# 8. Grant request role allowlist
# ---------------------------------------------------------------------------

class TestGL162ARoleAllowlist(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmp_db_path = tmp.name
        os.environ.setdefault("GRANTLAYER_DB", tmp.name)
        import src.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        import src.grant_requests as gr_mod
        importlib.reload(gr_mod)
        cls.gr_mod = gr_mod
        import src.models as models_mod
        importlib.reload(models_mod)
        cls.models_mod = models_mod

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db_path)
        except OSError:
            pass

    def _make_request(self, role):
        return self.models_mod.GrantRequest(
            subject_id="test-subject",
            role=role,
            action="read",
            resource="doc/1",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            requested_by="op-1",
            reason="test grant request",
        )

    def test_allowed_grant_roles_defined(self):
        """ALLOWED_GRANT_ROLES must be defined in grant_requests module."""
        self.assertTrue(hasattr(self.gr_mod, "ALLOWED_GRANT_ROLES"),
                        "grant_requests must define ALLOWED_GRANT_ROLES")
        roles = self.gr_mod.ALLOWED_GRANT_ROLES
        self.assertGreater(len(roles), 0, "ALLOWED_GRANT_ROLES must not be empty")

    def test_valid_roles_accepted(self):
        """Each role in ALLOWED_GRANT_ROLES must be accepted by create_grant_request."""
        for role in self.gr_mod.ALLOWED_GRANT_ROLES:
            with self.subTest(role=role):
                request = self._make_request(role)
                try:
                    created = self.gr_mod.create_grant_request(request)
                    self.assertEqual(created.role, role)
                except ValueError as exc:
                    self.fail(f"Valid role '{role}' was rejected: {exc}")

    def test_fake_admin_role_rejected(self):
        """Role 'fake-admin' must be rejected by create_grant_request."""
        request = self._make_request("fake-admin")
        with self.assertRaises(ValueError):
            self.gr_mod.create_grant_request(request)

    def test_unexpected_role_rejected(self):
        """An arbitrary unexpected role string must be rejected."""
        request = self._make_request("super-privileged-unexpected")
        with self.assertRaises(ValueError):
            self.gr_mod.create_grant_request(request)

    def test_role_length_validation_still_applies(self):
        """A role that exceeds MAX_ROLE_LENGTH must still be rejected."""
        long_role = "a" * 200
        request = self._make_request(long_role)
        with self.assertRaises(ValueError):
            self.gr_mod.create_grant_request(request)

    def test_invalid_role_error_is_safe(self):
        """Error for invalid role must be a ValueError with a safe message."""
        request = self._make_request("fake-admin")
        try:
            self.gr_mod.create_grant_request(request)
            self.fail("Expected ValueError for fake-admin role")
        except ValueError as exc:
            msg = str(exc)
            self.assertNotIn("password", msg.lower(),
                             "Error message must not leak sensitive data")
            self.assertNotIn("token", msg.lower(),
                             "Error message must not leak sensitive data")


# ---------------------------------------------------------------------------
# 9. Branch scope guard
# ---------------------------------------------------------------------------

class TestGL162ABranchScopeGuard(unittest.TestCase):
    """Only the allowed files may be changed on the GL-162A branch."""

    _ALLOWED_CHANGED = frozenset({
        ".gitignore",
        "scripts/public-secret-sensitive-scan.sh",
        "docs/public_secret_sensitive_scan_gate.md",
        "docs/examples/gl152/public_checklist_blocker_fixes.json",
        "backend/src/server.py",
        "backend/src/grant_requests.py",
        "backend/tests/test_gl162a_pre_publication_security_review_fixes.py",
    })

    _FORBIDDEN_PATTERNS = [
        ".claude/",
        "openapi",
        "requirements",
        "package.json",
        "frontend/",
        "website/",
        "sdk/",
    ]

    def _get_current_branch(self):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _get_diff_files(self):
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "main...HEAD"],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
            )
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except Exception:
            return []

    def test_scope_guard_on_gl162a_branch(self):
        branch = self._get_current_branch()
        if "162a" not in branch.lower():
            self.skipTest(f"Scope guard only runs on GL-162A branch; current: {branch}")
        changed = self._get_diff_files()
        unexpected = [f for f in changed if f not in self._ALLOWED_CHANGED]
        self.assertEqual(unexpected, [],
                         f"Unexpected files changed: {unexpected}\n"
                         f"Only these files are allowed: {sorted(self._ALLOWED_CHANGED)}")

    def test_no_claude_files_staged_or_changed(self):
        branch = self._get_current_branch()
        if "162a" not in branch.lower():
            self.skipTest(f"Scope guard only runs on GL-162A branch; current: {branch}")
        changed = self._get_diff_files()
        claude_files = [f for f in changed if f.startswith(".claude/")]
        self.assertEqual(claude_files, [],
                         f".claude/ files must not be staged or committed: {claude_files}")

    def test_no_forbidden_patterns_in_changed_files(self):
        branch = self._get_current_branch()
        if "162a" not in branch.lower():
            self.skipTest(f"Scope guard only runs on GL-162A branch; current: {branch}")
        changed = self._get_diff_files()
        for pattern in self._FORBIDDEN_PATTERNS:
            matches = [f for f in changed if pattern.lower() in f.lower()]
            self.assertEqual(matches, [],
                             f"Forbidden pattern '{pattern}' found in changed files: {matches}")


if __name__ == "__main__":
    unittest.main()
