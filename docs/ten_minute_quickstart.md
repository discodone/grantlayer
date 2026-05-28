# GL-146 10-Minute Quickstart

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Title and Status

This document is the **GL-146 10-Minute Quickstart**. It helps an external
developer set up GrantLayer locally, start the backend, verify
health/readiness, run a minimal safe API smoke path, and understand current
limitations.

| Field | Value |
|-------|-------|
| Issue | GL-146 |
| Status | developer-preview / local quickstart |
| Production code changed | **No** |
| SDK implemented | **No** |
| LangGraph/LangChain example implemented | **No** |
| Public GitHub readiness claimed | **No** |
| Production SaaS readiness claimed | **No** |
| Tenant isolation claimed/implemented | **No** |

This is **NOT production deployment guidance.**
This is **NOT managed SaaS setup.**
This is **NOT SDK implementation.**
This is **NOT LangGraph/LangChain integration implementation.**
This is **NOT public GitHub release.**
This is **NOT API behavior work.**
This is **NOT auth redesign.**
This is **NOT tenant/workspace implementation.**

---

## 2. What This Quickstart Does

- **Local setup** — clone the repo, create a virtualenv, and install dependencies.
- **Backend start** — run the backend locally on `127.0.0.1:8765`.
- **Health/readiness check** — verify the backend is alive and ready with `curl`.
- **Minimal safe local API smoke path** — create a grant, run a protected demo
  action, and check the audit log using only synthetic/demo data.

---

## 3. What This Quickstart Does Not Do

- **No production deployment** — this guide is for local evaluation only.
- **No real customer data** — all examples use synthetic identifiers and demo
  scenarios.
- **No managed SaaS setup** — there is no hosted service; you run the backend
  yourself.
- **No tenant isolation** — GrantLayer does not enforce tenant/workspace
  boundaries. All data shares a single namespace.
- **No SDK yet** — a minimal Python SDK is planned for GL-147.
- **No LangGraph/LangChain yet** — an integration example is planned for GL-148.
- **No public GitHub release yet** — public readiness work is planned for GL-149.

---

## 4. Prerequisites

- **Python 3.10+** (Python 3.13 recommended)
- **Git**
- **A shell** (bash, zsh, or equivalent)
- **Local repo checkout** — clone or copy the repository
- **No external service required** for the minimal path (SQLite is the default
  database)

---

## 5. Setup

### 5.1 Clone the repository

```bash
git clone https://github.com/<ORG_OR_USER>/grantlayer-mvp.git
cd grantlayer-mvp
```

> Replace `<ORG_OR_USER>` with the future public GitHub owner after publication.
> Until then, use the approved internal source.

> If you already have the repo locally, `cd` into it instead.

### 5.2 Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 5.3 Install dependencies

```bash
pip install -r requirements.txt
```

> The backend requires only `cryptography>=42.0.0` and `psycopg2-binary>=2.9.0`
> outside the Python standard library. PostgreSQL support is optional; SQLite
> works out of the box.

---

## 6. Configuration

### 6.1 Local/dev environment variables

For a safe local demo, set placeholder environment variables. **Do not use
these values in production.**

```bash
export GRANTLAYER_ADMIN_TOKEN="demo-admin-token-gl146"
export GRANTLAYER_REQUIRE_ADMIN_TOKEN="false"
export GRANTLAYER_ENABLE_DEMO_ENDPOINTS="false"
export GRANTLAYER_HOST="127.0.0.1"
export GRANTLAYER_PORT="8765"
```

> **Note:** `GRANTLAYER_REQUIRE_ADMIN_TOKEN=false` means protected endpoints
> are accessible without a Bearer token in demo mode. This is acceptable for
> local evaluation only.

### 6.2 Operator model default

GrantLayer defaults `ENABLE_OPERATOR_MODEL` to `true` (GL-141). The operator
model is active by default. Legacy admin-token compatibility remains available
when the operator model is disabled.

---

## 7. Run Backend

### 7.1 Start the server

```bash
python3 -m backend
```

Or via the convenience script:

```bash
./scripts/dev.sh
```

### 7.2 Expected startup behavior

You should see output similar to:

```
Starting GrantLayer MVP on http://127.0.0.1:8765 ...
```

The backend binds to `127.0.0.1:8765` by default. The dashboard is served at
`http://127.0.0.1:8765/`.

### 7.3 Custom host/port

```bash
GRANTLAYER_HOST=0.0.0.0 GRANTLAYER_PORT=9000 python3 -m backend
```

> Verify the exact start command from the current repo entrypoint
> (`backend/__main__.py` or `scripts/dev.sh`).

---

## 8. Verify Health / Readiness

### 8.1 Health check (public)

```bash
curl -s http://127.0.0.1:8765/health | python3 -m json.tool
```

**Expected response shape:**

```json
{
  "status": "ok",
  "service": "GrantLayer",
  "check": "liveness"
}
```

### 8.2 Readiness check (public)

```bash
curl -s http://127.0.0.1:8765/readiness | python3 -m json.tool
```

**Expected response shape:**

```json
{
  "status": "ready",
  "service": "GrantLayer",
  "check": "readiness"
}
```

> The readiness endpoint may return `"status": "not_ready"` during startup
> before the database is initialized. Wait a few seconds and retry.

---

## 9. Minimal Smoke Path

This path uses only synthetic/demo data. It does not require tenant isolation
and does not touch real customer data.

### 9.1 Create a grant

