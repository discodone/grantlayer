# Changelog

GrantLayer is a Developer Preview snapshot.

The public GitHub repository is a clean developer-facing snapshot. Internal Forgejo remains the source of truth. This changelog is for public snapshot
orientation and stable version anchors; it is not a full internal history.

## Developer Preview - Public Snapshot

- API-first verification and audit layer for agentic grant workflows.
- Evidence persistence and verification concepts for stored grant workflow
  records.
- Decision provenance for tracing why a grant workflow action was taken.
- Audit logs for operator, agent, grant, execution, and evidence activity.
- Compliance readiness surfaces for local evaluation and controlled pilot
  review.
- Operator controls for local developer-preview workflows.
- Tamper-evidence concepts based on hashes, signatures, and stored evidence
  records.
- Auditor export concepts for review packages and institutional handoff.
- Agent-facing docs:
  - `AGENTS.md`
  - `llms.txt`
  - `llms-full.txt`
  - `docs/agent_quickstart.md`
  - `docs/agent_task_contract.md`
- Python SDK preview for typed local API calls.
- LangGraph/LangChain-style integration example, where present in the public
  snapshot.
- Dashboard as a developer-preview/demo surface, not a production operations
  console.
- Public snapshot hygiene:
  - `backend/` is not published in the clean public snapshot.
  - No real secrets or customer data are included.
  - `.env.example` uses placeholders only.
  - The public repository follows the clean snapshot model rather than exposing
    full internal history.

## Recent Public Hardening Notes

- Public snapshot scanner-clean export.
- Removal of backend-dependent public CI workflow from the clean snapshot.
- Safe `.env.example` with placeholder-only values.
- Dashboard XSS hardening.
- Post-public intake triage workflow.
- GitHub Linguist and repository discovery metadata.

## Caveats

- GrantLayer is not production SaaS.
- Tenant isolation is not implemented.
- GrantLayer is not a replacement for auditors, legal review, or institutional governance.
- Do not use real secrets.
- Do not use real customer data.
- The public repository is a clean snapshot, not the full internal history.

## Public Update Process

Public updates should follow the internal snapshot workflow:

1. Open an internal issue.
2. Create an internal branch.
3. Make scoped changes and run validation.
4. Merge to internal `main` after review.
5. Build a clean public snapshot.
6. Confirm the scanner is clean.
7. Publish the public snapshot through the approved public release process.

## Roadmap-Style Next Areas

- Developer feedback triage.
- Documentation clarity.
- SDK/API examples.
- Integration examples.
- Production-hardening planning.
- Security and runtime hardening.

No dates are promised by this changelog.
