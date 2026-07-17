"""GL-344 — Cross-tenant privilege escalation via body-derived workspace_id.

P0 SECURITY. Proves the EXACT behavior claimed by the fix:

- Templates: a grant_admin authenticated to workspace A creating a template with a
  body workspace_id bound to workspace B receives 403 (never silently bound to B);
  no body workspace_id binds to the authenticated workspace; a matching body value
  is accepted.
- API keys (contract superseded — see TestApiKeyWorkspaceAuthority): the binding is
  the creator's RESOLVED workspace; any body workspace_id is rejected outright.
- Cross-tenant template lookups (get / deactivate / new-version) return 404 — the
  IDOR is closed and the other tenant's template is never observable.
- A repo-wide static guard asserts no mutation handler reads workspace_id from the
  request body as an authority (positive allowlist, not a hand-maintained exclusion).

These tests MUST fail against the pre-fix code (body.workspace_id is trusted and
template lookups are unfiltered) and pass after the fix.
"""

from __future__ import annotations

import os
import unittest
import uuid

_TEST_SECRET = "gl344-test-hs256-secret-32chars!!!"


def _make_client():
    from fastapi.testclient import TestClient

    from backend.src.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _jwt(workspace_id: str, tenant_id: str, sub: str = "user-a", role: str = "grant_admin") -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from backend.src.api.auth_jwt import encode_token

    return encode_token(
        {
            "sub": sub,
            "role": role,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "iss": "grantlayer",
            "aud": "grantlayer-api",
        },
        _TEST_SECRET,
    )


def _db_mod():
    import backend.src.core.db as db_mod

    return db_mod


class TestApiKeyWorkspaceAuthority(unittest.TestCase):
    """API-key creation binds to the creator's RESOLVED workspace.

    CONTRACT RETIRED: the original tests here pinned claim-derived binding
    with a body workspace_id accepted when it matched the JWT claim. That
    contract enabled client-chosen workspace binding (internal JWTs carry no
    workspace claim, so keys silently bound to "default"). Superseded by
    server-side workspace resolution: the binding is the creator's resolved
    workspace, any body workspace_id is rejected outright, and a caller
    without a resolvable workspace context cannot mint a key at all.
    """

    def setUp(self):
        # Enter the TestClient context so all requests in this test share one
        # event loop (asyncpg engine is loop-bound; TestClient spins a fresh
        # loop per request otherwise). Test-harness only — production uses a
        # single uvicorn loop.
        self.client = self.enterContext(_make_client())
        # A real workspace row in the ambient DB (unique per run): resolution
        # validates row existence + tenant, unlike the retired claim contract.
        self.tenant = f"t-{uuid.uuid4()}"
        self.ws = str(uuid.uuid4())
        conn = _db_mod().get_conn()
        try:
            conn.execute(
                """INSERT INTO workspaces
                       (id, tenant_id, name, slug, owner_id, status,
                        created_at, updated_at)
                   VALUES (?, ?, 'authority-ws', ?, 'system', 'active',
                           '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')""",
                (self.ws, self.tenant, str(uuid.uuid4())),
            )
            conn.commit()
        finally:
            conn.close()
        self.auth = {
            "Authorization": f"Bearer {_jwt(self.ws, self.tenant, sub='admin-a', role='owner')}",
            "X-Workspace-Id": self.ws,
        }

    def test_any_body_workspace_rejected(self):
        """A body workspace_id — matching or not — is rejected fail-loud."""
        for value in (self.ws, "somewhere-else"):
            resp = self.client.post(
                "/v1/api-keys",
                json={"name": "k", "scopes": ["read_write"], "workspace_id": value},
                headers=self.auth,
            )
            self.assertEqual(resp.status_code, 400, resp.text)

    def test_key_binds_to_resolved_workspace(self):
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "ok", "scopes": ["read_write"]},
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(resp.json()["workspaceId"], self.ws)

    def test_no_resolvable_workspace_refused(self):
        """A caller with no resolvable workspace context cannot mint a key."""
        headers = {
            "Authorization": f"Bearer {_jwt('ignored', f't-{uuid.uuid4()}', sub='nobody')}"
        }
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "k", "scopes": ["read_write"]},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 403, resp.text)


