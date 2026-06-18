package grantlayer

import rego.v1

# GrantLayer OPA Policy — main authorization rules.
# Evaluated by /v1/data/grantlayer/allow via the OPA HTTP API.

# Default: deny unless explicitly allowed.
default allow := false

# ── Grant approval: role-based ────────────────────────────────────────────────

# Owners and grant_admins can approve any grant action.
allow if {
    input.action in {"grant.approve", "grant.create", "grant.revoke"}
    input.subject.role in {"owner", "grant_admin"}
}

# Auditors can read grants but not create/approve/revoke.
allow if {
    input.action in {"grant.read", "audit.read"}
    input.subject.role in {"owner", "grant_admin", "auditor", "viewer"}
}

# ── Workspace access: workspace_id match ──────────────────────────────────────

# Users can access resources within their own workspace.
allow if {
    input.action in {"workspace.read", "workspace.member.list"}
    input.subject.workspace_id == input.resource.workspace_id
}

# Owners can access any workspace in their tenant.
allow if {
    input.action in {"workspace.read", "workspace.member.list"}
    input.subject.role in {"owner", "grant_admin"}
    input.subject.tenant_id == input.resource.tenant_id
}

# ── API key scope enforcement ─────────────────────────────────────────────────

# read_only API keys cannot mutate resources.
allow if {
    "read_only" in input.subject.scopes
    input.action in {"grant.read", "audit.read", "workspace.read"}
}

# read_write API keys can read and mutate.
allow if {
    "read_write" in input.subject.scopes
    input.action in {
        "grant.read", "grant.create", "grant.revoke",
        "audit.read",
        "workspace.read",
        "grant_request.create", "grant_request.read",
    }
}

# admin API keys have full access.
allow if {
    "admin" in input.subject.scopes
}
