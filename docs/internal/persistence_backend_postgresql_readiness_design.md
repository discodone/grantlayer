# GrantLayer Persistence Backend Boundary and PostgreSQL Readiness Design

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This document defines the persistence/backend boundary for GrantLayer as a **reusable, adaptable API-first product core** and prepares the path for PostgreSQL readiness without implementing it.

It clarifies:
- which persistence responsibilities belong to Product Core
- which database backend choices should remain configurable
- what is acceptable for local/test/demo SQLite usage
- what production-grade persistence will require
- how PostgreSQL readiness should be approached
- what must not be coupled too early
- which later implementation blocks should build persistence runtime behavior

This is a **product-foundation persistence design document**. It does not implement PostgreSQL, migrations, DB adapter code, runtime configuration, or secret management.

## 2. Product persistence principle

GrantLayer should protect **stable Product Core persistence contracts** while keeping concrete database backends configurable.

The Product Core owns persistent identifiers, record types, and transaction expectations for grant workflows. Concrete database connection details, driver selection, and backend-specific optimizations should remain replaceable adapter boundaries.

Local, test, and demo SQLite convenience must not accidentally become production persistence behavior. Any runtime mode that permits SQLite-only defaults must explicitly declare that it is not production-ready, and production deployment must refuse to start with unvalidated persistence configuration.

## 3. Product Core persistence responsibilities

Product Core persistence responsibilities include:

- **Stable persistent IDs** — identifiers that survive restarts, migrations, and backend changes
- **Grant request records** — create, read, list, and lifecycle state
- **Grant records** — approved grants with signatures, payload hashes, and signing key references
- **Grant execution records** — execution state, evidence linkage, and audit trail reference
- **Evidence bundle records** — stored evidence with integrity hashes and completeness metadata
- **Evidence verification records** — verification results, timestamps, and justification
- **Provenance/audit records** — decision provenance events, actor attribution, and policy references
- **Policy/compliance records** — active policy rules, requirements, exclusions, and permission profiles
- **Operator/access records where applicable** — operator identity references, role assignments, and capability mappings
- **Transaction expectations for product workflows** — grant approval and grant creation must not leave partially inconsistent state
- **Deterministic test fixtures** — test data that is isolated, reproducible, and never mixed with institutional data

## 4. Database backend boundary

The database backend boundary should enforce the following separation:

- **Product Core should not depend on SQLite-specific behavior** — queries and migrations should remain as backend-agnostic as possible; backend-specific adjustments belong in migration files and connection wrappers
- **Backend-specific connection details should stay behind configuration boundaries** — connection strings, pool settings, driver options, and retry policies should be runtime configuration, not hard-coded logic
- **Database credentials are secret-bearing config** — credentials must not be committed to source code, docs, examples, fixtures, or logs; they must be sourced through the approved secret boundary defined in GL-068
- **Storage backend choice should not change public API contracts** — switching from SQLite to PostgreSQL must not change API request/response schemas or endpoint behavior
- **Persistence errors should map into stable error semantics** — connection failures, transaction rollbacks, and constraint violations must be surfaced through stable error codes, not backend-specific exception text
- **Production mode should fail closed if persistence config is missing or invalid** — missing database backend declaration, unvalidated connection credentials, or unreachable persistence backend must block startup

## 5. SQLite boundary

SQLite is acceptable and convenient for:

- **local-dev** — single-developer, single-process development with local file storage
- **test** — in-memory or temporary file databases for deterministic automated verification
- **demo** — illustrative walkthroughs with isolated, non-production data
- **deterministic non-production examples** — fixtures and smoke tests that must run without external dependencies

SQLite is **not sufficient alone for production-readiness claims** because:

- it does not provide the concurrency, durability, and scaling guarantees required for institutional workloads
- file-level locking limits concurrent write throughput
- backup/restore and point-in-time recovery are operator-dependent rather than built-in
- schema migrations and long-running transactions require careful coordination outside the database

## 6. PostgreSQL readiness boundary

PostgreSQL should be treated as the **primary production candidate backend**, but not claimed ready until:

- **Connection configuration is explicit** — database URL, connection pool size, timeout values, and retry policy must be declared in configuration, not inferred
- **Credentials come from approved secret source** — database credentials must be sourced through the secret management boundary defined in GL-068, never from code or default strings
- **Schema compatibility is verified** — all Product Core tables, indexes, and constraints must be confirmed to work on PostgreSQL, not only on SQLite
- **Migrations are validated** — every migration must be tested against PostgreSQL, not only against SQLite
- **Transaction behavior is tested** — grant approval, grant creation, and evidence persistence flows must demonstrate correct transaction semantics on PostgreSQL
- **CI can run PostgreSQL-backed tests** — the test suite must be able to execute against a live PostgreSQL instance in CI or local environment
- **Backup/restore expectations are defined and verified** — retention, restore procedures, and recovery time objectives must be documented and tested
- **Operational runbooks exist** — database health checks, connection troubleshooting, and failover expectations must be documented for operators

