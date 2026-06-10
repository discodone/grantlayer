# GL-171 Public Release / GitHub Snapshot Readiness + Private Data Safety Review Gate

**Issue:** GL-171
**Review date:** 2026-06-01
**Base commit reviewed:** `db6979122129e9ea3970a2da757da7566e26de8f`
**Branch:** `gl-171-public-release-github-snapshot-readiness-review`
**Reviewer:** GrantLayer Senior Review Agent

---

## Non-Goals

- No GitHub push performed.
- No repository visibility change performed.
- No backend/src changes.
- No OpenAPI, migration, database-schema, or dependency changes.
- No SDK implementation changes.
- No frontend, website, or design changes.
- No snapshot publish script behavior changes.
- No git remote changes.
- No force push.
- No secret handling changes.
- No Paperclip references or status updates.

This review is **read-only**. All findings are advisory and for the next publish issue.

---

## Review Scope

| Area | Checked |
|------|---------|
| README.md — canonical status source | Yes |
| SECURITY.md — canonical security caveat source | Yes |
| docs/first_verifiable_output.md | Yes |
| docs/ten_minute_quickstart.md | Yes |
| examples/first_verifiable_output.py + examples/first_verifiable_output.json | Yes |
| docs/demo_script.md | Yes |
| docs/sprint_2_plan.md | Yes |
| docs/public_secret_sensitive_scan_gate.md | Yes |
| docs/examples/gl163/, gl164a/, gl165/, gl169/, gl170/ | Yes |
| scripts/build-clean-public-snapshot.sh — exclusion list | Yes |
| Public snapshot exclusion inventory | Yes |
| Private data / secret scan across public-facing docs and examples | Yes |

---

## Checked Files / Areas

1. README.md — status table, safety section, quickstart, developer entry path
2. SECURITY.md — supported status, caveat table, data-handling rules
3. docs/first_verifiable_output.md — discoverability, run command, caveats
4. docs/ten_minute_quickstart.md — setup path, caveats, run command
5. examples/first_verifiable_output.py — deterministic output script
6. examples/first_verifiable_output.json — committed deterministic reference output
7. docs/demo_script.md — internal path exposure check
8. docs/sprint_2_plan.md — Paperclip reference check
9. docs/public_secret_sensitive_scan_gate.md — internal path in examples check
10. docs/examples/gl163/, gl164a/, gl165/ — `sourceOfTruth` label check
11. scripts/build-clean-public-snapshot.sh — exclusion list completeness
12. Heuristic scan: raw tokens, private keys, email addresses, customer data, private hostnames

---

## Checks Performed

| Check | Result |
|-------|--------|
| README.md is single canonical status source (GL-170) | PASS |
| SECURITY.md is single canonical security caveat source (GL-170) | PASS |
| No duplicated broad status blocks in non-canonical docs (GL-170) | PASS |
| GrantLayer described as Developer Preview, not production SaaS | PASS |
| Tenant isolation described as not implemented | PASS |
| No real secrets in public docs | PASS |
| No real customer data in public docs | PASS |
| No private email addresses in public docs | PASS |
| No raw tokens, passwords, private keys | PASS |
| No private absolute paths in non-excluded public docs | CAUTION (see F-001) |
| No internal hostnames or URLs | PASS |
| `internal-forgejo` label not a URL or credential | PASS (label only) |
| `internal-forgejo` label disclosure in non-excluded example artifacts | CAUTION (see F-002) |
| `docs/demo_script.md` in snapshot exclusion list | FAIL — see F-001 |
| `docs/sprint_2_plan.md` in snapshot exclusion list | PASS — excluded |
| `docs/public_secret_sensitive_scan_gate.md` in snapshot exclusion list | PASS — excluded |
| first_verifiable_output example runs and matches committed output | PASS |
| Run command accurate in README and docs/first_verifiable_output.md | PASS |
| docs/first_verifiable_output.md discoverable from README | PASS |
| examples/first_verifiable_output.json committed deterministic reference | PASS |
| No GitHub push instruction in any reviewed file | PASS |
| Publication requires explicit human approval (visible in docs) | PASS |
| GL-162 publish gate process documented | PASS |
| No visibility-change instruction in any reviewed file | PASS |
| No history rewrite instruction in any reviewed file | PASS |
| README "GL-169 is public-facing polish only" label (now stale but accurate) | LOW (see F-003) |

---

## Area 1: Public-Facing Correctness

README.md and SECURITY.md are the canonical status sources after GL-170 deduplication. Both correctly state:

- Developer Preview / GL-0.1 posture
- Production SaaS readiness **not claimed**
- Tenant/workspace isolation **not implemented**
- Public GitHub release **not performed** — requires explicit later approval
- No real secrets in examples
- No real customer data in examples

