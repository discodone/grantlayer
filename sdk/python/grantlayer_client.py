"""
GrantLayer Minimal Python SDK — developer-preview, local use only.

Standard library only. No network calls at import time.
Not package-published. No production SaaS readiness claimed.
Tenant isolation not implemented.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


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
        data: Optional[bytes] = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url, data=data, headers=request_headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status: int = resp.status
                raw: bytes = resp.read()
                resp_headers = dict(resp.headers) if resp.headers else {}
                if raw:
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise GrantLayerJSONError(
                            f"Invalid JSON in response body: {exc}"
                        ) from exc
                else:
                    parsed = None
                return GrantLayerResponse(status=status, body=parsed, headers=resp_headers)
        except urllib.error.HTTPError as exc:
            raw_err = exc.read()
            try:
                msg = json.loads(raw_err).get("error", "request failed")
            except (ValueError, KeyError):
                msg = "request failed"
            raise GrantLayerHTTPError(exc.code, msg) from None
        except urllib.error.URLError as exc:
            raise GrantLayerClientError(f"Connection error: {exc.reason}") from exc

    def health(self) -> GrantLayerResponse:
        return self.request_json("GET", "/health")

    def ready(self) -> GrantLayerResponse:
        return self.request_json("GET", "/readiness")
