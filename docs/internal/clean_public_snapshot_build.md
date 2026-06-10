# Clean Public Snapshot Build

**Status:** Developer Preview / local snapshot only

---

## Caveats

> **Developer Preview:** This is a Developer Preview. GrantLayer is not production SaaS.
> Tenant isolation is not implemented. No real secrets. No real customer data.
> This snapshot is for developer evaluation only. Do not use in production.

---

## Purpose

GL-161 adds a local-only process to build a clean public snapshot candidate from the
vetted current repository tree. The snapshot contains only tracked files after applying
exclusions; it is suitable for review and manual approval before the GL-162 Publish Gate.

Full history publication is disallowed. No GitHub publication occurs in GL-161.
The clean public snapshot contains no real secrets, no real customer data, and
no private personal data.

---

## Prerequisites

- GL-160 go decision allows GL-161 next step (clean public snapshot build)
- Clean public snapshot required by GL-160 before any GitHub publication
- Full history publication disallowed per GL-158 git history exposure decision
- Manual approval required before publication at GL-162
- GL-157 scan gate must have passed on the current working tree
- GL-159 private mirror dry run must have passed on the current working tree

---

## How to Run

**Default (requires clean tracked tree):**

```bash
bash scripts/build-clean-public-snapshot.sh
```

**With custom output directory:**

```bash
bash scripts/build-clean-public-snapshot.sh --output /tmp/grantlayer-public-snapshot
```

**With --allow-dirty (local testing only — not for publication candidates):**

```bash
bash scripts/build-clean-public-snapshot.sh --allow-dirty --output /tmp/grantlayer-snapshot-test
```

---

## What Is Included

The snapshot includes all tracked files except those in the exclusion list below.
Required public-facing file categories:

- `LICENSE` (Apache-2.0)
- `README.md` (with Developer Preview caveat)
- `CONTRIBUTING.md` (contributor guidelines)
- `SECURITY.md` (vulnerability disclosure policy)
- `AGENTS.md` (agent integration entrypoint)
- `llms.txt` (LLM-readable summary)
- `llms-full.txt` (extended LLM summary)
- `backend/src/` (source code for validation)
- `backend/tests/` (test suite)
- `docs/` (design and operational documentation)
- `examples/` (agent examples and integrations)
- `sdk/python/` (Python SDK)
- `scripts/` (validation and operational scripts)
- `.github/` (issue templates, PR template)

---

## What Is Excluded

The following are excluded from the snapshot:

- `.git` directory (full internal git history — not published per GL-158 decision)
- `.claude` directory (internal tooling — must never be published)
- Internal remotes and remote references
- Private hostnames (internal infrastructure)
- Local terminal and provider traces
- Real secrets
- Real customer data
- Private personal data
- Private environment files (`.env`, `.env.*`)
- Compiled Python caches (`__pycache__/`, `*.pyc`)
- Temporary files (`tmp/`, `.tmp/`)
- Build output artifacts (`dist/`, `build/`)

---

## Public Export Exclusions

Certain internal files are excluded from the public snapshot even though they are tracked
in the source repository. These files are internal publication controls — they contain
scanner-triggering patterns intentionally (as test assertions, synthetic examples, or
forbidden-marker reference lists) and are not product documentation for external developers.

**Excluded internal gate/scanner/meta fixtures:**

- Internal GL public-readiness validation tests (`backend/tests/test_gl157_*` through `test_gl162b_*`)
  that contain scanner meta strings as test assertions (e.g., checking that private key
  markers, internal hostnames, and internal home-directory paths are absent from files).
- Internal scanner/meta docs (`docs/public_secret_sensitive_scan_gate.md`,
  `docs/git_history_exposure_review_public_snapshot_decision.md`,
  `docs/github_private_mirror_dry_run.md`, `docs/public_github_go_no_go_decision.md`,
  `docs/clean_public_snapshot_build.md`, `docs/github_public_repository_publish_gate.md`)
  that describe the internal publication control process and intentionally reference
  blocker patterns as examples.
- Internal example JSON fixtures (`docs/examples/gl136/`, `docs/examples/gl157/` through
  `docs/examples/gl162b/`) that contain synthetic private-key markers, internal path
  strings, or internal hostname strings as reference data.

**Important clarifications:**

- Excluding these internal gate fixtures does **not** weaken internal validation.
  The source repository (internal Forgejo) retains all files. The internal scanner
  (`scripts/public-secret-sensitive-scan.sh`) continues to run against the full source tree,
  and internal gate tests remain fully operational.
- Internal Forgejo remains the source of truth. The public snapshot is a curated
  developer-preview export, not a mirror of the full internal repository.
- The public snapshot includes product and developer-preview materials only:
  README, LICENSE, SECURITY, CONTRIBUTING, AGENTS, llms.txt, SDK, agent examples,
  integration docs, and GitHub issue/PR templates.
- The public snapshot must pass `scripts/public-secret-sensitive-scan.sh` after
  `git init` + `git add .` inside the snapshot directory. This is validated by
  `backend/tests/test_gl162b_public_snapshot_scanner_clean_export.py`.
- The full internal git history is not published. Only the clean working-tree
  snapshot may be published per the GL-158 git history exposure decision.

---

## Validation Checklist

Before passing the snapshot to GL-162, complete the following checks:

- [ ] Run `bash scripts/public-secret-sensitive-scan.sh` against current working tree (GL-157)
- [ ] Run GL-161 targeted test: `python3 -m unittest backend.tests.test_gl161_clean_public_snapshot_build -v`
- [ ] Run GL-160 regression: `python3 -m unittest backend.tests.test_gl160_public_github_go_no_go_decision -v`
- [ ] Run GL-159 regression: `python3 -m unittest backend.tests.test_gl159_github_private_mirror_dry_run -v`
- [ ] Run GL-158 regression: `python3 -m unittest backend.tests.test_gl158_git_history_exposure_review_public_snapshot_decision -v`
- [ ] Run security boundary regression: `python3 -m unittest backend.tests.test_security_boundary_regression -v`
- [ ] Run full backend suite before GL-162: `bash scripts/run-full-backend-suite.sh`
- [ ] Inspect `LICENSE` — Apache-2.0 present
- [ ] Inspect `README.md` — Developer Preview caveat present, not production SaaS caveat present
- [ ] Inspect `CONTRIBUTING.md` — contribution guidelines present
- [ ] Inspect `SECURITY.md` — vulnerability disclosure policy present
- [ ] Inspect `AGENTS.md` — agent entrypoint present
- [ ] Inspect `llms.txt` and `llms-full.txt` — LLM-readable summaries present
- [ ] Inspect `.github/` issue and PR templates — present and correct
- [ ] Verify `.git` is NOT in snapshot
- [ ] Verify `.claude` is NOT in snapshot
- [ ] Confirm no internal hostnames in snapshot tree
- [ ] Confirm no private paths in snapshot tree
- [ ] Confirm no real secrets in snapshot tree

---

## Snapshot Handoff to GL-162

Pass the following inputs to the GL-162 GitHub Public Repository Metadata / Publish Gate:

| Input | Value |
|---|---|
| Final snapshot path | Path from `--output` (e.g., `/tmp/grantlayer-public-snapshot`) |
| File count | Printed by script at completion |
| Tree hash / checksum | Run `find <snapshot-path> -type f \| sort \| xargs sha256sum \| sha256sum` |
| Validation summary | All checklist items above: pass / skip / deferred |
| Manual approval inputs | Required by GL-162 before any GitHub publication |

GL-162 requires explicit manual approval using the required approval phrase
before any publication to GitHub occurs. No publication is performed until
manual approval is granted.

---

## Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| Tracked `.env` or secret file included | Critical | grep exclusion in script; scan gate verification |
| `.claude/` tooling included | Critical | grep exclusion `^\.claude`; post-copy assertion in script |
| Full `.git/` history included | Critical | tar uses git ls-files (not cp -r); post-copy assertion |
| Private hostname in tracked file | High | GL-157 scan gate; `test_gl161_clean_public_snapshot_build.py` |
| Snapshot used for publication without approval | High | GL-162 requires explicit manual approval phrase |
| Dirty tree snapshot used as release candidate | Medium | Script refuses dirty tree by default; `--allow-dirty` explicit flag required |
| Over-claim of production readiness | Medium | Caveats required in README.md and docs |

---

## Abort / Rollback Procedure

**If the script fails:**
- Check the error message (dirty tree, non-empty output dir, missing LICENSE)
- Fix the reported issue and re-run
- The output directory is not created unless the script succeeds step 2; if partially created, remove it manually and re-run

**If the snapshot contains unexpected files:**
- Do not pass the snapshot to GL-162
- Remove the snapshot directory
- Investigate the git ls-files output: `git ls-files | grep -v '^\.claude' | grep -v '^\.env'`
- Fix any tracked files that should not be public, re-commit on a separate remediation branch
- Re-run the script after remediation is complete and merged

**If the scan gate reports issues:**
- Do not pass the snapshot to GL-162
- Review the scan output
- Remediate flagged content on a separate branch
- Merge remediation, then re-run the snapshot build

---

## Explicit Non-Goals

- **No GitHub publication** in GL-161
- **No GitHub API** calls in GL-161
- **No public repo created** in GL-161
- **No remote changes** of any kind in GL-161
- **No history rewrite** performed in GL-161
- **No secret cleanup / rotation** in GL-161 (use a separate remediation process)
- **No production SaaS readiness** claimed — this is a Developer Preview only
- **No tenant isolation implementation** — tenant isolation is not implemented
- **No full history clean claimed** — full internal git history has not been forensically audited

---

## Caveat Summary

This artifact is a **Developer Preview** — local snapshot build tooling and documentation
for use in the GrantLayer developer-preview public release preparation pipeline.

- **Not production SaaS.** GrantLayer is not production SaaS in this release.
- **Tenant isolation is not implemented.** Do not use for multi-tenant scenarios.
- **No real secrets.** No real secrets are included in this snapshot or its documentation.
- **No real customer data.** No real customer data is included.
- **Clean public snapshot.** The snapshot contains only tracked public-facing files.
- **Full history publication disallowed.** The full internal git history must not be published.
  Only this clean snapshot may be published per the GL-158 git history exposure decision.
- **Manual approval required.** Publication to GitHub requires explicit manual approval at GL-162.
- **No GitHub publication** occurs in GL-161. Publication awaits GL-162.
- **No history rewrite** is performed. The snapshot is a working-tree copy, not a filtered history.
