# GL-139 Audit Hash-Chain Write Lock Baseline

## Summary

GL-139 adds a **process-local write lock** around the audit hash-chain append critical section in `backend/src/audit_log.py`.

## What This Issue Does

- Adds a `threading.RLock` named `_AUDIT_HASH_CHAIN_WRITE_LOCK` at module level.
- Wraps the `append_event` hash-chain read-compute-insert sequence with that lock.
- Prevents in-process race conditions where two concurrent threads could read the same `latest` tail hash and produce duplicate `prev_hash` values.

## What This Issue Does NOT Do

- **Does NOT** enable `ThreadingHTTPServer` — that is the scope of **GL-140**.
- **Does NOT** add distributed or multi-process locking (no Redis, no PostgreSQL advisory locks).
- **Does NOT** change the audit event schema.
- **Does NOT** change the DB schema or add migrations.
- **Does NOT** change OpenAPI, endpoints, or API behavior.
- **Does NOT** change auth semantics, admin/operator token behavior, or structured logging.
- **Does NOT** add new dependencies.
- **Does NOT** implement tenant/workspace behavior.
- **Does NOT** change frontend/website/design/marketing files.

## Compatibility

- **SQLite**: Fully preserved. The lock is process-local and works with both the default `execute()` path and explicit `conn` parameter path.
- **PostgreSQL**: Compatible. The lock is orthogonal to the transaction/connection layer. Existing transaction behavior is preserved.

## Future Hardening

If multi-process deployment is required, a later issue may introduce:
- PostgreSQL advisory locks at the transaction level, or
- A distributed lock primitive (e.g., Redis Redlock) **only after** GL-140 process-local threading is baseline-stable.

## Relationship to Other Issues

- **GL-138** (check_admin_token cleanup): Preserved; no auth code touched.
- **GL-136** (key hygiene): Preserved; no crypto/PEM code touched.
- **GL-135** (security remediation intake): GL-139 is a prerequisite hardening step identified during intake.
- **GL-140** (ThreadingHTTPServer enablement): Must NOT be implemented until GL-139 is merged.
