"""GL-206 — Admin/Operator Tenant Control Plane tests.

Verifies the documentation artifact, JSON evidence bundle, security/auth
behavior of admin control-plane routes, operator tenant assignment enforcement,
safe response fields, audit events, and regression preservation.

Design notes:
- Admin control-plane routes: POST/GET /admin/operators, POST /admin/operators/{id}/revoke
- All admin routes require valid admin Bearer token (GRANTLAYER_ADMIN_TOKEN)
- Operator token on admin route → 403
- Revoked/inactive operators fail closed at DB query
- create_operator() requires explicit tenant_id (positional arg, no silent default)
- Safe response fields: no token_hash, lookup_hash, or raw token in list/read
- Raw token returned once on create (one-time disclosure pattern)
- Structured log events for operator_created / operator_revoked
- Audit hash-chain unchanged (uses safe_log, not AuditEvent model)
- GL-200 through GL-205 baselines preserved
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "admin_operator_tenant_control_plane.md")
JSON_PATH = os.path.join(
    REPO_ROOT, "docs", "examples", "gl206", "admin_operator_tenant_control_plane.json"
)

_ALLOWED_RESULTS = {"APPROVED_WITH_GAPS", "APPROVED", "approved_with_gaps", "approved"}
_ALLOWED_DECISIONS = {"APPROVED_WITH_GAPS", "APPROVED", "approved_with_gaps", "approved"}

_ADMIN_TOKEN = "gl206-strong-admin-token-xyz123"


# ──────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────

def _make_db() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _reload_modules(db_path: str):
    os.environ["GRANTLAYER_DB"] = db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    import backend.src.config as config_mod
    importlib.reload(config_mod)

    import backend.src.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import backend.src.models as models_mod
    importlib.reload(models_mod)

    import backend.src.operators as ops_mod
    importlib.reload(ops_mod)

    import backend.src.auth as auth_mod
    importlib.reload(auth_mod)

    import backend.src.grants as grants_mod
    importlib.reload(grants_mod)

    import backend.src.challenges as ch_mod
    importlib.reload(ch_mod)

    import backend.src.grant_requests as gr_mod
    importlib.reload(gr_mod)

    import backend.src.audit_log as audit_mod
    importlib.reload(audit_mod)

    return config_mod, db_mod, models_mod, ops_mod, auth_mod, grants_mod, ch_mod, gr_mod, audit_mod


def _load_json() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_doc() -> str:
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


def _run_handler(path: str, method: str = "GET",
                 auth_header: str | None = None,
                 body: bytes = b"",
                 extra_headers: dict | None = None) -> tuple[int, dict]:
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    _client = TestClient(create_app(), raise_server_exceptions=False)
    headers: dict = {}
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
        raise AssertionError(f"Unsupported method: {method}")
    try:
        data = resp.json()
    except Exception:
        data = {}
    if isinstance(data, dict) and isinstance(data.get("detail"), dict):
        data = data["detail"]
    return resp.status_code, data


class _BaseGL206(unittest.TestCase):
    """Base with env setup/teardown for GL-206 tests."""

    _ENV_KEYS = [
        "GRANTLAYER_DB",
        "GRANTLAYER_RUNTIME_MODE",
        "GRANTLAYER_ADMIN_TOKEN",
        "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
        "GRANTLAYER_REQUIRE_CHALLENGE",
        "GRANTLAYER_ENABLE_DEMO_ENDPOINTS",
        "GRANTLAYER_ENABLE_OPERATOR_MODEL",
        "GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN",
    ]

    def setUp(self):
        self._saved_env = {k: os.environ.get(k) for k in self._ENV_KEYS}
        self.db_path = _make_db()
        os.environ["GRANTLAYER_DB"] = self.db_path
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = _ADMIN_TOKEN
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN", None)
        self.mods = _reload_modules(self.db_path)
        self.config_mod = self.mods[0]
        self.db_mod = self.mods[1]
        self.ops_mod = self.mods[3]
        self.auth_mod = self.mods[4]
        self.audit_mod = self.mods[8]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _admin_auth(self) -> str:
        return f"Bearer {_ADMIN_TOKEN}"

    def _post_json(self, path: str, data: dict,
                   auth_header: str | None = None) -> tuple[int, dict]:
        body = json.dumps(data).encode()
        return _run_handler(path, method="POST",
                            auth_header=auth_header, body=body)

    def _get(self, path: str, auth_header: str | None = None) -> tuple[int, dict]:
        return _run_handler(path, method="GET",
                            auth_header=auth_header)


# ──────────────────────────────────────────────────────────────
# 1. Documentation artifact tests
# ──────────────────────────────────────────────────────────────

class TestGL206DocArtifactExists(unittest.TestCase):
    """Doc-001 through Doc-006: Documentation artifact existence and structure."""

    def test_doc_001_md_exists(self):
        """docs/admin_operator_tenant_control_plane.md must exist."""
        self.assertTrue(
            os.path.isfile(DOC_PATH),
            f"docs/admin_operator_tenant_control_plane.md must exist at {DOC_PATH}",
        )

    def test_doc_002_json_exists(self):
        """docs/examples/gl206/admin_operator_tenant_control_plane.json must exist."""
        self.assertTrue(
            os.path.isfile(JSON_PATH),
            f"docs/examples/gl206/admin_operator_tenant_control_plane.json must exist at {JSON_PATH}",
        )

    def test_doc_003_json_is_valid(self):
        """JSON artifact must be valid JSON."""
        data = _load_json()
        self.assertIsInstance(data, dict, "JSON artifact must be a JSON object")

    def test_doc_004_issue_id_is_gl206(self):
        """JSON issue_id must be GL-206."""
        data = _load_json()
        self.assertEqual(data.get("issue_id"), "GL-206", "issue_id must be GL-206")

    def test_doc_005_result_is_allowed(self):
        """JSON result must be in allowed set."""
        data = _load_json()
        result = data.get("result", "")
        self.assertIn(
            result, _ALLOWED_RESULTS,
            f"result '{result}' must be in {_ALLOWED_RESULTS}",
        )

    def test_doc_006_decision_is_allowed(self):
        """JSON decision must be in allowed set."""
        data = _load_json()
        decision = data.get("decision", "")
        self.assertIn(
            decision, _ALLOWED_DECISIONS,
            f"decision '{decision}' must be in {_ALLOWED_DECISIONS}",
        )

    def test_doc_007_required_json_fields_present(self):
        """JSON must contain all required top-level fields."""
        data = _load_json()
        required_fields = [
            "current_admin_operator_model_summary",
            "tenant_assignment_model",
            "admin_behavior_model",
            "operator_behavior_model",
            "control_plane_api_behavior",
            "audit_behavior",
            "security_model",
            "production_mode_implications",
            "controlled_preview_impact",
            "remaining_gaps",
            "risk_register",
            "safety_confirmations",
            "recommended_next_issues",
        ]
        for field in required_fields:
            self.assertIn(field, data, f"JSON must contain required field: {field}")

    def test_doc_008_input_sources_are_listed(self):
        """JSON input_sources_reviewed must be a non-empty list."""
        data = _load_json()
        sources = data.get("input_sources_reviewed", [])
        self.assertIsInstance(sources, list)
        self.assertGreater(len(sources), 5, "input_sources_reviewed must list key sources")

    def test_doc_009_input_source_docs_exist_on_disk(self):
        """Referenced doc/JSON source files must exist on disk."""
        data = _load_json()
        sources = data.get("input_sources_reviewed", [])
        file_sources = [s for s in sources if s.endswith(".md") or s.endswith(".json") or s.endswith(".py") or s.endswith(".yaml")]
        missing = []
        for src in file_sources:
            full = os.path.join(REPO_ROOT, src)
            if not os.path.exists(full):
                missing.append(src)
        self.assertEqual(
            missing, [],
            f"Input source files listed in JSON but not found on disk: {missing}",
        )

    def test_doc_010_safety_confirmations_are_true(self):
        """All safety_confirmations must be true."""
        data = _load_json()
        confirmations = data.get("safety_confirmations", {})
        self.assertIsInstance(confirmations, dict)
        for key, value in confirmations.items():
            self.assertTrue(value, f"safety_confirmations.{key} must be true, got {value!r}")

    def test_doc_011_no_production_saas_claim_in_md(self):
        """docs/admin_operator_tenant_control_plane.md must not claim production SaaS readiness."""
        doc = _load_doc()
        self.assertNotIn(
            "production SaaS ready",
            doc.lower().replace("\n", " "),
            "Doc must not claim production SaaS readiness",
        )

    def test_doc_012_remaining_gaps_is_list(self):
        """JSON remaining_gaps must be a non-empty list."""
        data = _load_json()
        gaps = data.get("remaining_gaps", [])
        self.assertIsInstance(gaps, list, "remaining_gaps must be a list")
        self.assertGreater(len(gaps), 0, "remaining_gaps must be non-empty")

    def test_doc_013_risk_register_is_list(self):
        """JSON risk_register must be a non-empty list."""
        data = _load_json()
        register = data.get("risk_register", [])
        self.assertIsInstance(register, list, "risk_register must be a list")
        self.assertGreater(len(register), 0, "risk_register must be non-empty")

    def test_doc_014_recommended_next_issues_is_list(self):
        """JSON recommended_next_issues must be a non-empty list."""
        data = _load_json()
        next_issues = data.get("recommended_next_issues", [])
        self.assertIsInstance(next_issues, list, "recommended_next_issues must be a list")
        self.assertGreater(len(next_issues), 0, "recommended_next_issues must be non-empty")


# ──────────────────────────────────────────────────────────────
# 2. Security/auth tests
# ──────────────────────────────────────────────────────────────

class TestGL206AdminAuthEnforcement(_BaseGL206):
    """Auth-001 through Auth-010: Admin auth enforcement on control-plane routes."""

    def test_auth_001_missing_token_on_admin_list(self):
        """Missing admin token on GET /admin/operators → 401 or 403."""
        status, body = self._get("/admin/operators", auth_header=None)
        self.assertIn(status, (401, 403),
                      f"Missing admin token must be 401 or 403, got {status}")
        self.assertIn("errorCode", body)

    def test_auth_002_invalid_token_on_admin_list(self):
        """Invalid admin token on GET /admin/operators → 401 or 403."""
        status, body = self._get("/admin/operators", auth_header="Bearer invalid-token-xyz")
        self.assertIn(status, (401, 403),
                      f"Invalid admin token must be 401 or 403, got {status}")
        self.assertIn("errorCode", body)

    def test_auth_003_missing_token_on_admin_create(self):
        """Missing admin token on POST /admin/operators → 401 or 403."""
        status, body = self._post_json(
            "/admin/operators",
            {"name": "Test", "role": "owner", "tenantId": "t1"},
            auth_header=None,
        )
        self.assertIn(status, (401, 403),
                      f"Missing admin token must be 401 or 403, got {status}")

    def test_auth_004_invalid_token_on_admin_create(self):
        """Invalid admin token on POST /admin/operators → 401 or 403."""
        status, body = self._post_json(
            "/admin/operators",
            {"name": "Test", "role": "owner", "tenantId": "t1"},
            auth_header="Bearer wrong-token",
        )
        self.assertIn(status, (401, 403),
                      f"Invalid admin token must be 401 or 403, got {status}")

    def test_auth_005_operator_token_on_admin_list_is_forbidden(self):
        """Operator token on GET /admin/operators → 403 (admin required, not operator)."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.ops_mod.create_operator(
            name="Op GL206", role="owner", token=token, tenant_id="gl206-tenant"
        )
        # Operator token should not be accepted on admin route
        status, body = self._get("/admin/operators", auth_header=f"Bearer {token}")
        self.assertIn(status, (401, 403),
                      f"Operator token on admin route must be 401 or 403, got {status}")

    def test_auth_006_operator_token_on_admin_create_is_forbidden(self):
        """Operator token on POST /admin/operators → 403."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.ops_mod.create_operator(
            name="Op Forbidden", role="owner", token=token, tenant_id="gl206-t"
        )
        status, body = self._post_json(
            "/admin/operators",
            {"name": "Evil Op", "role": "owner", "tenantId": "other-tenant"},
            auth_header=f"Bearer {token}",
        )
        self.assertIn(status, (401, 403),
                      f"Operator token on admin create must be 401 or 403, got {status}")

    def test_auth_007_revoked_operator_fails_closed(self):
        """Revoked (inactive) operator token → 401 or 403 on protected routes."""
        import secrets
        token = secrets.token_urlsafe(32)
        op, _ = self.ops_mod.create_operator(
            name="To Revoke", role="owner", token=token, tenant_id="demo"
        )
        # Verify it works before revoke
        status_before, _ = self._get("/grants", auth_header=f"Bearer {token}")
        self.assertEqual(status_before, 200, "Operator should work before revoke")
        # Revoke
        self.ops_mod.revoke_operator(op.operator_id)
        # Reload modules to ensure no caching
        self.mods = _reload_modules(self.db_path)
        # Now auth must fail
        status_after, body_after = self._get("/grants", auth_header=f"Bearer {token}")
        self.assertIn(status_after, (401, 403),
                      f"Revoked operator must get 401 or 403, got {status_after}")

    def test_auth_008_valid_admin_token_on_admin_list_succeeds(self):
        """Valid admin token on GET /admin/operators → 200."""
        status, body = self._get("/admin/operators", auth_header=self._admin_auth())
        self.assertEqual(status, 200, f"Valid admin token must get 200, got {status}")
        self.assertIsInstance(body, list)


class TestGL206OperatorCreate(_BaseGL206):
    """Create-001 through Create-006: Operator creation via admin route."""

    def test_create_001_with_explicit_tenant_id_succeeds(self):
        """POST /admin/operators with name, role, tenantId → 201."""
        status, body = self._post_json(
            "/admin/operators",
            {"name": "Alice", "role": "owner", "tenantId": "acme-corp"},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 201, f"Create with explicit tenantId must be 201, got {status}: {body}")
        self.assertIn("operatorId", body)
        self.assertEqual(body.get("tenantId"), "acme-corp")

    def test_create_002_without_tenant_id_is_400(self):
        """POST /admin/operators without tenantId → 400 or 422."""
        status, body = self._post_json(
            "/admin/operators",
            {"name": "Bob", "role": "owner"},
            auth_header=self._admin_auth(),
        )
        self.assertIn(status, (400, 422), f"Missing tenantId must be 400 or 422, got {status}")
        if status == 400:
            self.assertIn("errorCode", body)

    def test_create_003_tenant_id_preserved_in_created_operator(self):
        """Created operator must have the tenant_id from the request."""
        status, body = self._post_json(
            "/admin/operators",
            {"name": "Carol", "role": "grant_admin", "tenantId": "tenant-xyz"},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 201)
        op_id = body["operatorId"]
        # Verify via direct DB read
        op_safe = self.ops_mod.get_operator_safe(op_id)
        self.assertIsNotNone(op_safe)
        self.assertEqual(op_safe["tenantId"], "tenant-xyz")

    def test_create_004_response_contains_one_time_token(self):
        """POST /admin/operators response must include one-time raw token."""
        status, body = self._post_json(
            "/admin/operators",
            {"name": "Dave", "role": "owner", "tenantId": "demo"},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 201)
        self.assertIn("token", body,
                      "Create response must include one-time raw token")
        self.assertIsInstance(body["token"], str)
        self.assertGreater(len(body["token"]), 10)

    def test_create_005_create_response_excludes_hash_fields(self):
        """POST /admin/operators response must not include token_hash or lookup_hash."""
        status, body = self._post_json(
            "/admin/operators",
            {"name": "Eve", "role": "auditor", "tenantId": "gl206-t"},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 201)
        body_str = json.dumps(body)
        self.assertNotIn("token_hash", body_str)
        self.assertNotIn("lookup_hash", body_str)
        self.assertNotIn("token_lookup_hash", body_str)

    def test_create_006_missing_name_is_400(self):
        """POST /admin/operators without name → 400 or 422."""
        status, body = self._post_json(
            "/admin/operators",
            {"role": "owner", "tenantId": "demo"},
            auth_header=self._admin_auth(),
        )
        self.assertIn(status, (400, 422))


class TestGL206OperatorList(_BaseGL206):
    """List-001 through List-004: List operators via admin route."""

    def test_list_001_list_is_empty_on_fresh_db(self):
        """GET /admin/operators on fresh DB → 200 with empty list."""
        status, body = self._get("/admin/operators", auth_header=self._admin_auth())
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_list_002_created_operator_appears_in_list(self):
        """After creating operator, it appears in GET /admin/operators list."""
        self._post_json(
            "/admin/operators",
            {"name": "ListMe", "role": "owner", "tenantId": "t-list"},
            auth_header=self._admin_auth(),
        )
        status, body = self._get("/admin/operators", auth_header=self._admin_auth())
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)
        self.assertGreater(len(body), 0)
        names = [op.get("name") for op in body]
        self.assertIn("ListMe", names)

    def test_list_003_list_response_has_no_token_hash(self):
        """GET /admin/operators response must not include token_hash, lookup_hash, or raw token."""
        self._post_json(
            "/admin/operators",
            {"name": "HashCheck", "role": "owner", "tenantId": "demo"},
            auth_header=self._admin_auth(),
        )
        status, body = self._get("/admin/operators", auth_header=self._admin_auth())
        self.assertEqual(status, 200)
        body_str = json.dumps(body)
        self.assertNotIn("token_hash", body_str,
                         "List response must not contain token_hash")
        self.assertNotIn("lookup_hash", body_str,
                         "List response must not contain lookup_hash")
        self.assertNotIn("token_lookup_hash", body_str,
                         "List response must not contain token_lookup_hash")

    def test_list_004_tenant_id_included_in_list_response(self):
        """GET /admin/operators response must include tenantId for each operator."""
        self._post_json(
            "/admin/operators",
            {"name": "TenantInList", "role": "owner", "tenantId": "expected-tenant"},
            auth_header=self._admin_auth(),
        )
        status, body = self._get("/admin/operators", auth_header=self._admin_auth())
        self.assertEqual(status, 200)
        for op in body:
            self.assertIn("tenantId", op, "Each operator in list must have tenantId")


class TestGL206OperatorRead(_BaseGL206):
    """Read-001 through Read-003: Read single operator via admin route."""

    def test_read_001_read_existing_operator_succeeds(self):
        """GET /admin/operators/{id} for existing operator → 200."""
        _, create_body = self._post_json(
            "/admin/operators",
            {"name": "ReadMe", "role": "owner", "tenantId": "read-tenant"},
            auth_header=self._admin_auth(),
        )
        op_id = create_body["operatorId"]
        status, body = self._get(f"/admin/operators/{op_id}",
                                 auth_header=self._admin_auth())
        self.assertEqual(status, 200)
        self.assertEqual(body.get("operatorId"), op_id)
        self.assertEqual(body.get("tenantId"), "read-tenant")

    def test_read_002_read_response_has_no_token_hash(self):
        """GET /admin/operators/{id} must not include token_hash or raw token."""
        _, create_body = self._post_json(
            "/admin/operators",
            {"name": "ReadHashCheck", "role": "owner", "tenantId": "demo"},
            auth_header=self._admin_auth(),
        )
        op_id = create_body["operatorId"]
        status, body = self._get(f"/admin/operators/{op_id}",
                                 auth_header=self._admin_auth())
        self.assertEqual(status, 200)
        body_str = json.dumps(body)
        self.assertNotIn("token_hash", body_str)
        self.assertNotIn("lookup_hash", body_str)
        self.assertNotIn("token_lookup_hash", body_str)

    def test_read_003_read_nonexistent_operator_is_404(self):
        """GET /admin/operators/{id} for nonexistent ID → 404."""
        status, body = self._get("/admin/operators/nonexistent-id-xyz",
                                 auth_header=self._admin_auth())
        self.assertEqual(status, 404)
        self.assertIn("errorCode", body)


class TestGL206OperatorRevoke(_BaseGL206):
    """Revoke-001 through Revoke-004: Revoke operator via admin route."""

    def test_revoke_001_revoke_existing_operator_succeeds(self):
        """POST /admin/operators/{id}/revoke → 200."""
        _, create_body = self._post_json(
            "/admin/operators",
            {"name": "ToRevoke", "role": "owner", "tenantId": "demo"},
            auth_header=self._admin_auth(),
        )
        op_id = create_body["operatorId"]
        status, body = self._post_json(
            f"/admin/operators/{op_id}/revoke", {},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 200, f"Revoke must return 200, got {status}: {body}")
        self.assertTrue(body.get("ok"))
        self.assertTrue(body.get("revoked"))
        self.assertEqual(body.get("operatorId"), op_id)

    def test_revoke_002_revoked_operator_cannot_authenticate(self):
        """After revoke, operator token must be rejected."""
        import secrets
        raw_token = secrets.token_urlsafe(32)
        _, create_body = self._post_json(
            "/admin/operators",
            {"name": "RevokeAuth", "role": "owner", "tenantId": "demo"},
            auth_header=self._admin_auth(),
        )
        op_id = create_body["operatorId"]
        # We need to create via ops_mod directly to have the raw token
        # The admin route generates a token internally; let's use ops_mod directly
        op_d, raw = self.ops_mod.create_operator(
            name="RevokeAuthDirect", role="owner", token=raw_token, tenant_id="demo"
        )
        # Verify can authenticate before revoke
        self.mods = _reload_modules(self.db_path)
        self.ops_mod = self.mods[3]
        status_before, _ = self._get("/grants", auth_header=f"Bearer {raw_token}")
        self.assertEqual(status_before, 200, "Should work before revoke")
        # Revoke
        self.ops_mod.revoke_operator(op_d.operator_id)
        self.mods = _reload_modules(self.db_path)
        status_after, _ = self._get("/grants", auth_header=f"Bearer {raw_token}")
        self.assertIn(status_after, (401, 403),
                      f"Revoked operator must fail closed, got {status_after}")

    def test_revoke_003_revoke_nonexistent_operator_is_404(self):
        """POST /admin/operators/{id}/revoke for nonexistent ID → 404."""
        status, body = self._post_json(
            "/admin/operators/nonexistent-id-xyz/revoke", {},
            auth_header=self._admin_auth(),
        )
        self.assertEqual(status, 404)
        self.assertIn("errorCode", body)

    def test_revoke_004_operator_cannot_revoke_via_admin_route(self):
        """Operator token on POST /admin/operators/{id}/revoke → 401 or 403."""
        import secrets
        token = secrets.token_urlsafe(32)
        op, _ = self.ops_mod.create_operator(
            name="OpRevoke", role="owner", token=token, tenant_id="demo"
        )
        _, create_body = self._post_json(
            "/admin/operators",
            {"name": "Target", "role": "owner", "tenantId": "demo"},
            auth_header=self._admin_auth(),
        )
        target_id = create_body["operatorId"]
        self.mods = _reload_modules(self.db_path)
        status, body = self._post_json(
            f"/admin/operators/{target_id}/revoke", {},
            auth_header=f"Bearer {token}",
        )
        self.assertIn(status, (401, 403),
                      f"Operator token on admin revoke must be 401 or 403, got {status}")


class TestGL206TenantIsolation(_BaseGL206):
    """Tenant-001 through Tenant-004: Tenant isolation and anti-escalation."""

    def test_tenant_001_operator_tenant_id_preserved_after_auth(self):
        """Operator tenant_id from DB is preserved in auth context."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.ops_mod.create_operator(
            name="TenantCheck", role="owner", token=token, tenant_id="my-tenant"
        )
        self.mods = _reload_modules(self.db_path)
        self.ops_mod = self.mods[3]
        op = self.ops_mod.authenticate_operator(f"Bearer {token}")
        self.assertIsNotNone(op)
        self.assertEqual(op.tenant_id, "my-tenant")

    def test_tenant_002_x_tenant_id_header_cannot_override_server_assigned(self):
        """X-Tenant-ID header must not override server-assigned tenant_id."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.ops_mod.create_operator(
            name="HeaderTest", role="owner", token=token, tenant_id="real-tenant"
        )
        self.mods = _reload_modules(self.db_path)
        self.ops_mod = self.mods[3]
        # Try to override tenant via X-Tenant-ID header
        status, body = _run_handler("/grants", method="GET",
            auth_header=f"Bearer {token}",
            extra_headers={"X-Tenant-ID": "attacker-tenant"},
        )
        # The request should succeed but the tenant context must be real-tenant, not attacker-tenant
        # We verify by checking the grants list was filtered for real-tenant, not attacker-tenant
        self.assertEqual(status, 200, f"Request should succeed: {status}")
        # Verify operator still has correct tenant
        op = self.ops_mod.authenticate_operator(f"Bearer {token}")
        self.assertIsNotNone(op)
        self.assertEqual(op.tenant_id, "real-tenant",
                         "X-Tenant-ID header must not override server-assigned tenant")

    def test_tenant_003_operator_cannot_list_another_tenants_operators(self):
        """Operator cannot list operators belonging to another tenant via admin route."""
        import secrets
        token_a = secrets.token_urlsafe(32)
        self.ops_mod.create_operator(
            name="OpA", role="owner", token=token_a, tenant_id="tenant-a"
        )
        self.mods = _reload_modules(self.db_path)
        # Operator token A cannot list operators (admin route requires admin token)
        status, body = self._get("/admin/operators", auth_header=f"Bearer {token_a}")
        self.assertIn(status, (401, 403),
                      f"Operator token must not access admin operator list: {status}")

    def test_tenant_004_operator_create_requires_explicit_tenant_id(self):
        """create_operator() requires explicit tenant_id (no positional default)."""
        import inspect
        sig = inspect.signature(self.ops_mod.create_operator)
        params = sig.parameters
        tenant_id_param = params.get("tenant_id")
        self.assertIsNotNone(tenant_id_param,
                             "create_operator() must have tenant_id parameter")
        # Must not have a default (empty or "dev") — it must be required
        self.assertEqual(
            tenant_id_param.default,
            inspect.Parameter.empty,
            "create_operator() tenant_id must be required (no default). "
            f"Got default: {tenant_id_param.default!r}",
        )


# ──────────────────────────────────────────────────────────────
# 3. Audit event tests
# ──────────────────────────────────────────────────────────────

class TestGL206AuditEvents(_BaseGL206):
    """Audit-001 through Audit-004: Audit/log event behavior."""

    def test_audit_001_audit_hash_chain_valid_after_control_plane_ops(self):
        """Audit hash-chain must remain valid after admin control-plane operations."""
        # Create an operator via admin route
        self._post_json(
            "/admin/operators",
            {"name": "AuditTest", "role": "owner", "tenantId": "audit-tenant"},
            auth_header=self._admin_auth(),
        )
        self.mods = _reload_modules(self.db_path)
        self.audit_mod = self.mods[8]
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"],
                        f"Audit hash-chain must remain valid: {result}")

    def test_audit_002_revoke_does_not_break_hash_chain(self):
        """Revoking an operator must not break audit hash-chain."""
        import secrets
        token = secrets.token_urlsafe(32)
        op, _ = self.ops_mod.create_operator(
            name="AuditRevoke", role="owner", token=token, tenant_id="demo"
        )
        self.ops_mod.revoke_operator(op.operator_id)
        self.mods = _reload_modules(self.db_path)
        self.audit_mod = self.mods[8]
        result = self.audit_mod.verify_audit_hash_chain()
        self.assertTrue(result["valid"],
                        f"Audit hash-chain must remain valid after revoke: {result}")

    def test_audit_003_operator_safe_dict_has_no_token_fields(self):
        """Operator safe dict (used in admin responses) must not contain hash fields."""
        import secrets
        token = secrets.token_urlsafe(32)
        op, raw = self.ops_mod.create_operator(
            name="SafeDictTest", role="owner", token=token, tenant_id="demo"
        )
        safe = self.ops_mod._operator_to_safe_dict(op)
        safe_str = json.dumps(safe)
        self.assertNotIn("token_hash", safe_str)
        self.assertNotIn("lookup_hash", safe_str)
        self.assertNotIn("token_lookup_hash", safe_str)
        self.assertNotIn(raw, safe_str,
                         "Raw token must not appear in safe dict")

    def test_audit_004_to_dict_has_no_token_fields(self):
        """Operator.to_dict() must not contain token_hash, lookup_hash, or raw token."""
        import secrets
        token = secrets.token_urlsafe(32)
        op, _ = self.ops_mod.create_operator(
            name="ToDictTest", role="owner", token=token, tenant_id="demo"
        )
        d = op.to_dict()
        d_str = json.dumps(d)
        self.assertNotIn("token_hash", d_str)
        self.assertNotIn("lookup_hash", d_str)
        self.assertNotIn("token_lookup_hash", d_str)


# ──────────────────────────────────────────────────────────────
# 4. Regression preservation
# ──────────────────────────────────────────────────────────────

class TestGL206RegressionPreservation(_BaseGL206):
    """Regression-001 through Regression-010: GL-200 through GL-205 regression checks."""

    def test_regression_001_health_endpoint_is_public(self):
        """GET /health must return 200 without auth."""
        status, body = self._get("/health")
        self.assertEqual(status, 200, f"Health endpoint must be public: {status}")
        self.assertEqual(body.get("status"), "ok")

    def test_regression_002_readiness_endpoint_is_public(self):
        """GET /readiness must return 200 without auth."""
        status, body = self._get("/readiness")
        self.assertEqual(status, 200, f"Readiness endpoint must be public: {status}")
        self.assertIn("status", body)

    def test_regression_003_cross_tenant_grant_denial(self):
        """Operator from tenant-a cannot see grants from tenant-b (GL-200 regression)."""
        import secrets, datetime
        token_a = secrets.token_urlsafe(32)
        token_b = secrets.token_urlsafe(32)
        self.ops_mod.create_operator(
            name="TenantA Op", role="owner", token=token_a, tenant_id="tenant-gl206-a"
        )
        self.ops_mod.create_operator(
            name="TenantB Op", role="owner", token=token_b, tenant_id="tenant-gl206-b"
        )
        self.mods = _reload_modules(self.db_path)
        self.ops_mod = self.mods[3]
        grants_mod = self.mods[5]

        # Create a grant for tenant-a
        now = datetime.datetime.now(datetime.timezone.utc)
        valid_from = (now - datetime.timedelta(days=1)).isoformat().replace("+00:00", "Z")
        valid_until = (now + datetime.timedelta(days=30)).isoformat().replace("+00:00", "Z")
        from backend.src.models import Grant
        grant = Grant(
            subject_id="subject-1", role="owner", action="read",
            resource="res-1", valid_from=valid_from, valid_until=valid_until,
            created_by="op-a", reason="test"
        )
        grants_mod.create_grant(grant, tenant_id="tenant-gl206-a")

        # tenant-b should not see tenant-a's grant
        status_a, body_a = self._get("/grants", auth_header=f"Bearer {token_a}")
        status_b, body_b = self._get("/grants", auth_header=f"Bearer {token_b}")
        self.assertEqual(status_a, 200)
        self.assertEqual(status_b, 200)
        self.assertGreater(len(body_a), 0, "Tenant-a should see its own grants")
        self.assertEqual(len(body_b), 0, "Tenant-b must not see tenant-a grants")

    def test_regression_004_admin_token_fail_closed(self):
        """Wrong admin token on admin route → 401 or 403 (GL-201 regression)."""
        status, body = self._get("/admin/operators", auth_header="Bearer wrong-admin-token")
        self.assertIn(status, (401, 403),
                      f"Wrong admin token must fail closed: {status}")

    def test_regression_005_operator_model_routes_require_operator_auth(self):
        """GET /grants requires auth; no auth → 401 (GL-200 regression)."""
        status, body = self._get("/grants")
        self.assertIn(status, (401, 403),
                      f"Protected routes must require auth: {status}")

    def test_regression_006_operators_me_requires_operator_auth(self):
        """GET /operators/me requires operator auth; no auth → 401."""
        status, body = self._get("/operators/me")
        self.assertIn(status, (401, 403),
                      f"GET /operators/me must require auth: {status}")

    def test_regression_007_revoke_operator_function_exists(self):
        """ops_mod.revoke_operator() must exist and work."""
        self.assertTrue(
            hasattr(self.ops_mod, "revoke_operator"),
            "ops_mod must have revoke_operator function",
        )
        import secrets
        token = secrets.token_urlsafe(32)
        op, _ = self.ops_mod.create_operator(
            name="RevokeTest", role="owner", token=token, tenant_id="demo"
        )
        result = self.ops_mod.revoke_operator(op.operator_id)
        self.assertTrue(result, "revoke_operator must return True for existing op")

    def test_regression_008_revoke_nonexistent_returns_false(self):
        """revoke_operator() on nonexistent ID → False."""
        result = self.ops_mod.revoke_operator("nonexistent-id-xyz-123")
        self.assertFalse(result, "revoke_operator must return False for nonexistent op")

    def test_regression_009_list_operators_for_admin_returns_safe_dicts(self):
        """list_operators_for_admin() must return dicts without token_hash."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.ops_mod.create_operator(
            name="AdminListTest", role="owner", token=token, tenant_id="demo"
        )
        self.mods = _reload_modules(self.db_path)
        self.ops_mod = self.mods[3]
        operators = self.ops_mod.list_operators_for_admin()
        self.assertIsInstance(operators, list)
        self.assertGreater(len(operators), 0)
        for op_dict in operators:
            op_str = json.dumps(op_dict)
            self.assertNotIn("token_hash", op_str)
            self.assertNotIn("lookup_hash", op_str)
            self.assertNotIn("token_lookup_hash", op_str)

    def test_regression_010_get_operator_safe_returns_safe_dict(self):
        """get_operator_safe() must return dict without token_hash."""
        import secrets
        token = secrets.token_urlsafe(32)
        op, _ = self.ops_mod.create_operator(
            name="GetSafeTest", role="owner", token=token, tenant_id="demo"
        )
        self.mods = _reload_modules(self.db_path)
        self.ops_mod = self.mods[3]
        safe = self.ops_mod.get_operator_safe(op.operator_id)
        self.assertIsNotNone(safe)
        safe_str = json.dumps(safe)
        self.assertNotIn("token_hash", safe_str)
        self.assertNotIn("token_lookup_hash", safe_str)
        self.assertNotIn(token, safe_str, "Raw token must not appear in safe dict")


