# Git History Exposure Review / Public Snapshot Decision

**Status**: Developer Preview — public-readiness review only  
**Issue**: GL-158  
**Prerequisite**: GL-157 Public Secret / Sensitive Data Scan Gate (merged)

---

## Executive Decision

**Do not publish full internal git history.** Use a clean public snapshot for any future public GitHub developer-preview release unless a subsequent manual history audit explicitly approves full history publication.

This document reviews the exposure risk in the GrantLayer private working repository's git history, evaluates available options, and recommends a path forward for GL-159 and GL-160.

---

## Current Posture

GrantLayer is a developer preview. No public GitHub release has occurred. The repository has been developed as a private working repo with a private git remote. The full commit history includes:

- Internal development workflow artifacts
- Commit messages referencing internal tooling and workflow files
- Iterative fixup commits and review artifacts that are not intended for public review
- Possible traces of local terminal sessions, LLM provider output, and intermediate prompt/report artifacts in historical file states
- Branch names and stale refs that reflect internal naming conventions

The current working tree has been vetted through GL-152 through GL-157. However, **the scan gate (GL-157) operates on tracked files in the current working tree only** — it does not deeply scan git history blobs, past commits, or reflog entries.

---

## Inputs Reviewed

| Issue | Title | Relevance |
|---|---|---|
| GL-152 | Public Checklist Blocker Fixes | Resolved blocker items in current tree; does not cover history |
| GL-153 | LICENSE / CONTRIBUTING / SECURITY Decision Pack | Public posture documents present and vetted |
| GL-154 | AGENTS.md + llms.txt + Agent Integration Manifest | Public agent integration artifacts vetted |
| GL-155 | Agent Examples Pack | Example scripts reviewed for safe placeholder use |
| GL-156 | GitHub Issue / Feedback Templates | Public-facing templates reviewed |
| GL-157 | Public Secret / Sensitive Data Scan Gate | Current working tree heuristic scan passes; history not covered |

---

## Exposure Categories Reviewed

### 1. Internal Hostnames

Private git remotes, internal service URLs, and homelab hostnames may appear in historical commits, commit messages, config references, or documentation states that have since been updated. The current working tree scan (GL-157) checks for these but history is not covered.

### 2. Internal Absolute Paths

Historical file states may contain absolute filesystem paths from development environments (e.g. developer home directories, data mount paths). These paths are not appropriate for a public release.

### 3. Local Terminal and Provider Traces

Development sessions may have produced LLM provider API traces, terminal session artifacts, or intermediate output captured in tracked files at points in history that are no longer present in the current working tree.

### 4. Prompt and Final-Report Artifacts

GrantLayer development involved iterative prompt engineering and agent output review. Historical commits may contain draft prompt templates, intermediate agent reports, or raw LLM output that was later removed or replaced.

### 5. Stale Branch Names and Internal Workflow Details

Branch naming conventions and commit messages reference internal issue trackers, internal workflow files, and internal tooling not intended for public visibility.

### 6. Possible Credentials and Secrets in History

The current working tree passes the GL-157 heuristic scan. However, historical commits that added and later removed credentials, tokens, or configuration values are not verified clean without a full forensic history scan. **Full history is not claimed clean.**

### 7. Real Customer Data Risk

No real customer data is present in the current working tree (verified by GL-157). Historical states have not been audited. As a precaution, no customer data exposure risk can be ruled out for full history publication without a complete audit.

### 8. Private Personal Data Risk

No private personal data is present in the current working tree. Historical states are not audited. The same precaution applies as for customer data.

---

## Decision Options

### Option 1: Publish Full History

Publish the full internal git history to a public GitHub repository.

- **Pro**: Transparent development history; complete audit trail for contributors
- **Con**: Exposes all internal workflow artifacts, provider traces, prompt artifacts, stale branch refs, and potentially sensitive historical states without a complete forensic audit
- **Verdict**: **Not recommended** — full history is not claimed clean without explicit forensic audit evidence

