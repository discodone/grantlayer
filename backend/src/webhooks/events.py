"""Webhook event type definitions for the GrantLayer lifecycle."""

from __future__ import annotations

from enum import Enum


class GrantEvent(str, Enum):
    created = "grant.created"
    updated = "grant.updated"
    approved = "grant.approved"
    rejected = "grant.rejected"
    executed = "grant.executed"
    revoked = "grant.revoked"


class GrantRequestEvent(str, Enum):
    submitted = "grant_request.submitted"
    created = "grant_request.created"
    approved = "grant_request.approved"
    rejected = "grant_request.rejected"
    denied = "grant_request.denied"


ALL_WEBHOOK_EVENTS: frozenset[str] = frozenset(
    {e.value for e in GrantEvent} | {e.value for e in GrantRequestEvent}
)
