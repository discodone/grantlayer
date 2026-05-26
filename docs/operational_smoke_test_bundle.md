# Operational Smoke Test Bundle

## Purpose

The operational smoke test bundle provides a **fast, focused validation suite**
for quick post-deployment or pre-release confidence checks. It exercises the
most critical operational paths without running the full backend test suite.

## Standard Command

```bash
./scripts/run-operational-smoke-tests.sh
```

Or directly with unittest:

```bash
python3 -m unittest backend.tests.test_gl125_operational_smoke_bundle -v
```

## When to Run

- Immediately after deployment to verify the system is live.
- Before cutting a release candidate.
- After configuration or secret rotations.
- Before or after hotfixes to confirm core boundaries are intact.

## What It Checks

| Area | Representative Check |
|------|----------------------|
| **Health / Readiness** | `GET /health` returns 200 without leaking secrets. `GET /readiness` returns 200 or 503 with correct shape. |
| **Auth Boundary** | Protected endpoints reject missing and invalid tokens. Authorized requests succeed. |
| **Payload Validation** | Invalid JSON, top-level non-object JSON, and oversized bodies are rejected safely (GL-124). |
| **Correlation ID** | `X-Correlation-ID` is echoed in success and rejection responses. |
| **Structured Logging Safety** | Auth/rejection events include `correlation_id`. Logs do **not** contain raw `Authorization` headers, tokens, or request bodies. |
| **Security Boundary** | Multiple protected endpoints uniformly require authentication. |

## What It Does **Not** Replace

- **Full backend suite** (`scripts/run-full-backend-suite.sh`) — run that for
  comprehensive regression coverage.
- **PostgreSQL integration CI gate** — database-specific behavior is not exercised.
- **Security review / penetration test** — this is a smoke test, not an audit.
- **Backup/restore drill** — operational recovery is out of scope.

## Full Suite Rule

The full backend suite requires a timeout of **>= 900 seconds** and must be run
via:

```bash
./scripts/run-full-backend-suite.sh
```

Do **not** run the full suite through a 120-second-limited shell wrapper.

## Expected Result

```
0 failures / 0 errors
```

## Failure Handling

If any smoke test fails:

1. **Stop** the release or deployment.
2. Inspect the **first failing test** for the root cause.
3. Fix the issue before proceeding.
4. Re-run the smoke bundle to confirm resolution.
