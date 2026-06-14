# GL-223 Workspace Identity / Membership / Ownership Implementation Plan

GL-223 is an implementation plan, not the implementation itself. GL-223 does not add migrations. GL-223 does not enable real customer data. GL-223 does not claim Production SaaS readiness.

## Current Tenant/Workspace State Summary

Tenant context is server-derived. Workspace context is being formalized through
the GL-224 through GL-231 implementation sequence.

## Current Workspace Trust Gaps

Remaining gaps include full workspace lifecycle policy, ownership transfer,
membership administration, rollout controls, and production go/no-go evidence.

## Workspace Identity Model

A workspace is a tenant-scoped operating context with a stable server-assigned
identifier, name, owner, status, created timestamp, and updated timestamp.

## Membership Model

Workspace membership binds an operator to a workspace with a role and active
status. Membership is verified server-side before workspace-scoped access.

## Ownership Model

Each workspace has an owner. Ownership transfer must be explicit, audited, and
must prevent orphaned workspaces.

## Role / Scope Model

Effective access is the intersection of tenant role, workspace membership role,
and route-level operation.

## Workspace Lifecycle Model

Lifecycle states cover creation, activation, member invitation, member removal,
ownership transfer, suspension, and deactivation.

## Admin/Operator Ownership Boundary

Admin/operator routes may manage tenant-level operator records. Workspace
ownership and membership decisions require workspace-aware checks and audit
events.

## Server-Derived Workspace Context Model

Workspace context is derived from authentication and verified membership. Request
bodies cannot override tenant_id or workspace_id.

## Unsafe Workspace Override Prevention Model

Client-supplied tenant or workspace fields are ignored for authorization.
Workspace selection is accepted only through verified server-side context.

## Cross-Workspace Lookup Denial Model

Cross-workspace lookups return not found semantics where appropriate to avoid
resource enumeration.

## Cross-Workspace Mutation Denial Model

Mutations require matching tenant and workspace context and fail closed when
membership or ownership checks are missing.

## Audit / Evidence / Provenance / Compliance Propagation Model

Audit, evidence, provenance, and compliance records must preserve tenant and
workspace context without exposing real secrets or private data.

## Database / Schema Plan

The implementation sequence defines workspace, membership, invite, ownership,
and resource propagation schema work. GL-223 does not add migrations.

## Migration / Backfill Plan

Backfill must be deterministic, audited, reversible where practical, and safe
for synthetic/demo records before any production-like claims are made.

## API / Server Plan

API handlers must resolve workspace context server-side and propagate it to
service and persistence calls.

## OpenAPI Impact Plan

OpenAPI updates must document workspace selection, error codes, and safety
boundaries once implementation is complete.

## Testing Strategy

Tests must cover membership resolution, cross-workspace lookup denial,
cross-workspace mutation denial, audit propagation, and legacy compatibility.

## Rollout Strategy

Rollout proceeds through staged implementation issues and a final go/no-go gate.

## Rollback Strategy

Rollback keeps existing audit integrity, preserves synthetic/demo flows, and
does not delete historical records.

## Compatibility with Demo / Synthetic Flows

Demo and synthetic flows remain supported. Real Customer Data remains NO-GO.
Private Grant / Institutional Data remains NO-GO.

## Proposed Implementation Issue Breakdown

GL-224 through GL-231 cover schema, resolver, API propagation, route enforcement,
audit/evidence propagation, migration validation, and go/no-go review.

## Risk Register

Risks include incomplete membership checks, ambiguous ownership, backfill errors,
audit context gaps, and premature production claims.

## Decision

Proceed with the staged implementation plan while keeping production-readiness
claims blocked.

## Safety Confirmations

Production SaaS remains NO-GO.
Real Customer Data remains NO-GO.
Private Grant / Institutional Data remains NO-GO.
Official SDK/Package remains NO-GO.
Compliance Certification remains NO-GO.
Live PostgreSQL Production Readiness remains NO-GO.
No exploit details are included.
No real secrets are included.
No real customer or private data is used.

## Recommended Next Issues

Start GL-224 for workspace schema and membership baseline, then continue the
planned workspace enforcement sequence.
