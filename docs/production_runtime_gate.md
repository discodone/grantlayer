# GrantLayer Production Runtime Gate

## Purpose

The production runtime gate is a **narrow, fast validation check** that runs
before any staging deployment, production-like deployment, or pilot release
cut. It verifies that runtime mode classification, production-like config
safety, and secret-handling conventions are satisfied.

This gate is **not** a comprehensive test suite. It is a go/no-go decision
point that catches missing or unsafe configuration before deployment.

## Standard Command

```bash
./scripts/run-production-runtime-gate.sh
```

Or directly with unittest:

```bash
python3 -m unittest backend.tests.test_gl126_production_runtime_gate -v
```

## When to Run

- Before every **staging deployment**.
- Before every **production-like deployment**.
- Before cutting a **pilot release**.
- After any **runtime config or secrets change**.
- Before merging a branch that touches `backend/src/runtime_config.py`,
  `backend/src/config.py`, or `.env.example`.

## Go / No-Go Criteria

### Go

- Runtime mode is one of the recognized modes: `local`, `test`, `demo`,
  `staging`, `production`.
- Production-like modes (`staging`, `production`) have all required config:
  - `GRANTLAYER_REQUIRE_ADMIN_TOKEN=true`
  - `GRANTLAYER_ADMIN_TOKEN` is configured
  - `GRANTLAYER_REQUIRE_CHALLENGE=true`
  - `GRANTLAYER_ENABLE_DEMO_ENDPOINTS=false`
- Secret values are **never** printed in gate output, test failures, or docs.
- Local/test/demo modes remain usable for development and CI.

### No-Go

- Unrecognized runtime mode.
- Production-like mode with missing admin token enforcement.
- Production-like mode with missing admin token.
- Production-like mode with missing challenge enforcement.
- Production-like mode with demo endpoints enabled.
- Any gate output that includes raw secret values (tokens, private keys,
  passphrases, database passwords).

## Runtime Modes

| Mode | Production-like | Purpose |
|------|-----------------|---------|
| `local` | No | Developer convenience |
| `test` | No | Deterministic automated verification |
| `demo` | No | Illustrative non-production walkthrough |
| `staging` | Yes | Production-like validation before production |
| `production` | Yes | Explicit hardened operation only |

## Required Config Categories

1. **Runtime mode** — must be explicit and recognized.
2. **Database config** — `GRANTLAYER_DATABASE_URL` or `GRANTLAYER_DB` must be
   explicit in production-like modes (enforced by deployment operator; the
   gate documents this expectation).
3. **Admin/operator auth config** — `GRANTLAYER_REQUIRE_ADMIN_TOKEN` must be
   `true`; `GRANTLAYER_ADMIN_TOKEN` must be present.
4. **Challenge enforcement** — `GRANTLAYER_REQUIRE_CHALLENGE` must be `true`.
5. **Demo endpoints** — `GRANTLAYER_ENABLE_DEMO_ENDPOINTS` must be `false`.
6. **Secret/private-key/passphrase material** — must be configured externally;
   gate reports presence only, never value.

## Secret Handling

The gate and its tests report **presence only**, never value:

- `GRANTLAYER_ADMIN_TOKEN` — reported as configured / not configured.
- `GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN` — reported as configured / not configured.
- `GRANTLAYER_SIGNING_PRIVATE_KEY` — reported as configured / not configured.
- `GRANTLAYER_SIGNING_PRIVATE_KEY_PASSPHRASE` — reported as configured / not configured.
- `GRANTLAYER_DATABASE_URL` — reported as configured / not configured; URL
  fragments are never logged.

## Command Sequence

Run the gate first. If it passes, proceed to smoke tests and the full suite:

```bash
# 1. Production runtime gate (fast)
./scripts/run-production-runtime-gate.sh

# 2. Operational smoke tests (fast)
./scripts/run-operational-smoke-tests.sh

# 3. Full backend suite (comprehensive)
./scripts/run-full-backend-suite.sh
```

## Full Suite Rule

The full backend suite requires a timeout of **>= 900 seconds** and must be run
via:

```bash
./scripts/run-full-backend-suite.sh
```

Do **not** run the full suite through a 120-second-limited shell wrapper.
Coding agents should run targeted tests and relevant regressions instead.
If the environment cannot safely run the full suite with >= 900 seconds,
report exactly:

```
full backend suite: not_run_due_tool_timeout_limit
```

## Failure Handling

If the production runtime gate fails:

1. **Stop** the deployment or release.
2. Inspect the failing check for the root cause.
3. Fix the configuration or environment.
4. Re-run the gate to confirm resolution.
5. Only then proceed to smoke tests and the full suite.

## What the Gate Does **Not** Replace

- **Full backend suite** (`scripts/run-full-backend-suite.sh`) — run that for
  comprehensive regression coverage.
- **Operational smoke test bundle** (`scripts/run-operational-smoke-tests.sh`) —
  run that for quick post-deployment operational checks.
- **PostgreSQL CI gate** — database-specific immutability and connection tests.
- **Backup/restore drill** — operational recovery validation.
- **Monitoring/alerting validation** — observability stack checks.
- **Incident response runbook** — human process verification.
- **Security review / penetration test** — this is a config gate, not an audit.
