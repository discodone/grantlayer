# GrantLayer Product Foundation Implementation Cut (GL-074)

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose and non-goals

This document defines the **first implementation cut** after the Product Foundation design sequence (GL-064 through GL-073). It turns the readiness review into an executable implementation plan by ordering workstreams, defining safe boundaries, and stating what must remain true after each block.

It does not implement anything. It is a planning and sequencing artifact.

**GL-074 explicitly states:**
- GL-074 adds no implementation.
- GL-074 does not implement runtime configuration.
- GL-074 does not implement auth or operator access.
- GL-074 does not implement secret management.
- GL-074 does not implement persistence or PostgreSQL.
- GL-074 does not implement observability, logging, metrics, or tracing.
- GL-074 does not implement backup, restore, or data lifecycle jobs.
- GL-074 does not implement incident response, alerting, or monitoring.
- GL-074 does not implement deployment, Docker, or infrastructure.
- GL-074 does not change API behavior or the OpenAPI contract.
- GL-074 does not modify the database schema or migrations.
- GL-074 does not change the frontend or dashboard.
- GL-074 does not make GrantLayer production-ready.

## 2. Implementation ordering

The recommended order for the first implementation cut prioritizes **foundational enablers** before **dependent systems**:

| Sequence | Issue | Focus | Dependency |
|----------|-------|-------|------------|
| 1 | GL-076 | Runtime configuration enforcement baseline | None |
| 2 | GL-077 | Health / readiness endpoint baseline | GL-076 |
| 3 | GL-078 | Structured logging helper / correlation ID baseline | GL-076 |
| 4 | GL-079 | Secret source boundary hardening | GL-076, GL-078 |
| 5 | GL-080 | Persistence backend abstraction groundwork | GL-076, GL-078 |
| 6 | GL-081 | Deployment / runtime mode validation | GL-076, GL-077 |
| 7 | GL-082 | Operator access hardening | GL-076, GL-078, GL-079 |
| 8 | GL-083 | Claude Code review-only checkpoint (security/runtime) | GL-076 through GL-082 design alignment |
| 9 | GL-084+ | Backup / restore / data lifecycle jobs | GL-080, GL-082 |
| 10 | GL-085+ | Observability metrics and alerting | GL-077, GL-078 |
| 11 | GL-086+ | Incident response automation | GL-077, GL-085 |

This ordering ensures that every block adds value without requiring downstream blocks to be complete first.

## 3. Small safe issue boundaries

Each implementation block in the first cut must remain **small and safe**:

- **Maximum scope**: one foundation area per issue.
- **Maximum file count**: target fewer than 10 changed files per issue.
- **No cross-area rewrites**: an issue must not refactor auth while implementing logging.
- **No schema changes unless explicitly scoped**: persistence groundwork may touch the abstraction layer, but must not rewrite the database schema unless the issue explicitly scopes schema work.
- **No OpenAPI changes**: these blocks are backend-only; the OpenAPI contract remains unchanged until a future contract-freeze issue.
- **No frontend changes**: dashboard and UI remain untouched.
- **No deployment infrastructure changes**: Docker, orchestration, and infrastructure are out of scope for the first cut.

## 4. Suggested GL-076+ sequence

### GL-076 — Runtime configuration enforcement baseline
- **Goal**: Implement the runtime configuration model designed in GL-066.
- **Scope**: Environment variable parsing, runtime mode detection, configuration validation helper (`backend/src/runtime_config.py`), fail-fast `ValueError` for unsupported modes, and safe metadata inspection (`describe_runtime_config`).
- **Allowed files**: `backend/src/runtime_config.py` (new), `backend/tests/test_gl076_runtime_configuration_enforcement.py`.
- **Forbidden changes**: No OpenAPI changes, no frontend changes, no database schema changes.

