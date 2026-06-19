"""GL-342 — Enforce read_only scope + OPA policy on ALL mutation routes.

Tests that FAIL on the unpatched codebase:
1. Every API-key-accessible mutation route must return 403 insufficient_scope for a
   read_only key (before fix: ~16 routes silently accept the key and return business
   logic responses: 200, 400, 404, 422 instead of 403).
2. OPA deny must be wired to every mutation route via a shared require_mutation_authz
   dependency in deps.py (before fix: only grant.create checks OPA).

Excluded from scope-gate test — separate auth or no API key resolution:
  - /v1/auth/token            credential exchange
  - /v1/admin/*               admin bearer token
  - /v1/api-keys (POST/DEL)   API key management via JWT
  - /v1/demo-action           demo bypass
  - /v1/challenges            challenge protocol
  - /v1/auditor/exports/build auditor-role gate
  - /v1/grant-templates/*     JWT-only (no API key resolution today)
  - /v1/users/*               JWT-only (GDPR)
  - /v1/workspaces/*          admin-only gate
  - /v1/notifications/unsubscribe (POST)  query-param token, no bearer auth
"""

from __future__ import annotations

import os
import re
import unittest
from unittest.mock import AsyncMock, patch

_TEST_SECRET = "gl342-test-hs256-secret-32chars!!"

# Paths that legitimately skip the read_only API-key scope gate.
_SCOPE_EXEMPT_PATHS = frozenset({
    "/v1/auth/token",
    "/v1/admin/operators",
    "/v1/admin/operators/{operator_id}/revoke",
    "/v1/api-keys",
    "/v1/api-keys/{key_id}",
    "/v1/demo-action",
    "/v1/challenges",
    "/v1/auditor/exports/build",
    "/v1/grant-templates",
    "/v1/grant-templates/{template_id}/deactivate",
    "/v1/grant-templates/{template_id}/new-version",
    "/v1/users/{user_id}/erase",
    "/v1/users/{user_id}/export-data",
    "/v1/workspaces/{workspace_id}/plan",
    "/v1/notifications/unsubscribe",
})

_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Minimal valid bodies for routes with required Pydantic body fields.
# Routes not listed here receive json={} (dict body or no required fields).
_ROUTE_BODY: dict[str, dict] = {
    "/v1/grants": {
        "subjectId": "agent-001",
        "role": "executor",
        "action": "deploy",
        "resource": "service/api",
        "validFrom": "2025-01-01T00:00:00Z",
        "validUntil": "2026-01-01T00:00:00Z",
        "createdBy": "gl342-test",
        "reason": "GL-342 scope enforcement test",
    },
    "/v1/grants/bulk-update": {"grantIds": ["g-gl342-001"]},
    "/v1/grant-requests": {
        "subjectId": "agent-001",
        "role": "executor",
        "action": "deploy",
        "resource": "service/api",
        "validFrom": "2025-01-01T00:00:00Z",
        "validUntil": "2026-01-01T00:00:00Z",
        "reason": "GL-342 scope enforcement test",
    },
    "/v1/grant-requests/bulk-approve": {"requestIds": ["r-gl342-001"]},
    "/v1/grant-requests/bulk-reject": {"requestIds": ["r-gl342-001"]},
    "/v1/grant-requests/{request_id}/deny": {"reason": "GL-342 test denial"},
    "/v1/webhooks": {"url": "https://gl342.example.com/hook", "events": ["grant.created"]},
}


def _make_client():
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _jwt_token(role: str = "grant_admin") -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    from backend.src.api.auth_jwt import encode_token
    return encode_token(
        {
            "sub": "gl342-test-user",
            "role": role,
            "tenant_id": "t-gl342",
            "workspace_id": "ws-gl342",
            "iss": "grantlayer",
            "aud": "grantlayer-api",
        },
        _TEST_SECRET,
    )


def _create_api_key(client, scope: str) -> str:
    resp = client.post(
        "/v1/api-keys",
        json={"name": f"gl342-{scope}", "scopes": [scope], "workspace_id": "ws-gl342"},
        headers={"Authorization": f"Bearer {_jwt_token()}"},
    )
    assert resp.status_code == 201, f"API key creation failed ({scope}): {resp.text}"
    return resp.json()["key"]


