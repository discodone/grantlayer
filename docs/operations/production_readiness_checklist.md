# GrantLayer MVP — Production Readiness Checklist (GL-032)

This checklist documents the hardening items addressed in GL-032 and the remaining gaps before production deployment.

## Completed in GL-032

### Configuration Hardening
- [x] `GRANTLAYER_LOG_LEVEL` supports DEBUG, INFO, WARNING, ERROR; defaults to INFO.
- [x] `GRANTLAYER_HEALTH_PROBE_DB_TIMEOUT_MS` defaults to 2000 ms.
- [x] All config parsing lives in `backend/src/config.py` with safe helpers.
- [x] `startup_warnings()` emits precise warnings without leaking secret values.
- [x] `startup_ok()` remains advisory and does not break startup semantics.

### Health / Readiness Hardening
- [x] `GET /health` returns additive, safe readiness fields:
  - `dbConnected` — SELECT 1 probe
  - `dbWritable` — temp-table write probe (no persistent schema change)
  - `dbFilePresent` — true if on-disk DB file exists
  - `dbDirectoryWritable` — true if DB directory is writable
  - `dbSizeBytes` — file size for file-backed DB; null for in-memory
  - `journalMode` — PRAGMA journal_mode result
  - `dbPathKind` — `"file"` or `"memory"`
- [x] No raw `dbPath`, no absolute path leakage, no secrets in health output.
- [x] `docs/openapi.yaml` updated with new fields.

### SQLite Persistence Boundaries
- [x] Documented single-writer boundary.
- [x] Documented WAL behavior (`.db`, `.db-wal`, `.db-shm` must move together).
- [x] Documented filesystem requirements and `dbDirectoryWritable` usage.
- [x] Documented backup/restore limits (no built-in automated backup).
- [x] No PostgreSQL, no storage adapter, no migration framework introduced.

### Safe Logging / Safe Error Output
- [x] Token values never emitted in logs, error responses, or health output.
- [x] Startup warnings report presence only, not values.
- [x] No env values, salts, hashes, or private keys in public-facing output.

### Tests for Safe Defaults and No-Secret-Output
- [x] Log level defaults to INFO and rejects invalid values.
- [x] Health probe timeout defaults to 2000 ms.
- [x] `startup_warnings()` never contains secret values.
- [x] `GET /health` new readiness fields are present and safe.
- [x] `get_db_health()` returns consistent structure for file and memory DBs.

## Remaining Gaps (not in GL-032 scope)

- [ ] **Real authentication:** OAuth2, mTLS, or hardware token integration.
- [ ] **Session management:** Token rotation, expiry, and revocation.
- [x] **PostgreSQL backend:** Available as an optional deployment. Connection pooling, replication, and managed backups are the responsibility of the operator.
- [ ] **Schema migration framework:** Alembic or equivalent for versioned migrations.
- [ ] **Multi-node / HA:** Load balancing, clustering, distributed consensus.
- [ ] **Network exposure:** The server binds to `127.0.0.1` by default; any external exposure requires a reverse proxy with TLS.
- [ ] **Secrets management:** No HashiCorp Vault, AWS Secrets Manager, or equivalent integration.
- [ ] **Monitoring / alerting:** No Prometheus metrics, no structured logging, no log aggregation.
- [ ] **Compliance:** No SOC 2, ISO 27001, or GDPR attestations.
