# GL-115: Security / Data Integrity / Validation Review Gate

**Issue:** GL-115  
**Review type:** security_data_integrity_validation_review_gate  
**Reviewed after main commit:** `179d7d8bc6ea8203ee86c8047e3ef63aa2707c27` (GL-114 merge)  
**Review date:** 2026-05-25  
**Disposition:** proceed_with_cautions  
**Reviewer:** Claude Code (automated review gate)

---

## 1. Review Scope

This gate reviews the backend/product-core/security state after GL-102 through GL-114. It covers:

- `backend/src/server.py` — HTTP layer, CORS, auth, rate limiting, endpoint handlers
- `backend/src/audit_log.py` — hash-chain audit trail
- `backend/src/grant_requests.py` — grant request lifecycle
- `backend/src/challenges.py` — challenge/response store
- `backend/src/validation.py` — string-length validation helpers
- `backend/src/structured_logging.py` — structured log event builder
- `backend/src/logging_utils.py` — stdlib logging wrapper
- `backend/src/runtime_config.py` — runtime mode detection
- `backend/src/secret_sources.py` — secret boundary helpers
- `backend/src/operators.py` — operator credential management
- `backend/src/rate_limiter.py` — per-IP rate limiting
- `backend/src/db.py` — database connection layer
- `backend/tests/test_gl102*` through `test_gl114*` — per-issue test suites
- `backend/tests/test_security_boundary_regression.py` — security boundary regression suite
- `docs/full_product_readiness_gap_review.md` — GL-101 baseline
- `docs/production_hardening_roadmap.md` — production hardening plan
- `docs/runtime_configuration_environment_model.md` — runtime config design
- `docs/secret_management_baseline_design.md` — secret management design

---

## 2. Current Baseline After GL-114

| Metric | Value |
|--------|-------|
| Total tests | 3,001 |
| Skipped | 38 |
| Failures | 0 |
| Errors | 0 |
| Timeout | none |
| Backend source files | 40 |
| server.py lines | 1,485 |

The baseline is clean. All previously identified critical and high-priority blockers from GL-101 have been addressed by GL-102 through GL-114.

---

## 3. What GL-102–114 Materially Improved

| Issue | What Was Fixed |
|-------|---------------|
| GL-102 | SQLite-level audit event immutability guard (trigger blocks UPDATE/DELETE) |
| GL-103 | SHA-256 hash chain on audit events: `row_hash` and `prev_hash` fields |
| GL-104 | `verify_audit_hash_chain()` helper for offline tamper detection |
| GL-105 | `build_audit_chain_verification_report()` — structured auditor-readable report |
| GL-106 | Per-IP sliding-window rate limiting (auth: 10/min, api: 120/min) |
| GL-107 | O(1) SHA-256 lookup hash eliminates O(n) PBKDF2 loop for invalid tokens |
| GL-108 | PostgreSQL `BEFORE UPDATE/DELETE` triggers on `audit_events` table |
| GL-109 | `/operators/me` fails closed; no identity disclosure on unauthenticated calls |
| GL-110 | Private key encryption/externalization enforced in production-like modes |
| GL-111 | Demo action exceptions logged safely — no stack trace or payload leakage |
| GL-112 | Audit log helper deduplication — no functional change, cleaner module boundary |
| GL-113 | Structured logging baseline: `structured_logging.py` + `logging_utils.py` with redaction |
| GL-114 | String length validation on all user inputs via `validation.py` |

No critical severity issues remain from the GL-101 findings. The audit trust layer (GL-102 through GL-105) is now complete in its SQLite form. The auth performance vulnerability (GL-107) and rate limiting (GL-106) are addressed. Key material externalization (GL-110) is in place.

---

## 4. Remaining Risks

### Summary Table

| ID | Severity | Category | blocks_production | Suggested Issue |
|----|----------|----------|:-----------------:|----------------|
| GL115-F-001 | **high** | persistence | **yes** | GL-116: PostgreSQL Integration Test CI Gate |
| GL115-F-002 | medium | observability | no | GL-117: Structured Logging Integration into server.py |
| GL115-F-003 | medium | observability | no | GL-118: Correlation ID Propagation Baseline |
| GL115-F-004 | medium | security | no | GL-119: Operator Token Expiry and Rotation Baseline |
| GL115-F-005 | medium | security | no | GL-120: Auth Failure Structured Event Logging |
| GL115-F-006 | medium | persistence | no | GL-123: PostgreSQL Connection Pooling Baseline |
| GL115-F-007 | low | architecture | no | GL-121: server.py Modular Decomposition Plan |
| GL115-F-008 | low | security | no | GL-122: Remove BytesIO Content-Length Bypass |
| GL115-F-009 | low | security | no | GL-124: Challenge TTL Runtime Configuration |
| GL115-F-010 | low | security | no | GL-125: Per-Token Rate Limiting Baseline |

