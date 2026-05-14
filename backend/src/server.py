"""GrantLayer MVP — HTTP server."""

import json
import re
import datetime
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from .db import init_db
from .models import Grant, GrantRequest
from .grants import list_grants, create_grant, revoke_grant, get_grant, tamper_grant
from .audit_log import list_events
from .demo_action import handle_demo_action
from .challenges import create_challenge, list_challenges
from .auth import check_auth, check_admin_token, admin_token_warning, admin_token_is_configured
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
DASHBOARD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "dashboard", "index.html",
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class GrantLayerHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # noqa: N802
        print(f"[{self.log_date_time_string()}] {fmt % args}", flush=True)

    def _send_json(self, status: int, data) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in CORS_HEADERS.items():
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
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _missing(self, data: dict, fields: list) -> list:
        return [f for f in fields if not data.get(f)]

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    def _require_admin(self) -> bool:
        ok, status, payload = check_admin_token(self.headers.get("Authorization"))
        if not ok:
            self._send_json(status, payload)
            return False
        return True

    def _require_operator(self, roles: list[str]) -> tuple[bool, dict]:
        ok, status, payload = check_auth(self.headers.get("Authorization"), required_roles=roles)
        if not ok:
            self._send_json(status, payload)
            return False, {}
        return True, payload

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path

        if path in ("/", "/dashboard"):
            try:
                with open(DASHBOARD_PATH, "rb") as f:
                    self._send_html(f.read())
            except FileNotFoundError:
                self._send_json(404, {"error": "Dashboard not found"})

        elif path == "/health":
            health_payload = {
                "ok": True,
                "service": "grantlayer-mvp",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "dbConfigured": bool(config.GRANTLAYER_DB or config.GRANTLAYER_DATABASE_URL),
                "adminTokenConfigured": admin_token_is_configured(),
                "requireAdminToken": config.REQUIRE_ADMIN_TOKEN,
                "requireChallenge": config.REQUIRE_CHALLENGE,
                "demoEndpointsEnabled": config.ENABLE_DEMO_ENDPOINTS,
                "operatorModelEnabled": config.ENABLE_OPERATOR_MODEL,
                "operatorsConfigured": False,
            }
            # GL-032: additive readiness fields
            from .db import get_db_health
            health_payload.update(get_db_health())
            self._send_json(200, health_payload)

        elif path == "/grants":
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
            qs = parse_qs(urlparse(self.path).query)
            limit = int(qs.get("limit", ["200"])[0])
            events = list_events(limit=limit)
            self._send_json(200, [e.to_dict() for e in events])

        elif path == "/challenges":
            self._send_json(200, [c.to_dict() for c in list_challenges()])

        elif m := re.fullmatch(r"/grants/([^/]+)", path):
            grant_id = m.group(1)
            g = get_grant(grant_id)
            if g is None:
                self._send_json(404, {"error": "Grant not found"})
            else:
                d = g.to_dict()
                sig_result = verify_grant_signature(g)
                d["signaturePresent"] = g.signature is not None
                d["signingKeyId"] = g.signing_key_id
                d["payloadHash"] = g.payload_hash
                d["signatureValid"] = sig_result == "valid"
                self._send_json(200, d)

        elif path == "/operators/me":
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, {"error": "operator_model_disabled"})
                return
            op = ops.authenticate_operator(self.headers.get("Authorization"))
            if op is None:
                self._send_json(401, {"error": "operator_auth_required"})
                return
            self._send_json(200, op.to_dict())
            
        elif path == "/grant-requests":
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, {"error": "operator_model_disabled"})
                return
                
            qs = parse_qs(urlparse(self.path).query)
            status_filter = None
            if "status" in qs and qs["status"]:
                status_filter = qs["status"][0]
                
            requests = grant_requests.list_grant_requests(status_filter=status_filter)
            self._send_json(200, [r.to_dict() for r in requests])
            
        elif m := re.fullmatch(r"/grant-requests/([^/]+)", path):
            request_id = m.group(1)
            request = grant_requests.get_grant_request(request_id)
            if request is None:
                self._send_json(404, {"error": "Grant request not found"})
            else:
                self._send_json(200, request.to_dict())

        elif path == "/grant-executions":
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, {"error": "operator_model_disabled"})
                return
            ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            qs = parse_qs(urlparse(self.path).query)
            limit = int(qs.get("limit", ["200"])[0])
            grant_id = qs.get("grantId", [None])[0]
            operator_id = qs.get("operatorId", [None])[0]
            executions = execs.list_grant_executions(
                grant_id=grant_id,
                operator_id=operator_id,
                limit=limit,
            )
            self._send_json(200, [e.to_dict() for e in executions])

        elif m := re.fullmatch(r"/grant-executions/([^/]+)", path):
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, {"error": "operator_model_disabled"})
                return
            ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            execution_id = m.group(1)
            execution = execs.get_grant_execution(execution_id)
            if execution is None:
                self._send_json(404, {"error": "Grant execution not found", "errorCode": "grant_execution_not_found", "reason": "The requested grant execution does not exist."})
                return
            self._send_json(200, execution.to_dict())

        elif m := re.fullmatch(r"/grants/([^/]+)/executions", path):
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, {"error": "operator_model_disabled"})
                return
            ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
            if not ok:
                return
            grant_id = m.group(1)
            if get_grant(grant_id) is None:
                self._send_json(404, {"error": "Grant not found"})
                return
            qs = parse_qs(urlparse(self.path).query)
            limit = int(qs.get("limit", ["200"])[0])
            executions = execs.list_grant_executions_for_grant(grant_id, limit=limit)
            self._send_json(200, [e.to_dict() for e in executions])

        elif m := re.fullmatch(r"/evidence/executions/([^/]+)", path):
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
                if not ok:
                    return
            else:
                if not self._require_admin():
                    return
            execution_id = m.group(1)
            bundle = build_evidence_bundle(execution_id)
            if bundle is None:
                self._send_json(404, {"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist."})
                return
            self._send_json(200, bundle)

        elif m := re.fullmatch(r"/evidence/executions/([^/]+)/export", path):
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
                if not ok:
                    return
            else:
                if not self._require_admin():
                    return
            execution_id = m.group(1)
            bundle = build_evidence_bundle(execution_id)
            if bundle is None:
                self._send_json(404, {"error": "Execution not found", "errorCode": "execution_not_found", "reason": "The requested execution does not exist."})
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
            for k, v in CORS_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        elif m := re.fullmatch(r"/evidence/executions/([^/]+)/verify", path):
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
                if not ok:
                    return
            else:
                if not self._require_admin():
                    return
            execution_id = m.group(1)
            result = verify_execution(execution_id)
            self._send_json(200, result)

        elif m := re.fullmatch(r"/provenance/executions/([^/]+)/summary", path):
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
                if not ok:
                    return
            else:
                if not self._require_admin():
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
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
                if not ok:
                    return
            else:
                if not self._require_admin():
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
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
                if not ok:
                    return
            else:
                if not self._require_admin():
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
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
                if not ok:
                    return
            else:
                if not self._require_admin():
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

        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path

        if path == "/grants":
            if config.ENABLE_OPERATOR_MODEL:
                ok, payload = self._require_operator(["owner", "grant_admin"])
                if not ok:
                    return
                operator_id = payload["operator"]["operatorId"]
            else:
                if not self._require_admin():
                    return
                operator_id = None
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError):
                self._send_json(400, {"error": "Invalid JSON"})
                return
            missing = self._missing(data, [
                "subjectId", "role", "action", "resource",
                "validFrom", "validUntil", "createdBy", "reason",
            ])
            if missing:
                self._send_json(400, {"error": f"Missing fields: {missing}"})
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
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "grant_admin"])
                if not ok:
                    return
            else:
                if not self._require_admin():
                    return
            grant_id = m.group(1)
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError):
                self._send_json(400, {"error": "Invalid JSON"})
                return
            missing = self._missing(data, ["revokedBy", "reason"])
            if missing:
                self._send_json(400, {"error": f"Missing fields: {missing}"})
                return
            if get_grant(grant_id) is None:
                self._send_json(404, {"error": "Grant not found"})
                return
            ok = revoke_grant(grant_id, data["revokedBy"], data["reason"])
            if ok:
                self._send_json(200, {"ok": True, "grantId": grant_id})
            else:
                self._send_json(409, {"error": "Grant already revoked or not found"})

        elif path == "/challenges":
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError):
                self._send_json(400, {"error": "Invalid JSON"})
                return
            missing = self._missing(data, ["subjectId", "action", "resource"])
            if missing:
                self._send_json(400, {"error": f"Missing fields: {missing}"})
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
            if not config.ENABLE_DEMO_ENDPOINTS:
                self._send_json(403, {"error": "demo_endpoints_disabled"})
                return
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "demo_operator"])
                if not ok:
                    return
            else:
                if not self._require_admin():
                    return
            grant_id = m.group(1)
            result = tamper_grant(grant_id)
            if result is None:
                self._send_json(404, {"error": "Grant not found"})
            else:
                self._send_json(200, result)

        elif path == "/demo-action":
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError):
                self._send_json(400, {"error": "Invalid JSON"})
                return
            missing = self._missing(data, ["subjectId", "role", "action", "resource"])
            if missing:
                self._send_json(400, {"error": f"Missing fields: {missing}"})
                return
            caller_operator_id: str | None = None
            if config.ENABLE_OPERATOR_MODEL:
                op = ops.authenticate_operator(self.headers.get("Authorization"))
                if op is not None:
                    caller_operator_id = op.operator_id
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
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, {"error": "operator_model_disabled"})
                return
                
            # Only grant_admin or owner roles can create requests
            ok, payload = self._require_operator(["owner", "grant_admin"])
            if not ok:
                return
            operator_id = payload["operator"]["operatorId"]
            
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError):
                self._send_json(400, {"error": "Invalid JSON"})
                return
                
            missing = self._missing(data, [
                "subjectId", "role", "action", "resource",
                "validFrom", "validUntil", "reason",
            ])
            if missing:
                self._send_json(400, {"error": f"Missing fields: {missing}"})
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
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, {"error": "operator_model_disabled"})
                return
                
            # Only grant_admin or owner roles can approve requests
            ok, payload = self._require_operator(["owner", "grant_admin"])
            if not ok:
                return
            operator_id = payload["operator"]["operatorId"]
            
            request_id = m.group(1)
            request = grant_requests.get_grant_request(request_id)
            
            if request is None:
                self._send_json(404, {"error": "Grant request not found"})
                return
                
            # Don't allow approving your own requests
            if request.requested_by == operator_id:
                self._send_json(403, {
                    "error": "Cannot approve your own request",
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
                self._send_json(400, {"error": str(e)})
                
        elif m := re.fullmatch(r"/grant-requests/([^/]+)/deny", path):
            if not config.ENABLE_OPERATOR_MODEL:
                self._send_json(404, {"error": "operator_model_disabled"})
                return
                
            # Only grant_admin or owner roles can deny requests
            ok, payload = self._require_operator(["owner", "grant_admin"])
            if not ok:
                return
            operator_id = payload["operator"]["operatorId"]
            
            request_id = m.group(1)
            request = grant_requests.get_grant_request(request_id)
            
            if request is None:
                self._send_json(404, {"error": "Grant request not found"})
                return
                
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError):
                self._send_json(400, {"error": "Invalid JSON"})
                return
                
            if "reason" not in data or not data["reason"]:
                self._send_json(400, {"error": "Denial reason is required"})
                return
                
            try:
                updated_request = grant_requests.deny_grant_request(
                    request_id, operator_id, data["reason"]
                )
                self._send_json(200, {"ok": True, "request": updated_request.to_dict()})
            except ValueError as e:
                self._send_json(400, {"error": str(e)})

        elif path == "/agent-permissions/evaluate":
            if config.ENABLE_OPERATOR_MODEL:
                ok, _ = self._require_operator(["owner", "grant_admin", "auditor"])
                if not ok:
                    return
            else:
                if not self._require_admin():
                    return
            try:
                data = self._read_json()
            except (json.JSONDecodeError, ValueError):
                self._send_json(400, {"error": "Invalid JSON"})
                return
            missing = self._missing(data, ["agentId", "requestedScope", "assignedScopes"])
            if missing:
                self._send_json(400, {"error": f"Missing fields: {missing}"})
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

        else:
            self._send_json(404, {"error": "Not found"})


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    ensure_demo_keypair()
    init_db()
    warning = admin_token_warning()
    if warning:
        print(warning, flush=True)
    for msg in config.startup_warnings():
        print(msg, flush=True)
    server = HTTPServer((host, port), GrantLayerHandler)
    print(f"GrantLayer MVP running on http://{host}:{port}", flush=True)
    print(f"Dashboard:   http://{host}:{port}/", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.", flush=True)
