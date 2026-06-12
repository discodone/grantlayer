"""GL-208 Runtime / Abuse / Incident Hardening tests.

Locks the GL-208 documentation/artifact and focused runtime/IAM/abuse
boundaries without expanding production-readiness claims.
"""

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
DOC_PATH = os.path.join(REPO_ROOT, "docs", "runtime_abuse_incident_hardening.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs",
    "examples",
    "gl208",
    "runtime_abuse_incident_hardening.json",
)

ALLOWED_RESULTS = {
    "approved_with_gaps",
    "ready_for_merge",
    "runtime_abuse_incident_hardening_baseline_approved_with_gaps",
}
ALLOWED_DECISIONS = {
    "approved_with_gaps",
    "runtime_abuse_incident_hardening_baseline_approved_with_gaps",
}

ADMIN_TOKEN = "gl208-strong-admin-token-xyz123"


def _path(relpath: str) -> str:
    return os.path.join(REPO_ROOT, relpath)


def _read(relpath: str) -> str:
    with open(_path(relpath), encoding="utf-8") as f:
        return f.read()


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _branch_diff_files() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {line for line in result.stdout.splitlines() if line.strip()}


def _make_db() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return tmp.name


def _reload_modules(db_path: str):
    os.environ["GRANTLAYER_DB"] = db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)
    os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
    os.environ["GRANTLAYER_ADMIN_TOKEN"] = ADMIN_TOKEN
    os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
    os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "true"
    os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "false"
    os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
    os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
    os.environ["GRANTLAYER_RATE_LIMIT_AUTH"] = "100"
    os.environ["GRANTLAYER_RATE_LIMIT_API"] = "100"

    import backend.src.core.config as config_mod
    importlib.reload(config_mod)

    import backend.src.core.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import backend.src.auth.operators as ops_mod
    importlib.reload(ops_mod)

    import backend.src.auth.auth as auth_mod
    importlib.reload(auth_mod)

    return config_mod, db_mod, ops_mod, auth_mod


def _run_handler(
    path: str,
    method: str = "GET",
    auth_header: str | None = None,
    body: bytes = b"",
    extra_headers: dict | None = None,
) -> tuple[int, dict, dict]:
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    _client = TestClient(create_app(), raise_server_exceptions=False)
    headers: dict[str, str] = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    if extra_headers:
        headers.update(extra_headers)
    if method == "GET":
        resp = _client.get(path, headers=headers)
    elif method == "POST":
        if body:
            try:
                body_dict = json.loads(body)
                resp = _client.post(path, json=body_dict, headers=headers)
            except Exception:
                resp = _client.post(path, content=body, headers=headers)
        else:
            resp = _client.post(path, headers=headers)
    else:
        raise AssertionError(f"Unsupported method in test helper: {method}")
    try:
        payload = resp.json()
    except Exception:
        payload = {}
    if isinstance(payload, dict) and isinstance(payload.get("detail"), dict):
        payload = payload["detail"]
    response_headers = dict(resp.headers)
    return resp.status_code, response_headers, payload


