"""
GL-148: LangGraph/LangChain Integration Example
developer-preview — local use only — standard library only

Shows how GrantLayer can act as a policy/evidence/audit boundary inside
an AI-agent workflow. No LangGraph or LangChain installation required.

LangGraph adaptation:
  Each function below maps to a StateGraph node.  Wrap them in:
      builder.add_node("preflight", preflight_grantlayer)
      builder.add_node("context",   prepare_grant_decision_context)

LangChain adaptation:
  Expose run_local_workflow as a Tool:
      Tool(name="grantlayer_check", func=run_local_workflow, ...)

No external LLM calls.  No API keys.  Default behavior is dry-run.

Safety caveats:
  - developer-preview only; not production-ready
  - tenant isolation not implemented
  - no real secrets, no real customer data
  - token is never logged or returned in output
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Path injection — locate sdk/python relative to this file's repo root
# examples/langgraph_langchain/ → ../../ → repo root → sdk/python
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SDK_PATH = os.path.join(_REPO_ROOT, "sdk", "python")
if _SDK_PATH not in sys.path:
    sys.path.insert(0, _SDK_PATH)

# Import GL-147 SDK (standard library only, no network at import time)
from grantlayer_client import (  # noqa: E402
    GrantLayerClient,
    GrantLayerClientError,
    GrantLayerHTTPError,
    GrantLayerJSONError,
)


# ---------------------------------------------------------------------------
# Sample agent state
# ---------------------------------------------------------------------------

def build_sample_agent_state() -> Dict[str, Any]:
    """Return a minimal agent state dict representing a pending grant decision.

    In a real LangGraph workflow this dict is the TypedDict state threaded
    through every node.  Here it is a plain dict so no langgraph import is
    required.
    """
    return {
        "subjectId": "agent-demo-user",
        "role": "analyst",
        "action": "read",
        "resource": "reports/q1-summary",
        "validFrom": "2026-01-01T00:00:00Z",
        "validUntil": "2026-12-31T23:59:59Z",
        "createdBy": "gl148-example-agent",
        "reason": "GL-148 developer-preview dry-run — not a real grant request",
    }


# ---------------------------------------------------------------------------
# Preflight node
# ---------------------------------------------------------------------------

def preflight_grantlayer(
    state: Dict[str, Any],
    client: Optional[GrantLayerClient] = None,
    execute: bool = False,
) -> Dict[str, Any]:
    """Check GrantLayer health and readiness before proceeding.

    LangGraph node signature:
        def preflight_grantlayer(state: AgentState) -> AgentState:
            client = GrantLayerClient(state["base_url"], token=state.get("token"))
            result = _do_preflight(client)
            return {**state, "preflight": result}

    In dry-run mode (execute=False or client=None) returns a skipped result
    without making any network call.
    """
    if not execute or client is None:
        return {
            "status": "skipped",
            "mode": "dry_run",
            "health": None,
            "readiness": None,
        }

    try:
        health_resp = client.health()
        ready_resp = client.ready()
        return {
            "status": "ok",
            "mode": "execute",
            "health": health_resp.body,
            "readiness": ready_resp.body,
        }
    except GrantLayerHTTPError as exc:
        return {"status": "http_error", "mode": "execute", "error": str(exc)}
    except GrantLayerClientError as exc:
        return {"status": "connection_error", "mode": "execute", "error": str(exc)}


# ---------------------------------------------------------------------------
# Context preparation node
# ---------------------------------------------------------------------------

def prepare_grant_decision_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build the context that an LLM node would use to reason about a grant.

    In a real LangGraph workflow the LLM node would receive this dict,
    decide whether to approve/reject, and then call GrantLayer via the SDK
    to persist the decision and emit an audit event.

    LangChain Tool call shape (POST /demo-action):
        {
            "subjectId": state["subjectId"],
            "role":      state["role"],
            "action":    state["action"],
            "resource":  state["resource"],
        }
    """
    demo_action_body = {
        "subjectId": state.get("subjectId", "unknown"),
        "role": state.get("role", "unknown"),
        "action": state.get("action", "unknown"),
        "resource": state.get("resource", "unknown"),
    }

    grant_create_body = {
        "subjectId": state.get("subjectId"),
        "role": state.get("role"),
        "action": state.get("action"),
        "resource": state.get("resource"),
        "validFrom": state.get("validFrom"),
        "validUntil": state.get("validUntil"),
        "createdBy": state.get("createdBy"),
        "reason": state.get("reason"),
    }

    return {
        "agent_state_summary": state,
        "demo_action_body": demo_action_body,
        "grant_create_body": grant_create_body,
        "grantlayer_endpoints": {
            "health": "GET /health",
            "readiness": "GET /readiness",
            "demo_action": "POST /demo-action",
            "create_grant": "POST /grants",
            "audit_log": "GET /audit-events",
        },
        "adaptation_notes": (
            "Pass demo_action_body to POST /demo-action to check current approval status. "
            "Pass grant_create_body to POST /grants to create a new grant. "
            "Read /audit-events after any mutation to verify the audit trail."
        ),
    }