### Option 2: Filter or Rewrite Existing History

Use `git filter-repo` or BFG to rewrite history, removing sensitive content.

- **Pro**: Preserves some project history in cleaned form
- **Con**: Destructive and irreversible on the private working repo; requires identifying every sensitive pattern across all historical blobs; high risk of incomplete cleanup; changes all commit SHAs; breaks any existing forks or mirrors
- **Verdict**: **Not recommended for the private working repo** — history rewrite is a destructive operation that should not be performed on the active development repository; if ever needed it should be a separate step on a dedicated copy

### Option 3: Publish Clean Public Snapshot

Create a new public repository (or orphan branch) from the current vetted working tree only, with no internal git history.

- **Pro**: Lower risk; public review of code without internal workflow artifacts; avoids destructive history rewrite on private repo; preserves clean public posture; current tree already vetted through GL-152–GL-157
- **Con**: No public development history; contributors see only the published snapshot commit
- **Verdict**: **Recommended** — preferred path unless a later manual history audit explicitly approves full history publication

### Option 4: Keep Private Until Later

Do not publish yet; continue development privately.

- **Pro**: No exposure risk; allows more time for audit
- **Con**: Delays developer preview; blocks GL-159 / GL-160 dry run exercises
- **Verdict**: **Valid but not the primary recommendation** — GL-159/GL-160 dry run exercises can proceed against a private snapshot without public publication

---

## Recommendation

**Publish a clean public snapshot.**

Use an orphan branch or new public repository initialized from the current vetted working tree. Do not include internal git history in the initial public release.

This is the default path. The full history publication option may be revisited only if a later dedicated forensic history audit produces explicit evidence that the full history is clean and safe for public release.

---

## Rationale

- **Lower risk**: The current working tree is vetted; historical blobs are not.
- **Easier public review**: A clean snapshot is simpler for external contributors to review without internal workflow noise.
- **Avoids exposing internal artifacts**: Provider traces, prompt artifacts, internal workflow details, and stale refs do not belong in a public developer-preview repository.
- **Avoids destructive history rewrite on the private working repo**: Rewriting history is irreversible and should not be performed on the active development repository.
- **Preserves current vetted content and license posture**: The clean snapshot carries the Apache-2.0 license, all public-readiness documents, and the full current tree.
- **Compatible with GL-159 dry run**: A snapshot approach can be validated in GL-159 without performing any actual public publication.

---

## What Clean Public Snapshot Means

A clean public snapshot is a new public repository (or orphan branch) initialized from the current vetted working tree with no prior git history.

**Included in the snapshot:**

