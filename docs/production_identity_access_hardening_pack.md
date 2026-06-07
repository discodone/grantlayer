# GL-219 - Production Identity & Access Hardening Pack

**Issue ID:** GL-219
**Title:** Production Identity & Access Hardening Pack
**Branch:** `gl-219-production-identity-access-hardening-pack`
**Status:** Internal / Developer Preview

GL-219 is identity and access hardening. It is not a production readiness
declaration and does not add a production identity provider.

GrantLayer remains Developer Preview / Controlled Preview with strict
boundaries. Controlled external technical review remains allowed only with
strict boundaries. Controlled preview remains synthetic/demo data only.
Production SaaS remains NO-GO. Real customer data, private grant data, and
institutional data remain NO-GO. Official SDK/package remains NO-GO. Live
PostgreSQL production readiness remains NO-GO. Compliance certification remains
NO-GO. GDPR, SOC2, ISO, and enterprise readiness are not claimed.
Real customer data, private grant data, and institutional data remain NO-GO.
Compliance certification remains NO-GO.

Security-sensitive reports route to GitHub Security Advisories. No exploit
details are included. No real secrets are included. No real customer/private
data is used.
No exploit details are included.
No real secrets are included.
No real customer/private data is used.

Unrelated website-design/import files were excluded from GL-219. No
`website-design/` content or similarly named website-design import/report files
are included in this change.

---

## Context

GL-214 constrained operator roles and added durable operator lifecycle audit
events. GL-215 tightened tenant-visible execution routes. GL-216 documented
operations blockers and added a local dry-run gate. GL-217 preserved the
production no-go decision. GL-218 added export safety boundaries without
creating a public export.

GL-219 reduces the identity/access blocker by making the current model, missing
production IAM controls, OAuth/OIDC/JWT requirements, and fail-closed behavior
explicit and locally checkable. It does not replace the current auth system.

## Scope

- Current admin/operator/auth model assessment.
- Remaining production identity and access gaps.
- Safe local fail-closed checks for unsupported external identity settings.
- OAuth/OIDC/JWT validation posture required before any production use.
- Issuer, audience, expiry, signature, and key-rotation expectations.
- Static admin and operator token behavior in Developer Preview / Controlled
  Preview.
- Local dry-run identity/access gate script.
- Documentation, JSON artifact, and focused regression tests.

## Non-Goals

GL-219 does not:

- Claim Production SaaS readiness.
- Claim real customer/private grant/institutional data readiness.
- Add a real external identity provider.
- Add OAuth, OIDC, SAML, SSO, MFA, browser login, or user-account UI.
- Add a complete enterprise IAM system or broad RBAC/policy rewrite.
- Add third-party dependencies, migrations, deployment config, cloud config, or
  external hostnames.
- Publish packages or add package metadata.
- Create public snapshots, exports, release branches, release tags, or public
  GitHub pushes.
- Change GitHub workflows, snapshot publish scripts, or repository visibility.
- Log raw tokens, token hashes, authorization headers, DSNs, private keys, or
  credentials.
- Weaken GL-214, GL-215, GL-216, GL-217, or GL-218 boundaries.

## Input Sources Reviewed

| Source | Reviewed |
|---|---|
| docs/production_go_no_go_v5.md | Yes |
| docs/examples/gl217/production_go_no_go_v5.json | Yes |
| docs/production_iam_operator_control_completion.md | Yes |
| docs/examples/gl214/production_iam_operator_control_completion.json | Yes |
| docs/production_auth_secrets_config_hardening.md | Yes |
| docs/examples/gl201/production_auth_secrets_config_hardening.json | Yes |
| docs/admin_operator_tenant_control_plane.md | Yes |
| docs/examples/gl206/admin_operator_tenant_control_plane.json | Yes |
| docs/production_operations_hardening_pack.md | Yes |
| docs/examples/gl216/production_operations_hardening_pack.json | Yes |
| docs/tenant_workspace_production_guarantee.md | Yes |
| docs/examples/gl215/tenant_workspace_production_guarantee.json | Yes |
| docs/public_external_review_export_safety_pack.md | Yes |
| docs/examples/gl218/public_external_review_export_safety_pack.json | Yes |
| docs/runtime_abuse_incident_hardening.md | Yes |
| docs/examples/gl208/runtime_abuse_incident_hardening.json | Yes |
| docs/data_governance_audit_operations.md | Yes |
| docs/examples/gl209/data_governance_audit_operations.json | Yes |
| docs/openapi.yaml | Yes |
| README.md | Yes |
| SECURITY.md | Yes |
| AGENTS.md | Yes |
| llms.txt | Yes |
| llms-full.txt | Yes |
| backend/src/auth.py | Yes |
| backend/src/config.py | Yes |
| backend/src/operators.py | Yes |
| backend/src/server.py | Yes |
| backend/src/audit_log.py | Yes |
| backend/src/db.py | Yes |
| backend/src/models.py | Yes |
| backend/tests/ | Yes |
| scripts/ops/gl216_production_operations_gate.py | Yes |
| scripts/ops/gl218_public_export_safety_scan.py | Yes |
| scripts/verify-first-output.sh | Yes |
| examples/grant_lifecycle_evidence_bundle.py | Yes |

