# Public GitHub Go/No-Go Decision

**Status**: Developer Preview — pre-public decision  
**Issue**: GL-160  
**Prerequisites**: GL-152 through GL-159 (all merged)

---

## Executive Decision

**Decision**: Public release preparation **may proceed to GL-161 only**.

- Public release may proceed only as a **clean public snapshot**.
- **Full internal git history must not be published**.
- Actual publication requires a **separate explicit manual approval** before GL-162.
- No GitHub publication occurs in GL-160.
- No GitHub API is called in GL-160.
- No remotes are changed in GL-160.
- No history rewrite is performed in GL-160.

---

## Required Prerequisites Reviewed

All of the following must be merged to `main` before this decision is finalized:

| Issue | Title | Status |
|---|---|---|
| GL-152 | Public Checklist Blocker Fixes | reviewed |
| GL-153 | LICENSE / CONTRIBUTING / SECURITY Decision Pack | reviewed |
| GL-154 | AGENTS.md + llms.txt + Agent Integration Manifest | reviewed |
| GL-155 | Agent Examples Pack | reviewed |
| GL-156 | GitHub Issue Templates / Feedback Templates | reviewed |
| GL-157 | Public Secret / Sensitive Data Scan Gate | reviewed |
| GL-158 | Git History Exposure Review / Public Snapshot Decision | reviewed |
| GL-159 | GitHub Private Mirror Dry Run | reviewed |

---

## Go Criteria

The following must all be true before this decision allows GL-161 to proceed:

| Criterion | Check |
|---|---|
| Apache-2.0 LICENSE file present | `LICENSE` exists in repo root |
| README.md present with required caveats | includes Developer Preview and not-production-SaaS language |
| CONTRIBUTING.md present | contributor guidelines in place |
| SECURITY.md present with vulnerability disclosure | security policy documented |
| AGENTS.md present | agent integration entrypoint in place |
| llms.txt and llms-full.txt present | LLM-readable entrypoints in place |
| GitHub issue templates present | `.github/ISSUE_TEMPLATE/` non-empty |
| PR template present | `.github/pull_request_template.md` exists |
| Agent examples present | `examples/` contains agent examples |
| GL-157 scan gate script present and validated | `scripts/public-secret-sensitive-scan.sh` exists and passes |
| GL-158 clean snapshot decision documented | `docs/git_history_exposure_review_public_snapshot_decision.md` present |
| GL-159 private mirror dry-run documented | `docs/github_private_mirror_dry_run.md` present |
| GL-157 validation tests pass | `test_gl157_public_secret_sensitive_scan_gate.py` green |
| GL-158 validation tests pass | `test_gl158_git_history_exposure_review_public_snapshot_decision.py` green |
| GL-159 validation tests pass | `test_gl159_github_private_mirror_dry_run.py` green |
| Full backend suite passing on main | all tests green (or documented deferral) |

---

## No-Go Blockers

Any of the following is a hard blocker. Publication must not proceed if any blocker is present:

| Blocker | Description |
|---|---|
| Real secrets | Real API keys, tokens, or credentials in tracked files |
| Real customer data | Real grant applicants, customer records, or any production data |
| Private personal data | Passport numbers, SSNs, national IDs, bank account data |
| Internal hostnames | Internal service URLs or homelab addresses in snapshot |
| Internal absolute paths | Developer home directories or mount paths in snapshot |
| Overclaim: production SaaS | Claiming production SaaS readiness in public release |
| Overclaim: tenant isolation | Claiming tenant isolation is implemented |
| Overclaim: full history clean | Claiming full internal git history has been verified clean |
| Overclaim: public release | Claiming a public GitHub release has occurred before it has |
| Full internal history publication | Publishing `.git/` directory or raw git bundle |

---

## Publication Constraints

If the go decision is issued, the following constraints apply at all times:

- Publish **only a clean public snapshot** — never the full internal git history.
- **Exclude `.claude/`** from the snapshot at all times.
- **Exclude internal remote references** (Forgejo remote configuration, private CI endpoints).
- **Exclude private hostnames** from all snapshot content.
- **Exclude real customer data** from all snapshot content.
- **Exclude private personal data** from all snapshot content.
- **Do not claim full git history is clean** — the internal working history is not verified.
- **Do not publish any file that fails the GL-157 scan gate**.

---

## Required Manual Approval

Manual approval is required before GL-162 may proceed to actual GitHub publication.

### Manual Approval Inputs

Before approving, the owner must confirm:

| Input | Required Value |
|---|---|
| Final snapshot tree hash | Verified hash of the clean snapshot tree |
| Final remote target | Public GitHub repository URL |
| Final repo visibility | public |
| Final repo name | Confirmed repository slug |
| Final repo description | Public-facing description with Developer Preview caveat |
| Final repo topics / labels | Agreed label set |
| Final LICENSE metadata | Apache-2.0 |
| GL-157 scan gate result | Pass (exit code 0) |
| GL-159 dry-run result | Pass |
| Full backend suite result | Pass (or documented deferral) |
| Security caveats verified | Developer Preview, not production SaaS, no real data |

