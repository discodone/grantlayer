"""GL-203B OpenAPI / API Contract Cleanup tests.

Verifies that docs/openapi.yaml is updated, parseable, and accurately
reflects the GL-203B contract cleanup decisions. Also verifies that
required documentation artifacts exist and contain correct claim boundaries.
"""

import json
import os
import subprocess
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

OPENAPI_PATH = REPO_ROOT / "docs" / "openapi.yaml"
DOC_PATH = REPO_ROOT / "docs" / "openapi_api_contract_cleanup.md"
ARTIFACT_PATH = REPO_ROOT / "docs" / "examples" / "gl203b" / "openapi_api_contract_cleanup.json"


def _read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _changed_files() -> list:
    """Return files changed vs main (committed) plus any staged/unstaged local changes."""
    committed = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    local_staged = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    local_unstaged = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    combined = set()
    for result in [committed, local_staged, local_unstaged, untracked]:
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                combined.add(line)
    return sorted(combined)


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# 1. OpenAPI file existence and parseability
# ---------------------------------------------------------------------------

class TestGL203BOpenAPIExists(unittest.TestCase):

    def test_openapi_yaml_exists(self):
        self.assertTrue(OPENAPI_PATH.exists(), "docs/openapi.yaml must exist")

    def test_openapi_yaml_parseable(self):
        content = _read_text(OPENAPI_PATH)
        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError as e:
            self.fail(f"docs/openapi.yaml is not valid YAML: {e}")
        self.assertIsInstance(doc, dict, "docs/openapi.yaml must parse to a dict")


# ---------------------------------------------------------------------------
# 2. OpenAPI metadata and version
# ---------------------------------------------------------------------------

class TestGL203BOpenAPIMetadata(unittest.TestCase):

    def setUp(self):
        content = _read_text(OPENAPI_PATH)
        self.openapi = yaml.safe_load(content)
        self.info = self.openapi.get("info", {})
        self.description = self.info.get("description", "").lower()
        self.version = self.info.get("version", "")

    def test_version_not_stale_gl031(self):
        self.assertNotEqual(
            self.version,
            "0.31.0-rc",
            "OpenAPI version must not be the stale GL-031 value '0.31.0-rc'"
        )

    def test_version_contains_developer_preview_or_preview(self):
        v = self.version.lower()
        self.assertTrue(
            "developer" in v or "preview" in v or "dev" in v,
            f"OpenAPI version should reflect Developer Preview state, got: {self.version}"
        )

    def test_description_not_empty(self):
        self.assertTrue(len(self.description) > 50, "OpenAPI description must be substantive")

    def test_description_not_stale_gl031_reference(self):
        self.assertNotIn(
            "gl-031",
            self.description,
            "OpenAPI description must not reference stale GL-031 baseline"
        )

    def test_description_not_claim_production_saas(self):
        desc = self.description
        self.assertFalse(
            "production saas ready" in desc or "production-ready saas" in desc,
            "OpenAPI description must not claim production SaaS readiness"
        )

    def test_description_not_claim_official_sdk(self):
        desc = self.description
        self.assertFalse(
            "official sdk" in desc and "available" in desc,
            "OpenAPI description must not claim official SDK availability"
        )

    def test_description_not_claim_real_customer_data_ready(self):
        desc = self.description
        # Check does not positively claim readiness for real customer data.
        # Phrases like "not ready for real customer data" are acceptable.
        # Only flag if something asserts positive readiness.
        import re as _re
        positive_claim = bool(_re.search(
            r'(?<!not\s)(?<!not-)ready for real customer',
            desc
        ))
        self.assertFalse(
            positive_claim,
            "OpenAPI description must not positively claim readiness for real customer data"
        )

    def test_description_has_developer_preview_caveat(self):
        desc = self.description
        self.assertTrue(
            "developer preview" in desc or "controlled preview" in desc,
            "OpenAPI description must state Developer Preview or Controlled Preview status"
        )

    def test_description_has_tenant_context_note(self):
        desc = self.description
        self.assertTrue(
            "tenant" in desc and ("server" in desc or "derived" in desc or "server-derived" in desc),
            "OpenAPI description must document tenant context as server-derived"
        )

    def test_description_has_workspace_id_note(self):
        desc = self.description
        self.assertTrue(
            "workspace_id" in desc or "workspace" in desc,
            "OpenAPI description must mention workspace_id reserved/deferred status"
        )

    def test_description_has_correlation_id_note(self):
        desc = self.description
        self.assertTrue(
            "correlation" in desc or "x-correlation-id" in desc,
            "OpenAPI description must mention X-Correlation-ID header"
        )


