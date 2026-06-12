"""
GrantLayer SDK Prototype — GL-203C, experimental, internal-only.

**Status: Developer Preview / Controlled Preview with strict boundaries.**

This is NOT an official SDK. No package is published. No production SaaS
readiness is claimed. Not ready for real customer data, private grant data,
or institutional data. Tenant/workspace isolation is baseline-implemented
but not production-complete. No official SDK/package is claimed or published.

This prototype demonstrates that the GL-203B cleaned OpenAPI contract is
sufficient for SDK work. It is not a replacement for the existing
sdk/python/grantlayer_client.py and must not be confused with an official
or published SDK.

Design properties:
- Python standard library only (urllib.request, json). No external dependencies.
- Injectable/mockable transport for deterministic testing without network.
- Token values are NEVER logged, printed, repr'd, or included in errors.
- No arbitrary tenant override headers (tenant context is server-derived).
- No hardcoded production endpoints or tokens.
- Auth header is added ONLY when a token is explicitly supplied by the caller.
- Safe error handling: server error messages surfaced without leaking auth tokens.

Security-sensitive reports must be routed to GitHub Security Advisories.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class GrantLayerClientError(Exception):
    """Base error for all GrantLayer prototype client failures."""


class GrantLayerHTTPError(GrantLayerClientError):
    """Non-2xx HTTP response. Token value is never included."""

    def __init__(self, status: int, error_code: str, error_message: str) -> None:
        self.status = status
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(f"HTTP {status} [{error_code}]: {error_message}")


class GrantLayerJSONError(GrantLayerClientError):
    """Server returned a non-JSON or malformed response body."""


class GrantLayerConnectionError(GrantLayerClientError):
    """Network-level failure reaching the GrantLayer server."""


# ---------------------------------------------------------------------------
# Response wrapper
# ---------------------------------------------------------------------------

class GrantLayerResponse:
    """Parsed response from the GrantLayer API."""

    __slots__ = ("status", "body", "headers", "correlation_id")

    def __init__(
        self,
        status: int,
        body: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.status: int = status
        self.body: Any = body
        self.headers: Dict[str, str] = headers or {}
        self.correlation_id: Optional[str] = self.headers.get("x-correlation-id")

    def __repr__(self) -> str:
        return f"GrantLayerResponse(status={self.status}, body={self.body!r})"


# ---------------------------------------------------------------------------
# Fake transport (for testing without network)
# ---------------------------------------------------------------------------

class _FakeHTTPResponse:
    """Simulated HTTP response for FakeTransport. Not for production use."""

    def __init__(
        self,
        status: int,
        body_dict: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.status = status
        self._body = json.dumps(body_dict).encode("utf-8")
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class FakeTransport:
    """
    Injectable fake transport for deterministic tests.

    Captures outbound requests; returns pre-configured responses.
    No network calls are made.

    Usage::

        transport = FakeTransport()
        transport.add_response(200, {"status": "ok", "service": "grantlayer"})
        client = GrantLayerClient("http://fake", _transport=transport)
        resp = client.health()
        assert resp.status == 200
        # Inspect recorded requests:
        assert transport.calls[0].get_full_url().endswith("/health")
    """

    def __init__(self) -> None:
        self.calls: List[urllib.request.Request] = []
        self._responses: List[_FakeHTTPResponse] = []

    def add_response(
        self,
        status: int,
        body: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._responses.append(_FakeHTTPResponse(status, body, headers))

    def add_error(self, status: int, body: Any) -> None:
        """Add a response that will be raised as urllib.error.HTTPError."""
        import io
        raw = json.dumps(body).encode()
        self._responses.append(
            _HTTPErrorResponse(status, raw)
        )

    def __call__(
        self,
        request: urllib.request.Request,
        timeout: Optional[float] = None,
    ) -> _FakeHTTPResponse:
        self.calls.append(request)
        if not self._responses:
            raise RuntimeError(
                "FakeTransport: no more configured responses. "
                "Call add_response() before each request."
            )
        resp = self._responses.pop(0)
        if isinstance(resp, _HTTPErrorResponse):
            raise resp.as_http_error()
        return resp


class _HTTPErrorResponse:
    """Internal sentinel for FakeTransport error simulation."""

    def __init__(self, status: int, raw_body: bytes) -> None:
        self._status = status
        self._raw_body = raw_body

    def as_http_error(self) -> urllib.error.HTTPError:
        import io
        return urllib.error.HTTPError(
            url="fake://",
            code=self._status,
            msg=f"HTTP {self._status}",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(self._raw_body),
        )


# ---------------------------------------------------------------------------
# Core client
# ---------------------------------------------------------------------------

class GrantLayerClient:
    """
    Minimal HTTP client for the GrantLayer MVP API — GL-203C prototype.

    **Internal-only / Developer Preview.** Not an official SDK.

    Auth modes (see docs/openapi.yaml):
    - Legacy (ENABLE_OPERATOR_MODEL=false): pass an admin token.
    - Operator (ENABLE_OPERATOR_MODEL=true): pass an operator token.
    - Public endpoints (health, readiness) require no token.

    Tenant context is ALWAYS server-derived from authentication.
    This client does NOT send tenant override headers.

    Token safety:
    - Token is stored in a private attribute and never included in
      __repr__, error messages, or log output.
    - Pass token=None for public endpoint calls.

    Args:
        base_url: Server base URL (e.g. "http://127.0.0.1:8765").
                  No default — caller must supply.
        token: Bearer token for authenticated endpoints.
               Never logged or repr'd. Pass None for public endpoints.
        timeout: Request timeout in seconds.
        _transport: Injectable transport callable for testing.
                    Signature: (request, timeout) -> response-like.
                    Default None uses urllib.request.urlopen.
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        timeout: float = 10.0,
        _transport: Optional[Callable] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._transport = _transport

    def __repr__(self) -> str:
        # Token intentionally excluded from repr.
        return (
            f"GrantLayerClient("
            f"base_url={self._base_url!r}, "
            f"has_token={self._token is not None}"
            f")"
        )

    def _build_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        # No X-Tenant-ID or any tenant override header — tenant context is server-derived.
        if extra:
            headers.update(extra)
        return headers

    def _do_request(
        self,
        method: str,
        path: str,
        body: Any = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> GrantLayerResponse:
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = self._build_headers(extra_headers)
        data: Optional[bytes] = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(data))

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        transport = self._transport or urllib.request.urlopen

        try:
            with transport(req, timeout=self._timeout) as resp:
                status: int = resp.status
                raw: bytes = resp.read()
                resp_headers: Dict[str, str] = {}
                if hasattr(resp, "headers") and resp.headers:
                    resp_headers = {k.lower(): v for k, v in dict(resp.headers).items()}
                if raw:
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise GrantLayerJSONError(
                            f"Server returned non-JSON body: {exc}"
                        ) from exc
                else:
                    parsed = None
                return GrantLayerResponse(status=status, body=parsed, headers=resp_headers)
        except urllib.error.HTTPError as exc:
            raw_err = b""
            if hasattr(exc, "read"):
                try:
                    raw_err = exc.read()
                except Exception:
                    pass
            error_code = "http_error"
            error_message = f"HTTP {exc.code}"
            try:
                err_body = json.loads(raw_err)
                error_code = err_body.get("errorCode", error_code)
                error_message = err_body.get("error", error_message)
                # Never include reason/detail that might contain token info
            except (ValueError, AttributeError):
                pass
            raise GrantLayerHTTPError(exc.code, error_code, error_message) from None
        except urllib.error.URLError as exc:
            # Never include the URL in the error message if it might contain tokens
            raise GrantLayerConnectionError(
                f"Connection error reaching GrantLayer server: {exc.reason}"
            ) from exc

    # -----------------------------------------------------------------------
    # Public endpoints — no auth required
    # -----------------------------------------------------------------------

    def health(self) -> GrantLayerResponse:
        """GET /health — liveness check. No auth required."""
        return self._do_request("GET", "/health")

    def readiness(self) -> GrantLayerResponse:
        """GET /readiness — readiness check. No auth required."""
        return self._do_request("GET", "/readiness")

    # -----------------------------------------------------------------------
    # Core grant endpoints
    # -----------------------------------------------------------------------

    def list_grants(self) -> GrantLayerResponse:
        """GET /v1/grants — list all grants. Requires auth."""
        return self._do_request("GET", "/v1/grants")

    def get_grant(self, grant_id: str) -> GrantLayerResponse:
        """GET /v1/grants/{id} — get a single grant. Requires auth."""
        return self._do_request("GET", f"/v1/grants/{grant_id}")

    def create_grant(
        self,
        subject_id: str,
        role: str,
        action: str,
        resource: str,
        valid_from: str,
        valid_until: str,
        created_by: str,
        reason: str,
        max_uses: Optional[int] = None,
    ) -> GrantLayerResponse:
        """POST /v1/grants — create a new grant. Requires auth."""
        body: Dict[str, Any] = {
            "subjectId": subject_id,
            "role": role,
            "action": action,
            "resource": resource,
            "validFrom": valid_from,
            "validUntil": valid_until,
            "createdBy": created_by,
            "reason": reason,
        }
        if max_uses is not None:
            body["maxUses"] = max_uses
        return self._do_request("POST", "/v1/grants", body=body)

    def revoke_grant(
        self,
        grant_id: str,
        revoked_by: str,
        reason: str,
    ) -> GrantLayerResponse:
        """POST /v1/grants/{id}/revoke — revoke an active grant. Requires auth."""
        return self._do_request(
            "POST",
            f"/v1/grants/{grant_id}/revoke",
            body={"revokedBy": revoked_by, "reason": reason},
        )

    # -----------------------------------------------------------------------
    # Audit log
    # -----------------------------------------------------------------------

    def list_audit_events(self, limit: int = 200) -> GrantLayerResponse:
        """GET /v1/audit-events — list audit events. Requires auth."""
        return self._do_request("GET", f"/v1/audit-events?limit={limit}")

    # -----------------------------------------------------------------------
    # Challenges
    # -----------------------------------------------------------------------

    def list_challenges(self) -> GrantLayerResponse:
        """GET /v1/challenges — list all challenges. Requires auth."""
        return self._do_request("GET", "/v1/challenges")

    def create_challenge(
        self,
        subject_id: str,
        action: str,
        resource: str,
    ) -> GrantLayerResponse:
        """POST /v1/challenges — create a challenge. Requires auth."""
        return self._do_request(
            "POST",
            "/v1/challenges",
            body={"subjectId": subject_id, "action": action, "resource": resource},
        )

    # -----------------------------------------------------------------------
    # Operator profile
    # -----------------------------------------------------------------------

    def get_operator_me(self) -> GrantLayerResponse:
        """GET /v1/operators/me — current operator profile. Operator mode only."""
        return self._do_request("GET", "/v1/operators/me")

    # -----------------------------------------------------------------------
    # Grant requests (operator mode)
    # -----------------------------------------------------------------------

    def list_grant_requests(
        self, status_filter: Optional[str] = None
    ) -> GrantLayerResponse:
        """GET /v1/grant-requests — list grant requests. Requires auth."""
        path = "/v1/grant-requests"
        if status_filter:
            path = f"/v1/grant-requests?status={status_filter}"
        return self._do_request("GET", path)

    def get_grant_request(self, request_id: str) -> GrantLayerResponse:
        """GET /v1/grant-requests/{id} — get a single grant request. Operator mode only."""
        return self._do_request("GET", f"/v1/grant-requests/{request_id}")

    def create_grant_request(
        self,
        subject_id: str,
        role: str,
        action: str,
        resource: str,
        valid_from: str,
        valid_until: str,
        reason: str,
    ) -> GrantLayerResponse:
        """POST /v1/grant-requests — create a grant request. Operator mode only."""
        return self._do_request(
            "POST",
            "/v1/grant-requests",
            body={
                "subjectId": subject_id,
                "role": role,
                "action": action,
                "resource": resource,
                "validFrom": valid_from,
                "validUntil": valid_until,
                "reason": reason,
            },
        )

    def approve_grant_request(self, request_id: str) -> GrantLayerResponse:
        """POST /v1/grant-requests/{id}/approve — approve a request. Operator mode only."""
        return self._do_request("POST", f"/v1/grant-requests/{request_id}/approve")

    def deny_grant_request(self, request_id: str, reason: str) -> GrantLayerResponse:
        """POST /v1/grant-requests/{id}/deny — deny a request. Operator mode only."""
        return self._do_request(
            "POST",
            f"/v1/grant-requests/{request_id}/deny",
            body={"reason": reason},
        )

    # -----------------------------------------------------------------------
    # Grant executions (operator mode)
    # -----------------------------------------------------------------------

    def list_grant_executions(
        self,
        limit: int = 200,
        grant_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> GrantLayerResponse:
        """GET /v1/grant-executions — list executions. Operator mode only."""
        params = [f"limit={limit}"]
        if grant_id:
            params.append(f"grantId={grant_id}")
        if operator_id:
            params.append(f"operatorId={operator_id}")
        return self._do_request("GET", f"/v1/grant-executions?{'&'.join(params)}")

    def get_grant_execution(self, execution_id: str) -> GrantLayerResponse:
        """GET /v1/grant-executions/{id} — get a single execution. Operator mode only."""
        return self._do_request("GET", f"/v1/grant-executions/{execution_id}")

    def list_executions_for_grant(
        self, grant_id: str, limit: int = 200
    ) -> GrantLayerResponse:
        """GET /v1/grants/{id}/executions — list executions for a grant. Operator mode only."""
        return self._do_request("GET", f"/v1/grants/{grant_id}/executions?limit={limit}")

    # -----------------------------------------------------------------------
    # Evidence / provenance
    # -----------------------------------------------------------------------

    def get_evidence_bundle(self, execution_id: str) -> GrantLayerResponse:
        """GET /v1/evidence/executions/{id} — evidence bundle. Requires auth."""
        return self._do_request("GET", f"/v1/evidence/executions/{execution_id}")

    def verify_evidence_bundle(self, execution_id: str) -> GrantLayerResponse:
        """GET /v1/evidence/executions/{id}/verify — verify evidence. Requires auth."""
        return self._do_request("GET", f"/v1/evidence/executions/{execution_id}/verify")

    # -----------------------------------------------------------------------
    # Agent permissions
    # -----------------------------------------------------------------------

    def list_agent_permission_profiles(self) -> GrantLayerResponse:
        """GET /v1/agent-permissions/profiles — list profiles. Requires auth."""
        return self._do_request("GET", "/v1/agent-permissions/profiles")

    def get_agent_permission_profile(self, profile_name: str) -> GrantLayerResponse:
        """GET /v1/agent-permissions/profiles/{name} — get a profile. Requires auth."""
        return self._do_request("GET", f"/v1/agent-permissions/profiles/{profile_name}")

    def evaluate_agent_permission(
        self,
        agent_id: str,
        requested_scope: str,
        assigned_scopes: List[str],
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> GrantLayerResponse:
        """POST /v1/agent-permissions/evaluate — evaluate agent permission. Requires auth."""
        body: Dict[str, Any] = {
            "agentId": agent_id,
            "requestedScope": requested_scope,
            "assignedScopes": assigned_scopes,
        }
        if resource_type is not None:
            body["resourceType"] = resource_type
        if resource_id is not None:
            body["resourceId"] = resource_id
        return self._do_request("POST", "/v1/agent-permissions/evaluate", body=body)

    # -----------------------------------------------------------------------
    # Generic escape hatch
    # -----------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> GrantLayerResponse:
        """
        Generic request for endpoints not covered by named methods.

        Note: Extra headers must NOT include tenant override headers.
        Tenant context is always server-derived from authentication.
        """
        return self._do_request(method, path, body=body, extra_headers=extra_headers)
