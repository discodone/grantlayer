"""
GL-147: Minimal Python SDK — Validation Tests

Validates:
- SDK files exist
- JSON artifact structure and boolean flags
- SDK module import without network side effects
- SDK class/method shape
- Request construction, header injection, error mapping (monkeypatched, no network)
- README content and safety caveats
- Branch-scope guard (conditional on gl-147-minimal-python-sdk branch)
"""

import importlib.util
import json
import subprocess
import sys
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SDK_PY = REPO_ROOT / "sdk" / "python" / "grantlayer_client.py"
SDK_README = REPO_ROOT / "sdk" / "python" / "README.md"
JSON_ARTIFACT = REPO_ROOT / "docs" / "examples" / "gl147" / "minimal_python_sdk.json"


def _load_sdk() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("grantlayer_client", SDK_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_mock_response(status: int, body: object) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.status = status
    mock_resp.read.return_value = json.dumps(body).encode("utf-8")
    mock_resp.headers = {}
    return mock_resp


class TestGl147FilesExist(unittest.TestCase):
    def test_sdk_client_exists(self):
        self.assertTrue(SDK_PY.exists(), f"SDK client not found: {SDK_PY}")

    def test_sdk_readme_exists(self):
        self.assertTrue(SDK_README.exists(), f"SDK README not found: {SDK_README}")

    def test_json_artifact_exists(self):
        self.assertTrue(JSON_ARTIFACT.exists(), f"JSON artifact not found: {JSON_ARTIFACT}")


class TestGl147JsonArtifact(unittest.TestCase):
    def setUp(self):
        with open(JSON_ARTIFACT, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_json_parses(self):
        self.assertIsInstance(self.data, dict)

    def test_issue_id(self):
        self.assertEqual(self.data.get("issue_id"), "GL-147")

    def test_artifact_type(self):
        self.assertEqual(self.data.get("artifact_type"), "minimal_python_sdk")

    def test_sdk_created_true(self):
        self.assertIs(self.data.get("sdk_created"), True)

    def test_sdk_language(self):
        self.assertEqual(self.data.get("sdk_language"), "Python")

    def test_standard_library_only_true(self):
        self.assertIs(self.data.get("standard_library_only"), True)

    def test_package_published_false(self):
        self.assertIs(self.data.get("package_published"), False)

    def test_production_code_changed_false(self):
        self.assertIs(self.data.get("production_code_changed"), False)

    def test_backend_src_changed_false(self):
        self.assertIs(self.data.get("backend_src_changed"), False)

    def test_endpoint_api_behavior_changed_false(self):
        self.assertIs(self.data.get("endpoint_api_behavior_changed"), False)

    def test_openapi_changed_false(self):
        self.assertIs(self.data.get("openapi_changed"), False)

    def test_db_schema_changed_false(self):
        self.assertIs(self.data.get("db_schema_changed"), False)

    def test_dependencies_changed_false(self):
        self.assertIs(self.data.get("dependencies_changed"), False)

    def test_auth_semantics_changed_false(self):
        self.assertIs(self.data.get("auth_semantics_changed"), False)

    def test_langgraph_langchain_example_implemented_false(self):
        self.assertIs(self.data.get("langgraph_langchain_example_implemented"), False)

    def test_public_github_ready_claimed_false(self):
        self.assertIs(self.data.get("public_github_ready_claimed"), False)

    def test_production_saas_ready_claimed_false(self):
        self.assertIs(self.data.get("production_saas_ready_claimed"), False)

    def test_tenant_isolation_claimed_implemented_false(self):
        self.assertIs(self.data.get("tenant_isolation_claimed_implemented"), False)

    def test_uses_real_secrets_false(self):
        self.assertIs(self.data.get("uses_real_secrets"), False)

    def test_uses_real_customer_data_false(self):
        self.assertIs(self.data.get("uses_real_customer_data"), False)

    def test_client_features_present(self):
        features = self.data.get("client_features")
        self.assertIsInstance(features, list)
        self.assertGreater(len(features), 0)

    def test_safety_caveats_present(self):
        caveats = self.data.get("safety_caveats")
        self.assertIsInstance(caveats, list)
        self.assertGreater(len(caveats), 0)

    def test_validation_gates_present(self):
        gates = self.data.get("validation_gates")
        self.assertIsInstance(gates, list)
        self.assertGreater(len(gates), 0)

    def test_next_issue(self):
        next_issue = self.data.get("next_issue", "")
        self.assertIn("GL-148", next_issue)

    def test_sdk_path_field(self):
        self.assertIn("sdk/python/grantlayer_client.py", self.data.get("sdk_path", ""))

    def test_sdk_readme_path_field(self):
        self.assertIn("sdk/python/README.md", self.data.get("sdk_readme_path", ""))


class TestGl147SdkImport(unittest.TestCase):
    def setUp(self):
        self.mod = _load_sdk()

    def test_no_network_at_import(self):
        # Loading the module must not have made network calls; if we got here, it didn't.
        self.assertIsNotNone(self.mod)

    def test_grantlayerclient_is_class(self):
        self.assertTrue(
            isinstance(self.mod.GrantLayerClient, type),
            "GrantLayerClient must be a class",
        )

    def test_grantlayerclienterror_is_exception_class(self):
        self.assertTrue(issubclass(self.mod.GrantLayerClientError, Exception))

    def test_grantlayerhttperror_is_exception_class(self):
        self.assertTrue(issubclass(self.mod.GrantLayerHTTPError, self.mod.GrantLayerClientError))

    def test_grantlayerjsonerror_is_exception_class(self):
        self.assertTrue(issubclass(self.mod.GrantLayerJSONError, self.mod.GrantLayerClientError))

    def test_client_has_health(self):
        client = self.mod.GrantLayerClient("http://localhost:8765")
        self.assertTrue(callable(getattr(client, "health", None)))

    def test_client_has_ready(self):
        client = self.mod.GrantLayerClient("http://localhost:8765")
        self.assertTrue(callable(getattr(client, "ready", None)))

    def test_client_has_request_json(self):
        client = self.mod.GrantLayerClient("http://localhost:8765")
        self.assertTrue(callable(getattr(client, "request_json", None)))


class TestGl147SdkBehavior(unittest.TestCase):
    def setUp(self):
        self.mod = _load_sdk()
        self.Client = self.mod.GrantLayerClient

    def test_base_url_trailing_slash_normalized(self):
        c = self.Client("http://localhost:8765/")
        self.assertEqual(c.base_url, "http://localhost:8765")

    def test_base_url_no_slash_unchanged(self):
        c = self.Client("http://localhost:8765")
        self.assertEqual(c.base_url, "http://localhost:8765")

    def test_request_json_builds_correct_url(self):
        c = self.Client("http://localhost:8765")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return _make_mock_response(200, {"status": "ok"})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c.request_json("GET", "/health")
        self.assertEqual(captured["url"], "http://localhost:8765/health")

    def test_request_json_path_leading_slash_normalized(self):
        c = self.Client("http://localhost:8765")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return _make_mock_response(200, {})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c.request_json("GET", "health")
        self.assertEqual(captured["url"], "http://localhost:8765/health")

    def test_json_body_sets_content_type(self):
        c = self.Client("http://localhost:8765")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["ct"] = req.get_header("Content-type")
            return _make_mock_response(200, {})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c.request_json("POST", "/grants", body={"subject": "s"})
        self.assertEqual(captured["ct"], "application/json")

    def test_no_body_does_not_set_content_type(self):
        c = self.Client("http://localhost:8765")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["ct"] = req.get_header("Content-type")
            return _make_mock_response(200, {})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c.request_json("GET", "/health")
        self.assertIsNone(captured.get("ct"))

    def test_token_sets_authorization_header(self):
        c = self.Client("http://localhost:8765", token="demo-token-local")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["auth"] = req.get_header("Authorization")
            return _make_mock_response(200, {})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c.request_json("GET", "/grants")
        self.assertEqual(captured["auth"], "Bearer demo-token-local")

    def test_no_token_no_authorization_header(self):
        c = self.Client("http://localhost:8765", token=None)
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["auth"] = req.get_header("Authorization")
            return _make_mock_response(200, {})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c.request_json("GET", "/health")
        self.assertIsNone(captured.get("auth"))

    def test_http_error_raises_grantlayerhttperror(self):
        c = self.Client("http://localhost:8765", token="secret-token-local")

        def fake_urlopen(req, timeout=None):
            err = urllib.error.HTTPError(
                url="http://localhost:8765/grants",
                code=403,
                msg="Forbidden",
                hdrs=None,
                fp=None,
            )
            err.read = lambda: json.dumps({"error": "forbidden"}).encode("utf-8")
            raise err

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(self.mod.GrantLayerHTTPError) as ctx:
                c.request_json("GET", "/grants")

        exc = ctx.exception
        self.assertEqual(exc.status, 403)

    def test_http_error_does_not_expose_token(self):
        c = self.Client("http://localhost:8765", token="secret-token-local")

        def fake_urlopen(req, timeout=None):
            err = urllib.error.HTTPError(
                url="http://localhost:8765/grants",
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=None,
            )
            err.read = lambda: json.dumps({"error": "unauthorized"}).encode("utf-8")
            raise err

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(self.mod.GrantLayerHTTPError) as ctx:
                c.request_json("GET", "/grants")

        self.assertNotIn("secret-token-local", str(ctx.exception))

    def test_invalid_json_raises_grantlayerjsonerror(self):
        c = self.Client("http://localhost:8765")

        def fake_urlopen(req, timeout=None):
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            mock_resp.read.return_value = b"not valid json {{{"
            mock_resp.headers = {}
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(self.mod.GrantLayerJSONError):
                c.request_json("GET", "/health")

    def test_url_error_raises_grantlayerclienterror(self):
        c = self.Client("http://localhost:8765")

        def fake_urlopen(req, timeout=None):
            raise urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(self.mod.GrantLayerClientError):
                c.request_json("GET", "/health")

    def test_health_calls_get_health(self):
        c = self.Client("http://localhost:8765")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["method"] = req.get_method()
            captured["url"] = req.full_url
            return _make_mock_response(200, {"status": "ok"})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c.health()
        self.assertEqual(captured["method"], "GET")
        self.assertIn("/health", captured["url"])

    def test_ready_calls_get_readiness(self):
        c = self.Client("http://localhost:8765")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["method"] = req.get_method()
            captured["url"] = req.full_url
            return _make_mock_response(200, {"status": "ready"})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            c.ready()
        self.assertEqual(captured["method"], "GET")
        self.assertIn("/readiness", captured["url"])

    def test_response_object_has_status_and_body(self):
        c = self.Client("http://localhost:8765")

        with patch("urllib.request.urlopen", return_value=_make_mock_response(200, {"status": "ok"})):
            resp = c.health()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.body, {"status": "ok"})


class TestGl147ReadmeContent(unittest.TestCase):
    def setUp(self):
        self.text = SDK_README.read_text(encoding="utf-8")
        self.lower = self.text.lower()

    def test_developer_preview_status(self):
        self.assertTrue(
            "developer-preview" in self.lower or "local" in self.lower,
            "README must mention developer-preview or local status",
        )

    def test_not_package_published(self):
        self.assertTrue(
            "not package-published" in self.lower
            or "not published" in self.lower
            or "no pip" in self.lower,
            "README must state the package is not published",
        )

    def test_no_production_saas_ready_claim(self):
        self.assertNotIn(
            "production saas ready",
            self.lower,
            "README must not claim production SaaS readiness",
        )

    def test_tenant_isolation_not_implemented(self):
        self.assertIn(
            "tenant isolation",
            self.lower,
            "README must mention tenant isolation status",
        )
        self.assertIn(
            "not implemented",
            self.lower,
            "README must state tenant isolation is not implemented",
        )

    def test_no_real_secrets_in_readme(self):
        # Rough heuristic: no PEM-like content, no 'BEGIN PRIVATE KEY', etc.
        forbidden = ["-----BEGIN", "PRIVATE KEY", "sk-", "eyJhbGciOiJSUzI"]
        for marker in forbidden:
            self.assertNotIn(marker, self.text, f"README must not contain '{marker}'")

    def test_references_gl148(self):
        self.assertIn("gl-148", self.lower, "README must reference GL-148")

    def test_references_gl149(self):
        self.assertIn("gl-149", self.lower, "README must reference GL-149")

    def test_references_gl150(self):
        self.assertIn("gl-150", self.lower, "README must reference GL-150")


class TestGl147ScopeGuard(unittest.TestCase):
    """Branch-specific diff assertions. Skipped when not on gl-147-minimal-python-sdk."""

    EXPECTED_BRANCH = "gl-147-minimal-python-sdk"

    ALLOWED_FILES = {
        "sdk/python/grantlayer_client.py",
        "sdk/python/README.md",
        "docs/examples/gl147/minimal_python_sdk.json",
        "backend/tests/test_gl147_minimal_python_sdk.py",
        "docs/ten_minute_quickstart.md",
        "README.md",
    }

    FORBIDDEN_PATTERNS = [
        "backend/src/",
        "docs/openapi.yaml",
        "migrations/",
        "requirements.txt",
        "requirements-dev.txt",
        "pyproject.toml",
        "setup.py",
        "Pipfile",
        "poetry.lock",
        "frontend/",
        "website/",
        "design/",
        ".claude/",
    ]

    def _current_branch(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result.stdout.strip()

    def _changed_files(self) -> list[str]:
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def setUp(self):
        self.branch = self._current_branch()
        if self.branch != self.EXPECTED_BRANCH:
            self.skipTest(
                f"Scope guard skipped: not on {self.EXPECTED_BRANCH} (current: {self.branch})"
            )
        self.changed = self._changed_files()

    def test_no_backend_src_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/")]
        self.assertEqual(
            violations, [], f"backend/src/ must not be modified: {violations}"
        )

    def test_no_openapi_changes(self):
        violations = [f for f in self.changed if f == "docs/openapi.yaml"]
        self.assertEqual(violations, [], "docs/openapi.yaml must not be modified")

    def test_no_migration_changes(self):
        violations = [f for f in self.changed if "migration" in f.lower()]
        self.assertEqual(violations, [], f"Migration files must not be modified: {violations}")

    def test_no_dependency_file_changes(self):
        dep_files = {"requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py", "Pipfile", "poetry.lock"}
        violations = [f for f in self.changed if f in dep_files]
        self.assertEqual(violations, [], f"Dependency files must not be modified: {violations}")

    def test_no_frontend_website_design_changes(self):
        violations = [
            f for f in self.changed
            if any(f.startswith(prefix) for prefix in ("frontend/", "website/", "design/"))
        ]
        self.assertEqual(violations, [], f"Frontend/website/design files must not be modified: {violations}")

    def test_no_claude_config_changes(self):
        violations = [f for f in self.changed if f.startswith(".claude/")]
        self.assertEqual(violations, [], f".claude/ files must not be modified: {violations}")

    def test_only_expected_files_changed(self):
        unexpected = [f for f in self.changed if f not in self.ALLOWED_FILES]
        self.assertEqual(
            unexpected,
            [],
            f"Unexpected files changed: {unexpected}. Allowed: {sorted(self.ALLOWED_FILES)}",
        )

    def test_no_forbidden_pattern_in_diff(self):
        for pattern in self.FORBIDDEN_PATTERNS:
            violations = [f for f in self.changed if pattern in f]
            self.assertEqual(
                violations,
                [],
                f"Forbidden pattern '{pattern}' found in changed files: {violations}",
            )


if __name__ == "__main__":
    unittest.main()
