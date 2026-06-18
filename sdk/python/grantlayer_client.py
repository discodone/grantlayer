"""
GrantLayer Minimal Python SDK — developer-preview, local use only.

Uses httpx. No network calls at import time.
Not package-published. No production SaaS readiness claimed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx


class GrantLayerClientError(Exception):
    """Base error for all GrantLayer client failures."""


class GrantLayerHTTPError(GrantLayerClientError):
    """Raised when the server returns a non-2xx response."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


class GrantLayerJSONError(GrantLayerClientError):
    """Raised when the response body cannot be decoded as JSON."""


class GrantLayerResponse:
    def __init__(self, status: int, body: Any, headers: Optional[Dict[str, str]] = None) -> None:
        self.status = status
        self.body = body
        self.headers: Dict[str, str] = headers if headers is not None else {}


class GrantLayerClient:
    """Minimal HTTP client for the GrantLayer MVP API.

    Authentication:
      - Legacy mode (ENABLE_OPERATOR_MODEL=false): pass the admin token.
      - Operator mode (ENABLE_OPERATOR_MODEL=true): pass an operator token.
      - Health/readiness endpoints are public; pass token=None for those.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout = timeout

    def _build_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if extra:
            headers.update(extra)
        return headers

    def request_json(
        self,
        method: str,
        path: str,
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> GrantLayerResponse:
        url = f"{self.base_url}/{path.lstrip('/')}"
        request_headers = self._build_headers(headers)
        if body is not None:
            request_headers["Content-Type"] = "application/json"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=request_headers,
                    content=json.dumps(body).encode() if body is not None else None,
                )
        except httpx.ConnectError as exc:
            raise GrantLayerClientError(f"Connection error: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise GrantLayerClientError(f"Request timed out: {exc}") from exc

        status = response.status_code
        raw = response.content
        resp_headers = dict(response.headers)

        if status >= 400:
            try:
                msg = response.json().get("error", "request failed")
            except Exception:
                msg = "request failed"
            raise GrantLayerHTTPError(status, msg)

        parsed: Any = None
        if raw:
            try:
                parsed = response.json()
            except Exception as exc:
                raise GrantLayerJSONError(f"Invalid JSON in response body: {exc}") from exc

        return GrantLayerResponse(status=status, body=parsed, headers=resp_headers)

    def health(self) -> GrantLayerResponse:
        return self.request_json("GET", "/health")

    def ready(self) -> GrantLayerResponse:
        return self.request_json("GET", "/readiness")
