# GL-180 Public Docs Smoke Verification

**Issue:** GL-180  
**Title:** Public Docs Smoke Verification after GL-179 public snapshot correction push  
**Branch:** `gl-180-public-docs-smoke-verification`  
**Internal main commit used:** `56128e11571c7c2719be5921293933f35e609b18`  
**Public repository URL:** `https://github.com/Discodone/grantlayer.git`  
**Expected public commit prefix:** `d10bb09`  
**Actual public clone HEAD:** `d10bb09ea3fecf98aa82a1af93674b58c5e65a82`  
**Fresh clone path:** `/tmp/grantlayer-public-docs-smoke-gl180`  
**GL-179 internal report status:** pending on its own branch; not merged into `main` (`origin/gl-179-public-snapshot-correction-push` is present, while `main` remains at `56128e11571c7c2719be5921293933f35e609b18`)

## Scope

Verification report and test artifact only.
No runtime behavior changes, no public snapshot changes, and no public GitHub actions were performed.

Allowed internal deliverables:
- `docs/public_docs_smoke_verification.md`
- `docs/examples/gl180/public_docs_smoke_verification.json`
- `backend/tests/test_gl180_public_docs_smoke_verification.py`

## Checks Performed

- Fresh clone from the public GitHub repository URL.
- Verified the clone resolved to the expected public HEAD prefix `d10bb09`.
- Inspected `README.md` in the public clone for stale GL-175 wording and broken readiness-pack links.
- Inspected `SECURITY.md` in the public clone for the active GitHub Security Advisories channel and disclosure warnings.
- Confirmed the first verifiable output files are present in the public clone.
- Ran the first verifiable output example and compared it to the committed reference JSON.
- Ran targeted grep-based smoke checks for private paths, secret material, internal workflow references, and internal remote indicators.
- Confirmed the GL-177 follow-up documentation files remain absent from the public clone.

## Public State Verification

### README.md

Result: pass

- `README.md` exists in the fresh public clone.
- Stale wording is absent:
  - `visibility pending GL-175`
  - `Public GitHub release has not happened`
  - equivalent stale public-visibility wording
- The broken `docs/public_github_readiness_pack.md` link is absent.
- The README still references the first verifiable output and the quickstart path.
- Technical preview and non-production caveats remain visible.
- The README still says or clearly implies:
  - not production SaaS
  - tenant isolation is not implemented
  - no real secrets or customer data are required

### SECURITY.md

Result: pass

- `SECURITY.md` exists in the fresh public clone.
- The active GitHub Security Advisories channel is present:
  - `https://github.com/Discodone/grantlayer/security/advisories`
- The document warns not to disclose exploit details or secrets publicly.
- Stale wording is absent:
  - `visibility pending GL-175`
  - `Public GitHub release has not happened`
  - equivalent stale public-visibility wording
- Technical preview and non-production caveats remain visible.
- The document does not claim production SaaS readiness.
- The document does not claim tenant isolation is implemented.
- No private email, phone number, internal hostname, internal path, or private remote was added.

## GL-177 Findings Closure

| Finding | Status | Public-surface result |
|---------|--------|----------------------|
| F-001 | closed | Stale README/SECURITY wording is absent from the public clone. |
| F-002 | closed | SECURITY.md exposes a live GitHub Security Advisories reporting channel. |
| F-004 | closed | The broken README link to `docs/public_github_readiness_pack.md` is absent. |

Context:
- F-003: the internal-only report doc remains absent from the public repo and is not a blocker.
- F-005: scanner-pattern references remain present in expected documentation/script context and are not leakage.

## First Verifiable Output

Result: pass

- Files present:
  - `docs/first_verifiable_output.md`
  - `examples/first_verifiable_output.py`
  - `examples/first_verifiable_output.json`
- Command run:
  - `python3 /tmp/grantlayer-public-docs-smoke-gl180/examples/first_verifiable_output.py --output /tmp/gl180_first_verifiable_output.json`
- Exit code: `0`
- Deterministic match: `true`
- Notes: the generated output matched the committed reference JSON exactly.

## Private Data / Secret Smoke

Result: pass with cautions

- Scan scope: fresh public clone at `/tmp/grantlayer-public-docs-smoke-gl180`, with targeted grep checks over the public tree for private paths, secret material, internal workflow references, and internal remote indicators.
- The following practical checks were used:
  - stale wording / advisory channel check on `README.md` and `SECURITY.md`
  - first verifiable output file presence check
  - first verifiable output deterministic comparison
  - grep-based scan for `/home/adminuser`, `/paperclip/grantlayer-mvp`, internal Forgejo wording, private remotes, secret keywords, and direct-push instructions
- Private data found: `false`
- Secret material found: `false`
- Internal infrastructure found: `false`
- Paperclip or internal workflow found: `true`
- Blockers found: `false`
- Notes: the scan produced only expected documentation/script matches and public-facing descriptive references; no raw secrets, customer data, private keys, SSH keys, deploy keys, private home paths, or private remotes were identified.

## Findings

| ID | Severity | Area | Status | Recommendation | Blocking |
|----|----------|------|--------|----------------|----------|
| F-001 | medium | README / SECURITY stale wording | closed | None; verified absent on the public surface. | false |
| F-002 | high | SECURITY reporting channel | closed | None; GitHub Security Advisories is live and visible. | false |
| F-004 | low | README readiness-pack link | closed | None; broken link removed from the public surface. | false |
| F-003 | info | internal-only report doc context | context_only | None; absent from the public repo and not a blocker. | false |
| F-005 | info | scanner-pattern / public-surface noise | context_only | Optional later cleanup: add the known governance docs to the public export exclusion list if scanner noise should be reduced. | false |

## Finding Counts

| Severity | Count |
|----------|-------|
| critical | 0 |
| high | 1 |
| medium | 1 |
| low | 1 |
| info | 2 |
| total | 5 |

## Final Smoke Decision

`public_docs_smoke_passed_with_cautions`

The public GitHub repository is reachable, the corrected README and SECURITY content are live, the GL-177 findings are closed on the public surface, the first verifiable output remains deterministic, and the smoke scan found no blockers.

## Non-Goals

- No GitHub push performed.
- No visibility change performed.
- Internal repo was not pushed directly to GitHub.
- No force push performed.
- No history rewrite performed.
- No production/backend/src changes.
- No OpenAPI, migration, DB/schema, or dependency changes.
- No SDK implementation changes.
- No frontend, website, or design changes.
- No GitHub workflow changes.
- No snapshot publish script behavior changes.
- No git remote changes.
- No Paperclip status updates.
- No public snapshot contents were changed.

## Next Recommended Issue

**GL-181 build_clean_public_snapshot exclusion cleanup for GL-177/GL-178 governance docs**

This is the most relevant follow-up if the scanner-pattern noise should be reduced further.

## Explicit Statements

- No GitHub push was performed.
- No visibility change was performed.
- The internal repo was not pushed directly to GitHub.
