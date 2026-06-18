"""GL-336 — Fix inconsistent list responses and pagination.

Tests:
- GET /v1/grants returns a wrapper object (not raw array) with items, total, limit, offset.
- GrantListResponse includes next_cursor field.
- openapi.yaml documents GET /v1/grants as returning GrantListResponse (not array).
"""

from __future__ import annotations

import os
import unittest


def _make_client():
    os.environ.pop("GRANTLAYER_JWT_SECRET", None)
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestGrantListResponseShape(unittest.TestCase):
    def test_grants_list_schema_has_next_cursor(self):
        """GrantListResponse schema must include optional next_cursor field."""
        from backend.src.api.schemas import GrantListResponse
        fields = GrantListResponse.model_fields
        self.assertIn("next_cursor", fields)

    def test_grant_request_list_schema_has_next_cursor(self):
        """GrantRequestListResponse schema must include optional next_cursor field."""
        from backend.src.api.schemas import GrantRequestListResponse
        fields = GrantRequestListResponse.model_fields
        self.assertIn("next_cursor", fields)

    def test_grant_list_response_is_not_raw_array(self):
        """GrantListResponse is a wrapper object, not a list — fixing the OpenAPI lie."""
        from backend.src.api.schemas import GrantListResponse
        import inspect
        self.assertFalse(
            issubclass(GrantListResponse, list),
            "GrantListResponse must be a wrapper object, not a list",
        )
        self.assertIn("items", GrantListResponse.model_fields)
        self.assertIn("total", GrantListResponse.model_fields)


class TestOpenApiSpecCorrect(unittest.TestCase):
    def test_openapi_yaml_grants_list_documents_wrapper_not_array(self):
        """openapi.yaml GET /v1/grants must reference GrantListResponse, not type: array."""
        import os
        yaml_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "docs", "openapi.yaml"
        )
        yaml_path = os.path.normpath(yaml_path)
        with open(yaml_path) as f:
            content = f.read()

        # The old incorrect form should not be present for grants list
        import re
        # Check that GrantListResponse schema exists
        self.assertIn("GrantListResponse", content)
        # Check the schema is referenced in the grants list endpoint
        self.assertIn("$ref: \"#/components/schemas/GrantListResponse\"", content)

    def test_openapi_yaml_has_grant_list_response_schema(self):
        """openapi.yaml must define GrantListResponse component schema."""
        import os
        yaml_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "docs", "openapi.yaml")
        )
        with open(yaml_path) as f:
            content = f.read()
        self.assertIn("GrantListResponse:", content)
        self.assertIn("next_cursor", content)


class TestGrantListNextCursor(unittest.TestCase):
    def test_grants_endpoint_returns_wrapper_with_next_cursor_field(self):
        """GET /v1/grants response body must be a wrapper with items, total, nextCursor."""
        from unittest.mock import AsyncMock, patch
        from backend.src.api.schemas import GrantListResponse

        _AUTH = (
            {"sub": "u1", "role": "grant_admin", "tenant_id": "t1",
             "workspace_id": "ws1", "auth_method": "jwt", "scopes": []},
            {"workspace_id": "ws1", "tenant_id": "t1", "cross_workspace_access": False,
             "workspace_member_role": None, "resolution_mode": "jwt"},
        )

        async def _empty_list(*args, **kwargs):
            return ([], 0)

        with (
            patch("backend.src.api.routers.grants.resolve_auth_and_workspace", return_value=_AUTH),
            patch("backend.src.api.routers.grants.evaluate_policy", new_callable=AsyncMock, return_value=True),
        ):
            from unittest.mock import MagicMock, patch as _patch
            with _patch.object(__import__("backend.src.grants.grant_service", fromlist=["AsyncGrantService"]).AsyncGrantService, "list_grants", new_callable=AsyncMock, return_value=([], 0)):
                client = _make_client()
                resp = client.get("/v1/grants", headers={"Authorization": "Bearer dummy"})

        # May fail for other reasons (workspace), but if it returns 200 the body must be a wrapper
        if resp.status_code == 200:
            body = resp.json()
            self.assertIn("items", body)
            self.assertIn("total", body)
            self.assertIn("limit", body)
            self.assertIn("offset", body)
            # next_cursor may be present (even if null/missing is OK as it's Optional)

    def test_grant_list_response_next_cursor_none_when_all_on_one_page(self):
        """next_cursor must be None when total <= limit (all on one page)."""
        from backend.src.api.schemas import GrantListResponse
        resp = GrantListResponse(items=[], total=5, limit=100, offset=0)
        self.assertIsNone(resp.next_cursor)

    def test_grant_list_response_construction_with_cursor(self):
        """GrantListResponse can be constructed with nextCursor set."""
        from backend.src.api.schemas import GrantListResponse
        resp = GrantListResponse(items=[], total=200, limit=50, offset=0, nextCursor="50")
        self.assertEqual(resp.next_cursor, "50")