### GL-077 — Health / readiness endpoint baseline
- **Goal**: Add coarse health and readiness endpoints that operators and future runbooks can use.
- **Scope**: `/health` and `/ready` handlers, lightweight dependency checks (config loaded, database reachable), and structured response schemas.
- **Allowed files**: backend/src/health.py (new), backend/tests/test_gl077_health_readiness_baseline.py.
- **Forbidden changes**: No auth enforcement at these endpoints (they must remain accessible for health probes), no frontend changes.

### GL-077 — Structured logging helper / correlation ID baseline
- **Goal**: Introduce a structured logging helper that emits GL-071-compliant events and attaches correlation IDs.
- **Scope**: Logger factory, correlation ID middleware/generator, field catalog compliance, and redaction of secrets in log output.
- **Allowed files**: backend/src/logging_helper.py (new), backend/tests/test_gl077_structured_logging_baseline.py.
- **Forbidden changes**: No rewriting of existing log statements (gradual adoption), no OpenAPI changes.

### GL-078 — Secret source boundary hardening
- **Goal**: Abstract secret retrieval behind a boundary so that demo keys can be replaced by managed secrets without changing consumers.
- **Scope**: Secret source interface, environment-based secret loader, and migration path away from the demo Ed25519 keypair.
- **Allowed files**: backend/src/secrets.py (new), backend/tests/test_gl078_secret_source_boundary.py.
- **Forbidden changes**: No full HSM integration yet, no vault implementation unless scoped, no auth behavior changes.

