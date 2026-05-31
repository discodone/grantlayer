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
| Public GitHub release | **Not performed** — requires explicit later approval |
| Public snapshot | Clean developer-facing snapshot — no internal paths, no real secrets |
| Source of truth | Internal Forgejo — public GitHub is a clean read-only snapshot |
| Real customer data in examples | **No** — all examples use synthetic identifiers |
| Real secrets in examples | **No** — all tokens and keys are placeholders |

GrantLayer is in a **developer-preview / controlled-pilot posture**. The primary use case is cloning the repository, running the backend locally, and evaluating the Product Core flow.

---

## What you can do today

- **Run the local quickstart** — clone the repo, start the backend, and run a minimal safe API smoke path in ~10 minutes.
- **Generate the first verifiable output** — run one local Python example that writes a deterministic GrantLayer-style institutional record without starting the backend.
- **Use the minimal Python SDK** — import the SDK and make typed calls to health, readiness, grants, and audit endpoints.
- **Inspect the LangGraph/LangChain-style example** — review how GrantLayer fits into an agentic workflow without installing LangGraph or LangChain.
- **Review public readiness and feedback docs** — read the readiness pack, feedback log, key-hygiene rules, and dependency manifest.

---

## First verifiable output quickstart

For the fastest public-repo entry point, run the GL-168 first verifiable output
example from the repository root:

```bash
python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json
```

Expected output file:

```text
/tmp/grantlayer_first_output.json
```

The committed deterministic reference output is:

```text
examples/first_verifiable_output.json
```

Read the walkthrough in
[docs/first_verifiable_output.md](docs/first_verifiable_output.md). This path
uses Python standard library modules only, requires no real secrets, requires no
customer data, and is local/demo only. It prepares a first inspectable
GrantLayer-style record; it does not claim production SaaS readiness, and tenant
isolation is not implemented yet.

---

## Developer entry path

| Step | Document | What it covers |
|------|----------|----------------|
| 1 | [docs/first_verifiable_output.md](docs/first_verifiable_output.md) | Run the deterministic first verifiable output example |
| 2 | [docs/ten_minute_quickstart.md](docs/ten_minute_quickstart.md) | Clone, install, start backend, run smoke path |
| 3 | [sdk/python/README.md](sdk/python/README.md) | Import the SDK, make typed calls, handle errors |
| 4 | [docs/langgraph_langchain_integration_example.md](docs/langgraph_langchain_integration_example.md) | See how GrantLayer fits into an agent workflow |
| 5 | [docs/first_developer_feedback_log.md](docs/first_developer_feedback_log.md) | Structured feedback intake after trying the above |

> **Note:** All three steps work with SQLite and local Python only. No cloud service, database subscription, or third-party API is required for the baseline path.

---

## For AI Coding Agents

GrantLayer is local-first and agent-friendly. If you are an AI coding agent, start here:

| File | Purpose |
|------|---------|
| [`AGENTS.md`](AGENTS.md) | Primary agent entry point: rules, boundaries, workflow, and safety |
| [`llms.txt`](llms.txt) | Concise project summary and agent entry links |
| [`llms-full.txt`](llms-full.txt) | Detailed repository map, safe/forbidden areas, and next steps |
| [`docs/agent_quickstart.md`](docs/agent_quickstart.md) | 60-second orientation for first contributions |
| [`docs/agent_task_contract.md`](docs/agent_task_contract.md) | Issue/task specification and final-report format |
| [`docs/agent_integration_manifest.json`](docs/agent_integration_manifest.json) | Machine-readable project metadata |
| [`docs/ten_minute_quickstart.md`](docs/ten_minute_quickstart.md) | Clone → install → start backend → smoke path |
| [`sdk/python/README.md`](sdk/python/README.md) | Minimal Python SDK usage guide |
| [`docs/langgraph_langchain_integration_example.md`](docs/langgraph_langchain_integration_example.md) | How GrantLayer fits into an agentic workflow |