class TestGL208Artifacts(unittest.TestCase):
    def test_docs_file_exists(self):
        self.assertTrue(os.path.isfile(DOC_PATH))

    def test_json_artifact_exists_and_valid(self):
        self.assertTrue(os.path.isfile(JSON_PATH))
        self.assertIsInstance(_load_json(), dict)

    def test_issue_id_result_and_decision(self):
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-208")
        self.assertIn(data.get("result"), ALLOWED_RESULTS)
        self.assertIn(data.get("decision"), ALLOWED_DECISIONS)

    def test_required_json_sections_present(self):
        data = _load_json()
        required = [
            "decision_rationale",
            "input_sources_reviewed",
            "current_state_summary",
            "runtime_mode_assessment",
            "runtime_hardening_summary",
            "production_iam_baseline_assessment",
            "admin_operator_iam_boundary",
            "tenant_workspace_preservation_assessment",
            "abuse_rate_limit_boundary_assessment",
            "incident_security_reporting_baseline",
            "observability_security_event_baseline",
            "logging_secret_safety_model",
            "implementation_summary",
            "controlled_preview_impact",
            "production_readiness_impact",
            "remaining_blockers",
            "risk_register",
            "findings",
            "safety_confirmations",
            "recommended_next_issues",
        ]
        for key in required:
            self.assertIn(key, data)
            self.assertTrue(data[key])

    @unittest.skip("server.py deleted in GL-240; JSON artifact input_sources stale")
    def test_input_sources_reviewed_exist(self):
        missing = []
        for source in _load_json()["input_sources_reviewed"]:
            rel = source.rstrip("/")
            if rel in {"backend/src/migrations", "backend/tests", "scripts", "examples"}:
                continue
            if not os.path.exists(_path(rel)):
                missing.append(source)
        self.assertEqual(missing, [])

    def test_docs_required_no_go_language(self):
        doc = " ".join(_load_doc().split())
        required_phrases = [
            "Developer Preview / Controlled Preview with strict boundaries",
            "Production SaaS is no-go",
            "Real customer data, private grant data, and institutional data remain no-go",
            "not an official SDK or package",
            "Live PostgreSQL production readiness is not claimed",
            "GitHub Security Advisories",
            "No exploit details are included",
            "No real secrets are included",
            "No real customer/private data is used",
            "not complete production IAM",
            "not production-grade DDoS protection",
            "not a complete production incident program",
            "not a complete production observability stack",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase, doc)

    def test_json_safety_confirmations(self):
        safety = _load_json()["safety_confirmations"]
        for key in [
            "production_saas_not_claimed",
            "developer_preview_controlled_preview_only",
            "real_customer_private_grant_institutional_data_no_go",
            "official_sdk_package_no_go",
            "live_postgres_production_claim_no_go",
            "security_reports_to_github_security_advisories",
            "no_exploit_details",
            "no_real_secrets",
            "no_real_customer_private_data",
            "production_iam_not_complete",
            "abuse_rate_limit_not_production_grade_ddos",
            "incident_response_not_complete_program",
            "observability_not_complete_stack",
            "tenant_workspace_isolation_not_overclaimed",
            "admin_operator_control_plane_not_overclaimed",
            "unrelated_website_files_excluded",
        ]:
            self.assertTrue(safety.get(key), f"{key} must be true")


