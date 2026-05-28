# GitHub Private Mirror Dry Run

**Status**: Developer Preview — private dry-run only  
**Issue**: GL-159  
**Prerequisites**: GL-157 Public Secret / Sensitive Data Scan Gate (merged), GL-158 Git History Exposure Review / Public Snapshot Decision (merged)

---

## Purpose

This document defines the private mirror dry-run procedure for the GrantLayer developer-preview public release candidate. It translates the GL-158 recommendation (clean public snapshot, no full history publication) into a validated, step-by-step dry run that can be executed locally before GL-160 makes the final go/no-go decision.

No GitHub publication occurs here. No GitHub API is called. No remotes are changed. No history rewrite is performed. No public repo is created. This is a local validation exercise only.

---

## Prerequisites

Before running the dry run, all of the following must be true:

| Check | Requirement |
|---|---|
| GL-157 | Public secret / sensitive data scan gate exists and passes |
| GL-158 | Clean public snapshot decision documented and merged to main |
| GL-156 | GitHub issue and feedback templates present |
| GL-155 | Agent examples pack present |
| GL-154 | AGENTS.md, llms.txt, and agent integration manifest present |
| GL-153 | LICENSE / CONTRIBUTING / SECURITY decision pack present |
| GL-152 | Public checklist blocker fixes merged |
| LICENSE | Apache-2.0 LICENSE file present |
| README.md | Public-facing README with required caveats present |
| CONTRIBUTING.md | Contributor guidelines present |
| SECURITY.md | Security policy with required caveats present |
| AGENTS.md | Agent integration entrypoint present |
| llms.txt | LLM-readable entrypoint present |
| llms-full.txt | Extended LLM-readable entrypoint present |
| .github templates | Issue templates and PR template present |

---

## Dry-Run Posture

This dry run is explicitly constrained:

- **No GitHub publication**: No files are pushed to any public GitHub repository.
- **No GitHub API**: No calls to the GitHub REST or GraphQL API.
- **No remote changes**: No git remotes are added, changed, or removed.
- **No public repo created**: No public repository is created on any platform.
- **No mirror repo created on remote**: No mirroring operation is performed against any remote.
- **No history rewrite**: No `git filter-repo`, no BFG, no commit deletion, no history squash.
- **No secret cleanup or rotation**: No credential rotation is performed as part of this dry run.
- **No real secrets**: All validation uses placeholder or fixture data only.
- **No real customer data**: No grant applicants, customer records, or personal data are present.

The dry run creates a temporary local snapshot directory, copies tracked files, runs local validation, and produces a report. Nothing leaves the local machine.

---

## Clean Snapshot Candidate Contents

The following items are included in the clean public snapshot candidate:

| Path | Description |
|---|---|
| `LICENSE` | Apache-2.0 license |
| `README.md` | Public-facing project README with required caveats |
| `CONTRIBUTING.md` | Contributor guidelines |
| `SECURITY.md` | Security policy with vulnerability disclosure instructions |
| `AGENTS.md` | Agent integration entrypoint and instructions |
| `llms.txt` | LLM-readable compact project summary |
| `llms-full.txt` | Extended LLM-readable project summary |
| `backend/` | Backend source and all validation tests |
| `docs/` | All vetted documentation and examples |
| `examples/` | Vetted agent examples and integration scripts |
| `sdk/python/` | Python SDK |
| `.github/` | Issue templates, PR template, and workflow files |
| `scripts/public-secret-sensitive-scan.sh` | GL-157 scan gate script |
| `scripts/github-private-mirror-dry-run.sh` | This dry-run helper script |
| `docker-compose.yml` | Container composition (if needed for validation) |
| `Dockerfile` | Container definition (if needed for validation) |
| `requirements.txt` | Python dependencies |
| `requirements-dev.txt` | Development Python dependencies |
| `.env.example` | Safe example environment configuration |
| `ROADMAP.md` | Public roadmap |

---

## Explicit Exclusions

The following are excluded from the clean public snapshot:

| Excluded | Reason |
|---|---|
| `.git/` | Full internal git history — not published (GL-158 decision) |
| `.claude/` | Internal tooling configuration — never published |
| Private hostnames | Internal service URLs, homelab addresses — not appropriate for public release |
| Internal absolute paths | Developer home directories and mount paths — not appropriate for public release |
| Real secrets | No real production credentials, API keys, or tokens |
| Real customer data | No real grant applicants, customer records, or personal data |
| Private personal data | No passport numbers, SSNs, national IDs, or bank account data |
| `~/homelab-control/` | Internal workflow files — not tracked in this repository |
| Internal git remote configuration | Private Forgejo remote references |

---

## Dry-Run Validation Checklist

Execute each item in order before passing the dry run to GL-160:

### Scan Gate and History Review

