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

import pytest

_TEST_SECRET = "gl342-test-hs256-secret-32chars!!"

# GL-349: the old silent `_SCOPE_EXEMPT_PATHS` denylist is DISSOLVED. A mutation route
# may skip the *read_only API-key scope* gate ONLY because it authenticates via a
# different scheme (no gl_live_ API key reaches it) — never because it has no security.
# Every entry below carries (a) the reason it is exempt from the API-key scope gate and
# (b) the test that DOES enforce its tenant/authz scope. `test_no_mutation_route_is_silently_exempt`
# asserts this map exactly matches the non-API-key mutation routes (fail-closed): a new
# exempt route with no documented justification is RED.
_SCOPE_GATE_JUSTIFICATION: dict[str, str] = {
    "/v1/auth/token": "credential exchange; no API key; per-IP rate-limited (test_gl251).",
    "/v1/admin/operators": "admin bearer; tenant-scoped + enumerated in test_gl349.",
    "/v1/admin/operators/{operator_id}/revoke": "admin bearer; tenant-scoped + enumerated in test_gl349.",
    "/v1/api-keys": "API-key mgmt via JWT; create role-gated + workspace-bound (test_gl344/test_gl349).",
    "/v1/api-keys/{key_id}": "API-key mgmt via JWT; revoke tenant-scoped (test_gl349).",
    "/v1/demo-action": "demo bypass, guarded by demo-mode flag (test_gl190/test_gl262).",
    "/v1/challenges": "challenge protocol; auth + workspace resolved (test_gl345 wired-list).",
    "/v1/auditor/exports/build": "auditor-role gate via resolve_auth_and_workspace.",
    "/v1/grant-templates": "JWT-only; workspace-bound authority (test_gl344).",
    "/v1/grant-templates/{template_id}/deactivate": "JWT-only; workspace-scoped IDOR closed (test_gl344).",
    "/v1/grant-templates/{template_id}/new-version": "JWT-only; workspace-scoped IDOR closed (test_gl344).",
    "/v1/users/{user_id}/erase": "GDPR JWT-only; tenant-scoped (test_gl347).",
    "/v1/users/{user_id}/export-data": "GDPR JWT-only; tenant-scoped (test_gl347).",
    "/v1/workspaces/{workspace_id}/plan": "admin bearer; tenant-scoped + enumerated in test_gl349.",
    "/v1/notifications/unsubscribe": "query-param signed token, no bearer auth.",
}

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
            "tenant_id": "demo",
            "workspace_id": "ws-gl342",
            "iss": "grantlayer",
            "aud": "grantlayer-api",
        },
        _TEST_SECRET,
    )


def _create_api_key(client, scope: str) -> str:
    resp = client.post(
        "/v1/api-keys",
        json={"name": f"gl342-{scope}", "scopes": [scope]},
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
        if path in _SCOPE_GATE_JUSTIFICATION:
            continue
        for m in sorted(methods):
            routes.append((m, path))
    return sorted(routes, key=lambda x: (x[1], x[0]))


def _all_v1_mutation_paths() -> set[str]:
    """Every distinct /v1/ path that exposes at least one mutation method."""
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    from backend.src.api.app import create_app
    app = create_app()
    paths: set[str] = set()
    for route in app.routes:
        if not hasattr(route, "methods"):
            continue
        if not (route.methods & _MUTATION_METHODS):
            continue
        path: str = getattr(route, "path", "")
        if path.startswith("/v1/"):
            paths.add(path)
    return paths


def _to_test_path(path: str) -> str:
    """Replace FastAPI path params with a safe placeholder."""
    return re.sub(r"\{[^}]+\}", "nonexistent-gl342", path)


def _body_for(path: str) -> dict:
    """Return a valid minimal body for the given route path, or {} for dict-body routes."""
    return _ROUTE_BODY.get(path, {})


class TestNoSilentExemption(unittest.TestCase):
    """GL-349: the dissolved denylist must be a documented, fail-closed allowlist.

    Every /v1/ mutation route is EITHER scope-gated (tested for read_only/OPA above)
    OR carries a non-empty documented justification in _SCOPE_GATE_JUSTIFICATION. A new
    mutation route that is neither is RED — it cannot be silently exempted from security.
    """

    def test_no_mutation_route_is_silently_exempt(self):
        all_paths = _all_v1_mutation_paths()
        gated_paths = {p for _, p in _collect_testable_mutation_routes()}
        justified_paths = set(_SCOPE_GATE_JUSTIFICATION)

        uncovered = all_paths - gated_paths - justified_paths
        self.assertEqual(
            uncovered, set(),
            "Mutation route(s) neither scope-gated nor justified — silent exemption is "
            f"forbidden. Add scope enforcement or a documented justification: {sorted(uncovered)}",
        )

        stale = justified_paths - all_paths
        self.assertEqual(
            stale, set(),
            f"_SCOPE_GATE_JUSTIFICATION references path(s) no longer in the router table: {sorted(stale)}",
        )

    def test_every_justification_is_non_empty(self):
        empty = [p for p, reason in _SCOPE_GATE_JUSTIFICATION.items() if not reason.strip()]
        self.assertEqual(empty, [], f"Exempt path(s) missing a documented justification: {empty}")


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
        # Enter the TestClient context so all requests in this class share one
        # event loop (asyncpg engine is loop-bound; TestClient spins a fresh
        # loop per request otherwise). Test-harness only — production uses a
        # single uvicorn loop.
        cls.client = cls.enterClassContext(_make_client())
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


# Seeds a shared API key in setUpClass; opt out of the per-test PostgreSQL
# TRUNCATE fixture so the key survives across the class's tests (the fixture is
# a no-op on SQLite, so this only matters under the PostgreSQL Full Suite).
@pytest.mark.no_db_truncate
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
        # Enter the TestClient context so all requests in this class share one
        # event loop (asyncpg engine is loop-bound; TestClient spins a fresh
        # loop per request otherwise). Test-harness only — production uses a
        # single uvicorn loop.
        cls.client = cls.enterClassContext(_make_client())
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