def _collect_testable_mutation_routes() -> list[tuple[str, str]]:
    """Return (method, path) for all non-exempt mutation routes discovered from the live app."""
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    from backend.src.api.app import create_app
    app = create_app()
    routes: list[tuple[str, str]] = []
    for route in app.routes:
        if not hasattr(route, "methods"):
            continue
        methods = route.methods & _MUTATION_METHODS
        if not methods:
            continue
        path: str = getattr(route, "path", "")
        if not path.startswith("/v1/"):
            continue
        if path in _SCOPE_EXEMPT_PATHS:
            continue
        for m in sorted(methods):
            routes.append((m, path))
    return sorted(routes, key=lambda x: (x[1], x[0]))


def _to_test_path(path: str) -> str:
    """Replace FastAPI path params with a safe placeholder."""
    return re.sub(r"\{[^}]+\}", "nonexistent-gl342", path)


def _body_for(path: str) -> dict:
    """Return a valid minimal body for the given route path, or {} for dict-body routes."""
    return _ROUTE_BODY.get(path, {})


class TestScopeEnforcementDiscovery(unittest.TestCase):
    """Sanity: the route enumeration must find a meaningful set of mutation routes."""

    def test_minimum_route_count(self):
        """Enumeration must discover at least 12 non-exempt mutation routes."""
        routes = _collect_testable_mutation_routes()
        self.assertGreaterEqual(
            len(routes),
            12,
            f"Expected ≥12 mutation routes, got {len(routes)}: {routes}",
        )

    def test_known_vulnerable_routes_are_included(self):
        """Confirmed-vulnerable routes must appear in the enumeration."""
        routes = _collect_testable_mutation_routes()
        route_set = {(m, p) for m, p in routes}
        required = [
            ("POST", "/v1/grants/bulk-update"),
            ("POST", "/v1/grant-requests/bulk-approve"),
            ("POST", "/v1/grant-requests/bulk-reject"),
            ("POST", "/v1/approvals/lifecycle/build"),
            ("POST", "/v1/approvals/lifecycle/transition"),
            ("POST", "/v1/approvals/evaluate"),
            ("POST", "/v1/webhooks"),
        ]
        missing = [(m, p) for m, p in required if (m, p) not in route_set]
        self.assertEqual(missing, [], f"Required vulnerable routes missing: {missing}")