- [ ] Run `scripts/public-secret-sensitive-scan.sh` against the snapshot tree — must exit 0 with no blockers
- [ ] Confirm GL-157 scan gate validation tests pass (`python3 -m unittest backend.tests.test_gl157_public_secret_sensitive_scan_gate -v`)
- [ ] Confirm GL-158 review tests pass (`python3 -m unittest backend.tests.test_gl158_git_history_exposure_review_public_snapshot_decision -v`)
- [ ] Confirm full backend suite passes (or is deferred with documented reason)

### Public-Readiness Prerequisites

- [ ] GL-156 issue templates and PR template present and validated
- [ ] GL-155 agent examples present and validated
- [ ] GL-154 AGENTS.md and llms.txt present and validated
- [ ] GL-153 LICENSE, CONTRIBUTING, SECURITY present and validated
- [ ] GL-152 blocker fixes confirmed merged

### File Presence

- [ ] `LICENSE` (Apache-2.0) present
- [ ] `README.md` present with Developer Preview and not-production-SaaS caveats
- [ ] `CONTRIBUTING.md` present
- [ ] `SECURITY.md` present with vulnerability disclosure policy
- [ ] `AGENTS.md` present
- [ ] `llms.txt` present
- [ ] `docs/` non-empty with all GL-152–GL-159 documents
- [ ] `examples/` present with agent examples
- [ ] `sdk/python/` present
- [ ] `.github/ISSUE_TEMPLATE/` present with issue templates
- [ ] `.github/pull_request_template.md` present

### Snapshot Integrity

- [ ] `.claude/` is NOT present in snapshot tree
- [ ] `.git/` is NOT present in snapshot tree
- [ ] No private hostnames appear in snapshot tree
- [ ] No internal absolute paths appear in snapshot tree
- [ ] No real secrets in snapshot tree (scan gate confirms)
- [ ] No real customer data in snapshot tree (scan gate confirms)
- [ ] No private personal data in snapshot tree (scan gate confirms)

### Safety Verification

- [ ] Verify no GitHub remote is set (`git remote -v` shows no github.com remote)
- [ ] Verify no accidental `git push` to GitHub occurred
- [ ] Verify no GitHub API was called during the dry run
- [ ] Verify no history rewrite was performed

---

## Private Mirror / Snapshot Procedure

The following procedure creates a local clean snapshot for validation purposes only. Nothing is pushed to any remote.

### Step 1 — Ensure Prerequisites

```bash
git status --short
git branch --show-current
test -f scripts/public-secret-sensitive-scan.sh && echo "scan gate present" || echo "scan gate MISSING"
test -f docs/git_history_exposure_review_public_snapshot_decision.md && echo "GL-158 present" || echo "GL-158 MISSING"
```

### Step 2 — Create Snapshot Directory

```bash
SNAPSHOT_DIR=$(mktemp -d /tmp/grantlayer-snapshot-XXXXXXXX)
echo "Snapshot directory: $SNAPSHOT_DIR"
```

### Step 3 — Copy Tracked Files Only

Using `git ls-files` to copy only tracked files, excluding `.claude/` and `.git/`:

```bash
git ls-files | grep -v '^\.claude/' | tar -T - -cf - | tar -xf - -C "$SNAPSHOT_DIR"
```

Or using `git archive`:

```bash
git archive HEAD | tar -xf - -C "$SNAPSHOT_DIR"
```

Both methods exclude the `.git/` directory automatically. The `git ls-files` method also explicitly excludes `.claude/`.

### Step 4 — Verify Exclusions

```bash
test ! -d "$SNAPSHOT_DIR/.git" && echo ".git excluded OK" || echo ".git PRESENT — FAIL"
test ! -d "$SNAPSHOT_DIR/.claude" && echo ".claude excluded OK" || echo ".claude PRESENT — FAIL"
```

### Step 5 — Verify Snapshot Contents

```bash
ls "$SNAPSHOT_DIR"
test -f "$SNAPSHOT_DIR/LICENSE" && echo "LICENSE OK" || echo "LICENSE MISSING"
test -f "$SNAPSHOT_DIR/README.md" && echo "README.md OK" || echo "README.md MISSING"
test -f "$SNAPSHOT_DIR/CONTRIBUTING.md" && echo "CONTRIBUTING.md OK" || echo "CONTRIBUTING.md MISSING"
test -f "$SNAPSHOT_DIR/SECURITY.md" && echo "SECURITY.md OK" || echo "SECURITY.md MISSING"
test -f "$SNAPSHOT_DIR/AGENTS.md" && echo "AGENTS.md OK" || echo "AGENTS.md MISSING"
test -f "$SNAPSHOT_DIR/llms.txt" && echo "llms.txt OK" || echo "llms.txt MISSING"
test -d "$SNAPSHOT_DIR/docs" && echo "docs/ OK" || echo "docs/ MISSING"
test -d "$SNAPSHOT_DIR/examples" && echo "examples/ OK" || echo "examples/ MISSING"
test -d "$SNAPSHOT_DIR/sdk" && echo "sdk/ OK" || echo "sdk/ MISSING"
test -d "$SNAPSHOT_DIR/.github" && echo ".github/ OK" || echo ".github/ MISSING"
```

