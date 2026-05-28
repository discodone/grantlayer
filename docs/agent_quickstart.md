# Agent Quickstart

> **GrantLayer turns agentic grant workflows into verifiable institutional records.**
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

---

## 60-Second Orientation

You are an AI coding agent starting on GrantLayer. Do this in 60 seconds:

1. Read `AGENTS.md` — the primary agent entry point.
2. Read `llms.txt` — concise project summary and entry links.
3. Check `docs/agent_task_contract.md` — understand how issues and final reports work.
4. Check `docs/agent_integration_manifest.json` — machine-readable metadata.

Done. You are oriented.

---

## Read AGENTS.md and llms.txt First

These two files contain every rule you need:
- Safe default tasks
- Forbidden by default
- Validation commands
- Final report format
- Security and public-readiness rules

---

## Local-First Setup References

GrantLayer is local-first. No cloud service is required.

| Step | Command | Notes |
|------|---------|-------|
| Clone | `git clone <repo>` | Use approved internal source |
| Install | `pip install -r requirements.txt` | Only `cryptography` + `psycopg2-binary` outside stdlib |
| Start | `python3 -m backend` | Runs on `127.0.0.1:8765` |
| Health | `curl -s http://127.0.0.1:8765/health` | Should return `{"status":"ok"}` |

Full details: `docs/ten_minute_quickstart.md`

---

## Targeted Validation Commands

Run these on every branch before declaring ready:

```bash
# Mandatory fast regression
python3 -m unittest backend.tests.test_security_boundary_regression -v

# If your issue has a specific test, run it too
python3 -m unittest backend.tests.test_gl154_agent_entry_points_manifest -v
```

> Do not run the full backend suite through a 120-second-limited agent shell.
> Report `not_run_due_tool_timeout_limit` if you cannot run it.

---

## Safe First Contribution Ideas

If you have no specific issue assigned, these are safe starting points:

- **Update docs** — improve clarity, fix typos, add cross-links.
- **Write a validation test** for an existing issue (e.g. GL-151, GL-152, GL-153).
- **Create a JSON artifact** under `docs/examples/gl*/` that documents a design
  decision or readiness gate.
- **Improve the SDK README** (`sdk/python/README.md`) with better examples or
  error-handling guidance.

---

## Forbidden First Tasks

Do **not** do these as a first contribution unless the issue explicitly allows it:

- Change `backend/src/*` (production code)
- Change `docs/openapi.yaml`
- Add migrations
- Change `requirements.txt` or `requirements-dev.txt`
- Change `scripts/*`
- Touch `frontend/*`, `website/*`, or `design/*`
- Stage or commit `.claude/` files
- Use real secrets or customer data
- Claim production SaaS readiness
- Claim tenant isolation is implemented
- Claim public GitHub release happened
- Rewrite git history or perform secret-history cleanup
- Change git remotes or publish to GitHub
- Merge your own branch to `main`

---

## No Secrets / No Customer Data

- All examples use placeholder tokens (e.g. `demo-admin-token-gl146`).
- All examples use synthetic identifiers (e.g. `gl146-demo-subject-001`).
- Never commit real API keys, tokens, passwords, or encryption keys.
- Never commit real names, addresses, or identifiers.

---

## No Production SaaS / Tenant Isolation Claims

- GrantLayer is **developer preview**. Do not describe it as production-ready SaaS.
- Tenant/workspace isolation is **not implemented**. Do not claim otherwise.
- Public GitHub release is **not performed**. Do not claim otherwise.

---

## Next Step

- **GL-155 Agent Examples Pack** — ready-to-run agent examples and extended task
  contracts. Read the issue when it is created.

---

> This agent_quickstart.md was created in **GL-154 AGENTS.md + llms.txt + Agent Integration Manifest**. It does **not** publish to GitHub, change git remotes, rewrite history, clean secrets from history, change production code, change API behavior, add migrations, change the database schema, add dependencies, implement SDK changes, implement LangGraph/LangChain changes, launch a website or frontend, or claim production SaaS readiness or tenant isolation implementation. All examples use synthetic identifiers and placeholder tokens only.
