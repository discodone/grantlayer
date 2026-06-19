"""GL-345 — Auth + require_mutation_authz must run BEFORE any business-logic gate.

Regression from GL-342 (ordering bug). On grant_requests mutation routes,
`_require_operator_model()` ran BEFORE `resolve_auth_and_workspace` /
`require_mutation_authz`, so authz was non-invariant: when the operator model
is disabled, a `read_only` API key received 404 (operator_model_disabled)
instead of 403 (insufficient_scope). An attacker can therefore probe instance
configuration without passing the scope/authz gate, and GL-342's enumerating
test was green-by-luck only in isolation.

Two guarantees enforced here:
1. Authz is INVARIANT to the operator-model feature flag: a read_only key on a
   grant_requests mutation route gets 403 whether the operator model is enabled
   OR disabled (RED before fix: 404 when disabled).
2. POSITIVE wired-list: every /v1/ mutation route discovered from the live
   router table must be explicitly categorized below, and every route in the
   `mutation_authz` category must return 403 insufficient_scope for a read_only
   key in BOTH operator-model states. A new uncategorized mutation route fails
   the test (fail-closed), unlike GL-342's exclusion list.
"""

from __future__ import annotations

import os
import re
import unittest
from unittest import mock

_TEST_SECRET = "gl345-test-hs256-secret-32chars!!"
_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# ── POSITIVE wired-list ───────────────────────────────────────────────────────
# Every /v1/ mutation route maps to exactly one enforcement category. The test
# asserts the discovered router table equals these keys (fail-closed for new
# routes). Routes in `mutation_authz` must block read_only API keys with 403.
_CATEGORY_MUTATION_AUTHZ = "mutation_authz"

_ROUTE_POLICY: dict[tuple[str, str], str] = {
    # Standard API-key mutation routes — require_mutation_authz wired.
    ("POST", "/v1/grants"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/grants/bulk-update"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/grants/{grant_id}/revoke"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/grant-requests"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/grant-requests/bulk-approve"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/grant-requests/bulk-reject"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/grant-requests/{request_id}/approve"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/grant-requests/{request_id}/deny"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/approvals/evaluate"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/approvals/lifecycle/build"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/approvals/lifecycle/transition"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/agent-permissions/assignments/resolve"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/agent-permissions/evaluate"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/compliance/readiness/build"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/decision-provenance/v2/build"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/policy-requirements/evaluate"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/webhooks"): _CATEGORY_MUTATION_AUTHZ,
    ("DELETE", "/v1/webhooks/{webhook_id}"): _CATEGORY_MUTATION_AUTHZ,
    ("POST", "/v1/webhooks/{webhook_id}/test"): _CATEGORY_MUTATION_AUTHZ,
    # Routes that legitimately use a DIFFERENT auth/enforcement scheme.
    ("POST", "/v1/auth/token"): "credential_exchange",
    ("POST", "/v1/admin/operators"): "admin_plane",
    ("POST", "/v1/admin/operators/{operator_id}/revoke"): "admin_plane",
    ("PATCH", "/v1/workspaces/{workspace_id}/plan"): "admin_plane",
    ("POST", "/v1/api-keys"): "api_key_mgmt",
    ("DELETE", "/v1/api-keys/{key_id}"): "api_key_mgmt",
    ("POST", "/v1/demo-action"): "demo",
    ("POST", "/v1/challenges"): "challenge",
    ("POST", "/v1/auditor/exports/build"): "auditor_role",
    ("POST", "/v1/grant-templates"): "jwt_only",
    ("POST", "/v1/grant-templates/{template_id}/deactivate"): "jwt_only",
    ("POST", "/v1/grant-templates/{template_id}/new-version"): "jwt_only",
    ("POST", "/v1/users/{user_id}/erase"): "gdpr_jwt_only",
    ("POST", "/v1/users/{user_id}/export-data"): "gdpr_jwt_only",
    ("POST", "/v1/notifications/unsubscribe"): "query_token",
}

_ROUTE_BODY: dict[str, dict] = {
    "/v1/grants": {
        "subjectId": "agent-001", "role": "executor", "action": "deploy",
        "resource": "service/api", "validFrom": "2025-01-01T00:00:00Z",
        "validUntil": "2026-01-01T00:00:00Z", "createdBy": "gl345",
        "reason": "GL-345 authz-order test",
    },
    "/v1/grants/bulk-update": {"grantIds": ["g-gl345-001"]},
    "/v1/grant-requests": {
        "subjectId": "agent-001", "role": "executor", "action": "deploy",
        "resource": "service/api", "validFrom": "2025-01-01T00:00:00Z",
        "validUntil": "2026-01-01T00:00:00Z", "reason": "GL-345 authz-order test",
    },
    "/v1/grant-requests/bulk-approve": {"requestIds": ["r-gl345-001"]},
    "/v1/grant-requests/bulk-reject": {"requestIds": ["r-gl345-001"]},
    "/v1/grant-requests/{request_id}/deny": {"reason": "GL-345 test denial"},
    "/v1/webhooks": {"url": "https://gl345.example.com/hook", "events": ["grant.created"]},
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
            "sub": "gl345-test-user", "role": role,
            "tenant_id": "t-gl345", "workspace_id": "ws-gl345",
            "iss": "grantlayer", "aud": "grantlayer-api",
        },
        _TEST_SECRET,
    )


