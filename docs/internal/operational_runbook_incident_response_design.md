# GrantLayer Operational Runbook and Incident Response Baseline Design

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose and non-goals

This document establishes the **operational runbook and incident response baseline** for GrantLayer as a reusable, adaptable API-first product core. It prepares the path for future operational readiness, incident response, and operator coordination without implementing any of them.

It clarifies:
- what operational principles should guide GrantLayer operations
- which runtime modes are supported and what operational expectations apply to each
- what operator roles and responsibilities are needed for safe operation
- how incidents should be classified by severity
- what an incident lifecycle should look like from detection through post-incident review
- what runbook categories should exist for common incident types
- where escalation boundaries lie and when external parties must be involved
- what diagnostic signals operators should expect from future observability implementations
- what operator checks must be performed before and during manual intervention
- what safe manual intervention rules must be followed
- how audit and provenance integrity must be preserved during any operational action
- what communication expectations apply during incidents
- what post-incident review requirements are expected
- how operational expectations differ across environments
- which production-readiness gaps remain before operational runbooks are executable
- the future implementation sequence for operational and incident response work

This is a **product-foundation operational runbook and incident response design document**.

GL-073 explicitly states:
- GL-073 adds no incident-response implementation. GL-073 does not implement any incident response.
- GL-073 adds no monitoring implementation. GL-073 does not implement any monitoring.
- GL-073 adds no alerting implementation. GL-073 does not implement any alerting.
- GL-073 adds no operational automation. GL-073 does not implement any operational automation.
- GL-073 adds no deployment implementation. GL-073 does not implement any deployment.
- GL-073 adds no backup implementation. GL-073 does not implement any backup.
- GL-073 adds no restore implementation. GL-073 does not implement any restore.
- GL-073 adds no runtime config implementation. GL-073 does not implement any runtime configuration.
- GL-073 adds no database implementation. GL-073 does not implement any database.
- GL-073 adds no infrastructure implementation. GL-073 does not implement any infrastructure.
- GL-073 does not make GrantLayer production-ready.
- Operational actions must preserve audit/provenance integrity.
- Secret exposure incidents must follow the future secret-management policy and must not log raw secrets.
- Backup/restore incidents must follow the future backup/restore policy and must not improvise destructive recovery steps.

## 2. Operational principles for GrantLayer

GrantLayer operations should follow these principles:

- **Audit/provenance integrity is non-negotiable** — any operational action must preserve the immutability and tamper-evidence of audit and provenance records. Operational convenience must never justify modifying, deleting, or suppressing audit events.
- **Operator actions are themselves auditable** — every manual intervention must be recorded as an operator action event with actor attribution, timestamp, justification, and outcome.
- **Secrets must never be logged or transmitted in plain text** — raw secrets, tokens, private keys, and connection strings must never appear in logs, status pages, chat messages, or runbook outputs.
- **Contain before mitigation** — an incident must be contained (its blast radius limited) before attempting full mitigation or recovery. Reckless restart or rollback can increase damage.
- **Configuration mismatches are incidents** — running with the wrong runtime mode, stale configuration, or unvalidated deployment artifact is an operational incident even if the API appears healthy.
- **Evidence verification issues are integrity incidents** — any failure to verify evidence or any suspicion of tampered evidence must be treated as a potential integrity breach, not merely a user error.
- **No runbook is a substitute for judgment** — operators must be trained and empowered to deviate from runbooks when the documented path would increase risk, but deviations must themselves be documented.
- **No incident-response implementation is added in GL-073** — this document is purely a design and readiness baseline.

## 3. Supported operating modes

Operational expectations differ across runtime modes.

### 3.1 local
- **Purpose**: developer convenience during active development.
- **Operational expectation**: no formal runbook, no on-call, no incident response process. Local incidents are resolved by the developer.
- **Allowed actions**: restart, wipe database, rebuild from source, synthetic data injection.
- **Production claim boundary**: **must not** be described as production-ready or pilot-ready.

### 3.2 test
- **Purpose**: deterministic automated verification in CI and local test suites.
- **Operational expectation**: no operator intervention; failures are handled by CI retry or developer investigation.
- **Allowed actions**: rebuild fixtures, re-run test suite, inspect temporary database.
- **Production claim boundary**: no production claim.

