"""GL-352 — Audit event workspace attribution (RED phase).

Context / defect
----------------
``AuditEvent.workspace_id`` is currently ``Optional[str] = None`` and 24 of 26
write sites omit it, so nearly every audit event lands NULL-tagged. That blocks
per-workspace anchoring (GL-350) and is a real attribution/completeness defect.

Target end-state (what these tests pin down)
--------------------------------------------
1. ``workspace_id`` becomes a REQUIRED field (``workspace_id: str`` — no default)
   so mypy/dataclass construction enforces it at every construction site.
2. A ``SYSTEM_WORKSPACE`` sentinel exists for the genuinely workspace-less events
   (admin / gdpr), so those rows are tagged ``__system__`` instead of NULL.
3. Every real write path forwards the acting workspace onto the audit event.

These tests are written RED-first: they MUST fail now (attribution missing) and
pass once workspace_id is required + forwarded on all paths.
"""

from __future__ import annotations

import dataclasses
import importlib
import os
import tempfile
import unittest
import uuid

# The proposed sentinel value. Referenced as a literal here so the behavioral
# global-event tests fail on the ATTRIBUTION assertion (workspace_id is None,
# not the sentinel) rather than on an ImportError. The dedicated existence test
# (test_system_workspace_sentinel_exists) is what pins the real constant down.
_EXPECTED_SYSTEM_WORKSPACE = "__system__"

_TEST_SECRET = "gl352-test-hs256-secret-32chars!!"
_ISS = "grantlayer"
_AUD = "grantlayer-api"


# ══════════════════════════════════════════════════════════════════════════
# 1 + 2. Structural tests — field is required + sentinel exists (no DB)
# ══════════════════════════════════════════════════════════════════════════


class TestAuditEventFieldContract(unittest.TestCase):
    def test_audit_event_requires_workspace_id(self):
        """workspace_id must be a REQUIRED str field with no default value."""
        from backend.src.core.models import AuditEvent

        fields = {f.name: f for f in dataclasses.fields(AuditEvent)}
        self.assertIn("workspace_id", fields, "AuditEvent has no workspace_id field")
        ws = fields["workspace_id"]

        # No default and no default_factory → construction without workspace_id fails.
        self.assertIs(
            ws.default,
            dataclasses.MISSING,
            f"workspace_id must have NO default (found default={ws.default!r})",
        )
        self.assertIs(
            ws.default_factory,
            dataclasses.MISSING,
            "workspace_id must have NO default_factory",
        )

        # Type must be plain str, not Optional[str].
        self.assertNotIn(
            "Optional",
            str(ws.type),
            f"workspace_id must be typed str, not Optional (found {ws.type!r})",
        )
        self.assertNotIn(
            "None",
            str(ws.type),
            f"workspace_id must be typed str, not Optional (found {ws.type!r})",
        )

    def test_audit_event_construction_without_workspace_id_fails(self):
        """Constructing AuditEvent without workspace_id must raise TypeError."""
        from backend.src.core.models import AuditEvent

        with self.assertRaises(TypeError):
            AuditEvent(
                subject_id="s",
                role="operator",
                action="test_action",
                resource="res/1",
                approved=True,
                reason="no workspace supplied",
            )


class TestSystemWorkspaceSentinel(unittest.TestCase):
    def test_system_workspace_sentinel_exists(self):
        """A SYSTEM_WORKSPACE sentinel string constant must exist and be uuid-safe."""
        import backend.src.core.models as models

        self.assertTrue(
            hasattr(models, "SYSTEM_WORKSPACE"),
            "core.models must define a SYSTEM_WORKSPACE sentinel constant",
        )
        sentinel = models.SYSTEM_WORKSPACE
        self.assertIsInstance(sentinel, str)
        self.assertEqual(sentinel, _EXPECTED_SYSTEM_WORKSPACE)

        # Must never collide with a real workspace id (workspace ids are uuids).
        with self.assertRaises(ValueError):
            uuid.UUID(sentinel)


# ══════════════════════════════════════════════════════════════════════════
# Shared base for behavioral write-path tests (real temp DB)
# ══════════════════════════════════════════════════════════════════════════


