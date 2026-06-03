# AGENTS.md

> **GrantLayer turns agentic grant workflows into verifiable institutional records.**
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

---

## Project Summary

GrantLayer is a verification, audit, and compliance layer for agentic grant and
funding workflows. It is written in Python and runs locally with SQLite or
PostgreSQL.

This document is the primary entry point for AI coding agents working on the
GrantLayer repository.

---

## Current Status and Caveats

| Posture | Value |
|---------|-------|
| Maturity | **Developer Preview** — local evaluation and controlled pilot only |
| Production SaaS readiness | **Not claimed** |
| Tenant/workspace isolation | **Not implemented** |
| Public GitHub release | **Available** — `https://github.com/Discodone/grantlayer.git` (GL-176) |
| Real customer data in examples | **No** — all examples use synthetic identifiers |
| Real secrets in examples | **No** — all tokens and keys are placeholders |

GrantLayer is **not a production SaaS**. Tenant isolation is not implemented.
Do not deploy to shared multi-tenant infrastructure without completing the
remaining hardening gates.

---

## Start Here

If you are an AI coding agent starting work on GrantLayer, read these files in
order:

1. `README.md` — project overview, status, and developer entry path.
2. `AGENTS.md` — this file: agent-specific rules, task boundaries, and safety.
3. `docs/agent_quickstart.md` — 60-second orientation for first contributions.
4. `docs/public_agent_api_walkthrough_refresh.md` — public agent/API walkthrough for the no-install example path and backend handoff.
5. `docs/agent_task_contract.md` — how issues, branches, and final reports work.
6. `docs/agent_integration_manifest.json` — machine-readable project metadata.
7. `llms.txt` — concise project summary and entry-point links.
8. `llms-full.txt` — detailed repository map, safe/forbidden areas, and next steps.

After the above, pick a task from `docs/agent_task_contract.md` or an open issue.

---

## Local Setup and Validation

### Prerequisites
- Python 3.10+ (Python 3.13 recommended)
- pip, git, bash

### Quick validation
```bash
cd grantlayer-mvp
pip install -r requirements.txt
python3 -m backend
# In another terminal:
curl -s http://127.0.0.1:8765/health | python3 -m json.tool
```

### Targeted validation commands
```bash
# Fast regression — recommended for every agent branch
python3 -m unittest backend.tests.test_security_boundary_regression -v

# Issue-specific validation (example: GL-154)
python3 -m unittest backend.tests.test_gl154_agent_entry_points_manifest -v

# Full backend suite (only in environments with a real long-timeout shell;
# do not run through a 120-second-limited agent wrapper)
scripts/run-full-backend-suite.sh
```

> If you cannot run the full suite before a human merge, report
> `not_run_due_tool_timeout_limit` and let a Fast-Merge agent finish validation.

---

## Safe Default Tasks

These areas are safe for agent contributions **by default**:

- **Documentation** — any `.md` file, especially under `docs/`, `sdk/python/README.md`
- **Tests** — any file under `backend/tests/` that validates behavior without
  changing production code
- **Validation artifacts** — JSON examples and manifests under `docs/examples/gl*/`
- **SDK wrappers** — read-only SDK documentation, typed request/response helpers
  (do not change runtime grant logic)
- **Public readiness docs** — `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`
- **Quickstarts** — developer onboarding guides and smoke-path instructions

These specific files are explicitly expected in agent-friendly issues:
- `docs/ten_minute_quickstart.md`
- `docs/public_agent_api_walkthrough_refresh.md`
- `sdk/python/README.md`
- `docs/langgraph_langchain_integration_example.md`

---

## Forbidden by Default

Unless an issue explicitly overrides these boundaries, agents **must not**:

- Change any file under `backend/src/*` (production backend logic)
- Change `docs/openapi.yaml` (OpenAPI contract)
- Add or modify migrations under `backend/src/migrations/*`
- Change `requirements.txt` or `requirements-dev.txt` (dependencies)
- Change `scripts/*` (dev/prod scripts)
- Change anything under `frontend/*`, `website/*`, or `design/*`
- Stage or commit files under `.claude/` (agent-specific configuration is local)
- Add real secrets, API keys, tokens, or passwords
- Add real customer data (names, addresses, identifiers, etc.)
- Claim production SaaS readiness
- Claim tenant isolation is implemented
- Claim production readiness beyond the current developer-preview / controlled-pilot posture
- Rewrite git history
- Perform secret-history cleanup
- Change git remotes
- Push to GitHub or create a GitHub repository
- Merge to `main` without Fast-Merge agent review