**Important caveats:**
- GrantLayer is in **Developer Preview** — local evaluation and controlled pilot only.
- **No real secrets or customer data** anywhere in the repository.
- **Not production SaaS** — do not deploy to shared multi-tenant infrastructure.
- **Tenant isolation is not implemented** — data shares a single namespace.
- **Public GitHub release has not happened** — explicit approval required (GL-160).

Runtime agent examples are planned for **GL-155 Agent Examples Pack**.

---

## Repository and readiness links

- [CHANGELOG.md](CHANGELOG.md) — Public snapshot and version notes.
- [docs/public_github_readiness_pack.md](docs/public_github_readiness_pack.md) — Readiness checklist, messaging rules, release blockers, and go/no-go criteria before any future public sharing.
- [docs/first_developer_feedback_log.md](docs/first_developer_feedback_log.md) — First structured feedback intake (internal dry-run only; no real external feedback claimed).
- [docs/key_hygiene.md](docs/key_hygiene.md) — Key and secret hygiene rules for the repository.
- [docs/dependency_manifest.md](docs/dependency_manifest.md) — Python runtime and dev dependency manifest.

---

## Safety and limitations

- **Do not use real secrets** — all documentation uses placeholder tokens (e.g. `demo-admin-token-gl146`).
- **Do not use real customer data** — all examples use synthetic identifiers (e.g. `gl146-demo-subject-001`).
- **Production SaaS readiness is not claimed** — the backend has not completed all production-hardening gates required for a shared multi-tenant SaaS.
- **Tenant isolation is not implemented** — the backend does not enforce tenant/workspace boundaries at the data, authorization, or audit layers.
- **Public GitHub release/publication has not happened** — explicit human approval is still required before any public push.
- **GL-169 is public-facing polish only** — this issue prepares quickstart and repository orientation content; it performs no GitHub push and no repository visibility change.
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

## Suggested repository metadata

If and when public publication is approved, the following metadata is recommended:

| Field | Suggested value |
|-------|-----------------|
| Short description | "Developer-preview verification and audit layer for agentic grant workflows." |
| Topics | `grant-management`, `audit-trail`, `compliance`, `agentic-workflows`, `developer-preview`, `python` |
| License | Apache-2.0 (after explicit decision and file addition) |
| Website | None yet — no public landing page or marketing site exists |

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

## Setup

No installation required. Python 3.10+ and stdlib are sufficient.

```bash
git clone https://github.com/Discodone/grantlayer.git
cd grantlayer
```

## Start backend

```bash
cd grantlayer-mvp
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
cd grantlayer-mvp
python3 -m unittest discover -s backend/tests -v
```

Or via script:
```bash
./scripts/test.sh
```

Expected output: **1130 tests, 3 skipped, 0 failures.**

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

## Next steps

| Issue | Title | Purpose |
|-------|-------|---------|
| GL-153 | LICENSE / CONTRIBUTING / SECURITY Decision Pack | Add LICENSE, CONTRIBUTING.md, and SECURITY.md files. |
| GL-154 | AGENTS.md + llms.txt + Agent Integration Manifest | Add agent entry points, task contracts, and integration manifest. |
| GL-155 | Agent Examples Pack | Add ready-to-run agent examples and task contracts. |
| GL-156 | GitHub Issue Templates / Feedback Templates | Create issue templates, PR template, and feedback templates if public publication is approved later. |

---

> This README was polished in **GL-151 Public README / Repo Metadata Polish**, completed blockers were fixed in **GL-152 Public Checklist Blocker Fixes**, and governance files were added in **GL-153 LICENSE / CONTRIBUTING / SECURITY Decision Pack**. It does **not** publish to GitHub, change git remotes, rewrite history, clean secrets from history, change production code, change API behavior, add migrations, change the database schema, add dependencies, implement SDK changes, implement LangGraph/LangChain changes, launch a website or frontend, or claim production SaaS readiness or tenant isolation implementation. All examples use synthetic identifiers and placeholder tokens only.
