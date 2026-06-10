# GL-178 README / SECURITY Post-Public State Correction

**Issue:** GL-178
**Title:** README / SECURITY Post-Public State Correction
**Date:** 2026-06-02
**Branch:** gl-178-readme-security-post-public-state
**Base main commit:** `e127a84be1095e415841e433edd33a7a808f33f5`

---

## Scope

Update public-facing README.md and SECURITY.md to accurately reflect the post-GL-176 public state.
This issue updates internal main only. No GitHub push, no visibility change, no force push.

Allowed files modified:
- `README.md`
- `SECURITY.md`
- `docs/readme_security_post_public_state.md` (this file)
- `docs/examples/gl178/readme_security_post_public_state.json`
- `backend/tests/test_gl178_readme_security_post_public_state.py`

---

## GL-177 Findings Addressed

| Finding | Severity | Status | Resolution |
|---------|----------|--------|------------|
| F-001 | medium | Addressed | Removed all "visibility pending GL-175" / "Public GitHub release has not happened" wording from README.md and SECURITY.md; updated to state repo is publicly available (GL-176) |
| F-002 | high | Addressed | Added active security reporting channel in SECURITY.md Section 2: GitHub Security Advisories URL; warning not to disclose secrets/exploits publicly |
| F-004 | low | Addressed | Removed broken link to `docs/public_github_readiness_pack.md` from README.md; file is internal-only and not present in public snapshot |

Non-blocking items not addressed (out of scope):
- F-003: public code surface improvement — future work
- F-005: /home/adminuser in scanner script is a pattern definition, not leakage

---

## Files Changed

| File | Change |
|------|--------|
| `README.md` | Updated status table; removed stale GL-175 pending wording (×3 occurrences); updated caveats section; removed broken link to `docs/public_github_readiness_pack.md`; updated "Current status and next steps" table |
| `SECURITY.md` | Updated status table; replaced "reporting channel pending" Section 2 with active GitHub Security Advisories channel; updated Section 6 caveats; updated Section 7 status |
| `docs/readme_security_post_public_state.md` | This report |
| `docs/examples/gl178/readme_security_post_public_state.json` | JSON artifact |
| `backend/tests/test_gl178_readme_security_post_public_state.py` | Automated test |

---

## Security Reporting Channel Selected

**Channel:** GitHub Security Advisories
**URL:** `https://github.com/Discodone/grantlayer/security/advisories`
**Fallback:** Open a minimal public issue that does not include exploit details or secrets and request a private reporting path.

No private personal email, private phone number, internal hostname, internal path, or private remote was added.

---

## README Correction Summary

| Item | Before | After |
|------|--------|-------|
| Status table "Public GitHub release" row | "Not performed — ... pending (GL-175)" | "Available — publicly accessible at https://github.com/Discodone/grantlayer.git (GL-176)" |
| "For AI Coding Agents" caveats block | "Public GitHub release has not happened — ... pending (GL-175)" | "Public GitHub repository is available — publicly accessible at ... (GL-176)" |
| Safety and limitations block | Two stale items: "not happened" + "no push performed directly" | Single updated item: "repository is available" |
| Repository and readiness links | Included broken `docs/public_github_readiness_pack.md` link | Removed; file is internal-only |
| Current status and next steps table | "Formal public visibility decision — Pending (GL-175)" as last row | Added GL-175 Complete, GL-176 Complete, GL-177 Complete, GL-178 Complete rows |

---

## SECURITY Correction Summary

| Item | Before | After |
|------|--------|-------|
| Status table "Public snapshot" row | "Synced — ... pending (GL-175)" | "Available — publicly accessible (GL-176)" |
| Section 2 Reporting Guidance | Split "before/after" with "channel pending" for the after case | Single unified section with active GitHub Security Advisories channel; explicit warning not to disclose publicly |
| Section 6 Caveats | "Public GitHub publication has not happened — ... GL-175 still required" | "Public GitHub repository is available (GL-176)" |
| Section 7 Status | "A formal public-visibility decision is pending (GL-175)" | Updated to reflect GL-176 published, GL-177 smoke passed, GL-178 complete |

---

## Broken Link Handling

**Finding:** F-004 — `docs/public_github_readiness_pack.md` linked from README.md but not present in public snapshot.

**Resolution:** Link removed from README.md "Repository and readiness links" section.

**Reason:** The file `docs/public_github_readiness_pack.md` exists in the internal repository but was not included in the public snapshot (GL-172/GL-176). It is an internal readiness checklist intended for pre-publication gating, not a public developer resource. Removing the link prevents a broken reference for public consumers without any content loss.

---

## Caveats Preserved

| Caveat | Preserved in README | Preserved in SECURITY |
|--------|--------------------|-----------------------|
| Technical preview / Developer Preview | Yes | Yes |
| Local evaluation and controlled pilot only | Yes | Yes |
| Production SaaS readiness not claimed | Yes | Yes |
| Tenant isolation not implemented | Yes | Yes |
| No real secrets in examples | Yes | Yes |
| No real customer data in examples | Yes | Yes |

---

## Private Data / Secret Safety Check

| Check | Result |
|-------|--------|
| Private data found | No |
| Secret material found | No |
| Internal infrastructure references added | No |
| Private contact details added | No |
| Internal hostname added | No |
| Internal path added | No |
| Private remote reference added | No |

Only public GitHub URLs (`https://github.com/Discodone/grantlayer.git` and advisory URL) were used.

---

## Findings Table

| ID | Severity | Category | Description | Status |
|----|----------|----------|-------------|--------|
| F-001 | medium | Stale wording | README.md / SECURITY.md contained "visibility pending GL-175" references | Fixed |
| F-002 | high | Missing reporting channel | SECURITY.md had no active security reporting channel | Fixed |
| F-004 | low | Broken link | README.md linked to `docs/public_github_readiness_pack.md` which is not in public snapshot | Fixed (link removed) |

---

## Decision / Result

`readme_security_post_public_state_fixed`

All three GL-177 findings assigned to GL-178 (F-001, F-002, F-004) have been addressed.
No private data, secrets, internal infrastructure, or private contact details were added.
All required caveats are preserved.

---

## Non-Goals

- No GitHub push performed.
- No visibility change performed.
- No force push.
- Internal repo was not pushed directly to GitHub.
- No production/backend/src changes.
- No OpenAPI, migration, DB/schema, or dependency changes.
- No SDK implementation changes.
- No frontend/website/design changes.
- No GitHub workflow changes.
- No snapshot publish script behavior changes.
- No git remote changes.
- No Paperclip references or status updates.
- F-003 (public code surface improvement) not addressed — future work.
- F-005 (/home/adminuser in scanner script) not addressed — confirmed not leakage.

---

## Next Recommended Issue

**GL-179** — Public snapshot correction push for GL-178 README/SECURITY fixes.

Publish the GL-178 doc fixes to the public GitHub snapshot so the public-facing README.md and
SECURITY.md reflect the corrected post-public state. Include public smoke follow-up verification
after the push.