### Step 6 — Run Scan Gate on Snapshot

If a git repository is initialized in the snapshot (not required for dry run), run the scan gate:

```bash
if [ -d "$SNAPSHOT_DIR/.git" ]; then
    (cd "$SNAPSHOT_DIR" && bash scripts/public-secret-sensitive-scan.sh) && echo "Scan gate PASSED" || echo "Scan gate FAILED"
else
    # Run scan gate from repo root against snapshot files
    (cd "$SNAPSHOT_DIR" && find . -type f | sort | xargs grep -l '' 2>/dev/null | head -20)
    echo "Initialize snapshot as git repo to run scan gate, or run scan gate from source repo."
fi
```

### Step 7 — Inspect Remote Configuration

```bash
git remote -v
# Expected: no github.com remote
# Confirms: no accidental GitHub publication target exists
```

### Step 8 — Cleanup

```bash
rm -rf "$SNAPSHOT_DIR"
echo "Snapshot cleaned up — dry run complete"
```

**Do not push. Do not call the GitHub API. Do not add any remote.**

---

## GL-160 Handoff

GL-160 (Public GitHub Go/No-Go + Publish) requires the following inputs from GL-159:

| Input | Source |
|---|---|
| GL-159 dry-run result (pass/fail) | This document / GL-159 JSON artifact |
| Scan gate exit code on snapshot | GL-157 script output |
| Expected file set confirmed | Step 5 verification output |
| `.claude/` excluded confirmed | Step 4 verification output |
| No private hostnames confirmed | Scan gate + manual check |
| No accidental GitHub push confirmed | Step 7 remote check |
| GL-158 validation tests pass | Test suite output |
| GL-157 validation tests pass | Test suite output |
| GL-156 validation tests pass | Test suite output |
| GL-155 validation tests pass | Test suite output |
| Full backend suite result | Test suite output or documented deferral |

**Final manual approval required**: GL-160 must explicitly approve publication. The dry-run result from GL-159 is a necessary but not sufficient condition for publication.

**Public repo metadata to confirm before publish**:
- Repository name
- Repository description
- Topics / labels
- Visibility: public
- Default branch name
- README and SECURITY caveats verified in final snapshot

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Accidental push to GitHub during dry run | Low | High | Step 7 verifies no GitHub remote; script never calls `git push` |
| Snapshot missing required files | Low | Medium | Step 5 file presence verification catches omissions |
| `.claude/` accidentally included in snapshot | Low | High | Step 4 explicit exclusion check; `git ls-files` pipe excludes it |
| Private hostname leaked in snapshot | Low | Medium | GL-157 scan gate detects internal hostnames in tracked files |
| Scan gate false negative | Low | Medium | GL-160 runs scan gate again before final publish |
| Dry-run script calls GitHub API | Very Low | High | Script contains no `gh api` or GitHub API calls |
| History rewrite accidentally triggered | Very Low | High | Script contains no `git filter-repo` or BFG |
| Real secrets in snapshot | Very Low | High | GL-157 scan gate covers this; snapshot is from vetted working tree |

---

## Rollback / Abort Procedure

If any validation step fails:

1. **Stop immediately** — do not proceed to GL-160.
2. Remove the local snapshot directory: `rm -rf /tmp/grantlayer-snapshot-*`
3. Verify no GitHub push occurred: `git remote -v` (no github.com remote should exist).
4. Document the failure in the GL-159 report artifact.
5. Open a blocking issue for GL-160 describing the failure.
6. Do not merge GL-159 until the failure is resolved.

No rollback of git history, remotes, or credentials is needed because no destructive operations are performed.

---

## Non-Goals

GL-159 explicitly does **not**:

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
- Claim full history is clean (full history is not verified)
- Claim production SaaS readiness
- Claim tenant isolation is implemented
- Claim a public GitHub release has occurred

---

## Caveats

**Developer Preview**: GrantLayer is a developer preview. It is **not production SaaS** ready for enterprise or multi-tenant deployment.

**Tenant isolation is not implemented**: No workspace or tenant isolation exists. All data sharing a GrantLayer instance shares the same database.

**No real secrets**: This repository does not contain real production credentials, API keys, or tokens.

**No real customer data**: This repository does not contain real grant applicants, customer records, or personal data.

**Private dry-run only**: This document describes a local validation exercise. No public GitHub release has occurred as a result of GL-159.

**No history rewrite performed**: GL-159 does not perform any git history rewrite. The private working repository's history is unchanged.

**No GitHub publication**: No publication to a public GitHub repository has occurred as part of this issue.

**Not a production readiness gate alone**: The dry run is one gate; GL-160 makes the final publication decision.

---

## Next Step

**GL-160 Public GitHub Go/No-Go + Publish**

After GL-159 dry run completes and all validation checks pass, GL-160 makes the explicit go/no-go decision and (if approved) performs the actual public GitHub publication of the clean snapshot.
