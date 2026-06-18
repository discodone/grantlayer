"""Pydantic schemas for the webhook system."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .events import ALL_WEBHOOK_EVENTS


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
