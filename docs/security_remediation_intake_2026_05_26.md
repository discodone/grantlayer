# GrantLayer Security Remediation Intake

> GrantLayer issues time-boxed access grants, enforces them through policy, and records every decision in a verifiable audit trail.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Title and Scope

This document is the **GL-135 Security Remediation Intake**.
It creates a review, artifact, and test-only remediation intake package that
formally inserts the remediation block before tenant/workspace implementation.

This issue integrates two independent review artifacts into a single
machine-readable and human-readable package so that the remediation roadmap
is visible, sequenced, and gated before any implementation work begins.

**This is NOT remediation implementation.**
**This is NOT production code.**
**This is NOT key removal.**
**This is NOT git history rewrite.**
**This is NOT dependency installation.**
**This is NOT ThreadingHTTPServer enablement.**
**This is NOT auth behavior change.**
**This is NOT tenant/workspace implementation.**

## 2. Input Artifacts

GL-135 integrates the following review artifacts dated 2026-05-26:

| Artifact | Date | Source | Purpose |
|----------|------|--------|---------|
| Senior Developer Review 2026-05-26 | 2026-05-26 | Senior review of current backend posture | Identify security, hygiene, and structural findings before remediation scheduling |
| Remediation Plan 2026-05-26 | 2026-05-26 | Derived from senior review | Convert findings into sequenced, severity-ranked remediation issues |

Both artifacts are considered integrated when the following sections
(Current State, Integrated Findings, Severity, Corrected Roadmap, Sequencing Rules,
Explicit Non-Goals, and Final Statement) are present in this document and in
the corresponding JSON artifact.

## 3. Current State

| Field | Value |
|-------|-------|
| GL-128 through GL-134 completed | **Yes** |
| GL-134 Pilot Partner Dry Run completed | **Yes** |
| Controlled pilot preparation is strong | **Yes** |
| Production SaaS is complete | **No** |
| Multi-tenant isolation is implemented | **No** |
| Remediation block inserted | **Yes (by GL-135)** |
| Tenant/workspace implementation started | **No** |

GL-128 through GL-134 are complete. The controlled pilot preparation is strong.
Production SaaS remains blocked by remediation and tenant/workspace implementation.
No tenant/workspace data model, authorization, or isolation is implemented yet.

## 4. Integrated Findings

The senior review identified the following findings that must be remediated
before production SaaS can be claimed. Each finding is documented here with
enough context for the reader to understand why it is relevant and what issue
will address it.

1. **Committed demo private key / key hygiene** — A demo Ed25519 private key
   is tracked in the repository. This is a hygiene and secret-management
   concern that must be resolved before any production claim.
   - Corrected roadmap: GL-136
2. **Missing Python dependency manifest** — There is no `requirements.txt`,
   `pyproject.toml`, `setup.py`, `Pipfile`, or equivalent committed manifest
   that records the exact runtime and development dependencies.
   - Corrected roadmap: GL-137
3. **Duplicate check_admin_token stub** — A duplicate or redundant
   `check_admin_token` stub exists in the codebase. This creates maintenance
   confusion and risks divergence in auth enforcement.
   - Corrected roadmap: GL-138
4. **Single-threaded HTTPServer** — The server uses the base `HTTPServer`
   rather than `ThreadingHTTPServer`. This limits concurrency and prevents
   horizontal load handling.
   - Corrected roadmap: GL-140 (after GL-139)
5. **Audit hash-chain race condition if threading is enabled** — The audit
   hash-chain (`row_hash`, `prev_hash`) computation does not use a write lock.
   Enabling threading without a write lock creates a race condition that can
   break tamper-evident integrity.
   - Corrected roadmap: GL-139
6. **ENABLE_OPERATOR_MODEL false default** — The operator model feature flag
   defaults to `false`. For production SaaS this should default to `true` and
   legacy paths should be deprecated.
   - Corrected roadmap: GL-141
7. **BytesIO test hack in production _read_json** — The `_read_json` utility
   in the backend contains a `BytesIO` check that exists only to support tests.
   This test-only code should not run in production-path parsing.
   - Corrected roadmap: GL-142
8. **server.py god-file / route decomposition** — Routing logic is concentrated
   in a single large file (`server.py`). This complicates review, testing, and
   maintenance and should be decomposed into route modules.
   - Corrected roadmap: GL-143
9. **In-memory rate limiter not horizontally scalable** — The current rate
   limiter stores state in memory. It cannot scale across multiple processes
   or machines.
   - Corrected roadmap: GL-144 is tenant/workspace; distributed rate limiter
     is a future horizontal-scaling concern (P3).

## 5. Severity

### P0 — Block production SaaS unconditionally

- **Committed demo private key / key hygiene** — Tracked demo secrets are
  unacceptable in any production claim.

### P1 — Block production SaaS until fixed

- **Missing Python dependency manifest** — Reproducible builds and supply-chain
  visibility require a committed manifest.
- **Duplicate check_admin_token stub** — Auth enforcement divergence risk.
- **Audit hash-chain write lock** — Tamper-evident integrity risk under
  concurrent writes.