### 3.3 demo
- **Purpose**: partner demonstration and integration evaluation.
- **Operational expectation**: demo runner validates smoke state; any failure is handled by re-running the demo script or reverting to known demo fixtures.
- **Allowed actions**: reset demo data, re-run demo scenario, restart the demo process.
- **Production claim boundary**: must not be described as production-ready.

### 3.4 staging
- **Purpose**: pre-production validation and integration rehearsal.
- **Operational expectation**: informal incident response may be exercised; runbooks should be drafted and validated here before production use.
- **Allowed actions**: execute draft runbooks, validate escalation paths, rehearse recovery steps, test observability signals.
- **Production claim boundary**: not production; data must not be real institutional data unless explicitly cleared.

### 3.5 future production
- **Purpose**: live institutional workload with real data, real actors, and real audit requirements.
- **Operational expectation**: formal runbooks, defined on-call rotations, severity-driven response times, mandatory post-incident reviews, and documented escalation boundaries.
- **Allowed actions**: only those covered by approved runbooks; any deviation requires incident commander approval and operator-action logging.
- **Production claim boundary**: production readiness requires all P0 production-hardening gates to be closed.

## 4. Operator roles and responsibilities

The following roles are expected for future production operation. GL-073 does not implement any of them.

### 4.1 Operator (on-call)
- Receives alerts and initial incident notifications.
- Performs first-check diagnostics as defined in runbooks.
- Executes containment steps within their authority boundary.
- Escalates when containment fails, severity exceeds their authority, or secrets may be exposed.
- Logs every action as an operator action event.

### 4.2 Incident Commander
- Assumes control of a sev0, sev1, or sev2 incident.
- Coordinates communication, resource allocation, and escalation decisions.
- Authorizes deviations from standard runbooks.
- Ensures post-incident review is scheduled and completed.
- Must not perform technical remediation directly; delegates to operators and subject-matter experts.

### 4.3 Security Officer
- Owns secret exposure, authentication breach, and authorization anomaly incidents.
- Must be consulted for any suspected secret exposure before public communication.
- Must approve any secret rotation or credential revocation plan.
- Must verify that incident logs do not contain raw secrets.

### 4.4 Database / Persistence Subject-Matter Expert
- Owns persistence/database issue incidents and backup/restore concern incidents.
- Must approve any restore plan that touches product, audit, or provenance data.
- Must verify that restores do not overwrite audit or provenance records.
- Must confirm that point-in-time recovery preserves the cryptographic integrity chain.

### 4.5 Audit / Compliance Officer
- Owns audit/provenance integrity concern incidents.
- Must verify that any operational action does not alter, suppress, or invalidate audit records.
- Must participate in post-incident reviews for any incident touching data integrity or compliance boundaries.
- Must approve communication that references audit, compliance, or regulatory obligations.

## 5. Incident severity model

GrantLayer incidents are classified by severity using the matrix in `docs/examples/gl073/incident_severity_matrix.json`. The summary is:

| Severity | Name | Examples | Response Time | Escalation | Review |
|----------|------|----------|---------------|------------|--------|
| sev0 | Critical | Complete API outage, provenance integrity breach, suspected secret exposure | Immediate | Yes, immediately | Mandatory |
| sev1 | Major | Severe API degradation, auth system unavailable, data corruption suspicion | < 15 minutes | Yes | Mandatory |
| sev2 | Significant | Partial feature degradation, intermittent errors, backup failure | < 1 hour | Yes, if unresolved | Mandatory |
| sev3 | Minor | Non-critical bug, slow response, single-tenant demo issue | < 4 hours | No | Optional |
| sev4 | Low | Cosmetic issue, documentation gap, internal tool inconvenience | < 24 hours | No | Optional |

All severities in the matrix must have `implementationStatus` set to `design_only` or `not implemented`, reflecting that GL-073 is a design block only.

## 6. Incident lifecycle

Every incident should follow a structured lifecycle. GL-073 defines the lifecycle stages; future implementation will automate and instrument them.

### 6.1 Detection
- An incident is detected by an operator, a future monitoring system, a future alerting system, a user report, or an automated health check.
- Detection must include: timestamp, detector identity, initial signal or symptom, affected runtime mode, and preliminary severity guess.
- Detection records must be auditable and must not include raw secrets.

### 6.2 Triage
- Triage confirms whether the symptom represents a real incident, classifies severity, identifies affected systems, and determines if escalation is needed.
- Triage must answer: Is this a real incident? What is the severity? Which data categories are at risk? Is audit/provenance integrity threatened? Are secrets involved?
- Triage outputs: incident severity, incident commander assignment (if escalated), initial communication plan, and containment priority.

