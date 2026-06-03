# GrantLayer

> **GrantLayer turns agentic grant workflows into verifiable institutional records.**
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

GrantLayer is a verification, audit, and compliance layer for agentic grant and funding workflows.

When AI agents prepare funding applications, evaluate eligibility, collect evidence, or trigger approval decisions, institutions need a neutral verification layer — one that makes every step traceable, tamper-evident, and independently auditable. GrantLayer is that layer.

---

## Status

| Posture | Value |
|---------|-------|
| Release label | **GL-0.1 / Developer Preview** |
| Maturity | Local evaluation and controlled pilot only |
| Production SaaS readiness | **Not claimed** |
| Tenant/workspace isolation | **Not implemented** |
| Public GitHub release | **Available** — repository publicly available at `https://github.com/Discodone/grantlayer.git` (GL-176) |
| Public snapshot | Clean developer-facing snapshot — no internal paths, no real secrets |
| Source of truth | Internal Forgejo — public GitHub is a clean read-only snapshot |
| Real customer data in examples | **No** — all examples use synthetic identifiers |
| Real secrets in examples | **No** — all tokens and keys are placeholders |

GrantLayer is in a **developer-preview / controlled-pilot posture**. The primary use case is cloning the repository, running the backend locally, and evaluating the Product Core flow.

---

## What you can do today

- **Generate the first verifiable output** — run one local Python example that writes a deterministic GrantLayer-style institutional record without starting the backend.
- **Verify the first output matches the reference** — run the verify helper to confirm the committed artifact still matches the generator.
- **Run the grant lifecycle evidence bundle** — run the second local example to see a full grant lifecycle with evidence hashes and an audit chain.
- **Run the backend quickstart** — clone the repo, start the backend, and run a minimal safe API smoke path in ~10 minutes. *(Requires Python virtualenv and `pip install`.)*
- **Use the minimal Python SDK** — import the SDK and make typed calls to health, readiness, grants, and audit endpoints.
- **Inspect the LangGraph/LangChain-style example** — review how GrantLayer fits into an agentic workflow without installing LangGraph or LangChain.

---

## What to try first

**No install, no backend, no network required.** From the repository root:

```bash
python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json
```

Verify it matches the committed reference:

```bash
scripts/verify-first-output.sh
```

The committed reference artifact is [`examples/first_verifiable_output.json`](examples/first_verifiable_output.json).

Read the walkthrough in [docs/first_verifiable_output.md](docs/first_verifiable_output.md) and the verify-helper guide in [docs/first_output_verify_helper.md](docs/first_output_verify_helper.md).

This path uses Python standard library modules only, requires no real secrets, requires no customer data, and is local/demo only. It does not claim production SaaS readiness, and tenant isolation is not implemented.

## What to try next

**Second runnable example — grant lifecycle with evidence and audit chain.** Still no install, no backend, no network required:

```bash
python3 examples/grant_lifecycle_evidence_bundle.py --output /tmp/grantlayer_grant_lifecycle_evidence_bundle.json
diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_grant_lifecycle_evidence_bundle.json
```

The committed reference artifact is [`examples/grant_lifecycle_evidence_bundle.json`](examples/grant_lifecycle_evidence_bundle.json).

Read the explanation in [docs/grant_lifecycle_evidence_bundle.md](docs/grant_lifecycle_evidence_bundle.md).

