.PHONY: test test-all test-functional lint fix push coverage clean help

# Default: functional tests only (application logic, HTTP, DB, auth, grants).
# ~120 files / ~3 400 test methods.  Fast and meaningful for CI.
test: test-functional

# Functional tests: exclude doc-guard tests via pytest marker.
test-functional:
	@./scripts/run-functional-tests.sh

# Full suite: functional + doc-guard (documentation artifact existence checks).
# ~239 files / ~9 400 test methods.
test-all:
	@./scripts/run-full-backend-suite.sh

# Linting: ruff + mypy (must both pass before every commit).
lint:
	ruff check backend/src/ && python3 -m mypy backend/src/

# Auto-fix ruff violations where possible.
fix:
	ruff check --fix backend/src/

# Push to both remotes (origin = Forgejo, github = GitHub).
push:
	git push origin main && git push github main

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
	@echo "  make test       Run functional test suite (~3 400 tests, no doc_guard)"
	@echo "  make test-all   Run full suite including doc-guard (~9 400 tests)"
	@echo "  make lint       ruff check + mypy (baseline: 0 errors each)"
	@echo "  make fix        Auto-fix ruff violations"
	@echo "  make push       git push origin main && git push github main"
	@echo "  make coverage   Functional tests with --cov-report=term-missing"
	@echo "  make clean      Remove Claude Code temp files on ai-agent VM"
	@echo "  make help       Show this message"
	@echo ""