---

For the public no-install walkthrough and agent/API handoff, start with
`docs/public_agent_api_walkthrough_refresh.md`, then read the two runnable
examples and the backend quickstart in order.

## Issue Workflow for Coding Agents

Every agent contribution follows this flow:

1. **Read the issue contract** — every issue references `docs/agent_task_contract.md`
2. **Create a branch** from the latest `main`
3. **Make minimal scoped changes** — only what the issue asks for
4. **Run targeted validation** — run the issue-specific test plus the security
   boundary regression test
5. **Produce a final report** — follow the format in `docs/agent_task_contract.md`
6. **Commit and push the branch** — do NOT merge to `main`
7. **Set disposition** — choose exactly one from:
   - `ready_for_merge`
   - `merged_done`
   - `blocked`
   - `needs_manual_review`
   - `provider_timeout_recovery_needed`

---

## Branch / Merge Separation

- **Coding agents** write code, run targeted tests, and push branches.
- **Fast-Merge agents** review branch diffs, run full validation, merge to `main`,
  and verify `main` health.
- A coding agent should **never** merge its own branch to `main`.
- If a coding agent hits a timeout during full-suite validation, report
  `provider_timeout_recovery_needed` and let a Fast-Merge agent finish.

---

## Final Report Format

At the end of every issue, produce a final report with these sections:

```
GL-<NNN> Coding Final Report

Branch:
- branch name
- base main commit
- commit hash
- pushed to origin: yes/no
- origin branch visible: yes/no
- working tree clean: yes/no

Changed files:
- exact list

Scope:
- (repeat key booleans from the issue contract)

Agent-native coverage:
- (map issue deliverables to yes/no)

Validation:
- targeted test result
- regression test result
- full backend suite result: run / not_run_due_tool_timeout_limit
- failures / errors / timeout yes|no

Disposition:
- ready_for_merge | needs_manual_review | blocked | provider_timeout_recovery_needed
```

See `docs/agent_task_contract.md` for the complete contract and disposition rules.

---

## Security and Public-Readiness Rules

- **No real secrets** — never commit API keys, Bearer tokens, JWTs, encryption keys,
  or passwords. All examples use placeholders like `demo-admin-token-gl146`.
- **No real customer data** — never commit real names, addresses, identifiers, or
  other personal/organizational data. All examples use synthetic identifiers
  like `gl146-demo-subject-001`.
- **No overclaim** — do not claim production SaaS readiness or tenant isolation.
  The repository is publicly available (GL-176). Do not claim production readiness
  beyond the current developer-preview / controlled-pilot posture.
- **Local-first** — all documentation assumes local evaluation with SQLite.
  PostgreSQL is optional.

---

## Exact Safety Phrases for Agent Checks

The following lowercase phrases are intentionally included for agent and test
compatibility:

- tenant isolation is not implemented
- no real secrets
- no real customer data

---

## Current Public Status

The repository is publicly available at `https://github.com/Discodone/grantlayer.git` in a
developer-preview / controlled-pilot posture (GL-176). Agent examples are available
in `examples/langgraph_langchain/`, `examples/first_verifiable_output.py`, and
`examples/grant_lifecycle_evidence_bundle.py` (GL-155, GL-168, GL-189).

Public agent/API walkthroughs are documented in
`docs/public_agent_api_walkthrough_refresh.md`, `docs/first_output_verify_helper.md`,
`docs/grant_lifecycle_evidence_bundle.md`, and
`docs/public_feedback_infrastructure_pack.md`.

---

> This AGENTS.md was created in **GL-154 AGENTS.md + llms.txt + Agent Integration Manifest** and updated in **GL-193 Public Agent/API Walkthrough Refresh**. It does **not** change git remotes, rewrite history, clean secrets from history, change production code, change API behavior, add migrations, change the database schema, add dependencies, implement SDK changes, implement LangGraph/LangChain changes, launch a website or frontend, or claim production SaaS readiness or tenant isolation implementation. All examples use synthetic identifiers and placeholder tokens only.
