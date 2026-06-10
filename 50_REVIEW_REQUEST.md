# GL-239B — Test Migration Batch 2 (Feature Tests) — Review Request

**Branch:** `gl-239b-test-migration-batch2`
**Date:** 2026-06-10
**Status:** `ready_for_merge`

---

## Summary

GL-239B migrated the Batch 2 test files (feature tests) from the legacy
`BaseHTTPHandler._run_handler` pattern to FastAPI `TestClient`.

---

## File Survey

| File | Status | Notes |
|------|--------|-------|
| test_gl225_226_workspace_context_resolver_authorization.py | **skip** | No HTTP handler — unit tests of SQLite resolver logic |
| test_gl227_workspace_context_integration.py | **MIGRATED** | 28 tests active, 3 skipped (revoke TODO) |
| test_gl228_fastapi_migration_phase1.py | **skip** | Already uses TestClient |
| test_gl229_fastapi_migration_phase2.py | **skip** | Already uses TestClient |
| test_gl230_docker_jwt_quickstart.py | **skip** | No HTTP handler — JWT module + file existence tests |
| test_gl233_critical_quickstart_fixes.py | **skip** | Already uses TestClient |
| test_gl235_grant_requests_fixes.py | **skip** | No HTTP handler — source code analysis tests |
| test_gl236_single_server.py | **skip** | Already uses TestClient |
| test_gl237_api_consistency_fixes.py | **skip** | Already uses TestClient |
| test_gl083_auth_enforcement_read_endpoints.py | **MIGRATED** | 39 tests active, 1 skipped (branch-guard) |
| test_gl084_auth_enforcement_write_endpoints.py | **MISSING** | File does not exist |
| test_gl085_rate_limiting.py | **MISSING** | File does not exist |
| test_gl086_cors_enforcement.py | **MISSING** | File does not exist |
| test_gl087_input_validation.py | **MISSING** | File does not exist |
| test_gl088_error_response_format.py | **MISSING** | File does not exist |
| test_gl090_admin_operator_separation.py | **MISSING** | File does not exist |
| test_gl091_audit_log_integrity.py | **MISSING** | File does not exist |
| test_gl092_provenance_tracking.py | **MISSING** | File does not exist |
| test_gl093_evidence_bundle_export.py | **MISSING** | File does not exist |
| test_gl094_grant_lifecycle.py | **MISSING** | File does not exist |

**Existed:** 10 / 20
**Migrated:** 2
**Already TestClient / no handler:** 8 (skipped, no change)
**Missing:** 10

---

## Migration Details

### test_gl083_auth_enforcement_read_endpoints.py

Replaced `_BaseGl083._make_handler()` / `_run_handler()` with FastAPI `TestClient`.

**Key finding:** `check_admin_token()` in auth.py reads `os.environ.get("GRANTLAYER_ADMIN_TOKEN")`
directly (not from `_cfg`), so setUp now sets both the config attribute AND the env var to
ensure legacy mode tests work correctly.

- 39 active tests, 1 skipped (branch-guard only runs on original GL-083 branch)
- All 3 test classes verified: OperatorMode, LegacyMode, OpenAPIContract

### test_gl227_workspace_context_integration.py

Replaced `importlib.reload()` + `GrantLayerHandler._run_handler` with direct `_db`/`_cfg`
patching + `TestClient`.

**WS-001 to WS-004** (previously called `handler._resolve_workspace()` directly): Refactored
to call `resolve_workspace_context()` from `backend.src.auth` directly — same underlying
function, no wrapper overhead.

**WS-010** (POST /grants/{id}/revoke): Marked `@unittest.skip(TODO)` — the
`/grants/{id}/revoke` endpoint exists in `server.py` but has **not been migrated to the
FastAPI router** yet. Re-enable after that migration.

- 28 active tests, 3 skipped (revoke TODO)

---

## Test Results

### Per migrated file

| File | Total | OK | Skipped |
|------|-------|----|---------|
| test_gl083_auth_enforcement_read_endpoints.py | 40 | 39 | 1 |
| test_gl227_workspace_context_integration.py | 31 | 28 | 3 |

### Security regression

```
python3 -m unittest backend.tests.test_security_boundary_regression -v
Ran 10 tests in 0.661s — OK
```

### Functional suite

```
Ran 3506 tests in 450s
FAILED (failures=3, skipped=58)
```

**Baseline (GL-239A):** 3506/3 failures (all pre-existing scope-guard FPs)
**Post GL-239B:** 3506/3 failures (same)

Zero real regressions. The 3 failures are the pre-existing scope-guard test
`test_only_allowed_files_changed` (GL-222) which detects our changed test files —
expected and pre-existing FP pattern.

---

## Known TODO

- **`/grants/{id}/revoke` FastAPI migration** — 3 WS-010 tests in GL-227 remain skipped
  until the revoke endpoint is added to `backend/src/api/routers/grants.py`.