class TestAllMutationRoutesBlockReadOnlyKeys(unittest.TestCase):
    """Every API-key-accessible mutation route must return 403 insufficient_scope.

    FAILS on unpatched code: only grants.create and grants.revoke enforce scope;
    the other ~16 mutation routes accept read_only keys and return 200/400/404/422.

    Note: valid minimal bodies (from _ROUTE_BODY) are provided so that Pydantic body
    validation does not mask missing scope enforcement. After the fix, require_mutation_authz
    runs immediately after auth resolution (before business logic), so all routes return 403.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = _make_client()
        cls.readonly_key = _create_api_key(cls.client, "read_only")
        cls.mutation_routes = _collect_testable_mutation_routes()

    def test_all_mutation_routes_block_read_only_keys(self):
        """A read_only API key must receive 403 insufficient_scope on every mutation route.

        Before fix: ~16 routes return non-403 (business logic runs unchecked).
        After fix:  all routes return 403 insufficient_scope via require_mutation_authz.
        """
        violations: list[tuple[str, str, int, str]] = []
        for method, path in self.mutation_routes:
            test_path = _to_test_path(path)
            body = _body_for(path)
            resp = self.client.request(
                method,
                test_path,
                json=body,
                headers={"Authorization": f"Bearer {self.readonly_key}"},
            )
            response_body = resp.json() if resp.content else {}
            error_code = response_body.get("errorCode", "")
            if resp.status_code != 403 or error_code != "insufficient_scope":
                violations.append((method, test_path, resp.status_code, error_code))

        if violations:
            lines = "\n".join(
                f"  {m} {p}  →  HTTP {code}  errorCode={ec or '<none>'}"
                for m, p, code, ec in violations
            )
            self.fail(
                f"{len(violations)} mutation route(s) do NOT block read_only API keys:\n{lines}\n\n"
                "Add `await require_mutation_authz(auth_ctx, ws_ctx)` immediately after "
                "auth resolution in each handler (before business logic / DB lookups)."
            )

    def test_read_write_key_is_not_blocked_by_scope_gate(self):
        """A read_write API key must not be rejected by the scope gate on any mutation route."""
        rw_key = _create_api_key(self.client, "read_write")
        scope_violations: list[tuple[str, str, str]] = []
        for method, path in self.mutation_routes:
            test_path = _to_test_path(path)
            body = _body_for(path)
            resp = self.client.request(
                method,
                test_path,
                json=body,
                headers={"Authorization": f"Bearer {rw_key}"},
            )
            response_body = resp.json() if resp.content else {}
            if response_body.get("errorCode") == "insufficient_scope":
                scope_violations.append((method, test_path, str(resp.status_code)))

        if scope_violations:
            lines = "\n".join(f"  {m} {p} → HTTP {c}" for m, p, c in scope_violations)
            self.fail(
                f"Scope gate wrongly blocked read_write key on {len(scope_violations)} route(s):\n{lines}"
            )


class TestAllMutationRoutesWiredToOpa(unittest.TestCase):
    """OPA deny must be wired to every mutation route via require_mutation_authz.

    FAILS on unpatched code: evaluate_policy is only called in grants.create;
    patching backend.src.api.deps.evaluate_policy has no effect since no route
    imports it from there yet (create=True makes the patch non-erroring but the
    routes never call deps.evaluate_policy, so blocked=0).

    After fix: every route calls deps.require_mutation_authz which calls
    deps.evaluate_policy; patching that single name blocks all of them.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = _make_client()
        cls.rw_key = _create_api_key(cls.client, "read_write")
        cls.rw_headers = {"Authorization": f"Bearer {cls.rw_key}"}
        cls.mutation_routes = _collect_testable_mutation_routes()

    def test_opa_deny_blocks_all_mutation_routes(self):
        """Patching deps.evaluate_policy to deny must block every mutation route with 403 policy_denied.

        Before fix: 0 routes blocked (patch exists but routes don't call deps.evaluate_policy).
        After fix:  all routes blocked (all call it via require_mutation_authz).

        Uses a read_write API key (not JWT) so resolve_auth_and_workspace succeeds and
        the request reaches require_mutation_authz / evaluate_policy before any DB check.
        """
        violations: list[tuple[str, str, int, str]] = []
        with patch(
            "backend.src.api.deps.evaluate_policy",
            new=AsyncMock(return_value=False),
            create=True,
        ):
            for method, path in self.mutation_routes:
                test_path = _to_test_path(path)
                body = _body_for(path)
                resp = self.client.request(
                    method,
                    test_path,
                    json=body,
                    headers=self.rw_headers,
                )
                response_body = resp.json() if resp.content else {}
                error_code = response_body.get("errorCode", "")
                if resp.status_code != 403 or error_code != "policy_denied":
                    violations.append((method, test_path, resp.status_code, error_code))

        if violations:
            lines = "\n".join(
                f"  {m} {p}  →  HTTP {code}  errorCode={ec or '<none>'}"
                for m, p, code, ec in violations
            )
            self.fail(
                f"{len(violations)} mutation route(s) were NOT blocked by OPA deny:\n{lines}\n\n"
                "Wire require_mutation_authz (which calls deps.evaluate_policy) to each handler."
            )

    def test_opa_allow_does_not_produce_policy_denied(self):
        """When OPA allows, read_write key requests must not receive policy_denied."""
        rw_key = _create_api_key(self.client, "read_write")
        rw_headers = {"Authorization": f"Bearer {rw_key}"}
        with patch(
            "backend.src.api.deps.evaluate_policy",
            new=AsyncMock(return_value=True),
            create=True,
        ):
            for method, path in self.mutation_routes:
                test_path = _to_test_path(path)
                body = _body_for(path)
                resp = self.client.request(
                    method,
                    test_path,
                    json=body,
                    headers=rw_headers,
                )
                response_body = resp.json() if resp.content else {}
                self.assertNotEqual(
                    response_body.get("errorCode"),
                    "policy_denied",
                    f"OPA-allow wrongly produced policy_denied on {method} {test_path}: {response_body}",
                )


