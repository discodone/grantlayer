# GL-094B Audit Log Immutability Review

**Review ID:** GL-094B  
**Review Date:** 2026-05-23  
**Reviewer:** Claude Code (Security Review Agent)  
**Base Commit:** eca46bf582243dfcdafbf0fa330cc083b8b97ea2  
**Branch:** gl-094b-audit-log-immutability-review  
**Predecessor:** GL-094A Phase 1 Security Remediation Review

---

## Review-only statement

This document is review-only. No production code was modified, no implementation fixes were applied, no migrations were added, and no schema changes were made. All findings are advisory. Remediation is deferred to follow-on issues as described in the Recommended implementation issues section.

---

## Executive Summary

GL-094A identified audit log mutability as a HIGH severity finding (F-003) and recommended GL-094B as the focused follow-up. This review confirms and deepens that finding. The `audit_events` table is written via append-only application code, but has no database-level immutability enforcement, no tamper-evidence fields, and inconsistent transactional boundaries across the audit write paths. Grant lifecycle events (creation, revocation, consumption) are not logged to the audit trail at all. No hash chain, sequence number, checksum, or cryptographic signature is stored on audit rows, making silent modification or deletion undetectable.

**Conclusion: `proceed_with_cautions`**

No critical findings were identified. Four HIGH findings and three MEDIUM findings confirm that the audit log's integrity posture is insufficient for production compliance or forensic use. The risks are significant but addressable through targeted follow-on issues without blocking the current codebase.

---

## Scope reviewed

- Audit log append-only enforcement (application and database layers)
- Audit event tamper-evidence (hash chain, sequence, checksum, signature)
- Transactional integrity of audit writes relative to state changes
- Consistency of audit coverage across all sensitive actions
- Audit failure handling (surfaced vs. swallowed)
- Semantic correctness of audit event fields (approve vs. deny/revoke)
- Test coverage gaps for audit immutability

---

## Files inspected

| File | Purpose |
|------|---------|
| `backend/src/audit_log.py` | Audit event write and read functions |
| `backend/src/grant_requests.py` | Grant request lifecycle; audit call sites |
| `backend/src/grants.py` | Grant creation, revocation, consumption; tamper demo |
| `backend/src/server.py` | HTTP endpoints; audit-related routes |
| `backend/tests/test_gl092_deny_revoke_audit_semantics.py` | Rollback and semantic tests |
| `backend/tests/test_grant_requests.py` | Grant request integration tests |
| `docs/phase1_security_remediation_review.md` | GL-094A findings source |
| `docs/examples/gl094a/phase1_security_review_findings.json` | GL-094A findings JSON |

---

## Current audit model summary

The audit log is implemented as a single `audit_events` table written exclusively through `audit_log.append_event()` in `backend/src/audit_log.py`. The function executes a plain SQL `INSERT` with thirteen fields: `id`, `timestamp`, `subject_id`, `role`, `action`, `resource`, `approved`, `reason`, `matched_grant_id`, `challenge_id`, `challenge_present`, `challenge_result`, `grant_signature_result`. No UPDATE or DELETE operation is exposed by the `audit_log` module.

The application layer is therefore append-only by convention. However, this convention is not enforced at the database layer. Any process with a writable connection to the SQLite database file can issue an arbitrary `UPDATE` or `DELETE` against `audit_events` rows without triggering any application-level guard or database-level constraint.

Three read functions are present (`get_event`, `list_events`, `list_events_by_grant`), all using `SELECT`. No HTTP endpoint exposes mutation of audit rows.

Audit writes are called from `grant_requests.py` for approve, deny, and revoke actions. They are not called from `grants.py` for any grant lifecycle operation.

---

## Immutability risks

### No database-level write protection (HIGH — confirmed)

The `audit_events` table has no trigger, row-level policy, `CHECK` constraint, or `STRICT` table definition that prevents `UPDATE` or `DELETE`. SQLite does not enforce read-only access at the column or row level without explicit application of `WITHOUT ROWID` or trigger-based protection. Any actor with filesystem access to the database file can modify or erase audit rows without detection.

