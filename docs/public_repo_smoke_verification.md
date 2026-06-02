# GL-177 Public Repo Smoke Verification

**Issue:** GL-177
**Title:** Public Repo Smoke Verification
**Date:** 2026-06-02
**Branch:** gl-177-public-repo-smoke-verification
**Base main commit:** `07a1f2bfcc9ceef14535f673d2640f60743fad84`
**Reviewer:** GrantLayer Public Repo Smoke Verification Agent

---

## Verification Scope

This document records the GL-177 unauthenticated public smoke verification of the GrantLayer public
GitHub repository after the GL-176 correction push. It confirms that an external developer can
reach the repository, clone it, run the first verifiable output example, and that no private or
internal data is visible on the public-facing surface.

This is a verification and reporting issue. No publication, push, visibility change, or content
modification was performed.

---

## Repository Details

| Item | Value |
|------|-------|
| Public repository URL | `https://github.com/Discodone/grantlayer.git` |
| Expected public commit | `e4cd080df9d8da7d7cf4044e84eea4df8ac80cc6` |
| Previous public commit (pre-correction) | `8bf6c335af4f1229dd752e939ec5b0e5a6928bad` |
| Actual public clone HEAD | `e4cd080df9d8da7d7cf4044e84eea4df8ac80cc6` |
| Internal main commit used | `07a1f2bfcc9ceef14535f673d2640f60743fad84` |
| Fresh clone path | `/tmp/grantlayer-public-smoke-gl177` |

---

## Explicit Non-Goals

- **No GitHub push performed.** No content was pushed to GitHub in this issue.
- **No visibility change performed.** The repository visibility was not modified.
- **Internal repo was not pushed directly to GitHub.** All public content originates from the
  explicit snapshot workflow; the internal Forgejo repo was not pushed directly to GitHub.
- No backend/src changes.
- No OpenAPI, migration, DB/schema, or dependency changes.
- No SDK implementation changes.
- No frontend, website, or design changes.
- No snapshot publish script behavior changes.
- No git remote changes.
- No force push.
- No public snapshot content changes.
- No Paperclip references or status updates.

---

## Checks Performed

| # | Check | Method |
|---|-------|--------|
| 1 | Public reachability and clone | `git clone https://github.com/Discodone/grantlayer.git /tmp/grantlayer-public-smoke-gl177` |
| 2 | HEAD commit verification | `git rev-parse HEAD` in clone |
| 3 | Previous commit in history | `git log --oneline \| grep 8bf6c33` |
| 4 | Public root files present | `ls README.md SECURITY.md LICENSE AGENTS.md llms.txt llms-full.txt` |
| 5 | Corrected docs present | `ls docs/public_snapshot_human_review_gate.md docs/public_snapshot_post_publish_smoke_review.md` |
| 6 | Old internal labels absent from corrected docs | `grep -n "/home/adminuser\|/paperclip/grantlayer-mvp" corrected_files` |
| 7 | First verifiable output files present | `ls docs/first_verifiable_output.md examples/first_verifiable_output.py examples/first_verifiable_output.json` |
| 8 | First verifiable output runs | `python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output_gl177.json` |
| 9 | Deterministic output match | `diff /tmp/grantlayer_first_output_gl177.json examples/first_verifiable_output.json` |
| 10 | Private data scan — internal paths | `grep -rn "/home/adminuser" all file types` |
| 11 | Private data scan — paperclip paths | `grep -rn "/paperclip/grantlayer-mvp" all file types` |
| 12 | Secret material scan — tokens/keys | `grep -rni "ghp_\|github_pat_\|AKIA[0-9A-Z]\|sk-\|xoxb-\|xoxp-"` |
| 13 | Credential scan | `grep -rni "password=\|api_key=\|secret=" with values, excluding test/example/placeholder` |
| 14 | Internal infrastructure scan | Hostnames, IPs, Tailscale ranges, Forgejo hostnames |
| 15 | Push instructions scan | `grep -rni "git push.*github\|push.*origin.*main"` excluding prohibitions |
| 16 | Public caveats present | `grep` for required caveat phrases in README.md and SECURITY.md |
| 17 | Developer first impression | Manual review of README.md first 80 lines |

---

## 1. Public Reachability

**Result: PASS**

- Clone succeeded with exit code 0.
- `git clone https://github.com/Discodone/grantlayer.git /tmp/grantlayer-public-smoke-gl177` completed without authentication prompts or errors.
- Unauthenticated read access confirmed.
- HEAD commit: `e4cd080df9d8da7d7cf4044e84eea4df8ac80cc6` — matches expected.
- Previous commit `8bf6c335af4f1229dd752e939ec5b0e5a6928bad` confirmed in history.
- Public git log (first 5):

