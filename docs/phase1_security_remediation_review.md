# GL-094A Phase 1 Security Remediation Review

**Review-only artifact. No production code was changed during this review.**

| | |
|---|---|
| Review ID | GL-094A |
| Base main | `5b63026fdc333f36e4b0a3f6713cf4436ff76a63` |
| Review scope | GL-088 through GL-093 |
| Date | 2026-05-23 |
| Reviewer | Claude Code (automated security review) |

---

## Implementation Status

All six Phase 1 security issues are implemented and covered by tests.

| Issue | Title | Status | Test File |
|-------|-------|--------|-----------|
| GL-088 | Challenge Auth Enforcement | Implemented & Tested | test_gl088_challenge_auth_enforcement.py |
| GL-089 | Auth Default Fail-Closed Startup Gate | Implemented & Tested | test_gl089_auth_default_fail_closed.py |
| GL-090 | Request Body JSON Hardening | Implemented & Tested | test_gl090_request_body_json_hardening.py |
| GL-091 | Signature Auth Cache Hardening | Implemented & Tested | test_gl091_signature_auth_cache_hardening.py |
| GL-092 | Deny/Revoke Audit Semantics & Atomicity | Implemented & Tested | test_gl092_deny_revoke_audit_semantics.py |
| GL-093 | Grant Input Validation | Implemented & Tested | test_gl093_grant_input_validation.py |

---

## Issue Summaries

### GL-088: Challenge Auth Enforcement

POST `/challenges` and GET `/challenges` now require authentication. The `demo_operator` role is explicitly forbidden (403). Owner, `grant_admin`, and `auditor` roles may create challenges. Tests verify 401 for missing auth, 403 for demo_operator, and that public endpoints (`/health`, `/readiness`) remain unauthenticated.

**Gaps noted:** No test for malformed bearer prefix (e.g. `Basic` instead of `Bearer`); no test for an empty bearer token string (`Bearer `).

### GL-089: Auth Default Fail-Closed Startup Gate

`config.py` implements `startup_errors()` and `startup_ok()`. In `production`, `staging`, and `demo` runtime modes, startup fails (exit code 1) if `GRANTLAYER_ADMIN_TOKEN` is empty, `REQUIRE_ADMIN_TOKEN` is not enforced, `REQUIRE_CHALLENGE` is not set, or `ENABLE_DEMO_ENDPOINTS` is true. Local and test modes are intentionally permissive. Error messages never leak token values.

**Gaps noted:** No test for `RUNTIME_MODE` set to an unrecognised value; no test for partial startup-error combinations (some issues but not all).

### GL-090: Request Body JSON Hardening

`server.py` enforces `MAX_JSON_BODY_BYTES` on all mutation endpoints. Missing `Content-Length`, non-integer, negative, or oversized values return 400/413 before the body is read. Malformed JSON returns 400 without leaking parser internals. Tests cover `/grants`, `/challenges`, and `/demo-action`.

**Gaps noted:** No test for chunked transfer encoding; no test for `Content-Length` header case-sensitivity; no test for `Content-Length` value that mismatches actual body length.

### GL-091: Signature Auth Cache Hardening

`verify_grant_signature()` no longer swallows broad `Exception`; only `InvalidSignature` and `ValueError` return `"invalid"`, while unexpected infrastructure errors (e.g. `RuntimeError`, `PermissionError`) propagate. Auth cache keys use SHA-256 hex digest of the raw `Authorization` header, not Python's `hash()`. The cache is request-local per handler instance. Tests confirm raw token strings do not appear as cache keys.

**Gaps noted:** No timing-attack resistance test for signature comparison; no concurrent-request cache isolation test; no test for signatures from unrecognised `signing_key_id` values.

### GL-092: Deny/Revoke Audit Semantics & Atomicity

`deny_grant_request()` rolls back request state (`denied_by`, `denied_at`, `denial_reason`) if the audit log append fails. `revoke_grant_request()` rolls back both the grant and the request if either update fails. Audit events for deny and revoke both carry `approved=False`; approval events carry `approved=True`. Tests verify three-way distinguishability.

**Gaps noted:** `test_deny_failure_is_surfaced` contains a copy-paste bug — the mock assignment is `self.audit_mod.append_event = self.audit_mod.append_event` (a no-op), so the test does not actually verify that the exception surfaces.

### GL-093: Grant Input Validation

`validFrom`/`validUntil` must be valid ISO-8601 strings; `validFrom` must be strictly less than `validUntil`. `maxUses` must be a positive integer — booleans, floats, strings, zero, and negative values are all rejected with `"invalid_max_uses"`. Required string fields must be non-empty and non-whitespace-only. Tests cover the grant-creation endpoint; the grant-request endpoint also validates dates and reason.

**Gaps noted:** `maxUses` validation is not tested on the grant-request endpoint; no test for timestamps beyond year 9999 or for fractional-second precision; no test for timezone offsets outside the valid range.

