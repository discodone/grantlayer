# GL-220 - Production Runtime & Infrastructure Hardening Pack

**Issue ID:** GL-220
**Title:** Production Runtime & Infrastructure Hardening Pack
**Branch:** `gl-220-production-runtime-infrastructure-hardening-pack`
**Status:** Internal / Developer Preview

GL-220 is runtime/infrastructure hardening, not production SaaS readiness. It
documents current runtime boundaries, remaining infrastructure gaps, and adds a
local dry-run/plan gate. It does not perform real production deployment.

GrantLayer remains Developer Preview / Controlled Preview with strict boundaries.
Production SaaS remains NO-GO unless a later Go/No-Go gate changes
that. Real customer data, private grant data, and institutional data remain
NO-GO. Official SDK/package remains NO-GO. Compliance certification remains
NO-GO. Live PostgreSQL production readiness remains NO-GO.

No real cloud, deployment, TLS certificate, external hostname, monitoring, or production secret rollout is performed by GL-220.

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
data is used.

Unrelated website-design/import files were excluded from GL-220. No
`website-design/` content or similarly named website-design import/report files
are included in this change.

---

## Context

GL-214 constrained production IAM/operator-control behavior. GL-215 tightened
tenant-visible runtime enforcement. GL-216 documented production operations
blockers and added a local operations gate. GL-217 kept Production SaaS NO-GO.
GL-218 preserved public/export safety boundaries. GL-219 documented identity and
access hardening and added fail-closed checks for unsupported external identity
configuration.

Runtime/infrastructure remains a major blocker before any production SaaS or
real-data claim. GL-220 reduces that blocker by making TLS, reverse proxy,
container/runtime hardening, process model, network exposure, request limits,
observability, secrets, backup/restore integration, and remaining blockers
explicit and locally checkable.

## Scope

- TLS / HTTPS / reverse proxy posture.
- Container/runtime hardening posture.
- Process supervisor/service model posture.
- Runtime environment and secret handling posture.
- Production config fail-closed posture.
- Request size / timeout / concurrency posture.
- Rate-limit/runtime abuse posture.
- Network exposure / ingress posture.
- Health/readiness runtime posture.
- Logging/correlation/observability posture.
- External monitoring/alerting requirements.
- Backup/restore/DR runtime integration posture.
- PostgreSQL runtime connectivity posture.
- Identity/access runtime dependency posture.
- Tenant/workspace runtime enforcement posture.
- Release/rollback/runtime recovery posture.
- Local dry-run/plan runtime infrastructure gate.

## Non-Goals

GL-220 does not:

- Claim Production SaaS readiness.
- Claim real customer/private grant/institutional data readiness.
- Claim official SDK/package availability.
- Claim compliance certification, GDPR, SOC2, ISO, or enterprise readiness.
- Claim live PostgreSQL production readiness.
- Add real TLS termination, certificates, private keys, or external hostnames.
- Add real reverse proxy configuration for a live domain.
- Add production deployment automation, cloud provider integration, registry
  credentials, Kubernetes, Terraform, Helm, or production deployment files.
- Add analytics, tracking, forms, package publishing metadata, release tags, or
  public snapshot/export behavior.