class TestTemplateWorkspaceAuthority(unittest.TestCase):
    def setUp(self):
        # Enter the TestClient context so all requests in this test share one
        # event loop (asyncpg engine is loop-bound; TestClient spins a fresh
        # loop per request otherwise). Test-harness only — production uses a
        # single uvicorn loop.
        self.client = self.enterContext(_make_client())
        self.auth_a = {"Authorization": f"Bearer {_jwt('ws-A', 't-A', sub='admin-a')}"}

    def test_create_cross_tenant_body_workspace_rejected_403(self):
        resp = self.client.post(
            "/v1/grant-templates",
            json={"name": "evil", "workspace_id": "ws-B"},
            headers=self.auth_a,
        )
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_create_binds_to_authenticated_workspace(self):
        resp = self.client.post(
            "/v1/grant-templates",
            json={"name": "ok"},
            headers=self.auth_a,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(resp.json()["workspace_id"], "ws-A")

    def test_new_version_cross_tenant_body_workspace_rejected_403(self):
        create = self.client.post(
            "/v1/grant-templates",
            json={"name": "base"},
            headers=self.auth_a,
        )
        self.assertEqual(create.status_code, 201, create.text)
        tmpl_id = create.json()["id"]
        resp = self.client.post(
            f"/v1/grant-templates/{tmpl_id}/new-version",
            json={"name": "base v2", "workspace_id": "ws-B"},
            headers=self.auth_a,
        )
        self.assertEqual(resp.status_code, 403, resp.text)


class TestCrossTenantTemplateIdor(unittest.TestCase):
    def setUp(self):
        # Enter the TestClient context so all requests in this test share one
        # event loop (asyncpg engine is loop-bound; TestClient spins a fresh
        # loop per request otherwise). Test-harness only — production uses a
        # single uvicorn loop.
        self.client = self.enterContext(_make_client())
        self.auth_a = {"Authorization": f"Bearer {_jwt('ws-A', 't-A', sub='admin-a')}"}
        self.auth_b = {"Authorization": f"Bearer {_jwt('ws-B', 't-B', sub='admin-b')}"}
        # Tenant A creates a template in workspace A.
        create = self.client.post(
            "/v1/grant-templates",
            json={"name": "tenant-a-secret"},
            headers=self.auth_a,
        )
        self.assertEqual(create.status_code, 201, create.text)
        self.tmpl_id = create.json()["id"]

    def test_cross_tenant_get_returns_404(self):
        resp = self.client.get(f"/v1/grant-templates/{self.tmpl_id}", headers=self.auth_b)
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_cross_tenant_deactivate_returns_404(self):
        resp = self.client.post(
            f"/v1/grant-templates/{self.tmpl_id}/deactivate", headers=self.auth_b
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_cross_tenant_new_version_returns_404(self):
        resp = self.client.post(
            f"/v1/grant-templates/{self.tmpl_id}/new-version",
            json={"name": "stolen v2"},
            headers=self.auth_b,
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_owner_can_still_access_own_template(self):
        # Sanity: the legitimate owner is unaffected by the new filter.
        get_resp = self.client.get(f"/v1/grant-templates/{self.tmpl_id}", headers=self.auth_a)
        self.assertEqual(get_resp.status_code, 200, get_resp.text)


class TestVerifiedAuthorityPositiveAllowlist(unittest.TestCase):
    """GL-349 POSITIVE allowlist (replaces the old 4-pattern regex denylist).

    Enumerate EVERY create/update/delete handler + EVERY admin-plane handler from the
    live router table and assert each one derives tenant/workspace authority from a
    VERIFIED source. For each route a marker substring must appear in the handler's own
    source (``inspect.getsource(route.endpoint)``) — e.g. ``require_mutation_authz``,
    ``require_admin_scope``, ``assert_admin_tenant_scope``, ``_verified_workspace_id``.

    Fail-closed: a newly-added mutation/admin handler not present in these maps is RED by
    default, and a handler whose required verified-authority marker is missing is RED —
    so the cross-tenant class cannot recur one level deeper via a forgotten check.
    """

    _MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
    _ADMIN_PLANE_PREFIXES = ("/v1/admin", "/v1/workspaces", "/v1/jobs")

    # (method, path) → substring that MUST appear in the handler source as proof the
    # tenant/workspace authority comes from verified auth context.
    _VERIFIED_AUTHORITY: dict[tuple[str, str], str] = {
        # Standard mutation routes: shared authz gate over the resolved workspace ctx.
        ("POST", "/v1/grants"): "require_mutation_authz",
        ("POST", "/v1/grants/bulk-update"): "require_mutation_authz",
        ("POST", "/v1/grants/{grant_id}/revoke"): "require_mutation_authz",
        ("POST", "/v1/grant-requests"): "require_mutation_authz",
        ("POST", "/v1/grant-requests/bulk-approve"): "require_mutation_authz",
        ("POST", "/v1/grant-requests/bulk-reject"): "require_mutation_authz",
        ("POST", "/v1/grant-requests/{request_id}/approve"): "require_mutation_authz",
        ("POST", "/v1/grant-requests/{request_id}/deny"): "require_mutation_authz",
        ("POST", "/v1/approvals/evaluate"): "require_mutation_authz",
        ("POST", "/v1/approvals/lifecycle/build"): "require_mutation_authz",
        ("POST", "/v1/approvals/lifecycle/transition"): "require_mutation_authz",
        ("POST", "/v1/agent-permissions/assignments/resolve"): "require_mutation_authz",
        ("POST", "/v1/agent-permissions/evaluate"): "require_mutation_authz",
        ("POST", "/v1/compliance/readiness/build"): "require_mutation_authz",
        ("POST", "/v1/decision-provenance/v2/build"): "require_mutation_authz",
        ("POST", "/v1/policy-requirements/evaluate"): "require_mutation_authz",
        ("POST", "/v1/webhooks"): "require_mutation_authz",
        ("DELETE", "/v1/webhooks/{webhook_id}"): "require_mutation_authz",
        ("POST", "/v1/webhooks/{webhook_id}/test"): "require_mutation_authz",
        # Control-plane admin: shared AdminScope dependency (auth + tenant scope).
        ("GET", "/v1/admin/operators"): "require_admin_scope",
        ("GET", "/v1/admin/operators/{operator_id}"): "require_admin_scope",
        ("POST", "/v1/admin/operators"): "require_admin_scope",
        ("POST", "/v1/admin/operators/{operator_id}/revoke"): "require_admin_scope",
        ("GET", "/v1/workspaces"): "require_admin_scope",
        ("GET", "/v1/workspaces/{workspace_id}"): "require_admin_scope",
        ("PATCH", "/v1/workspaces/{workspace_id}/plan"): "require_admin_scope",
        ("GET", "/v1/jobs"): "require_admin_scope",
        ("GET", "/v1/jobs/{job_id}"): "require_admin_scope",
        # API-key management (JWT): create binds verified workspace + role-gates scope;
        # revoke confines a non-owner admin to the key's tenant.
        ("POST", "/v1/api-keys"): "async_resolve_auth_and_workspace",
        ("DELETE", "/v1/api-keys/{key_id}"): "assert_admin_tenant_scope",
        # Grant templates (JWT): workspace authority via _verified_workspace_id helper.
        ("POST", "/v1/grant-templates"): "_verified_workspace_id",
        ("POST", "/v1/grant-templates/{template_id}/deactivate"): "_verified_workspace_id",
        ("POST", "/v1/grant-templates/{template_id}/new-version"): "_verified_workspace_id",
        # GDPR (JWT): self-or-same-tenant-admin authorization.
        ("POST", "/v1/users/{user_id}/erase"): "_authorize_user_action",
        ("POST", "/v1/users/{user_id}/export-data"): "_authorize_user_action",
        # Challenge + auditor: workspace resolved from verified auth context.
        ("POST", "/v1/challenges"): "resolve_auth_and_workspace",
        ("POST", "/v1/auditor/exports/build"): "resolve_auth_and_workspace",
    }

    # Routes whose resource has NO tenant/workspace dimension (nothing to derive).
    # Still enumerated (fail-closed) with a documented reason.
    _NO_TENANT_AUTHORITY: dict[tuple[str, str], str] = {
        ("POST", "/v1/auth/token"): "credential exchange; issues a token, no tenant resource.",
        ("POST", "/v1/demo-action"): "demo bypass guarded by demo-mode flag.",
        ("POST", "/v1/notifications/unsubscribe"): "signed query-param token; no tenant resource.",
    }

    def _discover(self):
        import os
        os.environ.setdefault("GRANTLAYER_JWT_SECRET", "gl344-discover-secret-32chars!!!")
        from backend.src.api.app import create_app
        app = create_app()
        universe: dict[tuple[str, str], object] = {}
        for route in app.routes:
            methods = getattr(route, "methods", None)
            path = getattr(route, "path", "")
            if not methods or not path.startswith("/v1/"):
                continue
            is_mut = bool(methods & self._MUTATION_METHODS)
            is_admin = path.startswith(self._ADMIN_PLANE_PREFIXES)
            if not (is_mut or is_admin):
                continue
            for m in methods:
                if m in ("HEAD", "OPTIONS"):
                    continue
                if m not in self._MUTATION_METHODS and not is_admin:
                    continue
                universe[(m, path)] = getattr(route, "endpoint", None)
        return universe

    def test_every_handler_is_classified(self):
        universe = set(self._discover().keys())
        classified = set(self._VERIFIED_AUTHORITY) | set(self._NO_TENANT_AUTHORITY)
        unclassified = universe - classified
        stale = classified - universe
        self.assertEqual(
            unclassified, set(),
            "New mutation/admin handler(s) not in the GL-349 verified-authority allowlist "
            "(classify each with the source of its tenant/workspace authority): "
            f"{sorted(unclassified)}",
        )
        self.assertEqual(
            stale, set(),
            f"Allowlist references handler(s) no longer in the router table: {sorted(stale)}",
        )

    def test_each_handler_derives_authority_from_verified_source(self):
        import inspect
        universe = self._discover()
        offenders: list[str] = []
        for (method, path), marker in self._VERIFIED_AUTHORITY.items():
            endpoint = universe.get((method, path))
            if endpoint is None:
                offenders.append(f"{method} {path}: route not found")
                continue
            try:
                src = inspect.getsource(endpoint)
            except OSError:
                offenders.append(f"{method} {path}: source unavailable")
                continue
            if marker not in src:
                offenders.append(f"{method} {path}: missing verified-authority marker {marker!r}")
        self.assertEqual(
            offenders, [],
            "Handler(s) do not derive tenant/workspace authority from a verified source:\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
