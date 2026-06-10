# GL-181 Public Snapshot Exclusion Cleanup

**Issue:** GL-181  
**Title:** build_clean_public_snapshot Exclusion Cleanup for GL-177/GL-178 Governance Docs  
**Base commit:** `58b4301d3cd3357d36801e8ec95a8c3536d7c4ae`

## Scope

Public snapshot export hygiene only.
This issue updates the public snapshot exclusion list so internal governance/report docs are explicitly excluded from future public exports.

Allowed files:
- `scripts/build-clean-public-snapshot.sh`
- `docs/public_snapshot_exclusion_cleanup.md`
- `docs/examples/gl181/public_snapshot_exclusion_cleanup.json`
- `backend/tests/test_gl181_public_snapshot_exclusion_cleanup.py`

## Exclusion Cleanup Summary

The public snapshot export configuration now explicitly excludes the internal GL-177/GL-178 governance/report docs that were previously handled only indirectly through scanner heuristics.

This keeps the public snapshot focused on the public-facing docs and examples while preserving the internal repo contents for local review and validation.

## Target Exclusions Added

- `docs/public_repo_smoke_verification.md`
- `docs/examples/gl177/public_repo_smoke_verification.json`
- `docs/readme_security_post_public_state.md`
- `docs/examples/gl178/readme_security_post_public_state.json`
- `docs/public_snapshot_correction_push_gl179.md`
- `docs/examples/gl179/public_snapshot_correction_push_gl179.json`
- `docs/public_docs_smoke_verification.md`
- `docs/examples/gl180/public_docs_smoke_verification.json`

## Files Intentionally Preserved in Public Snapshot

- `README.md`
- `SECURITY.md`
- `LICENSE`
- `AGENTS.md`
- `llms.txt`
- `llms-full.txt`
- `docs/first_verifiable_output.md`
- `examples/first_verifiable_output.py`
- `examples/first_verifiable_output.json`

## Verification Performed

- Shell syntax check for the snapshot script.
- Local snapshot build into a temporary directory.
- Presence/absence checks against the generated snapshot.
- Regression checks to ensure public-facing files remain included and README/SECURITY public-state fixes remain intact.

## Generated Snapshot Result

Local snapshot build completed successfully into a temporary output directory.
The excluded GL-177/GL-178 governance docs were absent from the generated snapshot and the public-facing required files remained present.
Snapshot output path used for this verification: `/tmp/grantlayer-public-snapshot-gl181-UJXzJ6`.

## Private Data / Secret Safety Check

No private data, secret material, internal infrastructure references, or blockers were introduced by this cleanup.

## Findings Table

| ID | Severity | Status | Recommendation | Blocking |
|----|----------|--------|----------------|----------|
| F-181-001 | info | closed | Explicitly exclude the internal governance/report docs from future public snapshot exports. | false |

## Result

`public_snapshot_exclusion_cleanup_complete`

## Non-Goals

- No GitHub push performed.
- No visibility change performed.
- No force push.
- Internal repo was not pushed directly to GitHub.
- No production/backend/src changes.
- No OpenAPI, migration, DB/schema, or dependency changes.
- No SDK implementation changes.
- No frontend, website, or design changes.
- No GitHub workflow changes.
- No git remote changes.
- No Paperclip references or status updates.

## Next Recommended Issue

**GL-182 external developer feedback intake**
