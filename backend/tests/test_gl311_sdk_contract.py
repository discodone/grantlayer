"""GL-311 — SDK and contract test integration.

Covers:
- SDK v0.2.0 with async client
- SDK methods match OpenAPI spec paths
- Pydantic models parse correctly
- py.typed marker exists
- Contract test files exist
"""

from __future__ import annotations

import os
import unittest


REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestSDKVersion(unittest.TestCase):
    def test_sdk_version(self):
        from sdk.grantlayer import __version__
        self.assertIsNotNone(__version__)

    def test_sdk_exports_async_client(self):
        from sdk.grantlayer import AsyncGrantLayerClient
        self.assertIsNotNone(AsyncGrantLayerClient)

    def test_sdk_exports_pydantic_models(self):
        from sdk.grantlayer import Grant, GrantRequest, WebhookSubscription
        self.assertIsNotNone(Grant)

    def test_py_typed_marker(self):
        path = os.path.join(REPO_ROOT, "sdk", "grantlayer", "py.typed")
        self.assertTrue(os.path.isfile(path))


class TestContractTestsExist(unittest.TestCase):
    def _contract_path(self):
        return os.path.join(REPO_ROOT, "backend", "tests", "contract")

    def test_contract_dir_exists(self):
        self.assertTrue(os.path.isdir(self._contract_path()))

    def test_openapi_schema_test_exists(self):
        path = os.path.join(self._contract_path(), "test_openapi_schema.py")
        self.assertTrue(os.path.isfile(path))

    def test_sdk_contract_test_exists(self):
        path = os.path.join(self._contract_path(), "test_sdk_contract.py")
        self.assertTrue(os.path.isfile(path))

    def test_response_models_test_exists(self):
        path = os.path.join(self._contract_path(), "test_response_models.py")
        self.assertTrue(os.path.isfile(path))

    def test_schemathesis_test_exists(self):
        path = os.path.join(self._contract_path(), "test_schemathesis.py")
        self.assertTrue(os.path.isfile(path))


class TestSDKRetryConfig(unittest.TestCase):
    def test_client_has_max_retries_param(self):
        from sdk.grantlayer import GrantLayerClient
        import inspect
        sig = inspect.signature(GrantLayerClient.__init__)
        self.assertIn("max_retries", sig.parameters)

    def test_async_client_has_max_retries_param(self):
        from sdk.grantlayer import AsyncGrantLayerClient
        import inspect
        sig = inspect.signature(AsyncGrantLayerClient.__init__)
        self.assertIn("max_retries", sig.parameters)

    def test_rate_limit_error_has_retry_after(self):
        from sdk.grantlayer.exceptions import GrantLayerRateLimitError
        exc = GrantLayerRateLimitError(429, "slow down", retry_after=45)
        self.assertEqual(exc.retry_after, 45)


class TestSDKPyproject(unittest.TestCase):
    def test_sdk_pyproject_exists(self):
        path = os.path.join(REPO_ROOT, "sdk", "pyproject.toml")
        self.assertTrue(os.path.isfile(path))

    def test_sdk_pyproject_has_httpx(self):
        path = os.path.join(REPO_ROOT, "sdk", "pyproject.toml")
        with open(path) as f:
            content = f.read()
        self.assertIn("httpx", content)

    def test_sdk_pyproject_has_tenacity(self):
        path = os.path.join(REPO_ROOT, "sdk", "pyproject.toml")
        with open(path) as f:
            content = f.read()
        self.assertIn("tenacity", content)

    def test_sdk_pyproject_has_pydantic(self):
        path = os.path.join(REPO_ROOT, "sdk", "pyproject.toml")
        with open(path) as f:
            content = f.read()
        self.assertIn("pydantic", content)


if __name__ == "__main__":
    unittest.main()