For troubleshooting either example see [docs/public_developer_experience_polish_pack.md#troubleshooting](docs/public_developer_experience_polish_pack.md).

---

## Developer entry path

| Step | What to do | Details |
|------|-----------|---------|
| 1 | First verifiable output (no install) | [docs/first_verifiable_output.md](docs/first_verifiable_output.md) |
| 2 | Verify first output matches reference | [docs/first_output_verify_helper.md](docs/first_output_verify_helper.md) |
| 3 | Grant lifecycle evidence bundle (no install) | [docs/grant_lifecycle_evidence_bundle.md](docs/grant_lifecycle_evidence_bundle.md) |
| 4 | Backend quickstart *(requires pip install)* | [docs/ten_minute_quickstart.md](docs/ten_minute_quickstart.md) |
| 5 | Python SDK | [sdk/python/README.md](sdk/python/README.md) |
| 6 | Agent workflow integration example | [docs/langgraph_langchain_integration_example.md](docs/langgraph_langchain_integration_example.md) |
| 7 | Structured feedback intake | [docs/first_developer_feedback_log.md](docs/first_developer_feedback_log.md) |

> **Steps 1–3 require no virtualenv, no `pip install`, and no running backend.** Python stdlib only. No cloud service, database subscription, or third-party API is required for these paths.
> **Step 4 (backend quickstart) requires Python virtualenv and `pip install -r requirements.txt`** — see [docs/ten_minute_quickstart.md](docs/ten_minute_quickstart.md).

---

## For AI Coding Agents

GrantLayer is local-first and agent-friendly. If you are an AI coding agent, start here:

| File | Purpose |
|------|---------|
| [`AGENTS.md`](AGENTS.md) | Primary agent entry point: rules, boundaries, workflow, and safety |
| [`llms.txt`](llms.txt) | Concise project summary and agent entry links |
| [`llms-full.txt`](llms-full.txt) | Detailed repository map, safe/forbidden areas, and next steps |
| [`docs/agent_quickstart.md`](docs/agent_quickstart.md) | 60-second orientation for first contributions |
| [`docs/public_agent_api_walkthrough_refresh.md`](docs/public_agent_api_walkthrough_refresh.md) | Public agent/API walkthrough, entry points, and safety boundaries |
| [`docs/agent_task_contract.md`](docs/agent_task_contract.md) | Issue/task specification and final-report format |
| [`docs/agent_integration_manifest.json`](docs/agent_integration_manifest.json) | Machine-readable project metadata |
| [`docs/ten_minute_quickstart.md`](docs/ten_minute_quickstart.md) | Clone → install → start backend → smoke path |
| [`docs/public_feedback_infrastructure_pack.md`](docs/public_feedback_infrastructure_pack.md) | Public feedback intake, severity routing, and security advisory guidance |
| [`sdk/python/README.md`](sdk/python/README.md) | Minimal Python SDK usage guide |
| [`docs/langgraph_langchain_integration_example.md`](docs/langgraph_langchain_integration_example.md) | How GrantLayer fits into an agentic workflow |

**Important caveats:**
- GrantLayer is in **Developer Preview** — local evaluation and controlled pilot only.
- **No real secrets or customer data** anywhere in the repository.
- **Not production SaaS** — do not deploy to shared multi-tenant infrastructure.
- **Tenant isolation is not implemented** — data shares a single namespace.
- **Public GitHub repository is available** — the repository is publicly accessible at `https://github.com/Discodone/grantlayer.git` (GL-176).

Runtime agent examples are available — see `docs/langgraph_langchain_integration_example.md` and `examples/langgraph_langchain/grantlayer_agent_example.py` (added in GL-155).

---

## Repository and readiness links

- [CHANGELOG.md](CHANGELOG.md) — Public snapshot and version notes.
- [docs/first_developer_feedback_log.md](docs/first_developer_feedback_log.md) — First structured feedback intake (internal dry-run only; no real external feedback claimed).
- [docs/key_hygiene.md](docs/key_hygiene.md) — Key and secret hygiene rules for the repository.
- [docs/dependency_manifest.md](docs/dependency_manifest.md) — Python runtime and dev dependency manifest.

---

## Safety and limitations

- **Do not use real secrets** — all documentation uses placeholder tokens (e.g. `demo-admin-token-gl146`).
- **Do not use real customer data** — all examples use synthetic identifiers (e.g. `gl146-demo-subject-001`).
- **Production SaaS readiness is not claimed** — the backend has not completed all production-hardening gates required for a shared multi-tenant SaaS.
- **Tenant isolation is not implemented** — the backend does not enforce tenant/workspace boundaries at the data, authorization, or audit layers.
- **Public GitHub repository is available** — the repository is publicly accessible at `https://github.com/Discodone/grantlayer.git` (GL-176). All public content was synced via the explicit clean snapshot workflow; the internal Forgejo repo was not pushed directly to GitHub.
- **Local evaluation only** — this repo is intended for developer exploration and controlled pilot discussion, not production deployment.

---

## License posture

- **License:** Apache License 2.0. See [LICENSE](LICENSE).
- A `LICENSE` file was added in **GL-153**.

## Contribution and security posture

- **Contributing guide** — See [CONTRIBUTING.md](CONTRIBUTING.md). Covers developer-preview rules, coding-agent contribution guidelines, DCO recommendation, and testing expectations.
- **Security policy** — See [SECURITY.md](SECURITY.md). Covers reporting guidance, vulnerability scope, data-handling rules, and current caveats.
- No mature public contribution process is claimed.

---

## Repository metadata

The public repository is available at `https://github.com/Discodone/grantlayer.git`.

| Field | Value |
|-------|-------|
| Short description | "Developer-preview verification and audit layer for agentic grant workflows." |
| Topics | `grant-management`, `audit-trail`, `compliance`, `agentic-workflows`, `developer-preview`, `python` |
| License | Apache-2.0 |
| Website | None — no public landing page or marketing site exists |

---

## What GrantLayer is

GrantLayer is **not** a payment app, a blockchain app, a demo app, or a pure funding platform. It is an infrastructure-level verification and audit layer for agent-driven processes that involve grants, approvals, evidence, and compliance decisions.

Core concepts:
- **Evidence Bundles** — collect evidence, criteria, sources, and timestamps for every grant lifecycle event
- **Verification Core** — check completeness, consistency, versions, and hash integrity of stored evidence
- **Audit Trails** — make traceable who or what decided what, when, and on which grounds
- **Policy Layer** *(Phase 2)* — machine-readable grant rules, exclusion criteria, deadlines, and proof requirements

---

## MVP scope

The current MVP and Product Core establish the technical foundation:
- Action-level grant model (subject, role, action, resource, time window)
- Policy evaluation: fail-closed
- Grant revocation, usage limits, Ed25519 signatures
- Operator model with RBAC
- Grant Request approval workflow
- Grant Execution audit ledger
- Evidence Bundles with SHA-256 integrity hash
- Evidence Persistence (durable storage)
- Evidence Verification Core (server-side hash verification)
- Evidence Completeness scoring
- Compliance Gap Reports
- Agent Permissions (scopes, profiles, assignments)
- Approval Rules and Approval Lifecycle
- Decision Provenance v2
- Auditor Reports and Exports
- Policy Requirements / Rule Packs
- Compliance Readiness Summary
- API Error Consistency
- Security / Secrets Regression Hardening
- SQLite (default) + PostgreSQL (optional)

---

## What is explicitly not in this MVP

- No blockchain (planned as optional Phase 3 integrity layer)
- No wallets, stablecoins, or treasury logic
- No UI beyond a local debug dashboard
- No external notarization or certification services
- No production authentication (no OAuth, JWT, TLS)

---

## Stack

- **Backend:** Python 3.13, stdlib + `cryptography` v43.0.0 (Ed25519)
- **Frontend:** Vanilla HTML/JS, served by the backend — no build step
- **Database:** SQLite (WAL mode) or PostgreSQL, stored in `data/grantlayer.db` or PostgreSQL volume
- **Tests:** Python `unittest` (stdlib)

> Node.js was not available without sudo on this VM. Python stdlib produces an identical demo with zero external dependencies.

---

## Choose your path

**Path A — First verifiable output (no install, no backend, no network required):**

```bash
git clone https://github.com/Discodone/grantlayer.git
cd grantlayer
python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json
scripts/verify-first-output.sh
```

No virtualenv, no `pip install`, no running backend. Python stdlib only.
See [docs/first_verifiable_output.md](docs/first_verifiable_output.md) and [docs/first_output_verify_helper.md](docs/first_output_verify_helper.md).

**Path A2 — Grant lifecycle evidence bundle (no install, no backend, no network required):**

```bash
python3 examples/grant_lifecycle_evidence_bundle.py --output /tmp/grantlayer_grant_lifecycle_evidence_bundle.json
diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_grant_lifecycle_evidence_bundle.json
```

Extends the first verifiable output with a full lifecycle sequence, evidence hashes, and a linked audit chain.
See [docs/grant_lifecycle_evidence_bundle.md](docs/grant_lifecycle_evidence_bundle.md).

**Path B — Backend quickstart (requires Python virtualenv and `pip install`):**

```bash
git clone https://github.com/Discodone/grantlayer.git
cd grantlayer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start backend

```bash
python3 -m backend
```

Or via script:
```bash
./scripts/dev.sh
```

Backend starts on `http://127.0.0.1:8765`. Dashboard opens at the same URL.

Custom host/port:
```bash
GRANTLAYER_HOST=0.0.0.0 GRANTLAYER_PORT=9000 python3 -m backend
```

## Start dashboard

Open `http://127.0.0.1:8765/` in a browser after starting the backend.
The dashboard auto-refreshes every 10 seconds.

## Run tests

```bash
python3 -m unittest discover -s backend/tests -v
```

Or via script:
```bash
./scripts/test.sh
```

Run `scripts/run-full-backend-suite.sh` for the current internal validation suite.
The suite includes thousands of tests; known expected legacy scope-guard failures are pre-existing and documented.

## Configuration (GL-020 Product Hardening)

The MVP supports opt-in product-mode hardening via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GRANTLAYER_REQUIRE_ADMIN_TOKEN` | `false` | Require valid Bearer token on protected endpoints. |
| `GRANTLAYER_ADMIN_TOKEN` | *(empty)* | Static admin Bearer token. Never logged or returned. |
| `GRANTLAYER_REQUIRE_CHALLENGE` | `false` | Require `challengeId` on `POST /demo-action`. |
| `GRANTLAYER_ENABLE_DEMO_ENDPOINTS` | `false` | Enable the demo tamper endpoint. Default is **disabled**. |
| `GRANTLAYER_HOST` | `127.0.0.1` | Bind address. |
| `GRANTLAYER_PORT` | `8765` | HTTP port. |

### Product-mode vs demo-mode

**Demo-mode (default):** All unsafe defaults are allowed. The server explicitly prints warnings at startup.
**Product-mode:** Set `REQUIRE_ADMIN_TOKEN=true`, `REQUIRE_CHALLENGE=true`, and `ENABLE_DEMO_ENDPOINTS=false` for enforced hardening.

Note: this is still NOT production-ready. See [docs/security_boundaries.md](docs/security_boundaries.md) for what is missing (TLS, HSM/KMS, real IAM, etc.).

---

## API Quick Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /grants | List all grants |
| GET | /grants/:id | Get a single grant (includes signatureValid) |
| POST | /grants | Create a grant (optional `maxUses`) |
| POST | /grants/:id/revoke | Revoke a grant |
| POST | /grant-requests | Create a grant request (GL-022) |
| GET | /grant-requests | List grant requests (GL-022) |
| GET | /grant-requests/:id | Get a single grant request (GL-022) |
| POST | /grant-requests/:id/approve | Approve a grant request and create the grant (GL-022) |
| POST | /grant-requests/:id/deny | Deny a grant request (GL-022) |
| POST | /challenges | Create a challenge (5-min TTL) |
| GET | /challenges | List all challenges |
| POST | /demo-action | Run protected demo action (optional challengeId) |
| GET | /audit-events | List audit events |
| GET | /grant-executions | List grant executions (GL-023) — owner, grant_admin, auditor only |
| GET | /grant-executions/:id | Get a single grant execution (GL-023) — owner, grant_admin, auditor only |
| GET | /grants/:id/executions | List executions for a grant (GL-023) — owner, grant_admin, auditor only |
| GET | /evidence/executions/:id | Read-only evidence bundle for a grant execution (GL-025) — owner, grant_admin, auditor only |
| GET | / | Dashboard |
| POST | /demo/tamper-grant/:id | **Demo only** — corrupt a grant field without re-signing |

> For the full OpenAPI contract see `docs/openapi.yaml`.

---

## Example walkthrough

### 1. Create a grant (curl)
```bash
curl -s -X POST http://127.0.0.1:8765/grants \
  -H "Content-Type: application/json" \
  -d '{
    "subjectId": "tech-01",
    "role": "technician",
    "action": "restart-service",
    "resource": "customer-env-a",
    "validFrom": "2026-05-02T00:00:00Z",
    "validUntil": "2026-12-31T23:59:59Z",
    "createdBy": "admin",
    "reason": "Scheduled maintenance"
  }' | python3 -m json.tool
