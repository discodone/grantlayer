"""GL-332 — Wire OPA require_policy into endpoints and fix fail-mode drift.

End-to-end tests that would FAIL if scope enforcement is not wired up:
- OPA-deny on grant.create blocks POST /v1/grants with 403.
- OPA-unreachable on grant.create returns 503.
- evaluate_policy_sync is now fail-closed: raises 503 when OPA unreachable.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, patch

_TEST_SECRET = "gl332-test-hs256-secret-32chars!!"

_GRANT_BODY = {
    "subjectId": "agent-001",
    "role": "executor",
    "action": "deploy",
    "resource": "service/api",
    "validFrom": "2025-01-01T00:00:00Z",
    "validUntil": "2026-01-01T00:00:00Z",
    "createdBy": "opa-test-user",
    "reason": "OPA wiring test",
}

_MOCK_AUTH_CTX = {
    "sub": "opa-test-user",
    "role": "grant_admin",
    "tenant_id": "t-opa",
    "workspace_id": "ws-opa",
    "auth_method": "jwt",
    "scopes": [],
}
_MOCK_WS_CTX = {
    "workspace_id": "ws-opa",
    "tenant_id": "t-opa",
    "workspace_member_role": "grant_admin",
    "cross_workspace_access": False,
    "resolution_mode": "jwt",
}


def _make_client():
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _jwt_header() -> dict:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    from backend.src.api.auth_jwt import encode_token
    token = encode_token(
        {"sub": "opa-test-user", "role": "grant_admin", "tenant_id": "t-opa",
         "workspace_id": "ws-opa", "iss": "grantlayer", "aud": "grantlayer-api"},
        _TEST_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


class TestOpaWiredToGrantCreate(unittest.TestCase):
    """End-to-end tests: OPA check is wired into POST /v1/grants.

    Auth resolution is mocked to focus on the OPA gate; the test would still fail
    if evaluate_policy is never called (remove the mock → no 403/503 from OPA).
    """

    def _post_grant_with_opa(self, opa_mock, body=None):
        """Post to /v1/grants with mocked auth + mocked OPA."""
        with (
            patch("backend.src.api.routers.grants.resolve_auth_and_workspace",
                  return_value=(_MOCK_AUTH_CTX, _MOCK_WS_CTX)),
            patch("backend.src.api.deps.evaluate_policy", opa_mock),
        ):
            client = _make_client()
            return client.post("/v1/grants", json=body or _GRANT_BODY,
                               headers={"Authorization": "Bearer dummy"})

    def test_opa_deny_returns_403_on_post_grants(self):
        """OPA deny must block POST /v1/grants with 403 (enforcement is wired)."""
        mock = AsyncMock(return_value=False)
        resp = self._post_grant_with_opa(mock)
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertEqual(body.get("errorCode"), "policy_denied")

    def test_opa_evaluate_policy_is_called_on_post_grants(self):
        """evaluate_policy must actually be called for each grant creation."""
        mock = AsyncMock(return_value=True)
        self._post_grant_with_opa(mock)
        self.assertTrue(mock.called, "evaluate_policy was not called — OPA is NOT wired to POST /v1/grants")

    def test_opa_unreachable_returns_503_on_post_grants(self):
        """OPA unreachable must return 503 on POST /v1/grants (fail-closed)."""
        from fastapi import HTTPException

        async def _unreachable(*args, **kwargs):
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "policy_engine_unavailable",
                    "errorCode": "policy_engine_unavailable",
                    "reason": "OPA policy engine is configured but unreachable. Request denied.",
                },
            )

        resp = self._post_grant_with_opa(_unreachable)
        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertEqual(body.get("errorCode"), "policy_engine_unavailable")

    def test_opa_allow_does_not_block(self):
        """OPA allow must not block the request (business logic continues)."""
        mock = AsyncMock(return_value=True)
        resp = self._post_grant_with_opa(mock)
        body = resp.json()
        self.assertNotEqual(body.get("errorCode"), "policy_denied")
        self.assertNotEqual(body.get("errorCode"), "policy_engine_unavailable")

    def test_opa_not_configured_does_not_block(self):
        """Without GRANTLAYER_OPA_URL, evaluate_policy returns True (noop)."""
        old = os.environ.pop("GRANTLAYER_OPA_URL", None)
        try:
            with patch("backend.src.api.routers.grants.resolve_auth_and_workspace",
                       return_value=(_MOCK_AUTH_CTX, _MOCK_WS_CTX)):
                client = _make_client()
                resp = client.post("/v1/grants", json=_GRANT_BODY,
                                   headers={"Authorization": "Bearer dummy"})
            body = resp.json()
            self.assertNotEqual(body.get("errorCode"), "policy_denied")
        finally:
            if old:
                os.environ["GRANTLAYER_OPA_URL"] = old


class TestEvaluatePolicySyncFailClosed(unittest.TestCase):
    def setUp(self):
        os.environ["GRANTLAYER_OPA_URL"] = "http://localhost:19191"

    def tearDown(self):
        os.environ.pop("GRANTLAYER_OPA_URL", None)

    def test_evaluate_policy_sync_raises_503_when_unreachable(self):
        """evaluate_policy_sync must raise HTTPException 503 when OPA is unreachable (fail-closed)."""
        from fastapi import HTTPException
        from backend.src.policy.opa_client import evaluate_policy_sync
        with self.assertRaises(HTTPException) as ctx:
            evaluate_policy_sync("test.action", {}, {})
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail["errorCode"], "policy_engine_unavailable")

    def test_evaluate_policy_sync_was_fail_open_is_now_fail_closed(self):
        """Confirms the fix: the old fail-open True return is gone — must raise instead."""
        from fastapi import HTTPException
        from backend.src.policy.opa_client import evaluate_policy_sync
        with self.assertRaises(HTTPException):
            evaluate_policy_sync("grant.create", {"role": "grant_admin"}, {"workspace_id": "ws1"})


class TestEvaluatePolicyAsyncFailClosed(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        os.environ["GRANTLAYER_OPA_URL"] = "http://localhost:19191"

    def tearDown(self):
        os.environ.pop("GRANTLAYER_OPA_URL", None)

    async def test_evaluate_policy_async_raises_503_when_unreachable(self):
        """evaluate_policy (async) must raise HTTPException 503 on connection error."""
        from fastapi import HTTPException
        from backend.src.policy.opa_client import evaluate_policy
        with self.assertRaises(HTTPException) as ctx:
            await evaluate_policy("grant.create", {}, {})
        self.assertEqual(ctx.exception.status_code, 503)
