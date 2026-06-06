"""Tests for GL-215 Tenant / Workspace Production Guarantee."""

from __future__ import annotations

import datetime
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "tenant_workspace_production_guarantee.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl215",
    "tenant_workspace_production_guarantee.json",
)

ADMIN_TOKEN = "gl215-strong-admin-token-xyz123"

REQUIRED_INPUT_SOURCES = [
    "docs/production_readiness_gap_report_v4.md",
    "docs/examples/gl213/production_readiness_gap_report_v4.json",
    "docs/production_iam_operator_control_completion.md",
    "docs/examples/gl214/production_iam_operator_control_completion.json",
    "docs/admin_operator_tenant_control_plane.md",
    "docs/examples/gl206/admin_operator_tenant_control_plane.json",
    "docs/tenant_workspace_api_audit_regression_completion.md",
    "docs/examples/gl200c/tenant_workspace_api_audit_regression_completion.json",
    "docs/tenant_workspace_isolation_implementation_baseline.md",
    "docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json",
    "docs/tenant_workspace_isolation_design_pack.md",
    "docs/examples/gl200a/tenant_workspace_isolation_design_pack.json",
    "docs/production_auth_secrets_config_hardening.md",
    "docs/examples/gl201/production_auth_secrets_config_hardening.json",
    "docs/runtime_abuse_incident_hardening.md",
    "docs/examples/gl208/runtime_abuse_incident_hardening.json",
    "docs/data_governance_audit_operations.md",
    "docs/examples/gl209/data_governance_audit_operations.json",
    "docs/public_external_review_readiness_gate_pack.md",
    "docs/examples/gl212/public_external_review_readiness_gate_pack.json",
    "docs/live_postgres_validation_execution_gl206b.md",
    "docs/examples/gl206b/live_postgres_validation_execution_gl206b.json",
    "docs/openapi.yaml",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
]

ALLOWED_CHANGED_FILES = {
    "backend/src/server.py",
    "backend/src/grants.py",
    "backend/tests/test_gl215_tenant_workspace_production_guarantee.py",
    "docs/tenant_workspace_production_guarantee.md",
    "docs/examples/gl215/tenant_workspace_production_guarantee.json",
}


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _run_git(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _branch_changed_files() -> set[str]:
    changed = set(_run_git(["diff", "--name-only", "main...HEAD"]))
    status_lines = _run_git(["status", "--porcelain", "--untracked-files=all"])
    for line in status_lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        path = parts[1]
        if path.startswith("docs/website_design_") or path.startswith("website-design/"):
            continue
        changed.add(path)
    return changed


def _make_db() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _future(days: int = 30) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


def _past(days: int = 1) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


def _reload_modules(db_path: str):
    os.environ["GRANTLAYER_DB"] = db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)
    os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
    os.environ["GRANTLAYER_ADMIN_TOKEN"] = ADMIN_TOKEN
    os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
    os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
    os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
    os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)

    import src.config as config_mod
    importlib.reload(config_mod)

    import src.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import src.models as models_mod
    importlib.reload(models_mod)

    import src.operators as ops_mod
    importlib.reload(ops_mod)

    import src.auth as auth_mod
    importlib.reload(auth_mod)

    import src.grants as grants_mod
    importlib.reload(grants_mod)

    import src.grant_executions as exec_mod
    importlib.reload(exec_mod)

    import src.audit_log as audit_mod
    importlib.reload(audit_mod)

    import src.evidence_verification as evidence_verification_mod
    importlib.reload(evidence_verification_mod)

    import src.server as server_mod
    importlib.reload(server_mod)

    return {
        "config": config_mod,
        "db": db_mod,
        "models": models_mod,
        "operators": ops_mod,
        "auth": auth_mod,
        "grants": grants_mod,
        "executions": exec_mod,
        "audit": audit_mod,
        "server": server_mod,
    }


