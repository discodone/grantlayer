"""RED tests — workspace-scoped grant matching on the /v1/demo-action path.

Current bug (audited): demo_action matches grants TENANT-wide —
``list_grants(tenant_id=effective_tenant)`` with no workspace filter — so an
operator resolved into workspace B can present and CONSUME a grant created in
workspace A of the same tenant. These tests assert the DESIRED behavior:
grant matching on the execution path must be scoped to the caller's resolved
workspace (``ws_ctx["workspace_id"]``).

Expected state today (RED):
  - test_cross_workspace_grant_is_not_matched  FAILS — the cross-workspace
    request is currently APPROVED (the bug, live).
  - test_same_workspace_grant_is_matched       PASSES — positive control
    proving the deny test fails on the scoping bug, not on a broken harness
    (auth, signing, challenge config all demonstrably work).

Setup mirrors test_gl084_demo_action_auth_hardening.py: temp SQLite DB via
GRANTLAYER_DB + module reloads + operator-model bearer auth. Workspace rows
are inserted directly (same tenant "demo", both active); the caller operator
has role "owner" (cross-workspace role), so X-Workspace-Id selects the
resolved workspace after tenant/active validation — no membership rows needed.
"""

import importlib
import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_OWNER_TOKEN = "ws-scope-owner-token-1234567890"

_ENV_KEYS = (
    "GRANTLAYER_DB",
    "GRANTLAYER_ENABLE_OPERATOR_MODEL",
    "GRANTLAYER_REQUIRE_CHALLENGE",
    "GRANTLAYER_ADMIN_TOKEN",
    "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
    "GRANTLAYER_BOOTSTRAP_OPERATOR_TOKEN",
)


class _WorkspaceScopingBase(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_env = {k: os.environ.get(k) for k in _ENV_KEYS}
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        os.environ.pop("GRANTLAYER_REQUIRE_CHALLENGE", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        self.db_mod = db_mod

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)

        import backend.src.auth.operators as ops_mod
        importlib.reload(ops_mod)
        self.ops_mod = ops_mod

        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)

        import backend.src.grants.grants as grants_mod
        importlib.reload(grants_mod)
        self.grants_mod = grants_mod

        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        self.models_mod = models_mod

        # Caller operator: role "owner" (cross-workspace) in tenant "demo".
        self._insert_operator("op-ws-scope", "scope-owner", "owner", _OWNER_TOKEN)

        # Two sibling workspaces in the SAME tenant.
        self.ws_a = str(uuid.uuid4())
        self.ws_b = str(uuid.uuid4())
        self._insert_workspace(self.ws_a, "ws-a")
        self._insert_workspace(self.ws_b, "ws-b")

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in self._orig_env.items():
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    def _insert_operator(self, op_id, name, role, token):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO operators (id, name, role, token_hash, active, created_at)
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
                (op_id, name, role, self.ops_mod.hash_token(token)),
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_workspace(self, ws_id, slug):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO workspaces
                       (id, tenant_id, name, slug, owner_id, status,
                        created_at, updated_at)
                   VALUES (?, 'demo', ?, ?, 'op-ws-scope', 'active',
                           '2026-07-17T00:00:00Z', '2026-07-17T00:00:00Z')""",
                (ws_id, slug, slug),
            )
            conn.commit()
        finally:
            conn.close()

    def _create_signed_grant_in(self, workspace_id):
        """A signed, currently-valid grant living in *workspace_id*."""
        grant = self.models_mod.Grant(
            subject_id="agent-1",
            role="technician",
            action="modify-config",
            resource="server-1",
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2030-01-01T00:00:00Z",
            created_by="op-ws-scope",
            reason="workspace scoping test",
        )
        self.grants_mod.create_grant(
            grant, tenant_id="demo", workspace_id=workspace_id
        )
        return grant

    def _make_client(self):
        from fastapi.testclient import TestClient

        import backend.src.core.db as bk_db
        from backend.src.api.app import create_app

        bk_db.DB_PATH_OR_URL = self.tmp_db.name
        bk_db.DB_PATH = self.tmp_db.name
        os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        return TestClient(create_app(), raise_server_exceptions=False)

    def _post_demo_action(self, workspace_id):
        client = self._make_client()
        return client.post(
            "/v1/demo-action",
            json={
                "subjectId": "agent-1",
                "role": "technician",
                "action": "modify-config",
                "resource": "server-1",
            },
            headers={
                "Authorization": f"Bearer {_OWNER_TOKEN}",
                "X-Workspace-Id": workspace_id,
            },
        )

    def _grant_use_count(self, grant_id):
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT use_count FROM grants WHERE id = ?", (grant_id,)
            ).fetchone()
            return row["use_count"] if row is not None else None
        finally:
            conn.close()

    def _executions_referencing(self, grant_id):
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM grant_executions WHERE grant_id = ?",
                (grant_id,),
            ).fetchone()
            return row["n"]
        finally:
            conn.close()


class TestDemoActionWorkspaceScoping(_WorkspaceScopingBase):
    def test_cross_workspace_grant_is_not_matched(self):
        """A grant from workspace A must NOT authorize a request resolved into
        workspace B — matching must be scoped to the caller's workspace."""
        grant = self._create_signed_grant_in(self.ws_a)

        resp = self._post_demo_action(self.ws_b)
        body = resp.json()

        self.assertFalse(
            body.get("approved"),
            "CROSS-WORKSPACE GRANT USE: request resolved into workspace B was "
            f"authorized by workspace A's grant. Full response: {body}",
        )
        self.assertEqual(resp.status_code, 403, f"expected 403, got {resp.status_code}")
        self.assertEqual(
            self._grant_use_count(grant.id),
            0,
            "workspace A's grant use_count was consumed by a workspace B request",
        )
        self.assertEqual(
            self._executions_referencing(grant.id),
            0,
            "a GrantExecution row references workspace A's grant for a "
            "workspace B request",
        )

    def test_same_workspace_grant_is_matched(self):
        """Positive control (must PASS today): the same request resolved into
        the grant's OWN workspace is approved and consumes a use — proving the
        harness (auth, signing, challenge config) works and the deny test
        fails on the scoping bug alone."""
        grant = self._create_signed_grant_in(self.ws_a)

        resp = self._post_demo_action(self.ws_a)
        body = resp.json()

        self.assertEqual(resp.status_code, 200, f"positive control broke: {body}")
        self.assertTrue(body.get("approved"), f"positive control broke: {body}")
        self.assertEqual(body.get("matchedGrantId"), grant.id)
        self.assertEqual(self._grant_use_count(grant.id), 1)
        self.assertEqual(self._executions_referencing(grant.id), 1)


if __name__ == "__main__":
    unittest.main()
