# GL-176: Public GitHub Visibility Change Report

**Issue:** GL-176
**Date:** 2026-06-01
**Disposition:** published_and_public

---

## Caveats

> **Developer Preview:** GrantLayer is not production SaaS. Tenant isolation is not implemented.
> No real secrets. No real customer data. Local and demo use only.

---

## Source Internal Main Commit

`309c8b244a2413a94fa2575d36e807a5ac58e3f2`
(Merge branch 'gl-175-public-snapshot-visibility-decision-gate')

---

## Public Publish Worktree

`/tmp/grantlayer-public-publish`

---

## GitHub Remote

`https://github.com/discodone/grantlayer.git`

Verified: no internal Forgejo remote configured as GitHub push target.
Internal repo was NOT pushed directly to GitHub.

---

## Phase A — GL-175 Merge Gate Confirmation

Before Phase B started, all hard gate conditions were verified:

| Check | Result |
|---|---|
| GL-175 merged into internal main | YES — commit 309c8b2 |
| internal origin/main == local main | YES |
| Working tree clean | YES |
| Post-merge GL-175 validation | PASS (46/46 tests) |
| Full backend suite on merged main | PASS (6283 tests, 0 failures, 214 skipped) |
| GL-175 decision | proceed_to_public_visibility_or_snapshot_publish |
| GL-175 confidence | high |
| No blocking private-data or secret finding | YES |

---

## Pre-flight Checks

### Internal Main State

- Internal main clean: YES
- internal origin/main equals local main: YES
- GL-175 merged on main: YES
- GL-175 decision: `proceed_to_public_visibility_or_snapshot_publish`
- No blocking private-data/secret finding: YES

### Public Publish Worktree

- Worktree path: `/tmp/grantlayer-public-publish`
- GitHub remote verified as `https://github.com/discodone/grantlayer.git`
- No internal Forgejo remote as push target: YES
- No private remote pushed: YES
- Worktree clean before sync: YES

### Repository Settings Checklist

| Item | Status |
|---|---|
| README public-facing status current | YES — GL-175 cleanup applied |
| SECURITY.md reporting channel appropriate | YES |
| Developer Preview caveat present | YES |
| Not production SaaS caveat present | YES |
| Tenant isolation not implemented caveat | YES |
| No real secrets required | YES |
| No customer data required | YES |
| Local / demo use only | YES |

---

## Snapshot Build

- Script: `scripts/build-clean-public-snapshot.sh`
- Build path: `/tmp/grantlayer-snapshot-gl176`
- Files included: 199
- backend/ excluded: YES (by design, F-003 acknowledged)
- .git excluded: YES
- .claude excluded: YES
- .env files excluded: YES
- Build exit code: 0

---

## Private Data / Secret Safety

Scanner: `scripts/public-secret-sensitive-scan.sh`
Target: `/tmp/grantlayer-public-publish` (staged git ls-files)
Files scanned: 190
Meta-excluded: 9
Blockers found: **0**

Result: **CLEAN**

| Check | Result |
|---|---|
| No raw tokens | PASS |
| No API keys | PASS |
| No JWTs | PASS |
| No passwords | PASS |
| No private keys / SSH keys | PASS |
| No private email addresses | PASS |
| No internal Forgejo hostnames | PASS |
| No private home paths | PASS |
| No customer / user data | PASS |

**Advisory (not a blocker):** An internal repository path appeared as a checklist item
in the GL-173 absence-check list (the document was verifying that the path was not present
in the public snapshot). This was a label reference, not actual path leakage. The content
was corrected post-publication and the public snapshot exclusion list was updated to prevent
recurrence. The public scanner reported 0 blockers on the public snapshot.

---

## F-003 Acknowledgment

F-003 (9 Python files visible in public snapshot surface — SDK and scripts) is acknowledged.
Backend is excluded by design. F-003 is a future improvement and not a blocker for GL-176.

---

## Publication Actions

| Action | Result |
|---|---|
| Snapshot refreshed from internal main | YES |
| Sync method | build-clean-public-snapshot.sh → /tmp/grantlayer-snapshot-gl176, then cp into worktree |
| Public snapshot pushed | YES |
| Push source | /tmp/grantlayer-public-publish |
| Push target | https://github.com/discodone/grantlayer.git |
| Push commit | 8bf6c335af4f1229dd752e935ec5b0e5a6928bad |
| Force push | NO |
| History rewrite | NO |
| Internal repo pushed directly to GitHub | NO |

