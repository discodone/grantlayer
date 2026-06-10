# Public Visibility Go/No-Go Checklist

**Issue**: GL-167  
**Status**: Developer Preview - public visibility readiness checklist  
**Current recommendation**: `no_go`  
**Baseline internal main**: `08460fddeb9f841776b13f973bac6d5acdaf1584`  
**Deferred publish commit**: `4e4d7fc1733323148cfeb0306deb455aa1ebd63b`

---

## Purpose

This checklist is a public visibility readiness checklist for the GrantLayer
public snapshot. It is not a public launch, not a publication action, and not an
authorization to change repository visibility.

The current recommendation is `no_go` because the GitHub push is deferred and
final remote verification has not occurred.

---

## Decision States

| State | Meaning |
|---|---|
| `no_go` | Public visibility must not proceed. One or more required checks are blocked, missing, or not authorized. |
| `go_after_deferred_push_verified` | Public visibility may be reconsidered only after the deferred push is completed and remote verification confirms the expected public snapshot. |
| `go` | Public visibility may proceed only after all checklist items pass and explicit authorization for visibility change is recorded. |

---

## Current Recommendation

**Recommendation**: `no_go`

### Blocking Reasons

| Blocker | Status |
|---|---|
| `github_push_deferred` | The GitHub push has been deferred for later batch handling. |
| `remote_verification_missing` | The final remote repository file set, metadata, and scanner status have not been verified. |
| `visibility_change_not_authorized` | No authorization exists in GL-167 to change repository visibility. |

No GitHub push, GitHub visibility change, force push, internal repository push,
or full-history publication is authorized by this checklist.

---

## Snapshot Scanner Status

Before public visibility can move beyond `no_go`, the final public snapshot must
have a current scanner result:

| Check | Required Result |
|---|---|
| Public snapshot scanner completed | pass on the exact candidate tree |
| Scanner result tied to deferred publish commit | `4e4d7fc1733323148cfeb0306deb455aa1ebd63b` |
| Scanner result reviewed after push | pass after remote verification |
| Scanner output retained as an artifact | yes |

---

## Absence Checks

The public snapshot and final remote contents must be checked for absence of
forbidden material:

| Area | Required Result |
|---|---|
| Real secrets | absent |
| Private keys | absent |
| Real API tokens | absent |
| Passwords | absent |
| Real customer data | absent |
| Private personal data | absent |
| Internal hostnames | absent |
| Internal absolute paths | absent |
| Backend/internal fixtures not intended for publication | absent |
| Internal repository metadata | absent |

---

## Deferred GitHub Push Status

The deferred GitHub push is not complete. Public visibility remains `no_go`
until all of the following are true:

| Check | Current Status |
|---|---|
| Deferred push completed | no |
| Pushed tree matches expected public snapshot | not verified |
| Remote file set verified | not verified |
| Remote metadata verified | not verified |
| Remote scanner status verified | not verified |

---

## Repository Visibility

Repository visibility is unchanged in GL-167.

Required final verification before any visibility change:

| Check | Required Result |
|---|---|
| Visibility before GL-167 | unchanged |
| Visibility change performed by GL-167 | no |
| Visibility change authorization present | no |
| Visibility after deferred verification | must be confirmed before any change |

---

## Publication Boundaries

| Boundary | Required Result |
|---|---|
| Full internal git history publication | prohibited |
| Internal repository pushed to GitHub | prohibited |
| Clean public snapshot only | required for any future public publication |
| Force push | prohibited |
| GitHub push in GL-167 | prohibited |
| Repository visibility change in GL-167 | prohibited |

---

## Branch And History Safety

Before moving out of `no_go`, the reviewer must confirm:

- The public snapshot was produced from the intended version anchor.
- The internal repository history was not published.
- No history rewrite was performed as part of GL-167.
- No branch was force-pushed.
- No internal remote configuration was copied into the public snapshot.
- The pushed public tree, if later pushed, matches the reviewed snapshot tree.

---

## Secrets, Keys, And Token Checks

Required checks before any public visibility decision can become `go`:

| Check | Required Result |
|---|---|
| Secret scanner | pass |
| Private key markers | absent |
| Bearer tokens | absent except documented placeholders |
| API keys | absent except documented placeholders |
| JWT-like samples | absent except documented placeholders |
| Environment files | examples use placeholders only |

All examples must continue to use placeholder values only.

---

## Internal Hostname And Path Checks

The final public snapshot and remote repository must not contain:

- Internal service hostnames
- Private Forgejo or internal CI URLs
- Developer machine hostnames
- Developer home directory paths
- Private mount paths
- Internal-only deployment paths

---

## Backend/Internal Fixture Absence

The final public snapshot must exclude backend and internal fixtures unless a
future issue explicitly authorizes a specific public-facing fixture. Required
verification:

| Check | Required Result |
|---|---|
| `backend/src` production backend code in public snapshot | absent unless separately authorized |
| Internal backend fixtures | absent |
| Test data with internal identifiers | absent |
| Internal operational artifacts | absent |

---

## Production Readiness Claim Checks

Public materials must preserve the project caveats:

- GrantLayer is a Developer Preview.
- GrantLayer is not production SaaS.
- Tenant isolation is not implemented.
- No real secrets are included.
- No real customer data is included.
- Public visibility does not imply enterprise deployment readiness.

The checklist does not claim production SaaS readiness, tenant isolation
implementation, a completed public launch, or full internal history cleanliness.

---

## License, README, CHANGELOG, And Version Anchor Checks

Before public visibility can proceed:

| Check | Required Result |
|---|---|
| License present | Apache-2.0 license metadata present in the public snapshot |
| README caveats | Developer Preview and safety caveats present |
| CHANGELOG version anchor | public snapshot version anchor present |
| Version anchor matches reviewed commit | verified |
| Public snapshot description | avoids production or tenant-isolation overclaims |

---

## Open Blockers Before Public Visibility

The following blockers keep the current recommendation at `no_go`:

| Blocker | Required Resolution |
|---|---|
| `github_push_deferred` | Complete the deferred GitHub push through the approved batch process. |
| `remote_verification_missing` | Verify remote file set, metadata, scanner status, and absence checks after push. |
| `visibility_change_not_authorized` | Record explicit authorization before any visibility change. |

---

## Required Final Verification Before Visibility Change

No visibility change may occur until a reviewer records all of the following:

1. Deferred GitHub push completed.
2. Remote repository file set matches the reviewed public snapshot.
3. Public snapshot scanner passes on the pushed tree.
4. Absence checks pass on the pushed tree.
5. Repository metadata, license, README, CHANGELOG, and version anchor are correct.
6. Repository visibility is still unchanged before approval.
7. No full internal history was published.
8. No internal repository was pushed to GitHub.
9. No production SaaS readiness or tenant isolation implementation claim exists.
10. Explicit authorization for a visibility change is recorded.

---

## Explicit Non-Goals

GL-167 does not:

- Push to GitHub
- Change GitHub visibility
- Force push
- Push the internal repository to GitHub
- Publish full internal git history
- Rebuild the public snapshot unless local inspection is required
- Publish a snapshot
- Change production code
- Change `backend/src`
- Change OpenAPI
- Change migrations
- Add dependencies
- Rewrite git history
- Change git remotes
- Claim production SaaS readiness
- Claim implemented tenant isolation
- Claim public launch completion