- `LICENSE` (Apache-2.0)
- `README.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `AGENTS.md`
- `llms.txt`
- `docs/` (all vetted documents including this one)
- `docs/examples/` (all vetted examples)
- `backend/tests/` (all validation tests)
- `.github/ISSUE_TEMPLATE/` (all issue and feedback templates)
- `.github/pull_request_template.md`
- `scripts/public-secret-sensitive-scan.sh`
- `examples/` (vetted agent examples)
- `sdk/` (vetted SDK)

**Excluded from the snapshot:**

- `.claude/` (internal tooling configuration — never published)
- Internal git remotes and remote configuration
- Internal workflow files from `~/homelab-control/` (these are not tracked in this repo)
- Any file that triggers the GL-157 scan gate with a real blocker

---

## What GL-159 Must Do

GL-159 (GitHub Private Mirror Dry Run) must:

1. Create a private snapshot branch or private mirror repository from the current vetted working tree
2. Verify the resulting tree matches the expected content (no unintended additions or omissions)
3. Run the GL-157 scan gate (`scripts/public-secret-sensitive-scan.sh`) against the snapshot tree and confirm exit 0
4. Run all public-readiness validation tests against the snapshot
5. Verify git remote configuration shows no accidental GitHub remote set
6. Verify `.claude/` is not present in the snapshot tree
7. Verify no private hostnames or internal paths appear in the snapshot tree
8. Verify no accidental GitHub publication occurs during the dry run
9. Document the dry-run result in a structured report artifact

---

## What GL-160 Must Decide

GL-160 (Public GitHub Go/No-Go + Publish) must decide:

1. Whether to publish the clean snapshot to a public GitHub repository
2. Whether the repository metadata (name, description, topics, visibility) is correct for developer preview
3. Whether required release caveats are present and accurate in README and SECURITY
4. Whether the GL-159 dry-run result approves publication
5. Whether the scan gate passes on the final snapshot before publication
6. Whether any new issues discovered during GL-159 must be resolved first

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Historical commits contain credentials or tokens | Low–Medium | High | Clean snapshot avoids exposing history; forensic audit deferred |
| Historical commits contain internal hostnames/paths | Medium | Medium | Clean snapshot excludes history; current tree verified by GL-157 |
| Historical commits contain provider traces or prompt artifacts | Medium | Low–Medium | Clean snapshot avoids exposing history |
| Accidental full history publication during GL-159 dry run | Low | High | GL-159 must verify no GitHub remote set; must not push to public remote |
| Clean snapshot missing required files | Low | Medium | GL-159 tree validation step catches omissions |
| Scan gate false negative in snapshot | Low | Medium | GL-159 must run full scan gate; GL-160 must confirm before publish |
| Overclaim or wrong status in published docs | Low | Medium | All GL-152–GL-158 review docs include mandatory caveats |

---

## Go/No-Go Criteria for Public Release

The following criteria must all be met before GL-160 approves public release:

- [ ] GL-157 scan gate exits 0 on the snapshot tree
- [ ] All GL-158 validation tests pass
- [ ] GL-159 dry run completes without accidental publication
- [ ] GL-159 tree validation confirms expected file set
- [ ] No `.claude/` in snapshot tree
- [ ] No private hostnames or internal paths in snapshot tree
- [ ] Apache-2.0 LICENSE present
- [ ] README and SECURITY contain required caveats (Developer Preview, not production SaaS, tenant isolation not implemented)
- [ ] No real secrets, no real customer data, no private personal data in snapshot tree
- [ ] GL-160 go/no-go review explicitly approves publication

---

## Non-Goals

This document and GL-158 explicitly do **not**:

- Perform any git history rewrite, filtering, or squashing
- Run git filter-repo or BFG
- Delete commits or remove files from history
- Perform secret rotation
- Perform secret-history cleanup
- Publish to GitHub
- Create a public GitHub repository
- Create a mirror repository
- Call the GitHub API
- Change git remotes
- Claim full history is clean (it is not verified)
- Claim production SaaS readiness
- Claim tenant isolation is implemented
- Claim public GitHub release has occurred

---

## Caveats

**Developer Preview**: GrantLayer is a developer preview. It is **not production SaaS** ready for enterprise or multi-tenant deployment.

**Tenant isolation is not implemented**: No workspace or tenant isolation exists. All data sharing a GrantLayer instance shares the same database.

**No real secrets**: This repository does not contain real production credentials, API keys, or tokens.

**No real customer data**: This repository does not contain real grant applicants, customer records, or personal data.

**History not audited**: The full git history has not been forensically audited. Full history publication is not recommended and is not approved by this document.

**No history rewrite performed**: This issue does not perform any git history rewrite. The private working repository's history is unchanged.

**No GitHub publication**: No publication to a public GitHub repository has occurred as part of this issue.

---

## Next Step

**GL-159 GitHub Private Mirror Dry Run**

Using the clean public snapshot approach approved by this document, GL-159 creates a private snapshot, validates the tree, runs the scan gate, and produces a dry-run report without any actual public publication.

After GL-159, **GL-160 Public GitHub Go/No-Go + Publish** makes the final publication decision.