```

### 2. Demo action — approved
```bash
curl -s -X POST http://127.0.0.1:8765/demo-action \
  -H "Content-Type: application/json" \
  -d '{"subjectId":"tech-01","role":"technician","action":"restart-service","resource":"customer-env-a"}' \
  | python3 -m json.tool
```
Expected: `"approved": true`

### 3. Revoke the grant
```bash
curl -s -X POST http://127.0.0.1:8765/grants/<ID>/revoke \
  -H "Content-Type: application/json" \
  -d '{"revokedBy":"admin","reason":"Emergency stop"}' \
  | python3 -m json.tool
```

### 4. Demo action — blocked
```bash
curl -s -X POST http://127.0.0.1:8765/demo-action \
  -H "Content-Type: application/json" \
  -d '{"subjectId":"tech-01","role":"technician","action":"restart-service","resource":"customer-env-a"}' \
  | python3 -m json.tool
```
Expected: `"approved": false`, reason: `"Grant ... has been revoked"`

### 5. Check audit log
```bash
curl -s http://127.0.0.1:8765/audit-events | python3 -m json.tool
```

---

## Current status and next steps

The governance and readiness gates up to GL-192 are complete. The repository is publicly available
on GitHub in a developer-preview / controlled-pilot posture.

| What | Status |
|------|--------|
| Public README polish and blocker fixes | Complete (GL-151 / GL-152) |
| LICENSE, CONTRIBUTING, SECURITY | Added (GL-153) |
| Agent entry points (AGENTS.md, llms.txt, agent examples) | Added (GL-154 / GL-155) |
| Public snapshot hygiene and readiness review sequence | Complete (GL-168–GL-174) |
| Formal public visibility decision | Complete (GL-175) |
| Public GitHub visibility change and correction push | Complete (GL-176) |
| Public repo smoke verification | Complete — passed with cautions (GL-177) |
| README / SECURITY post-public state correction | Complete (GL-178) |
| First output verify helper | Complete (GL-188) |
| Second runnable example / grant lifecycle evidence bundle | Complete (GL-189) |
| Demo endpoint safety guard | Complete (GL-190) |
| Public developer experience polish pack | Complete (GL-191) |
| Public feedback infrastructure pack | Complete (GL-192) |

For troubleshooting and FAQ see [docs/public_developer_experience_polish_pack.md](docs/public_developer_experience_polish_pack.md).
For the public agent/API walkthrough that connects the no-install examples to the backend path, see [docs/public_agent_api_walkthrough_refresh.md](docs/public_agent_api_walkthrough_refresh.md).

---
