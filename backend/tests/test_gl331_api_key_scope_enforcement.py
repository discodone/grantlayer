"""GL-331 — Enforce API-key scopes.

End-to-end tests that would FAIL if scope enforcement is not wired up:
- A read_only API key must receive 403 on mutation routes (POST/PATCH/DELETE).
- A read_write API key must pass the scope gate (receives 201 or a business-logic error).
"""

from __future__ import annotations

import os
import unittest

_TEST_SECRET = "gl331-test-hs256-secret-32chars!!"


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
        {"sub": "scope-test-user", "role": role, "tenant_id": "demo",
         "iss": "grantlayer", "aud": "grantlayer-api"},
        _TEST_SECRET,
    )


def _create_api_key(client, scope: str):
    """Create an API key via the API and return its raw token."""
    resp = client.post(
        "/v1/api-keys",
        json={"name": f"test-{scope}", "scopes": [scope]},
        headers={"Authorization": f"Bearer {_jwt_token()}"},
    )
    assert resp.status_code == 201, f"Failed to create {scope} key: {resp.text}"
    return resp.json()["key"]


_GRANT_BODY = {
    "subjectId": "agent-001",
    "role": "executor",
    "action": "deploy",
    "resource": "service/api",
    "validFrom": "2025-01-01T00:00:00Z",
    "validUntil": "2026-01-01T00:00:00Z",
    "createdBy": "scope-test-user",
    "reason": "scope enforcement test",
}


class TestReadOnlyKeyBlocksMutations(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()
        self.readonly_key = _create_api_key(self.client, "read_only")

    def test_read_only_key_gets_403_on_post_grants(self):
        """A read_only key must be rejected on POST /v1/grants with 403."""
        resp = self.client.post(
            "/v1/grants",
            json=_GRANT_BODY,
            headers={"Authorization": f"Bearer {self.readonly_key}"},
        )
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertEqual(body.get("errorCode"), "insufficient_scope")

    def test_read_only_key_gets_403_on_revoke(self):
        """A read_only key must be rejected on POST /v1/grants/{id}/revoke with 403."""
        resp = self.client.post(
            "/v1/grants/nonexistent-id/revoke",
            json={"reason": "test"},
            headers={"Authorization": f"Bearer {self.readonly_key}"},
        )
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertEqual(body.get("errorCode"), "insufficient_scope")

    def test_read_only_key_can_read_grants(self):
        """A read_only key must be allowed on GET /v1/grants (read-only operation)."""
        resp = self.client.get(
            "/v1/grants",
            headers={"Authorization": f"Bearer {self.readonly_key}"},
        )
        # 200 or 4xx from business logic — but NOT 403 insufficient_scope
        body = resp.json()
        self.assertNotEqual(body.get("errorCode"), "insufficient_scope")


class TestReadWriteKeyPassesScopeGate(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()
        self.rw_key = _create_api_key(self.client, "read_write")

    def test_read_write_key_passes_scope_gate_on_post_grants(self):
        """A read_write key must not receive 403 insufficient_scope on POST /v1/grants."""
        resp = self.client.post(
            "/v1/grants",
            json=_GRANT_BODY,
            headers={"Authorization": f"Bearer {self.rw_key}"},
        )
        body = resp.json()
        # The scope gate must not block it; may succeed (201) or fail for business reasons
        self.assertNotEqual(resp.status_code, 403, f"Scope gate wrongly blocked read_write key: {body}")
        self.assertNotEqual(body.get("errorCode"), "insufficient_scope")


class TestScopeFunctionUnit(unittest.TestCase):
    def test_enforce_api_key_write_scope_read_only_raises(self):
        """Unit: enforce_api_key_write_scope raises 403 for read_only API key."""
        from fastapi import HTTPException
        from backend.src.api.deps import enforce_api_key_write_scope
        with self.assertRaises(HTTPException) as ctx:
            enforce_api_key_write_scope({"auth_method": "api_key", "scopes": ["read_only"]})
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["errorCode"], "insufficient_scope")

    def test_enforce_api_key_write_scope_read_write_passes(self):
        """Unit: enforce_api_key_write_scope does not raise for read_write key."""
        from backend.src.api.deps import enforce_api_key_write_scope
        enforce_api_key_write_scope({"auth_method": "api_key", "scopes": ["read_write"]})

    def test_enforce_api_key_write_scope_admin_passes(self):
        """Unit: enforce_api_key_write_scope does not raise for admin key."""
        from backend.src.api.deps import enforce_api_key_write_scope
        enforce_api_key_write_scope({"auth_method": "api_key", "scopes": ["admin"]})

    def test_enforce_api_key_write_scope_non_api_key_passes(self):
        """Unit: enforce_api_key_write_scope ignores JWT callers."""
        from backend.src.api.deps import enforce_api_key_write_scope
        enforce_api_key_write_scope({"auth_method": "jwt", "role": "grant_admin"})

    def test_enforce_workspace_mutation_accepts_auth_ctx(self):
        """Unit: enforce_workspace_mutation with read_only auth_ctx raises 403."""
        from fastapi import HTTPException
        from backend.src.api.deps import enforce_workspace_mutation
        ws = {"workspace_id": "ws1", "tenant_id": "t1", "cross_workspace_access": False,
              "workspace_member_role": None}
        auth = {"auth_method": "api_key", "scopes": ["read_only"]}
        with self.assertRaises(HTTPException) as ctx:
            enforce_workspace_mutation(ws, auth)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["errorCode"], "insufficient_scope")
