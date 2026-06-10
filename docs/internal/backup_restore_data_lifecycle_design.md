# GrantLayer Backup, Restore, and Data Lifecycle Design

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This document establishes the **backup, restore, and data lifecycle baseline** for GrantLayer as a reusable, adaptable API-first product core. It prepares the path for future backup, restore, retention, and data lifecycle readiness without implementing any of them.

It clarifies:
- which data categories exist in GrantLayer and their recovery criticality
- the boundary between data that should be backed up, archived, retained, and eventually purged
- the separation between product records, audit records, provenance records, evidence metadata, runtime configuration, secrets, and operational logs
- what a restore scope must include for each environment
- what recovery point objective (RPO) and recovery time objective (RTO) assumptions are reasonable
- how data lifecycle stages flow from active to archived to expired and purged
- what retention policy baseline should govern institutional, audit, legal, and operational data
- what export and import boundaries must be respected
- what is expected across local, test, demo, staging, and production environments
- what observability signals future backup/restore operations must emit
- which production-readiness gaps remain before backup and restore are complete
- the future implementation sequence for backup, restore, and data lifecycle work

This is a **product-foundation backup and restore design document**.

GL-072 explicitly states:
- GL-072 adds no backup implementation. GL-072 does not implement any backup.
- GL-072 adds no restore implementation. GL-072 does not implement any restore.
- GL-072 adds no lifecycle automation. GL-072 does not implement any lifecycle automation.
- GL-072 adds no retention job. GL-072 does not implement any retention job.
- GL-072 adds no database implementation. GL-072 does not implement any database.
- GL-072 adds no PostgreSQL implementation. GL-072 does not implement any PostgreSQL-specific feature.
- GL-072 adds no object storage implementation. GL-072 does not implement any object storage.
- GL-072 adds no infrastructure implementation. GL-072 does not implement any infrastructure.
- GL-072 does not make GrantLayer production-ready.
- Secrets must not be stored in ordinary backups unless future secret-management policy explicitly allows it.
- Audit/provenance records may have stricter retention and immutability requirements than ordinary operational data.

## 2. Backup/restore principles for GrantLayer

GrantLayer backup and restore should follow these principles:

- **Backup scope is data-category-driven** — not all data categories are treated the same way. Product records, audit records, and provenance records have different backup frequencies, retention, and immutability needs.
- **Secrets are excluded from ordinary backups** — secrets must not be stored in ordinary backups unless a future secret-management policy explicitly allows it. Secret recovery must use the approved secret source.
- **Audit and provenance records are integrity-sensitive** — these records may require append-only, tamper-evident storage and longer retention than operational data.
- **Restore must be intentional and scoped** — restores should target specific data categories and time ranges, not blanket database dumps.
- **Evidence payloads are out of product-core scope** — evidence metadata belongs to the product core; evidence payload storage is an extension boundary and must be backed up and restored via its own adapter.
- **Operational logs have short retention** — they do not need the same recovery priority as product records.
- **Configuration is replaceable, not the primary recovery target** — runtime configuration should be reproducible from a validated source; restoring stale config may be worse than rebuilding it.
- **No backup implementation is added in GL-072** — this document is purely a design and readiness baseline.

## 3. Data categories and recovery criticality

GrantLayer data can be divided into the following categories, ordered by recovery criticality:

### 3.1 Product records (highest criticality)
- Grant requests, grants, grant executions
- Evidence metadata (not payload content)
- Policy requirement results
- Approval records
- These records are the core business data. Loss or corruption directly impacts institutional operations.

### 3.2 Audit records (highest criticality)
- Decision audit events, actor attribution, timestamps
- Must be tamper-evident and retained for institutional, compliance, and forensic purposes.
- Audit/provenance records may have stricter retention and immutability requirements than ordinary operational data.

### 3.3 Provenance records (highest criticality)
- Cryptographic hashes, signatures, anchoring references
- Must survive any restoration event because they represent the integrity chain of trust.
- Should be stored in append-only, immutable storage.

### 3.4 Evidence metadata (high criticality)
- Evidence bundle records, verification results, completeness metadata
- Evidence payload references point to external storage; the metadata itself must be backed up.
- Actual payloads are backed up via the evidence storage adapter, not the product core.

