# GL-148: LangGraph/LangChain Integration Example

**Status:** developer-preview — local example only  
**Issue:** GL-148  
**Requires:** GL-146 quickstart completed, GL-147 SDK available  
**Tenant isolation:** not implemented  
**Production SaaS readiness:** not claimed  

---

## 1. What this example demonstrates

This example shows how GrantLayer can act as a **policy, evidence, and audit
boundary** inside an AI-agent workflow.  Using the GL-147 Python SDK, you can
call GrantLayer from any agent framework that can invoke a Python function.

Specifically the example demonstrates:

- **SDK preflight** — checking GrantLayer health and readiness before the
  agent makes a grant decision
- **Agent state construction** — building the minimal state dict that
  represents a pending grant request
- **Grant decision context** — preparing the request bodies your agent would
  send to `/demo-action` and `/grants`
- **Dry-run agent flow** — running the entire workflow without a live backend
  or any network call
- **Optional local backend execution** — running against a locally started
  GrantLayer instance with `--execute`
- **LangGraph/LangChain adaptation notes** — inline comments explaining how
  each function maps to a LangGraph `StateGraph` node or a LangChain `Tool`

---

## 2. What this example does NOT do

| Claim | Status |
|---|---|
| Requires LangGraph installation | No — standard library only |
| Requires LangChain installation | No — standard library only |
| Requires an external LLM or API key | No — no LLM calls |
| Makes network calls at import time | No |
| Performs real grant approvals | No |
| Uses real customer data | No |
| Uses real secrets | No |
| Claims production SaaS readiness | No |
| Implements tenant isolation | No |
| Publishes a package | No |
| Deploys to production | No |

---

## 3. Setup

**Step 1 — Complete the GL-146 10-minute quickstart**

Follow `docs/ten_minute_quickstart.md` to clone the repo, create a virtual
environment, install dependencies, and verify the backend starts.

**Step 2 — Confirm the GL-147 SDK is present**

```bash
ls sdk/python/grantlayer_client.py
ls sdk/python/README.md
```

Both files must exist.  The SDK is imported directly from the repo; no
`pip install` step is needed.

**Step 3 — (Optional) Start the local backend**

Only required if you want to run with `--execute`.  From the repo root:

```bash
python3 -m backend
# or
./scripts/dev.sh
```

Verify it is running:

```bash
curl http://127.0.0.1:8000/health
# → {"status": "ok", "service": "GrantLayer", "check": "liveness"}
```

---

## 4. Dry-run usage

Run the example without starting a backend.  No network calls are made.

```bash
cd /path/to/grantlayer-mvp
python3 examples/langgraph_langchain/grantlayer_agent_example.py
```

Expected output (abbreviated):

```json
{
  "mode": "dry_run",
  "grantlayer_preflight": {
    "status": "skipped",
    "mode": "dry_run"
  },
  "sample_decision_context": { "..." : "..." },
  "safety_caveats": [
    "developer-preview only — not production-ready",
    "tenant isolation not implemented",
    "..."
  ]
}
```

---

## 5. Local backend usage

With the backend running on `http://127.0.0.1:8000`, pass `--execute` to make
real HTTP calls:

```bash
python3 examples/langgraph_langchain/grantlayer_agent_example.py --execute
```

With a custom URL:

```bash
python3 examples/langgraph_langchain/grantlayer_agent_example.py \
  --base-url http://127.0.0.1:8000 \
  --execute
```

With an optional placeholder token (never use real production tokens here):

```bash
python3 examples/langgraph_langchain/grantlayer_agent_example.py \
  --base-url http://127.0.0.1:8000 \
  --token dev-placeholder-token \
  --execute
```

> **Security note:** The token is passed via `--token` and injected into the
> `Authorization: Bearer` header by the GL-147 SDK.  It is never printed,
> logged, or included in the output dict.

---

## 6. LangGraph/LangChain adaptation notes

### Mapping to LangGraph nodes

Each function in `grantlayer_agent_example.py` is designed to be a drop-in
LangGraph `StateGraph` node:

```python
# LangGraph adaptation (requires langgraph installation — not needed for this example)
# from langgraph.graph import StateGraph
# from typing import TypedDict

# class AgentState(TypedDict):
#     base_url: str
#     token: str | None   # never log this
#     preflight: dict
#     context: dict

# builder = StateGraph(AgentState)
# builder.add_node("preflight", preflight_grantlayer)
# builder.add_node("context",   prepare_grant_decision_context)
# builder.add_edge("preflight", "context")
# graph = builder.compile()
```

### Mapping to a LangChain Tool

```python
# LangChain adaptation (requires langchain installation — not needed for this example)
# from langchain.tools import Tool
#
# grantlayer_tool = Tool(
#     name="grantlayer_check",
#     description="Check GrantLayer policy and readiness before approving a grant.",
#     func=lambda args: run_local_workflow(
#         base_url=args["base_url"],
#         token=args.get("token"),   # injected at runtime, never logged
#         execute=True,
#     ),
# )
```

### Keep GrantLayer calls behind the SDK wrapper

Do not call GrantLayer endpoints directly with `requests` or `httpx` in
production agent code.  The GL-147 SDK handles:

- Bearer token injection (without leaking the token in exceptions)
- JSON serialisation / deserialisation
- HTTP error mapping to typed exceptions

### Handle errors gracefully

```python
try:
    resp = client.health()
except GrantLayerHTTPError as exc:
    # exc.status contains the HTTP status code
    # exc message never contains the token
    agent_state["preflight_error"] = str(exc)
except GrantLayerClientError as exc:
    agent_state["preflight_error"] = f"connection_error: {exc}"
```

### Keep secrets out of logs

- Never log `state["token"]` or any `Authorization` header value.
- Pass the token only to `GrantLayerClient(base_url, token=token)`.
- The SDK strips the token from all exception messages.

---

## 7. Security caveats

- **No real secrets** — do not use production tokens with this example.
- **No real customer data** — the sample state contains placeholder values only.
- **No production approval automation** — this example does not submit real
  grant requests to a production system.
- **Tenant isolation not implemented** — the GrantLayer MVP does not implement
  multi-tenant isolation.  Do not use it to isolate data between real tenants.
- **developer-preview only** — this example is for local developer exploration.
  It is not a production deployment guide.
- **No external LLM or API key required** — no calls to OpenAI, Anthropic, or
  any other LLM provider are made by this example.

---

## 8. Troubleshooting

### Import error: `ModuleNotFoundError: No module named 'grantlayer_client'`

The script injects `sdk/python/` into `sys.path` automatically when run from
the repo root.  If you run it from a different directory, ensure the repo root
is on `PYTHONPATH`:

```bash
PYTHONPATH=/path/to/grantlayer-mvp python3 \
  /path/to/grantlayer-mvp/examples/langgraph_langchain/grantlayer_agent_example.py
```

### `connection_error` in execute mode

The backend is not running.  Start it first:

```bash
python3 -m backend
```

Then retry with `--execute`.

### Token/header confusion

- The `--token` argument is optional.  Health and readiness endpoints are
  public and do not require a token.
- If you receive `HTTP 401` or `HTTP 403`, check that the token matches the
  `ADMIN_TOKEN` or operator token configured in the backend environment.
- See the GL-147 SDK README (`sdk/python/README.md`) for authentication modes.

### JSON/HTTP errors

`GrantLayerHTTPError` includes the HTTP status code in `exc.status`.
`GrantLayerJSONError` is raised when the response body is not valid JSON.
Both are subclasses of `GrantLayerClientError`, so you can catch the base
class to handle all GrantLayer errors in one `except` block.

---

## 9. Next steps

- **GL-149 Public GitHub Readiness Pack** — prepare the repo for first public
  external developer access: README polish, contributing guide, issue
  templates, and security policy.
- **GL-150 First Developer Feedback Log** — structured log of the first
  external developer attempts, blockers, and suggested improvements.
