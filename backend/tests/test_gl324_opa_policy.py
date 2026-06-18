"""GL-324 — OPA Policy Engine Integration.

Covers:
- opa_client module importable
- evaluate_policy returns True when OPA not configured
- evaluate_policy falls back gracefully when OPA unreachable
- evaluate_policy returns False when OPA denies
- evaluate_policy returns True when OPA allows
- require_policy raises 403 when OPA denies
- require_policy passes when OPA allows
- opa/policies/main.rego exists
- main.rego has grantlayer package
- main.rego has role-based grant approval rule
- main.rego has workspace_id match rule
- main.rego has api key scope enforcement rule
- OPA sidecar in docker-compose.yml
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_REPO_ROOT = Path(__file__).parent.parent.parent


class TestOpaClientImport(unittest.TestCase):
    def test_opa_client_importable(self):
        from backend.src.policy.opa_client import evaluate_policy, evaluate_policy_sync
        self.assertIsNotNone(evaluate_policy)
        self.assertIsNotNone(evaluate_policy_sync)

    def test_opa_client_constants(self):
        from backend.src.policy.opa_client import _DEFAULT_OPA_URL, _OPA_URL_ENV
        self.assertEqual(_OPA_URL_ENV, "GRANTLAYER_OPA_URL")
        self.assertIn("8181", _DEFAULT_OPA_URL)


class TestEvaluatePolicyNoOpa(unittest.TestCase):
    def setUp(self):
        os.environ.pop("GRANTLAYER_OPA_URL", None)

    def test_allow_when_opa_not_configured(self):
        import asyncio
        from backend.src.policy.opa_client import evaluate_policy

        async def _run():
            return await evaluate_policy("grant.read", {"role": "viewer"}, {})

        result = asyncio.run(_run())
        self.assertTrue(result)

    def test_sync_allow_when_opa_not_configured(self):
        from backend.src.policy.opa_client import evaluate_policy_sync
        result = evaluate_policy_sync("grant.read", {"role": "viewer"}, {})
        self.assertTrue(result)


class TestEvaluatePolicyWithMockedOpa(unittest.TestCase):
    def test_allow_when_opa_allows(self):
        import asyncio
        from backend.src.policy.opa_client import evaluate_policy

        async def _run():
            return await evaluate_policy("grant.create", {"role": "grant_admin"}, {})

        with patch.dict(os.environ, {"GRANTLAYER_OPA_URL": "http://localhost:8181"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.json.return_value = {"result": True}
                mock_response.raise_for_status = MagicMock()
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = asyncio.run(_run())
                self.assertTrue(result)

    def test_deny_when_opa_denies(self):
        import asyncio
        from backend.src.policy.opa_client import evaluate_policy

        async def _run():
            return await evaluate_policy("grant.revoke", {"role": "viewer"}, {})

        with patch.dict(os.environ, {"GRANTLAYER_OPA_URL": "http://localhost:8181"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_response = MagicMock()
                mock_response.json.return_value = {"result": False}
                mock_response.raise_for_status = MagicMock()
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = asyncio.run(_run())
                self.assertFalse(result)

    def test_fallback_true_when_opa_unreachable(self):
        import asyncio
        import httpx
        from backend.src.policy.opa_client import evaluate_policy

        async def _run():
            return await evaluate_policy("grant.create", {"role": "admin"}, {})

        with patch.dict(os.environ, {"GRANTLAYER_OPA_URL": "http://localhost:8181"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = asyncio.run(_run())
                self.assertTrue(result)  # graceful fallback


class TestRequirePolicy(unittest.TestCase):
    def test_passes_when_allowed(self):
        import asyncio
        from backend.src.api.routers.opa import require_policy

        async def _run():
            with patch("backend.src.api.routers.opa.evaluate_policy", AsyncMock(return_value=True)):
                await require_policy("grant.read", {}, {})

        asyncio.run(_run())  # should not raise

    def test_raises_403_when_denied(self):
        import asyncio
        from fastapi import HTTPException
        from backend.src.api.routers.opa import require_policy

        async def _run():
            with patch("backend.src.api.routers.opa.evaluate_policy", AsyncMock(return_value=False)):
                await require_policy("grant.revoke", {}, {})

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(_run())
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["errorCode"], "policy_denied")


class TestOpaRego(unittest.TestCase):
    def setUp(self):
        self.rego_path = _REPO_ROOT / "opa" / "policies" / "main.rego"

    def test_rego_file_exists(self):
        self.assertTrue(self.rego_path.exists())

    def test_rego_has_package(self):
        content = self.rego_path.read_text()
        self.assertIn("package grantlayer", content)

    def test_rego_has_default_deny(self):
        content = self.rego_path.read_text()
        self.assertIn("default allow", content)
        self.assertIn("false", content)

    def test_rego_has_role_based_approval(self):
        content = self.rego_path.read_text()
        self.assertIn("grant.approve", content)
        self.assertIn("grant_admin", content)

    def test_rego_has_workspace_id_match(self):
        content = self.rego_path.read_text()
        self.assertIn("workspace_id", content)

    def test_rego_has_api_key_scope_enforcement(self):
        content = self.rego_path.read_text()
        self.assertIn("read_only", content)
        self.assertIn("scopes", content)


class TestDockerComposeOpa(unittest.TestCase):
    def test_opa_service_in_docker_compose(self):
        compose_path = _REPO_ROOT / "docker-compose.yml"
        content = compose_path.read_text()
        self.assertIn("openpolicyagent/opa", content)
        self.assertIn("8181", content)
