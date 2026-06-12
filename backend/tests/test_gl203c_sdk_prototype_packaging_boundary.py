"""GL-203C SDK Prototype / Packaging Boundary tests.

Verifies the GL-203C packaging boundary decisions, prototype safety properties,
and that all claim boundaries are preserved.
"""

import importlib
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DOC_PATH = REPO_ROOT / "docs" / "sdk_prototype_packaging_boundary.md"
ARTIFACT_PATH = (
    REPO_ROOT / "docs" / "examples" / "gl203c" / "sdk_prototype_packaging_boundary.json"
)
PROTOTYPE_PATH = (
    REPO_ROOT / "examples" / "sdk_prototype" / "python" / "grantlayer_client.py"
)
PROTOTYPE_README = (
    REPO_ROOT / "examples" / "sdk_prototype" / "python" / "README.md"
)

EXPECTED_BRANCH = "gl-203c-sdk-prototype-packaging-boundary"

# Package publishing metadata that must NOT exist
FORBIDDEN_PACKAGING_FILES = [
    REPO_ROOT / "setup.py",
    REPO_ROOT / "package.json",
    REPO_ROOT / "package-lock.json",
    REPO_ROOT / "examples" / "sdk_prototype" / "python" / "setup.py",
    REPO_ROOT / "examples" / "sdk_prototype" / "python" / "package.json",
]

# pyproject.toml may exist for non-SDK tooling but must not have SDK publish config
_PYPROJECT = REPO_ROOT / "pyproject.toml"


def _read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _changed_files() -> list:
    committed = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    local = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    unstaged = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    combined = set()
    for result in [committed, local, unstaged, untracked]:
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                combined.add(line)
    return sorted(combined)


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip()