# ---------------------------------------------------------------------------
# 3. Security schemes
# ---------------------------------------------------------------------------

class TestGL203BSecuritySchemes(unittest.TestCase):

    def setUp(self):
        content = _read_text(OPENAPI_PATH)
        self.openapi = yaml.safe_load(content)
        self.schemes = self.openapi.get("components", {}).get("securitySchemes", {})

    def test_security_schemes_exist(self):
        self.assertGreater(len(self.schemes), 0, "OpenAPI must define at least one security scheme")

    def test_legacy_admin_token_scheme_present(self):
        self.assertIn("LegacyAdminToken", self.schemes, "LegacyAdminToken security scheme must be defined")

    def test_operator_token_scheme_present(self):
        self.assertIn("OperatorToken", self.schemes, "OperatorToken security scheme must be defined")

    def test_legacy_admin_token_not_expose_tenant_override(self):
        scheme = self.schemes.get("LegacyAdminToken", {})
        desc = scheme.get("description", "").lower()
        self.assertFalse(
            "tenant override" in desc,
            "LegacyAdminToken scheme must not document arbitrary tenant override"
        )

    def test_operator_token_not_expose_tenant_override(self):
        scheme = self.schemes.get("OperatorToken", {})
        desc = scheme.get("description", "").lower()
        self.assertFalse(
            "tenant override" in desc,
            "OperatorToken scheme must not document arbitrary tenant override"
        )

    def test_operator_token_describes_server_derived_tenant(self):
        scheme = self.schemes.get("OperatorToken", {})
        desc = scheme.get("description", "").lower()
        self.assertTrue(
            "tenant" in desc and ("server" in desc or "derived" in desc or "operator record" in desc),
            "OperatorToken description must note tenant context is server-derived"
        )


# ---------------------------------------------------------------------------
# 4. Public vs protected endpoints
# ---------------------------------------------------------------------------

class TestGL203BEndpointSecurity(unittest.TestCase):

    def setUp(self):
        content = _read_text(OPENAPI_PATH)
        self.openapi = yaml.safe_load(content)
        self.paths = self.openapi.get("paths", {})

    def _get_security(self, path: str, method: str):
        endpoint = self.paths.get(path, {})
        op = endpoint.get(method, {})
        return op.get("security", None)

    def test_health_is_public(self):
        if "/health" not in self.paths:
            self.skipTest("/health not in OpenAPI")
        security = self._get_security("/health", "get")
        self.assertIsNone(security, "/health must not require auth (no security field)")

    def test_readiness_is_public(self):
        if "/readiness" not in self.paths:
            self.skipTest("/readiness not in OpenAPI")
        security = self._get_security("/readiness", "get")
        self.assertIsNone(security, "/readiness must not require auth (no security field)")

    def test_grants_post_has_security(self):
        if "/grants" not in self.paths:
            self.skipTest("/grants not in OpenAPI")
        security = self._get_security("/grants", "post")
        self.assertIsNotNone(security, "POST /grants must have security requirements")
        self.assertGreater(len(security), 0, "POST /grants must have at least one security scheme")

    def test_audit_events_has_security(self):
        if "/audit-events" not in self.paths:
            self.skipTest("/audit-events not in OpenAPI")
        security = self._get_security("/audit-events", "get")
        self.assertIsNotNone(security, "GET /audit-events must have security requirements")

    def test_demo_action_has_security(self):
        if "/demo-action" not in self.paths:
            self.skipTest("/demo-action not in OpenAPI")
        security = self._get_security("/demo-action", "post")
        self.assertIsNotNone(security, "POST /demo-action must have security requirements")
        self.assertGreater(len(security), 0, "POST /demo-action must require auth")

    def test_demo_tamper_has_security_or_is_guarded(self):
        tamper_path = "/demo/tamper-grant/{id}"
        if tamper_path not in self.paths:
            self.skipTest("/demo/tamper-grant/{id} not in OpenAPI")
        endpoint = self.paths.get(tamper_path, {})
        op = endpoint.get("post", {})
        desc = op.get("description", "").lower()
        security = op.get("security", None)
        has_guard_described = (
            "demo" in desc and ("disabled" in desc or "enable_demo" in desc or "403" in desc or "guarded" in desc)
        ) or security is not None
        self.assertTrue(
            has_guard_described,
            "Demo tamper endpoint must document its safety guard or have security requirements"
        )


