"""GL-333 — Webhook SSRF guard.

End-to-end tests that would FAIL if SSRF protection is not wired:
- Registration rejects loopback, link-local, private, and metadata addresses.
- Delivery also blocks SSRF destinations (DNS rebinding protection).
"""

from __future__ import annotations

import unittest


class TestWebhookSsrfValidation(unittest.TestCase):
    """Registration-time SSRF validation via Pydantic WebhookCreateRequest."""

    def _validate(self, url: str) -> None:
        from backend.src.webhooks.schemas import WebhookCreateRequest
        # Should raise ValueError if URL is blocked
        WebhookCreateRequest(url=url, events=["grant.created"])

    def test_loopback_ipv4_blocked(self):
        with self.assertRaises(Exception):
            self._validate("http://127.0.0.1/hook")

    def test_loopback_127_x_blocked(self):
        with self.assertRaises(Exception):
            self._validate("http://127.1.2.3/hook")

    def test_loopback_localhost_blocked(self):
        with self.assertRaises(Exception):
            self._validate("http://localhost/hook")

    def test_cloud_metadata_169_blocked(self):
        with self.assertRaises(Exception):
            self._validate("http://169.254.169.254/latest/meta-data/")

    def test_private_10_x_blocked(self):
        with self.assertRaises(Exception):
            self._validate("http://10.0.0.1/hook")

    def test_private_192_168_blocked(self):
        with self.assertRaises(Exception):
            self._validate("http://192.168.1.100/hook")

    def test_private_172_16_blocked(self):
        with self.assertRaises(Exception):
            self._validate("http://172.16.0.1/hook")

    def test_private_172_31_blocked(self):
        with self.assertRaises(Exception):
            self._validate("http://172.31.255.255/hook")

    def test_non_private_external_url_passes(self):
        """External public IP addresses must pass SSRF validation."""
        from backend.src.webhooks.schemas import _is_ssrf_destination
        # 93.184.216.34 is example.com's IP — a well-known public address
        self.assertFalse(_is_ssrf_destination("93.184.216.34"))

    def test_http_scheme_required(self):
        with self.assertRaises(Exception):
            self._validate("ftp://example.com/hook")

    def test_empty_url_blocked(self):
        with self.assertRaises(Exception):
            self._validate("")


class TestIsSsrfDestinationFunction(unittest.TestCase):
    """Unit tests for the _is_ssrf_destination helper."""

    def test_loopback_127_0_0_1(self):
        from backend.src.webhooks.schemas import _is_ssrf_destination
        self.assertTrue(_is_ssrf_destination("127.0.0.1"))

    def test_loopback_localhost(self):
        from backend.src.webhooks.schemas import _is_ssrf_destination
        self.assertTrue(_is_ssrf_destination("localhost"))

    def test_link_local_169(self):
        from backend.src.webhooks.schemas import _is_ssrf_destination
        self.assertTrue(_is_ssrf_destination("169.254.169.254"))

    def test_private_10_x(self):
        from backend.src.webhooks.schemas import _is_ssrf_destination
        self.assertTrue(_is_ssrf_destination("10.10.10.10"))

    def test_private_192_168(self):
        from backend.src.webhooks.schemas import _is_ssrf_destination
        self.assertTrue(_is_ssrf_destination("192.168.0.1"))

    def test_unresolvable_is_ssrf(self):
        from backend.src.webhooks.schemas import _is_ssrf_destination
        self.assertTrue(_is_ssrf_destination("this.hostname.does.not.exist.invalid"))


class TestWebhookDeliverySsrfBlock(unittest.IsolatedAsyncioTestCase):
    """Delivery-time SSRF check (DNS rebinding protection)."""

    async def test_deliver_webhook_blocks_private_address(self):
        from backend.src.webhooks.service import WebhookService
        from backend.src.webhooks.repository import WebhookRepository
        from unittest.mock import MagicMock
        svc = WebhookService(repo=MagicMock(spec=WebhookRepository))
        with self.assertRaises(ValueError) as ctx:
            await svc.deliver_webhook(
                url="http://192.168.1.1/ssrf",
                secret="s3cr3t",
                event_type="grant.created",
                payload={"test": True},
            )
        self.assertIn("private", str(ctx.exception).lower())

    async def test_deliver_webhook_blocks_loopback(self):
        from backend.src.webhooks.service import WebhookService
        from backend.src.webhooks.repository import WebhookRepository
        from unittest.mock import MagicMock
        svc = WebhookService(repo=MagicMock(spec=WebhookRepository))
        with self.assertRaises(ValueError):
            await svc.deliver_webhook(
                url="http://127.0.0.1/ssrf",
                secret="s3cr3t",
                event_type="grant.created",
                payload={"test": True},
            )
