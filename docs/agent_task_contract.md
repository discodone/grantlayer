# Agent Task Contract

> **GrantLayer turns agentic grant workflows into verifiable institutional records.**
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

---

## Purpose

This document defines the standard task contract for AI coding agents working on
GrantLayer. Every issue is a contract. Agents must follow the contract structure,
produce minimal scoped changes, run validation, and produce a final report.

---

## Task Specification Structure

Each issue must define at minimum:

### Issue ID
A unique identifier such as `GL-154`.

### Goal
One sentence describing what the agent must accomplish.

### Expected Changed Files
A concrete list of files the agent should create or modify.

### Allowed Files (if necessary)
Files that may be touched if the issue requires it, but are not the primary
deliverables.

### Forbidden Files
Files that must not be touched unless the issue explicitly overrides the default
forbidden list. Default forbidden areas:
- `backend/src/*`
- `docs/openapi.yaml`
- `backend/src/migrations/*`
- `requirements.txt`, `requirements-dev.txt`
- `scripts/*`
- `frontend/*`, `website/*`, `design/*`
- `.claude/*` (do not stage or commit)
- `sdk/python/grantlayer_client.py`
- `examples/langgraph_langchain/grantlayer_agent_example.py`

### Acceptance Criteria
A checklist of concrete, verifiable outcomes.

### Validation Commands
Specific test commands that must pass before the branch is declared ready.

### Final Report
The agent must produce a final report in the exact format defined below.

---

## Branch and Merge Roles

- **Coding agents** create branches, write code, run targeted tests, push
  branches, and produce final reports. They **must not** merge to `main`.
- **Fast-Merge agents** review branch diffs, run full validation (including the
  full backend suite when possible), merge to `main`, and verify `main` health.

---

## Validation Policy

1. Run the issue-specific test (if provided).
2. Run `backend.tests.test_security_boundary_regression`.
3. Run the previous issue's validation test to confirm no regression.
4. If the environment supports it, run `scripts/run-full-backend-suite.sh`.
   If the agent shell has a 120-second timeout limit, report
   `not_run_due_tool_timeout_limit` instead of failing.

---

## Loop-Control Policy

- Do not run the full backend suite repeatedly through a 120-second-limited
  wrapper.
- Verify git status once, then proceed. Do not loop on `git status` or
  `git rev-parse`.
- If a test fails, fix the cause, re-run the targeted test, and move on.
- Avoid repeated git-status/git-rev-parse loops. Verify once, then proceed.

---

## Public-Readiness Safety Policy

- **No public GitHub publish** unless an explicit go/no-go issue (e.g. GL-160)
  has been completed and validated.
- **No production SaaS readiness claim** — never describe GrantLayer as
  production-ready SaaS in docs, issues, or code.
- **No tenant isolation implementation claim** — clearly state that
  tenant/workspace boundaries are not implemented.
- **No real secrets** — all examples use placeholder tokens.
- **No real customer data** — all examples use synthetic identifiers.
- **No rewrite of history** — agent issues do not perform git history cleanup.

---

## Disposition Values

At the end of every issue, the agent must choose exactly one disposition:

| Value | Meaning |
|-------|---------|
| `ready_for_merge` | All tests pass, scope is clean, branch is pushed. Ready for Fast-Merge agent. |
| `merged_done` | The Fast-Merge agent has already merged this branch to `main`. |
| `blocked` | A hard blocker prevents completion (missing dependency, upstream failure, scope conflict). |
| `needs_manual_review` | The work is complete but requires human review before merge (uncertain scope, edge case). |
| `provider_timeout_recovery_needed` | The agent hit a tool timeout (e.g. 120s shell limit) and could not finish full validation. A Fast-Merge agent with a real long-timeout environment must finish. |

---

## Example Final Report Skeleton

```
GL-<NNN> Coding Final Report

Branch:
- branch name: gl-<nnn>-<short-name>
- base main commit: <hash>
- commit hash: <hash>
- pushed to origin: yes/no
- origin branch visible: yes/no
- working tree clean: yes/no

Changed files:
- file1
- file2
- ...

Scope:
- (one line per key boolean from the issue acceptance criteria)
- docs/test/manifest only: yes/no
- production code changed: must be no
- backend/src changed: must be no
- ...

Agent-native coverage:
- (map issue deliverables to yes/no)

Validation:
- targeted test result: pass/fail/not_run
- regression test result: pass/fail/not_run
- full backend suite result: run / not_run_due_tool_timeout_limit
- failures: N
- errors: N
- timeout: yes/no

Disposition:
- ready_for_merge | needs_manual_review | blocked | provider_timeout_recovery_needed
```

---

## Caveats

- This contract does **not** authorize public GitHub publication.
- This contract does **not** authorize production SaaS readiness claims.
- This contract does **not** authorize tenant isolation implementation claims.
- This contract does **not** authorize the use of real secrets or real customer data.

---

> This agent_task_contract.md was created in **GL-154 AGENTS.md + llms.txt + Agent Integration Manifest**. It does **not** publish to GitHub, change git remotes, rewrite history, clean secrets from history, change production code, change API behavior, add migrations, change the database schema, add dependencies, implement SDK changes, implement LangGraph/LangChain changes, launch a website or frontend, or claim production SaaS readiness or tenant isolation implementation. All examples use synthetic identifiers and placeholder tokens only.