### GL-079 — Persistence backend abstraction groundwork
- **Goal**: Solidify the persistence backend abstraction so PostgreSQL can be wired in cleanly.
- **Scope**: Database session factory abstraction, connection pool configuration placeholder, and runtime-driven backend selection.
- **Allowed files**: backend/src/persistence.py or backend/src/db/* (new or existing), backend/tests/test_gl079_persistence_backend_abstraction.py.
- **Forbidden changes**: No schema rewrites, no migration rewrites, no data loss.

### GL-080 — Deployment / runtime mode validation
- **Goal**: Validate that the application refuses to start in an invalid or mismatched runtime mode.
- **Scope**: Startup assertions for runtime mode vs. configuration consistency, deployment artifact validation, and graceful failure modes.
- **Allowed files**: backend/src/deployment_validation.py (new), backend/tests/test_gl080_deployment_runtime_mode_validation.py.
- **Forbidden changes**: No Docker changes, no infrastructure changes, no deployment scripts changes.

### GL-081 — Operator access hardening
- **Goal**: Strengthen operator authentication and authorization boundaries.
- **Scope**: Operator role enforcement, token validation improvements, and access boundary checks for sensitive endpoints.
- **Allowed files**: backend/src/auth/* (existing), backend/tests/test_gl081_operator_access_hardening.py.
- **Forbidden changes**: No OAuth/JWT/SSO implementation unless explicitly scoped, no breaking changes to existing admin-token paths for existing tests.

### GL-082 — Claude Code review-only checkpoint (security / runtime)
- **Goal**: Review-only checkpoint to validate that GL-076 through GL-082 implementations align with the design documents and do not introduce forbidden changes.
- **Scope**: No code changes. Review diff, test coverage, and rollback feasibility.
- **Allowed files**: Review comments, updated planning docs only.
- **Forbidden changes**: No implementation code changes during this checkpoint.

## 5. Which implementation blocks must remain small

All blocks in GL-076 through GL-082 must remain small. Specifically:

- **GL-076 (runtime config)**: must not grow into a full configuration-management system.
- **GL-077 (health endpoints)**: must not grow into a full observability stack.
- **GL-078 (structured logging)**: must not rewrite every existing log line in one issue.
- **GL-079 (secret boundary)**: must not grow into a full vault or HSM integration.
- **GL-080 (persistence abstraction)**: must not rewrite the whole data layer.
- **GL-081 (deployment validation)**: must not implement containers or orchestration.
- **GL-082 (operator access)**: must not implement OAuth, SSO, or mTLS in the first cut.

## 6. Which blocks require full backend suite gates

Every implementation block from GL-076 onward must pass the full backend suite with zero failures and zero errors before it can be considered complete. No exceptions.

The following blocks are especially sensitive and must also pass targeted tests before the full suite:

- **GL-076**: targeted tests for configuration validation edge cases.
- **GL-077**: targeted tests for health endpoint responses and dependency failure simulation.
- **GL-078**: targeted tests for secret redaction and field catalog compliance.
- **GL-079**: targeted tests for secret retrieval failure and fallback behavior.
- **GL-080**: targeted tests for backend switching and connection error handling.
- **GL-081**: targeted tests for invalid runtime mode rejection.
- **GL-082**: targeted tests for unauthorized access rejection and authorized access success.

## 7. Which blocks require optional Claude Code review-only gate before starting

A **Claude Code review-only gate** is suggested before starting the following blocks, but it is **not a required step for every issue**:

- **GL-076**: review the design-to-code mapping for runtime configuration.
- **GL-079**: review secret handling to ensure no secrets are leaked in code, tests, or logs.
- **GL-082**: review auth boundary changes to ensure no accidental lockouts or bypasses.

## 8. Rollback considerations

Every implementation block must include a rollback plan:

- **Code rollback**: every block must be revertible by a single revert commit that restores the previous state.
- **Configuration rollback**: runtime configuration changes must degrade gracefully to defaults.
- **Database rollback**: persistence changes must not introduce irreversible schema migrations in the first cut. If a migration is unavoidable, a tested down-migration must be provided.
- **Auth rollback**: operator access changes must not break existing admin-token or operator-token paths used by tests.
- **Secret rollback**: secret source changes must fall back to the previous retrieval path if the new source fails.

## 9. Test strategy per implementation block

| Block | Targeted tests | Full suite gate | Regression tests |
|-------|---------------|-----------------|------------------|
| GL-076 | Config validation, env override, fail-fast | Yes | GL-055, GL-058, GL-061 |
| GL-077 | Health/readiness responses, dependency checks | Yes | GL-055, GL-073 |
| GL-078 | Secret redaction, correlation ID, field catalog | Yes | GL-071 |
| GL-079 | Secret retrieval, fallback, boundary isolation | Yes | GL-068 |
| GL-080 | Backend switching, connection handling | Yes | GL-070, GL-072 |
| GL-081 | Runtime mode validation, startup asserts | Yes | GL-069 |
| GL-082 | Auth success/failure, role enforcement | Yes | GL-067, GL-073 |

All targeted tests must be written in the same issue as the implementation and must pass locally and in CI.

## 10. Production-readiness disclaimer

**GrantLayer is not production-ready yet.**

The implementation cut defined in this document is the first step toward closing P0 production-hardening gates. Completing GL-076 through GL-082 will improve the foundation, but it will not make GrantLayer production-ready. Production readiness requires:

- All P0 gates from `docs/production_hardening_roadmap.md` to be implemented and verified.
- PostgreSQL to be a first-class CI target.
- Backup/restore jobs to be implemented and tested.
- Observability metrics and alerting to be operational.
- Incident response automation to be in place.
- A completed API contract freeze process.
- External security or compliance review if required by the pilot partner.

Do not claim production readiness until all of the above are complete.

---

## See also

- [`docs/product_foundation_readiness_review.md`](product_foundation_readiness_review.md) — GL-074 readiness review
- [`docs/production_hardening_roadmap.md`](production_hardening_roadmap.md) — GL-063 production-hardening roadmap
- [`docs/examples/gl074/product_foundation_implementation_backlog.json`](examples/gl074/product_foundation_implementation_backlog.json) — machine-readable implementation backlog
- [`backend/tests/test_gl074_product_foundation_readiness_cut.py`](../backend/tests/test_gl074_product_foundation_readiness_cut.py) — validation test for this implementation cut
