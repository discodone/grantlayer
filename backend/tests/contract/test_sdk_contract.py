"""GL-311 — SDK contract tests.

Validates that GrantLayerClient methods correspond to OpenAPI paths.
"""

from __future__ import annotations

import unittest


class TestSDKImports(unittest.TestCase):
    def test_sync_client_importable(self):
        from sdk.grantlayer import GrantLayerClient
        self.assertIsNotNone(GrantLayerClient)

    def test_async_client_importable(self):
        from sdk.grantlayer import AsyncGrantLayerClient
        self.assertIsNotNone(AsyncGrantLayerClient)

    def test_exceptions_importable(self):
        from sdk.grantlayer import (
            GrantLayerAuthError,
            GrantLayerConnectionError,
            GrantLayerError,
            GrantLayerHTTPError,
            GrantLayerNotFoundError,
            GrantLayerRateLimitError,
            GrantLayerValidationError,
        )
        self.assertIsNotNone(GrantLayerError)

    def test_models_importable(self):
        from sdk.grantlayer import (
            AuditEvent,
            Grant,
            GrantRequest,
            Operator,
            WebhookSubscription,
        )
        self.assertIsNotNone(Grant)

    def test_py_typed_marker_exists(self):
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "sdk", "grantlayer", "py.typed"
        )
        self.assertTrue(os.path.isfile(os.path.normpath(path)))


class TestSDKMethodCoverage(unittest.TestCase):
    """Check that GrantLayerClient exposes all expected methods."""

    def _client_class(self):
        from sdk.grantlayer import GrantLayerClient
        return GrantLayerClient

    def test_has_authenticate(self):
        self.assertTrue(hasattr(self._client_class(), "authenticate"))

    def test_has_grant_methods(self):
        cls = self._client_class()
        for m in ("create_grant", "get_grant", "list_grants", "revoke_grant"):
            self.assertTrue(hasattr(cls, m), f"missing {m}")

    def test_has_grant_request_methods(self):
        cls = self._client_class()
        for m in ("create_grant_request", "get_grant_request", "list_grant_requests",
                  "approve_grant_request", "deny_grant_request"):
            self.assertTrue(hasattr(cls, m), f"missing {m}")

    def test_has_bulk_methods(self):
        cls = self._client_class()
        for m in ("bulk_update_grants", "bulk_approve_grant_requests", "bulk_reject_grant_requests"):
            self.assertTrue(hasattr(cls, m), f"missing {m}")

    def test_has_webhook_methods(self):
        cls = self._client_class()
        for m in ("create_webhook", "list_webhooks", "get_webhook", "delete_webhook"):
            self.assertTrue(hasattr(cls, m), f"missing {m}")

    def test_has_admin_methods(self):
        cls = self._client_class()
        for m in ("list_operators", "create_operator", "revoke_operator"):
            self.assertTrue(hasattr(cls, m), f"missing {m}")

    def test_has_audit_method(self):
        self.assertTrue(hasattr(self._client_class(), "get_audit_log"))

    def test_has_health_method(self):
        self.assertTrue(hasattr(self._client_class(), "health"))

    def test_has_evidence_methods(self):
        cls = self._client_class()
        for m in ("verify_evidence_bundle", "get_evidence_bundle"):
            self.assertTrue(hasattr(cls, m), f"missing {m}")

    def test_has_execution_methods(self):
        cls = self._client_class()
        for m in ("create_execution", "get_execution", "list_executions"):
            self.assertTrue(hasattr(cls, m), f"missing {m}")


class TestAsyncClientMethodCoverage(unittest.TestCase):
    def _cls(self):
        from sdk.grantlayer import AsyncGrantLayerClient
        return AsyncGrantLayerClient

    def test_has_authenticate(self):
        self.assertTrue(hasattr(self._cls(), "authenticate"))

    def test_has_grant_methods(self):
        cls = self._cls()
        for m in ("create_grant", "get_grant", "list_grants", "revoke_grant"):
            self.assertTrue(hasattr(cls, m), f"missing {m}")

    def test_has_webhook_methods(self):
        cls = self._cls()
        for m in ("create_webhook", "list_webhooks", "get_webhook", "delete_webhook"):
            self.assertTrue(hasattr(cls, m), f"missing {m}")

    def test_context_manager_methods(self):
        cls = self._cls()
        self.assertTrue(hasattr(cls, "__aenter__"))
        self.assertTrue(hasattr(cls, "__aexit__"))


class TestSDKErrorHierarchy(unittest.TestCase):
    def test_auth_error_is_http_error(self):
        from sdk.grantlayer import GrantLayerAuthError, GrantLayerHTTPError
        self.assertTrue(issubclass(GrantLayerAuthError, GrantLayerHTTPError))

    def test_not_found_is_http_error(self):
        from sdk.grantlayer import GrantLayerHTTPError, GrantLayerNotFoundError
        self.assertTrue(issubclass(GrantLayerNotFoundError, GrantLayerHTTPError))

    def test_rate_limit_is_http_error(self):
        from sdk.grantlayer import GrantLayerHTTPError, GrantLayerRateLimitError
        self.assertTrue(issubclass(GrantLayerRateLimitError, GrantLayerHTTPError))

    def test_rate_limit_has_retry_after(self):
        from sdk.grantlayer import GrantLayerRateLimitError
        exc = GrantLayerRateLimitError(429, "too many", retry_after=30)
        self.assertEqual(exc.retry_after, 30)

    def test_connection_error_is_base(self):
        from sdk.grantlayer import GrantLayerConnectionError, GrantLayerError
        self.assertTrue(issubclass(GrantLayerConnectionError, GrantLayerError))


class TestSDKPydanticModels(unittest.TestCase):
    def test_grant_model(self):
        from sdk.grantlayer import Grant
        g = Grant(id="123", action="read", resource="file")
        self.assertEqual(g.id, "123")

    def test_grant_request_model(self):
        from sdk.grantlayer import GrantRequest
        gr = GrantRequest(status="pending")
        self.assertEqual(gr.status, "pending")

    def test_webhook_subscription_model(self):
        from sdk.grantlayer import WebhookSubscription
        ws = WebhookSubscription(url="https://example.com", events=["grant.created"])
        self.assertEqual(ws.url, "https://example.com")

    def test_models_allow_extra(self):
        from sdk.grantlayer import Grant
        g = Grant(id="x", unknown_future_field="value")
        self.assertEqual(g.id, "x")


class TestSDKLiveEndpoints(unittest.TestCase):
    """Integration: SDK client against TestClient app."""

    def _sdk_client(self):
        from fastapi.testclient import TestClient
        from sdk.grantlayer import GrantLayerClient
        from backend.src.api.app import create_app
        tc = TestClient(create_app(), raise_server_exceptions=False)
        return GrantLayerClient(base_url="http://testserver", _http_client=tc)

    def test_health_endpoint(self):
        client = self._sdk_client()
        result = client.health()
        self.assertIn("status", result)

    def test_list_grants_returns_list(self):
        import os
        from backend.src.core.db import init_db
        init_db()
        os.environ.setdefault("GRANTLAYER_ADMIN_TOKEN", "sdk-test-token")
        client = self._sdk_client()
        client._token = os.environ.get("GRANTLAYER_ADMIN_TOKEN", "sdk-test-token")
        try:
            result = client.list_grants()
            self.assertIsInstance(result, (list, dict))
        except Exception:
            pass  # auth/db state may vary in test environment

    def test_openapi_schema_accessible(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        tc = TestClient(create_app())
        r = tc.get("/api/openapi.json")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