class _WritePathBase(unittest.TestCase):
    """Isolated temp SQLite DB + JWT auth, driving the REAL write paths."""

    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

        self._env_backup = {}
        for key, val in [
            ("GRANTLAYER_DB", self.tmp_db.name),
            ("GRANTLAYER_ENABLE_OPERATOR_MODEL", "true"),
            ("GRANTLAYER_JWT_SECRET", _TEST_SECRET),
            ("GRANTLAYER_JWT_ALGORITHM", "HS256"),
            ("GRANTLAYER_JWT_MODE", "hs256"),
        ]:
            self._env_backup[key] = os.environ.get(key)
            os.environ[key] = val
        # OPA must be unconfigured so require_mutation_authz allows the write.
        self._env_backup["GRANTLAYER_OPA_URL"] = os.environ.get("GRANTLAYER_OPA_URL")
        os.environ.pop("GRANTLAYER_OPA_URL", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.DB_PATH_OR_URL = self.tmp_db.name
        db_mod.DB_PATH = self.tmp_db.name
        db_mod.init_db()
        self.db_mod = db_mod

        import backend.src.core.config as config_mod
        importlib.reload(config_mod)
        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        import backend.src.core.models as models_mod
        importlib.reload(models_mod)
        import backend.src.audit.audit_log as audit_mod
        importlib.reload(audit_mod)
        import backend.src.grants.grant_requests as requests_mod
        importlib.reload(requests_mod)

        self.config_mod = config_mod
        self.models_mod = models_mod
        self.audit_mod = audit_mod
        self.requests_mod = requests_mod

    def tearDown(self):
        try:
            os.unlink(self.tmp_db.name)
        except OSError:
            pass
        for key, orig in self._env_backup.items():
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig

    # ── helpers ──────────────────────────────────────────────────────────

    def _jwt(self, sub, role, tenant_id="demo", workspace_id=None):
        from backend.src.api.auth_jwt import encode_token

        claims = {
            "sub": sub,
            "role": role,
            "tenant_id": tenant_id,
            "iss": _ISS,
            "aud": _AUD,
        }
        if workspace_id is not None:
            claims["workspace_id"] = workspace_id
        return encode_token(claims, _TEST_SECRET)

    def _client(self):
        importlib.reload(self.config_mod)
        import backend.src.auth.auth as auth_mod
        importlib.reload(auth_mod)
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app

        return TestClient(create_app(), raise_server_exceptions=False)

    def _events(self, action):
        return [e for e in self.audit_mod.list_events(limit=2000) if e.action == action]

    def _one_event(self, action):
        evts = self._events(action)
        self.assertEqual(
            len(evts), 1, f"expected exactly one {action!r} audit event, got {len(evts)}"
        )
        return evts[0]

    def _make_request(self, tenant_id, workspace_id, **overrides):
        defaults = dict(
            subject_id="agent-1",
            role="technician",
            action="restart-service",
            resource="env-a",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2099-12-31T23:59:59Z",
            requested_by="requester-op",
            reason="Routine maintenance",
        )
        defaults.update(overrides)
        req = self.models_mod.GrantRequest(**defaults)
        return self.requests_mod.create_grant_request(
            req, tenant_id=tenant_id, workspace_id=workspace_id
        )


# ══════════════════════════════════════════════════════════════════════════
# 3. Behavioral tests through the REAL write paths — workspace forwarded
# ══════════════════════════════════════════════════════════════════════════


class TestGrantRequestWritePaths(_WritePathBase):
    def test_approval_audit_event_carries_workspace(self):
        ws = f"ws-{uuid.uuid4()}"
        req = self._make_request(tenant_id="demo", workspace_id=ws)
        self.requests_mod.approve_grant_request(
            req.id, "approver-op", tenant_id="demo", workspace_id=ws
        )
        evt = self._one_event("approve_grant_request")
        self.assertIsNotNone(evt.workspace_id, "approval audit event workspace_id is NULL")
        self.assertEqual(evt.workspace_id, ws)

    def test_denial_audit_event_carries_workspace(self):
        ws = f"ws-{uuid.uuid4()}"
        req = self._make_request(tenant_id="demo", workspace_id=ws)
        self.requests_mod.deny_grant_request(
            req.id, "denier-op", "Not allowed", tenant_id="demo", workspace_id=ws
        )
        evt = self._one_event("deny_grant_request")
        self.assertIsNotNone(evt.workspace_id, "denial audit event workspace_id is NULL")
        self.assertEqual(evt.workspace_id, ws)

    def test_revoke_audit_event_carries_workspace(self):
        ws = f"ws-{uuid.uuid4()}"
        req = self._make_request(tenant_id="demo", workspace_id=ws)
        self.requests_mod.approve_grant_request(
            req.id, "approver-op", tenant_id="demo", workspace_id=ws
        )
        self.requests_mod.revoke_grant_request(
            req.id, "revoker-op", "Security concern", tenant_id="demo", workspace_id=ws
        )
        evt = self._one_event("revoke_grant_request")
        self.assertIsNotNone(evt.workspace_id, "revoke audit event workspace_id is NULL")
        self.assertEqual(evt.workspace_id, ws)


class TestApiKeyWritePath(_WritePathBase):
    def test_api_key_created_audit_event_carries_workspace(self):
        ws = f"ws-{uuid.uuid4()}"
        client = self._client()
        token = self._jwt("api-key-user", "grant_admin", tenant_id="t1", workspace_id=ws)
        resp = client.post(
            "/v1/api-keys",
            json={"name": "K", "scopes": ["read_write"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        evt = self._one_event("api_key_created")
        self.assertIsNotNone(evt.workspace_id, "api_key_created audit event workspace_id is NULL")
        self.assertEqual(evt.workspace_id, ws)


class TestBulkWritePath(_WritePathBase):
    def test_bulk_update_audit_event_carries_workspace(self):
        # demo tenant + no membership → workspace resolves to the demo workspace "default".
        client = self._client()
        token = self._jwt("bulk-op", "grant_admin", tenant_id="demo")
        resp = client.post(
            "/v1/grants/bulk-update",
            json={"grantIds": [f"missing-{uuid.uuid4()}"], "revoke": False, "reason": "bulk"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        evt = self._one_event("bulk_update")
        self.assertIsNotNone(evt.workspace_id, "bulk_update audit event workspace_id is NULL")
        self.assertEqual(evt.workspace_id, "default")


class TestExportWritePath(_WritePathBase):
    def test_export_audit_event_carries_workspace(self):
        client = self._client()
        token = self._jwt("export-user", "auditor", tenant_id="demo")
        resp = client.get(
            "/v1/exports/grants.csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        evt = self._one_event("export_grants_csv")
        self.assertIsNotNone(evt.workspace_id, "export audit event workspace_id is NULL")
        self.assertEqual(evt.workspace_id, "default")


# ══════════════════════════════════════════════════════════════════════════
# 4. Global (workspace-less) events use the sentinel + a real scope
# ══════════════════════════════════════════════════════════════════════════


class TestGlobalEventsUseSentinel(_WritePathBase):
    def test_gdpr_event_uses_system_sentinel_and_system_scope(self):
        client = self._client()
        # Self-service GDPR export (caller acts on own sub) → always authorized.
        token = self._jwt("gdpr-subject", "user", tenant_id="demo")
        resp = client.post(
            "/v1/users/gdpr-subject/export-data",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 202, resp.text)
        evt = self._one_event("gdpr_export_requested")
        self.assertEqual(
            evt.workspace_id,
            _EXPECTED_SYSTEM_WORKSPACE,
            "gdpr audit event must carry the SYSTEM_WORKSPACE sentinel, not NULL",
        )
        self.assertEqual(evt.scope, "system")

    def test_admin_event_uses_system_sentinel_and_tenant_admin_scope(self):
        client = self._client()
        token = self._jwt("admin-op", "grant_admin", tenant_id="t1")
        resp = client.post(
            "/v1/admin/operators",
            json={"name": "New Op", "role": "auditor", "tenantId": "t1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        evt = self._one_event("operator_created")
        self.assertEqual(
            evt.workspace_id,
            _EXPECTED_SYSTEM_WORKSPACE,
            "admin audit event must carry the SYSTEM_WORKSPACE sentinel, not NULL",
        )
        self.assertEqual(evt.scope, "tenant_admin")


if __name__ == "__main__":
    unittest.main(verbosity=2)