- Change GitHub workflows, snapshot publish scripts, visibility, public GitHub
  push behavior, backend migrations, schema, dependencies, or broad backend
  runtime logic.

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/production_go_no_go_v5.md | Yes |
| docs/examples/gl217/production_go_no_go_v5.json | Yes |
| docs/production_identity_access_hardening_pack.md | Yes |
| docs/examples/gl219/production_identity_access_hardening_pack.json | Yes |
| docs/public_external_review_export_safety_pack.md | Yes |
| docs/examples/gl218/public_external_review_export_safety_pack.json | Yes |
| docs/production_operations_hardening_pack.md | Yes |
| docs/examples/gl216/production_operations_hardening_pack.json | Yes |
| docs/tenant_workspace_production_guarantee.md | Yes |
| docs/examples/gl215/tenant_workspace_production_guarantee.json | Yes |
| docs/production_iam_operator_control_completion.md | Yes |
| docs/examples/gl214/production_iam_operator_control_completion.json | Yes |
| docs/runtime_abuse_incident_hardening.md | Yes |
| docs/examples/gl208/runtime_abuse_incident_hardening.json | Yes |
| docs/live_postgres_backup_observability_baseline.md | Yes |
| docs/examples/gl205/live_postgres_backup_observability_baseline.json | Yes |
| docs/production_ops_go_no_go_v3.md | Yes |
| docs/examples/gl204/production_ops_go_no_go_v3.json | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| docs/openapi.yaml | Yes |
| backend/src/server.py | Yes |
| backend/src/config.py | Yes |
| backend/src/auth.py | Yes |
| backend/src/identity_access.py | Yes |
| backend/src/operators.py | Yes |
| backend/src/audit_log.py | Yes |
| backend/src/db.py | Yes |
| backend/src/models.py | Yes |
| backend/tests/ | Yes |
| scripts/ops/gl216_production_operations_gate.py | Yes |
| scripts/ops/gl218_public_export_safety_scan.py | Yes |
| scripts/ops/gl219_identity_access_gate.py | Yes |
| scripts/ops/gl205_live_postgres_validation.py | Yes |
| scripts/ops/gl205_backup_restore_drill.py | Yes |
| scripts/ops/gl209_audit_export_check.py | Yes |
| scripts/run-full-backend-suite.sh | Yes |
| examples/grant_lifecycle_evidence_bundle.py | Yes |

## Current Runtime/Infrastructure State Summary

GrantLayer currently runs as a local Python HTTP service using
`ThreadingHTTPServer`. SQLite is the default persistence path and PostgreSQL is
optional. The server has health and readiness endpoints, exact-match CORS
allowlisting, security headers, a one-megabyte JSON request body limit,
in-process rate limiting, correlation ID propagation, structured safe logging,
admin/operator auth guards, tenant-derived auth context, and production-like
startup checks for unsafe local/demo configuration.

This is suitable for Developer Preview and controlled synthetic/demo evaluation.
It is not a production service model. There is no real TLS boundary, reverse
proxy rollout, external load balancer, hardened container operating model,
process supervisor specification, external monitoring stack, production backup
automation, production PostgreSQL topology, or real secrets lifecycle.

## Production Runtime/Infrastructure Gap Assessment

| Area | Current state | Remaining gap |
|---|---|---|
| TLS / HTTPS / reverse proxy | Not implemented in-app; OpenAPI uses localhost HTTP | No TLS termination, certificate lifecycle, HSTS, proxy header trust model, or live hostname boundary |
| Container/runtime hardening | Dockerfile/compose examples exist for local use | No non-root/read-only/runtime capability policy, image scanning gate, registry control, SBOM gate, or orchestration runtime policy |
| Process/service model | `ThreadingHTTPServer` started directly | No production WSGI/ASGI/server supervisor, restart policy, graceful drain, worker sizing, or resource quotas |
| Runtime env/secrets | Env-based config with fail-closed checks and redaction posture | No vault/KMS/HSM integration, rotation automation, secret lease lifecycle, or production injection policy |
| Request limits | JSON body size limit and rate limit baseline exist | No production timeout budget, concurrency cap, slow-client handling, upload policy, queue/backpressure model, or edge rate limit |
| Network exposure | Localhost default and demo endpoint public exposure guard | No ingress allowlist, egress policy, firewall model, trusted proxy model, or segmentation plan |
| Observability | Structured logging and correlation ID baseline | No external metrics, tracing, alerting, pager, SIEM/SOC, SLOs, dashboards, or retention integration |
| Backup/restore/DR | Synthetic local drills and plan scripts | No scheduled production backups, restore RTO/RPO evidence, failover test, offsite retention, or runtime restore procedure |
| PostgreSQL | Optional support and ephemeral validation history | No production topology, pooling validation, permission model, failover, PITR, or live production readiness |
| Release/rollback | Documentation baseline | No deployment ring, rollback automation, config freeze, artifact provenance, or emergency runtime recovery procedure |

## Implemented Hardening Summary

GL-220 adds:

1. This runtime/infrastructure hardening report.
2. A machine-readable GL-220 JSON artifact.
3. `scripts/ops/gl220_runtime_infrastructure_gate.py`, a local-only dry-run/plan
   gate that checks required artifacts, branch scope, conservative claims, and
   redacted unsafe environment patterns.
