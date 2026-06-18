"""GrantLayer Python SDK — sync and async clients."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx

try:
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
    _TENACITY = True
except ImportError:
    _TENACITY = False

from .exceptions import (
    GrantLayerAuthError,
    GrantLayerConnectionError,
    GrantLayerHTTPError,
    GrantLayerNotFoundError,
    GrantLayerRateLimitError,
    GrantLayerValidationError,
)


def _parse_response(response: Any) -> Any:
    status = response.status_code
    if status < 400:
        if not response.content:
            return None
        try:
            return response.json()
        except Exception:
            return response.text

    try:
        detail = response.json()
    except Exception:
        detail = response.text

    if status == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        raise GrantLayerRateLimitError(status, detail, retry_after)
    if status in (401, 403):
        raise GrantLayerAuthError(status, detail)
    if status == 404:
        raise GrantLayerNotFoundError(status, detail)
    if status in (400, 422):
        raise GrantLayerValidationError(status, detail)
    raise GrantLayerHTTPError(status, detail)


class GrantLayerClient:
    """Synchronous HTTP client for the GrantLayer API."""

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        _http_client: Optional[Any] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries
        self._http_client = _http_client

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

        return _parse_response(response)

    def _req(self, method: str, path: str, **kwargs: Any) -> Any:
        if not _TENACITY or self._max_retries <= 0:
            return self._request(method, path, **kwargs)

        @retry(
            retry=retry_if_exception_type((GrantLayerConnectionError, GrantLayerRateLimitError)),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            reraise=True,
        )
        def _do() -> Any:
            return self._request(method, path, **kwargs)

        return _do()

    # ── Auth ───────────────────────────────────────────────────────────────

    def authenticate(self, operator_id: str, secret: str) -> str:
        data = self._req("POST", "/v1/auth/token", json={"operator_id": operator_id, "secret": secret})
        token: str = data["access_token"]
        self._token = token
        return token

    # ── Grants ─────────────────────────────────────────────────────────────

    def create_grant(self, **kwargs: Any) -> dict:
        return self._req("POST", "/v1/grants", json=kwargs)

    def get_grant(self, grant_id: str) -> dict:
        return self._req("GET", f"/v1/grants/{grant_id}")

    def list_grants(self, **filters: Any) -> list:
        return self._req("GET", "/v1/grants", params=filters or None)

    def revoke_grant(self, grant_id: str, reason: str = "") -> dict:
        return self._req("POST", f"/v1/grants/{grant_id}/revoke", json={"reason": reason})

    def bulk_update_grants(self, grant_ids: List[str], **update: Any) -> dict:
        return self._req("POST", "/v1/grants/bulk-update", json={"grantIds": grant_ids, **update})

    # ── Grant Requests ─────────────────────────────────────────────────────

    def create_grant_request(self, **kwargs: Any) -> dict:
        return self._req("POST", "/v1/grant-requests", json=kwargs)

    def get_grant_request(self, request_id: str) -> dict:
        return self._req("GET", f"/v1/grant-requests/{request_id}")

    def list_grant_requests(self, **filters: Any) -> Any:
        return self._req("GET", "/v1/grant-requests", params=filters or None)

    def approve_grant_request(self, request_id: str, reason: str = "") -> dict:
        return self._req("POST", f"/v1/grant-requests/{request_id}/approve", json={"reason": reason})

    def deny_grant_request(self, request_id: str, reason: str = "") -> dict:
        return self._req("POST", f"/v1/grant-requests/{request_id}/deny", json={"reason": reason})

    def bulk_approve_grant_requests(self, request_ids: List[str], reason: str = "") -> dict:
        return self._req("POST", "/v1/grant-requests/bulk-approve", json={"requestIds": request_ids, "reason": reason})

    def bulk_reject_grant_requests(self, request_ids: List[str], reason: str = "") -> dict:
        return self._req("POST", "/v1/grant-requests/bulk-reject", json={"requestIds": request_ids, "reason": reason})

    # ── Grant Executions ────────────────────────────────────────────────────

    def create_execution(self, **kwargs: Any) -> dict:
        return self._req("POST", "/v1/grant-executions", json=kwargs)

    def get_execution(self, execution_id: str) -> dict:
        return self._req("GET", f"/v1/grant-executions/{execution_id}")

    def list_executions(self, **filters: Any) -> list:
        return self._req("GET", "/v1/grant-executions", params=filters or None)

    # ── Audit Events ────────────────────────────────────────────────────────

    def get_audit_log(self, **filters: Any) -> Any:
        return self._req("GET", "/v1/audit-events", params=filters or None)

    # ── Evidence ────────────────────────────────────────────────────────────

    def verify_evidence_bundle(self, bundle_id: str) -> dict:
        return self._req("GET", f"/v1/evidence/executions/{bundle_id}/verify")

    def get_evidence_bundle(self, bundle_id: str) -> dict:
        return self._req("GET", f"/v1/evidence/executions/{bundle_id}")

    # ── Webhooks ────────────────────────────────────────────────────────────

    def create_webhook(self, url: str, events: List[str], **kwargs: Any) -> dict:
        return self._req("POST", "/v1/webhooks", json={"url": url, "events": events, **kwargs})

    def list_webhooks(self) -> list:
        return self._req("GET", "/v1/webhooks")

    def get_webhook(self, webhook_id: str) -> dict:
        return self._req("GET", f"/v1/webhooks/{webhook_id}")

    def delete_webhook(self, webhook_id: str) -> None:
        self._req("DELETE", f"/v1/webhooks/{webhook_id}")

    # ── Policy ──────────────────────────────────────────────────────────────

    def list_policy_requirements(self, **filters: Any) -> Any:
        return self._req("GET", "/v1/policy-requirements", params=filters or None)

    # ── Admin (operators) ────────────────────────────────────────────────────

    def list_operators(self) -> list:
        return self._req("GET", "/v1/admin/operators")

    def create_operator(self, name: str, role: str, tenant_id: str) -> dict:
        return self._req("POST", "/v1/admin/operators", json={"name": name, "role": role, "tenantId": tenant_id})

    def revoke_operator(self, operator_id: str) -> dict:
        return self._req("POST", f"/v1/admin/operators/{operator_id}/revoke")

    # ── Health ───────────────────────────────────────────────────────────────

    def health(self) -> dict:
        return self._req("GET", "/health")

    def admin_health(self) -> dict:
        return self._req("GET", "/admin/health")


class AsyncGrantLayerClient:
    """Async HTTP client for the GrantLayer API.

    Usage::

        async with AsyncGrantLayerClient(base_url="https://…", token="…") as client:
            grants = await client.list_grants()
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AsyncGrantLayerClient":
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def _request(self, method: str, path: str, *, json: Any = None, params: Optional[Dict[str, Any]] = None) -> Any:
        assert self._client is not None, "Use as async context manager"
        last_exc: Optional[Exception] = None
        for attempt in range(max(1, self._max_retries)):
            try:
                response = await self._client.request(method, path, json=json, params=params, headers=self._headers())
                return _parse_response(response)
            except GrantLayerRateLimitError as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(min(exc.retry_after, 30))
            except GrantLayerConnectionError as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except (GrantLayerAuthError, GrantLayerNotFoundError, GrantLayerValidationError):
                raise
        raise last_exc  # type: ignore[misc]

    async def authenticate(self, operator_id: str, secret: str) -> str:
        data = await self._request("POST", "/v1/auth/token", json={"operator_id": operator_id, "secret": secret})
        self._token = data["access_token"]
        return self._token

    async def create_grant(self, **kwargs: Any) -> dict:
        return await self._request("POST", "/v1/grants", json=kwargs)

    async def get_grant(self, grant_id: str) -> dict:
        return await self._request("GET", f"/v1/grants/{grant_id}")

    async def list_grants(self, **filters: Any) -> list:
        return await self._request("GET", "/v1/grants", params=filters or None)

    async def revoke_grant(self, grant_id: str, reason: str = "") -> dict:
        return await self._request("POST", f"/v1/grants/{grant_id}/revoke", json={"reason": reason})

    async def create_grant_request(self, **kwargs: Any) -> dict:
        return await self._request("POST", "/v1/grant-requests", json=kwargs)

    async def get_grant_request(self, request_id: str) -> dict:
        return await self._request("GET", f"/v1/grant-requests/{request_id}")

    async def list_grant_requests(self, **filters: Any) -> Any:
        return await self._request("GET", "/v1/grant-requests", params=filters or None)

    async def approve_grant_request(self, request_id: str, reason: str = "") -> dict:
        return await self._request("POST", f"/v1/grant-requests/{request_id}/approve", json={"reason": reason})

    async def deny_grant_request(self, request_id: str, reason: str = "") -> dict:
        return await self._request("POST", f"/v1/grant-requests/{request_id}/deny", json={"reason": reason})

    async def get_audit_log(self, **filters: Any) -> Any:
        return await self._request("GET", "/v1/audit-events", params=filters or None)

    async def create_webhook(self, url: str, events: List[str], **kwargs: Any) -> dict:
        return await self._request("POST", "/v1/webhooks", json={"url": url, "events": events, **kwargs})

    async def list_webhooks(self) -> list:
        return await self._request("GET", "/v1/webhooks")

    async def get_webhook(self, webhook_id: str) -> dict:
        return await self._request("GET", f"/v1/webhooks/{webhook_id}")

    async def delete_webhook(self, webhook_id: str) -> None:
        await self._request("DELETE", f"/v1/webhooks/{webhook_id}")

    async def list_operators(self) -> list:
        return await self._request("GET", "/v1/admin/operators")

    async def health(self) -> dict:
        return await self._request("GET", "/health")
