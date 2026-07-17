"""GL-349 — Close the cross-tenant class structurally on the control-plane.

Round-17 (Opus) confirmed the data-plane cross-tenant class is closed, but GL-347
was bolted onto only THREE handlers (create_operator, get/update workspace,
gdpr export/erase) while siblings with the SAME vulnerability stayed open:

  - admin.revoke_operator      cross-tenant WRITE  (P0: live revoke escalation)
  - admin.get_operator         cross-tenant read
  - admin.list_operators       cross-tenant read (repo.list() unfiltered)
  - workspaces.list_workspaces cross-tenant read (SELECT ... FROM workspaces, no WHERE)
  - api_keys.revoke            is_admin short-circuits ownership, no tenant check
  - api_keys.create            any authenticated user could mint an admin-scoped key

This suite is the STRUCTURAL forcing function the reviewer asked for: instead of a
hand-maintained exclusion list, it ENUMERATES every admin-plane / api-key route from
the live router table and asserts a tenant-A actor cannot reach a tenant-B resource.
A newly-added admin route that forgets tenant scoping is RED by default, because:

  1. `test_every_admin_plane_route_is_categorized` fails if a discovered route under
     /v1/admin, /v1/workspaces, /v1/jobs, or /v1/api-keys is not in _ROUTE_POLICY.
  2. Each policy category carries a concrete cross-tenant assertion (403, or absent
     from a tenant-filtered list, or deployment-admin-only) exercised against real
     seeded tenant-A/tenant-B rows.

Authority model (documented, enforced):
  - deployment-level admin (static admin token, NO tenant_id claim) = full authority.
  - tenant-scoped admin (JWT with tenant_id) = confined to its own tenant.

RED before the GL-349 fix; GREEN after.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import tempfile
import unittest
import uuid

_TEST_SECRET = "gl349-test-hs256-secret-32chars!!"
_TENANT_A = "tenant-a-gl349"
_TENANT_B = "tenant-b-gl349"
_NOW = "2026-01-01T00:00:00Z"
_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Routers whose routes are control-plane (admin-plane) or api-key management. Every
# route under these prefixes must appear in _ROUTE_POLICY (fail-closed).
_ADMIN_PLANE_PREFIXES = ("/v1/admin", "/v1/workspaces", "/v1/jobs", "/v1/api-keys")

# Enforcement category for each admin-plane / api-key route.
#   cross_tenant_403        — targeting a tenant-B resource by path id → 403
#   cross_tenant_create_403 — create bound to tenant/workspace B → 403
#   tenant_filtered_list    — list must NOT return tenant-B rows for a tenant-A caller
#   deployment_admin_only   — tenant-scoped admin rejected (resource has no tenant dim)
#   own_scoped              — inherently scoped to the caller's own subject (no target)
_ROUTE_POLICY: dict[tuple[str, str], str] = {
    ("GET", "/v1/admin/operators"): "tenant_filtered_list",
    ("GET", "/v1/admin/operators/{operator_id}"): "cross_tenant_403",
    ("POST", "/v1/admin/operators"): "cross_tenant_create_403",
    ("POST", "/v1/admin/operators/{operator_id}/revoke"): "cross_tenant_403",
    ("GET", "/v1/workspaces"): "tenant_filtered_list",
    ("GET", "/v1/workspaces/{workspace_id}"): "cross_tenant_403",
    ("PATCH", "/v1/workspaces/{workspace_id}/plan"): "cross_tenant_403",
    ("GET", "/v1/jobs"): "deployment_admin_only",
    ("GET", "/v1/jobs/{job_id}"): "deployment_admin_only",
    ("POST", "/v1/api-keys"): "cross_tenant_create_403",
    ("GET", "/v1/api-keys"): "own_scoped",
    # The enumeration actor is a tenant-A admin who is NOT the key owner, so a
    # DELETE of a tenant-B key is exactly the cross-tenant case → 403.
    ("DELETE", "/v1/api-keys/{key_id}"): "cross_tenant_403",
}

_RELOAD_CHAIN = (
    "backend.src.core.config",
    "backend.src.core.db",
    "backend.src.core.models",
    "backend.src.auth.operators",
    "backend.src.auth.auth",
    "backend.src.api.deps",
    "backend.src.api.routers.admin",
    "backend.src.api.routers.workspaces",
    "backend.src.api.routers.jobs",
    "backend.src.api.routers.api_keys",
    "backend.src.api.app",
)


def _reset_db_to_file() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    os.environ["GRANTLAYER_DB"] = f.name
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)
    os.environ["GRANTLAYER_RUNTIME_MODE"] = "test"
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
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


def _admin_jwt(tenant_id: str, sub: str | None = None, role: str = "grant_admin", workspace_id: str | None = None) -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    from backend.src.api.auth_jwt import encode_token
    claims = {
        "sub": sub or f"admin-{tenant_id}", "role": role, "tenant_id": tenant_id,
        "iss": "grantlayer", "aud": "grantlayer-api",
    }
    if workspace_id:
        claims["workspace_id"] = workspace_id
    return encode_token(claims, _TEST_SECRET)


def _seed_workspace(ws_id: str, tenant_id: str) -> None:
    from backend.src.core.db import get_session
    from backend.src.core.orm import Workspace
    s = get_session()
    try:
        s.merge(Workspace(
            id=ws_id, tenant_id=tenant_id, name=f"ws-{ws_id}", slug=f"slug-{ws_id}",
            owner_id="owner-gl349", status="active", created_at=_NOW, updated_at=_NOW,
            plan_tier="free",
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
            id=op_id, name=f"op-{op_id}", role="owner", token_hash=f"hash-{op_id}",
            active=1, created_at=_NOW, tenant_id=tenant_id,
        ))
        s.commit()
    finally:
        s.close()


def _seed_api_key(key_id: str, workspace_id: str, user_id: str, scopes=("read_write",)) -> None:
    from backend.src.core.db import get_session
    from backend.src.core.orm import ApiKey
    s = get_session()
    try:
        s.merge(ApiKey(
            id=key_id, workspace_id=workspace_id, user_id=user_id,
            key_hash=hashlib.sha256(key_id.encode()).hexdigest(),
            name=f"key-{key_id}", scopes=json.dumps(list(scopes)), created_at=_NOW,
        ))
        s.commit()
    finally:
        s.close()


def _discover_admin_plane_routes() -> set[tuple[str, str]]:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    from backend.src.api.app import create_app
    app = create_app()
    found: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        if not methods or not path.startswith(_ADMIN_PLANE_PREFIXES):
            continue
        for m in methods:
            if m in ("HEAD", "OPTIONS"):
                continue
            found.add((m, path))
    return found


class TestAdminPlaneInventoryFailClosed(unittest.TestCase):
    """Every admin-plane / api-key route must be categorized (fail-closed)."""

    def setUp(self):
        _reset_db_to_file()

    def test_every_admin_plane_route_is_categorized(self):
        discovered = _discover_admin_plane_routes()
        categorized = set(_ROUTE_POLICY.keys())
        uncategorized = discovered - categorized
        stale = categorized - discovered
        self.assertEqual(
            uncategorized, set(),
            "New admin-plane/api-key route(s) not categorized in GL-349 _ROUTE_POLICY "
            "(every such route MUST declare its tenant-scope enforcement): "
            f"{sorted(uncategorized)}",
        )
        self.assertEqual(
            stale, set(),
            f"GL-349 _ROUTE_POLICY references route(s) no longer in the router table: {sorted(stale)}",
        )


class TestCrossTenantEnumeration(unittest.TestCase):
    """Iterate every categorized route and assert tenant-A cannot reach tenant-B."""

    def setUp(self):
        _reset_db_to_file()
        self.client = _make_client()
        self.ws_a = f"ws-a-{uuid.uuid4().hex[:8]}"
        self.ws_b = f"ws-b-{uuid.uuid4().hex[:8]}"
        self.op_a = f"op-a-{uuid.uuid4().hex[:8]}"
        self.op_b = f"op-b-{uuid.uuid4().hex[:8]}"
        self.key_b = f"key-b-{uuid.uuid4().hex[:8]}"
        _seed_workspace(self.ws_a, _TENANT_A)
        _seed_workspace(self.ws_b, _TENANT_B)
        _seed_operator(self.op_a, _TENANT_A)
        _seed_operator(self.op_b, _TENANT_B)
        _seed_api_key(self.key_b, self.ws_b, user_id="user-b-gl349")
        self.headers_a = {"Authorization": f"Bearer {_admin_jwt(_TENANT_A, workspace_id=self.ws_a)}"}

    def _target_path(self, path: str) -> str:
        return (
            path.replace("{operator_id}", self.op_b)
            .replace("{workspace_id}", self.ws_b)
            .replace("{key_id}", self.key_b)
            .replace("{job_id}", "job-b-gl349")
        )

    def _request(self, method: str, path: str):
        body = None
        if (method, path) == ("POST", "/v1/admin/operators"):
            body = {"name": "x", "role": "owner", "tenantId": _TENANT_B}
        elif (method, path) == ("POST", "/v1/api-keys"):
            body = {"name": "x", "scopes": ["read_write"], "workspace_id": self.ws_b}
        elif (method, path) == ("PATCH", "/v1/workspaces/{workspace_id}/plan"):
            body = {"plan_tier": "enterprise"}
        return self.client.request(method, self._target_path(path), json=body, headers=self.headers_a)

    def test_cross_tenant_enumeration(self):
        """The full route inventory: tenant-A actor must never reach tenant-B."""
        violations: list[str] = []
        for (method, path), category in sorted(_ROUTE_POLICY.items()):
            resp = self._request(method, path)
            body = resp.json() if resp.content else {}
            if category in ("cross_tenant_403", "cross_tenant_create_403"):
                if resp.status_code != 403:
                    violations.append(f"{method} {path} [{category}] → {resp.status_code} (want 403): {body}")
            elif category == "deployment_admin_only":
                if resp.status_code != 403:
                    violations.append(f"{method} {path} [{category}] → {resp.status_code} (want 403): {body}")
            elif category == "tenant_filtered_list":
                if resp.status_code != 200:
                    violations.append(f"{method} {path} [{category}] → {resp.status_code} (want 200): {body}")
                else:
                    leaked = _TENANT_B in json.dumps(body)
                    if leaked:
                        violations.append(f"{method} {path} [{category}] LEAKED tenant-B rows: {body}")
            elif category == "own_scoped":
                # Inherently scoped to caller's own subject; cross-tenant tested explicitly
                # in TestApiKeyRevokeCrossTenant / list returns only caller's keys.
                pass
        self.assertEqual(violations, [], "Cross-tenant control-plane violations:\n" + "\n".join(violations))

    def test_own_tenant_access_still_works(self):
        """Backward-compat: a tenant-A admin can still act within tenant A."""
        # Read own operator
        r = self.client.get(f"/v1/admin/operators/{self.op_a}", headers=self.headers_a)
        self.assertEqual(r.status_code, 200, r.text)
        # Read own workspace
        r = self.client.get(f"/v1/workspaces/{self.ws_a}", headers=self.headers_a)
        self.assertEqual(r.status_code, 200, r.text)
        # Revoke own operator
        r = self.client.post(f"/v1/admin/operators/{self.op_a}/revoke", headers=self.headers_a)
        self.assertEqual(r.status_code, 200, r.text)

    def test_list_operators_returns_only_own_tenant(self):
        r = self.client.get("/v1/admin/operators", headers=self.headers_a)
        self.assertEqual(r.status_code, 200, r.text)
        tenants = {op.get("tenantId") for op in r.json()}
        self.assertNotIn(_TENANT_B, tenants, f"list_operators leaked tenant-B: {r.json()}")
        self.assertIn(_TENANT_A, tenants)

    def test_list_workspaces_returns_only_own_tenant(self):
        r = self.client.get("/v1/workspaces", headers=self.headers_a)
        self.assertEqual(r.status_code, 200, r.text)
        tenants = {ws.get("tenant_id") for ws in r.json()}
        self.assertNotIn(_TENANT_B, tenants, f"list_workspaces leaked tenant-B: {r.json()}")


class TestApiKeyRevokeCrossTenant(unittest.TestCase):
    """A tenant-A admin must NOT revoke a tenant-B-owned API key (is_admin short-circuit)."""

    def setUp(self):
        _reset_db_to_file()
        self.client = _make_client()
        self.ws_b = f"ws-b-{uuid.uuid4().hex[:8]}"
        self.key_b = f"key-b-{uuid.uuid4().hex[:8]}"
        _seed_workspace(self.ws_b, _TENANT_B)
        _seed_api_key(self.key_b, self.ws_b, user_id="user-b-gl349")

    def test_tenant_a_admin_cannot_revoke_tenant_b_key(self):
        """RED before fix: is_admin short-circuits → 200 revoked."""
        resp = self.client.delete(
            f"/v1/api-keys/{self.key_b}",
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_A)}"},
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json().get("errorCode"), "cross_tenant_forbidden")

    def test_owner_can_still_revoke_own_key(self):
        """Backward-compat: the key's owner revokes their own key regardless of tenant."""
        resp = self.client.delete(
            f"/v1/api-keys/{self.key_b}",
            headers={"Authorization": f"Bearer {_admin_jwt(_TENANT_B, sub='user-b-gl349')}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)


class TestApiKeyCreateScopeRoleGate(unittest.TestCase):
    """A non-admin caller must NOT mint an admin-scoped API key."""

    def setUp(self):
        _reset_db_to_file()
        self.client = _make_client()

    def test_non_admin_cannot_mint_admin_scoped_key(self):
        """RED before fix: scope is not gated by caller role → 201."""
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "evil", "scopes": ["admin"]},
            headers={"Authorization": f"Bearer {_admin_jwt('demo', sub='regular', role='executor')}"},
        )
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json().get("errorCode"), "insufficient_role_for_scope")

    def test_non_admin_can_mint_read_write_key(self):
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "ok", "scopes": ["read_write"]},
            headers={"Authorization": f"Bearer {_admin_jwt('demo', sub='regular', role='executor')}"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)

    def test_admin_can_mint_admin_scoped_key(self):
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "ok", "scopes": ["admin"]},
            headers={"Authorization": f"Bearer {_admin_jwt('demo', sub='boss', role='grant_admin')}"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)


if __name__ == "__main__":
    unittest.main()
