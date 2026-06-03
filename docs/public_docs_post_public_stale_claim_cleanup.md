# GL-187 Public Docs Post-Public Stale Claim Cleanup

## Issue ID

GL-187

## Title

Public Docs Post-Public Stale Claim Cleanup

## Context

GrantLayer is publicly available on GitHub at `https://github.com/Discodone/grantlayer.git`
(GL-176). Following the GL-186 AI Reviewer Feedback Triage, three AI-simulated external
reviewer reports (Codex Backend/DX, Kimi K2.6 Agent/OSS, Security/Product-Readiness) were
synthesized into 15 normalized findings. Repeated themes included:

- Stale pre-publication language in public-facing docs
- Clone path inconsistencies in quickstart guides
- Stale "public GitHub release not performed" / "visibility decision pending" language in agent files
- Hard-coded outdated test count claim (1130 tests, 0 failures)
- Hypothetical repository metadata section
- Backend quickstart prerequisites not separated from first-verifiable-output path
- GL-155 planned language when GL-155 is complete

This issue addresses the documentation accuracy and trust impact of those findings.

---

## Scope

Documentation and test/artifact only. No backend/src changes, no OpenAPI changes,
no migrations, no DB/schema changes, no dependency changes, no SDK changes,
no frontend/website/design changes, no GitHub workflow changes.

---

## GL-186 Findings Addressed

| Finding ID | Severity | Summary | Addressed |
|------------|----------|---------|-----------|
| F-001 | high | Stale test count in README | Yes |
| F-002 | high | CONTRIBUTING stale public-release status | Yes |
| F-003 | high | README hypothetical metadata section | Yes |
| F-004 | medium | ten_minute_quickstart stale clone URL | Yes |
| F-005 | medium | agent_quickstart internal-source wording | Yes |
| F-006 | low | sourceOfTruth: internal-forgejo in public JSON | Handled (files excluded from snapshot in GL-172) |
| F-007 | medium | README clone/cd inconsistency | Yes |
| F-008 | medium | First-output vs backend quickstart path clarity | Yes |
| F-009 | medium | AGENTS.md/llms-full.txt stale public-state wording | Yes |
| F-010 | low | GL-155 planned vs completed contradiction | Yes |

---

## Files Changed

- `README.md`
- `CONTRIBUTING.md`
- `AGENTS.md`
- `llms-full.txt`
- `llms.txt`
- `docs/ten_minute_quickstart.md`
- `docs/agent_quickstart.md`
- `docs/public_docs_post_public_stale_claim_cleanup.md` (this file)
- `docs/examples/gl187/public_docs_post_public_stale_claim_cleanup.json`
- `backend/tests/test_gl187_public_docs_post_public_stale_claim_cleanup.py`

---

## Stale Claims Removed

1. **README.md** — Removed hard-coded `"1130 tests, 3 skipped, 0 failures"`. Replaced with
   stable instruction: `Run scripts/run-full-backend-suite.sh for the current internal
   validation suite.`

2. **README.md** — Removed `"If and when public publication is approved"` hypothetical framing
   from the repository metadata section. Replaced with current public repository metadata.

3. **README.md** — Removed `cd grantlayer-mvp` inconsistency in the Start backend section.
   After cloning `https://github.com/Discodone/grantlayer.git` the working directory is
   already `grantlayer`; the duplicate `cd` was wrong.

4. **README.md** — Updated `"Runtime agent examples are planned for GL-155"` to reflect
   that GL-155 is complete and examples exist.

5. **CONTRIBUTING.md** — Updated `"Public GitHub release | Not performed — requires explicit
   later approval"` to `"Available"` with public URL.

6. **CONTRIBUTING.md** — Updated stale `"Agent entry points are planned for GL-154"` to
   reflect GL-154 is complete.

7. **CONTRIBUTING.md** — Removed `"Do not claim a public GitHub release has happened unless
   explicitly approved in writing"` (redundant/confusing since repo is now public).

8. **AGENTS.md** — Updated `"Public GitHub release | Not performed"` to `"Available"`.

9. **AGENTS.md** — Updated forbidden list: replaced `"Claim a public GitHub release has
   happened"` with accurate posture guard.

10. **AGENTS.md** — Updated security/overclaim rule to remove stale GL-160 reference.

11. **AGENTS.md** — Replaced stale `"GL-155 Agent Examples Pack ... next planned issue"`
    with current public status and examples reference.

12. **llms-full.txt** — Updated `"formal visibility decision pending (GL-175)"` to reflect
    repository is publicly available.

13. **llms-full.txt** — Updated `"No-Overclaim Rules"` to remove stale
    `"Do not claim a public GitHub release has happened"`.

14. **llms-full.txt** — Updated `"Next Planned Issues"` table (GL-155–GL-160 were stale)
    to current next issues (GL-187–GL-190).

15. **llms.txt** — Updated `"formal visibility decision pending (GL-175)"` to current state.

16. **llms.txt** — Updated stale GL-155 next step to reflect examples available.

17. **docs/ten_minute_quickstart.md** — Replaced placeholder/future clone URL
    `https://github.com/<ORG_OR_USER>/grantlayer-mvp.git` with actual URL
    `https://github.com/Discodone/grantlayer.git`. Updated `cd` path to `cd grantlayer`.