### 3.5 Configuration records (medium criticality)
- Runtime configuration values, validated settings
- Should be reproducible from deployment artifacts and secrets.
- Restoring stale config can cause more harm than rebuilding from source.

### 3.6 Compliance and gap reports (medium criticality)
- Compliance readiness summaries, gap reports
- Useful for audits but typically reproducible from product and policy data.

### 3.7 Operational logs (low criticality)
- Structured logs, metrics snapshots, trace spans
- Short-lived; their primary value is incident response within a narrow time window.
- Not a primary restore target.

### 3.8 Secrets (excluded from ordinary backup)
- API keys, signing keys, tokens, passwords, connection strings
- Must not be stored in ordinary backups unless future secret-management policy explicitly allows it.
- Recovery must use the approved secret source (secret manager, HSM, etc.).

## 4. Boundary between data domains

GrantLayer must keep these data domains conceptually separate for backup, restore, and lifecycle purposes.

### 4.1 Product records
- Core business state that GrantLayer manages directly.
- Must be backup-eligible and restore-eligible.
- Retention depends on institutional policy.

### 4.2 Audit records
- Immutable, append-only decision history.
- May require separate storage, longer retention, and stricter access controls.
- Should not be overwritten during restore.

### 4.3 Provenance records
- Cryptographic proof of decisions and state changes.
- Must be preserved across any restore event.
- Ideally stored in immutable, append-only storage.

### 4.4 Evidence metadata
- References and verification results for evidence.
- Backed up with product records; actual payloads backed up separately.

### 4.5 Evidence payload references
- Pointers to external storage systems (object storage, file systems, etc.).
- The external system is responsible for its own backup and restore.
- Product core must not attempt to inline or duplicate payloads in its own backups.

### 4.6 Runtime configuration
- Validated configuration values used at runtime.
- Should be reproducible from deployment artifacts.
- Ordinary restores may skip config in favor of rebuilding from source.

### 4.7 Secrets
- Must not be stored in ordinary backups unless future secret-management policy explicitly allows it.
- Recovery must use dedicated secret-management procedures.

### 4.8 Operational logs
- Ephemeral observability data.
- Short retention; not a restore priority.

## 5. Backup scope model

GrantLayer backups should be scoped by data category. See `docs/examples/gl072/backup_restore_scope_matrix.json` for the representative scope matrix.

Key backup rules:
- Product records, audit records, provenance records, and evidence metadata are the primary backup scope.
- Operational logs may be backed up for a short window but are not critical.
- Secrets are excluded from ordinary backups unless a future policy explicitly allows it.
- Evidence payload references are backed up, but the payloads themselves are backed up by the external storage adapter.
- Configuration records may be included for convenience but should be reproducible from source.

## 6. Restore scope model

Restores should be scoped and intentional:

- **Full product restore** — grant requests, grants, executions, evidence metadata. Used after catastrophic data loss.
- **Audit record restore** — append-only restoration of audit events. Must not overwrite existing audit records.
- **Provenance restore** — cryptographic chain must be intact after restore. Provenance records should be verified post-restore.
- **Point-in-time restore** — product records restored to a specific timestamp. Audit and provenance must remain intact.
- **Config rebuild (preferred over restore)** — operators should rebuild validated config from deployment artifacts rather than restore stale config from backup.
- **Operational log replay is not supported** — logs are not restored; systems should rebuild from current time forward.

## 7. Recovery point objective / recovery time objective assumptions

GL-072 defines design-time RPO and RTO assumptions. These are targets, not guarantees.

- **RPO for product records** — minutes to hours, depending on backup frequency.
- **RPO for audit/provenance records** — near-zero, because they should be streamed to immutable storage as they are created.
- **RTO for product records** — hours to restore from backup, plus validation.
- **RTO for audit/provenance** — minutes if using immutable append-only storage; hours if recovering from backup snapshots.
- **RPO/RTO for operational logs** — not defined; logs are ephemeral.
- **RPO/RTO for secrets** — not applicable; secrets are recovered via secret-management procedures, not backup restore.

Actual RPO/RTO values will be defined in future operational runbooks.

## 8. Data lifecycle stages

GrantLayer data flows through the following lifecycle stages. See `docs/examples/gl072/data_lifecycle_policy_catalog.json` for representative policies.