### 6.3 Containment
- Containment limits the blast radius before attempting full mitigation.
- Containment actions may include: disabling a failing endpoint, revoking a suspected token, isolating a compromised host, pausing a deployment pipeline, or switching to a degraded-read mode.
- Containment must be logged as an operator action event with justification.
- Containment must not destroy audit records, provenance records, or evidence metadata.

### 6.4 Mitigation
- Mitigation removes the root cause or restores normal operation within the contained boundary.
- Mitigation actions may include: restarting a service after root cause is understood, rolling back a deployment, rotating a secret, rebuilding a configuration, or restoring data from a validated backup.
- Mitigation must not overwrite audit or provenance records.
- Mitigation must be validated with a smoke check or health verification before being considered complete.

### 6.5 Recovery
- Recovery restores the system to full normal operation and verifies that all subsystems are healthy.
- Recovery includes: re-enabling disabled endpoints, confirming traffic is stable, validating that audit/provenance records are intact, confirming that secrets are correctly loaded, and running a representative end-to-end check.
- Recovery must be declared explicitly by the incident commander or operator.
- Recovery does not close the incident until the post-incident review is scheduled.

### 6.6 Post-incident review
- Every sev0, sev1, and sev2 incident requires a post-incident review.
- The review must cover: timeline of detection, triage, containment, mitigation, and recovery; what went well; what did not go well; what runbook gaps were exposed; what follow-up actions are required; and whether any audit or compliance officer must be notified.
- The review output must be stored as a durable record (not an ephemeral chat log) and linked to the incident identifier.
- If audit/provenance integrity was touched, the review must include a verification statement from the audit/compliance officer.

## 7. Runbook categories

GrantLayer should have representative runbooks for the following categories. See `docs/examples/gl073/operational_runbook_catalog.json` for the machine-readable catalog.

### 7.1 API unavailable
- The API returns no response, 503 errors, or connection refused for all endpoints.
- Runbook covers: health check execution, dependency status (database, secret source), recent deployment or configuration change, restart protocol, and escalation path.

### 7.2 Degraded API behavior
- The API responds but with elevated latency, elevated error rate, partial feature failure, or inconsistent responses.
- Runbook covers: identifying the degraded endpoint, correlating with recent changes, checking for resource exhaustion, deciding whether to degrade gracefully or restart, and logging operator actions.

### 7.3 Authentication/authorization incident
- Users or operators cannot authenticate, tokens are rejected unexpectedly, or permissions are incorrectly granted or denied.
- Runbook covers: distinguishing between auth provider failure and GrantLayer permission logic failure, checking token validity and expiry, identifying whether the incident is systemic or scoped, and escalating to the security officer.

### 7.4 Secret exposure suspicion
- Any suspicion that a secret (API key, signing key, token, password, connection string) has been exposed, leaked, or compromised.
- Runbook covers: immediate containment (revocation, isolation), confirming scope of exposure, secret rotation plan, verifying that no raw secrets were logged during the incident, and mandatory security officer involvement.
- **Raw secrets must never be logged in incident records, runbook outputs, or communication channels.**

### 7.5 Persistence/database issue
- Database connection failures, query timeouts, data corruption suspicion, or replication lag.
- Runbook covers: checking connection pool health, identifying whether the issue is in the database server or the application layer, determining if a point-in-time restore is appropriate, and involving the database/persistence subject-matter expert.
- **Restores must not overwrite audit or provenance records.**

### 7.6 Evidence verification issue
- Evidence fails verification, hash mismatch, tamper detection triggers, or completeness score anomalies.
- Runbook covers: isolating the affected evidence bundle, determining whether the issue is in the evidence payload storage or the verification logic, preserving the current state for forensic analysis, and escalating to the audit/compliance officer.

### 7.7 Audit/provenance integrity concern
- Any suspicion that audit records or provenance records have been altered, deleted, or suppressed; or that the cryptographic integrity chain is broken.
- Runbook covers: immediate freeze of any deletion or purge jobs, hash chain verification, comparison with immutable storage copies if available, and mandatory involvement of the audit/compliance officer.
- **Audit and provenance records must never be overwritten, deleted, or suppressed as part of incident response.**