# ---------------------------------------------------------------------------
# 5. Tenant context — no arbitrary override header
# ---------------------------------------------------------------------------

class TestGL203BTenantContract(unittest.TestCase):

    def setUp(self):
        content = _read_text(OPENAPI_PATH)
        self.openapi = yaml.safe_load(content)
        self.paths = self.openapi.get("paths", {})
        self.text = content.lower()

    def test_no_arbitrary_tenant_override_header_documented(self):
        suspicious = [
            "x-tenant-id",
            "x-tenant-override",
            "tenant-override",
        ]
        for header in suspicious:
            self.assertNotIn(
                header,
                self.text,
                f"OpenAPI must not document arbitrary tenant override header '{header}'"
            )

    def test_tenant_context_documented_as_server_derived(self):
        self.assertTrue(
            "server-derived" in self.text or
            "server derived" in self.text or
            ("tenant" in self.text and "server" in self.text and "derived" in self.text),
            "OpenAPI must document tenant context as server-derived"
        )

    def test_workspace_id_documented_as_reserved_or_deferred(self):
        self.assertTrue(
            "workspace_id" in self.text or "workspace" in self.text,
            "OpenAPI must mention workspace_id reserved/deferred status"
        )

    def test_workspace_id_deferred_or_reserved_noted(self):
        lower = self.text
        self.assertTrue(
            ("workspace" in lower) and (
                "reserved" in lower or "deferred" in lower or "nullable" in lower or
                "not enforced" in lower or "not currently enforced" in lower
            ),
            "OpenAPI must note workspace_id is reserved/nullable/deferred"
        )


# ---------------------------------------------------------------------------
# 6. Schema correctness — AuditEvent GL-200B fields
# ---------------------------------------------------------------------------

class TestGL203BAuditEventSchema(unittest.TestCase):

    def setUp(self):
        content = _read_text(OPENAPI_PATH)
        self.openapi = yaml.safe_load(content)
        self.schemas = self.openapi.get("components", {}).get("schemas", {})
        self.audit_schema = self.schemas.get("AuditEvent", {})

    def test_audit_event_schema_exists(self):
        self.assertIn("AuditEvent", self.schemas, "AuditEvent schema must be defined")

    def test_audit_event_has_tenant_id_field(self):
        props = self.audit_schema.get("properties", {})
        self.assertIn(
            "tenant_id",
            props,
            "AuditEvent schema must include tenant_id field (GL-200B)"
        )

    def test_audit_event_tenant_id_is_nullable(self):
        props = self.audit_schema.get("properties", {})
        tenant_id = props.get("tenant_id", {})
        self.assertTrue(
            tenant_id.get("nullable", False) is True,
            "AuditEvent.tenant_id must be nullable (pre-migration events have null tenant_id)"
        )

    def test_audit_event_has_workspace_id_field(self):
        props = self.audit_schema.get("properties", {})
        self.assertIn(
            "workspace_id",
            props,
            "AuditEvent schema must include workspace_id field (GL-200B)"
        )

    def test_audit_event_has_row_hash_field(self):
        props = self.audit_schema.get("properties", {})
        self.assertIn(
            "row_hash",
            props,
            "AuditEvent schema must include row_hash field (tamper-evidence chain)"
        )

    def test_audit_event_has_scope_field(self):
        props = self.audit_schema.get("properties", {})
        self.assertIn(
            "scope",
            props,
            "AuditEvent schema must include scope field (GL-200B)"
        )


# ---------------------------------------------------------------------------
# 7. ComplianceReadinessSummary schema defined
# ---------------------------------------------------------------------------

class TestGL203BComplianceReadinessSummarySchema(unittest.TestCase):

    def setUp(self):
        content = _read_text(OPENAPI_PATH)
        self.openapi = yaml.safe_load(content)
        self.schemas = self.openapi.get("components", {}).get("schemas", {})

    def test_compliance_readiness_summary_schema_defined(self):
        self.assertIn(
            "ComplianceReadinessSummary",
            self.schemas,
            "ComplianceReadinessSummary schema must be defined in components/schemas (was referenced but missing before GL-203B)"
        )

    def test_compliance_readiness_summary_has_record_type(self):
        schema = self.schemas.get("ComplianceReadinessSummary", {})
        props = schema.get("properties", {})
        self.assertIn("recordType", props, "ComplianceReadinessSummary must have recordType property")

    def test_compliance_readiness_summary_has_readiness_status(self):
        schema = self.schemas.get("ComplianceReadinessSummary", {})
        props = schema.get("properties", {})
        self.assertIn("readinessStatus", props, "ComplianceReadinessSummary must have readinessStatus property")


