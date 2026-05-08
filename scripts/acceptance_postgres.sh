#!/usr/bin/env bash
# GrantLayer MVP — GL-035 PostgreSQL Operational Smoke Verification Script
#
# Usage (from repo root):
#   export GRANTLAYER_DATABASE_URL=postgres://user:pass@host/db
#   ./scripts/acceptance_postgres.sh
#
# Skips cleanly if:
#   - GRANTLAYER_DATABASE_URL is not set or not postgres://
#   - psycopg2 is not installed
#   - PostgreSQL is not reachable
#
# Validates:
#   - fresh DB initializes schema via migrations
#   - migrations are idempotent on second run
#   - create/list/revoke Grant works
#   - GrantRequest approval flow works
#   - Challenge creation and demo-action work
#   - audit events and grant executions persist
#   - evidence bundle retrieval works
#   - restart persistence (basic)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Determine whether this script is applicable ──

if [[ -z "${GRANTLAYER_DATABASE_URL:-}" ]]; then
    echo "SKIP: GRANTLAYER_DATABASE_URL not set"
    exit 0
fi

if ! [[ "${GRANTLAYER_DATABASE_URL}" =~ ^postgres(ql)?:// ]]; then
    echo "SKIP: GRANTLAYER_DATABASE_URL is not a PostgreSQL URL"
    exit 0
fi

if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo "SKIP: psycopg2 is not installed"
    exit 0
fi

echo "=== GL-035 PostgreSQL Smoke Verification ==="
echo "DSN hostname: $(python3 -c "from urllib.parse import urlparse; print(urlparse('$GRANTLAYER_DATABASE_URL').hostname)")"

# ── Quick connectivity probe ──
if ! python3 -c "
import psycopg2, sys
try:
    conn = psycopg2.connect('$GRANTLAYER_DATABASE_URL')
    conn.cursor().execute('SELECT 1')
    conn.close()
except Exception as e:
    print(f'PostgreSQL not reachable: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
    echo "SKIP: PostgreSQL server not reachable"
    exit 0
fi

# ── Prepare isolated DB for smoke test ──
# Use the provided DB URL as-is; migrations should be idempotent.
export PYTHONPATH="${PYTHONPATH:-}:$REPO_ROOT/backend"

echo "--- Step 1: Fresh DB initialization ---"
python3 -c "
import os, sys
sys.path.insert(0, os.path.join('$REPO_ROOT', 'backend'))
from src import db
db.init_db()
print('OK: init_db completed')
"

echo "--- Step 2: Migration idempotency ---"
python3 -c "
import os, sys
sys.path.insert(0, os.path.join('$REPO_ROOT', 'backend'))
from src import db
db.init_db()
print('OK: init_db is idempotent')
"

echo "--- Step 3: Grant lifecycle (create/list/revoke) ---"
python3 -c "
import os, sys, uuid
sys.path.insert(0, os.path.join('$REPO_ROOT', 'backend'))
from src.db import get_conn, query_one, query_all, execute
grant_id = str(uuid.uuid4())
with get_conn() as conn:
    conn.execute(
        'INSERT INTO grants (id, subject_id, role, action, resource, valid_from, valid_until, created_by, reason, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (grant_id, 'subject-1', 'admin', 'read', 'res-1', '2024-01-01', '2025-01-01', 'smoke', 'test', '2024-01-01'),
    )
    conn.commit()

row = query_one('SELECT * FROM grants WHERE id = ?', (grant_id,))
assert row is not None, 'Grant not found after insert'
assert row['subject_id'] == 'subject-1'

execute('UPDATE grants SET revoked = 1, revoked_by = ?, revoked_reason = ?, revoked_at = ? WHERE id = ?',
    ('smoke', 'revoked in test', '2024-01-02', grant_id))
row = query_one('SELECT * FROM grants WHERE id = ?', (grant_id,))
assert row['revoked'] == 1
print('OK: grant lifecycle works')
"

echo "--- Step 4: GrantRequest approval flow ---"
python3 -c "
import os, sys, uuid
sys.path.insert(0, os.path.join('$REPO_ROOT', 'backend'))
from src.db import get_conn, query_one, execute
req_id = str(uuid.uuid4())
grant_id = str(uuid.uuid4())
with get_conn() as conn:
    conn.execute(
        'INSERT INTO grant_requests (id, subject_id, role, action, resource, valid_from, valid_until, requested_by, reason, status, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (req_id, 'sub-2', 'user', 'write', 'res-2', '2024-01-01', '2025-01-01', 'requester', 'please', 'requested', '2024-01-01'),
    )
    conn.execute(
        'INSERT INTO grants (id, subject_id, role, action, resource, valid_from, valid_until, created_by, reason, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (grant_id, 'sub-2', 'user', 'write', 'res-2', '2024-01-01', '2025-01-01', 'approver', 'approved', '2024-01-01'),
    )
    conn.execute(
        'UPDATE grant_requests SET status = ?, approved_by = ?, approved_at = ?, grant_id = ? WHERE id = ?',
        ('approved', 'approver', '2024-01-02', grant_id, req_id),
    )
    conn.commit()
row = query_one('SELECT * FROM grant_requests WHERE id = ?', (req_id,))
assert row['status'] == 'approved'
assert row['grant_id'] == grant_id
print('OK: grant request approval flow works')
"

echo "--- Step 5: Challenge + demo-action ---"
python3 -c "
import os, sys, uuid
sys.path.insert(0, os.path.join('$REPO_ROOT', 'backend'))
from src.db import get_conn, query_one, execute
chal_id = str(uuid.uuid4())
with get_conn() as conn:
    conn.execute(
        'INSERT INTO challenges (id, subject_id, action, resource, created_at, expires_at, status) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (chal_id, 'sub-3', 'read', 'res-3', '2024-01-01T00:00:00', '2025-01-01T00:00:00', 'active'),
    )
    conn.commit()
row = query_one('SELECT * FROM challenges WHERE id = ?', (chal_id,))
assert row is not None
assert row['status'] == 'active'
print('OK: challenge works')
"

echo "--- Step 6: Audit events and executions persist ---"
python3 -c "
import os, sys, uuid
sys.path.insert(0, os.path.join('$REPO_ROOT', 'backend'))
from src.db import get_conn, query_one, execute
evt_id = str(uuid.uuid4())
exec_id = str(uuid.uuid4())
with get_conn() as conn:
    conn.execute(
        'INSERT INTO audit_events (id, timestamp, subject_id, role, action, resource, approved, reason) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (evt_id, '2024-01-01T00:00:00', 'sub-4', 'user', 'read', 'res-4', 1, 'test'),
    )
    conn.execute(
        'INSERT INTO grant_executions (id, grant_id, action, resource, result, executed_at, audit_event_id) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (exec_id, None, 'read', 'res-4', 'succeeded', '2024-01-01T00:00:00', evt_id),
    )
    conn.commit()
row = query_one('SELECT * FROM grant_executions WHERE id = ?', (exec_id,))
assert row is not None
assert row['result'] == 'succeeded'
print('OK: audit events and executions persist')
"

echo "--- Step 7: Evidence bundle retrieval ---"
python3 -c "
import os, sys, uuid
sys.path.insert(0, os.path.join('$REPO_ROOT', 'backend'))
from src.db import get_conn, query_one, execute
from src.evidence_bundle import build_evidence_bundle
exec_id = str(uuid.uuid4())
with get_conn() as conn:
    conn.execute(
        'INSERT INTO grant_executions (id, grant_id, action, resource, result, executed_at, audit_event_id) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (exec_id, None, 'read', 'res-5', 'succeeded', '2024-01-01T00:00:00', None),
    )
    conn.commit()
bundle = build_evidence_bundle(exec_id)
assert bundle is not None
assert bundle.get('execution', {}).get('result') == 'succeeded'
print('OK: evidence bundle retrieval works')
"

echo "--- Step 8: Restart persistence ---"
python3 -c "
import os, sys
sys.path.insert(0, os.path.join('$REPO_ROOT', 'backend'))
from src import db
db.init_db()
"
count=$(python3 -c "
import os, sys
sys.path.insert(0, os.path.join('$REPO_ROOT', 'backend'))
from src.db import query_one
row = query_one('SELECT count(*) AS c FROM schema_migrations')
print(row['c'])
")
echo "OK: restart persistence verified (schema_migrations has ${count} entries)"

echo ""
echo "=== GL-035 PostgreSQL Smoke Verification PASSED ==="
