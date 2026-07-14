"""RED-before-GREEN tests for scripts/verify-anchor.py — the keyless offline verifier.

These run the script as a SUBPROCESS (exactly as a third party would) against:
  * a genuine in-test NDJSON export fixture (built with the real export fold so it
    matches production byte-for-byte), and
  * a LOCAL HTTP stub standing in for Koios (no network in the test suite).

The stub is a real localhost HTTP server, so the script exercises its actual
urllib code path — nothing in the script is mocked or given a test-only branch.
The verifier proves "this export has not been rewritten since the anchor time";
these tests pin the VERIFIED path plus every failure mode (tamper / truncate /
reorder / tx-not-found / count mismatch) with a precise exit reason.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

# The export-side fold IS the reference for building a genuine fixture; the SCRIPT
# under test deliberately reimplements it with zero dependency on our code.
from backend.src.api.routers.audit_compliance import _iter_chain, _sign_manifest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify-anchor.py"
ANCHOR_LABEL = "923350"


# --------------------------------------------------------------------------- #
# Fixture: a genuine export (data lines + HMAC manifest footer) and its head.  #
# --------------------------------------------------------------------------- #
def _build_export() -> tuple[list[str], str, int]:
    """Return (ndjson_lines, final_hash, entry_count) for a real 3-entry export."""
    events = [
        {
            "subject_id": "op-a",
            "action": "approve_grant_request",
            "resource": "grant_request/aaa",
            "approved": True,
            "workspace_id": "default",
            "seq": 1,
        },
        {
            "subject_id": "op-b",
            "action": "approve_grant_request",
            "resource": "grant_request/bbb",
            "approved": True,
            "workspace_id": "default",
            "seq": 2,
        },
        {
            "subject_id": "export-user",
            "action": "export_audit_csv",
            "resource": "audit_events",
            "approved": True,
            "workspace_id": "default",
            "seq": 3,
        },
    ]
    lines: list[str] = []
    all_hashes: list[str] = []
    final = "0" * 64
    for event, prev_hash, entry_hash in _iter_chain(events):
        rec = {**event, "_chain_hash": entry_hash, "_prev_hash": prev_hash}
        all_hashes.append(entry_hash)
        final = entry_hash
        lines.append(json.dumps(rec, ensure_ascii=True))
    manifest = {
        "_type": "manifest",
        "_entry_count": len(all_hashes),
        "_final_hash": final,
        "_hmac_signature": _sign_manifest(all_hashes),
    }
    lines.append(json.dumps(manifest, ensure_ascii=True))
    return lines, final, len(all_hashes)


# --------------------------------------------------------------------------- #
# Local Koios stub — a real HTTP server returning a canned {h,s,t} payload.    #
# --------------------------------------------------------------------------- #
class _KoiosStub:
    """Context manager: serves POST /tx_metadata and GET /tx_by_metalabel."""

    def __init__(self, tx_id: str, payload: dict | None):
        self._tx_id = tx_id
        self._payload = payload  # None => tx not found (empty result)
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address
        return f"http://127.0.0.1:{port}/api/v1"

    def __enter__(self) -> "_KoiosStub":
        tx_id = self._tx_id
        payload = self._payload

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def _send(self, obj):
                body = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("content-length", 0))
                self.rfile.read(length)
                if not self.path.startswith("/api/v1/tx_metadata"):
                    self._send([])
                    return
                if payload is None:
                    self._send([])  # tx not found
                    return
                self._send(
                    [{"tx_hash": tx_id, "metadata": {ANCHOR_LABEL: payload}}]
                )

            def do_GET(self):
                if self.path.startswith("/api/v1/tx_by_metalabel"):
                    self._send([{"tx_hash": tx_id}] if payload is not None else [])
                else:
                    self._send([])

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


def _run(ndjson: Path, tx_id: str, base_url: str, *extra: str):
    env = {"KOIOS_BASE_URL": base_url, "PATH": "/usr/bin:/bin"}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--ndjson", str(ndjson), "--tx-id", tx_id, *extra],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return proc


@pytest.fixture()
def export(tmp_path):
    lines, final, count = _build_export()
    f = tmp_path / "export.ndjson"
    f.write_text("\n".join(lines) + "\n")
    return f, final, count, lines


TX = "f61d97f76413c32f794a24dfb7ea7a78866e50149348d9a7f9a674fc6923390c"


def test_verified_when_export_matches_chain(export):
    f, final, count, _ = export
    payload = {"h": final, "s": count, "t": "2026-07-14T11:18:01.574059Z"}
    with _KoiosStub(TX, payload) as stub:
        proc = _run(f, TX, stub.base_url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFIED" in proc.stdout


def test_tampered_line_fails_and_names_line(export):
    f, final, count, lines = export
    # Edit a value in the SECOND data line without recomputing its chain hash.
    obj = json.loads(lines[1])
    obj["approved"] = False
    lines[1] = json.dumps(obj, ensure_ascii=True)
    f.write_text("\n".join(lines) + "\n")
    payload = {"h": final, "s": count, "t": "2026-07-14T11:18:01Z"}
    with _KoiosStub(TX, payload) as stub:
        proc = _run(f, TX, stub.base_url)
    assert proc.returncode == 1
    out = proc.stdout + proc.stderr
    assert "line 2" in out.lower() or "line: 2" in out.lower()


def test_truncated_last_line_fails_count(export):
    f, final, count, lines = export
    # Drop the last DATA line (index -2, keeping the manifest footer at -1).
    del lines[-2]
    f.write_text("\n".join(lines) + "\n")
    payload = {"h": final, "s": count, "t": "2026-07-14T11:18:01Z"}
    with _KoiosStub(TX, payload) as stub:
        proc = _run(f, TX, stub.base_url)
    assert proc.returncode == 1
    assert "count" in (proc.stdout + proc.stderr).lower()


def test_reordered_lines_fail(export):
    f, final, count, lines = export
    lines[0], lines[1] = lines[1], lines[0]
    f.write_text("\n".join(lines) + "\n")
    payload = {"h": final, "s": count, "t": "2026-07-14T11:18:01Z"}
    with _KoiosStub(TX, payload) as stub:
        proc = _run(f, TX, stub.base_url)
    assert proc.returncode == 1


def test_tx_not_found_fails(export):
    f, final, count, _ = export
    with _KoiosStub(TX, None) as stub:  # empty Koios result
        proc = _run(f, TX, stub.base_url)
    assert proc.returncode == 1
    assert "not found" in (proc.stdout + proc.stderr).lower()


def test_head_mismatch_fails(export):
    f, _final, count, _ = export
    # Chain attests a DIFFERENT head than the export recomputes to.
    payload = {"h": "a" * 64, "s": count, "t": "2026-07-14T11:18:01Z"}
    with _KoiosStub(TX, payload) as stub:
        proc = _run(f, TX, stub.base_url)
    assert proc.returncode == 1
    out = (proc.stdout + proc.stderr).lower()
    assert "head" in out or "mismatch" in out


def test_hmac_key_ok(export):
    f, final, count, _ = export
    payload = {"h": final, "s": count, "t": "2026-07-14T11:18:01Z"}
    # _DEFAULT_HMAC_KEY from audit_compliance signed the fixture manifest.
    with _KoiosStub(TX, payload) as stub:
        proc = _run(
            f, TX, stub.base_url, "--hmac-key", "grantlayer-audit-hmac-default-key"
        )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFIED" in proc.stdout


def test_hmac_key_wrong_fails(export):
    f, final, count, _ = export
    payload = {"h": final, "s": count, "t": "2026-07-14T11:18:01Z"}
    with _KoiosStub(TX, payload) as stub:
        proc = _run(f, TX, stub.base_url, "--hmac-key", "the-wrong-key")
    assert proc.returncode == 1
    assert "hmac" in (proc.stdout + proc.stderr).lower()
