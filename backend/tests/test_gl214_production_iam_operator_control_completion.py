"""Tests for GL-214 Production IAM & Operator Control Completion."""

from __future__ import annotations

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
DOC_PATH = os.path.join(REPO_ROOT, "docs", "production_iam_operator_control_completion.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl214",
    "production_iam_operator_control_completion.json",
)

ADMIN_TOKEN = "gl214-strong-admin-token-xyz123"

ALLOWED_CHANGED_FILES = {
    "backend/src/server.py",
    "backend/tests/test_gl214_production_iam_operator_control_completion.py",
    "docs/production_iam_operator_control_completion.md",
    "docs/examples/gl214/production_iam_operator_control_completion.json",
}

REQUIRED_INPUT_SOURCES = [
    "docs/production_readiness_gap_report_v4.md",
    "docs/examples/gl213/production_readiness_gap_report_v4.json",
    "docs/public_external_review_readiness_gate_pack.md",
    "docs/examples/gl212/public_external_review_readiness_gate_pack.json",
    "docs/sdk_pilot_production_gate.md",
    "docs/examples/gl211/sdk_pilot_production_gate.json",
    "docs/live_postgres_validation_execution_gl206b.md",
    "docs/examples/gl206b/live_postgres_validation_execution_gl206b.json",
    "docs/admin_operator_tenant_control_plane.md",
    "docs/examples/gl206/admin_operator_tenant_control_plane.json",
    "docs/production_auth_secrets_config_hardening.md",
    "docs/examples/gl201/production_auth_secrets_config_hardening.json",
    "docs/runtime_abuse_incident_hardening.md",
    "docs/examples/gl208/runtime_abuse_incident_hardening.json",
    "docs/data_governance_audit_operations.md",
    "docs/examples/gl209/data_governance_audit_operations.json",
    "docs/tenant_workspace_api_audit_regression_completion.md",
    "docs/examples/gl200c/tenant_workspace_api_audit_regression_completion.json",
    "docs/tenant_workspace_isolation_implementation_baseline.md",
    "docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json",
    "docs/tenant_workspace_isolation_design_pack.md",
    "docs/examples/gl200a/tenant_workspace_isolation_design_pack.json",
    "docs/openapi.yaml",
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "backend/src/auth.py",
    "backend/src/config.py",
    "backend/src/operators.py",
    "backend/src/server.py",
    "backend/src/audit_log.py",
    "backend/src/db.py",
    "backend/src/models.py",
    "backend/src/grant_requests.py",
    "backend/tests/",
    "scripts/ops/",
    "examples/grant_lifecycle_evidence_bundle.py",
]


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


def _reload_modules(db_path: str):
    os.environ["GRANTLAYER_DB"] = db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)
    os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
    os.environ["GRANTLAYER_ADMIN_TOKEN"] = ADMIN_TOKEN
    os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
    os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
    os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)

    import src.config as config_mod
    importlib.reload(config_mod)

    import src.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import src.operators as ops_mod
    importlib.reload(ops_mod)

    import src.auth as auth_mod
    importlib.reload(auth_mod)

    import src.audit_log as audit_mod
    importlib.reload(audit_mod)

    import src.server as server_mod
    importlib.reload(server_mod)

    return config_mod, db_mod, ops_mod, auth_mod, audit_mod, server_mod


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