```
e4cd080 GL-176 fix: remove internal path labels from gate review docs
8bf6c33 GL-175/GL-176: sync public snapshot — visibility decision gate
4b42f7f GL-172: include scanner script; scanner self-excludes (META_EXCLUDE)
d9418c5 GL-172 sync clean public snapshot
4e4d7fc GL-166: sync clean public snapshot
```

---

## 2. Public Root Files

**Result: PASS**

All expected public root files are present in the fresh clone:

| File | Present |
|------|---------|
| README.md | yes |
| SECURITY.md | yes |
| LICENSE | yes |
| AGENTS.md | yes |
| llms.txt | yes |
| llms-full.txt | yes |

---

## 3. Public Correction Verification

**Result: PARTIAL PASS — see F-003**

The GL-176 correction commit (`e4cd080`) is HEAD on the public repository. The correction
touched exactly 2 files as confirmed by `git show HEAD --name-only`:

| Expected Corrected File | Present in Public Clone | Old Internal Labels Absent |
|-------------------------|------------------------|---------------------------|
| docs/public_snapshot_human_review_gate.md | yes | yes |
| docs/public_snapshot_post_publish_smoke_review.md | yes | yes |
| docs/public_github_visibility_change_report.md | **no** | N/A |

**Old internal label scan** (`/home/adminuser`, `/paperclip/grantlayer-mvp`):

```
grep -n "/home/adminuser|/paperclip/grantlayer-mvp" \
  docs/public_snapshot_human_review_gate.md \
  docs/public_snapshot_post_publish_smoke_review.md
→ (no output, exit code 1 — no matches)
```

The two present corrected docs are clean. The third file (`docs/public_github_visibility_change_report.md`)
was listed in the GL-177 task context as a corrected file but is not present in the public clone
and was never part of any public snapshot commit. It is an internal workflow document. This is
documented as finding F-003 (low, non-blocking).

---

## 4. First Verifiable Output

**Result: PASS**

Required files present:

| File | Present |
|------|---------|
| docs/first_verifiable_output.md | yes |
| examples/first_verifiable_output.py | yes |
| examples/first_verifiable_output.json | yes |

Run command (from fresh public clone `/tmp/grantlayer-public-smoke-gl177`):

```bash
python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output_gl177.json
```

| Check | Result |
|-------|--------|
| Exit code | 0 |
| Generated output path | /tmp/grantlayer_first_output_gl177.json |
| Expected output path | examples/first_verifiable_output.json |
| Deterministic match | **yes** — `diff` produced no output |
| Real secrets required | no |
| Customer data required | no |

---

## 5. Public-Facing Caveats

**Result: PASS**

All required caveats are present in README.md and SECURITY.md:

| Caveat | Location | Present |
|--------|----------|---------|
| Technical preview / Developer Preview | README.md (lines 17, 27, 371), SECURITY.md (line 13) | yes |
| Not production SaaS | README.md (lines 20, 104, 284), SECURITY.md (lines 15, 18) | yes |
| Tenant isolation not implemented | README.md (lines 20, 105, 127), SECURITY.md (lines 19, 82) | yes |
| No real secrets required | README.md (lines 64, 103), SECURITY.md (line 71) | yes |
| No customer data required | README.md (lines 64, 103), SECURITY.md (line 72) | yes |
| Local / demo use only | README.md (lines 65, 130) | yes |

**Note:** While all required caveats are present, README.md and SECURITY.md contain stale status
statements that claim the public release has not happened and that GL-175 is pending. See F-001.

---

## 6. Private Data / Secret Smoke Check

**Result: PASS — no blockers found**

Scan scope: `/tmp/grantlayer-public-smoke-gl177` — all `.md`, `.py`, `.json`, `.txt`, `.yaml`, `.yml`, `.sh` files, excluding `.git/`.

