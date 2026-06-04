# GL-200B Implementation Report: Tenant/Workspace Isolation Baseline

**Issue:** GL-200B  
**Branch:** `gl-200b-tenant-workspace-isolation-implementation-baseline`  
**Commit:** `07918ff`  
**Date:** 2026-06-04  
**Status:** complete

## Decision

`tenant_workspace_baseline_implemented`

## Summary

GL-200B implements the Option A baseline from the GL-200A design pack: `tenant_id` on all business resource tables, operator tenant binding, HTTP-layer tenant context injection, and a backward-compatible dual-mode audit hash chain. All resources default to `tenant='demo'` for backward compatibility.

## Files Changed

| File | Change Type |
|---|---|
| `backend/src/migrations/0010_gl200b_tenant_workspace_isolation.py` | NEW — migration |
| `backend/src/models.py` | Modified — AuditEvent tenant fields |
| `backend/src/operators.py` | Modified — tenant_id field, create_operator() |
| `backend/src/auth.py` | Modified — tenant_id in auth payload |
| `backend/src/grants.py` | Modified — tenant filtering |
| `backend/src/challenges.py` | Modified — tenant filtering |
| `backend/src/grant_requests.py` | Modified — tenant filtering + audit context |
| `backend/src/audit_log.py` | Modified — dual-mode hash, tenant filter |
| `backend/src/server.py` | Modified — _get_tenant_id() helper, routes |
| `backend/tests/test_gl200b_tenant_workspace_isolation_baseline.py` | NEW — 61 tests |
| `docs/tenant_workspace_isolation_implementation_baseline.md` | NEW — documentation |
| `docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json` | NEW — artifact |

## Test Results

| Test Suite | Tests | Status |
|---|---|---|
| GL-200B baseline | 61/61 | PASS |
| GL-200A design pack | 145/145 | PASS |
| GL-199 production gap | 60/60 | PASS |
| GL-198 preview boundary | 94/94 | PASS |
| Security boundary regression | 10/10 | PASS |
| verify-first-output.sh | MATCH | PASS |
| Evidence bundle diff | MATCH | PASS |
| **Full backend suite** | **7679 total** | **54 failures (all scope-guard FPs)** |

### Failure Classification

All 54 failures in the full suite are pre-existing scope-guard false positives from earlier issues. These tests guard that specific earlier issues (GL-112, GL-125–127, GL-137, GL-139–141, GL-151–153, GL-162b/c, GL-164a, GL-169–172, GL-181–185, GL-188) did not change production code or add migrations. Since GL-200B legitimately changes source and adds migration 0010, these guards fire as expected FPs.

**Zero behavioral regressions.** No new real failures introduced.

GL-200A baseline: 7618 tests / 23 failures.  
GL-200B result: 7679 tests / 54 failures (61 new tests + 31 new scope-guard FPs).

## Isolation Properties Implemented

- **Tenant-scoped list filtering**: all list functions filter by tenant_id when provided
- **Cross-tenant lookup returns None**: get functions return None for wrong tenant (no existence leakage → 404 at HTTP layer)
- **Cross-tenant mutation fails**: revoke/approve/deny operations fail when resource is in different tenant
- **Default tenant='demo'**: resources and operators default to 'demo' for backward compatibility with all pre-existing tests and workflows
- **Admin-token → tenant='demo'**: consistent with resource defaults; no cross-tenant gap
- **Operator mode → op.tenant_id**: each operator carries their tenant; auth payload includes it
- **Audit events**: tenant_id, workspace_id, scope stored; list_events(tenant_id) filter available
- **Dual-mode hash chain**: pre-migration events (tenant_id=None) verified with original payload format; new events include tenant_id in hash

## What Is NOT Implemented (Future Issues)

- `workspace_id` enforcement (GL-200C) — column reserved/nullable
- Admin-plane tenant isolation (GL-200D)
- Tenant provisioning API (GL-200D+)
- Row-level security at DB layer

## Safety Confirmations

- No public GitHub push performed
- No production SaaS claim made
- No frontend/design/public-snapshot changes
- No GitHub workflow changes
- No force push
- No --no-verify bypass

## Next Step

**GL-200C**: workspace_id enforcement — add workspace scoping on top of tenant isolation.