4. Focused regression tests for the GL-220 docs, JSON artifact, gate script, and
   forbidden-change boundaries.

No real deployment, cloud integration, TLS certificate/private key, external
hostname, monitoring rollout, production secret handling, migration, dependency,
GitHub workflow, snapshot publish script, package metadata, or backend runtime
rewrite is added.

## TLS / HTTPS / Reverse Proxy Posture

GrantLayer does not terminate TLS itself and does not ship a production reverse
proxy config. Current documentation and OpenAPI remain local HTTP for developer
preview. A future production gate must define TLS termination, certificate
lifecycle, HSTS policy, secure cookie/header policy if applicable, proxy header
trust, client IP handling, request buffering, and host allowlisting. GL-220 does
not add certificates, private keys, external hostnames, or a live domain config.

## Container/Runtime Hardening Posture

Existing Docker artifacts are local/developer conveniences, not production
container hardening. A production container posture must define non-root user,
read-only filesystem, dropped capabilities, minimal writable paths, runtime
seccomp/AppArmor or equivalent policy, image provenance, vulnerability scanning,
registry access control, image signing or verification, and update cadence.
GL-220 does not add registry credentials, orchestration files, or production
container deployment config.

## Process Supervisor/Service Model Posture

The current service starts a Python `ThreadingHTTPServer` directly. That remains
a Developer Preview service model. Production would require a process manager,
restart and health policy, graceful shutdown and drain behavior, worker sizing,
CPU/memory limits, file descriptor limits, backlog handling, log forwarding,
and clear ownership for operational runbooks. GL-220 documents the gap only.

## Runtime Environment and Secret Handling Posture

Configuration is environment-variable based. Existing fail-closed checks reject
unsafe production-like admin/operator settings and unsupported external
identity configuration. Runtime logs and gates avoid raw tokens, token hashes,
authorization headers, DSNs, private keys, and credentials. Production still
requires a managed secret store, rotation automation, break-glass handling,
least-privilege secret injection, audit of access to secrets, and emergency
revocation.

## Production Config Fail-Closed Posture

Production-like modes already fail closed for missing admin-token enforcement,
missing admin token, placeholder/weak tokens, disabled challenge enforcement,
enabled demo endpoints, unsafe bootstrap operator tokens, and unsupported
OAuth/OIDC/JWT provider configuration. Remaining runtime fail-closed gaps
include TLS/proxy assumptions, trusted ingress, external monitoring failure
modes, production database topology checks, backup/restore readiness checks,
and secret-store lifecycle checks.

## Request Size / Timeout / Concurrency Posture

The HTTP handler enforces a one-megabyte JSON body limit and rejects malformed
or empty JSON. In-process rate limits exist for auth and API categories. There
is no production timeout budget, slow-client mitigation, edge request cap,
per-route concurrency limit, worker pool sizing, request queue/backpressure
model, or external load-balancer timeout alignment. These remain production
runtime blockers.

## Rate-Limit/Runtime Abuse Posture

GL-208 established a runtime abuse and rate-limit baseline with safe logging and
correlation signals. That baseline is useful for controlled preview, but it is
not production-grade abuse protection. Production still needs edge enforcement,
tenant-aware quotas, alerting on abuse signals, lockout and recovery policy,
runbook ownership, and validation under realistic traffic patterns.

## Network Exposure / Ingress Posture

The default host is local loopback and demo endpoint public exposure is guarded.
There is no production ingress topology, firewall/allowlist model, public
reverse proxy, trusted proxy header policy, egress control, private network
segmentation, or administrative network boundary. Public website publish and
public snapshot/export remain separate gates and are not performed by GL-220.

## Health/Readiness Runtime Posture

`/health` and `/readiness` are public and return safe minimal status without raw
environment values, secrets, tokens, or tenant data. Readiness can report
runtime configuration invalidity. Production still needs deployment-specific
readiness semantics, database dependency checks, dependency timeout budgets,
load balancer integration, probe authentication/segmentation decisions, and
alert routing. GL-220 does not change endpoint behavior.

## Logging/Correlation/Observability Posture