### No application-level guard against direct database access (HIGH — confirmed)

The application accesses SQLite via a shared connection pool. There is no write-blocking view, no separate read-only database credential for audit reads, and no separation between the credential used to write state tables and the credential used to write audit rows. A compromised application process or internal credential can modify audit rows via the same connection used for normal operations.

### tamper_grant() bypasses grant signature without access control (MEDIUM — confirmed)

`backend/src/grants.py` contains a `tamper_grant()` function that issues a direct `UPDATE` on a grant row, deliberately invalidating its signature without re-signing. The function carries a demo comment but has no environment guard, feature flag, or authorization check preventing its invocation in a production context. While this directly affects grant integrity rather than the audit log, it demonstrates that no database-level constraint prevents mutation of sensitive rows.

---

## Transactional integrity risks

### approve_grant_request() audit written outside transaction (HIGH — confirmed)

In `grant_requests.py` lines 119–132, the transaction is committed at line 120 (`conn.commit()`) and the audit event is written afterward at line 123 via `audit_log.append_event(...)` with no `conn` argument. If the process crashes, is killed, or encounters an exception between the commit and the audit write, the state transition is persisted but the audit record is lost. There is no retry, compensating write, or dead-letter mechanism.

### revoke_grant_request() audit written outside transaction (HIGH — confirmed)

In `grant_requests.py` lines 238–250, the same post-commit pattern applies to revocation. The grant revocation and request status update are committed at line 238, and the audit event is written at line 241 outside the transaction. The audit record for a revocation can be silently lost on crash between these two operations.

### deny_grant_request() audit written inside transaction (informational — resolved by existing work)

In `grant_requests.py` lines 176–186, the deny path correctly passes `conn=conn` to `audit_log.append_event()`, making the audit write atomic with the state update. This is the correct pattern and should be adopted by the approve and revoke paths.

### expire_old_requests() has no audit trail (MEDIUM — confirmed)

In `grant_requests.py` lines 262–301, the batch expiration function updates multiple grant requests from `requested` to `expired` state with no call to `audit_log.append_event()`. Expired requests leave no forensic record of when or why they transitioned. This creates a gap in the audit trail for requests that were never explicitly approved, denied, or revoked.

---

## Tamper-evidence gaps

### No hash chain on audit events (HIGH — confirmed)

Each `audit_events` row is independent. There is no sequence number, no previous-row hash, no Merkle root, and no cryptographic commitment linking rows. An adversary who can write to the database can insert, delete, or reorder rows without leaving any detectable artifact. External reference points (log aggregator, SIEM, write-once storage) would be required to detect tampering, but no such integration is present or documented.

### No integrity metadata fields (HIGH — confirmed)

The thirteen fields stored per audit event include no integrity-bearing metadata: no row hash, no HMAC, no signature, no sequence counter, no monotonic ID, and no write-time nonce. Compare with the grant table, which stores `signature`, `signing_key_id`, and `payload_hash` computed at insert time. Audit events have no equivalent protection.

### Grant lifecycle not audited (HIGH — confirmed)

`backend/src/grants.py` contains `create_grant()`, `revoke_grant()`, and `try_consume_grant_use()`. None of these functions call `audit_log.append_event()`. Grant creation, direct revocation, and each individual use consumption are invisible in the audit trail. An auditor reviewing `audit_events` would see approve/deny/revoke actions on grant requests but would have no record of the underlying grant object being created or consumed.

### Grant signature verification not confirmed on read (MEDIUM — suspected)

The grant table stores `signature`, `signing_key_id`, and `payload_hash` fields. The explore agents found no evidence that `grants.get_grant()` or any retrieval path verifies the signature on read. If verification is absent, the stored signature provides write-time integrity only and does not detect post-insert modification. This is outside the direct scope of audit log immutability but is noted as a related tamper-evidence gap.

---

## Test gaps

### No test for audit event immutability (MEDIUM — test_gap)

Existing tests in `test_grant_requests.py` and `test_gl092_deny_revoke_audit_semantics.py` verify that audit events are created and that `approved` is set correctly for approve vs. deny/revoke. No test asserts that an existing audit event cannot be modified or deleted after insertion, that direct UPDATE/DELETE is rejected, or that a row retrieved after an attempted modification is identical to the row at insertion time.

