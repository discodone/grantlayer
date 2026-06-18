"""GL-314 — Email notification system tests.

Covers:
- Templates module importable
- All 4 templates render without error
- Templates contain expected HTML structure
- render_template raises ValueError for unknown template
- make_unsubscribe_token generates a token
- verify_unsubscribe_token validates a valid token
- verify_unsubscribe_token rejects an invalid token
- email.send_email with noop backend does not send
- Unsubscribe GET endpoint returns 200 for valid token
- Unsubscribe GET endpoint returns 400 for invalid token
- Unsubscribe POST endpoint returns 200 for valid token
"""

from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch


class TestTemplatesModule(unittest.TestCase):
    def test_templates_importable(self):
        from backend.src.notifications.templates import render_template, _KNOWN_TEMPLATES
        self.assertIsNotNone(render_template)

    def test_known_templates(self):
        from backend.src.notifications.templates import _KNOWN_TEMPLATES
        self.assertIn("grant_approved", _KNOWN_TEMPLATES)
        self.assertIn("grant_rejected", _KNOWN_TEMPLATES)
        self.assertIn("grant_request_submitted", _KNOWN_TEMPLATES)
        self.assertIn("webhook_failure_alert", _KNOWN_TEMPLATES)

    def test_render_grant_approved(self):
        from backend.src.notifications.templates import render_template
        html = render_template("grant_approved", {
            "grant_id": "g-123",
            "action": "read",
            "resource": "file://data",
            "valid_until": "2026-12-31",
            "unsubscribe_url": "https://example.com/unsub?token=abc",
        })
        self.assertIn("Grant Approved", html)
        self.assertIn("g-123", html)
        self.assertIn("unsubscribe", html.lower())

    def test_render_grant_rejected(self):
        from backend.src.notifications.templates import render_template
        html = render_template("grant_rejected", {
            "request_id": "req-1",
            "reason": "Policy violation",
            "unsubscribe_url": "https://example.com/unsub?token=abc",
        })
        self.assertIn("Rejected", html)

    def test_render_grant_request_submitted(self):
        from backend.src.notifications.templates import render_template
        html = render_template("grant_request_submitted", {
            "request_id": "req-2",
            "action": "write",
            "resource": "s3://bucket",
            "unsubscribe_url": "https://example.com/unsub?token=abc",
        })
        self.assertIn("Submitted", html)

    def test_render_webhook_failure_alert(self):
        from backend.src.notifications.templates import render_template
        html = render_template("webhook_failure_alert", {
            "webhook_id": "wh-1",
            "url": "https://example.com/hook",
            "event_type": "grant.created",
            "error": "Connection refused",
            "attempts": 3,
            "unsubscribe_url": "https://example.com/unsub?token=abc",
        })
        self.assertIn("Webhook", html)

    def test_render_unknown_template_raises(self):
        from backend.src.notifications.templates import render_template
        with self.assertRaises(ValueError):
            render_template("nonexistent_template", {})

    def test_templates_output_valid_html(self):
        from backend.src.notifications.templates import render_template
        html = render_template("grant_approved", {
            "grant_id": "g-test",
            "action": "x",
            "resource": "y",
            "valid_until": "z",
            "unsubscribe_url": "u",
        })
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)

    def test_templates_autoescape_xss(self):
        from backend.src.notifications.templates import render_template
        html = render_template("grant_approved", {
            "grant_id": "<script>alert(1)</script>",
            "action": "read",
            "resource": "file",
            "valid_until": "2026-12-31",
            "unsubscribe_url": "u",
        })
        self.assertNotIn("<script>alert(1)</script>", html)


class TestUnsubscribeToken(unittest.TestCase):
    def test_make_token(self):
        from backend.src.notifications.email import make_unsubscribe_token
        token = make_unsubscribe_token("user@example.com")
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 10)

    def test_verify_valid_token(self):
        from backend.src.notifications.email import make_unsubscribe_token, verify_unsubscribe_token
        token = make_unsubscribe_token("user@example.com")
        email = verify_unsubscribe_token(token)
        self.assertEqual(email, "user@example.com")

    def test_verify_invalid_token(self):
        from backend.src.notifications.email import verify_unsubscribe_token
        email = verify_unsubscribe_token("not-a-valid-token")
        self.assertIsNone(email)

    def test_verify_tampered_token(self):
        from backend.src.notifications.email import make_unsubscribe_token, verify_unsubscribe_token
        token = make_unsubscribe_token("user@example.com")
        tampered = token[:-3] + "xxx"
        email = verify_unsubscribe_token(tampered)
        self.assertIsNone(email)

    def test_verify_empty_token(self):
        from backend.src.notifications.email import verify_unsubscribe_token
        self.assertIsNone(verify_unsubscribe_token(""))


class TestSendEmailNoop(unittest.TestCase):
    def _run(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def test_send_email_noop_no_error(self):
        import os
        os.environ["GRANTLAYER_EMAIL_BACKEND"] = "noop"
        try:
            from backend.src.notifications.email import send_email
            self._run(send_email(
                to="user@example.com",
                template="grant_approved",
                context={
                    "grant_id": "g-1",
                    "action": "read",
                    "resource": "file",
                    "valid_until": "2026-12-31",
                },
            ))
        finally:
            os.environ.pop("GRANTLAYER_EMAIL_BACKEND", None)

    def test_send_email_adds_unsubscribe_url(self):
        import os
        os.environ["GRANTLAYER_EMAIL_BACKEND"] = "noop"
        try:
            from backend.src.notifications.email import send_email
            ctx: dict = {
                "grant_id": "g-2", "action": "read", "resource": "file", "valid_until": "2026-12-31"
            }
            self._run(send_email(to="user2@example.com", template="grant_approved", context=ctx))
            self.assertIn("unsubscribe_url", ctx)
        finally:
            os.environ.pop("GRANTLAYER_EMAIL_BACKEND", None)

    def test_send_email_mock_smtp(self):
        import os
        os.environ["GRANTLAYER_EMAIL_BACKEND"] = "smtp"
        with patch("backend.src.notifications.email._send_smtp") as mock_send:
            from backend.src.notifications.email import send_email
            self._run(send_email(
                to="test@example.com",
                template="grant_rejected",
                context={"request_id": "r-1", "reason": "denied"},
            ))
            mock_send.assert_called_once()
        os.environ.pop("GRANTLAYER_EMAIL_BACKEND", None)


class TestUnsubscribeEndpoints(unittest.TestCase):
    def _make_client(self):
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_unsubscribe_invalid_token_400(self):
        client = self._make_client()
        r = client.get("/v1/notifications/unsubscribe?token=invalid")
        self.assertEqual(r.status_code, 400)

    def test_unsubscribe_valid_token_200(self):
        from backend.src.notifications.email import make_unsubscribe_token
        token = make_unsubscribe_token("user@example.com")
        client = self._make_client()
        r = client.get(f"/v1/notifications/unsubscribe?token={token}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("content-type", ""))

    def test_unsubscribe_post_invalid_token(self):
        client = self._make_client()
        r = client.post("/v1/notifications/unsubscribe?token=badtoken")
        self.assertEqual(r.status_code, 400)

    def test_unsubscribe_post_valid_token(self):
        from backend.src.notifications.email import make_unsubscribe_token
        token = make_unsubscribe_token("admin@example.com")
        client = self._make_client()
        r = client.post(f"/v1/notifications/unsubscribe?token={token}")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("email"), "admin@example.com")


if __name__ == "__main__":
    unittest.main()