class TestRequireMutationAuthzUnit(unittest.TestCase):
    """Unit tests for the require_mutation_authz dependency in deps.py.

    All tests FAIL before fix: the function does not exist yet.
    """

    def test_require_mutation_authz_exists_in_deps(self):
        """require_mutation_authz must be importable from backend.src.api.deps."""
        from backend.src.api import deps
        self.assertTrue(
            hasattr(deps, "require_mutation_authz"),
            "require_mutation_authz is not defined in backend.src.api.deps",
        )
        import inspect
        fn = getattr(deps, "require_mutation_authz")
        self.assertTrue(
            inspect.iscoroutinefunction(fn),
            "require_mutation_authz must be async (it awaits evaluate_policy)",
        )

    def test_require_mutation_authz_blocks_read_only_api_key(self):
        """require_mutation_authz must raise 403 insufficient_scope for a read_only API key."""
        import asyncio
        from fastapi import HTTPException
        from backend.src.api.deps import require_mutation_authz

        auth_ctx = {
            "auth_method": "api_key", "scopes": ["read_only"],
            "sub": "u1", "workspace_id": "ws-1", "tenant_id": "t-1",
        }
        ws_ctx = {
            "workspace_id": "ws-1", "tenant_id": "t-1",
            "workspace_member_role": None, "cross_workspace_access": False,
        }
        with patch("backend.src.api.deps.evaluate_policy", AsyncMock(return_value=True), create=True):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(require_mutation_authz(auth_ctx, ws_ctx))
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(ctx.exception.detail.get("errorCode"), "insufficient_scope")

    def test_require_mutation_authz_calls_evaluate_policy(self):
        """require_mutation_authz must call evaluate_policy once per invocation."""
        import asyncio
        from backend.src.api.deps import require_mutation_authz

        auth_ctx = {
            "auth_method": "jwt", "sub": "u1", "role": "grant_admin",
            "workspace_id": "ws-1", "tenant_id": "t-1", "scopes": [],
        }
        ws_ctx = {
            "workspace_id": "ws-1", "tenant_id": "t-1",
            "workspace_member_role": "grant_admin", "cross_workspace_access": False,
        }
        mock_policy = AsyncMock(return_value=True)
        with patch("backend.src.api.deps.evaluate_policy", mock_policy, create=True):
            asyncio.run(require_mutation_authz(auth_ctx, ws_ctx))

        self.assertTrue(mock_policy.called, "require_mutation_authz did not call evaluate_policy")

    def test_require_mutation_authz_raises_403_on_opa_deny(self):
        """require_mutation_authz must raise 403 policy_denied when OPA returns False."""
        import asyncio
        from fastapi import HTTPException
        from backend.src.api.deps import require_mutation_authz

        auth_ctx = {
            "auth_method": "jwt", "sub": "u1", "role": "grant_admin",
            "workspace_id": "ws-1", "tenant_id": "t-1", "scopes": [],
        }
        ws_ctx = {
            "workspace_id": "ws-1", "tenant_id": "t-1",
            "workspace_member_role": "grant_admin", "cross_workspace_access": False,
        }
        with patch("backend.src.api.deps.evaluate_policy", AsyncMock(return_value=False), create=True):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(require_mutation_authz(auth_ctx, ws_ctx))
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(ctx.exception.detail.get("errorCode"), "policy_denied")

    def test_evaluate_policy_importable_from_deps_after_fix(self):
        """After fix, backend.src.api.deps must export evaluate_policy (imported from opa_client)."""
        from backend.src.api import deps
        self.assertTrue(
            hasattr(deps, "evaluate_policy"),
            "deps.evaluate_policy not found — deps.py must import evaluate_policy from opa_client",
        )