### 7.8 Backup/restore concern
- Backup failure, backup integrity suspicion, restore need, or recovery point objective violation.
- Runbook covers: verifying the backup scope and integrity, identifying the correct restore snapshot, executing a scoped restore (not a blanket dump), validating restored data, and confirming that audit/provenance records remain intact.
- **Backup/restore incidents must follow the future backup/restore policy and must not improvise destructive recovery steps.**

### 7.9 Configuration/runtime mode mismatch
- The system is running with the wrong runtime mode, unvalidated configuration, or a configuration value that contradicts the deployment environment.
- Runbook covers: identifying the mismatch, determining whether the system must be stopped immediately, rebuilding configuration from validated deployment artifacts, and running a post-config smoke check.

### 7.10 Deployment rollback need
- A deployment has introduced regression, instability, or security exposure and must be rolled back.
- Runbook covers: identifying the last known good deployment, verifying rollback artifact integrity, executing the rollback, validating health post-rollback, and deciding whether the new deployment must be blocked from re-release until root cause is fixed.

## 8. Escalation boundaries

Escalation is required when an incident exceeds the operator's authority, expertise, or time-bound containment capability.

| Scenario | Escalate To | Condition |
|----------|-------------|-----------|
| sev0 or sev1 severity | Incident Commander immediately | Any sev0 or sev1 classification |
| Suspected secret exposure | Security Officer immediately | Any suspicion of leaked or compromised secret |
| Audit/provenance integrity concern | Audit/Compliance Officer immediately | Any suspicion of altered or suppressed audit record |
| Database corruption or restore need | Database / Persistence SME | Any persistence issue beyond connection retry |
| Auth system breach or anomaly | Security Officer | Any auth incident that is not a simple token expiry |
| Evidence tamper detection | Audit/Compliance Officer | Any evidence verification failure indicating tamper |
| Communication to external parties | Incident Commander + Security Officer | Any incident that may require public or partner notification |
| Runbook does not cover the symptom | Incident Commander | When standard runbook steps would increase risk |

Escalation must be logged as an operator action event with timestamp, reason, and recipient role.

## 9. Required diagnostic signals

Future observability implementations (beyond GL-073) must provide the following diagnostic signals for safe operations. GL-073 documents them as requirements only.

- **API health status** — a coarse-grained signal indicating whether the API is accepting requests and returning expected responses.
- **Endpoint-level latency and error rate** — per-endpoint signals to identify degraded behavior before it becomes an outage.
- **Database connection pool status** — active connections, waiting requests, and recent connection failures.
- **Authentication failure rate** — rate of failed login, token rejection, or permission denial events, with distinction between user error and systemic failure.
- **Runtime mode declaration** — explicit signal of which runtime mode the process believes it is in.
- **Configuration validation status** — whether the current configuration passed validation or has known mismatches.
- **Recent deployment identifier** — what deployment artifact or version is currently running.
- **Audit record write success/failure rate** — whether audit events are being recorded successfully.
- **Provenance hash computation success/failure rate** — whether provenance hashes are being computed and stored without error.
- **Backup completion status** — whether the most recent backup completed successfully, failed, or is overdue.
- **Secret source connectivity** — whether the system can reach its configured secret source (if applicable).

All diagnostic signals must be designed to emit structured events following the GL-071 baseline when observability is implemented.

## 10. Required operator checks

Before taking any manual action that affects runtime state, data, or configuration, an operator must perform the following checks:

1. **Identify the runtime mode** — confirm whether the target is local, test, demo, staging, or production. Do not apply production runbook steps to a local instance.
2. **Confirm the current deployment version** — know what is running before attempting restart, rollback, or config change.
3. **Check recent changes** — review recent deployments, configuration changes, or operator actions that may have preceded the incident.
4. **Verify audit/provenance integrity is not at risk** — ensure the planned action will not overwrite, delete, or suppress audit or provenance records.
5. **Confirm no raw secrets will be exposed** — ensure that logs, command output, or shared screens will not display secrets.
6. **Check whether escalation is required** — if the incident is sev0, sev1, sev2, or involves secrets, audit, or database integrity, escalate before acting.
7. **Document the planned action** — record the operator action event with justification before execution.
8. **Validate post-action state** — after the action, run a health check or smoke test to confirm the intended outcome and detect unintended side effects.

## 11. Safe manual intervention rules

Manual intervention must follow these safety rules:

- **Stop before you break the audit chain** — if an action might alter the sequence of audit or provenance records, pause and escalate.
- **Never restart blindly** — restarting without understanding the root cause can mask a data integrity issue or trigger a cascading failure.
- **Never rollback secrets from backup** — secrets must be rotated or re-fetched from the approved secret source; never restore secret values from a backup snapshot.
- **Never bypass auth for convenience** — disabling authentication or elevating a demo token to bypass an auth issue is a security incident, not a workaround.
- **Never delete evidence metadata to "fix" a verification failure** — a verification failure is a signal of potential tampering or bug; deleting metadata destroys forensic evidence.
- **Log every manual action** — every command, config edit, restart, rollback, or data change must be recorded as an operator action event.
- **Test in staging before applying to production** — if a containment or mitigation step is novel, rehearse it in a non-production environment first.
- **Preserve the current state for forensics** — before destructive recovery (restore, wipe, rebuild), capture the current state or a snapshot for later analysis.

## 12. Data integrity and auditability considerations

Operational actions have direct implications for data integrity and auditability.

- **Audit/provenance records must remain immutable** — no incident response action may update, delete, or suppress an audit event or provenance record. The only permitted transition is classification change (e.g., to legal-hold state).
- **Operator actions are auditable events** — every manual intervention creates an operator action record with actor, timestamp, command or action description, justification, and outcome.
- **Incident timelines must be reconstructible** — detection, triage, containment, mitigation, recovery, and review timestamps must be durable and linked by incident identifier.
- **Forensic preservation** — before any destructive recovery step, operators must preserve the current database state or relevant snapshot for later review.
- **Cross-category isolation** — restoring or deleting product records must not cascade to audit records, provenance records, or evidence metadata.
- **Redaction applies to incident artifacts** — incident logs, runbook outputs, and communication channels must apply the same redaction rules as operational logs (no raw secrets, no full evidence payloads).

## 13. Communication and status update expectations

Communication during incidents must be deliberate and controlled.

- **Internal status updates** — sev0 and sev1 incidents require status updates at least every 15 minutes until containment is achieved. sev2 incidents require updates at least every 1 hour.
- **External communication** — any public, partner, or regulatory communication must be approved by the incident commander and, if secrets or compliance are involved, by the security officer or audit/compliance officer.
- **No raw secrets in communication** — status pages, chat channels, emails, and incident tickets must never include raw secrets, tokens, private keys, or full connection strings.
- **Communication records are part of the incident timeline** — key communications (decisions, escalations, external notifications) should be referenced in the post-incident review.
- **Communication channels must be durable** — ephemeral chat messages are insufficient for sev0 and sev1 incidents; a durable incident log or ticket must capture decisions.

## 14. Post-incident review requirements

Post-incident reviews are mandatory for sev0, sev1, and sev2 incidents.

- **Timeline reconstruction** — the review must include a minute-level or event-level timeline from detection through recovery.
- **Root cause analysis** — the review must identify the contributing causes (not just the trigger) and distinguish between technical, process, and human factors.
- **Runbook gap identification** — if a runbook did not exist, was unclear, or was wrong, the review must document the gap and propose an update.
- **Follow-up action tracking** — every review must produce a set of tracked follow-up actions with owners and deadlines.
- **Audit/compliance sign-off** — if the incident touched audit, provenance, evidence integrity, or secrets, the review must include a sign-off from the relevant officer.
- **Review distribution** — the review record must be stored durably and accessible to future incident commanders, operators, and auditors.
- **No blame attribution** — the review focuses on system and process improvement, not individual blame.

## 15. Environment-specific differences

Operational runbook expectations differ across runtime modes.

### 15.1 local
- No formal incident response process.
- No on-call rotation.
- No communication expectations.
- Operators (developers) may restart, wipe, or rebuild at will.
- Audit/provenance integrity should still be respected for testing purposes.

### 15.2 test
- No formal incident response process.
- Failures are investigated by developers or CI maintainers.
- No communication expectations.
- No post-incident review required.

### 15.3 demo
- Informal incident response: reset demo data or re-run the demo runner.
- No on-call rotation.
- Communication limited to internal demo coordinator.
- No post-incident review required.

### 15.4 staging
- Draft runbooks should be exercised here.
- Informal on-call rotation may be used for rehearsal.
- Internal communication only; no external status pages.
- Post-incident review is recommended but not mandatory.
- All manual interventions should be logged to validate the operator action event model.