```bash
curl -s -X POST http://127.0.0.1:8765/grants \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "gl146-demo-subject-001",
    "role": "technician",
    "action": "restart-service",
    "resource": "gl146-demo-resource-001",
    "validFrom": "2026-05-01T00:00:00Z",
    "validUntil": "2026-12-31T23:59:59Z",
    "createdBy": "gl146-demo-admin",
    "reason": "GL-146 quickstart demo grant"
  }' | python3 -m json.tool
```

Save the returned `id` field as `GRANT_ID` for the next steps.

### 9.2 Run a protected demo action

```bash
curl -s -X POST http://127.0.0.1:8765/demo-action \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "gl146-demo-subject-001",
    "role": "technician",
    "action": "restart-service",
    "resource": "gl146-demo-resource-001"
  }' | python3 -m json.tool
```

**Expected:** `"approved": true`

### 9.3 Check the audit log

```bash
curl -s http://127.0.0.1:8765/audit-events | python3 -m json.tool
```

You should see audit events for the grant creation and the demo action.

### 9.4 Revoke the grant

```bash
curl -s -X POST "http://127.0.0.1:8765/grants/${GRANT_ID}/revoke" \
  -H "Content-Type: application/json" \
  -d '{
    "revokedBy": "gl146-demo-admin",
    "reason": "GL-146 quickstart cleanup"
  }' | python3 -m json.tool
```

### 9.5 Verify the grant is revoked

```bash
curl -s "http://127.0.0.1:8765/grants/${GRANT_ID}" | python3 -m json.tool
```

**Expected:** `"status": "revoked"`

### 9.6 Re-run the demo action — now blocked

```bash
curl -s -X POST http://127.0.0.1:8765/demo-action \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "gl146-demo-subject-001",
    "role": "technician",
    "action": "restart-service",
    "resource": "gl146-demo-resource-001"
  }' | python3 -m json.tool
```

**Expected:** `"approved": false`, with a reason indicating the grant has been
revoked.

> This minimal smoke path demonstrates the core Product Core flow: grant
> creation, execution, audit, revocation, and enforcement.

---

## 10. Troubleshooting

### 10.1 Port already in use

If `127.0.0.1:8765` is already in use, either stop the other process or start
GrantLayer on a different port:

```bash
GRANTLAYER_PORT=9000 python3 -m backend
```

Remember to update all `curl` commands to use the new port.

### 10.2 Missing dependency

If you see `ModuleNotFoundError: No module named 'cryptography'`, ensure you
activated the virtualenv and installed requirements:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 10.3 Python import path

If `python3 -m backend` fails with an import error, ensure you are in the repo
root (`grantlayer-mvp`) and that the `backend/` directory is on the Python path.
The `python3 -m backend` command handles this automatically when run from the
repo root.

### 10.4 Auth / operator token confusion

- In demo mode (`GRANTLAYER_REQUIRE_ADMIN_TOKEN=false`), protected endpoints do
  not require a Bearer token.
- In product mode (`GRANTLAYER_REQUIRE_ADMIN_TOKEN=true`), you must supply
  `Authorization: Bearer <token>` on protected endpoints.
- The operator model is enabled by default (GL-141). Operator tokens are managed
  separately from the legacy admin token.

### 10.5 Readiness not ready

If `/readiness` returns `"status": "not_ready"`, wait a few seconds for the
database to initialize and retry. If it persists, check the startup output for
errors.

### 10.6 Request body / content-length issues

Always include `-H "Content-Type: application/json"` when sending JSON bodies.
Ensure the JSON is well-formed. If you see `400 Bad Request` with a
`content_length_required` or `invalid_json` error, verify the request body and
headers.

---

## 11. Safety Checklist

Before proceeding beyond local evaluation, confirm:

- [ ] **No secrets in docs or shell history** — the demo admin token is a
  placeholder; do not reuse it elsewhere.
- [ ] **No production data** — all examples use synthetic identifiers
  (`gl146-demo-*`).
- [ ] **No public SaaS claim** — this quickstart does not describe GrantLayer as
  production-ready SaaS.
- [ ] **Tenant isolation not implemented** — all data shares a single namespace.
  Do not run unrelated customer data in the same deployment.
- [ ] **Local-only demo/testing** — this guide is for local evaluation and
  controlled pilot exploration only.

---

## 12. Next Steps

| Issue | Title | Purpose |
|-------|-------|---------|
| GL-147 | Minimal Python SDK | A minimal Python client/SDK that wraps the OpenAPI contract with typed requests and responses. |
| GL-148 | LangGraph/LangChain Integration Example | A concrete example showing how GrantLayer grant requests, evidence bundles, and policy checks fit into a LangGraph node graph. |
| GL-149 | Public GitHub Readiness Pack | A checklist and set of artifacts (README, CONTRIBUTING, issue templates, CI badges) that prepare the repo for public visibility. |
| GL-150 | First Developer Feedback Log | A structured log or template for capturing the first real (or explicitly simulated) developer feedback on the quickstart, SDK, and integration example. |

---

> GL-146 documents the **10-minute developer quickstart** for the GrantLayer
> Developer Adoption track. It does **not** implement any SDK, quickstart
> runtime code, integration example, public GitHub release, API change, auth
> redesign, tenant/workspace implementation, or production SaaS claim. It
> explicitly preserves all existing gates (GL-136 through GL-145) and mandates
> that no public release or developer adoption claim is made until GL-146
> through GL-150 are completed and validated.
