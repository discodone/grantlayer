"""GL-347 — Control-plane admin actions must be scoped to the caller's tenant.

Three handlers let a tenant-A admin act on tenant B:
  - admin.create_operator trusted body.tenant_id (require_admin accepts any tenant);
  - workspaces.get_workspace / update_workspace_plan looked up by path workspace_id
    with no tenant scope;
  - gdpr export/erase treated any tenant-admin as authorized, scoped only by path
    user_id.

Fix doctrine: every control-plane admin action verifies the caller's admin role is
scoped to the SAME tenant as the target, deriving the target tenant from the verified
request (body for create, persisted row for workspaces, the user's footprint for GDPR)
and rejecting cross-tenant targets with 403. A deployment-level admin (static admin
token, no tenant claim) retains full authority; a tenant-scoped admin (JWT with a
tenant_id claim) is confined to its own tenant.

RED before fix (all return success / 202 / 200 before the fix):
  - tenant-A admin creating an operator in tenant B → 403
  - tenant-A admin reading / updating a tenant-B workspace plan → 403
  - tenant-A admin exporting / erasing a tenant-B user → 403

Backward-compat (must stay GREEN): a deployment-level admin token may still act
cross-tenant; a tenant-scoped admin may still act within its own tenant.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
import uuid

_TEST_SECRET = "gl347-test-hs256-secret-32chars!!"
_TENANT_A = "tenant-a-gl347"
_TENANT_B = "tenant-b-gl347"
_ADMIN_TOKEN = "gl347-deployment-admin-token-xyz"
_NOW = "2026-01-01T00:00:00Z"

# Modules whose stale references to backend.src.core.db must be refreshed after a
# DB swap. Sibling tests (e.g. GL-206/GL-215) reload the db module onto a temp DB
# but not the router modules, leaving routers bound to a stale get_async_db. We
# reload the full chain onto our own temp file so sync seeding and the async app
# read the SAME file-based DB (an in-memory DB is per-connection and cannot be
# seeded synchronously).
_RELOAD_CHAIN = (
    "backend.src.core.config",
    "backend.src.core.db",
    "backend.src.core.models",
    "backend.src.auth.operators",
    "backend.src.auth.auth",
    "backend.src.api.deps",
    "backend.src.api.routers.admin",
    "backend.src.api.routers.workspaces",
    "backend.src.api.routers.gdpr",
    "backend.src.api.app",
)


def _reset_db_to_file():
    """Point the whole stack at a fresh temp-file DB and return its path."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    os.environ["GRANTLAYER_DB"] = f.name
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)
    os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    for name in _RELOAD_CHAIN:
        mod = sys.modules.get(name)
        if mod is not None:
            importlib.reload(mod)
    import backend.src.core.db as db
    db.init_db()
    return f.name


def _make_client():
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _admin_jwt(tenant_id: str, role: str = "grant_admin") -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    from backend.src.api.auth_jwt import encode_token
    return encode_token(
        {
            "sub": f"admin-{tenant_id}", "role": role, "tenant_id": tenant_id,
            "iss": "grantlayer", "aud": "grantlayer-api",
        },
        _TEST_SECRET,
    )


def _seed_workspace(ws_id: str, tenant_id: str) -> None:
    from backend.src.core.db import get_session
    from backend.src.core.orm import Workspace
    s = get_session()
    try:
        s.merge(Workspace(
            id=ws_id, tenant_id=tenant_id, name=f"ws-{ws_id}",
            slug=f"slug-{ws_id}", owner_id="owner-gl347", status="active",
            created_at=_NOW, updated_at=_NOW, plan_tier="free",
        ))
        s.commit()
    finally:
        s.close()


def _seed_operator(op_id: str, tenant_id: str) -> None:
    from backend.src.core.db import get_session
    from backend.src.core.orm import Operator
    s = get_session()
    try:
        s.merge(Operator(
            id=op_id, name=f"op-{op_id}", role="owner",
            token_hash="gl347-unused-hash", active=1, created_at=_NOW,
            tenant_id=tenant_id,
        ))
        s.commit()
    finally:
        s.close()


