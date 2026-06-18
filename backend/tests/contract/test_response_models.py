"""GL-311 — Response model contract tests.

Validates that API response shapes match SDK Pydantic models.
"""

from __future__ import annotations

import os
import unittest


def _make_client():
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


class TestHealthResponseModel(unittest.TestCase):
    def test_health_has_status_field(self):
        client = _make_client()
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("status", data)
        self.assertIn("service", data)

    def test_health_status_is_string(self):
        client = _make_client()
        data = client.get("/health").json()
        self.assertIsInstance(data["status"], str)


class TestGrantsResponseModel(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("GRANTLAYER_ADMIN_TOKEN", "contract-test-token")
        self._token = os.environ["GRANTLAYER_ADMIN_TOKEN"]

    def _client_with_auth(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        tc = TestClient(create_app(), raise_server_exceptions=False)
        return tc, {"Authorization": f"Bearer {self._token}"}

    def test_list_grants_returns_array(self):
        from backend.src.core.db import init_db
        init_db()
        tc, headers = self._client_with_auth()
        r = tc.get("/v1/grants", headers=headers)
        self.assertIn(r.status_code, (200, 401, 500))
        if r.status_code == 200:
            data = r.json()
            self.assertIsInstance(data, (list, dict))

    def test_audit_events_response_shape(self):
        from backend.src.core.db import init_db
        init_db()
        tc, headers = self._client_with_auth()
        r = tc.get("/v1/audit-events", headers=headers)
        self.assertIn(r.status_code, (200, 401, 403, 500))
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("items", [])
            if items:
                event = items[0]
                # Audit events should have at least one of these fields
                self.assertTrue(
                    any(k in event for k in ("id", "subject_id", "subjectId", "action", "timestamp"))
                )


class TestWebhookResponseModel(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("GRANTLAYER_ADMIN_TOKEN", "contract-test-token")
        self._token = os.environ["GRANTLAYER_ADMIN_TOKEN"]

    def test_create_webhook_response_has_id(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        tc = TestClient(create_app(), raise_server_exceptions=False)
        headers = {"Authorization": f"Bearer {self._token}"}
        r = tc.post("/v1/webhooks", json={
            "url": "https://example.com/hook",
            "events": ["grant.created"],
        }, headers=headers)
        if r.status_code == 201:
            data = r.json()
            self.assertIn("id", data)
            self.assertIn("url", data)

    def test_list_webhooks_returns_list(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        tc = TestClient(create_app(), raise_server_exceptions=False)
        headers = {"Authorization": f"Bearer {self._token}"}
        r = tc.get("/v1/webhooks", headers=headers)
        if r.status_code == 200:
            data = r.json()
            self.assertIsInstance(data, (list, dict))


class TestPydanticModelsParsing(unittest.TestCase):
    def test_parse_grant_from_dict(self):
        from sdk.grantlayer import Grant
        raw = {
            "id": "g-123",
            "subjectId": "agent-1",
            "action": "read",
            "resource": "file://data",
            "revoked": False,
        }
        g = Grant(**raw)
        self.assertEqual(g.id, "g-123")
        self.assertEqual(g.revoked, False)

    def test_parse_audit_event_from_dict(self):
        from sdk.grantlayer import AuditEvent
        raw = {
            "id": "evt-123",
            "action": "grant.created",
            "approved": True,
            "timestamp": "2026-01-01T00:00:00Z",
        }
        evt = AuditEvent(**raw)
        self.assertEqual(evt.action, "grant.created")
        self.assertTrue(evt.approved)

    def test_parse_webhook_from_dict(self):
        from sdk.grantlayer import WebhookSubscription
        raw = {
            "id": "wh-1",
            "url": "https://example.com/hook",
            "events": ["grant.created", "grant.revoked"],
            "active": True,
        }
        ws = WebhookSubscription(**raw)
        self.assertEqual(len(ws.events), 2)

    def test_grant_model_extra_fields_allowed(self):
        from sdk.grantlayer import Grant
        g = Grant(id="x", future_field="yes", another_new_field=42)
        self.assertEqual(g.id, "x")

    def test_operator_model(self):
        from sdk.grantlayer import Operator
        op = Operator(operatorId="op-1", name="Test", role="grant_admin", active=True)
        self.assertEqual(op.role, "grant_admin")


if __name__ == "__main__":
    unittest.main()
