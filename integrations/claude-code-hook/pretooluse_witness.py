#!/usr/bin/env python3
"""Claude Code PreToolUse hook: witness every tool call on the GrantLayer chain.

LOG-ONLY BY DESIGN — THIS HOOK NEVER BLOCKS A TOOL CALL. It exercises the
same /v1/exercise decision endpoint the product hardens, records the decision
(approved / denied / unavailable) in a local log, and then ALWAYS exits 0 so
the tool call proceeds regardless of the outcome, an API error, a timeout, or
a rate limit. Enforcement is a separate, future decision; nothing in this
file may ever `sys.exit(2)` (the Claude Code "block" exit code) or emit a
permissionDecision.

WITNESS CONTENT: the tool NAME and the decision — nothing else. Tool
ARGUMENTS are never logged, never transmitted, never hashed: arguments can
contain file paths, file contents, and secrets, and on-chain anchoring makes
any leak permanent. The stdin JSON is parsed only to read `tool_name`; the
`tool_input` field is deliberately never touched.

AVAILABILITY: every HTTP call has a hard 1-second timeout (two calls, so the
worst case adds ~2s once, only when the API is down). HTTP 429 (the free
tier allows 100 requests/min per workspace and a busy Claude Code session —
at 2 requests per tool call — can exceed it) is logged as `rate_limited`,
which is an UNAVAILABILITY of the witness, never a denial of the tool call.

Configuration (env, all optional):
  GRANTLAYER_HOOK_API       default http://127.0.0.1:8765
  GRANTLAYER_HOOK_KEY_FILE  default ~/grantlayer-ops/claude-hook-agent.key.json
                            (a subject-bound API key: gl-393 refuses unbound
                            keys on /v1/exercise — see README for the gated
                            key-creation step; the key does NOT exist yet)
  GRANTLAYER_HOOK_LOG       default ~/grantlayer-ops/claude-hook-decisions.log
  GRANTLAYER_HOOK_SUBJECT   default claude-code-agent (must equal the key's
                            bound subjectId or /v1/exercise answers 400)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = os.environ.get("GRANTLAYER_HOOK_API", "http://127.0.0.1:8765")
KEY_FILE = os.environ.get(
    "GRANTLAYER_HOOK_KEY_FILE",
    os.path.expanduser("~/grantlayer-ops/claude-hook-agent.key.json"),
)
LOG_FILE = os.environ.get(
    "GRANTLAYER_HOOK_LOG",
    os.path.expanduser("~/grantlayer-ops/claude-hook-decisions.log"),
)
SUBJECT = os.environ.get("GRANTLAYER_HOOK_SUBJECT", "claude-code-agent")
RESOURCE = "claude-code/tool"
TIMEOUT_S = 1.0  # per request; a slow or dead API must not stall the session


def _log(outcome: str, tool_name: str, detail: str = "") -> None:
    line = (
        f"{datetime.now(timezone.utc).isoformat()} tool={tool_name} "
        f"outcome={outcome}{' ' + detail if detail else ''}\n"
    )
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except OSError:
        pass  # a broken log file must not break the session either


def _post(path: str, token: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        API + path,
        method="POST",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except (ValueError, OSError):
            return e.code, {}


def main() -> None:
    # Read ONLY tool_name from the event; tool_input is never inspected.
    try:
        event = json.load(sys.stdin)
        tool_name = str(event.get("tool_name", "unknown"))[:128]
    except (ValueError, OSError):
        _log("unavailable", "unknown", "reason=unparseable_event")
        return

    try:
        with open(KEY_FILE) as f:
            key = json.load(f)["key"]
    except (OSError, ValueError, KeyError):
        _log("unavailable", tool_name, "reason=no_key_file")
        return

    tup = {
        "subjectId": SUBJECT,
        "role": "agent",
        "action": tool_name,
        "resource": RESOURCE,
    }
    try:
        st, ch = _post(
            "/v1/challenges", key,
            {k: tup[k] for k in ("subjectId", "action", "resource")},
        )
        if st == 429:
            _log("unavailable", tool_name, "reason=rate_limited")
            return
        if st != 201 or "challengeId" not in ch:
            _log("unavailable", tool_name, f"reason=challenge_http_{st}")
            return
        st, resp = _post(
            "/v1/exercise", key, {**tup, "challengeId": ch["challengeId"]},
        )
        if st == 200 and resp.get("approved") is True:
            _log("approved", tool_name, f"audit_event={resp.get('auditEventId')}")
        elif st == 429:
            _log("unavailable", tool_name, "reason=rate_limited")
        elif st == 200 or st == 403:
            # A real answer from the decision endpoint: witnessed as denied,
            # tool call proceeds anyway (log-only).
            _log("denied", tool_name, f"http={st} reason={resp.get('reason')}")
        else:
            # 400 subject mismatch / unbound key / anything else: the witness
            # is misconfigured or unavailable — never counted as a denial.
            _log("unavailable", tool_name, f"reason=http_{st}")
    except Exception as exc:  # timeouts, connection refused, anything
        _log("unavailable", tool_name, f"reason={type(exc).__name__}")


if __name__ == "__main__":
    try:
        main()
    finally:
        # LOG-ONLY GUARANTEE: unconditional success exit — never exit 2,
        # never block, no stdout (stdout could be interpreted by the hook
        # runner; silence means "no opinion, proceed").
        sys.exit(0)