Structured logging, safe redaction helpers, normalized correlation IDs, and
`X-Correlation-ID` response propagation exist. Logs normalize dynamic path
segments and avoid sensitive payload material. Production still requires
external log aggregation, metrics, tracing, dashboard ownership, alert
thresholds, retention policy, SIEM/SOC integration, and incident handoff.

## External Monitoring/Alerting Requirements

Before any production infrastructure readiness claim, GrantLayer needs an
external observability stack with:

- availability, latency, error-rate, auth-denial, rate-limit, database,
  migration, backup, restore, and audit-chain signals;
- alert thresholds and escalation ownership;
- dashboard and runbook links;
- synthetic checks using synthetic/demo data only until real-data gates change;
- log retention and access control;
- secret-safe redaction verification;
- incident correlation across API, database, backup, and identity layers.

GL-220 does not add live monitoring, pager, SIEM, or analytics integration.

## Backup/Restore/DR Runtime Integration Posture

GL-205 and GL-216 provide synthetic drills and planning artifacts. Runtime
production readiness still requires scheduled backups, restore drills with
documented RTO/RPO, failover testing, offsite/encrypted retention, PITR or an
approved alternative for PostgreSQL, backup access control, recovery ownership,
and audit-chain verification after restore. GL-220 does not add backup
automation or DR infrastructure.

## PostgreSQL Runtime Connectivity Posture

PostgreSQL remains optional and not production-ready. Ephemeral validation
history does not establish production topology. Production requires connection
pooling under load, least-privilege roles, TLS to database where applicable,
schema migration rollout and rollback procedure, failover behavior, PITR,
observability, and operational ownership. Live PostgreSQL production readiness
remains NO-GO.

## Identity/Access Runtime Dependency Posture

GL-219 improved fail-closed handling for unsupported external identity
configuration and documented OAuth/OIDC/JWT requirements. The runtime still uses
the controlled-preview bearer-token model. Production identity requires a real
validated provider path, named admins, SSO/MFA or approved equivalent, lifecycle
automation, emergency access governance, and safe integration with tenant and
workspace mapping. GL-220 does not add an identity provider.

## Tenant/Workspace Runtime Enforcement Posture

GL-215 hardened tenant-visible execution-derived routes and cross-tenant denial
on the demo tamper path. Tenant context is server-derived. Workspace enforcement
remains deferred, database row-level security is not implemented, tenant
provisioning/lifecycle is incomplete, and adversarial multi-tenant production
validation is not complete. Tenant/workspace isolation is not
production-complete.

## Release/Rollback/Runtime Recovery Posture

Current release/rollback posture is documentation-level only. Production needs
versioned deploy artifacts, config freeze/review, rollback criteria, migration
rollback and forward-fix policy, emergency restart and drain procedures, runtime
state recovery, backup restore decision authority, and post-incident review
requirements. GL-220 does not create release metadata, branches, tags, or
deployment automation.

## Optional Runtime Gate Script Summary

`scripts/ops/gl220_runtime_infrastructure_gate.py` was added as a local-only
dry-run/plan helper. It:

- verifies expected docs, artifacts, source inputs, and scripts exist;
- checks branch scope for forbidden deployment/cloud/package/public-export/TLS
  key paths;
- checks GL-220 docs/script for obvious secret-like values and overclaims;
- inspects selected environment variable names/values for unsafe production-like
  DSN, token, private-key, cloud, or credential patterns;
- redacts matched values before output;
- states that it is not production infrastructure certification.

It does not contact external services, require real credentials, run destructive
commands, create deployment artifacts, create cloud resources, write TLS
certificates/private keys, or modify GitHub workflows.

## Production-Readiness Impact

GL-220 materially reduces runtime/infrastructure ambiguity by turning the
remaining gaps into documented, testable blockers and by adding a local gate.
It does not make GrantLayer production-ready. Production SaaS remains NO-GO.
Real customer/private grant/institutional data remains NO-GO. Compliance
certification remains NO-GO. Live PostgreSQL production readiness remains
NO-GO.

## Controlled-Preview Impact

Controlled preview remains allowed only with strict boundaries and synthetic/demo
data. GL-220 improves reviewer clarity around deployment, runtime, TLS,
network, observability, secrets, and backup expectations. It does not expand the
data boundary, deployment boundary, public publish boundary, or SDK/package
boundary.

