"""GL-237: API consistency fixes — test suite.

Covers:
  BUG 1 — Role validation in POST /grants (422 for invalid roles)
  BUG 2 — camelCase contract for /grant-requests responses
  BUG 3 — Legacy server.py comments removed from app.py
  BUG 4 — RuntimeError troubleshooting hint in QUICKSTART.md
  BUG 5 — Correct paths in AGENTS.md
"""

import os
import pathlib
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(
    _FASTAPI_AVAILABLE,
    "FastAPI not installed",
)

if _FASTAPI_AVAILABLE:
    import backend.src.core.config as _cfg
    import backend.src.core.db as _db
    from backend.src.api.app import create_app

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_JWT_SECRET = "test-secret-gl237"


class _Base(unittest.TestCase):
    _operator_model = True

    def setUp(self):
        self._orig_op = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_admin = _cfg.GRANTLAYER_ADMIN_TOKEN
        self._orig_jwt_secret_env = os.environ.get("GRANTLAYER_JWT_SECRET", "")

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True
        _cfg.ENABLE_OPERATOR_MODEL = self._operator_model
        _cfg.GRANTLAYER_ADMIN_TOKEN = ""
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=True)

    def tearDown(self):
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_op
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        _cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin
        if self._orig_jwt_secret_env:
            os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_jwt_secret_env
        else:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        _db.DB_PATH_OR_URL = self._orig_db
        _db.DB_PATH = self._orig_db
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def _get_token(self) -> str:
        from backend.src.api.auth_jwt import create_dev_token
        return create_dev_token(secret=_JWT_SECRET)

    def _auth(self, token: str = "") -> dict:
        t = token or self._get_token()
        return {"Authorization": f"Bearer {t}"}

    def _grant_body(self, role: str = "viewer") -> dict:
        return {
            "subjectId": "agent-test",
            "role": role,
            "action": "read",
            "resource": "reports",
            "validFrom": "2025-01-01T00:00:00Z",
            "validUntil": "2025-12-31T23:59:59Z",
            "createdBy": "test-op",
            "reason": "gl237 test",
        }


# ── BUG 1: Role validation in POST /grants ───────────────────────────────────

@_SKIP
class TestBug1GrantsRoleValidation(_Base):
    def test_invalid_role_returns_422(self):
        r = self.client.post("/grants", json=self._grant_body("hacker"), headers=self._auth())
        self.assertEqual(r.status_code, 422)

    def test_invalid_role_error_code(self):
        r = self.client.post("/grants", json=self._grant_body("hacker"), headers=self._auth())
        body = r.json()
        self.assertEqual(body.get("errorCode"), "invalid_role")

    def test_invalid_role_reason_lists_allowed(self):
        r = self.client.post("/grants", json=self._grant_body("superadmin"), headers=self._auth())
        body = r.json()
        self.assertIn("viewer", body.get("reason", ""))

    def test_valid_role_viewer_returns_201(self):
        r = self.client.post("/grants", json=self._grant_body("viewer"), headers=self._auth())
        self.assertEqual(r.status_code, 201)

    def test_valid_role_auditor_returns_201(self):
        r = self.client.post("/grants", json=self._grant_body("auditor"), headers=self._auth())
        self.assertEqual(r.status_code, 201)

    def test_valid_role_operator_returns_201(self):
        r = self.client.post("/grants", json=self._grant_body("operator"), headers=self._auth())
        self.assertEqual(r.status_code, 201)

    def test_valid_role_admin_returns_201(self):
        r = self.client.post("/grants", json=self._grant_body("admin"), headers=self._auth())
        self.assertEqual(r.status_code, 201)

    def test_empty_string_role_rejected(self):
        body = self._grant_body("")
        r = self.client.post("/grants", json=body, headers=self._auth())
        self.assertIn(r.status_code, [400, 422])

    def test_all_allowed_roles_accepted(self):
        from backend.src.grants.grant_requests import ALLOWED_GRANT_ROLES
        for role in ALLOWED_GRANT_ROLES:
            with self.subTest(role=role):
                r = self.client.post("/grants", json=self._grant_body(role), headers=self._auth())
                self.assertEqual(r.status_code, 201, f"Expected 201 for valid role '{role}', got {r.status_code}")

    def test_grants_router_imports_allowed_grant_roles(self):
        import backend.src.api.routers.grants as grants_router
        from backend.src.grants.grant_requests import ALLOWED_GRANT_ROLES
        self.assertTrue(hasattr(grants_router, "ALLOWED_GRANT_ROLES"))
        self.assertEqual(grants_router.ALLOWED_GRANT_ROLES, ALLOWED_GRANT_ROLES)


# ── BUG 2: camelCase contract for /grant-requests ────────────────────────────

