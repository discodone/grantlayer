"""SQLAlchemy ORM models for the webhook system.

WebhookEndpoint — a registered webhook subscription (alias of WebhookSubscription).
WebhookDelivery  — records of individual delivery attempts with status/error.
"""

from __future__ import annotations

from ..core.orm import WebhookDelivery  # noqa: F401 (re-export)
from ..core.orm import WebhookSubscription as WebhookEndpoint  # noqa: F401 (re-export)

__all__ = ["WebhookEndpoint", "WebhookDelivery"]