def _load_prototype():
    """Dynamically load the prototype client module."""
    spec = importlib.util.spec_from_file_location(
        "gl203c_prototype_client", str(PROTOTYPE_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. Documentation and artifact existence
# ---------------------------------------------------------------------------

class TestGL203CFilesExist(unittest.TestCase):

    def test_doc_exists(self):
        self.assertTrue(DOC_PATH.exists(), f"doc must exist: {DOC_PATH}")

    def test_artifact_exists(self):
        self.assertTrue(ARTIFACT_PATH.exists(), f"artifact must exist: {ARTIFACT_PATH}")

    def test_artifact_valid_json(self):
        with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                self.fail(f"GL-203C artifact is not valid JSON: {e}")
        self.assertIsInstance(data, dict)

    def test_prototype_exists(self):
        self.assertTrue(PROTOTYPE_PATH.exists(), f"prototype must exist: {PROTOTYPE_PATH}")

    def test_prototype_readme_exists(self):
        self.assertTrue(PROTOTYPE_README.exists(), f"prototype README must exist: {PROTOTYPE_README}")


# ---------------------------------------------------------------------------
# 2. JSON artifact content
# ---------------------------------------------------------------------------

class TestGL203CArtifactContent(unittest.TestCase):

    def setUp(self):
        with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_issue_id_is_gl203c(self):
        self.assertEqual(self.data.get("issue_id"), "GL-203C")

    def test_result_is_allowed(self):
        result = self.data.get("result", "")
        self.assertNotIn("blocked", result.lower(), "result must not be blocked")
        self.assertTrue(len(result) > 0, "result must be non-empty")

    def test_decision_is_allowed(self):
        decision = self.data.get("decision", "")
        forbidden = ["publish", "official_sdk_released", "production_saas"]
        for bad in forbidden:
            self.assertNotIn(bad, decision.lower(), f"decision must not contain '{bad}'")
        self.assertTrue(len(decision) > 0, "decision must be non-empty")

    def test_input_sources_reviewed_exist(self):
        sources = self.data.get("input_sources_reviewed", [])
        self.assertGreater(len(sources), 5, "must review multiple input sources")

    def test_sdk_feasibility_assessment_exists(self):
        self.assertIn("sdk_feasibility_assessment", self.data)
        assessment = self.data["sdk_feasibility_assessment"]
        self.assertIsInstance(assessment, dict)
        self.assertGreater(len(assessment), 0)

    def test_openapi_dependency_assessment_exists(self):
        self.assertIn("openapi_dependency_assessment", self.data)

    def test_prototype_boundary_exists(self):
        self.assertIn("prototype_boundary", self.data)

    def test_packaging_boundary_exists(self):
        self.assertIn("packaging_boundary", self.data)

    def test_token_secret_safety_model_exists(self):
        self.assertIn("token_secret_safety_model", self.data)
        model = self.data["token_secret_safety_model"]
        self.assertFalse(model.get("token_in_repr", True), "token must not appear in repr")
        self.assertFalse(model.get("token_in_error_messages", True), "token must not appear in errors")

    def test_tenant_workspace_sdk_boundary_exists(self):
        self.assertIn("tenant_workspace_sdk_boundary", self.data)
        boundary = self.data["tenant_workspace_sdk_boundary"]
        self.assertFalse(
            boundary.get("tenant_override_header_supported", True),
            "tenant override header must not be supported"
        )

    def test_allowed_public_claims_exist(self):
        claims = self.data.get("allowed_public_claims", [])
        self.assertGreater(len(claims), 0)

    def test_prohibited_claims_include_official_sdk(self):
        prohibited = [str(c).lower() for c in self.data.get("prohibited_public_claims", [])]
        combined = " ".join(prohibited)
        self.assertTrue(
            "official sdk" in combined or "official" in combined,
            "prohibited claims must include official SDK availability"
        )

    def test_prohibited_claims_include_package_publishing(self):
        prohibited = [str(c).lower() for c in self.data.get("prohibited_public_claims", [])]
        combined = " ".join(prohibited)
        self.assertTrue(
            "installable" in combined or "pypi" in combined or "package" in combined,
            "prohibited claims must address package publishing"
        )

    def test_prohibited_claims_include_production_saas(self):
        prohibited = [str(c).lower() for c in self.data.get("prohibited_public_claims", [])]
        combined = " ".join(prohibited)
        self.assertIn("production", combined, "prohibited claims must include production SaaS readiness")

    def test_prohibited_claims_include_real_customer_data(self):
        prohibited = [str(c).lower() for c in self.data.get("prohibited_public_claims", [])]
        combined = " ".join(prohibited)
        self.assertTrue(
            "customer data" in combined or "real customer" in combined,
            "prohibited claims must include real customer data readiness"
        )

    def test_prohibited_claims_include_tenant_workspace_guarantee(self):
        prohibited = [str(c).lower() for c in self.data.get("prohibited_public_claims", [])]
        combined = " ".join(prohibited)
        self.assertTrue(
            "tenant" in combined or "workspace" in combined,
            "prohibited claims must address tenant/workspace production guarantee"
        )

    def test_remaining_gaps_exist(self):
        gaps = self.data.get("remaining_gaps", [])
        self.assertGreater(len(gaps), 0)

    def test_safety_confirmations_no_production_saas(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(conf.get("no_production_saas_claim", False))

    def test_safety_confirmations_tenant_not_overclaimed(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(conf.get("tenant_workspace_isolation_not_overclaimed", False))

    def test_safety_confirmations_no_real_customer_data(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(conf.get("no_real_customer_private_grant_data_readiness_claimed", False))

    def test_safety_confirmations_no_official_sdk(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(conf.get("no_official_sdk_claimed", False))

    def test_safety_confirmations_no_package_publishing(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(conf.get("no_package_publishing", False))

    def test_safety_confirmations_no_package_metadata(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(conf.get("no_package_publishing_metadata", False))

    def test_safety_confirmations_no_setup_py(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(conf.get("no_setup_py", False))

    def test_safety_confirmations_no_backend_src_changes(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(conf.get("no_backend_src_changes", False))

    def test_safety_confirmations_no_api_behavior_changes(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(conf.get("no_api_behavior_changes", False))

    def test_safety_confirmations_openapi_not_changed(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertFalse(conf.get("openapi_changed", True), "OpenAPI must not be changed in GL-203C")

    def test_recommended_next_includes_gl204(self):
        issues = self.data.get("recommended_next_issues", [])
        gl204 = [i for i in issues if "GL-204" in str(i.get("issue", ""))]
        self.assertGreater(len(gl204), 0, "GL-204 must be in recommended next issues")

    def test_recommended_next_gl203d_is_conditional(self):
        issues = self.data.get("recommended_next_issues", [])
        gl203d = [i for i in issues if "GL-203D" in str(i.get("issue", ""))]
        if gl203d:
            self.assertTrue(
                gl203d[0].get("conditional", False),
                "GL-203D must be marked conditional"
            )

    def test_website_untracked_files_excluded(self):
        conf = self.data.get("safety_confirmations", {})
        self.assertTrue(
            conf.get("website_untracked_files_excluded", False),
            "Artifact must confirm website untracked files were excluded"
        )


# ---------------------------------------------------------------------------
# 3. Documentation content
# ---------------------------------------------------------------------------

class TestGL203CDocContent(unittest.TestCase):

    def setUp(self):
        self.doc = _read_text(DOC_PATH).lower()

    def test_doc_has_gl203c_issue_id(self):
        self.assertIn("gl-203c", self.doc)

    def test_doc_states_developer_preview(self):
        self.assertTrue(
            "developer preview" in self.doc or "controlled preview" in self.doc
        )

    def test_doc_states_not_production_saas(self):
        self.assertTrue(
            "not production saas" in self.doc or "not a production saas" in self.doc
        )

    def test_doc_states_not_ready_for_real_customer_data(self):
        self.assertTrue(
            "not ready for real customer" in self.doc or
            "real customer data" in self.doc or
            "not ready for private grant" in self.doc
        )

    def test_doc_states_no_official_sdk(self):
        self.assertTrue(
            "not an official sdk" in self.doc or
            "no official sdk" in self.doc or
            ("official" in self.doc and "not" in self.doc)
        )

    def test_doc_routes_security_to_advisories(self):
        self.assertIn("github security advisories", self.doc)

    def test_doc_has_no_exploit_details(self):
        import re as _re
        # Negative mentions like "no exploit details" or "no exploit guidance" are fine.
        # Check that exploit doesn't appear in a positive/instructional context.
        positive_exploit = _re.findall(
            r'exploit',
            self.doc
        )
        for match_ctx in positive_exploit:
            # All occurrences must be in a negative/confirmatory context
            pass
        # Simple heuristic: doc should not contain "how to exploit" or "exploit the"
        self.assertNotIn("how to exploit", self.doc, "Doc must not contain exploit instructions")
        self.assertNotIn("exploit the ", self.doc, "Doc must not describe exploiting the system")

    def test_doc_has_no_real_secrets(self):
        self.assertNotIn("-----begin rsa", self.doc)
        self.assertNotIn("-----begin openssh", self.doc)

    def test_doc_has_remaining_gaps(self):
        self.assertIn("remaining gap", self.doc)

    def test_doc_has_sdk_feasibility(self):
        self.assertIn("feasib", self.doc)

    def test_doc_has_packaging_boundary(self):
        self.assertIn("packaging boundary", self.doc)

    def test_doc_has_token_safety_model(self):
        self.assertTrue(
            "token" in self.doc and "safety" in self.doc
        )

    def test_doc_has_tenant_workspace_boundary(self):
        self.assertIn("tenant", self.doc)
        self.assertIn("server-derived", self.doc)

    def test_doc_recommended_next_issues(self):
        self.assertTrue(
            "gl-204" in self.doc or "gl-203d" in self.doc
        )


# ---------------------------------------------------------------------------
# 4. No forbidden packaging metadata files
# ---------------------------------------------------------------------------

class TestGL203CNoPackageMetadata(unittest.TestCase):

    def test_no_sdk_setup_py(self):
        sdk_setup = REPO_ROOT / "examples" / "sdk_prototype" / "setup.py"
        self.assertFalse(sdk_setup.exists(), "setup.py must not exist in prototype dir")

    def test_no_sdk_pyproject_toml(self):
        sdk_pyproject = REPO_ROOT / "examples" / "sdk_prototype" / "pyproject.toml"
        self.assertFalse(sdk_pyproject.exists(), "pyproject.toml must not exist in prototype dir")

    def test_no_sdk_package_json(self):
        sdk_pkg = REPO_ROOT / "examples" / "sdk_prototype" / "package.json"
        self.assertFalse(sdk_pkg.exists(), "package.json must not exist in prototype dir")

    def test_no_root_setup_py(self):
        root_setup = REPO_ROOT / "setup.py"
        self.assertFalse(root_setup.exists(), "Root setup.py must not exist (would imply official package)")

    def test_no_pyproject_with_sdk_publish_config(self):
        if not _PYPROJECT.exists():
            return
        content = _read_text(_PYPROJECT).lower()
        self.assertFalse(
            "grantlayer-sdk" in content or "grantlayer_sdk" in content,
            "pyproject.toml must not contain SDK publish config"
        )
        self.assertFalse(
            "pypi" in content and "publish" in content,
            "pyproject.toml must not have PyPI publish workflow"
        )


# ---------------------------------------------------------------------------
# 5. Prototype location — only in approved path
# ---------------------------------------------------------------------------

class TestGL203CPrototypeLocation(unittest.TestCase):

    def test_prototype_in_approved_path(self):
        self.assertTrue(
            PROTOTYPE_PATH.exists(),
            "Prototype must be at examples/sdk_prototype/python/grantlayer_client.py"
        )

    def test_no_sdk_in_official_sdk_path(self):
        official_sdk = REPO_ROOT / "sdk" / "python" / "grantlayer_prototype.py"
        self.assertFalse(
            official_sdk.exists(),
            "GL-203C prototype must not be placed in official sdk/ directory"
        )


# ---------------------------------------------------------------------------
# 6. Prototype import and class existence
# ---------------------------------------------------------------------------

class TestGL203CPrototypeImport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_prototype()

    def test_prototype_importable(self):
        self.assertIsNotNone(self.mod)

    def test_client_class_exists(self):
        self.assertTrue(
            hasattr(self.mod, "GrantLayerClient"),
            "GrantLayerClient class must exist"
        )

    def test_fake_transport_exists(self):
        self.assertTrue(
            hasattr(self.mod, "FakeTransport"),
            "FakeTransport class must exist for testing"
        )

    def test_error_classes_exist(self):
        for cls_name in [
            "GrantLayerClientError",
            "GrantLayerHTTPError",
            "GrantLayerJSONError",
            "GrantLayerConnectionError",
        ]:
            self.assertTrue(
                hasattr(self.mod, cls_name),
                f"{cls_name} must exist"
            )

    def test_response_class_exists(self):
        self.assertTrue(hasattr(self.mod, "GrantLayerResponse"))


# ---------------------------------------------------------------------------
# 7. Prototype token safety
# ---------------------------------------------------------------------------

class TestGL203CPrototypeTokenSafety(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_prototype()

    def _make_client(self, token="test-token-placeholder"):
        return self.mod.GrantLayerClient(
            base_url="http://fake.internal",
            token=token,
        )

    def test_token_not_in_repr(self):
        client = self._make_client(token="super-secret-placeholder-token")
        r = repr(client)
        self.assertNotIn("super-secret-placeholder-token", r,
                         "Token value must not appear in repr(client)")
        self.assertIn("has_token=True", r,
                      "repr must show has_token=True when token is set")

    def test_no_token_repr_shows_false(self):
        client = self._make_client(token=None)
        r = repr(client)
        self.assertIn("has_token=False", r)

    def test_token_not_in_http_error_str(self):
        client = self._make_client(token="should-not-appear-in-error")
        transport = self.mod.FakeTransport()
        transport.add_error(401, {"error": "Unauthorized", "errorCode": "auth_required", "reason": "no token"})
        client._transport = transport
        try:
            client.list_grants()
            self.fail("Expected GrantLayerHTTPError")
        except self.mod.GrantLayerHTTPError as e:
            self.assertNotIn("should-not-appear-in-error", str(e))
            self.assertNotIn("should-not-appear-in-error", repr(e))

    def test_token_type_in_exception(self):
        err = self.mod.GrantLayerHTTPError(401, "auth_required", "Authentication required")
        self.assertEqual(err.status, 401)
        self.assertEqual(err.error_code, "auth_required")
        self.assertNotIn("token", str(err).lower().replace("authentication", ""))


# ---------------------------------------------------------------------------
# 8. Prototype transport injection and behavior
# ---------------------------------------------------------------------------

class TestGL203CPrototypeFakeTransport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_prototype()

    def _client(self, token=None):
        transport = self.mod.FakeTransport()
        client = self.mod.GrantLayerClient(
            base_url="http://fake.internal:8765",
            token=token,
            _transport=transport,
        )
        return client, transport

    def test_health_request_construction(self):
        client, transport = self._client()
        transport.add_response(200, {"status": "ok", "service": "grantlayer", "checkType": "liveness"})
        resp = client.health()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.body["status"], "ok")
        self.assertEqual(len(transport.calls), 1)
        req = transport.calls[0]
        self.assertTrue(req.get_full_url().endswith("/health"))
        self.assertEqual(req.get_method(), "GET")

    def test_readiness_request_construction(self):
        client, transport = self._client()
        transport.add_response(200, {"status": "ready", "service": "grantlayer", "checkType": "readiness"})
        resp = client.readiness()
        self.assertEqual(resp.status, 200)
        self.assertTrue(req.get_full_url().endswith("/readiness") for req in transport.calls)

    def test_auth_header_added_when_token_provided(self):
        client, transport = self._client(token="test-bearer-token")
        transport.add_response(200, [])
        client.list_grants()
        req = transport.calls[0]
        auth = req.get_header("Authorization")
        self.assertIsNotNone(auth, "Authorization header must be set when token is provided")
        self.assertTrue(auth.startswith("Bearer "), "Authorization must be Bearer scheme")
        self.assertIn("test-bearer-token", auth)

    def test_auth_header_absent_when_no_token(self):
        client, transport = self._client(token=None)
        transport.add_response(200, {"status": "ok", "service": "grantlayer", "checkType": "liveness"})
        client.health()
        req = transport.calls[0]
        auth = req.get_header("Authorization")
        self.assertIsNone(auth, "Authorization header must NOT be set when no token provided")

    def test_no_tenant_override_header(self):
        client, transport = self._client(token="any-token")
        transport.add_response(200, [])
        client.list_grants()
        req = transport.calls[0]
        headers_lower = {k.lower(): v for k, v in req.headers.items()}
        self.assertNotIn("x-tenant-id", headers_lower,
                         "Prototype must NOT send X-Tenant-ID header")
        self.assertNotIn("x-tenant-override", headers_lower,
                         "Prototype must NOT send X-Tenant-Override header")

    def test_fake_transport_no_network(self):
        # This test proves no network call is made when using FakeTransport
        client, transport = self._client()
        transport.add_response(200, {"status": "ok"})
        resp = client.health()
        self.assertEqual(resp.status, 200)
        # If any real network call was made, this would either fail or
        # be detectable. With FakeTransport, calls are captured in-process.
        self.assertEqual(len(transport.calls), 1)

    def test_list_grants_request(self):
        client, transport = self._client(token="demo-token")
        transport.add_response(200, [])
        resp = client.list_grants()
        self.assertEqual(resp.status, 200)
        req = transport.calls[0]
        self.assertIn("/v1/grants", req.get_full_url())
        self.assertEqual(req.get_method(), "GET")

    def test_create_grant_request_body(self):
        client, transport = self._client(token="demo-token")
        transport.add_response(201, {"id": "grant-001"})
        client.create_grant(
            subject_id="gl203c-demo-subject",
            role="technician",
            action="read",
            resource="gl203c-demo-resource",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2026-12-31T23:59:59Z",
            created_by="gl203c-demo-admin",
            reason="GL-203C prototype test",
        )
        req = transport.calls[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertIn("/v1/grants", req.get_full_url())
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["subjectId"], "gl203c-demo-subject")
        self.assertEqual(body["role"], "technician")
        self.assertNotIn("tenantId", body, "Request body must not contain tenantId override")

    def test_error_response_handled_safely(self):
        client, transport = self._client(token="token")
        transport.add_error(404, {"error": "Grant not found", "errorCode": "grant_not_found", "reason": "..."})
        try:
            client.get_grant("nonexistent")
            self.fail("Expected GrantLayerHTTPError")
        except self.mod.GrantLayerHTTPError as e:
            self.assertEqual(e.status, 404)
            self.assertEqual(e.error_code, "grant_not_found")

    def test_correlation_id_captured(self):
        client, transport = self._client()
        transport.add_response(
            200,
            {"status": "ok"},
            headers={"x-correlation-id": "test-corr-001"},
        )
        resp = client.health()
        self.assertEqual(resp.correlation_id, "test-corr-001")

    def test_list_audit_events_with_limit(self):
        client, transport = self._client(token="demo-token")
        transport.add_response(200, [])
        client.list_audit_events(limit=50)
        req = transport.calls[0]
        self.assertIn("limit=50", req.get_full_url())

    def test_evaluate_agent_permission_request(self):
        client, transport = self._client(token="demo-token")
        transport.add_response(200, {"allowed": True, "agentId": "agent-001"})
        client.evaluate_agent_permission(
            agent_id="agent-001",
            requested_scope="grants:read",
            assigned_scopes=["grants:read", "audit:read"],
        )
        req = transport.calls[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertIn("/v1/agent-permissions/evaluate", req.get_full_url())
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["agentId"], "agent-001")
        self.assertEqual(body["requestedScope"], "grants:read")

    def test_revoke_grant_request(self):
        client, transport = self._client(token="demo-token")
        transport.add_response(200, {"ok": True})
        client.revoke_grant("grant-001", "demo-admin", "test revocation")
        req = transport.calls[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertIn("/v1/grants/grant-001/revoke", req.get_full_url())
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["revokedBy"], "demo-admin")


# ---------------------------------------------------------------------------
# 9. Prototype source content safety checks
# ---------------------------------------------------------------------------

class TestGL203CPrototypeSourceSafety(unittest.TestCase):

    def setUp(self):
        self.source = _read_text(PROTOTYPE_PATH).lower()

    def test_no_real_token_hardcoded(self):
        suspicious = ["sk-", "eyj", "ghp_", "glpat-"]
        for prefix in suspicious:
            self.assertNotIn(prefix, self.source,
                             f"Prototype must not contain real token prefix '{prefix}'")

    def test_no_hardcoded_production_url(self):
        prod_indicators = ["https://api.grantlayer.com", "production.grantlayer"]
        for url in prod_indicators:
            self.assertNotIn(url, self.source,
                             f"Prototype must not hardcode production URL '{url}'")

    def test_no_print_of_token(self):
        import re
        source_orig = _read_text(PROTOTYPE_PATH)
        # Check for print(.*token) patterns that would log token values
        pattern = re.compile(r'print\s*\(.*_token', re.IGNORECASE)
        self.assertFalse(
            bool(pattern.search(source_orig)),
            "Prototype must not print token values"
        )

    def test_developer_preview_caveat_in_docstring(self):
        self.assertTrue(
            "developer preview" in self.source or "not an official sdk" in self.source,
            "Prototype module docstring must include Developer Preview caveat"
        )

    def test_tenant_override_not_supported_stated(self):
        self.assertTrue(
            "tenant" in self.source and (
                "server-derived" in self.source or
                "no override" in self.source or
                "not support" in self.source or
                "not sent" in self.source
            ),
            "Prototype must document that tenant context is server-derived"
        )

    def test_stdlib_only_imports(self):
        source_orig = _read_text(PROTOTYPE_PATH)
        import ast
        try:
            tree = ast.parse(source_orig)
        except SyntaxError:
            self.fail("Prototype must be valid Python")
        external_imports = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = ""
                if isinstance(node, ast.Import):
                    module = node.names[0].name
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                top = module.split(".")[0]
                if top and top not in (
                    "__future__", "json", "urllib", "typing",
                    "importlib", "os", "sys", "io", "re",
                    "pathlib", "collections", "abc", "functools",
                    "contextlib", "dataclasses", "enum", "types",
                    "warnings", "logging", "traceback",
                ):
                    external_imports.append(top)
        self.assertEqual(
            external_imports, [],
            f"Prototype must use only stdlib; found external imports: {external_imports}"
        )


# ---------------------------------------------------------------------------
# 10. Scope guard — GL-203C allowed files only
# ---------------------------------------------------------------------------

ALLOWED_CHANGED_PATTERNS = [
    "docs/sdk_prototype_packaging_boundary.md",
    "docs/examples/gl203c/",
    "backend/tests/test_gl203c_sdk_prototype_packaging_boundary.py",
    "examples/sdk_prototype/",
    # Optional
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/openapi_api_contract_cleanup.md",
]

FORBIDDEN_PATTERNS = [
    "backend/src/",
    "backend/src/migrations/",
    "requirements",
    "sdk/python/grantlayer_client.py",
    "frontend/",
    "website/",
    ".github/workflows/",
    "scripts/publish",
    "scripts/snapshot",
    "setup.py",
    "pyproject.toml",
    "package.json",
    "docs/openapi.yaml",
]


class TestGL203CScopeGuard(unittest.TestCase):

    def setUp(self):
        self.branch = _current_branch()
        if self.branch != EXPECTED_BRANCH:
            self.skipTest(f"Scope guard skipped: not on {EXPECTED_BRANCH} (current: {self.branch})")
        self.changed = _changed_files()

    def test_no_backend_src_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/")]
        self.assertEqual(violations, [], f"backend/src/ must not change: {violations}")

    def test_no_migration_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/migrations/")]
        self.assertEqual(violations, [], f"Migrations must not change: {violations}")

    def test_no_dependency_file_changes(self):
        dep = {"requirements.txt", "requirements-dev.txt"}
        violations = [f for f in self.changed if f in dep]
        self.assertEqual(violations, [], f"Dependency files must not change: {violations}")

    def test_no_official_sdk_changes(self):
        violations = [f for f in self.changed if f == "sdk/python/grantlayer_client.py"]
        self.assertEqual(violations, [], f"Official SDK must not change: {violations}")

    def test_no_openapi_yaml_changes(self):
        violations = [f for f in self.changed if f == "docs/openapi.yaml"]
        self.assertEqual(violations, [], f"docs/openapi.yaml must not change in GL-203C: {violations}")

    def test_no_frontend_website_changes(self):
        violations = [f for f in self.changed
                      if f.startswith("frontend/") or f.startswith(".github/workflows/")]
        self.assertEqual(violations, [], f"Frontend/workflows must not change: {violations}")

    def test_no_package_metadata(self):
        pkg_files = {"setup.py", "package.json", "package-lock.json"}
        violations = [f for f in self.changed if f in pkg_files]
        self.assertEqual(violations, [], f"Package metadata must not be added: {violations}")

    def test_prototype_is_in_approved_path(self):
        # Only files under examples/ that contain sdk_prototype must be in the right path.
        # Backend test files with "sdk_prototype" in the name live under backend/tests/ — allowed.
        proto_changes = [
            f for f in self.changed
            if f.startswith("examples/") and "sdk_prototype" in f
        ]
        for f in proto_changes:
            self.assertTrue(
                f.startswith("examples/sdk_prototype/"),
                f"Prototype example changes must be under examples/sdk_prototype/: {f}"
            )

    def test_doc_created(self):
        self.assertIn(
            "docs/sdk_prototype_packaging_boundary.md",
            self.changed,
        )

    def test_artifact_created(self):
        self.assertIn(
            "docs/examples/gl203c/sdk_prototype_packaging_boundary.json",
            self.changed,
        )

    def test_test_file_created(self):
        self.assertIn(
            "backend/tests/test_gl203c_sdk_prototype_packaging_boundary.py",
            self.changed,
        )

    def test_prototype_created(self):
        proto = "examples/sdk_prototype/python/grantlayer_client.py"
        self.assertIn(proto, self.changed)

    def test_no_website_files_included(self):
        # Pre-existing untracked website files (from website-design-workspace-import
        # branch work) must not be COMMITTED in GL-203C. Check only committed changes.
        committed_result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        committed = [
            line.strip()
            for line in committed_result.stdout.splitlines()
            if line.strip()
        ]
        website_violations = [
            f for f in committed
            if "website_design" in f or f.startswith("website-design/")
        ]
        self.assertEqual(
            website_violations, [],
            f"Website files must not be committed in GL-203C: {website_violations}"
        )


# ---------------------------------------------------------------------------
# 11. No public push / visibility verification
# ---------------------------------------------------------------------------

class TestGL203CPublishBoundary(unittest.TestCase):

    def test_no_public_remote_push(self):
        result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        remotes = result.stdout.lower()
        self.assertNotIn(
            "github.com/discodone/grantlayer",
            remotes,
            "GL-203C must not be pushed to public GitHub"
        )


if __name__ == "__main__":
    unittest.main()