---

## 5. Security Boundary Review

**CORS:** `_cors_headers_for()` uses exact-string matching against an allowlist — no wildcards, no prefix matching. Origin values that don't match the allowlist receive no `Access-Control-Allow-Origin` header. **Correct.**

**Authentication:** `_require_auth()` enforces both operator-model and legacy admin-token paths. The `/operators/me` endpoint was fixed in GL-109 to fail closed. All protected endpoints call `_require_auth()` before processing. **Correct.**

**Rate limiting:** GL-106 implemented per-IP sliding-window rate limiting via `RateLimiter`. Auth endpoints: 10 req/min, API endpoints: 120 req/min. The check is applied before request processing. **Correct at the IP level.** Gap: no per-token rate limiting (GL115-F-010).

**Demo gate:** `GRANTLAYER_ENABLE_DEMO_ENDPOINTS` defaults to `false`; the tamper endpoint returns 404 unless explicitly enabled. The security boundary regression suite (10 tests) covers this. **Correct.**

**Challenge validation:** Fail-closed pattern — any unexpected state returns a non-`valid` code. One-time use enforced. TTL enforced. **Correct.** Gap: TTL hardcoded, not runtime-configurable (GL115-F-009).

**Self-approval guard:** `grant_requests.py` prevents the requesting operator from approving their own request. **Correct.**

---

## 6. Data Integrity / Audit Review

