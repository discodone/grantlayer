"""Tests for GL-260: workspace-level resource isolation.

Validates that grants, grant_requests, and grant_executions are scoped to
the workspace_id of the creating caller — callers in a different workspace
cannot read or mutate those resources.

Strategy:
- Two operators (op-A, op-B) each in their own workspace (ws-A, ws-B),
  same tenant.
- Resources created by op-A get workspace_id=ws-A.
- op-B (workspace_id=ws-B) cannot see or act on op-A's resources.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_FUTURE = "2099-01-01T00:00:00Z"
_PAST = "2000-01-01T00:00:00Z"
_TENANT = "tenant-gl260"
_WS_A = "ws-gl260-a"
_WS_B = "ws-gl260-b"
_OP_A = "op-gl260-a"
_OP_B = "op-gl260-b"
_JWT_SECRET = "gl260-test-jwt-secret-32chars-xyz"


def _setup_two_workspace_env(tmp_db_path: str):
    """Bootstrap a DB with two workspaces and their JWT-authenticated operators."""
    os.environ["GRANTLAYER_DB"] = tmp_db_path
    os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET

    import backend.src.core.db as db_mod
    importlib.reload(db_mod)
    db_mod.DB_PATH_OR_URL = tmp_db_path
    db_mod.DB_PATH = tmp_db_path
    db_mod.init_db()

    from backend.src.core.db import execute

    # Insert two workspaces (tenant_id is a bare string; no tenants table at runtime)
    _ts = "2025-01-01T00:00:00Z"
    for ws_id in (_WS_A, _WS_B):
        execute(
            "INSERT OR IGNORE INTO workspaces (id, tenant_id, name, slug, owner_id, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
            (ws_id, _TENANT, ws_id, ws_id, "system", _ts, _ts),
        )

    # Add each JWT operator as member of their workspace
    for op_id, ws_id in ((_OP_A, _WS_A), (_OP_B, _WS_B)):
        execute(
            "INSERT OR IGNORE INTO workspace_members (id, workspace_id, operator_id, role, status) VALUES (?, ?, ?, 'admin', 'active')",
            (f"mem-{op_id}", ws_id, op_id),
        )


def _make_jwt_token(op_id: str, role: str = "owner") -> str:
    """Create a signed JWT for the given operator in the test tenant."""
    from backend.src.api.auth_jwt import encode_token
    payload = {
        "sub": op_id,
        "tenant_id": _TENANT,
        "role": role,
        "iss": "grantlayer",
        "aud": "grantlayer-api",
    }
    return encode_token(payload, _JWT_SECRET, ttl_hours=1)


def _make_auth_header(op_id: str) -> str:
    return f"Bearer {_make_jwt_token(op_id)}"


class TestGL260WorkspaceIsolation(unittest.TestCase):
    """GL-260: workspace-scoped resource isolation tests."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_jwt = os.environ.get("GRANTLAYER_JWT_SECRET")
        self._orig_op_model = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")

        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

        _setup_two_workspace_env(self.tmp.name)

        # Reload config so module-level ENABLE_OPERATOR_MODEL reflects the env var
        # set above — guards against contamination from tests that set it to false.
        for mod_name in list(sys.modules.keys()):
            if "backend.src.core.config" in mod_name:
                importlib.reload(sys.modules[mod_name])

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=False)

        self._auth_a = _make_auth_header(_OP_A)
        self._auth_b = _make_auth_header(_OP_B)

    def tearDown(self):
        os.unlink(self.tmp.name)
        for key, orig in (
            ("GRANTLAYER_DB", self._orig_db),
            ("GRANTLAYER_JWT_SECRET", self._orig_jwt),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", self._orig_op_model),
        ):
            if orig is not None:
                os.environ[key] = orig
            else:
                os.environ.pop(key, None)
        for mod_name in list(sys.modules.keys()):
            if "backend.src.core.config" in mod_name:
                importlib.reload(sys.modules[mod_name])

    # ── helpers ──────────────────────────────────────────────────────────────

    def _create_grant_as_a(self) -> str:
        """Create a grant in workspace A and return its ID."""
        resp = self.client.post(
            "/v1/grants",
            json={
                "subjectId": "agent-x",
                "role": "viewer",
                "action": "read",
                "resource": "doc/secret",
                "validFrom": _PAST,
                "validUntil": _FUTURE,
                "createdBy": _OP_A,
                "reason": "GL-260 workspace isolation test",
            },
            headers={"Authorization": self._auth_a, "X-Workspace-Id": _WS_A},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["id"]

    def _create_grant_request_as_a(self) -> str:
        """Create a grant request in workspace A and return its ID."""
        resp = self.client.post(
            "/v1/grant-requests",
            json={
                "subjectId": "agent-y",
                "role": "viewer",
                "action": "read",
                "resource": "doc/other",
                "validFrom": _PAST,
                "validUntil": _FUTURE,
                "reason": "GL-260 grant-request isolation test",
            },
            headers={"Authorization": self._auth_a, "X-Workspace-Id": _WS_A},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["id"]

    # ── grants: read isolation ────────────────────────────────────────────────

    def test_op_a_can_read_own_grant(self):
        grant_id = self._create_grant_as_a()
        resp = self.client.get(
            f"/v1/grants/{grant_id}",
            headers={"Authorization": self._auth_a, "X-Workspace-Id": _WS_A},
        )
        self.assertEqual(resp.status_code, 200)

    def test_op_b_cannot_read_grant_from_workspace_a(self):
        grant_id = self._create_grant_as_a()
        resp = self.client.get(
            f"/v1/grants/{grant_id}",
            headers={"Authorization": self._auth_b, "X-Workspace-Id": _WS_B},
        )
        self.assertEqual(resp.status_code, 404)

    def test_op_b_list_does_not_include_workspace_a_grants(self):
        self._create_grant_as_a()
        resp = self.client.get(
            "/v1/grants",
            headers={"Authorization": self._auth_b, "X-Workspace-Id": _WS_B},
        )
        self.assertEqual(resp.status_code, 200)
        grant_ids = [g["id"] for g in resp.json()["items"]]
        # Workspace B's list must be empty — the grant belongs to workspace A
        self.assertEqual(grant_ids, [])

    def test_op_a_list_includes_own_grant(self):
        grant_id = self._create_grant_as_a()
        resp = self.client.get(
            "/v1/grants",
            headers={"Authorization": self._auth_a, "X-Workspace-Id": _WS_A},
        )
        self.assertEqual(resp.status_code, 200)
        grant_ids = [g["id"] for g in resp.json()["items"]]
        self.assertIn(grant_id, grant_ids)

    # ── grant requests: read isolation ───────────────────────────────────────

    def test_op_b_cannot_read_grant_request_from_workspace_a(self):
        req_id = self._create_grant_request_as_a()
        resp = self.client.get(
            f"/v1/grant-requests/{req_id}",
            headers={"Authorization": self._auth_b, "X-Workspace-Id": _WS_B},
        )
        self.assertEqual(resp.status_code, 404)

    def test_op_b_list_does_not_include_workspace_a_grant_requests(self):
        self._create_grant_request_as_a()
        resp = self.client.get(
            "/v1/grant-requests",
            headers={"Authorization": self._auth_b, "X-Workspace-Id": _WS_B},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["items"], [])

    def test_op_a_list_includes_own_grant_request(self):
        req_id = self._create_grant_request_as_a()
        resp = self.client.get(
            "/v1/grant-requests",
            headers={"Authorization": self._auth_a, "X-Workspace-Id": _WS_A},
        )
        self.assertEqual(resp.status_code, 200)
        req_ids = [r["id"] for r in resp.json()["items"]]
        self.assertIn(req_id, req_ids)

    # ── cross-workspace mutation denied ──────────────────────────────────────

    def test_op_b_cannot_approve_workspace_a_grant_request(self):
        req_id = self._create_grant_request_as_a()
        resp = self.client.post(
            f"/v1/grant-requests/{req_id}/approve",
            headers={"Authorization": self._auth_b, "X-Workspace-Id": _WS_B},
        )
        # 404: op-B can't even see the request in workspace-B
        self.assertEqual(resp.status_code, 404)

    def test_op_b_cannot_deny_workspace_a_grant_request(self):
        req_id = self._create_grant_request_as_a()
        resp = self.client.post(
            f"/v1/grant-requests/{req_id}/deny",
            json={"reason": "cross-workspace denial attempt"},
            headers={"Authorization": self._auth_b, "X-Workspace-Id": _WS_B},
        )
        self.assertEqual(resp.status_code, 404)

    # ── legacy default workspace rows are isolated from explicit workspaces ───

    def _insert_legacy_grant_default_workspace(self) -> str:
        """Directly insert a grant in the legacy default workspace."""
        import uuid
        from backend.src.core.db import execute
        grant_id = f"g_legacy_{uuid.uuid4().hex[:8]}"
        ts = "2025-01-01T00:00:00Z"
        execute(
            """INSERT INTO grants
               (id, subject_id, role, action, resource, valid_from, valid_until,
                created_by, reason, revoked, created_at, max_uses, use_count,
                signature, signing_key_id, payload_hash, tenant_id, workspace_id)
               VALUES (?, 'legacy-agent', 'viewer', 'read', 'legacy-doc',
                       ?, ?, 'legacy-op', 'legacy row', 0, ?, NULL, 0,
                       NULL, NULL, NULL, ?, 'default')""",
            (grant_id, ts, "2099-01-01T00:00:00Z", ts, _TENANT),
        )
        return grant_id

    def test_legacy_null_workspace_grant_not_visible_to_workspace_a(self):
        """A grant in the default workspace must not bleed into workspace A."""
        grant_id = self._insert_legacy_grant_default_workspace()
        # List — must not appear in workspace A's list
        resp = self.client.get(
            "/v1/grants",
            headers={"Authorization": self._auth_a, "X-Workspace-Id": _WS_A},
        )
        self.assertEqual(resp.status_code, 200)
        ids = [g["id"] for g in resp.json()["items"]]
        self.assertNotIn(grant_id, ids, "Legacy default-workspace grant leaked into workspace A list")

    def test_legacy_null_workspace_grant_not_visible_to_workspace_b(self):
        """A grant in the default workspace must not bleed into workspace B."""
        grant_id = self._insert_legacy_grant_default_workspace()
        resp = self.client.get(
            "/v1/grants",
            headers={"Authorization": self._auth_b, "X-Workspace-Id": _WS_B},
        )
        self.assertEqual(resp.status_code, 200)
        ids = [g["id"] for g in resp.json()["items"]]
        self.assertNotIn(grant_id, ids, "Legacy default-workspace grant leaked into workspace B list")

    def test_legacy_null_workspace_grant_not_fetchable_by_id_from_workspace_a(self):
        """GET /grants/{id} with workspace filter must return 404 for default-workspace rows."""
        grant_id = self._insert_legacy_grant_default_workspace()
        resp = self.client.get(
            f"/v1/grants/{grant_id}",
            headers={"Authorization": self._auth_a, "X-Workspace-Id": _WS_A},
        )
        self.assertEqual(resp.status_code, 404)