---

## Findings

### F-001 — HIGH: CORS wildcard allows any origin

**Status:** gap  
**Affected files:** `backend/src/server.py` (line 49)  
**Description:** `Access-Control-Allow-Origin: *` is returned on every response. Any browser origin can make credentialed cross-origin requests to the API. In production this should be restricted to known consumer domains.  
**Recommended issue:** GL-095

---

### F-002 — HIGH: Private key stored without file permission hardening

**Status:** gap  
**Affected files:** `backend/src/crypto_signing.py` (line 42)  
**Description:** The Ed25519 private key is written to `data/demo_ed25519_private_key.pem` using `NoEncryption()`. `os.makedirs` does not set restrictive permissions on the file. If `data/` is world-readable the private key is immediately compromised. The file comment says "Demo only" but no runtime enforcement prevents this being used in non-demo modes.  
**Recommended issue:** GL-096

---

### F-003 — HIGH: Audit log has no immutability protection

**Status:** gap  
**Affected files:** `backend/src/audit_log.py`  
**Description:** Audit events are inserted into `audit_events` via plain `INSERT`. No database trigger, row-level policy, or application constraint prevents subsequent `UPDATE` or `DELETE` on existing rows. An attacker with database write access (or a compromised application credential) can silently alter or erase the audit trail. Entries are also not hash-chained, so tampering is undetectable without an external reference.  
**Recommended issue:** GL-094B

---

### F-004 — MEDIUM: Self-approval enforcement not encapsulated in grant_requests module

**Status:** gap  
**Affected files:** `backend/src/server.py` (lines 917–924), `backend/src/grant_requests.py`  
**Description:** The check that prevents an operator from approving their own request lives in `server.py`, not in `grant_requests.approve_grant_request()`. Any future code path that calls the module function directly bypasses the guard. Authorization invariants should be enforced at the data layer, not only at the HTTP layer.  
**Recommended issue:** GL-097

---

### F-005 — MEDIUM: Denial reason field has no length bound

**Status:** gap  
**Affected files:** `backend/src/grant_requests.py` (line 145)  
**Description:** `deny_grant_request()` accepts an arbitrary `reason` string and stores it in the database without length validation. A caller can write multi-megabyte strings per denial event, causing unbounded database growth and potentially triggering memory pressure during reads.  
**Recommended issue:** GL-097

---

### F-006 — MEDIUM: expire_old_requests() is never triggered

**Status:** gap  
**Affected files:** `backend/src/grant_requests.py` (lines 262–301)  
**Description:** `expire_old_requests()` is implemented but never called — there is no background job, cron trigger, or request-time hook that invokes it. Stale grant requests remain indefinitely in the `"requested"` state, polluting the queue and potentially allowing requests that should have expired to be approved long after their intended window.  
**Recommended issue:** GL-098

---

### F-007 — LOW: GL-092 test has copy-paste bug in deny-failure mock

**Status:** inconsistency  
**Affected files:** `backend/tests/test_gl092_deny_revoke_audit_semantics.py`  
**Description:** `test_deny_failure_is_surfaced` assigns `self.audit_mod.append_event = self.audit_mod.append_event` — a no-op that leaves the real function in place. The test therefore does not verify that an audit failure exception actually surfaces from `deny_grant_request()`. The rollback coverage in adjacent tests is valid, but this specific assertion is not exercised.  
**Recommended issue:** GL-092 follow-up patch

---

## Recommended Next Issues

| Priority | Issue ID | Title | Rationale |
|----------|----------|-------|-----------|
| 1 | GL-094B | Audit log immutability | High-severity gap; compliance and forensic integrity depend on this |
| 2 | GL-095 | CORS origin hardening | High-severity; trivially exploitable in browser-based integrations |
| 3 | GL-096 | Private key file permission enforcement | High-severity key management gap; one-line fix with high value |
| 4 | GL-097 | Grant module: self-approval guard + denial reason length | Encapsulates two medium gaps; prevents auth bypass via future callers |
| 5 | GL-098 | Request expiry background trigger | Medium-severity; feature is implemented but dead without a trigger |

---

## Regressions and Inconsistencies

No functional regressions were found. GL-088 through GL-093 do not break prior GL-080 through GL-087 behaviour. All test suites include regression guards for earlier issues.

One test inconsistency was identified (F-007): a no-op mock in `test_gl092` leaves a specific assertion unverified. This is a test quality issue, not a production code defect.

---

## Conclusion

**`proceed_with_cautions`**

All six Phase 1 security issues (GL-088 through GL-093) are correctly implemented and backed by tests. The codebase is ready to proceed to Phase 2. The three high-severity findings (F-001 CORS wildcard, F-002 unencrypted key, F-003 mutable audit log) should be scheduled as immediate follow-on work before any production deployment. The test inconsistency in GL-092 (F-007) should be patched before the next test suite release.