class TestAdminCreateOperatorTenantScope(unittest.TestCase):
    def setUp(self):
        _reset_db_to_file()
        self.client = _make_client()

    def test_tenant_a_admin_cannot_create_operator_in_tenant_b(self):
        """RED before fix: returns 201 (body.tenant_id trusted)."""
        resp = self.client.post(
            "/v1/admin/operators",
            json={"name": "Cross", "role": "owner", "tenantId": _TENANT_B},
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json().get("errorCode"), "cross_tenant_forbidden")

    def test_tenant_a_admin_can_create_operator_in_own_tenant(self):
        resp = self.client.post(
            "/v1/admin/operators",
            json={"name": "Own", "role": "owner", "tenantId": _TENANT_A},
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(resp.json().get("tenantId"), _TENANT_A)

    def test_deployment_admin_token_may_create_in_any_tenant(self):
        """Backward-compat: a static admin token (no tenant claim) is unrestricted."""
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = _ADMIN_TOKEN
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        from backend.src.core.db import init_db
        init_db()
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        client = TestClient(create_app(), raise_server_exceptions=False)
        try:
            resp = client.post(
                "/v1/admin/operators",
                json={"name": "Global", "role": "owner", "tenantId": _TENANT_B},
                headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"},
            )
            self.assertEqual(resp.status_code, 201, resp.text)
        finally:
            os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
            os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET


class TestWorkspaceTenantScope(unittest.TestCase):
    def setUp(self):
        _reset_db_to_file()
        self.client = _make_client()
        self.ws_a = f"ws-a-{uuid.uuid4().hex[:8]}"
        self.ws_b = f"ws-b-{uuid.uuid4().hex[:8]}"
        _seed_workspace(self.ws_a, _TENANT_A)
        _seed_workspace(self.ws_b, _TENANT_B)

    def test_tenant_a_admin_cannot_read_tenant_b_workspace(self):
        """RED before fix: returns 200 with tenant-B workspace data."""
        resp = self.client.get(
            f"/v1/workspaces/{self.ws_b}",
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json().get("errorCode"), "cross_tenant_forbidden")

    def test_tenant_a_admin_cannot_update_tenant_b_plan(self):
        """RED before fix: returns 200 and changes tenant-B plan."""
        resp = self.client.patch(
            f"/v1/workspaces/{self.ws_b}/plan",
            json={"plan_tier": "enterprise"},
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json().get("errorCode"), "cross_tenant_forbidden")

    def test_tenant_a_admin_can_read_own_workspace(self):
        resp = self.client.get(
            f"/v1/workspaces/{self.ws_a}",
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json().get("tenant_id"), _TENANT_A)

    def test_tenant_a_admin_can_update_own_plan(self):
        resp = self.client.patch(
            f"/v1/workspaces/{self.ws_a}/plan",
            json={"plan_tier": "pro"},
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json().get("plan_tier"), "pro")

    def test_missing_workspace_is_404_not_403(self):
        resp = self.client.get(
            f"/v1/workspaces/does-not-exist-{uuid.uuid4().hex}",
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 404, resp.text)


class TestGdprTenantScope(unittest.TestCase):
    def setUp(self):
        _reset_db_to_file()
        self.client = _make_client()
        self.victim_b = f"victim-b-{uuid.uuid4().hex[:8]}"
        _seed_operator(self.victim_b, _TENANT_B)

    def test_tenant_a_admin_cannot_export_tenant_b_user(self):
        """RED before fix: returns 202 (any tenant-admin authorized)."""
        resp = self.client.post(
            f"/v1/users/{self.victim_b}/export-data",
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json().get("errorCode"), "cross_tenant_forbidden")

    def test_tenant_a_admin_cannot_erase_tenant_b_user(self):
        """RED before fix: returns 202 and anonymizes the tenant-B operator."""
        resp = self.client.post(
            f"/v1/users/{self.victim_b}/erase",
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json().get("errorCode"), "cross_tenant_forbidden")

    def test_tenant_b_admin_can_export_own_tenant_user(self):
        resp = self.client.post(
            f"/v1/users/{self.victim_b}/export-data",
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_B)}"},
        )
        self.assertEqual(resp.status_code, 202, resp.text)

    def test_user_with_no_footprint_is_allowed(self):
        """A target with no tenant footprint exposes no cross-tenant data."""
        resp = self.client.post(
            f"/v1/users/ghost-{uuid.uuid4().hex}/export-data",
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 202, resp.text)


if __name__ == "__main__":
    unittest.main()