## Remaining Runtime/Infrastructure Blockers

- No real TLS termination, certificate lifecycle, HSTS, reverse proxy trust
  boundary, or live external hostname model.
- No production container hardening policy, image provenance gate, registry
  control, or orchestration baseline.
- No production process supervisor/service model, graceful drain, worker sizing,
  restart policy, or resource quota model.
- No production network ingress/egress topology, firewall/allowlist model, or
  trusted proxy policy.
- No production timeout, concurrency, backpressure, or edge rate-limit model.
- No external metrics, tracing, log aggregation, alerting, pager, SIEM/SOC, or
  SLO ownership.
- No production secret-store/KMS/HSM integration or rotation automation.
- No scheduled backup automation, restore RTO/RPO evidence, failover, PITR, or
  DR runtime integration.
- No production PostgreSQL topology, pooling, least-privilege runtime role, or
  live production validation.
- No production identity provider, SSO/MFA, named admin lifecycle, or external
  JWT/OIDC validator.
- Workspace enforcement, database RLS, tenant lifecycle, and adversarial
  multi-tenant validation remain incomplete.

## Risk Register

| Risk | Severity | Status | Mitigation |
|---|---|---|---|
| TLS/reverse proxy assumptions are undefined | P0 | Open | Future TLS/proxy hardening gate |
| Runtime container/process model is not production-grade | P0 | Open | Future service model and container hardening gate |
| Network exposure could be misconfigured outside local preview | P0 | Open | Keep public deployment NO-GO; require ingress design before production |
| External observability and alerting are absent | P0 | Open | Future monitoring/alerting implementation gate |
| Backup/restore/DR is not automated or production-tested | P0 | Open | Future backup/DR runtime execution gate |
| Secrets lifecycle remains manual/environment-based | P0 | Open | Future managed secrets and rotation gate |
| PostgreSQL runtime topology is not production-ready | P0 | Open | Future PostgreSQL production operations gate |
| Identity and tenant/workspace blockers affect runtime safety | P0 | Open | Preserve GL-219/GL-215 blockers and require follow-up gates |

## Decision

`production_runtime_infrastructure_hardening_pack_ready_for_merge_with_blockers`

## Decision Rationale

GL-220 is ready for internal merge because it adds conservative
runtime/infrastructure documentation, a JSON artifact, a local dry-run/plan gate,
and focused tests without expanding deployment scope or weakening prior
boundaries. It does not resolve production infrastructure readiness. The
remaining blockers keep Production SaaS, real data, compliance certification,
official SDK/package, and live PostgreSQL production readiness at NO-GO.

## Safety Confirmations

- GL-220 is runtime/infrastructure hardening, not production SaaS readiness.
- GrantLayer remains Developer Preview / Controlled Preview with strict
  boundaries.
- Production SaaS remains NO-GO unless a later Go/No-Go gate changes that.
- Real customer data, private grant data, and institutional data remain NO-GO.
- Official SDK/package remains NO-GO.
- Compliance certification remains NO-GO.
- Live PostgreSQL production readiness remains NO-GO.
- No real cloud, deployment, TLS certificate, external hostname, monitoring, or production secret rollout is performed by GL-220.
- No exploit details are included.
- No real secrets are included.
- No real customer/private data is used.
- Security-sensitive reports route to GitHub Security Advisories.
- No GitHub workflow changes are made.
- No snapshot publish script changes are made.
- No public GitHub push, public publish, or visibility change is performed.
- No migrations, DB/schema, dependency, package metadata, deployment, cloud,
  Kubernetes, Terraform, Helm, TLS certificate, or TLS private-key files are
  added.
- GL-216 operations, GL-218 public/export safety, and GL-219 identity/access
  behavior are preserved.
- Unrelated website-design/import files are excluded.

## Recommended Next Issues

- GL-220 Merge if ready.
- GL-221 Workspace Enforcement & Final Go/No-Go v6.
- Future TLS/reverse proxy and network ingress hardening gate.
- Future container/process supervisor and runtime resource limit gate.
- Future external observability/alerting and incident integration gate.
- Future backup/restore/DR runtime execution gate.