# ---------------------------------------------------------------------------
# Dry-run workflow (no network, no backend required)
# ---------------------------------------------------------------------------

def run_dry_run_workflow() -> Dict[str, Any]:
    """Run the full agent workflow in dry-run mode.

    No network calls are made.  Returns a JSON-serialisable dict that
    mirrors the shape a live run would return.  Safe to call in CI, tests,
    and offline demos.
    """
    state = build_sample_agent_state()
    preflight = preflight_grantlayer(state, client=None, execute=False)
    context = prepare_grant_decision_context(state)

    return {
        "mode": "dry_run",
        "grantlayer_preflight": preflight,
        "sample_decision_context": context,
        "safety_caveats": [
            "developer-preview only — not production-ready",
            "tenant isolation not implemented",
            "no real secrets used",
            "no real customer data used",
            "token is never logged or returned",
            "no external LLM or API key required",
            "no network calls made in dry-run mode",
        ],
    }


# ---------------------------------------------------------------------------
# Local backend workflow (optional, requires running backend)
# ---------------------------------------------------------------------------

def run_local_workflow(
    base_url: str,
    token: Optional[str] = None,
    execute: bool = False,
) -> Dict[str, Any]:
    """Run the agent workflow against a local GrantLayer backend.

    Set execute=True to make real HTTP calls.  If the backend is not
    reachable, returns a safe error dict without exposing the token.

    Args:
        base_url: Local backend URL, e.g. http://127.0.0.1:8000
        token:    Optional bearer token (admin or operator).  Never logged.
        execute:  If False, behaves identically to run_dry_run_workflow().
    """
    if not execute:
        return run_dry_run_workflow()

    # LangGraph adaptation:
    #   In a real node, inject client via dependency or state:
    #       client = GrantLayerClient(state["base_url"], token=state.get("_token"))
    client = GrantLayerClient(base_url, token=token, timeout=10.0)
    state = build_sample_agent_state()

    preflight = preflight_grantlayer(state, client=client, execute=True)

    if preflight.get("status") not in ("ok", "skipped"):
        return {
            "mode": "execute",
            "grantlayer_preflight": preflight,
            "sample_decision_context": None,
            "error": "preflight_failed — backend may be unavailable",
            "safety_caveats": [
                "developer-preview only — not production-ready",
                "tenant isolation not implemented",
                "token is never logged or returned",
            ],
        }

    context = prepare_grant_decision_context(state)

    return {
        "mode": "execute",
        "grantlayer_preflight": preflight,
        "sample_decision_context": context,
        "safety_caveats": [
            "developer-preview only — not production-ready",
            "tenant isolation not implemented",
            "no real secrets used",
            "no real customer data used",
            "token is never logged or returned",
        ],
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="GL-148 GrantLayer LangGraph/LangChain integration example"
    )
    p.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="GrantLayer backend URL (default: http://127.0.0.1:8000)",
    )
    p.add_argument(
        "--token",
        default=None,
        help="Optional bearer token (admin or operator). Never logged.",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Actually call the local backend (default: dry-run)",
    )
    return p


if __name__ == "__main__":
    args = _build_parser().parse_args()
    result = run_local_workflow(
        base_url=args.base_url,
        token=args.token,
        execute=args.execute,
    )
    # Never include the token in output
    print(json.dumps(result, indent=2))