## Current Admin / Operator / Auth Model

Admin authentication uses `GRANTLAYER_ADMIN_TOKEN` as a Bearer token with
constant-time comparison. Admin-only operator management routes call the admin
guard. In legacy admin-token mode, tenant context is bound server-side to
`demo`. Production-like startup already rejects missing enforcement, missing
admin token, unsafe placeholder tokens, disabled challenge enforcement, enabled
demo endpoints, and unsafe bootstrap operator tokens.

Operator authentication uses bearer tokens stored as PBKDF2-HMAC-SHA256 hashes.
A deterministic SHA-256 lookup hash narrows candidate rows before PBKDF2
verification. Revoked or inactive rows are excluded. Expired tokens fail closed.
Operator tenant context is loaded from the stored operator row and cannot be
overridden by request headers. Operator roles are constrained to
`owner`, `grant_admin`, and `auditor` for admin-created operators.

Health and readiness routes remain public and do not include tenant data.
Business routes use the existing admin/operator guards and server-derived tenant
context. The current model is a controlled-preview bearer-token baseline, not a
production identity-management system.

## Identity / Access Gap Assessment

| Area | Current state | Remaining gap |
|---|---|---|
| Admin identity | Static admin bearer token with constant-time check | Single shared secret, no named admin identity, no SSO, no MFA, no dual control |
| Operator identity | Hashed bearer tokens, active/expiry checks, tenant binding | No provider-backed lifecycle, automated deprovisioning, or rotation workflow |
| External identity | Not implemented | No OAuth/OIDC/JWT validator, metadata handling, or provider trust model |
| JWT claims | Not accepted as auth | No issuer/audience/expiry/signature/key validation |
| Tenant mapping | Server-derived from operator row | No trusted external claim-to-tenant mapping |
| Workspace mapping | Reserved nullable field | Workspace enforcement remains deferred |
| Access governance | owner/grant_admin/auditor route vocabulary | No full production RBAC/policy administration |
| Emergency access | Static token and manual operator controls | No break-glass vaulting, dual approval, or access review workflow |
| Audit/observability | Durable audit-chain events for operator create/revoke | No production SIEM/SOC integration or alert ownership |
| Real data boundary | Synthetic/demo only | Real customer/private grant/institutional data remains blocked |

## Implemented Hardening Summary

GL-219 adds:

1. `backend/src/identity_access.py`, a stdlib-only posture helper that documents
   required JWT/OIDC validation controls and returns safe machine-readable
   identity/access status.
2. A `config.startup_errors()` hook that fails closed in production-like modes
   when unsupported OAuth/OIDC/JWT enablement flags or issuer/audience/JWKS/JWT
   configuration are present before a real validator exists.
3. `scripts/ops/gl219_identity_access_gate.py`, a local-only dry-run/plan gate
   that checks required artifacts and reports identity blockers without network
   calls, raw tokens, credentials, or production certification.
4. This report, a JSON artifact, and focused tests.

No external provider, dependency, migration, schema change, workflow change,
public export, public push, deployment config, package metadata, or official SDK
change is added.

## OAuth / OIDC / JWT Validation Posture

Before any future production gate may accept OAuth/OIDC/JWT bearer tokens, a
real validator must provide all of the following:

- Signature validation before claims are trusted.
- Explicit issuer allowlist with exact issuer match.
- Explicit audience allowlist with exact audience match.
- Expiration, not-before, and issued-at validation with bounded clock skew.
- Algorithm allowlist that rejects `none` and unexpected algorithms.
- JWKS or key material selection by key id, with unknown keys denied.
- Key rotation and retired-key handling with a documented overlap window.
- Tenant/workspace mapping from trusted claims only.
- Revocation or deprovisioning lifecycle for operators and admin access.
- Safe logging that omits raw tokens, token hashes, authorization headers, and
  signing keys.
- Provider outage and metadata-fetch failures deny protected access.

GL-219 does not implement these controls. It represents them as requirements and
blocks misleading production-like external identity configuration until a later
approved identity-provider gate exists.

## Issuer / Audience / Expiry / Key Rotation Expectations

Issuer and audience must be exact-match allowlists, not substring checks or
unbounded configuration. Expiration, not-before, issued-at, and clock-skew rules
must be enforced before tenant or role claims are used. Key selection must use a
trusted key id and must deny missing, unknown, retired, or algorithm-mismatched
keys. Key rotation must define overlap, cache invalidation, emergency retirement,
and provider outage behavior.