### Files changed in public snapshot (GL-176 sync)

- `README.md` — GL-175 cleanup applied (status table updated, stale next steps removed, internal footnotes removed)
- `SECURITY.md` — GL-175 cleanup applied (status table updated, internal workflow footnote removed)
- `llms.txt` — GL-175 status reference updated
- `llms-full.txt` — GL-175 status reference updated
- `docs/public_snapshot_visibility_decision_gate.md` — new (GL-175)
- `docs/examples/gl175/public_snapshot_visibility_decision_gate.json` — new (GL-175)
- `docs/public_snapshot_human_review_gate.md` — new (GL-174)
- `docs/examples/gl174/public_snapshot_human_review_gate.json` — new (GL-174)
- `docs/public_snapshot_post_publish_smoke_review.md` — new (GL-173)
- `docs/examples/gl173/public_snapshot_post_publish_smoke_review.json` — new (GL-173)

---

## Visibility Change

- Changed: NO (already public)
- Prior visibility: public
- Current visibility: public
- Verification: `git ls-remote https://github.com/discodone/grantlayer.git` returned
  `8bf6c335af4f1229dd752e935ec5b0e5a6928bad` (HEAD) without authentication, confirming
  the repository is publicly accessible.
- GitHub CLI (gh): not available
- Visibility change via API: not required

---

## Post-Publication Smoke Checks

| Check | Result |
|---|---|
| GitHub remote reachable | YES — git ls-remote succeeded unauthenticated |
| git ls-remote HEAD | 8bf6c335af4f1229dd752e935ec5b0e5a6928bad |
| README.md present | YES |
| SECURITY.md present | YES |
| LICENSE present | YES |
| AGENTS.md present | YES |
| llms.txt present | YES |
| docs/examples present | YES |
| GL-175 visibility decision doc present | YES |
| GL-174 human review gate doc present | YES |
| GL-173 post-publish smoke review doc present | YES |
| No obvious internal leakage (scanner) | YES — 0 blockers |
| Clone URL | https://github.com/Discodone/grantlayer.git |

---

## Explicit Confirmations

- No force push: **CONFIRMED**
- Internal repo was NOT pushed directly to GitHub: **CONFIRMED**
- No backend/src changes: **CONFIRMED**
- No OpenAPI / migration / DB / schema changes: **CONFIRMED**
- No dependency manifest changes: **CONFIRMED**
- No frontend / website / design changes: **CONFIRMED**
- No SDK implementation changes: **CONFIRMED**
- No GitHub workflow changes: **CONFIRMED**
- No Paperclip API calls: **CONFIRMED**
- No private data cleanup by history rewrite: **CONFIRMED**

---

## Internal Report Files

These report files are in the internal repo only and are NOT included in the public snapshot:

- `docs/public_github_visibility_change_report.md` (this file)
- `docs/examples/gl176/public_github_visibility_change_report.json`
- `backend/tests/test_gl176_public_github_visibility_change_report.py`

The internal report is NOT included in the public snapshot (backend/tests/ is excluded;
docs/public_github_visibility_change_report.md and docs/examples/gl176/ would be included
unless added to the public export exclusion list for GL-177+).

---

## Remaining Cautions

1. Repository is a Developer Preview — not production SaaS.
2. Tenant isolation is not implemented.
3. No real secrets or customer data required or present.
4. F-003: Python files visible in public surface (SDK/scripts) — future improvement, not blocker.
5. Advisory (resolved): An internal repository path appeared as a checklist label in the GL-173
   smoke review doc. Corrected post-publication; exclusion list updated to prevent recurrence.
6. gh CLI not available — visibility confirmed public via git ls-remote without auth. Manual
   visibility management via GitHub UI if ever needed.

---

## Next Recommended Step

GL-176 is complete. The public snapshot is pushed and the repository is publicly accessible.

Recommended next steps:
- Monitor for community feedback on the public repository
- Address F-003 (Python surface exposure) in a future issue
- Evaluate whether GL-173/174/175 gate docs that reference internal path labels should be
  added to the public snapshot exclusion list in the build script (future improvement)
- Consider adding `docs/public_github_visibility_change_report.md` to the public exclusion
  list if it contains internal governance references not suitable for the public snapshot

---

## Final Disposition

`published_and_public`