The GL-170 deduplication removed repeated broad status blocks from non-canonical docs and replaced them with README.md pointers. The quickstart (docs/ten_minute_quickstart.md), developer adoption docs, and readiness pack now correctly delegate canonical status to README.md. No stale or duplicated broad status blocks were found in the reviewed scope.

One low-severity wording note: the README.md Safety section still contains the line "GL-169 is public-facing polish only…" — this is accurate but is now two issues old. It is not a blocker.

---

## Area 2: Quickstart Readiness

The first verifiable output example is fully discoverable:

- README.md "First verifiable output quickstart" section contains the exact run command:
  `python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json`
- Expected output path (`/tmp/grantlayer_first_output.json`) is stated.
- Committed deterministic reference path (`examples/first_verifiable_output.json`) is stated.
- `docs/first_verifiable_output.md` is linked from README.md developer entry path table.
- The example was run locally during this review:
  `python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output_gl171_test.json`
  Output matched `examples/first_verifiable_output.json` exactly (zero diff).
- The example uses Python standard library only, no network, no secrets, no customer data.
- docs/first_verifiable_output.md correctly states "not production SaaS ready" and "tenant isolation is not implemented."

---

## Area 3: Safety and Non-Production Boundaries

All reviewed public-facing docs correctly state:

- Technical preview / non-production status
- Not production SaaS
- Tenant isolation is not implemented
- No real secrets required
- No real customer data required
- Local/demo only where applicable

No overclaim language was found in the reviewed scope. The public-facing posture is accurate.

---

## Area 4: GitHub Publish Readiness

- No file reviewed contains an instruction to push the internal repository directly to GitHub.
- The documentation consistently requires explicit human approval before any GitHub publication.
- The `scripts/build-clean-public-snapshot.sh` and `docs/clean_public_snapshot_build.md` describe a clean snapshot build and review process (GL-161/GL-162 gate).
- The `/tmp/grantlayer-public-publish` temporary publish directory is not refreshed here; that belongs to the next publish issue.
- This GL-171 review issue performs no GitHub push and no visibility change.

---

## Area 5: Secret / Privacy / Internal Leakage Safety

No raw tokens, private keys, private email addresses, phone numbers, AWS keys, GitHub tokens, or session credentials were found in public-facing docs or example files.

The `docs/public_secret_sensitive_scan_gate.md` file contains scan-blocker example content (including internal path patterns used as detection examples); this file is correctly excluded from the public snapshot in `scripts/build-clean-public-snapshot.sh` and its example content does not constitute a real leaked path.

`docs/demo_script.md` contains the path `cd /paperclip/grantlayer-mvp` at line 39. This is an internal operational path referencing the Paperclip internal workflow system. This file is **not** in the current public snapshot exclusion list. This is the highest-severity finding from this review (see F-001 below).

`docs/sprint_2_plan.md` contains a German sentence referencing Paperclip as a Docker-container service. This file **is** in the snapshot exclusion list and would not appear in a public snapshot.

---

## Area 6: Private Data / Public Snapshot Safety

### Scan Scope

All public-facing documentation files (`docs/**`, `examples/**`, `README.md`, `SECURITY.md`, `AGENTS.md`, `CONTRIBUTING.md`, `llms.txt`, `llms-full.txt`) and the snapshot exclusion list in `scripts/build-clean-public-snapshot.sh`.

Internal backend source and tests (`backend/`) are excluded from the public snapshot by design and were not the focus of public-readiness scanning.

### Checks Performed

| Check | Result |
|-------|--------|
| Real raw API tokens / JWTs / passwords | None found |
| Private key material (RSA, SSH, Ed25519 PEM) | None found |
| Private email addresses | None found |
| Phone numbers | None found |
| Real customer / user data | None found |
| Private absolute paths in non-excluded files | `/paperclip/grantlayer-mvp` in docs/demo_script.md — HIGH (see F-001) |
| Internal hostnames or Forgejo URLs | `"internal-forgejo"` label (no URL) in 3 non-excluded example JSONs — MEDIUM (see F-002) |
| Internal terminal URLs | None found |
| Environment files or secret-bearing configs | None found |
| Paperclip references in non-excluded files | docs/demo_script.md (path only) — HIGH (see F-001); docs/sprint_2_plan.md excluded from snapshot |
| GitHub visibility-change instructions | None found |
| Instructions to push internal repo directly to GitHub | None found |
| Public examples use synthetic/demo data only | Confirmed |

### Summary