**Hash chain:** GL-103 adds `row_hash` (SHA-256 of this row's canonical payload) and `prev_hash` (hash of the previous row) to every audit event. Canonical JSON is deterministic (sorted keys). Genesis hash is `"0" * 64`. **Correct.**

**Verification:** GL-104 `verify_audit_hash_chain()` is read-only and covers both row_hash mismatches and broken chain links. GL-105 `build_audit_chain_verification_report()` provides actionable recommendations per failure. **Correct.**

**Immutability — SQLite:** GL-102 adds a SQLite trigger that raises an exception on UPDATE or DELETE on `audit_events`. **Correct for SQLite.**

**Immutability — PostgreSQL:** GL-108 adds PostgreSQL `BEFORE UPDATE` and `BEFORE DELETE` triggers raising `restrict_audit_mutation`. **Correct in design.** Gap: These triggers are only tested if `psycopg2` and a real PostgreSQL instance are available; the CI suite runs SQLite only. This is the highest-priority remaining gap (GL115-F-001).

**Transactional consistency:** `approve_grant_request()` creates the grant + updates the request + appends an audit event in a single transaction with rollback on failure. **Correct.**

**Skipping pre-chain rows:** The verification helper gracefully skips rows with `NULL` `row_hash` (created before GL-103 migration). **Correct.**

---

## 7. Validation / Request Hardening Review

**String length validation:** GL-114 added `validate_string_length()` and `validate_optional_string_length()` in `validation.py`. Constants: `MAX_SHORT_ID_LENGTH=128`, `MAX_ROLE_LENGTH=64`, `MAX_NAME_LENGTH=256`, `MAX_REASON_LENGTH=1000`. Applied to all user-supplied inputs. **Correct.**

**Body size bound:** `_read_json()` enforces a 1 MB maximum body size via Content-Length check before reading. **Correct.**

**Content-Length check bypass:** Lines 154–166 of `server.py` contain a special case where `BytesIO` rfile inputs skip Content-Length validation with comment "Backward compatibility: test mocks using BytesIO." This is a test-only workaround embedded in the production handler. While not exploitable in current call paths, it is a maintenance risk (GL115-F-008).

**Non-empty string validation:** `_require_non_empty_string()` checks for blank values before length validation. **Correct.**

**Expired request rejection:** GL-098 checks request expiry before processing approval/denial. **Correct.**

---

## 8. Logging / Exception-Safety Review

**Structured logging baseline:** GL-113 provides `structured_logging.py` with `generate_correlation_id()`, `normalize_correlation_id()`, `redact_log_value()`, and `build_log_event()`. Sensitive key detection covers 13+ patterns (password, token, api_key, signing_key, etc.). Secret pattern detection covers Bearer tokens, connection strings, PEM keys. **Design is correct.**

**Integration gap:** `server.py` imports zero functions from `structured_logging.py` or `logging_utils.py`. HTTP request start, completion, auth failures, and rate limit hits produce no structured log events. Production operations teams have no structured observability. (GL115-F-002)

**Correlation ID gap:** `generate_correlation_id()` and `build_request_context()` exist but are never called in `server.py`. No correlation ID is threaded through the request lifecycle or included in audit event metadata. (GL115-F-003)

**Exception safety for demo actions:** GL-111 ensures unexpected exceptions in demo action handlers are logged safely without exposing sensitive data. **Correct.**

**Fail-safe logging:** `logging_utils.py` `safe_log()` never raises; serialization failures produce a minimal fallback output. **Correct.**

---

## 9. Secret / Private-Key Handling Review

**Secret boundary:** `secret_sources.py` never includes secret values in error messages, repr, or str output. `read_required_secret()` raises `SecretConfigurationError` on missing values; the exception safe-repr shows only the key name. **Correct.**

**Key externalization:** GL-110 enforces that production-like modes (`staging`, `production`) may not use demo keypairs. Plaintext keys in `local`/`test` modes require 0o600 file permissions. Production-like modes read from an environment variable or encrypted key file. **Correct.**

**Runtime mode gate:** `runtime_config.py` `is_production_like()` is used as the gate for the GL-089 startup check. Unsupported mode strings raise `ValueError`. **Correct.**

**Secret detection in logs:** `logging_utils.py` blocklists `authorization`, `token`, `password`, `stack_trace`, `evidence`, `payload` from log output. `structured_logging.py` redaction covers recursive structures up to depth 10. **Correct.**

---

## 10. PostgreSQL / Persistence Readiness Review

**Audit immutability triggers:** GL-108 implements the triggers. The test file `test_gl108_postgres_audit_immutability.py` uses `psycopg2` but skips if the library is unavailable. No CI matrix runs PostgreSQL. **Gap: GL115-F-001 — must be resolved before production deployment.**

**Connection management:** `db.py` and all source modules use direct `sqlite3`/`psycopg2` connections without a connection pool. Under concurrent production load (multiple simultaneous HTTP requests), PostgreSQL will exhaust max_connections. Each connection setup adds ~10–50ms latency per request. **Gap: GL115-F-006.**

**Schema migrations:** The migrations directory exists and contains versioned SQL files. No automated migration runner is wired into the server startup path (intentional for the current phase). **Acceptable at this stage.**

---

## 11. Production-Readiness Conclusion

**Disposition: proceed_with_cautions**

The hardening work from GL-102 through GL-114 resolves all 2 critical and 8 of the 10 high-priority blockers identified in the GL-101 full product readiness gap review. The audit trust layer is architecturally complete. Auth performance, rate limiting, key externalization, and input validation are in place.

The single remaining production blocker is GL115-F-001: the PostgreSQL audit immutability triggers implemented in GL-108 are not CI-gated against a real PostgreSQL instance. Audit tamper-protection is the most critical production security guarantee. Until automated CI verifies the triggers work correctly under concurrent modification attempts, deployment to production should be withheld.

The five medium-severity findings (GL115-F-002 through GL115-F-006) are material quality and operational gaps but do not constitute security vulnerabilities that would expose user data or allow unauthorized access. They should be addressed before production but do not individually block the next implementation iteration.

---

## 12. Prioritized Recommended Next Issues

| Priority | Issue | Severity | Rationale |
|----------|-------|----------|-----------|
| 1 | **GL-116: PostgreSQL Integration Test CI Gate** | high | Only production blocker; audit immutability unverified in CI |
| 2 | **GL-117: Structured Logging Integration into server.py** | medium | Operations team needs structured observability |
| 3 | **GL-118: Correlation ID Propagation Baseline** | medium | Cross-request tracing prerequisite for incident response |
| 4 | **GL-119: Operator Token Expiry and Rotation Baseline** | medium | Credential lifecycle gap; compromised tokens have indefinite validity |
| 5 | **GL-120: Auth Failure Structured Event Logging** | medium | Auth failures are invisible in audit log; anomaly detection impossible |
| 6 | **GL-123: PostgreSQL Connection Pooling Baseline** | medium | Production scalability; direct connections exhaust max_connections |
| 7 | **GL-121: server.py Modular Decomposition Plan** | low | Maintainability; 1,485-line monolith |
| 8 | **GL-122: Remove BytesIO Content-Length Bypass** | low | Test workaround in production code path |
| 9 | **GL-124: Challenge TTL Runtime Configuration** | low | Operational flexibility; hardcoded 5-minute TTL |
| 10 | **GL-125: Per-Token Rate Limiting Baseline** | low | Defense-in-depth; IP-based limit bypassable with distributed clients |

**Recommended first implementation issue after GL-115:** GL-116 — PostgreSQL Integration Test CI Gate.

GL-116 scope: add a `docker-compose.test.yml` (or equivalent) that starts PostgreSQL, applies the GL-108 trigger SQL, and runs `test_gl108_postgres_audit_immutability.py` against the live database. No production code changes. No API changes. No schema changes beyond what GL-108 already defines.
