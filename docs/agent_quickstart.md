# Agent Quickstart

> **GrantLayer issues time-boxed access grants, enforces them through policy, and records every decision in a verifiable audit trail.**
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

---

## 60-Second Orientation

You are an AI coding agent starting on GrantLayer. Do this in 60 seconds:

1. Read `AGENTS.md` — the primary agent entry point.
2. Read `llms.txt` — concise project summary and entry links.
3. Check `docs/agent_task_contract.md` — understand how issues and final reports work.
4. Check `docs/agent_integration_manifest.json` — machine-readable metadata.
5. If you need the public walkthrough that connects the no-install examples to
   the backend path, read `docs/public_agent_api_walkthrough_refresh.md`.

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
| Clone | `git clone https://github.com/Discodone/grantlayer.git` | Public repository |
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
- The repository is publicly available at `https://github.com/Discodone/grantlayer.git` (GL-176).
  Do not claim production readiness beyond the current developer-preview / controlled-pilot posture.
- Security-sensitive concerns belong in GitHub Security Advisories, not public issues.

---

## Agent Examples

Agent examples are available:
- `examples/first_verifiable_output.py` — first verifiable output, no install required (GL-168)
- `examples/grant_lifecycle_evidence_bundle.py` — second runnable example, no install required (GL-189)
- `docs/public_agent_api_walkthrough_refresh.md` — public agent/API walkthrough and safety guide (GL-193)
- `docs/public_feedback_infrastructure_pack.md` — public feedback routing and Security Advisory guidance (GL-192)
- `examples/langgraph_langchain/grantlayer_agent_example.py` — LangGraph/LangChain integration example (GL-155)

Current public walkthroughs: GL-188 (verify helper), GL-189 (second runnable example), GL-192 (feedback infrastructure), GL-193 (agent/API walkthrough refresh).

---

> This agent_quickstart.md was created in **GL-154 AGENTS.md + llms.txt + Agent Integration Manifest** and updated in **GL-193 Public Agent/API Walkthrough Refresh**. It does **not** change git remotes, rewrite history, clean secrets from history, change production code, change API behavior, add migrations, change the database schema, add dependencies, implement SDK changes, implement LangGraph/LangChain changes, launch a website or frontend, or claim production SaaS readiness or tenant isolation implementation. All examples use synthetic identifiers and placeholder tokens only.
