# Agent Examples Pack

> **GrantLayer issues time-boxed access grants, enforces them through policy, and records every decision in a verifiable audit trail.**
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

---

## Purpose

This directory contains local-first, dry-run examples for agentic workflows using
GrantLayer concepts. Each script is a standalone Python file that uses only the
standard library — no external API keys, no network calls, and no real secrets.

These examples demonstrate how AI coding agents can interact with GrantLayer
concepts such as evidence review, approval guardrails, audit export, and policy
checks in a safe, deterministic environment.

---

## Status

| Posture | Value |
|---------|-------|
| Maturity | **Developer Preview** — local evaluation and controlled pilot only |
| Production SaaS readiness | **Not claimed** |
| Tenant/workspace isolation | **Not implemented** |
| Real customer data in examples | **No** — all examples use synthetic identifiers |
| Real secrets in examples | **No** — all tokens and keys are placeholders |

GrantLayer is **not a production SaaS**; tenant isolation is not implemented in this release.
No real secrets. No real customer data. Do not deploy to shared multi-tenant
infrastructure without completing the remaining hardening gates.

These examples require **no external API key** and use only Python's standard library.

---

## Quick Start

Run any example directly:

```bash
python3 examples/agents/evidence_review_agent.py
python3 examples/agents/approval_guardrail_agent.py
python3 examples/agents/audit_export_agent.py
python3 examples/agents/policy_check_agent.py
```

Each script prints deterministic JSON output to stdout and uses fake/demo data only.

---

## Example Overview

| Script | Concept | Description |
|--------|---------|-------------|
| `evidence_review_agent.py` | Evidence review | Reviews a demo evidence bundle and produces findings |
| `approval_guardrail_agent.py` | Approval guardrail | Evaluates a request against guardrails and decides approve/block |
| `audit_export_agent.py` | Audit export | Exports demo audit events in a deterministic summary |
| `policy_check_agent.py` | Policy check | Runs a set of demo policy rules and reports pass/fail/warn |

---

## Agent Documentation

- [`AGENTS.md`](../../AGENTS.md) — primary entry point for AI coding agents
- [`docs/agent_quickstart.md`](../agent_quickstart.md) — 60-second orientation
- [`docs/agent_task_contract.md`](../agent_task_contract.md) — issue and branch rules
- [`docs/agent_integration_manifest.json`](../agent_integration_manifest.json) — machine-readable metadata
- [`sdk/python/README.md`](../../sdk/python/README.md) — minimal Python SDK guide
- [`docs/langgraph_langchain_integration_example.md`](../langgraph_langchain_integration_example.md) — LangGraph / LangChain example

---

## Next Steps

The next issue in the public-readiness sequence is:

- **GL-156 GitHub Issue Templates / Feedback Templates**