def _create_api_key(client, scope: str) -> str:
    resp = client.post(
        "/v1/api-keys",
        json={"name": f"gl345-{scope}", "scopes": [scope], "workspace_id": "ws-gl345"},
        headers={"Authorization": f"Bearer {_jwt_token()}"},
    )
    assert resp.status_code == 201, f"API key creation failed ({scope}): {resp.text}"
    return resp.json()["key"]


def _discover_mutation_routes() -> set[tuple[str, str]]:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    from backend.src.api.app import create_app
    app = create_app()
    found: set[tuple[str, str]] = set()
    for route in app.routes:
        if not hasattr(route, "methods"):
            continue
        methods = route.methods & _MUTATION_METHODS
        path: str = getattr(route, "path", "")
        if not methods or not path.startswith("/v1/"):
            continue
        for m in methods:
            found.add((m, path))
    return found


def _to_test_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "nonexistent-gl345", path)


class TestPositiveWiredList(unittest.TestCase):
    """The router table must exactly match the categorized wired-list (fail-closed)."""

    def test_every_mutation_route_is_categorized(self):
        discovered = _discover_mutation_routes()
        categorized = set(_ROUTE_POLICY.keys())
        uncategorized = discovered - categorized
        stale = categorized - discovered
        self.assertEqual(
            uncategorized, set(),
            f"New mutation route(s) not in the GL-345 positive wired-list "
            f"(categorize each explicitly): {sorted(uncategorized)}",
        )
        self.assertEqual(
            stale, set(),
            f"Wired-list contains route(s) no longer in the router table: {sorted(stale)}",
        )


class TestAuthzInvariantToOperatorModel(unittest.TestCase):
    """Authz must run before the operator-model business gate (RED before fix)."""

    @classmethod
    def setUpClass(cls):
        cls.client = _make_client()
        cls.readonly_key = _create_api_key(cls.client, "read_only")

    def _assert_403_insufficient_scope(self, method, path, operator_enabled):
        test_path = _to_test_path(path)
        body = _ROUTE_BODY.get(path, {})
        with mock.patch(
            "backend.src.core.config.ENABLE_OPERATOR_MODEL", operator_enabled
        ):
            resp = self.client.request(
                method, test_path, json=body,
                headers={"Authorization": f"Bearer {self.readonly_key}"},
            )
        rbody = resp.json() if resp.content else {}
        self.assertEqual(
            (resp.status_code, rbody.get("errorCode")),
            (403, "insufficient_scope"),
            f"{method} {test_path} (operator_model={operator_enabled}) returned "
            f"{resp.status_code}/{rbody.get('errorCode')}; authz must run before the "
            f"operator-model gate.",
        )

    def test_grant_requests_create_403_when_operator_model_disabled(self):
        """RED before fix: returns 404 operator_model_disabled instead of 403."""
        self._assert_403_insufficient_scope("POST", "/v1/grant-requests", False)

    def test_grant_requests_approve_403_when_operator_model_disabled(self):
        self._assert_403_insufficient_scope(
            "POST", "/v1/grant-requests/{request_id}/approve", False
        )

    def test_grant_requests_deny_403_when_operator_model_disabled(self):
        self._assert_403_insufficient_scope(
            "POST", "/v1/grant-requests/{request_id}/deny", False
        )

    def test_all_mutation_authz_routes_block_read_only_in_both_states(self):
        """Every mutation_authz route returns 403 insufficient_scope regardless of
        the operator-model flag — authz is invariant to business preconditions."""
        routes = [
            (m, p) for (m, p), cat in _ROUTE_POLICY.items()
            if cat == _CATEGORY_MUTATION_AUTHZ
        ]
        violations: list[str] = []
        for operator_enabled in (True, False):
            for method, path in routes:
                test_path = _to_test_path(path)
                body = _ROUTE_BODY.get(path, {})
                with mock.patch(
                    "backend.src.core.config.ENABLE_OPERATOR_MODEL", operator_enabled
                ):
                    resp = self.client.request(
                        method, test_path, json=body,
                        headers={"Authorization": f"Bearer {self.readonly_key}"},
                    )
                rbody = resp.json() if resp.content else {}
                if resp.status_code != 403 or rbody.get("errorCode") != "insufficient_scope":
                    violations.append(
                        f"  {method} {test_path} operator_model={operator_enabled} "
                        f"→ {resp.status_code}/{rbody.get('errorCode')}"
                    )
        if violations:
            self.fail(
                "Routes failed to enforce authz before business gates:\n"
                + "\n".join(violations)
            )


if __name__ == "__main__":
    unittest.main()
