# GrantLayer Test Suite

This directory contains all tests for the GrantLayer backend.

---

## Running Tests

```bash
# Functional tests only (recommended for development)
./scripts/run-functional-tests.sh
# or: python3 -m unittest discover -s backend/tests -v

# Full suite including documentation checks
./scripts/run-full-backend-suite.sh
# or: make test-all (if make is available)

# Single test module
python3 -m unittest backend.tests.<test_module> -v

# Security boundary regression (run this on every branch)
python3 -m unittest backend.tests.test_security_boundary_regression -v
```

---

## Test Categories

### Functional Tests (~120 files, ~3400 tests)

These test real backend behavior: API endpoints, database operations, authentication,
grant lifecycle, audit chain, workspace enforcement.

Key test files:

| File | What it tests |
|------|---------------|
| `test_security_boundary_regression.py` | Core security invariants (demo endpoint, auth fail-closed) |
| `test_e2e_mvp_workflow.py` | End-to-end grant workflow |
| `test_product_core.py` | Core grant and audit functionality |
| `test_grant_requests.py` | Grant request / approval workflow |
| `test_grant_executions.py` | Grant execution tracking |
| `test_operators.py` | Operator authentication and management |
| `test_policy_engine.py` | Grant policy evaluation |
| `test_admin_token.py` | Admin token auth behavior |
| `test_api_error_contract.py` | API error response shape |
| `test_evidence_bundle.py` | Evidence bundle generation |
| `test_evidence_audit_contract.py` | Audit event contract |

The remaining `test_gl*.py` files in the functional category test specific
hardening and feature work (auth enforcement, rate limiting, signature verification,
workspace isolation, FastAPI migration, etc.).

### Documentation Guard Tests (~120 files, ~6000 tests)

These verify that documentation artifacts (Markdown files, JSON evidence bundles)
exist and contain the expected content. They do not test application behavior.

Documentation guard tests are excluded from the functional run. They are listed
in `_doc_guard_modules.py`.

---

## Test Infrastructure

| File | Purpose |
|------|---------|
| `conftest.py` | pytest marker injection (doc_guard marker) |
| `_doc_guard_modules.py` | Canonical list of documentation guard test modules |
| `fixtures/` | Shared test fixtures |

---

## Prerequisites

Tests run without external services — they use in-memory or temp-file SQLite.

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for pytest and dev tools
```

FastAPI-dependent tests require:
```bash
pip install fastapi uvicorn pydantic starlette httpx
```