def _run_handler(
    server_mod,
    path: str,
    method: str = "GET",
    auth_header: str | None = None,
    body: bytes = b"",
    extra_headers: dict | None = None,
) -> tuple[int, dict, bytes]:
    handler_class = server_mod.GrantLayerHandler
    handler = handler_class.__new__(handler_class)
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    headers: dict[str, str] = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    if body:
        headers["Content-Length"] = str(len(body))
    if extra_headers:
        headers.update(extra_headers)
    handler.headers = headers
    handler.path = path
    handler.command = method
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 0)
    handler.server = None
    if method == "GET":
        handler.do_GET()
    elif method == "POST":
        handler.do_POST()
    else:
        raise AssertionError(f"Unsupported method: {method}")
    handler.wfile.seek(0)
    response = handler.wfile.read()
    status = int(response.split(b"\r\n", 1)[0].split(b" ")[1])
    parts = response.split(b"\r\n\r\n", 1)
    body_out = json.loads(parts[1]) if len(parts) > 1 and parts[1] else {}
    return status, body_out, response


class TestGL215DocumentationArtifact(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.doc = _load_doc()

    def test_doc_and_json_exist_and_json_valid(self):
        self.assertTrue(os.path.isfile(DOC_PATH))
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(self.data, dict)

    def test_issue_id_result_and_decision(self):
        self.assertEqual(self.data["issue_id"], "GL-215")
        self.assertIn(self.data["result"], {"ready_for_merge", "blocked"})
        self.assertIn(self.data["decision"], {"ready_for_merge", "blocked"})

    def test_required_json_fields_present(self):
        required = [
            "title",
            "decision_rationale",
            "input_sources_reviewed",
            "current_tenant_workspace_state_summary",
            "production_tenant_workspace_gap_assessment",
            "implemented_hardening_summary",
            "tenant_id_derivation_model",
            "workspace_id_derivation_deferred_model",
            "cross_tenant_lookup_denial_behavior",
            "cross_tenant_mutation_denial_behavior",
            "admin_operator_tenant_boundary",
            "route_protection_filtering_model",
            "audit_tenant_workspace_propagation",
            "unsafe_override_prevention",
            "openapi_api_contract_implications",
            "migration_schema_implications",
            "production_readiness_impact",
            "controlled_preview_impact",
            "remaining_tenant_workspace_blockers",
            "risk_register",
            "findings",
            "safety_confirmations",
            "recommended_next_issues",
        ]
        for field in required:
            self.assertIn(field, self.data)
            self.assertTrue(self.data[field], field)

    def test_input_sources_reviewed_exist(self):
        reviewed = set(self.data["input_sources_reviewed"])
        for source in REQUIRED_INPUT_SOURCES:
            self.assertIn(source, reviewed)
            self.assertTrue(os.path.exists(os.path.join(REPO_ROOT, source)), source)

    def test_doc_states_required_boundaries(self):
        required_phrases = [
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS remains no-go",
            "Real customer data, private grant data, and institutional data remain no-go",
            "Official SDK/package remains no-go",
            "Compliance certification remains no-go",
            "production PostgreSQL readiness remains no-go",
            "synthetic/demo data only",
            "Security-sensitive reports route to GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase, self.doc)

    def test_safety_confirmations(self):
        sc = self.data["safety_confirmations"]
        for key in [
            "production_saas_no_go",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "compliance_certification_no_go",
            "live_postgresql_production_no_go",
            "ephemeral_postgres_validation_not_overclaimed",
            "controlled_preview_synthetic_demo_data_only",
            "github_security_advisories_for_sensitive_reports",
            "no_exploit_details_included",
            "no_real_secrets_included",
            "no_real_customer_private_data_included",
            "public_publish_avoided",
            "public_snapshot_export_avoided",
            "package_publishing_avoided",
            "package_metadata_avoided",
            "no_github_workflow_changes",
            "no_snapshot_publish_script_changes",
            "no_public_github_push",
            "no_public_publish",
            "no_visibility_change",
            "unrelated_website_design_import_files_excluded",
        ]:
            self.assertIs(sc.get(key), True, key)


class _BaseGL215Runtime(unittest.TestCase):
    ENV_KEYS = [
        "GRANTLAYER_DB",
        "GRANTLAYER_DATABASE_URL",
        "GRANTLAYER_RUNTIME_MODE",
        "GRANTLAYER_ADMIN_TOKEN",
        "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
        "GRANTLAYER_REQUIRE_CHALLENGE",
        "GRANTLAYER_ENABLE_DEMO_ENDPOINTS",
        "GRANTLAYER_ENABLE_OPERATOR_MODEL",
        "GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN",
    ]

    def setUp(self):
        self.saved_env = {k: os.environ.get(k) for k in self.ENV_KEYS}
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.models = self.mods["models"]
        self.ops = self.mods["operators"]
        self.grants = self.mods["grants"]
        self.executions = self.mods["executions"]
        self.db = self.mods["db"]
        self.server = self.mods["server"]
        self.op_a, self.token_a = self.ops.create_operator(
            "tenant-a-owner", "owner", "gl215-token-a", tenant_id="tenant_a"
        )
        self.op_b, self.token_b = self.ops.create_operator(
            "tenant-b-owner", "owner", "gl215-token-b", tenant_id="tenant_b"
        )

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _auth_a(self) -> str:
        return f"Bearer {self.token_a}"

    def _auth_b(self) -> str:
        return f"Bearer {self.token_b}"

    def _make_grant(self, tenant_id: str):
        grant = self.models.Grant(
            subject_id="subject-1",
            role="viewer",
            action="read",
            resource="resource-1",
            valid_from=_past(),
            valid_until=_future(),
            created_by="operator",
            reason="synthetic test grant",
        )
        self.grants.create_grant(grant, tenant_id=tenant_id)
        return grant

    def _make_execution(self, tenant_id: str, grant_id: str | None = None):
        execution = self.models.GrantExecution(
            grant_id=grant_id,
            action="read",
            resource="resource-1",
            operator_id="operator",
        )
        self.executions.create_grant_execution(execution, tenant_id=tenant_id)
        return execution


class TestGL215TenantWorkspaceRuntimeHardening(_BaseGL215Runtime):
    def test_secondary_execution_routes_deny_cross_tenant_lookup(self):
        execution = self._make_execution("tenant_a")
        routes = [
            f"/evidence/executions/{execution.id}",
            f"/evidence/executions/{execution.id}/export",
            f"/evidence/executions/{execution.id}/verify",
            f"/provenance/executions/{execution.id}/summary",
            f"/auditor/reports/executions/{execution.id}",
            f"/evidence/executions/{execution.id}/completeness",
            f"/compliance/gaps/executions/{execution.id}",
        ]
        for route in routes:
            with self.subTest(route=route):
                status, body, _ = _run_handler(
                    self.server,
                    route,
                    method="GET",
                    auth_header=self._auth_b(),
                )
                self.assertEqual(status, 404)
                self.assertEqual(body.get("errorCode"), "execution_not_found")

    def test_evidence_verify_cross_tenant_does_not_mutate_archive_status(self):
        execution = self._make_execution("tenant_a")
        self.db.execute(
            """
            INSERT INTO evidence_archives (
                id, evidence_hash, canonical_version, hash_algorithm,
                bundle_json, execution_id, grant_id, grant_request_id,
                created_at, stored_by, last_verified_at, last_verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, NULL, NULL)
            """,
            (
                execution.id,
                "0" * 64,
                "unsupported",
                "sha256",
                json.dumps({"canonicalVersion": "unsupported", "hashAlgorithm": "sha256", "evidenceHash": "0" * 64}),
                execution.id,
                _past(),
                "synthetic",
            ),
        )
        status, body, _ = _run_handler(
            self.server,
            f"/evidence/executions/{execution.id}/verify",
            method="GET",
            auth_header=self._auth_b(),
        )
        self.assertEqual(status, 404)
        self.assertEqual(body.get("errorCode"), "execution_not_found")
        row = self.db.query_one(
            "SELECT last_verification_status FROM evidence_archives WHERE execution_id = ?",
            (execution.id,),
        )
        self.assertIsNone(row["last_verification_status"])

    def test_demo_tamper_cross_tenant_mutation_denied(self):
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        mods = _reload_modules(self.db_path)
        self.server = mods["server"]
        self.grants = mods["grants"]
        grant = self._make_grant("tenant_a")
        status, body, _ = _run_handler(
            self.server,
            f"/demo/tamper-grant/{grant.id}",
            method="POST",
            auth_header=self._auth_b(),
            body=b"{}",
        )
        self.assertEqual(status, 404)
        self.assertEqual(body.get("errorCode"), "grant_not_found")
        row = self.db.query_one("SELECT role FROM grants WHERE id = ?", (grant.id,))
        self.assertEqual(row["role"], "viewer")

    def test_caller_tenant_and_workspace_override_ignored_on_grant_create(self):
        payload = {
            "subjectId": "subject-override",
            "role": "viewer",
            "action": "read",
            "resource": "resource-override",
            "validFrom": _past(),
            "validUntil": _future(),
            "createdBy": "caller",
            "reason": "synthetic override attempt",
            "tenantId": "tenant_b",
            "workspaceId": "workspace_b",
        }
        status, body, _ = _run_handler(
            self.server,
            "/grants",
            method="POST",
            auth_header=self._auth_a(),
            body=json.dumps(payload).encode(),
        )
        self.assertEqual(status, 201)
        row = self.db.query_one(
            "SELECT tenant_id, workspace_id FROM grants WHERE id = ?",
            (body["id"],),
        )
        self.assertEqual(row["tenant_id"], "tenant_a")
        self.assertIsNone(row["workspace_id"])

    def test_operator_admin_audit_events_preserve_safe_tenant_context(self):
        status, body, _ = _run_handler(
            self.server,
            "/admin/operators",
            method="POST",
            auth_header=f"Bearer {ADMIN_TOKEN}",
            body=json.dumps({
                "name": "tenant-a-auditor",
                "role": "auditor",
                "tenantId": "tenant_a",
            }).encode(),
        )
        self.assertEqual(status, 201)
        events = self.mods["audit"].list_events(tenant_id="tenant_a")
        event_dicts = [event.to_dict() for event in events]
        self.assertTrue(any(e["action"] == "operator_created" for e in event_dicts))
        serialized = json.dumps(event_dicts, sort_keys=True)
        forbidden = [
            "token_hash",
            "tokenLookupHash",
            "Authorization",
            "Bearer ",
            "GRANTLAYER_ADMIN_TOKEN",
            "postgres://",
            "private_key",
            ADMIN_TOKEN,
        ]
        for value in forbidden:
            self.assertNotIn(value, serialized)

    def test_health_and_readiness_public_behavior_preserved(self):
        for route in ["/health", "/readiness"]:
            status, body, _ = _run_handler(self.server, route, method="GET")
            self.assertIn(status, {200, 503})
            self.assertNotIn("tenantId", body)
            self.assertNotIn("workspaceId", body)


class TestGL215ForbiddenChangeGuards(unittest.TestCase):
    def test_changed_files_are_allowed_and_website_imports_excluded(self):
        changed = _branch_changed_files()
        disallowed = changed - ALLOWED_CHANGED_FILES
        self.assertFalse(disallowed, f"Unexpected changed files: {sorted(disallowed)}")
        self.assertNotIn("website-design/", changed)
        self.assertFalse(any(path.startswith("docs/website_design_") for path in changed))

    def test_forbidden_files_and_directories_absent_from_branch_changes(self):
        changed = _branch_changed_files()
        forbidden_exact = {
            "setup.py",
            "package.json",
            "package-lock.json",
        }
        forbidden_prefixes = (
            ".github/workflows/",
            "public-export/",
            "public-snapshot/",
            "release/",
            "releases/",
        )
        forbidden_suffixes = (
            "/setup.py",
            "/package.json",
            "/package-lock.json",
            "/pyproject.toml",
        )
        for path in changed:
            self.assertNotIn(path, forbidden_exact)
            self.assertFalse(path.startswith(forbidden_prefixes), path)
            self.assertFalse(path.endswith(forbidden_suffixes), path)
            self.assertFalse(path.startswith("scripts/") and "snapshot" in path.lower(), path)

    def test_no_forbidden_readiness_or_package_claims(self):
        combined = (_load_doc() + "\n" + json.dumps(_load_json(), sort_keys=True)).lower()
        forbidden_claims = [
            "is production saas ready",
            "production saas is ready",
            "ready for real customer data: yes",
            "ready for private grant data: yes",
            "official sdk is available",
            "is compliance certified",
            "gdpr ready: yes",
            "soc2 ready: yes",
            "iso ready: yes",
            "production postgresql ready: yes",
        ]
        for claim in forbidden_claims:
            self.assertNotIn(claim, combined)


if __name__ == "__main__":
    unittest.main()
