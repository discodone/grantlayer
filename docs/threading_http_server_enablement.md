# GL-140 ThreadingHTTPServer Enablement

## Summary

GL-140 replaces the single-threaded `HTTPServer` with `ThreadingHTTPServer` in `backend/src/server.py`. This enables the server to handle concurrent HTTP requests in separate threads, completing the threading foundation that GL-139 prepared with its process-local audit hash-chain write lock.

## What This Issue Does

- Changes the import on line 8 of `server.py` to include `ThreadingHTTPServer` from `http.server`.
- Changes the `run()` function to instantiate `ThreadingHTTPServer` instead of `HTTPServer`.
- Each incoming request is now handled in its own thread (`ThreadingMixIn` behaviour from the Python stdlib).

## What This Issue Does NOT Do

- **Does NOT** change any endpoint or API behaviour.
- **Does NOT** change the OpenAPI specification.
- **Does NOT** add database migrations or schema changes.
- **Does NOT** change auth semantics, admin/operator token behaviour, or structured logging.
- **Does NOT** add new dependencies.
- **Does NOT** implement tenant/workspace behaviour.
- **Does NOT** change frontend, website, or design files.
- **Does NOT** remove or weaken the GL-139 audit hash-chain write lock (`_AUDIT_HASH_CHAIN_WRITE_LOCK`).

## Prerequisite

GL-139 added `_AUDIT_HASH_CHAIN_WRITE_LOCK` (a `threading.RLock`) around the audit hash-chain append critical section. Without that lock, enabling `ThreadingHTTPServer` would allow concurrent requests to produce duplicate `prev_hash` values in the audit chain. GL-140 is only safe because GL-139 is already merged.

## Compatibility

- **SQLite**: Fully preserved. The `ThreadingMixIn` model spawns one thread per request; the audit write lock ensures the hash-chain remains consistent across concurrent writes.
- **PostgreSQL**: Compatible. The threading model is orthogonal to the DB connection layer; existing transaction behaviour is preserved.

## Scope

Changed files:

- `backend/src/server.py` — import + instantiation
- `backend/tests/test_gl140_threading_http_server_enablement.py` — targeted tests
- `backend/tests/test_gl139_audit_hash_chain_write_lock.py` — branch-guard fix for the "not enabled" assertion
- `docs/threading_http_server_enablement.md` — this file
- `docs/examples/gl140/threading_http_server_enablement.json` — machine-readable scope record
