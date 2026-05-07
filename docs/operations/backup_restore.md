# GrantLayer MVP — Backup & Restore Operations

This document describes manual backup and restore procedures for the SQLite database used by GrantLayer MVP. There is no built-in automated backup scheduling in GL-032.

## Scope

- Applies to: file-backed SQLite databases (`GRANTLAYER_DB` pointing to a file path)
- In-memory databases (`:memory:`) are ephemeral and not backed up

## Files Involved

When using WAL mode (default), three files must be treated as a single unit:

| File | Purpose |
|------|---------|
| `grantlayer.db` | Main database file |
| `grantlayer.db-wal` | Write-ahead log (uncommitted changes) |
| `grantlayer.db-shm` | Shared-memory file for WAL indexing |

**Important:** Copying only `.db` while the server is running produces an inconsistent snapshot. Always include all three files, or use a SQLite online backup method.

## Backup Procedures

### Method 1 — Offline File Copy (Recommended)

Stop the server, copy the file set, then restart.

```bash
# Stop GrantLayer
# (e.g., Ctrl+C or docker compose down)

# Copy the full file set
cp data/grantlayer.db      /backup/grantlayer-$(date +%Y%m%d).db
cp data/grantlayer.db-wal  /backup/grantlayer-$(date +%Y%m%d).db-wal
cp data/grantlayer.db-shm  /backup/grantlayer-$(date +%Y%m%d).db-shm

# Restart GrantLayer
```

### Method 2 — VACUUM INTO (Online)

Use an external SQLite client while the server is running.

```bash
sqlite3 data/grantlayer.db "VACUUM INTO '/backup/grantlayer-$(date +%Y%m%d).db'"
```

This produces a clean, standalone `.db` file without WAL files. The backup is transactionally consistent but does not preserve uncommitted WAL entries that were not yet checkpointed.

### Method 3 — SQLite Online Backup API

For automated tools, use the SQLite backup API (e.g., via Python `sqlite3` module or `sqlite3` CLI `.backup` command).

```bash
sqlite3 data/grantlayer.db ".backup /backup/grantlayer-$(date +%Y%m%d).db"
```

## Restore Procedure

1. Stop the server if it is running.
2. Replace the three files with a consistent backup set.
3. Ensure the target directory is writable.
4. Restart the server.

```bash
# Stop GrantLayer

# Restore from backup
cp /backup/grantlayer-20260507.db     data/grantlayer.db
cp /backup/grantlayer-20260507.db-wal data/grantlayer.db-wal
cp /backup/grantlayer-20260507.db-shm data/grantlayer.db-shm

# Restart GrantLayer
```

**Warning:** Do not mix files from different points in time. A `.db` file from one backup and a `.db-wal` from another will likely produce corruption or data loss.

## Filesystem Requirements

- The directory containing `grantlayer.db` must be writable for WAL and journal file creation.
- Health checks report `dbDirectoryWritable` so operators can detect permission problems early.
- Verify restore by checking `GET /health` after restart (`dbFilePresent`, `dbWritable`, `dbConnected` should all be `true`).

## What GL-032 Does NOT Provide

- No automated scheduled backups
- No cloud storage integration (S3, GCS, etc.)
- No point-in-time recovery
- No replication or multi-node failover
- No backup encryption
