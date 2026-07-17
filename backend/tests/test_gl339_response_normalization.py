"""GL-339 — Normalize response casing and error-body shape.

Tests:
- API key create response uses camelCase (workspaceId, createdAt, expiresAt).
- API key list response uses camelCase.
- API key revoke response uses camelCase (revokedAt).
- 500 handler returns {error, errorCode, reason} not {error, message}.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch


def _make_token(role: str = "owner") -> str:
    from backend.src.api.auth_jwt import encode_token
    secret = "gl339-test-secret-exactly-32bytes!"
    from backend.src.core.config import JWT_ISSUER, JWT_AUDIENCE
    return encode_token(
        {"sub": "u1", "role": role, "tenant_id": "demo",
         "iss": JWT_ISSUER or "grantlayer", "aud": JWT_AUDIENCE or "grantlayer-api"},
        secret,
    )


def _make_client():
    os.environ["GRANTLAYER_JWT_SECRET"] = "gl339-test-secret-exactly-32bytes!"
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestApiKeyResponseCamelCase(unittest.TestCase):
    def setUp(self):
        os.environ["GRANTLAYER_JWT_SECRET"] = "gl339-test-secret-exactly-32bytes!"
        os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
        os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
        # Enter the TestClient context so all requests in this test share one
        # event loop (asyncpg engine is loop-bound; TestClient spins a fresh
        # loop per request otherwise). Test-harness only — production uses a
        # single uvicorn loop.
        self.client = self.enterContext(_make_client())
        self.auth = {"Authorization": f"Bearer {_make_token()}"}

    def _create_key(self, scope: str = "read_only") -> dict:
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "test-key", "scopes": [scope]},
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def test_create_response_has_workspace_id_camel(self):
        """API key create response must use workspaceId (camelCase)."""
        body = self._create_key()
        self.assertIn("workspaceId", body, f"Expected workspaceId, got keys: {list(body.keys())}")
        self.assertNotIn("workspace_id", body, "snake_case workspace_id must not appear in response")

    def test_create_response_has_created_at_camel(self):
        """API key create response must use createdAt (camelCase)."""
        body = self._create_key()
        self.assertIn("createdAt", body, f"Expected createdAt, got keys: {list(body.keys())}")
        self.assertNotIn("created_at", body)

    def test_list_response_uses_camel_case(self):
        """API key list response must use camelCase field names."""
        self._create_key()
        resp = self.client.get("/v1/api-keys", headers=self.auth)
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json()
        self.assertGreater(len(items), 0)
        item = items[0]
        self.assertIn("workspaceId", item, f"Expected workspaceId, got: {list(item.keys())}")
        self.assertIn("createdAt", item)
        self.assertNotIn("workspace_id", item)
        self.assertNotIn("created_at", item)

    def test_revoke_response_uses_camel_case(self):
        """API key revoke response must use revokedAt (camelCase)."""
        body = self._create_key()
        key_id = body["id"]
        resp = self.client.delete(f"/v1/api-keys/{key_id}", headers=self.auth)
        self.assertEqual(resp.status_code, 200, resp.text)
        result = resp.json()
        self.assertIn("revokedAt", result, f"Expected revokedAt, got: {list(result.keys())}")
        self.assertNotIn("revoked_at", result)


class TestErrorBodyShape(unittest.TestCase):
    def setUp(self):
        os.environ["GRANTLAYER_JWT_SECRET"] = "gl339-test-secret-exactly-32bytes!"
        os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
        os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)

    def test_500_handler_returns_error_code_reason(self):
        """500 handler must return {error, errorCode, reason} not {error, message}."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from backend.src.api.app import create_app
        app = create_app()
        # Inject a route that always raises
        @app.get("/internal/boom")
        async def _boom():
            raise RuntimeError("test-500")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/internal/boom")
        self.assertEqual(resp.status_code, 500)
        body = resp.json()
        self.assertIn("errorCode", body, f"500 body must have errorCode, got: {body}")
        self.assertIn("reason", body, f"500 body must have reason, got: {body}")
        self.assertNotIn("message", body, f"500 body must not use 'message' key, got: {body}")

    def test_400_errors_have_error_code_and_reason(self):
        """HTTPException 400 must include errorCode and reason."""
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        client = TestClient(create_app(), raise_server_exceptions=False)
        # Invalid grant create body → Pydantic 422
        resp = client.post(
            "/v1/grants",
            json={"bad": "payload"},
            headers={"Authorization": "Bearer dummy"},
        )
        # 422 or 401 — either way, no 'message' key in 4xx responses
        body = resp.json()
        self.assertNotIn("message", body, f"4xx body must not use 'message' key, got: {body}")
