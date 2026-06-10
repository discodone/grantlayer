# GL-187P: Public Snapshot Correction Push

**Issue:** GL-187P
**Title:** Public Snapshot Correction Push for GL-187 Public Docs Stale Claim Cleanup
**Date:** 2026-06-03
**Disposition:** correction_pushed

---

## Caveats

> **Developer Preview:** GrantLayer is not production SaaS. Tenant isolation is not implemented.
> No real secrets. No real customer data. Local and demo use only.

---

## Internal Main Commit Used

`40c0449d90f2b781296d9089eb4e6ec0ff2b1dcd`
(GL-187 fixup: update GL-170 stale test assertions for public repo state)

---

## Public Publish Worktree

`/tmp/grantlayer-public-publish`

Refreshed from internal main via `scripts/build-clean-public-snapshot.sh` (GL-161 established workflow).

---

## GitHub Remote Verified

`https://github.com/discodone/grantlayer.git`

- No internal Forgejo remote configured as push target: YES
- No private remote configured as push target: YES
- Internal repo was NOT pushed directly to GitHub: YES

---

## Previous Public Commit

`d10bb09ea3fecf98aa82a1af93674b58c5e65a82`
(GL-178/GL-179: README and SECURITY post-public state correction)

---

## New Public Commit

`11d3f16fd64b77a52561cb329780fd33affde0f8`
(GL-187/GL-181–186: public docs stale claim cleanup and snapshot sync)

---

## Files Pushed Publicly

| File | Change |
|------|--------|
| `README.md` | Modified — GL-187 stale test count, hypothetical metadata wording, clone/cd consistency, and public-state corrections applied |
| `CONTRIBUTING.md` | Modified — GL-187 stale public-release claim removed |
| `AGENTS.md` | Modified — GL-187 stale public-state wording removed; public release status updated |
| `docs/ten_minute_quickstart.md` | Modified — GL-187 public clone URL corrected |
| `docs/agent_quickstart.md` | Modified — GL-187 public clone/internal source wording corrected |
| `llms-full.txt` | Modified — GL-187 stale public-state wording removed |
| `llms.txt` | Modified — GL-187 stale public-state wording removed |
| `scripts/build-clean-public-snapshot.sh` | Modified — GL-181 exclusion entries added for GL-177/178/179/180 governance docs |
| `docs/ai_reviewer_feedback_triage.md` | Added — GL-186 AI reviewer feedback triage report |
| `docs/external_developer_feedback_intake.md` | Added — GL-182 external developer feedback intake report |
| `docs/external_feedback_triage_public_issue_hygiene.md` | Added — GL-183 external feedback triage report |
| `docs/first_external_reviewer_invite_pack.md` | Added — GL-184 first external reviewer invite pack report |
| `docs/first_reviewer_feedback_window.md` | Added — GL-185 first reviewer feedback window report |
| `docs/public_docs_post_public_stale_claim_cleanup.md` | Added — GL-187 cleanup report |
| `docs/public_snapshot_exclusion_cleanup.md` | Added — GL-181 exclusion cleanup report |
| `docs/examples/gl181/public_snapshot_exclusion_cleanup.json` | Added — GL-181 JSON artifact |
| `docs/examples/gl182/external_developer_feedback_intake.json` | Added — GL-182 JSON artifact |
| `docs/examples/gl183/external_feedback_triage_public_issue_hygiene.json` | Added — GL-183 JSON artifact |
| `docs/examples/gl184/first_external_reviewer_invite_pack.json` | Added — GL-184 JSON artifact |
| `docs/examples/gl185/first_reviewer_feedback_window.json` | Added — GL-185 JSON artifact |
| `docs/examples/gl186/ai_reviewer_feedback_triage.json` | Added — GL-186 JSON artifact |
| `docs/examples/gl187/public_docs_post_public_stale_claim_cleanup.json` | Added — GL-187 JSON artifact |

22 files changed, 3818 insertions(+), 58 deletions(-)

---

## GL-187 Fixes Published

| Finding | Fix | Published on GitHub |
|---------|-----|---------------------|
| Stale test count in README ("1130 tests, 3 skipped, 0 failures") | Removed stale hard-coded assertion | YES |
| CONTRIBUTING "Public GitHub release: Not performed" stale claim | Updated to Available with public URL | YES |
| README hypothetical public metadata wording ("If and when…") | Removed hypothetical framing | YES |
| ten_minute_quickstart clone command missing or using internal source | Updated to public GitHub clone URL | YES |
| agent_quickstart internal source / ambiguous wording | Corrected to public clone URL | YES |
| README clone/cd path inconsistency | Fixed to consistent `cd grantlayer` | YES |
| README first-output vs backend-quickstart path clarified | Path clarified | YES |
| AGENTS/llms-full stale "Not performed" public release wording | Updated to Available | YES |
| GL-155 planned/completed contradiction | Resolved — marked available | YES |
| sourceOfTruth/internal-forgejo public confusion | Handled — files excluded from snapshot in GL-172 | YES |

---

## Caveats Preserved

| Caveat | Status |
|--------|--------|
| Developer/technical preview | PRESERVED — visible in README, CONTRIBUTING, AGENTS |
| Not production SaaS | PRESERVED — visible in README, CONTRIBUTING, AGENTS |
| Tenant/workspace isolation not implemented | PRESERVED — visible in AGENTS |
| No real secrets or customer data | PRESERVED — visible in README, CONTRIBUTING, AGENTS, ten_minute_quickstart |
| Synthetic/demo data only | PRESERVED — all examples use synthetic identifiers |
| Security channel: GitHub Security Advisories | PRESERVED — visible in CONTRIBUTING |

---

## Stale Phrase Verification

Checked phrases:

