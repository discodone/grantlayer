.PHONY: test test-all test-functional

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