### 15.5 future production
- Formal runbooks are mandatory.
- Defined on-call rotation with escalation paths.
- External status pages or partner notification channels may be required.
- Post-incident review is mandatory for sev0, sev1, and sev2.
- All operator actions are logged and audited.
- Security officer and audit/compliance officer roles are active.

## 16. Production-readiness gaps

GL-073 does not claim production operational readiness. The following gaps remain to be closed by later implementation blocks:

- No monitoring system is implemented.
- No alerting system is implemented.
- No automated health checks are implemented.
- No incident ticketing or tracking system is integrated.
- No operator action event logging is implemented.
- No incident commander workflow is implemented.
- No on-call rotation or paging integration is implemented.
- No structured runbook execution or automation is implemented.
- No status page or external communication channel is implemented.
- No post-incident review workflow or template is implemented.
- No escalation routing or role mapping is implemented.
- No secret rotation automation is implemented.
- No database point-in-time restore automation is implemented.
- No configuration validation gate at startup is implemented.
- No deployment rollback automation is implemented.
- No forensic snapshot capture workflow is implemented.
- No audit/compliance officer sign-off workflow is implemented.

## 17. Future implementation sequence

The following sequence is recommended for operational runbook and incident response implementation blocks after GL-073:

1. **Health check and smoke test baseline** — implement coarse health and readiness endpoints that support runbook first-checks.
2. **Operator action event logging** — implement structured operator action events following the GL-071 baseline.
3. **Monitoring and alerting baseline** — implement the minimum metrics and alerting thresholds documented in the GL-071 observability design.
4. **Incident ticketing integration** — integrate with an incident tracking system or define a lightweight internal incident record format.
5. **Runbook execution support** — implement runbook templates and a lightweight execution checklist that operators can follow and log.
6. **Escalation routing** — implement role mapping and escalation paths so that sev0/sev1 incidents reach the incident commander automatically.
7. **Post-incident review workflow** — implement review templates, timeline reconstruction helpers, and follow-up action tracking.
8. **Secret rotation runbook automation** — implement safe secret rotation with rollback capability and validation.
9. **Database restore validation runbook** — implement scoped restore with integrity checks and audit preservation.
10. **Deployment rollback automation** — implement safe rollback with health validation and artifact integrity checks.
11. **Forensic snapshot capture** — implement automatic pre-recovery snapshot capture for later analysis.
12. **External status page** — implement a minimal external status page for partner-facing incidents.

## Non-goals

- GL-073 does not implement any incident response, monitoring, alerting, or operational automation.
- GL-073 does not implement any deployment, runtime configuration, or infrastructure.
- GL-073 does not implement any backup, restore, or data lifecycle automation.
- GL-073 does not implement any logging, observability, metrics, or tracing.
- GL-073 does not implement any authentication, authorization, or secret management.
- GL-073 does not implement any persistence, database, or PostgreSQL-specific feature.
- GL-073 does not implement any dashboard, UI, or client.
- GL-073 does not claim production readiness.

---

## See also

- [`docs/production_hardening_roadmap.md`](production_hardening_roadmap.md) — GL-066 production hardening roadmap
- [`docs/product_architecture_extension_boundaries.md`](product_architecture_extension_boundaries.md) — GL-065 product architecture and extension boundaries
- [`docs/runtime_configuration_environment_model.md`](runtime_configuration_environment_model.md) — GL-068 runtime configuration and environment model
- [`docs/deployment_package_runtime_modes_design.md`](deployment_package_runtime_modes_design.md) — GL-069 deployment package and runtime modes design
- [`docs/persistence_backend_postgresql_readiness_design.md`](persistence_backend_postgresql_readiness_design.md) — GL-070 persistence backend and PostgreSQL readiness design
- [`docs/observability_structured_logging_baseline_design.md`](observability_structured_logging_baseline_design.md) — GL-071 observability and structured logging baseline design
- [`docs/backup_restore_data_lifecycle_design.md`](backup_restore_data_lifecycle_design.md) — GL-072 backup, restore, and data lifecycle design
- [`docs/examples/gl073/incident_severity_matrix.json`](examples/gl073/incident_severity_matrix.json) — machine-readable incident severity matrix
- [`docs/examples/gl073/operational_runbook_catalog.json`](examples/gl073/operational_runbook_catalog.json) — machine-readable operational runbook catalog
- [`backend/tests/test_gl073_operational_runbook_incident_response.py`](../backend/tests/test_gl073_operational_runbook_incident_response.py) — validation test for this design