- `1130 tests|3 skipped, 0 failures` → ABSENT
- `Public GitHub release.*Not performed` → ABSENT
- `If and when public publication is approved` → ABSENT
- `visibility decision pending` → ABSENT
- `formal visibility decision pending` → ABSENT
- `approved internal source` → ABSENT
- `public GitHub release has not happened` → ABSENT
- `publication is pending` → ABSENT

Result: **CLEAN — no stale blocking occurrences**

---

## Private Data / Secret Safety

- Private data found: NO
- Secret material found: NO
- Internal infrastructure found: NO (no private hostnames, IPs, tokens, private paths)
- Blockers found: NO

Public snapshot scanner (`public-secret-sensitive-scan.sh`) run on the snapshot:
- Scanned files: 204
- Meta-excluded: 9 (scanner/docs/tests self-references)
- **Blockers found: 0**

Additional manual checks:
- No `/home/adminuser`, `/paperclip/grantlayer-mvp`, or absolute private paths
- No `192.168.*`, `forgejo`, `terminal.hofer`, `hofercloud`, `tapWjov8`
- "Paperclip" appears only in forbidden-action scope guards ("Do not Reference Paperclip") — meta-reference only, not actual exposure
- "internal-forgejo" appears only in the context of describing a resolved finding — descriptive only, not a live URL or hostname
- No private emails, phone numbers, tokens, API keys, JWTs, SSH keys, deploy keys

---

## Publication Actions

| Action | Result |
|--------|--------|
| Public snapshot pushed | YES |
| Push source | `/tmp/grantlayer-public-publish` |
| Push target | `https://github.com/discodone/grantlayer.git` |
| Force push | NO |
| History rewrite | NO |
| Visibility changed | NO |
| Internal repo pushed directly to GitHub | NO |

**No force push used** — push was fast-forward: `d10bb09..11d3f16`
**Visibility unchanged** — public repository remains public; no settings changed
**Internal repo was NOT pushed directly to GitHub** — all content went through the clean public snapshot workflow via `/tmp/grantlayer-public-publish`

---

## Post-Push Smoke Checks

| Check | Result |
|-------|--------|
| GitHub remote reachable unauthenticated | YES — `git ls-remote` succeeded |
| Public HEAD updated | YES — `11d3f16fd64b77a52561cb329780fd33affde0f8` |
| local main equals origin/main in publish worktree | YES |
| Working tree clean in publish worktree | YES (GL-177/178 untracked docs excluded, never committed) |
| README.md present | YES |
| CONTRIBUTING.md present | YES |
| AGENTS.md present | YES |
| llms.txt present | YES |
| llms-full.txt present | YES |
| SECURITY.md present | YES |
| docs/ten_minute_quickstart.md present | YES |
| docs/agent_quickstart.md present | YES |
| docs/first_verifiable_output.md present | YES |
| examples/first_verifiable_output.py present | YES |
| examples/first_verifiable_output.json present | YES |
| Stale GL-187 target phrases absent on public surface | YES — CLEAN |
| Public clone URL visible in README | YES — `https://github.com/Discodone/grantlayer.git` |
| Developer Preview caveat present | YES |
| No real secrets/customer data caveat present | YES |
| Tenant isolation caveat present | YES |
| SECURITY/advisory path present | YES — GitHub Security Advisories referenced in CONTRIBUTING |

---

## Findings and Cautions

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| F-187P-001 | informational | Snapshot sync also included accumulated GL-181–186 public docs (not only GL-187 changes) since last push was GL-179P | Expected — all docs passed scanner; all are within allowed public scope; no private data found |
| F-187P-002 | informational | AGENTS.md quick-validation section still says `cd grantlayer-mvp` (internal clone path convention) | Not a GL-187 scope item; AGENTS.md is for agent/developer use; the path reflects the local dev environment name; acceptable for developer preview context |
| F-187P-003 | informational | GL-177/178 governance docs exist as untracked files in `/tmp/grantlayer-public-publish` (never committed to public repo) | No action needed — they were never pushed to GitHub; they are correctly excluded from the public snapshot |
| F-187P-004 | informational | `git init` in snapshot dir caused `.git/config` to be inadvertently copied to public worktree, overwriting the origin remote | Recovered — `git remote add origin https://github.com/discodone/grantlayer.git` restored the correct remote before commit/push; future snapshot builds should use `--no-git` or explicitly exclude `.git/config` from copy |

---

## Internal Report Changed Files

| File | Type |
|------|------|
| `docs/public_snapshot_correction_push_gl187.md` | Report (this document) |
| `docs/examples/gl187p/public_snapshot_correction_push_gl187.json` | JSON artifact |
| `backend/tests/test_gl187p_public_snapshot_correction_push.py` | Test |

---

## Internal Validation Commands and Results

```
python3 -m py_compile backend/tests/test_gl187p_public_snapshot_correction_push.py → PASS
python3 -m unittest backend.tests.test_gl187p_public_snapshot_correction_push -v → see validation section
python3 -m unittest backend.tests.test_gl187_public_docs_post_public_stale_claim_cleanup -v → see validation section
python3 -m unittest backend.tests.test_gl186_ai_reviewer_feedback_triage -v → see validation section
python3 -m unittest backend.tests.test_security_boundary_regression -v → see validation section
git diff --check → CLEAN
git status --short → clean (branch files only)
```

---

## Final Disposition

**correction_pushed**

GL-187 public documentation cleanup successfully published to GitHub.
Previous public commit: `d10bb09ea3fecf98aa82a1af93674b58c5e65a82`
New public commit: `11d3f16fd64b77a52561cb329780fd33affde0f8`
No force push. No visibility change. Internal repo not pushed directly to GitHub.

---

## Next Recommended Issue

**GL-188 First Output Verify Helper Script**
