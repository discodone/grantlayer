#!/usr/bin/env bash
#
# GrantLayer pre-push gate — the checks the .githooks/pre-push hook runs before
# a push that updates main. A FAST sieve (lint + a migration/audit-critical test
# subset, ~40-60s), not the full suite; the full CI suite remains the source of
# truth and catches whatever the subset misses.
#
# Single source of truth for the gate. Invoked by:
#   - .githooks/pre-push   (automatically, on push to main)
#   - make test-precommit  (manually, any time)
#   - bash scripts/pre-push-gate.sh
#
# Deliberately make-free: `make` is not guaranteed to be installed on the push
# host, so this script calls ruff / mypy / pytest directly.
#
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
export TMPDIR="${TMPDIR:-/home/adminuser/tmp}"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/backend"

# Migration + audit-critical subset. test_gl238_glxxx_cleanup.py MUST stay in
# this list — it is the exact regression this gate exists to prevent.
SUBSET=(
    backend/tests/test_gl238_glxxx_cleanup.py
    backend/tests/test_migration_parity.py
    backend/tests/test_migration_runner_alembic_guard.py
    backend/tests/test_migration_runner_postgres_guard.py
    backend/tests/test_gl348_migration_chain_fresh_db.py
    backend/tests/test_audit_write_atomicity.py
    backend/tests/test_gl103_audit_hash_chain.py
    backend/tests/test_gl102_audit_log_db_immutability.py
    backend/tests/test_gl104_audit_chain_verification_helper.py
    backend/tests/test_gl105_audit_chain_verification_report.py
    backend/tests/test_audit_workspace_not_null.py
)

echo "pre-push gate [1/3]: ruff…"
ruff check backend/src/

echo "pre-push gate [2/3]: mypy…"
python3 -m mypy backend/src/

echo "pre-push gate [3/3]: migration/audit test subset…"
python3 -m pytest "${SUBSET[@]}" -q -p no:cacheprovider \
    -m "not doc_guard and not scope_guard and not performance"

echo "pre-push gate: all checks passed."