- **Private data found:** No (no PII, customer data, or credentials)
- **Secret material found:** No (no tokens, keys, passwords)
- **Only synthetic/demo data in public examples:** Yes
- **Snapshot publication blocked by critical private-data or secret finding:** No
- **Snapshot publication cautions:** Yes — see F-001 (demo_script.md internal path not excluded) and F-002 (internal-forgejo label in non-excluded artifacts)

---

## Findings

| ID | Severity | Area | Status | Finding | Recommendation |
|----|----------|------|--------|---------|----------------|
| F-001 | HIGH | Private Data / Snapshot Safety | Open | `docs/demo_script.md` contains `cd /paperclip/grantlayer-mvp` (internal operational path revealing Paperclip internal system directory). This file is **not** in the `PUBLIC_EXPORT_EXCLUDE` list in `scripts/build-clean-public-snapshot.sh`. It would be included in a future public snapshot. | Add `docs/demo_script.md` to `PUBLIC_EXPORT_EXCLUDE` in `scripts/build-clean-public-snapshot.sh` before the next snapshot build. Address in the next publish or snapshot-build issue. Do not rewrite history here. |
| F-002 | MEDIUM | Private Data / Snapshot Safety | Open | `docs/examples/gl163/post_public_agent_intake_triage.json`, `docs/examples/gl164a/public_repo_discovery_metadata.json`, and `docs/examples/gl165/public_changelog_version_anchors.json` each contain `"sourceOfTruth": "internal-forgejo"`. This label discloses that an internal Forgejo instance is the canonical source of truth. No URL or credentials are exposed. These files are not in the snapshot exclusion list. | Confirm acceptability of the `internal-forgejo` descriptive label in public artifacts, or add these three JSON files to the snapshot exclusion list. Addressable in the next publish issue. |
| F-003 | LOW | Public-Facing Correctness | Open | README.md Safety section still contains "GL-169 is public-facing polish only…" — accurate but now two issues old (GL-170 and GL-171 have since landed). No incorrect claim. | Optional: update the line to reference the current latest internal issue when README is next revised. Not a blocker. |
| F-004 | LOW | Quickstart Readiness | Pass | The `"publicRepository"` field in `docs/examples/gl164a/public_repo_discovery_metadata.json` contains a public GitHub URL (`https://github.com/discodone/grantlayer`). This is a planned/reference URL from GL-164A and not a leaked credential. | No action required; this is a documented reference URL. |

---

## Finding Counts by Severity

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 1 |
| Low | 2 |
| **Total** | **4** |

---

## Readiness Decision

**`proceed_with_cautions_to_public_snapshot_publish`**

### Rationale

- No critical findings (no secrets, credentials, private keys, tokens, PII, or customer data).
- One HIGH finding: `docs/demo_script.md` contains an internal operational path (`/paperclip/grantlayer-mvp`) and is not excluded from the snapshot builder. This must be addressed before the next snapshot publish, but it does not constitute a credential leak or PII exposure.
- One MEDIUM finding: `"sourceOfTruth": "internal-forgejo"` label in three non-excluded example JSONs. Descriptive only, no URL or credential.
- Two LOW findings, neither blocking.
- All quickstart paths pass: deterministic output verified, run command accurate, first_verifiable_output.md discoverable.
- README.md and SECURITY.md are clean, deduplicated canonical status sources.
- Public examples use synthetic/demo data only.
- No GitHub push or visibility change performed or instructed.

The repository is ready for a public snapshot publish **after the HIGH finding is addressed** (adding `docs/demo_script.md` to the snapshot exclusion list). The cautions from F-001 and F-002 should be resolved in the next publish issue before the snapshot build is executed.

---

## Explicit Confirmations

- **No GitHub push performed** — this issue creates a branch and pushes to internal origin only.
- **No visibility change performed** — no GitHub visibility setting was altered.
- **No production/backend/src changes** — all changes are in docs/, examples/, and backend/tests/ review artifacts.
- **No OpenAPI, migration, database, or dependency changes.**

---

## Next Recommended Issue

**GL-172: Public Snapshot Publish — Pre-Publish Caution Resolution + Snapshot Build + Publish Gate**

Before executing the publish:
1. Add `docs/demo_script.md` to `PUBLIC_EXPORT_EXCLUDE` in `scripts/build-clean-public-snapshot.sh` (resolves F-001).
2. Confirm or exclude `"sourceOfTruth": "internal-forgejo"` artifacts (resolves F-002).
3. Run `bash scripts/build-clean-public-snapshot.sh` to rebuild the clean snapshot.
4. Run `bash scripts/public-secret-sensitive-scan.sh` on the snapshot.
5. Run the full backend suite (`bash scripts/run-full-backend-suite.sh`).
6. Only then proceed to the GL-162 Publish Gate for actual GitHub push with explicit human approval.