### No test for approve/revoke audit write-after-crash scenario (MEDIUM — test_gap)

No test simulates a crash or exception between the transaction commit and the post-commit audit write in `approve_grant_request()` or `revoke_grant_request()`. The rollback behavior for `deny_grant_request()` is tested in `test_gl092_deny_revoke_audit_semantics.py` (lines 164–184), but the equivalent scenario for the post-commit paths is untested.

### No test for expire_old_requests() audit absence (MEDIUM — test_gap)

No test verifies whether expiration events should or should not appear in the audit trail. The current behavior (no audit on expiry) is untested and undocumented.

---

## Audit failure handling

`audit_log.append_event()` has no internal error handling. Exceptions propagate to the caller. In the `deny_grant_request()` path, this is correct: the exception causes a transaction rollback, preventing state divergence. In the `approve_grant_request()` and `revoke_grant_request()` paths, the audit write occurs after the transaction has already committed. An exception in the post-commit audit write is caught by the outer `except Exception as e` block, which calls `conn.rollback()` — but the transaction was already committed and the rollback has no effect on the state change. The exception is re-raised to the caller, but the audit record is permanently lost for that operation.

---

## Semantic correctness

Audit event semantics for `approved` field are correctly set: `approve_grant_request` uses `approved=True` and `deny_grant_request` / `revoke_grant_request` use `approved=False`. The action field (`approve_grant_request`, `deny_grant_request`, `revoke_grant_request`) provides unambiguous semantic distinction. Tests in `test_gl092_deny_revoke_audit_semantics.py` verify these semantics. No confusion risk between approval and denial/revocation was found in the event data model.

---

## Recommended implementation issues

| Issue ID | Title | Priority | Findings addressed |
|----------|-------|----------|--------------------|
| GL-097 | Enforce audit log immutability at database layer | High | GL094B-FINDING-001, GL094B-FINDING-005, GL094B-FINDING-006 |
| GL-098 | Add hash chain and tamper-evidence fields to audit events | High | GL094B-FINDING-001, GL094B-FINDING-005 |
| GL-099 | Fix approve/revoke transactional audit writes; add expire audit trail | High | GL094B-FINDING-002, GL094B-FINDING-004 |
| GL-100 | Add audit logging to grants.py lifecycle; guard tamper_grant() | Medium | GL094B-FINDING-003, GL094B-FINDING-007 |

**GL-097** should add SQLite triggers (`BEFORE UPDATE`, `BEFORE DELETE`) on `audit_events` that raise an error, or migrate to a write-once partition / ledger table. Database-level enforcement is the only mechanism that prevents bypass by direct database access.

**GL-098** should add a `row_hash` field (SHA-256 of the row fields at insert time) and a `prev_hash` field (hash of the preceding row's `row_hash`) to create a hash chain. The chain can be verified at audit time to detect insertion gaps or row modification.

**GL-099** should refactor `approve_grant_request()` and `revoke_grant_request()` to pass `conn=conn` to `audit_log.append_event()`, matching the correct pattern already used by `deny_grant_request()`. Expiration events should be appended inside the `expire_old_requests()` transaction for each expired request.

**GL-100** should add `audit_log.append_event()` calls to `create_grant()`, `revoke_grant()`, and `try_consume_grant_use()` in `grants.py`. The `tamper_grant()` function should be removed or guarded behind an explicit non-production environment assertion.

---

## Conclusion

**`proceed_with_cautions`**

The GrantLayer MVP audit log is append-only by application convention and has no HTTP-exposed mutation paths. Audit event semantics (approved vs. denied/revoked) are correct and tested. However, four HIGH findings and three MEDIUM findings confirm that the audit trail lacks the database-level immutability enforcement, tamper-evidence, and transactional consistency required for production compliance or forensic reliability. These gaps are not blocking for continued development but must be addressed before any compliance-sensitive deployment. The recommended issues (GL-097 through GL-100) provide a clear remediation path.