# ---------------------------------------------------------------------------
# 8. /operators/me response schema
# ---------------------------------------------------------------------------

class TestGL203BOperatorsMeSchema(unittest.TestCase):

    def setUp(self):
        content = _read_text(OPENAPI_PATH)
        self.openapi = yaml.safe_load(content)
        self.paths = self.openapi.get("paths", {})

    def test_operators_me_has_tenant_id_field(self):
        if "/operators/me" not in self.paths:
            self.skipTest("/operators/me not in OpenAPI")
        op = self.paths["/operators/me"].get("get", {})
        schema = op.get("responses", {}).get("200", {}).get("content", {}) \
                   .get("application/json", {}).get("schema", {})
        props = schema.get("properties", {})
        self.assertTrue(
            "tenantId" in props,
            "/operators/me 200 response schema must include tenantId field"
        )

    def test_operators_me_has_active_field(self):
        if "/operators/me" not in self.paths:
            self.skipTest("/operators/me not in OpenAPI")
        op = self.paths["/operators/me"].get("get", {})
        schema = op.get("responses", {}).get("200", {}).get("content", {}) \
                   .get("application/json", {}).get("schema", {})
        props = schema.get("properties", {})
        self.assertTrue(
            "active" in props,
            "/operators/me 200 response schema must include active field"
        )


# ---------------------------------------------------------------------------
# 9. Documentation file existence and content
# ---------------------------------------------------------------------------

class TestGL203BDocExists(unittest.TestCase):

    def test_doc_exists(self):
        self.assertTrue(DOC_PATH.exists(), "docs/openapi_api_contract_cleanup.md must exist")

    def test_artifact_exists(self):
        self.assertTrue(ARTIFACT_PATH.exists(), "docs/examples/gl203b/openapi_api_contract_cleanup.json must exist")

    def test_artifact_valid_json(self):
        self.assertTrue(ARTIFACT_PATH.exists(), "Artifact must exist before parsing")
        with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                self.fail(f"GL-203B JSON artifact is not valid JSON: {e}")
        self.assertIsInstance(data, dict, "GL-203B artifact must be a JSON object")


class TestGL203BArtifactContent(unittest.TestCase):

    def setUp(self):
        with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_issue_id_is_gl203b(self):
        self.assertEqual(
            self.data.get("issue_id"),
            "GL-203B",
            "Artifact issue_id must be GL-203B"
        )

    def test_decision_is_allowed(self):
        decision = self.data.get("decision", "")
        forbidden_decisions = ["publish_sdk", "official_sdk", "production_saas_ready"]
        for bad in forbidden_decisions:
            self.assertNotIn(
                bad, decision.lower(),
                f"Artifact decision must not contain '{bad}'"
            )
        self.assertTrue(len(decision) > 0, "Artifact must have a non-empty decision")

    def test_sdk_readiness_impact_exists(self):
        self.assertIn(
            "sdk_readiness_impact",
            self.data,
            "Artifact must include sdk_readiness_impact field"
        )

    def test_sdk_not_implemented(self):
        sdk_impact = self.data.get("sdk_readiness_impact", {})
        self.assertFalse(
            sdk_impact.get("sdk_implemented", True),
            "Artifact must confirm SDK was not implemented in GL-203B"
        )

    def test_sdk_not_claimed(self):
        sdk_impact = self.data.get("sdk_readiness_impact", {})
        self.assertFalse(
            sdk_impact.get("sdk_claimed", True),
            "Artifact must confirm SDK is not claimed"
        )

    def test_package_publishing_avoided(self):
        sdk_impact = self.data.get("sdk_readiness_impact", {})
        self.assertFalse(
            sdk_impact.get("package_publishing", True),
            "Artifact must confirm no package publishing"
        )

    def test_remaining_gaps_exist(self):
        gaps = self.data.get("remaining_gaps", [])
        self.assertGreater(len(gaps), 0, "Artifact must document remaining gaps")

    def test_recommended_next_issues_include_gl203c_as_conditional(self):
        issues = self.data.get("recommended_next_issues", [])
        gl203c_entries = [i for i in issues if "GL-203C" in str(i.get("issue", ""))]
        self.assertGreater(
            len(gl203c_entries),
            0,
            "Artifact recommended_next_issues must include GL-203C"
        )
        for entry in gl203c_entries:
            self.assertTrue(
                entry.get("conditional", False) is True,
                "GL-203C must be marked as conditional in recommended_next_issues"
            )

    def test_recommended_next_issues_include_gl204(self):
        issues = self.data.get("recommended_next_issues", [])
        gl204_entries = [i for i in issues if "GL-204" in str(i.get("issue", ""))]
        self.assertGreater(
            len(gl204_entries),
            0,
            "Artifact recommended_next_issues must include GL-204"
        )

    def test_safety_confirmations_no_production_saas(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_production_saas_claim", False),
            "Artifact must confirm no production SaaS claim"
        )

    def test_safety_confirmations_tenant_not_overclaimed(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("tenant_workspace_isolation_not_overclaimed", False),
            "Artifact must confirm tenant/workspace isolation not overclaimed"
        )

    def test_safety_confirmations_no_real_customer_data(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_real_customer_private_grant_data_readiness_claimed", False),
            "Artifact must confirm no real customer/private grant data readiness claimed"
        )

    def test_safety_confirmations_no_official_sdk(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_official_sdk_claimed", False),
            "Artifact must confirm no official SDK claimed"
        )

    def test_safety_confirmations_no_backend_src_changes(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_backend_src_changes", False),
            "Artifact must confirm no backend/src changes"
        )

    def test_safety_confirmations_no_api_behavior_changes(self):
        confirmations = self.data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_api_behavior_changes", False),
            "Artifact must confirm no API behavior changes"
        )