## 7. Migration and schema evolution boundary

Schema evolution should follow these boundaries:

- **Migrations should remain explicit and reviewable** — every schema change must be represented by a numbered migration file with a clear purpose and rollback expectation
- **Schema changes must not happen silently** — automatic schema creation or modification without migration review is not acceptable for production
- **Backward compatibility should be considered for product releases** — schema changes that break existing Product Core records or API contracts must be versioned and communicated
- **Data migration risk should be separated from API behavior** — risky data migrations require dedicated validation and rollback planning, distinct from API feature work
- **Production deployment requires migration/runbook guidance** — operators must know which migrations apply, in what order, and what verification steps confirm success

## 8. Transaction and consistency expectations

Product Core workflows have transaction expectations that future backend work must validate:

- **Grant approval and grant creation flows require transactional clarity** — a grant request must not be approved without a corresponding grant record, and a grant record must not exist without a valid signature and payload hash
- **Evidence persistence and verification records need consistent linkage** — evidence bundle storage and verification results must refer to the same execution identifier and must not diverge
- **Audit/provenance records should not be partially inconsistent with workflow state** — a provenance event for grant approval must correspond to an existing grant record with matching identifiers
- **Future PostgreSQL work should include transaction semantics tests** — regression tests must verify that concurrent operations, failures mid-transaction, and rollback scenarios leave Product Core records in a consistent state

## 9. Backup, restore, and data lifecycle relationship

Persistence backend readiness is connected to backup/restore and data lifecycle design:

- **Backup/restore is not implemented in this block** — this design defines the boundary and expectations only
- **Production persistence must define retention, restore, and recovery expectations** — operators need documented retention policies, restore procedures, and disaster recovery guidance before production claims are valid
- **Data lifecycle design must consider product core record immutability** — evidence bundles, audit records, and provenance events may have stricter retention and deletion constraints than mutable workflow state

## 10. Future implementation expectations

The following later implementation blocks should build persistence runtime behavior:

1. **Persistence configuration schema** — explicit, versioned schema for database backend selection, connection parameters, and pool settings
2. **Database backend selection boundary** — runtime mechanism to select SQLite or PostgreSQL based on validated configuration, with clear product-core abstraction
3. **PostgreSQL connection configuration** — explicit, validated PostgreSQL connection parameters with bounded retry and health verification
4. **PostgreSQL test service / CI gate** — ability to run the full test suite against a live PostgreSQL instance in CI or local development
5. **Schema compatibility verification** — automated verification that all migrations and Product Core queries work correctly on PostgreSQL
6. **Migration execution validation** — testing framework that validates every migration against both SQLite and PostgreSQL
7. **Transaction consistency regression tests** — tests that verify atomic grant creation, approval, and evidence persistence under concurrent and failure conditions
8. **Backup/restore design and verification** — documented retention, restore procedures, and recovery testing
9. **Persistence operational runbook** — operator guidance for database health, connection troubleshooting, failover, and incident response
10. **Production fail-closed persistence startup checks** — startup validation that refuses to start if persistence configuration is missing, invalid, or unreachable in production mode

## 11. What not to implement yet

This block does **not** implement:

- PostgreSQL runtime support
- DB adapter refactor
- Migration changes
- Schema changes
- Docker Compose PostgreSQL service
- CI PostgreSQL service
- Cloud database setup
- Backup/restore automation
- Performance tuning
- Multi-tenant database model

## 12. Decision boundary

GrantLayer should **not claim production persistence readiness** until database backend selection, PostgreSQL compatibility, migrations, transactions, secrets, CI, backup/restore, and operational runbooks are implemented and verified.

SQLite local/test/demo convenience must not become production deployment behavior.

---

## Related artifacts

- `docs/persistence_backend_postgresql_readiness_design.md` (this document)
- `docs/examples/gl070/persistence_backend_matrix.json`
- `docs/examples/gl070/postgresql_readiness_catalog.json`
- `backend/tests/test_gl070_persistence_backend_postgresql_readiness.py`
- `docs/deployment_package_runtime_modes_design.md`
- `docs/runtime_configuration_environment_model.md`
- `docs/product_architecture_extension_boundaries.md`
- `docs/production_hardening_roadmap.md`
