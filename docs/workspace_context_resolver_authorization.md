# GL-225/226: Workspace Context Resolver + Authorization Enforcement

## Status

IMPLEMENTED — local/demo quality. Not production SaaS. No real customer data.

## Overview

GL-225 introduces a server-derived workspace context resolver that securely determines
which workspace a request operates in. GL-226 adds cross-workspace authorization
enforcement for resource lookups and mutations.

Both functions live in `backend/src/auth.py`. No schema migrations are required
(they rely on the workspace tables from GL-224 migration 0011).

---

## Workspace Context Resolver (`resolve_workspace_context`)

### Contract

```python
def resolve_workspace_context(
    auth_payload: dict,
    client_workspace_id: str | None = None,
) -> tuple[str | None, int, dict]:
    ...
```

Returns `(workspace_id, http_status, context_dict)`.
- On success: `http_status == 200`, `workspace_id` is the verified workspace.
- On failure: `workspace_id is None`, `http_status in {400, 403}`, `context_dict` is an error payload.

### Resolution Modes

| Mode | Trigger | workspace_id Source |
|---|---|---|
| `legacy_demo` | No `operatorId` in payload | Fixed: `"default"` |
| `single_membership` | Operator has exactly one active membership, no `client_workspace_id` | Database membership |
| `membership_verified` | Operator supplies `client_workspace_id`, has membership | Client-supplied, verified |
| `cross_workspace_role` | `owner`/`grant_admin_global` + `client_workspace_id` | Client-supplied, tenant-verified |
| `cross_workspace_role_demo_fallback` | Cross-workspace role, demo tenant, no `client_workspace_id` | Fixed: `"default"` |

### Security Properties

- **No trust on client-supplied `workspace_id`** without database membership verification.
- **Fail-closed**: operators with no active memberships receive `403 no_workspace_membership`.
- **Tenant boundary enforced**: a `workspace_id` from another tenant is returned as `403 workspace_not_found`.
- **Inactive workspace rejected**: `403 workspace_inactive`.
- **Ambiguous multi-membership**: `400 workspace_id_required` when operator has multiple memberships and no `workspace_id` supplied.

### Error Codes

| Code | HTTP | Description |
|---|---|---|
| `no_workspace_membership` | 403 | Operator has no active memberships |
| `workspace_access_denied` | 403 | Operator has no membership in requested workspace |
| `workspace_not_found` | 403 | Workspace does not exist or belongs to another tenant |
| `workspace_inactive` | 403 | Workspace status is not `active` |
| `invalid_workspace_id` | 400 | Empty or blank `workspace_id` supplied |
| `workspace_id_required` | 400 | Multiple memberships or cross-workspace role without explicit target |

### Demo/Synthetic Compatibility

When `ENABLE_OPERATOR_MODEL` is false or the auth payload has no `operatorId`, the
resolver returns the canonical demo workspace (`id="default"`, `tenant_id="demo"`).
This is fully backward-compatible with all pre-GL-225 tests and scenarios.

---

## Authorization Enforcement (`check_workspace_resource_access`)

### Contract

```python
def check_workspace_resource_access(
    resource_workspace_id: str | None,
    caller_workspace_id: str,
    caller_tenant_id: str,
    resource_tenant_id: str | None,
    cross_workspace_access: bool = False,
    require_mutation: bool = False,
    workspace_member_role: str | None = None,
) -> tuple[bool, int, dict]:
    ...
```

Returns `(allowed, http_status, payload)`.
- On success: `(True, 200, {})`.
- On denial: `(False, 403, error_dict)`.

### Rules (in evaluation order)

1. **Cross-tenant always denied** — `resource_tenant_id != caller_tenant_id` → `403 cross_tenant_access_denied`. No bypass.
2. **Unscoped resource allowed** — `resource_workspace_id is None` → allowed (backward compat).
3. **Same-workspace allowed** — `resource_workspace_id == caller_workspace_id` → allowed, subject to role check.
4. **Cross-workspace lookup denied** — different workspace, `cross_workspace_access=False` → `403 cross_workspace_lookup_denied`.
5. **Cross-workspace mutation denied** — different workspace, `cross_workspace_access=False`, mutation → `403 cross_workspace_mutation_denied`.
6. **Admin cross-workspace allowed** — `cross_workspace_access=True` → allowed, subject to role check.
7. **Readonly mutation denied** — `workspace_member_role="workspace_readonly"` + `require_mutation=True` → `403 workspace_role_insufficient`.

### Admin/Cross-Workspace Access

Operators with `role in {"owner", "grant_admin_global"}` receive `cross_workspace_access=True`
in their workspace context (set by `resolve_workspace_context`). This flag must be:

- **Explicitly set** in the returned context dict — never inferred silently.
- **Logged/audited** by callers before acting on cross-workspace resources.
- **Scoped to the caller's tenant** — the tenant boundary is still enforced.

### Role Hierarchy for Mutations

| Role | Lookup | Mutation |
|---|---|---|
| `workspace_owner` | Yes | Yes |
| `workspace_admin` | Yes | Yes |
| `workspace_member` | Yes | Yes |
| `workspace_readonly` | Yes | No |

---

## Usage Pattern

Callers that want to enforce workspace context on a request:

```python
# 1. Authenticate the operator
ok, auth_ctx = self._require_auth(["owner", "grant_admin"])
if not ok:
    return

# 2. Resolve workspace context (fail-closed)
client_ws_id = data.get("workspaceId") or qs.get("workspaceId")
ws_id, ws_status, ws_ctx = resolve_workspace_context(auth_ctx, client_workspace_id=client_ws_id)
if ws_id is None:
    self._send_json(ws_status, ws_ctx)
    return

# 3. When accessing a resource, enforce workspace boundary
allowed, status, err = check_workspace_resource_access(
    resource_workspace_id=resource.workspace_id,
    caller_workspace_id=ws_id,
    caller_tenant_id=auth_ctx.get("tenant_id", "demo"),
    resource_tenant_id=resource.tenant_id,
    cross_workspace_access=ws_ctx.get("cross_workspace_access", False),
    require_mutation=True,
    workspace_member_role=ws_ctx.get("workspace_member_role"),
)
if not allowed:
    self._send_json(status, err)
    return
```

Note: As of GL-225/226, existing server.py routes are not yet updated to call these
functions. The resolver and enforcer are introduced as auditable, tested primitives.
Route integration is a subsequent step.

---

## Files

| File | Role |
|---|---|
| `backend/src/auth.py` | Resolver + enforcer implementation (added to existing module) |
| `backend/tests/test_gl225_226_workspace_context_resolver_authorization.py` | 64-test suite |
| `docs/workspace_context_resolver_authorization.md` | This document |
| `docs/examples/gl225_226/workspace_context_resolver_authorization.json` | Machine-readable artifact |
| `scripts/ops/gl225_226_workspace_context_gate.py` | Local-only ops gate |

## Safety Confirmations

- No production SaaS claims.
- No real customer data.
- No real secrets or private key material.
- No network calls in implementation.
- No destructive database operations.
- No new migration files (uses GL-224 tables).
- Local/demo quality only.