class TestGL203BDocContent(unittest.TestCase):

    def setUp(self):
        self.doc = _read_text(DOC_PATH).lower()

    def test_doc_states_developer_preview(self):
        self.assertTrue(
            "developer preview" in self.doc or "controlled preview" in self.doc,
            "Doc must state Developer Preview / Controlled Preview status"
        )

    def test_doc_states_not_production_saas(self):
        self.assertTrue(
            "not production saas" in self.doc or "not a production saas" in self.doc,
            "Doc must state this is not a production SaaS"
        )

    def test_doc_states_not_ready_for_real_customer_data(self):
        self.assertTrue(
            "not ready for real customer" in self.doc or
            "not ready for private grant" in self.doc or
            "real customer data" in self.doc,
            "Doc must state not ready for real customer/private grant data"
        )

    def test_doc_states_no_official_sdk_claimed(self):
        self.assertTrue(
            "no official sdk" in self.doc or "not claimed" in self.doc or
            "not published" in self.doc,
            "Doc must state no official SDK/package is claimed"
        )

    def test_doc_routes_security_reports_to_advisories(self):
        self.assertTrue(
            "github security advisories" in self.doc or "security advisories" in self.doc,
            "Doc must route security-sensitive reports to GitHub Security Advisories"
        )

    def test_doc_includes_no_exploit_details(self):
        lower = self.doc
        self.assertFalse(
            "exploit" in lower and "how to" in lower,
            "Doc must not include exploit guidance"
        )

    def test_doc_includes_no_real_secrets(self):
        self.assertNotIn(
            "-----begin rsa private key-----",
            self.doc,
            "Doc must not include real private keys"
        )
        self.assertNotIn(
            "-----begin openssh private key-----",
            self.doc,
            "Doc must not include real private keys"
        )

    def test_doc_has_gl203b_issue_id(self):
        self.assertIn("gl-203b", self.doc, "Doc must reference GL-203B issue ID")

    def test_doc_has_remaining_gaps(self):
        self.assertIn("remaining gap", self.doc, "Doc must document remaining gaps")

    def test_doc_has_sdk_readiness_impact(self):
        self.assertIn("sdk", self.doc, "Doc must discuss SDK-readiness impact")

    def test_doc_has_recommended_next_issues(self):
        self.assertTrue(
            "gl-203c" in self.doc or "gl-204" in self.doc,
            "Doc must include recommended next issues (GL-203C or GL-204)"
        )


# ---------------------------------------------------------------------------
# 10. Scope guard — allowed files only
# ---------------------------------------------------------------------------

ALLOWED_CHANGED_FILE_PATTERNS = [
    "docs/openapi.yaml",
    "docs/openapi_api_contract_cleanup.md",
    "docs/examples/gl203b/",
    "backend/tests/test_gl203b_openapi_api_contract_cleanup.py",
    # Optional allowed files per issue spec
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/api_contract_sdk_packaging_decision.md",
]

