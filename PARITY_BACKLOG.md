# PostgreSQL Full-Suite Parity Backlog (GL-351)

**Status:** open · **Opened:** 2026-06-23 · **Tracking:** no external tracker (repo-internal)

## Known gaps (tracked, not urgent)

- **`doc_guard` test set is not run by any CI job** — every CI test step uses
  `-m "not doc_guard"`, so doc-guard tests (repo/artifact validation, e.g.
  `test_gl310_dev_tooling`) run only in local `make test-all`. They are
  CI-ungated. Should be wired into a fast dedicated CI job or the pre-push hook.
- **`ruff`/`mypy` are undeclared dev dependencies** — pulled in only via an
  ad-hoc `pip install ruff mypy` in the SQLite Unit Tests job, declared in no
  requirements file (same class as the `PyYAML` gap fixed 2026-07-15). Should be
  moved into `backend/requirements-dev.txt` so every job/clone gets them
  deterministically.

## Mainnet anchoring — status 2026-07-16 (guards MERGED, live-preprod-proven, path still disabled)

**Merged to `main`** (merge commit `70bc070`, `--no-ff`; original `7eae777`
preserved as a parent so the audit trail binding the live preprod tx to the
exact code stays intact): fail-closed spend guards for mainnet Cardano
anchoring — three gates plus signing-key redaction, 22/22 proven
offline/network-free AND **proven live against the real preprod chain** (see
below). The **mainnet path stays disabled** — merging changed nothing about
that.

- Gate A — wallet-balance ceiling (pre-build, fail-closed: no balance
  confirmation ⇒ no submit).
- Gate B — expected-address pin (worker/app refuse to boot on mismatch; re-checked
  pre-submit).
- Gate C — per-tx fee ceiling (post-build, before the single irreversible
  `submit_tx`).
- Redaction — sanitized re-raise (`AnchorSubmitError(type(exc).__name__)`) + a
  `CardanoConfig.__repr__` that masks `signing_key` / `blockfrost_project_id`.

**Cap parameters chosen:**

- Wallet float: **25 ADA**.
- Wallet ceiling: **50 ADA** — `GRANTLAYER_CARDANO_MAX_WALLET_LOVELACE=50000000`.
- Per-tx fee ceiling: **1.0 ADA** — `GRANTLAYER_CARDANO_MAX_FEE_LOVELACE=1000000`.
- Expected-address pin (`GRANTLAYER_CARDANO_EXPECTED_ADDRESS`) is **required on
  mainnet**; app + worker refuse to boot on `network=mainnet` without all three
  caps and a key that derives to the pinned address.

**DONE 2026-07-16 — live on-chain preprod proof (the gate for this merge):**

- **Gate A refusal live:** wallet 9,999.83 tADA vs a 50 ADA cap →
  `aborted_overfunded_or_wrong_wallet`; zero spend, UTxO set identical, no DB
  row, `submit_tx` never reached — against real Blockfrost.
- **Happy-path anchor live:** tx
  `380692ef46093f9be361c6a83e94fb18c0e2efa01e23834c4bb9b17c0af1ea9f` (preprod
  block 4,942,650), fee **170,737 lovelace = 0.170737 tADA** — genuinely
  evaluated by Gate C under the 1.0 ADA ceiling (on-chain fee == wallet balance
  delta). Payload `{h: fbd71925…cbd295, s: 5, t: 2026-07-16T10:54:00.893628Z}`
  over a real 5-event audit chain; `submitted` row witnessed mid-run →
  `confirmed` + tx id; exactly one tx on the wallet.
- **Independent keyless verification:** `verify-anchor.py --network preprod` →
  **VERIFIED, exit 0** via Koios (no credentials, no GrantLayer code/DB); both
  negative controls discriminate — a tampered line fails with the precise line
  named (`line 3: _chain_hash mismatch`), a truncated tail fails the count
  check. All three gates behaved live exactly as against the offline stubs.

**REMAINING — manual, operator-only (unchanged; not Claude Code):**

1. **Mainnet key ceremony** — a separate key, separate wallet, separate secret
   file (**NEVER run `gen_preprod_wallet.py` against mainnet**). Fund to the 25 ADA
   cap and set `EXPECTED_ADDRESS` to the derived mainnet address.
2. **First mainnet anchor** — run manually (not on the daily cron), behind the
   human checkpoint, verify on-chain, and only then enable the cron.

**Mainnet remains DISABLED on `main`.** Merging the guards changes nothing about
mainnet being off: `network` defaults to `preprod`, and app + worker refuse to
boot on `network=mainnet` without all three caps and a key deriving to the
pinned address.

## Landed 2026-07-15 — Tier-1 hardening

- **CI made honest** — the `postgres-ci` integration job was repointed from
  `init_db()` to `alembic upgrade head` (`dd125f3`). `init_db()` refuses
  PostgreSQL after the runner's fail-closed guard, so it died in setup and kept
  the whole workflow permanently red; provisioning via Alembic first restores it.
  `main` is green again.
- **Stale VM instance decommissioned** — the old SQLite-backed instance (frozen
  at migration 0011, unused) was torn down with `docker compose down -v`. Only
  the 240 KB `grantlayer-data` volume was destroyed; key material lives host-side
  in the repo dir and was untouched. The instance is rebuildable from `main` via
  the Alembic path.