- **Active** — currently in use, readable, writable, and backed up.
- **Archived** — no longer actively accessed but retained for compliance or historical reference. Read-only.
- **Retained for audit** — kept for institutional audit and compliance purposes. Immutable.
- **Retained for legal hold** — kept for legal or regulatory proceedings. Must not be deleted.
- **Expired** — past its retention period, pending deletion or purge review.
- **Deletion pending** — marked for deletion, awaiting operator confirmation or automated purge.
- **Deleted or purged** — no longer stored in primary or backup systems, or cryptographically shredded.

## 9. Retention policy baseline

The following retention classes are recommended for future implementation:

- **Operational data** — days to weeks (varies by volume and environment).
- **Product records** — months to years, governed by institutional policy.
- **Audit records** — years, possibly indefinite, governed by compliance requirements.
- **Provenance records** — indefinite or partner-agreed minimum.
- **Evidence metadata** — aligned with product records and partner agreements.
- **Evidence payloads** — partner-agreed, may be shorter or longer than metadata.
- **Compliance reports** — aligned with audit record retention.
- **Secrets** — governed by secret-management policy and rotation schedule, not ordinary data retention.

## 10. Deletion and archival boundaries

Future GrantLayer implementations should enforce the following deletion and archival boundaries:

- **Audit and provenance records must not be destructively deleted** — they may be transitioned to archived or legal-hold states, but not purged without explicit policy.
- **Evidence payloads must be deletable by evidence storage policy** — metadata retention may outlast payload retention.
- **Product records may be soft-deleted initially** — with a grace period before final purge.
- **Operational logs may be purged on schedule** — no special retention requirements beyond operational needs.
- **Secrets must be deleted via secret-management procedures** — not via ordinary data deletion jobs.
- **Cross-category deletion is not permitted** — deleting a grant request must not cascade to audit records or provenance events.

## 11. Evidence and audit immutability considerations

GrantLayer must treat audit and provenance data as append-only and tamper-evident.

- **Audit records** — once written, they must not be updated or deleted by product operations. The only allowed transitions are archival or legal-hold classification.
- **Provenance records** — cryptographic hashes and signatures must be preserved across backup, restore, and migration events. Restoring a database snapshot must not invalidate provenance.
- **Evidence verification results** — verification timestamps and outcomes are part of the audit/provenance chain and must be immutable.
- **Immutability implementation** — future blocks should consider write-once storage, append-only database constraints, or blockchain anchoring for provenance.

## 12. Export/import boundaries

Future GrantLayer implementations may support export and import for specific data categories. The following boundaries should be respected:

- **Export scope** — product records, evidence metadata, and audit events may be exported for partner integration or offline analysis.
- **Secrets must not be exported** — API keys, tokens, and private keys must never be included in exports.
- **Evidence payloads are exported via the storage adapter** — not by the product core.
- **Import validation** — imported records must be validated against current schema, policy, and integrity constraints.
- **Import must not overwrite audit/provenance** — imported records should be merged or inserted, never replacing existing audit or provenance events.
- **Redaction policy applies to exports** — the same redaction rules that apply to logs apply to exports.

## 13. Environment-specific differences

Backup, restore, and lifecycle expectations differ across runtime modes:

### local / dev
- No formal backup required; developers may use local snapshots or SQLite file copies.
- No retention policy enforcement.
- No production-ready claim is made.

### test
- Test data should be isolated and reproducible from fixtures; backups are not meaningful.
- Data may be ephemeral; databases may be recreated per test run.
- No retention policy needed.

### demo
- Demo data may be reset on demand; no backup required.
- If backed up, data should be clearly labeled as demo-only.
- Short retention if any.

### staging / pilot
- Backups should exist for validation and disaster recovery rehearsal.
- Retention may be shorter than production but should follow the same category boundaries.
- Restores should be tested regularly.

### production (future)
- Formal backup schedules, retention policies, and restore runbooks must be in place.
- Audit/provenance must be streamed to immutable storage.
- Evidence payloads backed up via the storage adapter.
- Secrets excluded from ordinary backups.
- RPO and RTO must be measured and reported.
- Deletion and purge jobs must be audited.

## 14. Security and redaction rules for backups

Backups must follow the same security and redaction rules as the runtime system.

