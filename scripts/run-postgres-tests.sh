#!/usr/bin/env bash
# GrantLayer MVP — GL-116 PostgreSQL Integration Test Runner
#
# Usage (from repo root):
#   export GRANTLAYER_DATABASE_URL=postgres://user:pass@host:port/db
#   ./scripts/run-postgres-tests.sh
#
# Or with docker-compose.postgres.yml:
#   docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d
#   export GRANTLAYER_DATABASE_URL=postgres://grantlayer:grantlayer_password_change_me@localhost:5432/grantlayer
#   ./scripts/run-postgres-tests.sh
#   docker compose -f docker-compose.yml -f docker-compose.postgres.yml down
#
# Required environment variables:
#   GRANTLAYER_DATABASE_URL  or  GRANTLAYER_TEST_DATABASE_URL
#
# Skips cleanly if:
#   - PostgreSQL URL is not configured
#   - psycopg2 is not installed
#   - PostgreSQL is not reachable
#
# Does NOT require secrets in the repository.
# Does NOT start external production services.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Determine whether this script is applicable ──

PG_URL="${GRANTLAYER_DATABASE_URL:-${GRANTLAYER_TEST_DATABASE_URL:-}}"

if [[ -z "${PG_URL}" ]]; then
    echo "SKIP: Neither GRANTLAYER_DATABASE_URL nor GRANTLAYER_TEST_DATABASE_URL is set"
    echo "Set one of them to a postgres:// URL to run PostgreSQL integration tests."
    exit 0
fi

if ! [[ "${PG_URL}" =~ ^postgres(ql)?:// ]]; then
    echo "SKIP: Database URL is not a PostgreSQL URL"
    exit 0
fi

if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo "SKIP: psycopg2 is not installed"
    echo "Install it with: pip install psycopg2-binary"
    exit 0
fi

echo "=== GL-116 PostgreSQL Integration Test Runner ==="
echo "DSN hostname: $(python3 -c "from urllib.parse import urlparse; print(urlparse('${PG_URL}').hostname)")"

# ── Quick connectivity probe ──
if ! python3 -c "
import psycopg2, sys
try:
    conn = psycopg2.connect('${PG_URL}')
    conn.cursor().execute('SELECT 1')
    conn.close()
except Exception as e:
    print(f'PostgreSQL not reachable: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
    echo "SKIP: PostgreSQL server not reachable"
    exit 0
fi

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}/backend"

echo "--- Running GL-108/GL-116 PostgreSQL integration tests ---"
python3 -m unittest backend.tests.test_gl108_postgres_audit_immutability.TestGl116PostgresAuditImmutabilityIntegration -v

echo ""
echo "=== GL-116 PostgreSQL Integration Tests PASSED ==="