| Check | Pattern | Result |
|-------|---------|--------|
| Internal path /home/adminuser | grep -rn "/home/adminuser" | 2 matches in `scripts/public-secret-sensitive-scan.sh` lines 31/202 — pattern definitions only, not data leakage |
| Internal path /paperclip/grantlayer-mvp | grep -rn "/paperclip/grantlayer-mvp" | no matches |
| GitHub tokens | ghp\_, github_pat\_ | no matches |
| AWS access keys | AKIA[0-9A-Z]{16} | no matches |
| OpenAI / other API keys | sk- prefix | false positives only (e.g., "disk-full") |
| Slack tokens | xoxb-, xoxp- | no matches |
| Hardcoded credentials | password=, api_key=, secret= with values | no matches (excluding test/example/placeholder) |
| Internal hostnames | forge.internal, terminal.internal, private homelab domain | no matches |
| Private IPs | 192.168., Tailscale ranges | no matches |
| Private Forgejo hostnames | actual hostnames | no matches (word "Forgejo" used in architectural description only) |
| Private terminal URL | private homelab terminal hostname | no matches |
| Private email addresses | sensitive patterns | no matches (SHA hashes are false positives) |
| Instructions to push internal repo to GitHub | direct push instructions | no matches (references appear only in prohibition/audit context) |
| Customer or user data | real names, identifiers | no matches (all examples use synthetic data) |

**Summary:**

| Metric | Value |
|--------|-------|
| private_data_found | **false** |
| secret_material_found | **false** |
| internal_infrastructure_found | **false** |
| paperclip_or_internal_workflow_found | **false** |
| blockers_found | **false** |

---

## 7. Developer First Impression

**Result: GOOD WITH CAUTIONS**

| Aspect | Assessment |
|--------|-----------|
| External developer can understand what GrantLayer is | yes — README introduction is clear and concise |
| Can find a runnable example | yes — first verifiable output quickstart is prominent in README |
| Caveats visible enough | yes — status table and narrative sections both state preview posture |
| Obvious stale status | yes — "Public GitHub release: Not performed" and "formal visibility decision pending (GL-175)" are stale |
| Confusing next-step instruction | partial — security contact section says "pending" with no active channel |

The README effectively communicates GrantLayer's purpose, posture, and entry points. The first
verifiable output example is the clearest developer on-ramp. The stale status claims (F-001) and
missing security contact (F-002) are the main gaps for a developer or security researcher landing
on the repository for the first time.

---

## Findings

| ID | Severity | Area | Status | Blocking | Recommendation |
|----|----------|------|--------|----------|----------------|
| F-001 | medium | public_surface_status | open | false | Create GL-178 to update README.md and SECURITY.md status tables. Replace stale "Public GitHub release: Not performed" and "formal visibility decision pending (GL-175)" with accurate post-GL-176 state. |
| F-002 | high | security_reporting | open | false | Enable GitHub Security Advisories and update SECURITY.md section 2 to provide an active reporting channel before any broader promotion. |
| F-003 | low | public_correction_scope | info | false | Confirm docs/public_github_visibility_change_report.md is intentionally internal-only. Update context docs if needed to reflect GL-176 correction covered 2 files, not 3. |
| F-004 | low | public_documentation | open | false | Fix broken README.md link to docs/public_github_readiness_pack.md in GL-178. File exists internally but was not included in public snapshot. |
| F-005 | info | private_data_scan | accepted | false | No action required. /home/adminuser in scripts/public-secret-sensitive-scan.sh is a scanner pattern definition, not data leakage. |

---

## Finding Counts by Severity

| Severity | Count |
|----------|-------|
| critical | 0 |
| high | 1 |
| medium | 1 |
| low | 2 |
| info | 1 |
| **total** | **5** |

---

## Final Smoke Decision

**`public_repo_smoke_passed_with_cautions`**

No blockers were found. No private data, secrets, internal credentials, or internal infrastructure
references were found in the public clone surface. The first verifiable output example runs
successfully and produces deterministic output matching the committed reference. The public
correction commit is confirmed at HEAD. The required public caveats are present.

Cautions requiring follow-up in GL-178:
- F-001 (medium): Stale public-release status in README.md and SECURITY.md
- F-002 (high): No active security reporting channel for the now-public repository
- F-004 (low): Broken README link to docs/public_github_readiness_pack.md

These cautions do not block smoke but should be addressed before any broader promotion of the
public repository.

---

## Next Recommended Issue

**GL-178: Public snapshot status update**

Scope: Update README.md and SECURITY.md to reflect accurate post-GL-176 state (stale GL-175
references), establish an active security reporting channel (GitHub Security Advisories), and
fix the broken docs/public_github_readiness_pack.md link. Verification-only issue; no backend
or infrastructure changes.

---

## Explicit Confirmations

| Confirmation | Value |
|--------------|-------|
| No GitHub push performed | **confirmed** |
| No visibility change performed | **confirmed** |
| Internal repo was not pushed directly to GitHub | **confirmed** |
| No production / backend/src changes | **confirmed** |
| No OpenAPI / migration / DB / dependency changes | **confirmed** |
| No frontend / website / design changes | **confirmed** |
| Working tree clean after artifact creation | pending (will be verified after commit) |