@_SKIP
class TestBug2GrantRequestsCamelCase(_Base):
    def _create_request(self) -> dict:
        body = {
            "subjectId": "agent-007",
            "role": "viewer",
            "action": "read",
            "resource": "reports",
            "validFrom": "2025-01-01T00:00:00Z",
            "validUntil": "2025-12-31T23:59:59Z",
            "reason": "gl237 camelCase test",
        }
        r = self.client.post("/grant-requests", json=body, headers=self._auth())
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def test_create_response_uses_camel_case_keys(self):
        resp = self._create_request()
        self.assertIn("subjectId", resp)
        self.assertIn("requestedBy", resp)
        self.assertIn("validFrom", resp)
        self.assertIn("validUntil", resp)
        self.assertIn("createdAt", resp)
        self.assertIn("updatedAt", resp)

    def test_create_response_no_snake_case_keys(self):
        resp = self._create_request()
        self.assertNotIn("subject_id", resp)
        self.assertNotIn("requested_by", resp)
        self.assertNotIn("valid_from", resp)
        self.assertNotIn("valid_until", resp)
        self.assertNotIn("created_at", resp)

    def test_list_response_uses_camel_case(self):
        self._create_request()
        r = self.client.get("/grant-requests", headers=self._auth())
        self.assertEqual(r.status_code, 200)
        items = r.json()
        self.assertGreater(len(items), 0)
        item = items[0]
        self.assertIn("subjectId", item)
        self.assertIn("requestedBy", item)
        self.assertNotIn("subject_id", item)

    def test_get_single_response_uses_camel_case(self):
        created = self._create_request()
        req_id = created["id"]
        r = self.client.get(f"/grant-requests/{req_id}", headers=self._auth())
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("subjectId", body)
        self.assertIn("requestedBy", body)
        self.assertNotIn("subject_id", body)

    def test_grants_response_already_camel_case(self):
        r = self.client.post("/grants", json=self._grant_body("viewer"), headers=self._auth())
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertIn("subjectId", body)
        self.assertIn("validFrom", body)
        self.assertIn("validUntil", body)
        self.assertIn("createdBy", body)
        self.assertNotIn("subject_id", body)

    def test_grant_request_response_schema_exists(self):
        from backend.src.api.schemas import GrantRequestResponse
        self.assertTrue(callable(GrantRequestResponse.from_grant_request))

    def test_grant_request_response_has_camel_aliases(self):
        from backend.src.api.schemas import GrantRequestResponse
        aliases = {
            info.alias
            for info in GrantRequestResponse.model_fields.values()
            if info.alias
        }
        self.assertIn("subjectId", aliases)
        self.assertIn("requestedBy", aliases)
        self.assertIn("validFrom", aliases)
        self.assertIn("validUntil", aliases)
        self.assertIn("createdAt", aliases)


# ── BUG 3: Legacy server.py comments removed from app.py ─────────────────────

class TestBug3AppPyCleanup(unittest.TestCase):
    def _app_content(self) -> str:
        p = _REPO_ROOT / "backend" / "src" / "api" / "app.py"
        return p.read_text()

    def test_no_server_py_continues_to_run_in_parallel(self):
        self.assertNotIn("server.py continues to run in parallel", self._app_content())

    def test_no_strangler_fig_pattern_mention_in_docstring(self):
        content = self._app_content()
        self.assertNotIn("strangler fig", content.lower()[:500])

    def test_no_run_alongside_server_py(self):
        self.assertNotIn("alongside server.py", self._app_content())

    def test_module_docstring_is_clean(self):
        content = self._app_content()
        first_triple = content.index('"""') + 3
        end_triple = content.index('"""', first_triple)
        docstring = content[first_triple:end_triple]
        self.assertNotIn("server.py", docstring)


# ── BUG 4: RuntimeError troubleshooting hint in QUICKSTART.md ────────────────

class TestBug4QuickstartRuntimeError(unittest.TestCase):
    def _qs(self) -> str:
        return (_REPO_ROOT / "QUICKSTART.md").read_text()

    def test_runtimeerror_mentioned_in_troubleshooting(self):
        self.assertIn("RuntimeError", self._qs())

    def test_missing_column_mentioned(self):
        self.assertIn("missing column", self._qs())

    def test_down_v_fix_is_documented(self):
        self.assertIn("docker compose down -v", self._qs())

    def test_requestid_not_used_in_quickstart(self):
        content = self._qs()
        self.assertNotIn("requestId", content,
                         "QUICKSTART should use 'id', not 'requestId'")


# ── BUG 5: Correct paths in AGENTS.md ────────────────────────────────────────

class TestBug5AgentsMdPaths(unittest.TestCase):
    def _agents(self) -> str:
        return (_REPO_ROOT / "AGENTS.md").read_text()

    def test_requirements_dev_no_backend_prefix(self):
        """requirements-dev.txt lives at repo root, not backend/."""
        content = self._agents()
        self.assertIn("requirements-dev.txt", content)
        self.assertNotIn("backend/requirements-dev.txt", content)

    def test_run_functional_tests_no_backend_prefix(self):
        """Script lives at repo-root scripts/, not backend/scripts/."""
        content = self._agents()
        self.assertIn("scripts/run-functional-tests.sh", content)
        self.assertNotIn("backend/scripts/run-functional-tests.sh", content)

    def test_run_full_suite_no_backend_prefix(self):
        content = self._agents()
        self.assertIn("scripts/run-full-backend-suite.sh", content)
        self.assertNotIn("backend/scripts/run-full-backend-suite.sh", content)

    def test_no_cd_backend_before_pip(self):
        """No 'cd backend' before pip install — both live at repo root."""
        content = self._agents()
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "pip install" in line and "requirements-dev" in line:
                if i > 0 and lines[i - 1].strip() == "cd backend":
                    self.fail(
                        "Found 'cd backend' immediately before pip install — "
                        "requirements-dev.txt is at repo root"
                    )

    def test_documented_paths_exist_on_disk(self):
        self.assertTrue((_REPO_ROOT / "requirements-dev.txt").exists())
        self.assertTrue((_REPO_ROOT / "scripts" / "run-functional-tests.sh").exists())
        self.assertTrue((_REPO_ROOT / "scripts" / "run-full-backend-suite.sh").exists())
