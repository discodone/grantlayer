.PHONY: install test test-all test-functional test-precommit test-contract perf-test helm-lint docs docs-serve \
        lint format fix migrate docker-up docker-down audit push coverage clean help hooks

# Default: functional tests only (application logic, HTTP, DB, auth, grants).
# ~120 files / ~3 400 test methods.  Fast and meaningful for CI.
test: test-functional

# Install dev dependencies and pre-commit hooks (idempotent).
install:
	@./scripts/dev-setup.sh

# Functional tests: exclude doc-guard tests via pytest marker.
test-functional:
	@./scripts/run-functional-tests.sh

# Full suite: functional + doc-guard (documentation artifact existence checks).
# ~239 files / ~9 400 test methods.
test-all:
	@./scripts/run-full-backend-suite.sh

# Fast pre-push gate: ruff + mypy + a migration/audit-critical test subset
# (~40-60s), the same checks the .githooks/pre-push hook runs before a push to
# main. The subset is defined in scripts/pre-push-gate.sh (single source of
# truth); the full CI suite remains the real gate.
test-precommit:
	@bash scripts/pre-push-gate.sh

# Contract tests: OpenAPI schema + SDK contract + schemathesis fuzz.
test-contract:
	pytest backend/tests/contract/ -v --tb=short -m "contract"

# Performance benchmarks: relative regression detection (p95 within 2x baseline).
# Excluded from normal make test — run manually or in dedicated CI stage.
perf-test:
	pytest backend/tests/performance/ -v --tb=short -m "performance"

# Helm chart lint (requires helm CLI).
helm-lint:
	helm lint deploy/helm/grantlayer/

# Build MkDocs documentation site.
docs:
	mkdocs build

# Serve documentation locally.
docs-serve:
	mkdocs serve

# Linting: ruff + mypy (must both pass before every commit).
lint:
	ruff check backend/src/ && python3 -m mypy backend/src/

# Format source code in-place with ruff.
format:
	ruff format backend/src/
	ruff check --fix backend/src/

# Auto-fix ruff violations where possible.
fix:
	ruff check --fix backend/src/

# Run Alembic migrations against the configured database.
migrate:
	python3 -m alembic -c backend/alembic.ini upgrade head

# Start all services via Docker Compose (detached).
docker-up:
	docker compose up -d

# Stop all Docker Compose services.
docker-down:
	docker compose down

# Print last 100 audit events from the local SQLite DB.
audit:
	python3 -c "\
from backend.src.core.db import get_engine; \
from sqlalchemy import text; \
e = get_engine(); \
conn = e.connect(); \
rows = conn.execute(text('SELECT timestamp, subject_id, action, resource, approved FROM audit_events ORDER BY seq DESC LIMIT 100')).fetchall(); \
[print(r) for r in rows]"

# Push to both remotes (origin = Forgejo, github = GitHub).
push:
	git push origin main && git push github main

# Enable the versioned git hooks (pre-push gate). Run once per clone —
# core.hooksPath is local config and is NOT carried by git clone.
hooks:
	git config core.hooksPath .githooks
	@echo "core.hooksPath set to .githooks — the pre-push gate is now active."

# Coverage report: functional tests with per-module missing-line output.
coverage:
	pytest backend/tests/ -q --tb=short -m "not doc_guard" --cov=backend/src --cov-report=term-missing

# Remove Claude Code temp files on the ai-agent VM to free disk space.
clean:
	rm -rf /home/adminuser/tmp/claude-1000/ && find /home/adminuser/tmp -name "tmp*.db*" -delete

# Show all available make targets.
help:
	@echo ""
	@echo "GrantLayer — available make targets"
	@echo ""
	@echo "  make install          Install dev dependencies + pre-commit hooks"
	@echo "  make test             Run functional test suite (~3 400 tests, no doc_guard)"
	@echo "  make test-all         Run full suite including doc-guard (~9 400 tests)"
	@echo "  make test-contract    Run OpenAPI contract + schemathesis fuzz tests"
	@echo "  make lint             ruff check + mypy (baseline: 0 errors each)"
	@echo "  make format           ruff format + ruff fix in-place"
	@echo "  make fix              Auto-fix ruff violations"
	@echo "  make migrate          Run Alembic DB migrations"
	@echo "  make docker-up        docker compose up -d"
	@echo "  make docker-down      docker compose down"
	@echo "  make audit            Print last 100 audit events"
	@echo "  make push             git push origin main && git push github main"
	@echo "  make coverage         Functional tests with --cov-report=term-missing"
	@echo "  make perf-test        Performance benchmarks (p95 regression detection)"
	@echo "  make helm-lint        Lint the Helm chart in deploy/helm/grantlayer/"
	@echo "  make docs             Build MkDocs documentation site"
	@echo "  make docs-serve       Serve documentation locally"
	@echo "  make clean            Remove Claude Code temp files on ai-agent VM"
	@echo "  make help             Show this message"
	@echo ""
