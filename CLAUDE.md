# GrantLayer — Claude Code Instructions

## Git Rules (MANDATORY)
- After every completed issue: automatically merge to main and push to BOTH remotes (origin + github)
- Auto-merge conditions: tests ≥ baseline / 0 failures, mypy 0 errors, ruff 0 errors
- If any condition fails: stop, report to Anton, wait for instructions
- Branch naming: gl-{number}-{short-description}
- Commit message format: feat|fix|docs|refactor(gl-{number}): description
- After merge: close the corresponding GitHub issue with: gh issue close {number} --repo discodone/grantlayer

## Baseline (must pass after every commit)
- pytest backend/tests/ -q --tb=short -m "not doc_guard" --timeout 3m → ≥3621 passed / 0 failures
- python3 -m mypy backend/src/ → 0 errors
- ruff check backend/src/ → 0 errors

## Merge gate fast path (tree-hash rule, added 2026-07-25)
Rationale: the gate exists to ensure every tree reaching main was validated by
the full suite — not to run it twice on the same tree.

When merging a branch whose branch CI is fully green, compare tree hashes:
`git rev-parse <merge-commit>^{tree}` vs `git rev-parse <branch-head>^{tree}`.
- **IDENTICAL** (main did not move since branching — the common case): the
  local pre-push gate is `ruff check backend/src/` + `python3 -m mypy
  backend/src/` + the audit/migration subset below (~40s, measured 141
  passed / 0 failures on 2026-07-25). The full suite is NOT re-run locally:
  branch CI already validated this exact tree, and main CI validates it again
  remotely after push.
- **DIFFERENT** (main moved; the merge created a tree no CI has seen): run
  the full local suite before push, as before.

Audit/migration subset (explicit files — do NOT substitute a `-k` expression;
broad `-k` slices were measured both slower (3m21) and isolation-fragile
(4 fixture-order false failures)):
```
python3 -m pytest -q -m "not doc_guard" \
  backend/tests/test_fold_golden_vectors.py \
  backend/tests/test_anchor_public_fold_parity.py \
  backend/tests/test_verifier_fold_parity.py \
  backend/tests/test_gl103_audit_hash_chain.py \
  backend/tests/test_gl104_audit_chain_verification_helper.py \
  backend/tests/test_gl105_audit_chain_verification_report.py \
  backend/tests/test_migration_parity.py \
  backend/tests/test_migration_runner_alembic_guard.py \
  backend/tests/test_migration_runner_postgres_guard.py \
  backend/tests/test_gl348_migration_chain_fresh_db.py \
  backend/tests/test_gl340_repo_hygiene.py
```

Everything else is unchanged: the pre-push hook is never bypassed, the
three-SHA match (local/origin/github) is still required, main CI must FINISH
green after every merge push, and site/ changes still get live verification
against grantlayer.de.

## Coverage (actual, re-measured 2026-06-19)
- **91% repo-wide** (9,348 statements / 795 missed), measured via `pytest backend/tests/ --cov=backend.src`.
- The full doc_guard-inclusive suite reports the same 91% — doc_guard tests add no material coverage.
- The earlier "95.2%" figure is STALE: it was measured at GL-302 when the codebase was ~6,619 statements. The codebase has since grown ~40% to 9,348 statements and real coverage is now 91%. Do NOT repeat the 95.2% claim in reviews, docs, or the website.
- Raising coverage back to 95% is honest follow-up work tracked as GL-348 — do it with real tests, never by padding trivial tests to hit a number.

## CI Ignored Tests (known issues, do not re-ignore without fixing)
- test_gl112_audit_log_duplication_cleanup.py
- test_gl139_audit_hash_chain_write_lock.py
- test_gl141_operator_model_default.py
- test_gl214_production_iam_operator_control_completion.py
- test_gl203b_openapi_api_contract_cleanup.py
- test_gl230_docker_jwt_quickstart.py (missing pyyaml in PostgreSQL CI job)

## Known Limitations (documented, deliberately not fixed yet)
- **Append-side chain fork under multi-writer (latent, cannot trigger today).**
  `_get_latest_row_hash` (backend/src/audit/audit_log.py) selects the previous
  chain tip with `ORDER BY timestamp DESC, seq DESC LIMIT 1`. Timestamps are
  assigned before the write lock and seq under it, so under MULTI-WRITER
  parallelism a compounding 3+ event timestamp/seq inversion could make two
  appends pick different tips and fork the stored row_hash chain. This is
  SINGLE-WRITER-SAFE: the live deployment is one API process and appends run
  under the audit write lock (pg_advisory_xact_lock / RLock), so the condition
  cannot occur today. Address IF/WHEN multi-writer becomes real — fix
  direction: select the append tip by the same seq-ASC total order the verify
  side already uses (`_fetch_all_audit_events_ordered`:
  `ORDER BY (seq IS NULL), seq ASC, id ASC`), i.e. tip = max seq, not max
  timestamp. Do not change the ordering silently: the stored prev-tip choice
  feeds row_hash bytes, so any change must be proven append-equivalent under
  the single-writer regime before it lands.

## Architecture
- Repository Pattern: backend/src/core/repositories.py + repositories_sqlalchemy.py
- Service Layer: grant_service.py, grant_request_service.py, operator_service.py
- ORM Models: backend/src/core/orm.py (Grant, GrantRequest, GrantExecution, Operator)
- No raw SQL anywhere — use SQLAlchemy ORM or session.execute(text().bindparams())
- No custom SQL placeholder parsing

## Database
- SQLite for local/test, PostgreSQL 16 for production
- Always test PostgreSQL compatibility (no rowid, no datetime(), no SQLite-specific syntax)
- Test isolation: always use uuid4()-generated IDs per test, never hardcoded IDs

## Disk Management (ai-agent VM)
- If disk full: rm -rf /home/adminuser/tmp/claude-1000/ && find /home/adminuser/tmp -name "tmp*.db*" -delete
- tmpDir is configured in ~/.config/claude/settings.json

## Current Roadmap
- GL-302: Test coverage push (95.2% at the time, 6,619 stmts; now 91% repo-wide after ~40% codebase growth — see Coverage section)
- GL-348: Raise coverage back to 95% (honest follow-up, real tests only)
- GL-303: Redis hard requirement + rate limiting on all endpoints
- GL-304: BIGSERIAL audit tiebreak + cursor-based pagination
- GL-305: Async FastAPI
- Target: 10/10 external review score