### Approval Phrase

The owner must state the following phrase explicitly before GL-162 proceeds:

> **"I approve preparing the clean GrantLayer developer-preview snapshot for public GitHub publication."**

No automated process may substitute for this explicit approval. Manual approval required for any actual public publication.

---

## GL-161 Handoff

GL-161 (Clean Public Snapshot Build) must:

1. Build the clean public snapshot from the current `main` tree using `git archive` or `git ls-files` (excludes `.git/` and `.claude/`).
2. Validate the full file allowlist against the expected candidate contents from GL-159.
3. Verify all explicit exclusions (`.git/`, `.claude/`, private hostnames, internal paths).
4. Run the GL-157 scan gate (`scripts/public-secret-sensitive-scan.sh`) against the snapshot tree.
5. Run targeted public-readiness tests against the snapshot.
6. Produce a snapshot tree hash for manual approval.
7. Document the result for GL-162 handoff.

GL-161 must not push to any remote. It is a local build and validation step only.

---

## GL-162 Handoff

GL-162 (GitHub Public Repository Metadata / Publish Gate) must:

1. Configure the public repository metadata (name, description, topics, default branch, license).
2. Await explicit manual approval using the phrase specified above.
3. Publish the clean snapshot to GitHub **only after manual approval**.
4. Verify the repository after publication (visibility, file set, no forbidden content, no internal remotes).
5. Confirm no GitHub publication occurs without manual approval.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Accidental publication of full internal git history | Low | High | Snapshot build uses git archive; scope guard blocks `.git/` |
| Real secret present in snapshot | Low | High | GL-157 scan gate must exit 0 before any publication |
| Internal hostname exposed in snapshot | Low | Medium | GL-157 scan gate detects internal hostnames |
| Production SaaS overclaim in public materials | Low | Medium | All public docs include Developer Preview caveat |
| Tenant isolation overclaim | Low | Medium | All public docs include tenant isolation caveat |
| Snapshot published without manual approval | Low | High | GL-162 requires explicit approval phrase before any push |
| Stale scan gate (new secrets added after last scan) | Medium | High | GL-161 re-runs scan gate on the final snapshot tree |
| Scope creep into production backend code | Low | Medium | Scope guard in test suite catches backend/src changes |

---

## Rollback / Abort Procedure

### Before GL-162 (no publication yet)

If any validation step fails before GL-162 executes:

1. **Stop immediately** — do not proceed to GL-162.
2. Do not push any snapshot to any remote.
3. Document the failure in the GL-160 report artifact.
4. Open a blocking issue describing the failure and which go criterion was not met.
5. Do not merge GL-161 until the failure is resolved.

No rollback of git history, remotes, or credentials is needed — no destructive operations are performed in GL-160 or GL-161.

### After GL-162 (if publication occurred and must be reversed)

1. Delete the public GitHub repository immediately.
2. Identify what was exposed (scan gate output, file list).
3. If any real credential was exposed: rotate immediately and notify affected parties.
4. Document the incident in a post-mortem.
5. Determine root cause and fix before re-attempting publication.

---

## Explicit Non-Goals

GL-160 explicitly does **not**:

- Publish to a public GitHub repository
- Create a public GitHub repository
- Call the GitHub API
- Create a mirror repository on any remote
- Add a GitHub remote to the local repository
- Push to GitHub or any unapproved remote
- Rewrite git history
- Run `git filter-repo` or BFG
- Delete commits or remove files from history
- Rotate secrets
- Perform secret-history cleanup
- Claim full git history is clean (the full internal working history is not verified)
- Claim production SaaS readiness
- Claim tenant isolation is implemented
- Claim a public GitHub release has occurred
- No history rewrite is performed in this issue

---

## Caveats

**Developer Preview**: GrantLayer is a developer preview. It is **not production SaaS** ready for enterprise or multi-tenant deployment.

**Tenant isolation is not implemented**: No workspace or tenant isolation exists. All data sharing a GrantLayer instance shares the same database.

**No real secrets**: This repository does not contain real production credentials, API keys, or tokens.

**No real customer data**: This repository does not contain real grant applicants, customer records, or personal data.

**No GitHub publication**: No publication to a public GitHub repository has occurred as part of this issue. No GitHub API was called. No remotes were changed.

**No history rewrite performed**: GL-160 does not perform any git history rewrite. The private working repository's history is unchanged.

**Clean public snapshot required**: Any future public release must be a clean snapshot — not the full internal git history.

**Full internal git history must not be published**: The internal working history contains development artifacts not suitable for public release.

**Manual approval required**: No automated process may substitute for the explicit owner approval phrase before GL-162 proceeds.

---

## Next Step

**GL-161 Clean Public Snapshot Build**

After GL-160 artifacts are validated and merged, GL-161 builds and validates the clean public snapshot locally. The snapshot is not pushed until GL-162 receives explicit manual approval.

**GL-162 GitHub Public Repository Metadata / Publish Gate**

After GL-161 validates the clean snapshot and the owner provides explicit approval, GL-162 configures the public repository metadata and performs the actual publication.
