# GitHub Public Repository Metadata / Publish Gate

**Status:** Developer Preview / publish gate only

---

## Purpose

This document defines the final GitHub repository metadata and the publish gate that must be passed before the clean GrantLayer developer-preview snapshot may be published to public GitHub.

This is a gate document. It does not perform publication. No GitHub publication is performed, no GitHub API is called, no repository is created, no remote is modified, and no history is rewritten in this issue.

---

## Prerequisites

Before any publication attempt:

1. **GL-160 go/no-go decision completed** — `docs/public_github_go_no_go_decision.md` must be present and merged on main.
2. **GL-161 clean public snapshot build completed** — `scripts/build-clean-public-snapshot.sh` must be present and merged on main; the snapshot must have been built and validated locally.
3. **Clean public snapshot required** — Only the output of the GL-161 snapshot build process may be published. No other tree form is acceptable.
4. **Full internal history publication is forbidden** — The full Forgejo git history must never be pushed to a public GitHub repository.
5. **Manual approval required before actual publication** — See the [Required Manual Approval](#required-manual-approval) section.

---

## Repository Metadata

### Recommended Repository Name

```
grantlayer
```

### Alternative Repository Name

```
grantlayer-mvp
```

### Short Description

```
Developer-preview verification and audit layer for agentic grant workflows.
```

### Suggested Topics

```
grant-management
audit-trail
compliance
agentic-workflows
developer-preview
python
openapi
public-sector
```

### License

```
Apache-2.0
```

### Visibility

Public only after manual approval has been given. The repository must remain private or not yet created until the exact manual approval phrase has been recorded.

### Homepage

None until a public website exists. Leave the homepage field blank at initial publication.

---

## Public Positioning

- **Developer Preview** — this is a developer preview, not a stable production release.
- **Not production SaaS** — GrantLayer is not a production SaaS service. It must not be positioned as one.
- **Tenant isolation is not implemented** — multi-tenant isolation has not been implemented. This must not be claimed.
- **No real secrets** — the repository and snapshot must contain no real secrets, tokens, passwords, or credentials.
- **No real customer data** — the repository and snapshot must contain no real customer data.
- **Clean snapshot only** — only the output of the GL-161 clean public snapshot build process may be published.
- **Full internal git history is not published** — the clean snapshot is a flat export; the Forgejo commit history is not included.

---

## Agent-Facing Entry Points

The following paths are the primary entry points for agents integrating with GrantLayer:

| Path | Purpose |
|------|---------|
| `README.md` | Top-level project overview and quickstart links |
| `AGENTS.md` | Agent integration overview and capabilities |
| `llms.txt` | Minimal LLM-readable project summary |
| `llms-full.txt` | Full LLM-readable project documentation |
| `docs/agent_quickstart.md` | Step-by-step agent quickstart |
| `docs/agent_task_contract.md` | Agent task contract and behavioral expectations |
| `docs/agent_integration_manifest.json` | Machine-readable integration manifest |
| `examples/agents/` | Agent integration example scripts |
| `sdk/python/` | Python SDK for programmatic agent access |

---

## GitHub Settings Checklist

Before and after publication:

- [ ] License detected as Apache-2.0 by GitHub
- [ ] Issues enabled
- [ ] Discussions: optional, enable later if needed
- [ ] Wiki: disabled initially
- [ ] Projects: disabled initially unless needed for public roadmap
- [ ] Squash merge preferred (configured as default merge strategy)
- [ ] Branch protection: future follow-up after initial publication
- [ ] Security policy visible (SECURITY.md present in repository root)

---

## First Pinned / Public Content

At initial publication the following must be present and correct:

- `README.md` — project overview, developer preview caveat, quickstart
- `SECURITY.md` — security policy and responsible disclosure process
- `CONTRIBUTING.md` — contribution guidelines
- `docs/agent_quickstart.md` — agent quickstart guide
- `.github/ISSUE_TEMPLATE/` — issue templates for bug reports, feature requests, and agent feedback

---

## Required Manual Approval

No publication may proceed without the repository owner providing the following exact phrase in writing:

> **I approve publishing the clean GrantLayer developer-preview snapshot to public GitHub.**

The approval record must also include:

- Final snapshot path (absolute local path to the snapshot directory or archive)
- Final snapshot tree hash or checksum (if available from the GL-161 build output)
- Target repository owner or GitHub organization
- Target repository name
- Visibility (`public`)
- Confirmation that the full internal git history is not being published (snapshot only)

---

## Publish Gate Checklist

All steps must pass before publication proceeds:

- [ ] Run GL-161 snapshot build (`scripts/build-clean-public-snapshot.sh`)
- [ ] Run public secret/sensitive scan (GL-157 scan gate) on the snapshot output
- [ ] Run GL-162 targeted test (`python3 -m unittest backend.tests.test_gl162_github_public_repository_publish_gate -v`)
- [ ] Run GL-161 regression (`python3 -m unittest backend.tests.test_gl161_clean_public_snapshot_build -v`)
- [ ] Run GL-160 regression (`python3 -m unittest backend.tests.test_gl160_public_github_go_no_go_decision -v`)
- [ ] Run GL-159 regression (`python3 -m unittest backend.tests.test_gl159_github_private_mirror_dry_run -v`)
- [ ] Run full backend suite (`scripts/run-full-backend-suite.sh`)
- [ ] Inspect clean snapshot file list — confirm only expected public files are included
- [ ] Inspect `README.md` — confirm developer preview caveat is present
- [ ] Inspect `SECURITY.md` — confirm security policy is present and correct
- [ ] Inspect `CONTRIBUTING.md` — confirm contribution guidelines are present
- [ ] Inspect `AGENTS.md` — confirm agent integration overview is present
- [ ] Inspect `llms.txt` and `llms-full.txt` — confirm LLM-readable summaries are present
- [ ] Verify no `.claude/` directory or files in snapshot
- [ ] Verify no `.git/` history in snapshot (flat export only)
- [ ] Verify no internal hostnames or internal paths in snapshot
- [ ] Verify no real secrets, tokens, passwords, or credentials in snapshot
- [ ] Verify no real customer data in snapshot
- [ ] Verify no private personal data in snapshot
- [ ] Record manual approval phrase, snapshot path, hash, and target repository details

---

## Abort / Rollback Procedure

If any gate check fails:

1. **Do not publish.** Stop immediately.
2. **Keep Forgejo main as source of truth.** Do not modify Forgejo remotes.
3. **Delete the local snapshot** if it contains unsafe content (real secrets, real customer data, or private personal data).
4. **Investigate and fix** the failing gate before re-running.
5. **If accidental public publication occurs:**
   a. Immediately make the repository private or delete it.
   b. If real secrets were exposed, rotate them immediately.
   c. Document the incident including timestamp, nature of exposure, and remediation steps.
   d. Do not re-publish until all gates pass and a new manual approval is recorded.

---

## GL-163 Post-Public Agent Intake & First Feedback Triage

After successful publication, GL-163 begins with the following inputs:

- Public repository URL
- Publication timestamp
- First-week feedback triage cadence (suggested: daily for week 1)
- Security report handling process (per SECURITY.md responsible disclosure)
- Agent task intake process (per AGENTS.md and issue templates)
- First-week review schedule

---

## Explicit Non-Goals

This issue does **not**:

- Publish to GitHub
- Call the GitHub API
- Create a GitHub repository
- Modify any git remote
- Rewrite git history
- Run git filter-repo or BFG
- Delete commits
- Remove files from history
- Perform secret history cleanup
- Rotate secrets
- Claim that the full git history is clean
- Claim production SaaS readiness
- Claim tenant isolation has been implemented
- Claim a public GitHub release has occurred

---

## Caveats

- **Developer Preview** — this is a developer preview, not a stable production release.
- **Not production SaaS** — GrantLayer is not a production SaaS service.
- **Tenant isolation is not implemented.**
- **No real secrets** are included in the repository or snapshot.
- **No real customer data** is included in the repository or snapshot.
