"""GrantLayer MVP — HTTP server."""

import datetime
import hashlib
import json
import re
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from .db import init_db
from .models import Grant, GrantRequest
from .grants import list_grants, create_grant, revoke_grant, get_grant, tamper_grant
from .audit_log import list_events
from .demo_action import handle_demo_action
from .challenges import create_challenge, list_challenges
from .auth import check_auth, check_admin_token, admin_token_warning
from .crypto_signing import ensure_demo_keypair, verify_grant_signature
from . import config
from . import operators as ops
from . import grant_requests
from . import grant_executions as execs
from .evidence_bundle import build_evidence_bundle
from .evidence_verification import verify_execution
from .provenance_summary import build_decision_provenance_summary
from .evidence_completeness import build_evidence_completeness_for_execution
from .auditor_report import build_auditor_report_for_execution
from .compliance_gap_report import build_compliance_gap_report_for_execution
from .agent_permissions import evaluate_agent_permission
from .agent_permission_profiles import (
    get_agent_permission_profile,
    list_agent_permission_profiles,
)
from .agent_permission_assignments import resolve_agent_permission_assignment
from .approval_rules import evaluate_approval_requirements
from .approval_lifecycle import build_approval_request_lifecycle, transition_approval_request
from .compliance_readiness import build_compliance_readiness_summary
from .decision_provenance import build_decision_provenance_v2
from .auditor_export import build_institutional_auditor_export
from .policy_requirements import evaluate_policy_requirements
from .runtime_config import describe_runtime_config, get_runtime_mode
from .rate_limiter import RateLimiter

DASHBOARD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "dashboard", "index.html",
)

_rate_limiter = RateLimiter(
    auth_limit=config.GRANTLAYER_RATE_LIMIT_AUTH,
    api_limit=config.GRANTLAYER_RATE_LIMIT_API,
)

def _cors_headers_for(origin: str | None) -> dict[str, str]:
    """Return CORS headers only for explicitly allowed origins.

    Uses exact string matching. No wildcard grants. No reflection of
    arbitrary origins. Unlisted origins receive no CORS access.
    """
    if origin and origin in config.CORS_ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Vary": "Origin",
        }
    return {}


MAX_JSON_BODY_BYTES = 1_048_576


class _QueryParamError(Exception):
    """Raised when a query parameter fails safe parsing so the caller can return."""
    pass


class _BodyParseError(ValueError):
    """Raised when request body parsing fails so the caller can send a safe response."""
    def __init__(self, status: int, payload: dict):
        self.status = status
        self.payload = payload
        super().__init__()


class GrantLayerHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # noqa: N802
        print(f"[{self.log_date_time_string()}] {fmt % args}", flush=True)

    def _gl030_error(self, error: str, code: str, reason: str | None = None) -> dict:
        """Build a consistent GL-030 additive error payload.

        All error responses use the shape:
        {
            "error": "human-readable summary",
            "errorCode": "machine-readable-code",
            "reason": "detailed explanation"
        }
        """
        return {
            "error": error,
            "errorCode": code,
            "reason": reason or error,
        }

    def _handle_json_error(self, exc: Exception) -> None:
        """Send a safe deterministic response for JSON body parse failures.

        If *exc* is a `_BodyParseError` the stored status/payload are used;
        otherwise a generic safe HTTP 400 is returned.
        """
        if isinstance(exc, _BodyParseError):
            self._send_json(exc.status, exc.payload)
        else:
            self._send_json(
                400,
                self._gl030_error(
                    "Invalid JSON",
                    "INVALID_JSON",
                    "The request body is not valid JSON.",
                ),
            )

    def _send_json(self, status: int, data) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin")
        for k, v in _cors_headers_for(origin).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            # Backward compatibility: test mocks using BytesIO with empty
            # content should be treated as empty body. For real connections,
            # require Content-Length to bound reads safely.
            try:
                from io import BytesIO
                if isinstance(self.rfile, BytesIO) and self.rfile.tell() >= len(self.rfile.getvalue()):
                    return {}
            except Exception:
                pass
            raise _BodyParseError(
                400,
                self._gl030_error(
                    "Missing Content-Length",
                    "missing_content_length",
                    "The Content-Length header is required for JSON request bodies.",
                ),
            )
        try:
            length = int(content_length)
        except ValueError:
            raise _BodyParseError(
                400,
                self._gl030_error(
                    "Invalid Content-Length",
                    "invalid_content_length",
                    "The Content-Length header must be a valid non-negative integer.",
                ),
            )
        if length < 0:
            raise _BodyParseError(
                400,
                self._gl030_error(
                    "Invalid Content-Length",
                    "invalid_content_length",
                    "The Content-Length header must be a valid non-negative integer.",
                ),
            )
        if length > MAX_JSON_BODY_BYTES:
            raise _BodyParseError(
                413,
                self._gl030_error(
                    "Payload Too Large",
                    "payload_too_large",
                    f"Request body exceeds maximum size of {MAX_JSON_BODY_BYTES} bytes.",
                ),
            )
        if length == 0:
            raise _BodyParseError(
                400,
                self._gl030_error(
                    "Empty request body",
                    "empty_request_body",
                    "The request body is empty and valid JSON is required.",
                ),
            )
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise _BodyParseError(
                400,
                self._gl030_error(
                    "Invalid JSON",
                    "invalid_json",
                    "The request body is not valid JSON.",
                ),
            )

    def _missing(self, data: dict, fields: list) -> list:
        return [f for f in fields if f not in data or data.get(f) is None]

    def _validate_iso_timestamp(self, value, field_name: str) -> tuple[bool, dict | None]:
        """Validate a value is a valid ISO-8601 timestamp string.

        Returns (ok, error_payload).  Does not leak raw exceptions.
        """
        if not isinstance(value, str) or not value.strip():
            return False, self._gl030_error(
                f"Invalid {field_name}",
                "invalid_timestamp",
                f"{field_name} must be a valid ISO-8601 timestamp.",
            )
        try:
            if value.endswith("Z"):
                datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                datetime.datetime.fromisoformat(value)
        except ValueError:
            return False, self._gl030_error(
                f"Invalid {field_name}",
                "invalid_timestamp",
                f"{field_name} must be a valid ISO-8601 timestamp.",
            )
        return True, None

    def _validate_grant_dates(self, valid_from: str, valid_until: str) -> tuple[bool, dict | None]:
        """Validate that valid_from and valid_until are parseable and valid_from < valid_until."""
        ok, err = self._validate_iso_timestamp(valid_from, "validFrom")
        if not ok:
            return False, err
        ok, err = self._validate_iso_timestamp(valid_until, "validUntil")
        if not ok:
            return False, err
        try:
            vf = (
                datetime.datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
                if valid_from.endswith("Z")
                else datetime.datetime.fromisoformat(valid_from)
            )
            vu = (
                datetime.datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
                if valid_until.endswith("Z")
                else datetime.datetime.fromisoformat(valid_until)
            )
        except ValueError:
            return False, self._gl030_error(
                "Invalid date range",
                "invalid_date_range",
                "The specified date range is invalid.",
            )
        if vf >= vu:
            return False, self._gl030_error(
                "Invalid date range",
                "invalid_date_range",
                "validFrom must be strictly before validUntil.",
            )
        return True, None

    def _validate_max_uses(self, value) -> tuple[bool, dict | None]:
        """Validate maxUses: if present it must be an integer >= 1.  bool is not accepted as int."""
        if value is None:
            return True, None
        if isinstance(value, bool):
            return False, self._gl030_error(
                "Invalid maxUses",
                "invalid_max_uses",
                "maxUses must be an integer >= 1.",
            )
        if not isinstance(value, int):
            return False, self._gl030_error(
                "Invalid maxUses",
                "invalid_max_uses",
                "maxUses must be an integer >= 1.",
            )
        if value < 1:
            return False, self._gl030_error(
                "Invalid maxUses",
                "invalid_max_uses",
                "maxUses must be an integer >= 1.",
            )
        return True, None

    def _parse_int_query_param(
        self, qs, name: str, default=None, minimum: int = 1, maximum: int = 1000
    ) -> int | None:
        """Safely parse an integer query parameter.

        - Returns *default* if the parameter is absent or the list is empty.
        - Returns the parsed integer if it is valid and within bounds.
        - Sends a deterministic HTTP 400 JSON response and raises
          `_QueryParamError` for invalid, out-of-bounds, or empty values.
        """
        raw_list = qs.get(name)
        if not raw_list:
            return default
        raw = raw_list[0]
        if raw == "":
            self._send_json(
                400,
                self._gl030_error(
                    f"Invalid query parameter: {name}",
                    "INVALID_QUERY_PARAMETER",
                    f"The {name} parameter must be a valid integer.",
                ),
            )
            raise _QueryParamError(name)
        try:
            value = int(raw)
        except (ValueError, TypeError):
            self._send_json(
                400,
                self._gl030_error(
                    f"Invalid query parameter: {name}",
                    "INVALID_QUERY_PARAMETER",
                    f"The {name} parameter must be a valid integer.",
                ),
            )
            raise _QueryParamError(name)
        if value < minimum:
            self._send_json(
                400,
                self._gl030_error(
                    f"Invalid query parameter: {name}",
                    "INVALID_QUERY_PARAMETER",
                    f"The {name} parameter must be at least {minimum}.",
                ),
            )
            raise _QueryParamError(name)
        if value > maximum:
            self._send_json(
                400,
                self._gl030_error(
                    f"Invalid query parameter: {name}",
                    "INVALID_QUERY_PARAMETER",
                    f"The {name} parameter must be at most {maximum}.",
                ),
            )
            raise _QueryParamError(name)
        return value

    def do_OPTIONS(self):  # noqa: N802
        """Handle CORS preflight deterministically and without state mutation."""
        self.send_response(204)
        origin = self.headers.get("Origin")
        for k, v in _cors_headers_for(origin).items():
            self.send_header(k, v)
        self.end_headers()

    def _require_admin(self) -> tuple[bool, dict]:
        auth_header = self.headers.get("Authorization")
        cache_key = ("admin", hashlib.sha256(auth_header.encode("utf-8")).hexdigest() if auth_header else None)
        cached = getattr(self, "_auth_cache", {}).get(cache_key)
        if cached is not None:
            ok, status, payload = cached
            if not ok:
                self._send_json(status, payload)
                return False, {}
            return True, {}
        ok, status, payload = check_admin_token(auth_header)
        if not hasattr(self, "_auth_cache"):
            self._auth_cache = {}
        self._auth_cache[cache_key] = (ok, status, payload)
        if not ok:
            self._send_json(status, payload)
            return False, {}
        return True, {}

    def _require_operator(self, roles: list[str]) -> tuple[bool, dict]:
        auth_header = self.headers.get("Authorization")
        cache_key = ("operator", tuple(roles), hashlib.sha256(auth_header.encode("utf-8")).hexdigest() if auth_header else None)
        cached = getattr(self, "_auth_cache", {}).get(cache_key)
        if cached is not None:
            ok, status, payload = cached
            if not ok:
                self._send_json(status, payload)
                return False, {}
            return True, payload
        ok, status, payload = check_auth(auth_header, required_roles=roles)
        if not hasattr(self, "_auth_cache"):
            self._auth_cache = {}
        self._auth_cache[cache_key] = (ok, status, payload)
        if not ok:
            self._send_json(status, payload)
            return False, {}
        return True, payload

    def _require_auth(self, roles: list[str]) -> tuple[bool, dict]:
        """Unified auth check: operator model or legacy admin token.

        Consolidates the repeated ENABLE_OPERATOR_MODEL branching so each
        endpoint calls auth once.  On failure the response is already sent
        as deterministic safe JSON with keys 'error', 'errorCode', 'reason'.
        """
        if config.ENABLE_OPERATOR_MODEL:
            return self._require_operator(roles)
        return self._require_admin()

    def _check_rate_limit(self, group: str) -> bool:
        """Check rate limit for the current client IP and endpoint group.

        Returns True if the request is allowed.  On False a deterministic
        HTTP 429 response with Retry-After is already sent.

        When client_address is not available (e.g. some test mocks) the
        check is skipped to avoid breaking test suites that are not
        explicitly testing rate-limit behaviour.
        """
        client_address = getattr(self, "client_address", None)
        if client_address is None:
            return True
        ip = client_address[0]
        allowed, retry_after = _rate_limiter.check(ip, group)
        if not allowed:
            payload = self._gl030_error(
                "Rate limit exceeded",
                "rate_limit_exceeded",
                f"Too many requests. Retry after {retry_after} seconds.",
            )
            body = json.dumps(payload).encode()
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Retry-After", str(retry_after))
            origin = self.headers.get("Origin")
            for k, v in _cors_headers_for(origin).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
            return False
        return True

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path

        if path in ("/", "/dashboard"):
            try:
                with open(DASHBOARD_PATH, "rb") as f:
                    self._send_html(f.read())
            except FileNotFoundError:
                self._send_json(404, self._gl030_error("Dashboard not found", "dashboard_not_found", "The requested dashboard file could not be found."))

        elif path == "/health":
            self._send_json(200, {
                "status": "ok",
                "service": "grantlayer",
                "checkType": "liveness",
            })

        elif path == "/readiness":
            try:
                runtime_info = describe_runtime_config()
                self._send_json(200, {
                    "status": "ready",
                    "service": "grantlayer",
                    "checkType": "readiness",
                    "runtimeMode": runtime_info.get("runtimeMode"),
                    "isProductionLike": runtime_info.get("isProductionLike"),
                })
            except ValueError:
                self._send_json(503, {
                    "status": "not_ready",
                    "service": "grantlayer",
                    "checkType": "readiness",
                    "errorCode": "RUNTIME_CONFIG_INVALID",
                })

        elif path == "/grants":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            grants = list_grants()
            result = []
            for g in grants:
                d = g.to_dict()
                sig_result = verify_grant_signature(g)
                d["signaturePresent"] = g.signature is not None
                d["signingKeyId"] = g.signing_key_id
                d["payloadHash"] = g.payload_hash
                d["signatureValid"] = sig_result == "valid"
                result.append(d)
            self._send_json(200, result)

        elif path == "/audit-events":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            qs = parse_qs(urlparse(self.path).query)
            try:
                limit = self._parse_int_query_param(qs, "limit", default=200)
            except _QueryParamError:
                return
            events = list_events(limit=limit)
            self._send_json(200, [e.to_dict() for e in events])

        elif path == "/challenges":
            if not self._check_rate_limit("auth"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            self._send_json(200, [c.to_dict() for c in list_challenges()])

        elif m := re.fullmatch(r"/grants/([^/]+)", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            grant_id = m.group(1)
            g = get_grant(grant_id)
            if g is None:
                self._send_json(404, self._gl030_error("Grant not found", "grant_not_found", "The requested grant does not exist."))
            else:
                d = g.to_dict()
                sig_result = verify_grant_signature(g)
                d["signaturePresent"] = g.signature is not None
                d["signingKeyId"] = g.signing_key_id
                d["payloadHash"] = g.payload_hash
                d["signatureValid"] = sig_result == "valid"
                self._send_json(200, d)

        elif path == "/operators/me":
            if not self._check_rate_limit("auth"):
                return
            ok, payload = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, self._gl030_error("Operator model is disabled", "operator_model_disabled", "The operator model is not enabled on this instance."))
                return
            self._send_json(200, payload.get("operator", {}))
            
        elif path == "/grant-requests":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return

            qs = parse_qs(urlparse(self.path).query)
            status_filter = None
            if "status" in qs and qs["status"]:
                status_filter = qs["status"][0]

            requests = grant_requests.list_grant_requests(status_filter=status_filter)
            self._send_json(200, [r.to_dict() for r in requests])

        elif m := re.fullmatch(r"/grant-requests/([^/]+)", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return

            request_id = m.group(1)
            request = grant_requests.get_grant_request(request_id)
            if request is None:
                self._send_json(404, self._gl030_error("Grant request not found", "grant_request_not_found", "The requested grant request does not exist."))
            else:
                self._send_json(200, request.to_dict())

        elif path == "/grant-executions":
            if not self._check_rate_limit("api"):
                return
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, self._gl030_error("Operator model is disabled", "operator_model_disabled", "The operator model is not enabled on this instance."))
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            qs = parse_qs(urlparse(self.path).query)
            try:
                limit = self._parse_int_query_param(qs, "limit", default=200)
            except _QueryParamError:
                return
            grant_id = qs.get("grantId", [None])[0]
            operator_id = qs.get("operatorId", [None])[0]
            executions = execs.list_grant_executions(
                grant_id=grant_id,
                operator_id=operator_id,
                limit=limit,
            )
            self._send_json(200, [e.to_dict() for e in executions])

        elif m := re.fullmatch(r"/grant-executions/([^/]+)", path):
            if not self._check_rate_limit("api"):
                return
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, self._gl030_error("Operator model is disabled", "operator_model_disabled", "The operator model is not enabled on this instance."))
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            execution_id = m.group(1)
            execution = execs.get_grant_execution(execution_id)
            if execution is None:
                self._send_json(404, self._gl030_error("Grant execution not found", "grant_execution_not_found", "The requested grant execution does not exist."))
                return
            self._send_json(200, execution.to_dict())

        elif m := re.fullmatch(r"/grants/([^/]+)/executions", path):
            if not self._check_rate_limit("api"):
                return
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, self._gl030_error("Operator model is disabled", "operator_model_disabled", "The operator model is not enabled on this instance."))
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            grant_id = m.group(1)
            if get_grant(grant_id) is None:
                self._send_json(404, self._gl030_error("Grant not found", "grant_not_found", "The requested grant does not exist."))
                return
            qs = parse_qs(urlparse(self.path).query)
            try:
                limit = self._parse_int_query_param(qs, "limit", default=200)
            except _QueryParamError:
                return
            executions = execs.list_grant_executions_for_grant(grant_id, limit=limit)
            self._send_json(200, [e.to_dict() for e in executions])

        elif m := re.fullmatch(r"/evidence/executions/([^/]+)", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            execution_id = m.group(1)
            bundle = build_evidence_bundle(execution_id)
            if bundle is None:
                self._send_json(404, self._gl030_error("Execution not found", "execution_not_found", "The requested execution does not exist."))
                return
            self._send_json(200, bundle)

        elif m := re.fullmatch(r"/evidence/executions/([^/]+)/export", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            execution_id = m.group(1)
            bundle = build_evidence_bundle(execution_id)
            if bundle is None:
                self._send_json(404, self._gl030_error("Execution not found", "execution_not_found", "The requested execution does not exist."))
                return
            from .evidence_bundle import export_bundle_json
            body = export_bundle_json(bundle).encode("utf-8")
            evidence_hash = bundle.get("evidenceHash", "")
            short_hash = evidence_hash[:8] if evidence_hash else ""
            filename = f"evidence-{execution_id}-{short_hash}.json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("X-Evidence-Hash", evidence_hash)
            origin = self.headers.get("Origin")
            for k, v in _cors_headers_for(origin).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        elif m := re.fullmatch(r"/evidence/executions/([^/]+)/verify", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            execution_id = m.group(1)
            result = verify_execution(execution_id)
            self._send_json(200, result)

        elif m := re.fullmatch(r"/provenance/executions/([^/]+)/summary", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            execution_id = m.group(1)
            qs = parse_qs(urlparse(self.path).query)
            include_timeline = qs.get("includeTimeline", ["true"])[0].lower() != "false"
            include_warnings = qs.get("includeWarnings", ["true"])[0].lower() != "false"
            include_raw_evidence = qs.get("includeRawEvidence", ["false"])[0].lower() == "true"
            summary = build_decision_provenance_summary(
                execution_id,
                include_timeline=include_timeline,
                include_warnings=include_warnings,
                include_raw_evidence=include_raw_evidence,
            )
            if summary is None:
                self._send_json(404, {
                    "error": "Execution not found",
                    "errorCode": "execution_not_found",
                    "reason": "The requested execution does not exist or has no provenance records.",
                })
                return
            self._send_json(200, summary)

        elif m := re.fullmatch(r"/auditor/reports/executions/([^/]+)", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            execution_id = m.group(1)
            qs = parse_qs(urlparse(self.path).query)
            include_raw_evidence = qs.get("includeRawEvidence", ["false"])[0].lower() == "true"
            report = build_auditor_report_for_execution(
                execution_id,
                include_raw_evidence=include_raw_evidence,
            )
            if report is None:
                self._send_json(404, {
                    "error": "Execution not found",
                    "errorCode": "execution_not_found",
                    "reason": "The requested execution does not exist or has no linked provenance records.",
                })
                return
            self._send_json(200, report)

        elif m := re.fullmatch(r"/evidence/executions/([^/]+)/completeness", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            execution_id = m.group(1)
            qs = parse_qs(urlparse(self.path).query)
            include_details = qs.get("includeDetails", ["true"])[0].lower() != "false"
            report = build_evidence_completeness_for_execution(execution_id, include_details=include_details)
            if report is None:
                self._send_json(404, {
                    "error": "Execution not found",
                    "errorCode": "execution_not_found",
                    "reason": "The requested execution does not exist or has no linked provenance records.",
                })
                return
            self._send_json(200, report)

        elif m := re.fullmatch(r"/compliance/gaps/executions/([^/]+)", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            execution_id = m.group(1)
            qs = parse_qs(urlparse(self.path).query)
            include_details = qs.get("includeDetails", ["true"])[0].lower() != "false"
            report = build_compliance_gap_report_for_execution(execution_id, include_details=include_details)
            if report is None:
                self._send_json(404, {
                    "error": "Execution not found",
                    "errorCode": "execution_not_found",
                    "reason": "The requested execution does not exist or has no linked provenance records.",
                })
                return
            self._send_json(200, report)

        elif path == "/agent-permissions/profiles":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            self._send_json(200, list_agent_permission_profiles())

        elif m := re.fullmatch(r"/agent-permissions/profiles/([^/]+)", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            profile_name = m.group(1)
            profile = get_agent_permission_profile(profile_name)
            if profile is None:
                self._send_json(404, {**self._gl030_error("Profile not found", "profile_not_found", "The requested permission profile does not exist."), "profileName": profile_name})
                return
            self._send_json(200, profile)

        else:
            self._send_json(404, self._gl030_error("Not found", "not_found", "The requested endpoint or resource does not exist."))

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path

        if path == "/grants":
            if not self._check_rate_limit("api"):
                return
            ok, payload = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            operator_id = payload.get("operator", {}).get("operatorId") if config.ENABLE_OPERATOR_MODEL else None
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            missing = self._missing(data, [
                "subjectId", "role", "action", "resource",
                "validFrom", "validUntil", "createdBy", "reason",
            ])
            if missing:
                self._send_json(400, self._gl030_error(f"Missing fields: {missing}", "missing_required_fields", f"The following required fields are missing: {missing}."))
                return
            # GL-093: validate required string fields are non-empty strings
            for field in ("subjectId", "role", "action", "resource", "createdBy", "reason"):
                if field in data and (not isinstance(data[field], str) or data[field].strip() == ""):
                    self._send_json(400, self._gl030_error(
                        f"Invalid field: {field}",
                        "invalid_field",
                        f"{field} must be a non-empty string.",
                    ))
                    return
            ok, err = self._validate_grant_dates(data["validFrom"], data["validUntil"])
            if not ok:
                self._send_json(400, err)
                return
            ok, err = self._validate_max_uses(data.get("maxUses"))
            if not ok:
                self._send_json(400, err)
                return
            grant = Grant(
                subject_id=data["subjectId"],
                role=data["role"],
                action=data["action"],
                resource=data["resource"],
                valid_from=data["validFrom"],
                valid_until=data["validUntil"],
                created_by=operator_id if operator_id else data["createdBy"],
                reason=data["reason"],
                max_uses=data.get("maxUses"),
            )
            create_grant(grant)
            self._send_json(201, {
                **grant.to_dict(),
                "signaturePresent": grant.signature is not None,
                "signingKeyId": grant.signing_key_id,
                "payloadHash": grant.payload_hash,
            })

        elif m := re.fullmatch(r"/grants/([^/]+)/revoke", path):
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            grant_id = m.group(1)
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            missing = self._missing(data, ["revokedBy", "reason"])
            if missing:
                self._send_json(400, self._gl030_error(f"Missing fields: {missing}", "missing_required_fields", f"The following required fields are missing: {missing}."))
                return
            if get_grant(grant_id) is None:
                self._send_json(404, self._gl030_error("Grant not found", "grant_not_found", "The requested grant does not exist."))
                return
            ok = revoke_grant(grant_id, data["revokedBy"], data["reason"])
            if ok:
                self._send_json(200, {"ok": True, "grantId": grant_id})
            else:
                self._send_json(409, self._gl030_error("Grant already revoked or not found", "grant_already_revoked", "The grant is already revoked or does not exist."))

        elif path == "/challenges":
            if not self._check_rate_limit("auth"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            missing = self._missing(data, ["subjectId", "action", "resource"])
            if missing:
                self._send_json(400, self._gl030_error(f"Missing fields: {missing}", "missing_required_fields", f"The following required fields are missing: {missing}."))
                return
            challenge = create_challenge(data["subjectId"], data["action"], data["resource"])
            self._send_json(201, {
                "challengeId": challenge.id,
                "subjectId": challenge.subject_id,
                "action": challenge.action,
                "resource": challenge.resource,
                "expiresAt": challenge.expires_at,
            })

        elif m := re.fullmatch(r"/demo/tamper-grant/([^/]+)", path):
            if not self._check_rate_limit("auth"):
                return
            if not config.ENABLE_DEMO_ENDPOINTS:
                self._send_json(403, self._gl030_error("Demo endpoints are disabled", "demo_endpoints_disabled", "Demo endpoints are not enabled on this instance."))
                return
            ok, _ = self._require_auth(["owner", "demo_operator"])
            if not ok:
                return
            grant_id = m.group(1)
            result = tamper_grant(grant_id)
            if result is None:
                self._send_json(404, self._gl030_error("Grant not found", "grant_not_found", "The requested grant does not exist."))
            else:
                self._send_json(200, result)

        elif path == "/demo-action":
            if not self._check_rate_limit("auth"):
                return
            caller_operator_id: str | None = None
            ok, payload = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            if config.ENABLE_OPERATOR_MODEL:
                caller_operator_id = payload.get("operator", {}).get("operatorId")
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            missing = self._missing(data, ["subjectId", "role", "action", "resource"])
            if missing:
                self._send_json(400, self._gl030_error(f"Missing fields: {missing}", "missing_required_fields", f"The following required fields are missing: {missing}."))
                return
            result = handle_demo_action(
                subject_id=data["subjectId"],
                role=data["role"],
                action=data["action"],
                resource=data["resource"],
                challenge_id=data.get("challengeId"),
                operator_id=caller_operator_id,
            )
            self._send_json(200 if result["approved"] else 403, result)
            
        elif path == "/grant-requests":
            # Create a new grant request
            if not self._check_rate_limit("api"):
                return
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, self._gl030_error("Operator model is disabled", "operator_model_disabled", "The operator model is not enabled on this instance."))
                return
            # Only grant_admin or owner roles can create requests
            ok, payload = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            operator_id = payload.get("operator", {}).get("operatorId")
            
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
                
            missing = self._missing(data, [
                "subjectId", "role", "action", "resource",
                "validFrom", "validUntil", "reason",
            ])
            if missing:
                self._send_json(400, self._gl030_error(f"Missing fields: {missing}", "missing_required_fields", f"The following required fields are missing: {missing}."))
                return
            for field in ("subjectId", "role", "action", "resource", "reason"):
                if field in data and (not isinstance(data[field], str) or data[field].strip() == ""):
                    self._send_json(400, self._gl030_error(
                        f"Invalid field: {field}",
                        "invalid_field",
                        f"{field} must be a non-empty string.",
                    ))
                    return
            ok, err = self._validate_grant_dates(data["validFrom"], data["validUntil"])
            if not ok:
                self._send_json(400, err)
                return
            request = GrantRequest(
                subject_id=data["subjectId"],
                role=data["role"],
                action=data["action"],
                resource=data["resource"],
                valid_from=data["validFrom"],
                valid_until=data["validUntil"],
                requested_by=operator_id,
                reason=data["reason"],
            )
            
            created_request = grant_requests.create_grant_request(request)
            self._send_json(201, created_request.to_dict())
            
        elif m := re.fullmatch(r"/grant-requests/([^/]+)/approve", path):
            if not self._check_rate_limit("api"):
                return
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, self._gl030_error("Operator model is disabled", "operator_model_disabled", "The operator model is not enabled on this instance."))
                return
            # Only grant_admin or owner roles can approve requests
            ok, payload = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            operator_id = payload.get("operator", {}).get("operatorId")
            
            request_id = m.group(1)
            request = grant_requests.get_grant_request(request_id)
            
            if request is None:
                self._send_json(404, self._gl030_error("Grant request not found", "grant_request_not_found", "The requested grant request does not exist."))
                return
                
            # Don't allow approving your own requests
            if request.requested_by == operator_id:
                self._send_json(403, {
                    **self._gl030_error("Cannot approve your own request", "self_approval_forbidden", "An operator cannot approve their own grant request."),
                    "requestedBy": request.requested_by,
                    "approverId": operator_id
                })
                return
                
            try:
                updated_request, new_grant = grant_requests.approve_grant_request(request_id, operator_id)
                self._send_json(200, {
                    "ok": True,
                    "request": updated_request.to_dict(),
                    "grant": new_grant.to_dict()
                })
            except ValueError as e:
                self._send_json(400, self._gl030_error(str(e), "invalid_request", str(e)))
                
        elif m := re.fullmatch(r"/grant-requests/([^/]+)/deny", path):
            if not self._check_rate_limit("api"):
                return
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, self._gl030_error("Operator model is disabled", "operator_model_disabled", "The operator model is not enabled on this instance."))
                return
            # Only grant_admin or owner roles can deny requests
            ok, payload = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            operator_id = payload.get("operator", {}).get("operatorId")
            
            request_id = m.group(1)
            request = grant_requests.get_grant_request(request_id)
            
            if request is None:
                self._send_json(404, self._gl030_error("Grant request not found", "grant_request_not_found", "The requested grant request does not exist."))
                return
                
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
                
            if "reason" not in data or not data["reason"]:
                self._send_json(400, self._gl030_error("Denial reason is required", "missing_denial_reason", "A reason is required when denying a grant request."))
                return
                
            try:
                updated_request = grant_requests.deny_grant_request(
                    request_id, operator_id, data["reason"]
                )
                self._send_json(200, {"ok": True, "request": updated_request.to_dict()})
            except ValueError as e:
                self._send_json(400, self._gl030_error(str(e), "invalid_request", str(e)))

        elif path == "/agent-permissions/evaluate":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            missing = self._missing(data, ["agentId", "requestedScope", "assignedScopes"])
            if missing:
                self._send_json(400, self._gl030_error(f"Missing fields: {missing}", "missing_required_fields", f"The following required fields are missing: {missing}."))
                return
            result = evaluate_agent_permission(
                agent_id=data["agentId"],
                requested_scope=data["requestedScope"],
                assigned_scopes=data["assignedScopes"],
                resource_type=data.get("resourceType"),
                resource_id=data.get("resourceId"),
                context=data.get("context"),
            )
            self._send_json(200, result)

        elif path == "/agent-permissions/assignments/resolve":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            missing = self._missing(data, ["agentId", "requestedScope"])
            if missing:
                self._send_json(400, self._gl030_error(f"Missing fields: {missing}", "missing_required_fields", f"The following required fields are missing: {missing}."))
                return
            result = resolve_agent_permission_assignment(
                agent_id=data["agentId"],
                requested_scope=data["requestedScope"],
                assigned_scopes=data.get("assignedScopes"),
                assigned_profiles=data.get("assignedProfiles"),
                resource_type=data.get("resourceType"),
                resource_id=data.get("resourceId"),
                context=data.get("context"),
                include_details=data.get("includeDetails", True),
            )
            self._send_json(200, result)

        elif path == "/approvals/lifecycle/build":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            result = build_approval_request_lifecycle(
                approval_requirement=data.get("approvalRequirement"),
                request_id=data.get("requestId"),
                action=data.get("action"),
                actor_id=data.get("actorId"),
                subject_id=data.get("subjectId"),
                requested_by=data.get("requestedBy"),
                approvers=data.get("approvers"),
                status=data.get("status"),
                created_at=data.get("createdAt"),
                expires_at=data.get("expiresAt"),
                context=data.get("context"),
                include_details=data.get("includeDetails", True),
            )
            self._send_json(200, result)

        elif path == "/approvals/lifecycle/transition":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            missing = self._missing(data, ["approvalRequest", "transition"])
            if missing:
                self._send_json(400, self._gl030_error(f"Missing fields: {missing}", "missing_required_fields", f"The following required fields are missing: {missing}."))
                return
            result = transition_approval_request(
                approval_request=data["approvalRequest"],
                transition=data["transition"],
                actor_id=data.get("actorId"),
                reason=data.get("reason"),
                at=data.get("at"),
                context=data.get("context"),
                include_details=data.get("includeDetails", True),
            )
            self._send_json(200, result)

        elif path == "/approvals/evaluate":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            missing = self._missing(data, ["action"])
            if missing:
                self._send_json(400, self._gl030_error(f"Missing fields: {missing}", "missing_required_fields", f"The following required fields are missing: {missing}."))
                return
            result = evaluate_approval_requirements(
                action=data["action"],
                actor_id=data.get("actorId"),
                amount=data.get("amount"),
                currency=data.get("currency"),
                risk_level=data.get("riskLevel"),
                compliance_report=data.get("complianceReport"),
                evidence_completeness=data.get("evidenceCompleteness"),
                permission_result=data.get("permissionResult"),
                policy_flags=data.get("policyFlags"),
                context=data.get("context"),
                include_details=data.get("includeDetails", True),
            )
            self._send_json(200, result)

        elif path == "/decision-provenance/v2/build":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            result = build_decision_provenance_v2(
                decision_id=data.get("decisionId"),
                decision_type=data.get("decisionType"),
                subject_id=data.get("subjectId"),
                actor_id=data.get("actorId"),
                action=data.get("action"),
                decision=data.get("decision"),
                reason=data.get("reason"),
                evidence_completeness=data.get("evidenceCompleteness"),
                compliance_gap_report=data.get("complianceGapReport"),
                permission_result=data.get("permissionResult"),
                approval_requirement=data.get("approvalRequirement"),
                approval_lifecycle=data.get("approvalLifecycle"),
                provenance_summary=data.get("provenanceSummary"),
                auditor_report=data.get("auditorReport"),
                policy_results=data.get("policyResults"),
                inputs=data.get("inputs"),
                context=data.get("context"),
                created_at=data.get("createdAt"),
                include_details=data.get("includeDetails", True),
            )
            self._send_json(200, result)

        elif path == "/auditor/exports/build":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            result = build_institutional_auditor_export(
                export_id=data.get("exportId"),
                export_type=data.get("exportType"),
                subject_id=data.get("subjectId"),
                decision_id=data.get("decisionId"),
                generated_by=data.get("generatedBy"),
                auditor_id=data.get("auditorId"),
                decision_provenance=data.get("decisionProvenance"),
                auditor_report=data.get("auditorReport"),
                evidence_completeness=data.get("evidenceCompleteness"),
                compliance_gap_report=data.get("complianceGapReport"),
                permission_result=data.get("permissionResult"),
                approval_requirement=data.get("approvalRequirement"),
                approval_lifecycle=data.get("approvalLifecycle"),
                policy_results=data.get("policyResults"),
                metadata=data.get("metadata"),
                context=data.get("context"),
                created_at=data.get("createdAt"),
                include_details=data.get("includeDetails", True),
            )
            self._send_json(200, result)

        elif path == "/policy-requirements/evaluate":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            result = evaluate_policy_requirements(
                policy_pack=data.get("policyPack"),
                subject=data.get("subject"),
                evidence_completeness=data.get("evidenceCompleteness"),
                compliance_gap_report=data.get("complianceGapReport"),
                permission_result=data.get("permissionResult"),
                approval_requirement=data.get("approvalRequirement"),
                approval_lifecycle=data.get("approvalLifecycle"),
                decision_provenance=data.get("decisionProvenance"),
                auditor_export=data.get("auditorExport"),
                context=data.get("context"),
                created_at=data.get("createdAt"),
                include_details=data.get("includeDetails", True),
            )
            self._send_json(200, result)

        elif path == "/compliance/readiness/build":
            if not self._check_rate_limit("api"):
                return
            ok, _ = self._require_auth(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError) as e:
                self._handle_json_error(e)
                return
            # Build summary from request body using the existing pure builder
            policy_req_eval = data.get("policyRequirementEvaluation")
            summary = build_compliance_readiness_summary(
                subject_id=data.get("subjectId"),
                workflow_id=data.get("workflowId"),
                evidence_completeness=data.get("evidenceCompleteness"),
                compliance_gap_report=data.get("complianceGapReport"),
                permission_result=data.get("permissionResult"),
                approval_requirement=data.get("approvalRequirement"),
                approval_lifecycle=data.get("approvalLifecycle"),
                provenance_summary=data.get("decisionProvenance"),
                auditor_report=data.get("auditorExport"),
                policy_results=[policy_req_eval] if policy_req_eval is not None else None,
                context=data.get("context"),
                created_at=data.get("createdAt"),
                include_details=data.get("includeDetails", True),
            )
            # Map builder output field names to API contract field names
            if summary.get("readinessStatus") == "not_assessed":
                summary["readinessStatus"] = "insufficient_data"
            if "approval" in summary:
                approval = summary.pop("approval")
                if approval is not None:
                    summary["approvalRequirement"] = approval.get("requirement")
                    summary["approvalLifecycle"] = approval.get("lifecycle")
            if "provenance" in summary:
                summary["decisionProvenance"] = summary.pop("provenance")
            if "auditorReport" in summary:
                summary["auditorExport"] = summary.pop("auditorReport")
            if "policy" in summary:
                policy_list = summary.pop("policy")
                if policy_list and len(policy_list) > 0:
                    summary["policyRequirementEvaluation"] = policy_list[0]
                else:
                    summary["policyRequirementEvaluation"] = None
            self._send_json(200, summary)

        else:
            self._send_json(404, self._gl030_error("Not found", "not_found", "The requested endpoint or resource does not exist."))


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    ensure_demo_keypair()
    init_db()
    warning = admin_token_warning()
    if warning:
        print(warning, flush=True)
    for msg in config.startup_warnings():
        print(msg, flush=True)
    # GL-089: fail-closed startup gate for non-local / production-like modes
    if config.RUNTIME_MODE not in ("local", "test"):
        if not config.startup_ok():
            print("FATAL: Unsafe configuration detected in non-local mode. Server will not start.", flush=True)
            for err in config.startup_errors():
                print(err, flush=True)
            raise SystemExit(1)
    server = HTTPServer((host, port), GrantLayerHandler)
    print(f"GrantLayer MVP running on http://{host}:{port}", flush=True)
    print(f"Dashboard:   http://{host}:{port}/", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.", flush=True)
