# GrantLayer — Claude Code Instructions

## Git Rules (MANDATORY)
- After every merge to main: git push origin main AND git push github main
- Never push to github without explicit approval from Anton
- Branch naming: gl-{number}-{short-description}
- Commit message format: feat|fix|docs|refactor(gl-{number}): description

## Baseline (must pass after every commit)
- pytest backend/tests/ -q --tb=short -m "not doc_guard" --timeout 3m → ≥3325 passed / 0 failures
- python3 -m mypy backend/src/ → 0 errors
- ruff check backend/src/ → 0 errors

## CI Ignored Tests
- test_gl112_audit_log_duplication_cleanup.py
- test_gl139_audit_hash_chain_write_lock.py
- test_gl141_operator_model_default.py
- test_gl214_production_iam_operator_control_completion.py
- test_gl203b_openapi_api_contract_cleanup.py
- test_gl230_docker_jwt_quickstart.py

## Architecture
- Repository Pattern: core/repositories.py + repositories_sqlalchemy.py
- Service Layer: grant_service.py, grant_request_service.py, operator_service.py
- ORM Models: core/orm.py
- No raw SQL — SQLAlchemy ORM only
- No custom SQL placeholder parsing

## Database
- SQLite for local/test, PostgreSQL 16 for production
- Test isolation: always use uuid4()-generated IDs per test

## Disk Management
- If disk full: rm -rf /home/adminuser/tmp/claude-1000/ && find /home/adminuser/tmp -name "tmp*.db*" -delete

## Current Roadmap
- GL-302: Test coverage 95%+
- GL-303: Redis hard requirement
- GL-304: BIGSERIAL audit tiebreak
- GL-305: Async FastAPI
- Target: 10/10 external review score
