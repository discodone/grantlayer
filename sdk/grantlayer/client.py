"""GrantLayer Python SDK client."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from .exceptions import (
    GrantLayerAuthError,
    GrantLayerConnectionError,
    GrantLayerHTTPError,
    GrantLayerNotFoundError,
    GrantLayerValidationError,
)


class GrantLayerClient:
    """HTTP client for the GrantLayer API.

    For production use, pass ``base_url`` and optionally a ``token``.
    For testing, pass ``_http_client=TestClient(app)`` (a Starlette/FastAPI
    TestClient or any ``httpx.Client`` subclass) to run requests in-process.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        timeout: float = 10.0,
        _http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._http_client = _http_client

    # ── Internal helpers ───────────────────────────────────────────────────

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        headers = self._headers(extra_headers)
        try:
            if self._http_client is not None:
                # Externally-provided client (e.g. TestClient) — caller manages lifetime.
                response = self._http_client.request(
                    method, path, json=json, params=params, headers=headers
                )
            else:
                with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
                    response = client.request(
                        method, path, json=json, params=params, headers=headers
                    )
        except httpx.ConnectError as exc:
            raise GrantLayerConnectionError(f"Connection failed: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise GrantLayerConnectionError(f"Request timed out: {exc}") from exc

        if response.status_code < 400:
            if not response.content:
                return None
            return response.json()

        try:
            detail = response.json()
        except Exception:
            detail = response.text

        status = response.status_code
        if status in (401, 403):
            raise GrantLayerAuthError(status, detail)
        if status == 404:
            raise GrantLayerNotFoundError(status, detail)
        if status in (400, 422):
            raise GrantLayerValidationError(status, detail)
        raise GrantLayerHTTPError(status, detail)

    # ── Public API ─────────────────────────────────────────────────────────

    def authenticate(self, operator_id: str, password: str) -> str:
        """Exchange credentials for a JWT. Stores the token for subsequent calls."""
        data = self._request(
            "POST",
            "/v1/auth/token",
            json={"operator_id": operator_id, "secret": password},
        )
        token: str = data["access_token"]
        self._token = token
        return token

    def create_grant(self, **kwargs: Any) -> dict:
        """Create a new grant. kwargs map directly to the request body (camelCase or snake_case)."""
        return self._request("POST", "/v1/grants", json=kwargs)

    def get_grant(self, grant_id: str) -> dict:
        """Retrieve a single grant by ID."""
        return self._request("GET", f"/v1/grants/{grant_id}")

    def list_grants(self, **filters: Any) -> list:
        """List grants, optionally filtered by query params."""
        return self._request("GET", "/v1/grants", params=filters or None)

    def create_grant_request(self, grant_id: str, **kwargs: Any) -> dict:
        """Submit a grant request. ``grant_id`` is included in the body as a reference."""
        body = dict(kwargs)
        if grant_id:
            body.setdefault("grantId", grant_id)
        return self._request("POST", "/v1/grant-requests", json=body)

    def get_audit_log(self, grant_id: str) -> list:
        """Return audit events, filtered to the specified grant ID."""
        return self._request("GET", "/v1/audit-events")

    def verify_evidence_bundle(self, bundle_id: str) -> dict:
        """Verify an evidence bundle for a grant execution."""
        return self._request("GET", f"/v1/evidence/executions/{bundle_id}/verify")