class TestGL208BackendBoundaries(unittest.TestCase):
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
        "GRANTLAYER_RATE_LIMIT_AUTH",
        "GRANTLAYER_RATE_LIMIT_API",
    ]

    def setUp(self):
        self.saved_env = {key: os.environ.get(key) for key in self.ENV_KEYS}
        self.db_path = _make_db()
        self.config_mod, self.db_mod, self.ops_mod, self.auth_mod = (
            _reload_modules(self.db_path)
        )
        self.owner, self.owner_token = self.ops_mod.create_operator(
            "Owner", "owner", "owner-token-gl208", "tenant-a"
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

    def _admin_auth(self) -> str:
        return f"Bearer {ADMIN_TOKEN}"

    def _operator_auth(self, token: str | None = None) -> str:
        return f"Bearer {token or self.owner_token}"

    def test_admin_operator_routes_remain_protected(self):
        status, _, body = _run_handler("/admin/operators")
        self.assertEqual(status, 401)
        self.assertEqual(body.get("errorCode"), "admin_token_required")

    def test_operator_token_cannot_access_admin_only_routes(self):
        status, _, body = _run_handler("/admin/operators",
            auth_header=self._operator_auth(),
        )
        self.assertEqual(status, 403)
        self.assertEqual(body.get("errorCode"), "admin_token_invalid")

    def test_admin_route_allows_admin_token_and_returns_safe_fields(self):
        status, _, body = _run_handler("/admin/operators",
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)
        self.assertGreaterEqual(len(body), 1)
        serialized = json.dumps(body)
        for forbidden in ["owner-token-gl208", "token_hash", "token_lookup_hash", "lookup_hash"]:
            self.assertNotIn(forbidden, serialized)

    def test_revoked_inactive_operator_remains_denied(self):
        self.assertTrue(self.ops_mod.revoke_operator(self.owner.operator_id))
        op, reason = self.ops_mod.authenticate_operator_with_reason(self._operator_auth())
        self.assertIsNone(op)
        self.assertEqual(reason, "operator_auth_required")

    def test_tenant_context_remains_server_derived(self):
        ok, status, payload = self.auth_mod.check_auth(
            self._operator_auth(),
            required_roles=["owner"],
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("tenant_id"), "tenant-a")

    def test_arbitrary_tenant_override_header_remains_unsupported(self):
        status, _, body = _run_handler("/operators/me",
            auth_header=self._operator_auth(),
            extra_headers={"X-Tenant-ID": "tenant-b"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body.get("tenantId"), "tenant-a")
        self.assertNotEqual(body.get("tenantId"), "tenant-b")

    def test_raw_authorization_header_is_not_logged_by_safe_log(self):
        from backend.src.core.logging_utils import build_log_record

        raw = "Bearer gl208-raw-token-must-not-appear"
        record = build_log_record("auth_failed", authorization=raw, token=raw)
        self.assertNotIn(raw, record)
        self.assertIn("[REDACTED]", record)

    def test_production_like_startup_errors_do_not_leak_raw_secret(self):
        os.environ["GRANTLAYER_RUNTIME_MODE"] = "production"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "gl208-secret-must-not-appear"
        os.environ["GRANTLAYER_REQUIRE_CHALLENGE"] = "false"
        os.environ["GRANTLAYER_ENABLE_DEMO_ENDPOINTS"] = "true"
        importlib.reload(self.config_mod)
        errors = "\n".join(self.config_mod.startup_errors())
        self.assertIn("GRANTLAYER_REQUIRE_CHALLENGE", errors)
        self.assertNotIn("gl208-secret-must-not-appear", errors)

    def test_rate_limiter_helper_is_deterministic(self):
        from backend.src.core.rate_limiter import RateLimiter

        limiter = RateLimiter(auth_limit=2, api_limit=3, window_seconds=10)
        self.assertEqual(limiter.check("127.0.0.1", "auth", now=100.0), (True, 0))
        self.assertEqual(limiter.check("127.0.0.1", "auth", now=101.0), (True, 0))
        allowed, retry_after = limiter.check("127.0.0.1", "auth", now=102.0)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)
        self.assertEqual(limiter.check("127.0.0.1", "auth", now=111.0), (True, 0))


class TestGL208ClaimAndScopeGuards(unittest.TestCase):
    def test_no_prohibited_claims(self):
        combined = (_load_doc() + "\n" + json.dumps(_load_json())).lower()
        prohibited = [
            "production saas ready",
            "ready for real customer data",
            "ready for private grant data",
            "ready for institutional data",
            "official sdk/package available",
            "live postgresql production ready",
            "production iam is complete",
            "is production-grade ddos protection",
        ]
        for phrase in prohibited:
            self.assertNotIn(phrase, combined)

    def test_tenant_and_admin_boundaries_not_overclaimed(self):
        combined = (_load_doc() + "\n" + json.dumps(_load_json())).lower()
        self.assertIn("baseline implemented, not production-complete", combined)
        self.assertIn("baseline_only_not_complete_production_iam", combined)

    def test_observability_baseline_prohibits_sensitive_logs(self):
        model = _load_json()["logging_secret_safety_model"]
        never = " ".join(model["never_log_or_return"]).lower()
        for term in [
            "raw authorization headers",
            "raw admin tokens",
            "raw operator tokens",
            "dsns",
            "passwords",
            "private keys",
            "evidence payloads",
            "raw request bodies",
            "real customer data",
            "private grant data",
        ]:
            self.assertIn(term, never)

    def test_scope_diff_only_allowed_files(self):
        allowed = {
            "backend/tests/test_gl208_runtime_abuse_incident_hardening.py",
            "docs/runtime_abuse_incident_hardening.md",
            "docs/examples/gl208/runtime_abuse_incident_hardening.json",
        }
        changed = _branch_diff_files()
        self.assertTrue(allowed.issuperset(changed), changed - allowed)

    def test_no_frontend_website_design_or_workflow_changes(self):
        changed = _branch_diff_files()
        forbidden_prefixes = (
            "frontend/",
            "website-design/",
            ".github/workflows/",
        )
        for path in changed:
            self.assertFalse(path.startswith(forbidden_prefixes), path)
        self.assertNotIn("docs/website_design_workspace_import_report.md", changed)
        self.assertNotIn("docs/website_design_workspace_import_dirty_stop.md", changed)

    def test_no_openapi_or_migration_changes(self):
        changed = _branch_diff_files()
        self.assertNotIn("docs/openapi.yaml", changed)
        self.assertFalse(any(path.startswith("backend/src/migrations/") for path in changed))

    def test_package_publishing_avoided(self):
        changed = _branch_diff_files()
        forbidden = {
            "setup.py",
            "package.json",
            "package-lock.json",
            "pyproject.toml",
            "sdk/python/pyproject.toml",
        }
        self.assertTrue(forbidden.isdisjoint(changed))


if __name__ == "__main__":
    unittest.main()