18. **docs/ten_minute_quickstart.md** — Removed `"No public GitHub release yet"` from
    "What This Quickstart Does Not Do".

19. **docs/ten_minute_quickstart.md** — Removed stale approval-required note:
    `"Replace <ORG_OR_USER> with the future public GitHub owner after publication. Until
    then, use the approved internal source."`

20. **docs/agent_quickstart.md** — Updated clone row: replaced `"Use approved internal
    source"` with public URL and `"Public repository"`.

21. **docs/agent_quickstart.md** — Updated `"Public GitHub release is not performed"` to
    reflect public status.

---

## Public Clone / Quickstart Corrections

- `README.md` now uses `git clone https://github.com/Discodone/grantlayer.git` followed
  by `cd grantlayer` consistently.
- `docs/ten_minute_quickstart.md` now uses `git clone https://github.com/Discodone/grantlayer.git`
  and `cd grantlayer`.
- `docs/agent_quickstart.md` now shows the public clone URL in the setup table.
- `README.md` "Choose your path" section clearly separates:
  - Path A: First verifiable output — no install/backend/network required.
  - Path B: Backend quickstart — requires Python virtualenv and `pip install`.

---

## Agent-Facing State Corrections

- `AGENTS.md`: Status table updated — `"Not performed"` → `"Available"` with public URL.
- `AGENTS.md`: Forbidden list updated — no longer says "claim a public GitHub release
  happened" (which would block accurate references to the live public repo).
- `AGENTS.md`: Next step section replaced stale GL-155 planned language with current
  public status and examples reference.
- `llms-full.txt`: All stale `"formal visibility decision pending"` language updated.
- `llms-full.txt`: Next Planned Issues table updated to GL-187–GL-190.
- `llms.txt`: Stale visibility state updated. Stale GL-155 next step updated.
- `docs/agent_quickstart.md`: Clone path updated. Publication status updated.

---

## Source-of-Truth / Internal-Forgejo Handling

The `sourceOfTruth: internal-forgejo` label appeared in three JSON files:
- `docs/examples/gl163/post_public_agent_intake_triage.json`
- `docs/examples/gl164a/public_repo_discovery_metadata.json`
- `docs/examples/gl165/public_changelog_version_anchors.json`

All three were added to the `PUBLIC_EXPORT_EXCLUDE` list in GL-172. They are not
included in the public GitHub snapshot. No changes to those files are needed.

The README Status table row `"Source of truth | Internal Forgejo — public GitHub is a
clean read-only snapshot"` is accurate and informative. It explains the mirror relationship
and is preserved as-is.

The `llms-full.txt` section 2 note was updated to clarify: "Internal Forgejo remains the
development mirror; GitHub is the public read-only snapshot."

---

## Caveats Preserved

All existing accurate caveats are preserved across all changed files:
- Developer/technical preview posture
- Not production SaaS
- Tenant/workspace isolation not implemented
- No real secrets or customer data
- No real customer data in examples (synthetic identifiers only)
- Local evaluation and controlled pilot only
- Security-sensitive reports route to GitHub Security Advisories

---

## Deferred Follow-Ups

| Issue | Title | Reason Deferred |
|-------|-------|-----------------|
| GL-188 | First Output Verify Helper Script | Out of scope for doc-only GL-187; minimal script |
| GL-189 | Second Runnable Example — Grant Lifecycle Evidence Bundle | Requires new example implementation |
| GL-190 | Demo Endpoint Safety Guard / Startup Warning | Requires backend/src change; scoped separately |

---

## Safety Confirmations

- No GitHub push performed
- No visibility change performed
- Internal repo was not pushed directly to GitHub
- No outreach sent
- No reviewer private data included
- No GitHub API label changes performed
- No GitHub issue changes performed
- Production SaaS not claimed
- Tenant isolation not claimed
- No secrets included
- No exploit details included
- No real customer data requested
- No private grant data requested

---

## Non-Goals

- No backend/src changes
- No OpenAPI changes
- No migration changes
- No DB/schema changes
- No dependency manifest changes
- No SDK implementation changes
- No frontend/website/design changes
- No GitHub workflow changes
- No snapshot publish script behavior changes
- No git remote changes
- No public GitHub push
- No visibility change
- No Paperclip status updates
- No verify-first-output helper script (deferred GL-188)
- No second runnable example (deferred GL-189)
- No demo endpoint safety hardening (deferred GL-190)

---

## Explicit Statements

- **No GitHub push performed** — internal branch pushed to internal origin only.
- **No visibility change performed** — repository remains publicly accessible as established in GL-176.
- **Internal repo was not pushed directly to GitHub** — no git remote change, no force push.
- **No production/backend/src changes** — all changes are documentation only.
- **No OpenAPI/migration/DB/dependency changes** — scope is docs/tests/artifacts only.
- **No frontend/website/design changes** — not in scope.

---

## Next Recommended Issue

GL-188 First Output Verify Helper Script — small helper to run `first_verifiable_output.py`
and compare the JSON output against the committed reference output.
