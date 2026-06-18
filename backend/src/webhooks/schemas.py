"""Pydantic schemas for the webhook system."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from .events import ALL_WEBHOOK_EVENTS


def _is_ssrf_destination(host: str) -> bool:
    """Return True if *host* resolves to a private/loopback/link-local address.

    Blocks: loopback (127.x, ::1), link-local (169.254.x, fe80::/10),
    private RFC-1918 (10.x, 172.16-31.x, 192.168.x), and unspecified (0.0.0.0).
    DNS rebinding is mitigated by resolving here and again at delivery time.
    """
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        return False  # unresolvable — let delivery fail naturally

    for _family, _type, _proto, _canonname, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if (
            ip.is_loopback
            or ip.is_link_local
            or ip.is_private
            or ip.is_unspecified
            or ip.is_multicast
        ):
            return True
    return False


class WebhookCreateRequest(BaseModel):
    url: str = Field(..., max_length=2048)
    events: List[str]
    secret: Optional[str] = Field(None, max_length=256)

    model_config = {"populate_by_name": True}

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url must be non-empty")
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("url must start with http:// or https://")
        parsed = urlparse(v)
        host = parsed.hostname or ""
        if not host:
            raise ValueError("url must contain a valid hostname")
        if _is_ssrf_destination(host):
            raise ValueError(
                "url destination is not allowed: loopback, link-local, and private "
                "network addresses are blocked to prevent SSRF attacks"
            )
        return v

    @field_validator("events")
    @classmethod
    def _validate_events(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("events must contain at least one event type")
        invalid = [e for e in v if e not in ALL_WEBHOOK_EVENTS]
        if invalid:
            raise ValueError(
                f"Unknown event types: {invalid}. Valid: {sorted(ALL_WEBHOOK_EVENTS)}"
            )
        return list(set(v))


class WebhookResponse(BaseModel):
    id: str
    tenant_id: str = Field(alias="tenantId")
    workspace_id: Optional[str] = Field(alias="workspaceId")
    url: str
    events: List[str]
    active: bool
    created_at: str = Field(alias="createdAt")
    created_by: str = Field(alias="createdBy")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "WebhookResponse":
        import json
        events = json.loads(row["events"]) if isinstance(row["events"], str) else row["events"]
        return cls(
            id=row["id"],
            tenantId=row["tenant_id"],
            workspaceId=row.get("workspace_id"),
            url=row["url"],
            events=events,
            active=bool(row["active"]),
            createdAt=row["created_at"],
            createdBy=row["created_by"],
        )


class WebhookListResponse(BaseModel):
    items: List[WebhookResponse]
    total: int


class WebhookDeliveryResponse(BaseModel):
    id: str
    webhook_id: str = Field(alias="webhookId")
    event_type: str = Field(alias="eventType")
    status: str
    http_status: Optional[int] = Field(alias="httpStatus")
    error: Optional[str] = None
    attempt: int
    created_at: str = Field(alias="createdAt")
    delivered_at: Optional[str] = Field(alias="deliveredAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "WebhookDeliveryResponse":
        return cls(
            id=row["id"],
            webhookId=row["webhook_id"],
            eventType=row["event_type"],
            status=row["status"],
            httpStatus=row.get("http_status"),
            error=row.get("error"),
            attempt=row["attempt"],
            createdAt=row["created_at"],
            deliveredAt=row.get("delivered_at"),
        )


class WebhookDeliveryListResponse(BaseModel):
    items: List[WebhookDeliveryResponse]
    total: int