- **Secrets must not be stored in ordinary backups** unless future secret-management policy explicitly allows it.
- **Backup encryption** — production backups must be encrypted at rest and in transit.
- **Backup access controls** — only authorized operators and disaster-recovery roles may access backups.
- **Backup integrity verification** — checksums or cryptographic proofs should verify backup integrity.
- **Redaction applies** — exports from backups must apply the same redaction rules as live systems.
- **Test/demo data must be clearly labeled** — restored test or demo data must not be confused with institutional data.
- **Backup storage separation** — backups should be stored in a different failure domain than the primary system.

## 15. Operator responsibilities

Operators running GrantLayer in production must be able to:

- Identify which data categories are included in a given backup snapshot.
- Restore specific categories without affecting others.
- Verify backup integrity before relying on it.
- Rebuild validated runtime configuration from deployment artifacts rather than restoring stale config.
- Execute a point-in-time restore while preserving audit and provenance immutability.
- Confirm that secrets are recovered via secret-management procedures, not from backup.
- Review and approve deletion or purge jobs.
- Report RPO and RTO metrics.

Operator runbooks for these tasks are future scope.

## 16. Observability requirements for backup/restore events

Future implementations must emit observability signals for backup and restore events. These events should be logged as structured events following the GL-071 baseline.

Required event types:
- **backup_started** — scope, timestamp, operator or job identifier.
- **backup_completed** — success or failure, bytes transferred, duration.
- **backup_failed** — error category, retryable or fatal.
- **restore_started** — scope, source snapshot, operator identifier.
- **restore_completed** — success or failure, categories restored, validation status.
- **restore_failed** — error category, impacted categories.
- **lifecycle_transition** — record moved from active to archived, expired, or deletion_pending.
- **purge_executed** — records permanently deleted, operator confirmation, audit event reference.

All events must include correlation IDs following the GL-071 baseline.

## 17. Production-readiness gaps

GL-072 does not claim production backup, restore, or data lifecycle readiness. The following gaps remain to be closed by later implementation blocks:

- Backup scheduling and automation are not implemented.
- Restore procedures and validation are not implemented.
- Retention job automation is not implemented.
- Deletion and purge job automation is not implemented.
- Immutable audit/provenance storage is not implemented.
- Backup encryption at rest and in transit is not configured.
- Backup integrity verification is not implemented.
- Point-in-time restore capability is not implemented.
- Object storage adapter for evidence payload backup is not implemented.
- Cross-region or off-site backup replication is not configured.
- Operator runbooks for backup/restore are not written.
- RPO/RTO measurement and reporting are not implemented.
- Export/import functionality is not implemented.
- Lifecycle automation triggers (inactive detection, expiration) are not implemented.

## 18. Future implementation sequence

The following sequence is recommended for backup, restore, and data lifecycle implementation blocks after GL-072:

1. **Backup scope implementation** — instrument product-core data categories for snapshot-based backup; exclude secrets.
2. **Immutable audit stream** — stream audit and provenance events to append-only, tamper-evident storage.
3. **Evidence payload backup adapter** — implement backup/restore via the evidence storage adapter boundary.
4. **Restore validation** — implement restore procedures with integrity checks and category scoping.
5. **Retention policy engine** — implement retention classes, lifecycle transitions, and scheduled jobs.
6. **Deletion and purge jobs** — implement deletion_pending → deleted_or_purged workflows with operator approval gates.
7. **Backup encryption and access controls** — enforce encryption at rest, encryption in transit, and role-based access.
8. **Point-in-time restore** — implement time-bounded restore for product records.
9. **Export/import boundaries** — implement scoped export and validated import with redaction and integrity checks.
10. **Operator runbooks and observability** — document procedures, measure RPO/RTO, and emit structured backup/restore events.

## Non-goals

- GL-072 does not implement any backup, restore, or data lifecycle automation.
- GL-072 does not implement any retention job or scheduler.
- GL-072 does not implement any database or PostgreSQL-specific feature.
- GL-072 does not implement any object storage or cloud storage integration.
- GL-072 does not implement any export or import functionality.
- GL-072 does not implement any runtime configuration.
- GL-072 does not implement any logging, observability, metrics, or tracing.
- GL-072 does not implement any authentication, authorization, or permission decisions.
- GL-072 does not implement any secret management.
- GL-072 does not implement any persistence or deployment infrastructure.
- GL-072 does not claim production readiness.
