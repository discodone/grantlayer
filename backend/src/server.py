"""GrantLayer MVP — HTTP server."""

import json
import re
import datetime
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from .db import init_db
from .models import Grant
from .grants import list_grants, create_grant, revoke_grant, get_grant, tamper_grant
from .audit_log import list_events
from .demo_action import handle_demo_action
from .challenges import create_challenge, list_challenges
from .crypto_signing import ensure_demo_keypair, verify_grant_signature

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

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path

        if path in ("/", "/dashboard"):
            try:
                with open(DASHBOARD_PATH, "rb") as f:
                    self._send_html(f.read())
            except FileNotFoundError:
                self._send_json(404, {"error": "Dashboard not found"})

        elif path == "/health":
            self._send_json(200, {
                "ok": True,
                "service": "grantlayer-mvp",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            })

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

        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path

        if path == "/grants":
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
                created_by=data["createdBy"],
                reason=data["reason"],
            )
            create_grant(grant)
            self._send_json(201, {
                **grant.to_dict(),
                "signaturePresent": grant.signature is not None,
                "signingKeyId": grant.signing_key_id,
                "payloadHash": grant.payload_hash,
            })

        elif m := re.fullmatch(r"/grants/([^/]+)/revoke", path):
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
            result = handle_demo_action(
                subject_id=data["subjectId"],
                role=data["role"],
                action=data["action"],
                resource=data["resource"],
                challenge_id=data.get("challengeId"),
            )
            self._send_json(200 if result["approved"] else 403, result)

        else:
            self._send_json(404, {"error": "Not found"})


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    ensure_demo_keypair()
    init_db()
    server = HTTPServer((host, port), GrantLayerHandler)
    print(f"GrantLayer MVP running on http://{host}:{port}", flush=True)
    print(f"Dashboard:   http://{host}:{port}/", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.", flush=True)