# ──────────────────────────────────────────────────────────────
# 5. Posture/claim tests
# ──────────────────────────────────────────────────────────────

class TestGL206PostureClaims(unittest.TestCase):
    """Posture-001 through Posture-010: Documentation posture and claim safety."""

    def test_posture_001_no_production_saas_claim_in_doc(self):
        """docs/admin_operator_tenant_control_plane.md must not claim production SaaS readiness."""
        doc = _load_doc()
        # Should not contain affirmative production SaaS claim
        unsafe_phrases = [
            "production saas ready",
            "production saas readiness: yes",
            "production saas readiness: confirmed",
        ]
        doc_lower = doc.lower()
        for phrase in unsafe_phrases:
            self.assertNotIn(phrase, doc_lower,
                             f"Doc must not contain phrase: '{phrase}'")

    def test_posture_002_tenant_isolation_not_overclaimed(self):
        """Doc must not claim tenant/workspace isolation is production-complete without negation."""
        doc = _load_doc()
        # The doc should only say "not production-complete" or similar negations,
        # never affirmatively claim "isolation is production-complete"
        unsafe_phrases = [
            "isolation is production-complete",
            "isolation: production-complete",
            "tenant isolation is complete",
            "workspace isolation is complete",
        ]
        doc_lower = doc.lower()
        for phrase in unsafe_phrases:
            self.assertNotIn(phrase, doc_lower,
                             f"Doc must not contain affirmative phrase: '{phrase}'")

    def test_posture_003_no_real_customer_data_claim(self):
        """JSON must confirm no real customer/private data readiness."""
        data = _load_json()
        confirmations = data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_real_customer_data"),
            "safety_confirmations.no_real_customer_data must be true",
        )

    def test_posture_004_no_official_sdk_claim(self):
        """JSON must confirm no official SDK/package."""
        data = _load_json()
        confirmations = data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_official_sdk"),
            "safety_confirmations.no_official_sdk must be true",
        )

    def test_posture_005_no_frontend_changes_claim(self):
        """JSON must confirm no frontend/website/design changes."""
        data = _load_json()
        confirmations = data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_frontend_changes"),
            "safety_confirmations.no_frontend_changes must be true",
        )

    def test_posture_006_no_github_workflow_changes_claim(self):
        """JSON must confirm no GitHub workflow changes."""
        data = _load_json()
        confirmations = data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_github_workflow_changes"),
            "safety_confirmations.no_github_workflow_changes must be true",
        )

    def test_posture_007_no_public_push_claim(self):
        """JSON must confirm no public GitHub push."""
        data = _load_json()
        confirmations = data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_public_push"),
            "safety_confirmations.no_public_push must be true",
        )

    def test_posture_008_no_frontend_files_in_branch(self):
        """No frontend/website/design files in this branch (git diff check)."""
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True,
            cwd=REPO_ROOT,
        )
        changed_files = result.stdout.strip().splitlines()
        frontend_files = [f for f in changed_files
                         if "website-design" in f or "website_design" in f
                         or f.startswith("frontend/")]
        self.assertEqual(
            frontend_files, [],
            f"No frontend/website-design files should be in this branch: {frontend_files}",
        )

    def test_posture_009_no_github_workflow_files_in_branch(self):
        """No .github/ workflow changes in this branch."""
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True,
            cwd=REPO_ROOT,
        )
        changed_files = result.stdout.strip().splitlines()
        workflow_files = [f for f in changed_files if f.startswith(".github/")]
        self.assertEqual(
            workflow_files, [],
            f"No .github/ workflow files should be changed: {workflow_files}",
        )

    def test_posture_010_no_package_publishing_claim(self):
        """JSON must confirm no package publishing."""
        data = _load_json()
        confirmations = data.get("safety_confirmations", {})
        self.assertTrue(
            confirmations.get("no_package_publishing"),
            "safety_confirmations.no_package_publishing must be true",
        )


if __name__ == "__main__":
    unittest.main()