These expectations are represented in `JWT_VALIDATION_REQUIREMENTS` and in the
GL-219 gate output. They are not represented as live provider config.

## Static Admin / Operator Token Safety

Static admin token behavior remains acceptable only for Developer Preview and
strict Controlled Preview with synthetic/demo data. Production-like startup
keeps the GL-201 fail-closed checks for missing, placeholder, or short admin and
bootstrap tokens. Admin route failures return safe reason codes and do not echo
token values.

Operator tokens remain hashed, tenant-bound, and one-time visible on creation.
List/read/revoke paths do not expose raw tokens, token hashes, lookup hashes,
authorization headers, DSNs, private keys, or credentials. Revoked, inactive,
expired, malformed, or unknown tokens fail closed.

## Fail-Closed Behavior

| Scenario | Behavior |
|---|---|
| Missing production-like admin token | Startup error |
| Placeholder or short production-like admin token | Startup error |
| Unsafe bootstrap operator token in production-like mode | Startup error |
| Unsupported OAuth/OIDC/JWT enablement flag in production-like mode | Startup error |
| Issuer/audience/JWKS/JWT config present without validator in production-like mode | Startup error |
| Missing admin auth on admin route | Denied with safe response |
| Invalid admin auth on admin route | Denied with safe response |
| Operator token on admin route | Denied |
| Revoked/inactive/expired operator token | Denied |
| Unknown external identity token | Not accepted by any external identity path |

Startup and gate outputs include variable names and reason codes only. They do
not include raw values.

## Production-Readiness Impact

GL-219 materially reduces the identity/access blocker by converting a major
implicit gap into explicit fail-closed startup behavior and local evidence. It
does not complete production identity and access management. Production SaaS,
real customer data, private grant/institutional data, compliance certification,
official SDK/package, and live PostgreSQL production readiness remain NO-GO.

## Controlled-Preview Impact

Controlled Preview remains synthetic/demo data only. GL-219 improves local
misconfiguration safety and review clarity without expanding allowed data,
publish, deployment, or identity-provider scope.

## Remaining Identity / Access Blockers

- Production OAuth/OIDC/JWT validator is not implemented.
- Static admin token remains a production blocker.
- SSO, MFA, named admin identities, and account lifecycle are absent.
- Dual-control break-glass, access review, and emergency governance are absent.
- Automated operator deprovisioning and rotation workflows are absent.
- Workspace enforcement, database row-level security, and tenant lifecycle
  remain blockers.
- Production monitoring, alerting, SIEM/SOC, incident rota, and access anomaly
  response remain incomplete.
- Real customer/private grant/institutional data remains blocked.

## Risk Register

| ID | Risk | Severity | Status |
|---|---|---|---|
| GL219-R1 | Single static admin token remains | P0 | Open |
| GL219-R2 | External identity tokens could be misconfigured before validator exists | P0 | Reduced by fail-closed startup checks |
| GL219-R3 | JWT issuer/audience/expiry/key rotation requirements are not implemented | P0 | Open |
| GL219-R4 | Operator lifecycle automation remains manual | P1 | Open |
| GL219-R5 | Workspace and tenant lifecycle remain incomplete | P0 | Open |

## Decision

`ready_for_internal_review_with_blockers`

## Decision Rationale

GL-219 adds narrow, reviewable hardening and evidence for production identity
and access gaps while preserving the current auth system and all prior safety
boundaries. The remaining production IAM blocker is reduced but not closed.

## Safety Confirmations

- Developer Preview / Controlled Preview with strict boundaries preserved.
- Controlled preview remains synthetic/demo data only.
- Production SaaS remains NO-GO.
- Real customer/private grant/institutional data remains NO-GO.
- Official SDK/package remains NO-GO.
- Live PostgreSQL production readiness remains NO-GO.
- Compliance certification, GDPR, SOC2, ISO, and enterprise readiness are not
  claimed.
- No external identity provider is added.
- No OAuth/OIDC/SAML/SSO/MFA/user-account UI is added.
- No third-party dependency, migration, deployment config, workflow change,
  public export, public push, package metadata, or SDK packaging change is
  added.
- No raw tokens, token hashes, authorization headers, DSNs, private keys, or
  credentials are included in docs, logs, audit events, or test fixtures.
- Unrelated website-design/import files are excluded.

## Recommended Next Issues

- Dedicated production identity-provider design gate for OAuth/OIDC/JWT
  validation, without live vendor configuration.
- Operator/admin lifecycle and rotation workflow hardening.
- Workspace enforcement, tenant lifecycle, and RLS hardening.
- Production access governance, break-glass, alerting, and incident ownership
  gate.