class TestGL214DocumentationArtifact(unittest.TestCase):
    def setUp(self):
        self.data = _load_json()
        self.doc = _load_doc()

    def test_doc_and_json_exist_and_json_valid(self):
        self.assertTrue(os.path.isfile(DOC_PATH))
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(self.data, dict)

    def test_issue_id_result_and_decision(self):
        self.assertEqual(self.data["issue_id"], "GL-214")
        self.assertIn(self.data["result"], {"ready_for_merge", "blocked"})
        self.assertIn(self.data["decision"], {"ready_for_merge", "blocked"})

    def test_required_json_fields_present(self):
        required = [
            "title",
            "decision_rationale",
            "input_sources_reviewed",
            "current_iam_operator_state_summary",
            "production_iam_gap_assessment",
            "implemented_hardening_summary",
            "admin_token_behavior",
            "operator_token_behavior",
            "revoked_inactive_operator_behavior",
            "operator_tenant_role_scope_boundary",
            "admin_operator_route_protection",
            "audit_coverage_for_iam_operator_actions",
            "token_secret_safety_model",
            "fail_closed_behavior",
            "production_readiness_impact",
            "controlled_preview_impact",
            "remaining_iam_blockers",
            "risk_register",
            "findings",
            "safety_confirmations",
            "recommended_next_issues",
        ]
        for field in required:
            self.assertIn(field, self.data)
            self.assertTrue(self.data[field])

    def test_input_sources_reviewed_exist(self):
        reviewed = set(self.data["input_sources_reviewed"])
        for source in REQUIRED_INPUT_SOURCES:
            self.assertIn(source, reviewed)
            path = os.path.join(REPO_ROOT, source.rstrip("/"))
            self.assertTrue(os.path.exists(path), source)

    def test_doc_states_required_boundaries(self):
        required_phrases = [
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS remains no-go",
            "Real customer data, private grant data, and institutional data remain no-go",
            "Official SDK/package remains no-go",
            "Compliance certification remains no-go",
            "production PostgreSQL readiness remains no-go",
            "Security-sensitive reports route to GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
            "synthetic/demo data only",
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
            "public_publish_avoided",
            "public_snapshot_export_avoided",
            "package_publishing_avoided",
            "package_metadata_avoided",
            "github_security_advisories_for_sensitive_reports",
            "no_exploit_details_included",
            "no_real_secrets_included",
            "no_real_customer_private_data_included",
            "no_github_workflow_changes",
            "no_snapshot_publish_script_changes",
            "no_public_github_push",
            "no_public_publish",
            "no_visibility_change",
            "unrelated_website_design_import_files_excluded",
        ]:
            self.assertTrue(sc.get(key), key)


class _BaseGL214Server(unittest.TestCase):
    ENV_KEYS = [
        "GRANTLAYER_DB",
        "GRANTLAYER_DATABASE_URL",
        "GRANTLAYER_RUNTIME_MODE",
        "GRANTLAYER_ADMIN_TOKEN",
        "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
        "GRANTLAYER_REQUIRE_CHALLENGE",
        "GRANTLAYER_ENABLE_OPERATOR_MODEL",
        "GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN",
    ]

    def setUp(self):
        self.saved_env = {k: os.environ.get(k) for k in self.ENV_KEYS}
        self.db_path = _make_db()
        (
            self.config_mod,
            self.db_mod,
            self.ops_mod,
            self.auth_mod,
            self.audit_mod,
            self.server_mod,
        ) = _reload_modules(self.db_path)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
        for k, v in self.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _admin_auth(self) -> str:
        return f"Bearer {ADMIN_TOKEN}"

    def _post_json(
        self,
        path: str,
        data: dict,
        auth_header: str | None = None,
        extra_headers: dict | None = None,
    ) -> tuple[int, dict, bytes]:
        return _run_handler(
            self.server_mod,
            path,
            method="POST",
            auth_header=auth_header,
            body=json.dumps(data).encode(),
            extra_headers=extra_headers,
        )

    def _get(
        self,
        path: str,
        auth_header: str | None = None,
        extra_headers: dict | None = None,
    ) -> tuple[int, dict, bytes]:
        return _run_handler(
            self.server_mod,
            path,
            method="GET",
            auth_header=auth_header,
            extra_headers=extra_headers,
        )

    def _create_operator(self, tenant_id: str = "tenant-a", role: str = "owner"):
        status, body, _raw = self._post_json(
            "/admin/operators",
            {"name": "Operator", "role": role, "tenantId": tenant_id},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 201, body)
        return body