- **ThreadingHTTPServer only after/with audit lock** — Concurrency improvement
  must not be enabled until the audit lock is in place.
- **Operator model default true and legacy deprecation** — The default must
  favor the secure path; legacy paths must be scheduled for removal.
- **BytesIO test hack removal** — Production parsing must not contain
  test-only branches.

### P2 — Important but not a production blocker

- **server.py route decomposition** — Structural cleanup that improves
  maintainability and reviewability.

### P3 — Future horizontal-scaling concern

- **Redis/distributed rate limiter for horizontal scaling** — Replaces the
  in-memory rate limiter with a distributed implementation when multi-instance
  deployment is required.

## 6. Corrected Roadmap

The following issues replace or precede the prior tenant/workspace roadmap
(GL-132 Section 10) with a remediation block that must be completed before
any production SaaS claim is made.

| Issue | Title | Purpose |
|-------|-------|---------|
| GL-136 | Remove Demo Private Key From Tracking / Add Key Hygiene Gate | Remove the demo Ed25519 private key from repository tracking and add a key-hygiene gate (e.g., pre-commit or CI scan) so that no private key can be committed in the future. |
| GL-137 | Add Python Dependency Manifest | Add a committed `requirements.txt` and/or `pyproject.toml` that records exact runtime and development dependencies with pinned versions. |
| GL-138 | Remove Duplicate check_admin_token Stub | Consolidate or remove the duplicate `check_admin_token` stub so that exactly one auth-enforcement path exists. |
| GL-139 | Audit Hash-Chain Write Lock Baseline | Add a write lock around audit hash-chain computation so that concurrent audit inserts do not corrupt the `row_hash` / `prev_hash` chain. |
| GL-140 | ThreadingHTTPServer Enablement | Replace `HTTPServer` with `ThreadingHTTPServer` only after GL-139 is implemented and tested. |
| GL-141 | Operator Model Default True / Legacy Deprecation | Change `ENABLE_OPERATOR_MODEL` default to `true` and deprecate the legacy auth path with a documented removal timeline. |
| GL-142 | Remove BytesIO Test Hack From _read_json | Remove the `BytesIO` test-only branch from the production `_read_json` utility; keep test concerns in tests only. |
| GL-143 | server.py Route Decomposition Plan | Decompose the monolithic `server.py` into focused route modules without changing endpoint behavior or OpenAPI contract. |

After the remediation block is complete, tenant/workspace implementation
continues with the existing planned issue:

| Issue | Title | Purpose |
|-------|-------|---------|
| GL-144 | Tenant / Workspace Data Model Design | Design tenant and workspace entities, identifiers, and database schema. |

## 7. Sequencing Rules

The following sequencing rules must be respected:

1. **ThreadingHTTPServer must not be enabled before audit hash-chain write
   locking is implemented and tested.**
   - GL-139 must be completed before GL-140 begins.
   - The test suite for GL-139 must verify that concurrent audit inserts
     produce a valid hash chain.
2. **Production SaaS must not be claimed until P0/P1 remediations and
   tenant/workspace boundaries are implemented.**
   - All P0 and P1 items (GL-136 through GL-142) must be completed and
     their tests passing.
   - GL-144 (tenant/workspace data model) must be completed and its tests
     passing.
   - Only then may the backend be described as production SaaS ready.
3. **Full backend suite must use `scripts/run-full-backend-suite.sh`, not a
   120-second-limited wrapper.**
   - Any CI or local runner that invokes the full suite must use the
     standard runner script; timeout-limiting wrappers that silently
     truncate results are forbidden.

## 8. Explicit Non-Goals

The following changes are explicitly out of scope for GL-135:

- **No code remediation in GL-135** — GL-135 does not implement any of the
  findings listed in Sections 4 and 5.
- **No key removal/history rewrite in GL-135** — GL-135 does not remove keys
  or rewrite git history; that is GL-136.
- **No dependency changes in GL-135** — GL-135 does not add, remove, or pin
  dependencies; that is GL-137.
- **No runtime behavior changes in GL-135** — GL-135 does not change server,
  auth, audit, or API behavior.
- **No tenant implementation in GL-135** — no tenant entity, model, or
  identifier is added.
- **No workspace implementation in GL-135** — no workspace entity, model, or
  identifier is added.
- **No production code changes** (`backend/src/`).
- **No API / OpenAPI change** — no endpoint behavior or OpenAPI specification
  is changed.
- **No DB migration or schema change**.
- **No dependency additions or version changes**.
- **No website, landing page, design, brand, or marketing file changes**.
- **No deployment automation, monitoring backend integration, or incident
  automation**.

## 9. Final Statement

> GL-135 inserts the **remediation block before tenant/workspace
> implementation**. It documents the integrated findings from the Senior
> Developer Review 2026-05-26 and the Remediation Plan 2026-05-26, assigns
> severity rankings (P0/P1/P2/P3), establishes a corrected roadmap
> (GL-136 through GL-144), defines sequencing rules, and lists explicit
> non-goals. It does **not** implement any remediation, remove any keys,
> change any runtime behavior, or add any tenant/workspace code.
> It does **not** authorize production SaaS or a shared multi-tenant
> environment.

(End of file)
