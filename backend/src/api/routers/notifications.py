"""Notification preferences and unsubscribe endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse

from ...notifications.email import verify_unsubscribe_token

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(token: str = Query(...)) -> Any:
    email = verify_unsubscribe_token(token)
    if email is None:
        return HTMLResponse(
            content="<html><body><h2>Invalid or expired unsubscribe link.</h2></body></html>",
            status_code=400,
        )
    return HTMLResponse(
        content=f"<html><body><h2>Unsubscribed {email} from GrantLayer notifications.</h2></body></html>",
        status_code=200,
    )


@router.post("/unsubscribe")
async def unsubscribe_post(token: str = Query(...)) -> Any:
    email = verify_unsubscribe_token(token)
    if email is None:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_token", "reason": "Invalid or expired unsubscribe token."},
        )
    return {"ok": True, "email": email, "status": "unsubscribed"}