FORBIDDEN_CHANGED_FILE_PATTERNS = [
    "backend/src/",
    "backend/src/migrations/",
    "requirements",
    "setup.py",
    "pyproject.toml",
    "sdk/python/grantlayer_client.py",
    "frontend/",
    "website/",
    ".github/workflows/",
    "scripts/publish",
    "scripts/snapshot",
]

EXPECTED_BRANCH = "gl-203b-openapi-api-contract-cleanup"


class TestGL203BScopeGuard(unittest.TestCase):

    def setUp(self):
        self.branch = _current_branch()
        if self.branch != EXPECTED_BRANCH:
            self.skipTest(
                f"Scope guard skipped: not on {EXPECTED_BRANCH} (current: {self.branch})"
            )
        self.changed = _changed_files()

    def test_no_backend_src_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/")]
        self.assertEqual(
            violations,
            [],
            f"backend/src/ must not be modified in GL-203B: {violations}"
        )

    def test_no_migration_changes(self):
        violations = [f for f in self.changed if f.startswith("backend/src/migrations/")]
        self.assertEqual(
            violations,
            [],
            f"Migrations must not be modified in GL-203B: {violations}"
        )

    def test_no_dependency_file_changes(self):
        dep_files = {"requirements.txt", "requirements-dev.txt", "setup.py", "pyproject.toml"}
        violations = [f for f in self.changed if f in dep_files]
        self.assertEqual(
            violations,
            [],
            f"Dependency files must not be modified in GL-203B: {violations}"
        )

    def test_no_sdk_implementation_changes(self):
        violations = [f for f in self.changed if f == "sdk/python/grantlayer_client.py"]
        self.assertEqual(
            violations,
            [],
            f"sdk/python/grantlayer_client.py must not be modified in GL-203B: {violations}"
        )

    def test_no_frontend_website_design_changes(self):
        violations = [
            f for f in self.changed
            if f.startswith("frontend/") or f.startswith("website/") or f.startswith("design/")
        ]
        self.assertEqual(
            violations,
            [],
            f"frontend/website/design must not be modified in GL-203B: {violations}"
        )

    def test_no_github_workflow_changes(self):
        violations = [f for f in self.changed if f.startswith(".github/workflows/")]
        self.assertEqual(
            violations,
            [],
            f".github/workflows/ must not be modified in GL-203B: {violations}"
        )

    def test_no_snapshot_publish_script_changes(self):
        violations = [
            f for f in self.changed
            if "snapshot" in f and f.startswith("scripts/")
        ]
        self.assertEqual(
            violations,
            [],
            f"Snapshot publish scripts must not be modified in GL-203B: {violations}"
        )

    def test_openapi_yaml_is_changed(self):
        self.assertIn(
            "docs/openapi.yaml",
            self.changed,
            "docs/openapi.yaml must be changed in GL-203B"
        )

    def test_doc_is_created(self):
        self.assertIn(
            "docs/openapi_api_contract_cleanup.md",
            self.changed,
            "docs/openapi_api_contract_cleanup.md must be created in GL-203B"
        )

    def test_artifact_is_created(self):
        artifact_path = "docs/examples/gl203b/openapi_api_contract_cleanup.json"
        self.assertIn(
            artifact_path,
            self.changed,
            f"{artifact_path} must be created in GL-203B"
        )

    def test_test_file_is_created(self):
        test_path = "backend/tests/test_gl203b_openapi_api_contract_cleanup.py"
        self.assertIn(
            test_path,
            self.changed,
            f"{test_path} must be created in GL-203B"
        )


# ---------------------------------------------------------------------------
# 11. No GitHub push / public publish verification (declarative)
# ---------------------------------------------------------------------------

class TestGL203BPublishBoundary(unittest.TestCase):
    """These tests verify the publish boundary via git remote state."""

    def test_no_public_remote_push_occurred(self):
        result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        remotes = result.stdout.lower()
        # If there is a public GitHub remote, ensure GL-203B branch is not pushed there
        # This is a declarative check — we cannot prevent push after-the-fact,
        # but we verify the remote state does not include unexpected public endpoints.
        self.assertNotIn(
            "github.com/discodone/grantlayer",
            remotes,
            "GL-203B must not be pushed to the public GitHub repository"
        )


if __name__ == "__main__":
    unittest.main()
