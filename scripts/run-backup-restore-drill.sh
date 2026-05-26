#!/usr/bin/env bash
# GrantLayer MVP — GL-127 Backup / Restore Minimum Drill Runner
#
# Usage (from repo root):
#   ./scripts/run-backup-restore-drill.sh
#
# Minimum operational backup/restore drill for pilot/production-readiness.
# This is a checklist and validation package, not a managed backup system.
#
# Does NOT require external services.
# Does NOT perform real backup or restore operations.
# Does NOT modify files.
# Does NOT hide failures.
# Does NOT print secret values.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo "=== GrantLayer Backup / Restore Minimum Drill ==="
echo "Repository root: ${REPO_ROOT}"
echo "Command: python3 -m unittest backend.tests.test_gl127_backup_restore_minimum_drill -v"
echo ""

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}/backend"

EXIT_CODE=0
python3 -m unittest backend.tests.test_gl127_backup_restore_minimum_drill -v || EXIT_CODE=$?

echo ""
echo "=== Backup / Restore Minimum Drill Finished ==="
echo "Exit code: ${EXIT_CODE}"

exit "${EXIT_CODE}"