- **Fast pre-push gate for main added and armed** (`7ab6113`) — `.githooks/pre-push`
  + `scripts/pre-push-gate.sh` run ruff + mypy + an ~43s migration/audit test
  subset (including the `test_gl238` cleanup sentinel) before any push that
  updates `main`. Proven to block a failing push (exit 1) and allow a clean one
  (exit 0). Feature branches are left to CI. Bypass is explicit and logged
  (`GL_SKIP_PREPUSH=1` or `--no-verify`); activated per-clone via
  `core.hooksPath` (`make hooks`). The full CI suite remains the source of truth.

## Landed 2026-07-14 — migration-system drift closed

Three fixes reconciled the two migration systems and made the deployment
contract fail-loud instead of silently divergent:

- **Audit-write atomicity** (`af831d7`) — mutation and its `append_event` now
  share the request session, so a failed audit write rolls back the mutation
  instead of leaving a Cardano-anchored gap.
- **Runner fail-loud guard** (`fd93265`) — the runner's legacy-baseline shortcut
  now raises `RuntimeError` instead of marking every migration applied without
  executing it when it finds an Alembic-provisioned database. See
  DEPLOYMENT.md §11 for the operator remedy.
- **Migration parity + runner freeze** (`32f0e5e`) — one Alembic catch-up
  revision (`d4e5f6a7b8c9`) brings Alembic to full parity with the frozen
  runner (tables, indexes, 19 server defaults, `audit_events.seq`, immutability
  triggers); the file-based runner is frozen dev/test-only; `init_db()` defers
  to Alembic when it owns the schema; PostgreSQL CI now provisions with
  `alembic upgrade head`; and `backend/tests/test_migration_parity.py` fails CI
  if a runner migration ever adds an object Alembic lacks.

The two PostgreSQL runtime parity bugs enumerated below (sync-engine URL
`ArgumentError`; `workspace_id` `NOT NULL` enforced only on PostgreSQL) are
separate and remain open.

## Verified closed 2026-07-14 — audit_events seq + immutability triggers on Alembic PG

**Item:** a pure Alembic-provisioned PostgreSQL database was reported to be
missing `audit_events.seq` and the `no_update`/`no_delete` immutability triggers,
leaving the production audit log without DB-level append-only protection and
breaking `verify_audit_hash_chain` / cursor pagination.

**Status: RESOLVED by revision `d4e5f6a7b8c9` (commit `32f0e5e`).** Confirmed
empirically on throwaway PostgreSQL 16 containers: at the pre-catch-up revision
`c3d4e5f6a7b8` the drift is real (`seq` absent, zero triggers); at head
(`d4e5f6a7b8c9`, `alembic upgrade head`) `audit_events` has `seq` (+ backing
sequence + index) and both immutability triggers, and functionally UPDATE and
DELETE are rejected by the DB, `verify_audit_hash_chain` validates, and cursor
pagination over `seq` pages correctly. A permanent PG-only regression test
(`backend/tests/test_migration_parity.py::TestMigrationParityPostgresFunctional`,
gated on `GRANTLAYER_PARITY_PG_DSN`) pins these five guarantees and fails loudly
if a future revision regresses any of them. No new migration was required; a
production DB provisioned before this revision only needs `alembic upgrade head`.

Known/intentional: on a fresh DB the first inserted row gets `seq = 2` (the
catch-up runs `setval(sequence, MAX(seq) + 1)` on an empty table). This is not
fixed — the seq contract is strict monotonicity + uniqueness, which holds; the
absolute starting value is irrelevant to ordering, verification, and pagination.

## Summary

The PostgreSQL 16 Full Suite CI job had never run to completion before. Clearing
the prerequisite blockers (missing runtime deps `arq`/`audit`/`asyncpg`,
optional-dependency test conditionals, and finally per-test PostgreSQL isolation
via the autouse TRUNCATE fixture) let the suite run far enough to surface a
backlog of genuine PG/SQLite parity bugs that SQLite alone never exposed.

The SQLite Unit Tests job (4,697 tests, green) remains the merge gate. The PG
Full Suite was made non-blocking (`continue-on-error: true`) in commit `6aa52ad`
so the honest v2.1.0 release can ship decoupled from this backlog, while the job
keeps running and reporting.

## Parity bugs identified so far

1. **URL `ArgumentError` on the sync engine** in the evidence-export path — PG-only failure.
2. **Raw `INSERT INTO grants` omitting `workspace_id` -> `NotNullViolation`** on PG.
   Migration 0012 applies `NOT NULL` only on PostgreSQL; SQLite silently skips
   `ALTER COLUMN ... SET NOT NULL`, so the same insert succeeds on SQLite and the
   divergence is invisible there.
3. **Likely more** — the suite runs with `-x` today, so it stops at the first
   failure. The full extent is unknown until it runs to completion without `-x`.

## Plan (Option A — triage)

1. Run the full suite against the local PG container to completion, WITHOUT `-x`.
2. Enumerate every PG-only failure.
3. Categorize each as either:
   - (a) a real schema/parity/code bug that affects production, or
   - (b) a test-only SQLite-ism (test relies on SQLite-specific behavior).
4. Fix the real bugs in a batch; adjust the test-only cases.
5. Once the divergences are triaged and fixed, restore the PG Full Suite to a
   blocking merge gate.

## Related

- Non-blocking CI change: commit `6aa52ad` (`.github/workflows/postgres-ci.yml`)
- Isolation prerequisite: commit `a8826b2` (TRUNCATE seed-row restore) + `9230687` (autouse TRUNCATE fixture)