class TestGL214ImplementationBehavior(_BaseGL214Server):
    def test_missing_admin_token_fails_closed_on_operator_create(self):
        status, body, raw = self._post_json(
            "/admin/operators",
            {"name": "Op", "role": "owner", "tenantId": "tenant-a"},
        )
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "admin_token_required")
        self.assertNotIn(ADMIN_TOKEN.encode(), raw)

    def test_invalid_admin_token_fails_closed_on_operator_create(self):
        status, body, raw = self._post_json(
            "/admin/operators",
            {"name": "Op", "role": "owner", "tenantId": "tenant-a"},
            auth_header="Bearer wrong-token",
        )
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "admin_token_invalid")
        self.assertNotIn(b"wrong-token", raw)

    def test_placeholder_admin_token_rejected_in_production_like_config(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "admin"
        importlib.reload(self.config_mod)
        errors = self.config_mod.startup_errors()
        self.assertTrue(any("GRANTLAYER_ADMIN_TOKEN" in err for err in errors))
        self.assertFalse(any("admin" == err for err in errors))

    def test_operator_token_cannot_create_operator(self):
        op = self._create_operator()
        status, body, raw = self._post_json(
            "/admin/operators",
            {"name": "Other", "role": "owner", "tenantId": "tenant-a"},
            auth_header=f"Bearer {op['token']}",
        )
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "admin_token_invalid")
        self.assertNotIn(op["token"].encode(), raw)

    def test_operator_token_cannot_revoke_operator(self):
        op = self._create_operator()
        status, body, raw = self._post_json(
            f"/admin/operators/{op['operatorId']}/revoke",
            {},
            auth_header=f"Bearer {op['token']}",
        )
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "admin_token_invalid")
        self.assertNotIn(op["token"].encode(), raw)

    def test_revoked_operator_token_cannot_authenticate(self):
        op = self._create_operator()
        status, body, _raw = self._post_json(
            f"/admin/operators/{op['operatorId']}/revoke",
            {},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 200, body)
        status, body, raw = self._get("/operators/me", auth_header=f"Bearer {op['token']}")
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")
        self.assertNotIn(op["token"].encode(), raw)

    def test_inactive_operator_cannot_authenticate(self):
        op, token = self.ops_mod.create_operator(
            name="Inactive",
            role="owner",
            token="gl214-inactive-token",
            tenant_id="tenant-a",
        )
        self.db_mod.execute("UPDATE operators SET active = 0 WHERE id = ?", (op.operator_id,))
        status, body, raw = self._get("/operators/me", auth_header=f"Bearer {token}")
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "operator_auth_required")
        self.assertNotIn(token.encode(), raw)

    def test_operator_tenant_id_cannot_be_overridden_by_header(self):
        op = self._create_operator(tenant_id="tenant-a")
        status, body, _raw = self._get(
            "/operators/me",
            auth_header=f"Bearer {op['token']}",
            extra_headers={"X-Tenant-ID": "tenant-b"},
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(body["tenantId"], "tenant-a")

    def test_admin_create_operator_requires_explicit_tenant_assignment(self):
        status, body, _raw = self._post_json(
            "/admin/operators",
            {"name": "Op", "role": "owner"},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "missing_required_fields")

    def test_admin_create_operator_rejects_unknown_role(self):
        status, body, _raw = self._post_json(
            "/admin/operators",
            {"name": "Op", "role": "superuser", "tenantId": "tenant-a"},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body.get("errorCode"), "invalid_operator_role")

    def test_admin_list_get_revoke_preserve_safe_gl206_semantics(self):
        op = self._create_operator(tenant_id="tenant-a", role="auditor")
        status, operators, _raw = self._get("/admin/operators", auth_header=self._admin_auth())
        self.assertEqual(status, 200)
        self.assertEqual(len(operators), 1)
        listed = operators[0]
        self.assertEqual(listed["operatorId"], op["operatorId"])
        forbidden = {"token_hash", "tokenHash", "token_lookup_hash", "lookup_hash", "tokenLookupHash", "token"}
        self.assertFalse(forbidden & set(listed))

        status, got, _raw = self._get(
            f"/admin/operators/{op['operatorId']}",
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 200)
        self.assertFalse(forbidden & set(got))

        status, body, _raw = self._post_json(
            f"/admin/operators/{op['operatorId']}/revoke",
            {},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["revoked"])

    def test_audit_entries_for_create_and_revoke_do_not_include_token_material(self):
        op = self._create_operator(tenant_id="tenant-a")
        self._post_json(
            f"/admin/operators/{op['operatorId']}/revoke",
            {},
            auth_header=self._admin_auth(),
        )
        events = self.audit_mod.list_events(limit=20)
        lifecycle_events = [e for e in events if e.action in {"operator_created", "operator_revoked"}]
        self.assertEqual({e.action for e in lifecycle_events}, {"operator_created", "operator_revoked"})
        for event in lifecycle_events:
            rendered = json.dumps(event.to_dict(), sort_keys=True)
            self.assertEqual(event.tenant_id, "tenant-a")
            self.assertEqual(event.scope, "tenant_admin")
            self.assertNotIn(op["token"], rendered)
            self.assertNotIn("token_hash", rendered)
            self.assertNotIn("lookup_hash", rendered)
            self.assertNotIn("Authorization", rendered)
            self.assertNotIn(ADMIN_TOKEN, rendered)

    def test_health_and_readiness_remain_public(self):
        health_status, health_body, _ = self._get("/health")
        readiness_status, readiness_body, _ = self._get("/readiness")
        self.assertEqual(health_status, 200)
        self.assertEqual(health_body["status"], "ok")
        self.assertEqual(readiness_status, 200)
        self.assertEqual(readiness_body["status"], "ready")

    def test_rate_limit_runtime_helper_is_preserved(self):
        self.assertTrue(hasattr(self.server_mod, "_rate_limiter"))
        self.assertTrue(hasattr(self.server_mod.GrantLayerHandler, "_check_rate_limit"))


class TestGL214ForbiddenChangeGuards(unittest.TestCase):
    def test_branch_diff_only_contains_allowed_files(self):
        changed = _branch_changed_files()
        self.assertEqual(changed, ALLOWED_CHANGED_FILES)

    def test_forbidden_paths_not_changed(self):
        changed = _branch_changed_files()
        forbidden_prefixes = (
            ".github/workflows/",
            "frontend/",
            "website/",
            "website-design/",
            "backend/src/migrations/",
            "scripts/build-clean-public-snapshot.sh",
            "scripts/publish-public-snapshot.sh",
        )
        forbidden_exact = {
            "setup.py",
            "package.json",
            "package-lock.json",
            "pyproject.toml",
            "sdk/pyproject.toml",
        }
        for path in changed:
            self.assertFalse(path.startswith(forbidden_prefixes), path)
            self.assertNotIn(path, forbidden_exact)

    def test_no_public_snapshot_export_or_package_metadata_created(self):
        absent = [
            "public-export",
            "public_export",
            "public-snapshot",
            "public_snapshot",
            "setup.py",
            "package.json",
            "package-lock.json",
            "sdk/pyproject.toml",
        ]
        for path in absent:
            self.assertFalse(os.path.exists(os.path.join(REPO_ROOT, path)), path)

    def test_unrelated_website_design_import_files_excluded_from_branch_diff(self):
        changed = _branch_changed_files()
        excluded = {
            "website-design/IMPORT_CHECKLIST.md",
            "website-design/README.md",
            "docs/website_design_workspace_import_report.md",
            "docs/website_design_workspace_import_report_dirty_stop.md",
            "docs/website_design_workspace_import_dirty_stop.md",
            "docs/website-design-workspace-import-report.md",
            "docs/website-design-workspace-import-report-dirty-stop.md",
        }
        self.assertFalse(changed & excluded)


if __name__ == "__main__":
    unittest.main()
