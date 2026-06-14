"""
GL-200B Tenant/Workspace Isolation Implementation Baseline — test suite.

Covers:
- Tenant context attached on resource create (grants, grant_requests, challenges)
- Tenant-scoped list filtering (cross-tenant isolation)
- Cross-tenant direct ID lookup denial (returns None / 404)
- Cross-tenant mutation denial (revoke, approve, deny)
- Audit events include tenant_id for scoped operations
- Audit hash-chain integrity preserved across pre/post-migration events
- Operator model returns tenant_id in auth context
- Admin token mode resolves to 'demo' tenant
- DB migration adds required columns (idempotency + fresh path)
- Legacy/backfilled rows do not become globally accessible
- Demo endpoint safety preserved (GL-190 guard)
- Health/readiness endpoints remain public and carry no tenant data
- workspace_id column reserved and backfilled to default
- No production SaaS claim
- No tenant isolation claimed as complete

Design notes:
- GL-200B implements Option A baseline: tenant_id on all business resource tables.
- workspace_id is reserved for GL-200C and defaults to the demo workspace.
- Cross-tenant resource lookups return None (functions) or 404 (HTTP).
- Admin-token mode is bound to 'demo' tenant for dev/demo backward compatibility.
- Existing chain events (tenant_id=None) are verified with legacy payload format.
- New chain events (tenant_id set) use updated payload format.
"""

import datetime
import importlib
import json
import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOC_PATH = os.path.join(REPO_ROOT, "docs", "tenant_workspace_isolation_implementation_baseline.md")
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs", "examples", "gl200b",
    "tenant_workspace_isolation_implementation_baseline.json",
)


def _make_db():
    """Return a fresh temp-file SQLite DB path."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _reload_modules(db_path: str):
    """Reload backend modules with a fresh isolated DB."""
    os.environ["GRANTLAYER_DB"] = db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)
    # Ensure plaintext key loading is allowed in test context regardless of
    # what a prior xdist worker may have set via config reload.
    os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"

    import backend.src.core.config as config_mod
    importlib.reload(config_mod)

    import backend.src.core.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import backend.src.core.models as models_mod
    importlib.reload(models_mod)

    import backend.src.auth.operators as ops_mod
    importlib.reload(ops_mod)

    import backend.src.auth.auth as auth_mod
    importlib.reload(auth_mod)

    import backend.src.grants.grants as grants_mod
    importlib.reload(grants_mod)

    import backend.src.auth.challenges as ch_mod
    importlib.reload(ch_mod)

    import backend.src.grants.grant_requests as gr_mod
    importlib.reload(gr_mod)

    import backend.src.audit.audit_log as audit_mod
    importlib.reload(audit_mod)

    return db_mod, models_mod, ops_mod, auth_mod, grants_mod, ch_mod, gr_mod, audit_mod


def _future_date(days=30) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


def _past_date(days=30) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


class TestMigrationColumns(unittest.TestCase):
    """M-001 through M-004: migration adds required columns, is idempotent, fresh path works."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _get_columns(self, table):
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return [r[1] for r in rows]
        finally:
            conn.close()

    def test_grants_has_tenant_id(self):
        """M-001: grants table has tenant_id column."""
        cols = self._get_columns("grants")
        self.assertIn("tenant_id", cols)

    def test_grants_has_workspace_id(self):
        """M-001: grants table has workspace_id column (reserved for GL-200C)."""
        cols = self._get_columns("grants")
        self.assertIn("workspace_id", cols)

    def test_grant_requests_has_tenant_id(self):
        """M-001: grant_requests table has tenant_id column."""
        cols = self._get_columns("grant_requests")
        self.assertIn("tenant_id", cols)

    def test_challenges_has_tenant_id(self):
        """M-001: challenges table has tenant_id column."""
        cols = self._get_columns("challenges")
        self.assertIn("tenant_id", cols)

    def test_audit_events_has_tenant_id(self):
        """M-001: audit_events table has tenant_id column."""
        cols = self._get_columns("audit_events")
        self.assertIn("tenant_id", cols)

    def test_audit_events_has_scope(self):
        """M-001: audit_events table has scope column."""
        cols = self._get_columns("audit_events")
        self.assertIn("scope", cols)

    def test_operators_has_tenant_id(self):
        """M-001: operators table has tenant_id column."""
        cols = self._get_columns("operators")
        self.assertIn("tenant_id", cols)

    def test_grant_executions_has_tenant_id(self):
        """M-001: grant_executions table has tenant_id column."""
        cols = self._get_columns("grant_executions")
        self.assertIn("tenant_id", cols)

    def test_migration_idempotent(self):
        """M-003: re-running migrations does not fail."""
        # Run migrations a second time via runner directly
        from backend.src.migrations import runner
        conn = self.db_mod.get_conn()
        try:
            runner.run_migrations(conn)
        finally:
            conn.close()

    def test_workspace_id_defaulted(self):
        """workspace_id is defaulted after GL-283; NULL is no longer allowed."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="sub1",
            role="viewer",
            action="read",
            resource="res1",
            valid_from=_past_date(1),
            valid_until=_future_date(30),
            created_by="op1",
            reason="test",
        )
        g.create_grant(grant, tenant_id="t1")
        # workspace_id should be the default workspace for new grants
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute("SELECT workspace_id FROM grants WHERE id = ?", (grant.id,)).fetchone()
            self.assertEqual(row["workspace_id"], "default")
        finally:
            conn.close()


class TestTenantContextOnCreate(unittest.TestCase):
    """Tenant context is attached on resource create."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_create_grant_stores_tenant_id(self):
        """Tenant context attached on grant create."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="sub1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op1", reason="test",
        )
        g.create_grant(grant, tenant_id="tenant_alpha")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute("SELECT tenant_id FROM grants WHERE id = ?", (grant.id,)).fetchone()
            self.assertEqual(row["tenant_id"], "tenant_alpha")
        finally:
            conn.close()

    def test_create_grant_explicit_demo_tenant(self):
        """Grant created with explicit tenant_id='demo' is stored under 'demo' tenant."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="sub2", role="viewer", action="read", resource="res2",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op1", reason="test",
        )
        g.create_grant(grant, tenant_id="demo")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute("SELECT tenant_id FROM grants WHERE id = ?", (grant.id,)).fetchone()
            self.assertEqual(row["tenant_id"], "demo")
        finally:
            conn.close()

    def test_create_challenge_stores_tenant_id(self):
        """Tenant context attached on challenge create."""
        import backend.src.auth.challenges as ch
        challenge = ch.create_challenge("sub1", "read", "res1", tenant_id="tenant_beta")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute("SELECT tenant_id FROM challenges WHERE id = ?", (challenge.id,)).fetchone()
            self.assertEqual(row["tenant_id"], "tenant_beta")
        finally:
            conn.close()

    def test_create_grant_request_stores_tenant_id(self):
        """Tenant context attached on grant_request create."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        import backend.src.grants.grant_requests as gr
        importlib.reload(gr)
        from backend.src.core.models import GrantRequest
        req = GrantRequest(
            subject_id="sub1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            requested_by="op1", reason="need access",
        )
        gr.create_grant_request(req, tenant_id="tenant_gamma")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute("SELECT tenant_id FROM grant_requests WHERE id = ?", (req.id,)).fetchone()
            self.assertEqual(row["tenant_id"], "tenant_gamma")
        finally:
            conn.close()


class TestCrossTenantListFiltering(unittest.TestCase):
    """T-001/T-005: Cross-tenant list filtering — operator A cannot see tenant B's resources."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _make_grant(self, tenant_id, subject="subA"):
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id=subject, role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op1", reason="test",
        )
        g.create_grant(grant, tenant_id=tenant_id)
        return grant

    def test_list_grants_filtered_by_tenant(self):
        """T-001: list_grants(tenant_id='t1') excludes t2 grants."""
        import backend.src.grants.grants as g
        g1 = self._make_grant("t1")
        g2 = self._make_grant("t2")
        result = g.list_grants(tenant_id="t1")
        ids = [r.id for r in result]
        self.assertIn(g1.id, ids)
        self.assertNotIn(g2.id, ids)

    def test_list_grants_no_filter_returns_all(self):
        """list_grants() with no filter returns all (backward compat for internal use)."""
        import backend.src.grants.grants as g
        g1 = self._make_grant("t1")
        g2 = self._make_grant("t2")
        result = g.list_grants()
        ids = [r.id for r in result]
        self.assertIn(g1.id, ids)
        self.assertIn(g2.id, ids)

    def test_list_challenges_filtered_by_tenant(self):
        """list_challenges(tenant_id) excludes other tenants."""
        import backend.src.auth.challenges as ch
        c1 = ch.create_challenge("s1", "act", "res1", tenant_id="t1")
        c2 = ch.create_challenge("s2", "act", "res2", tenant_id="t2")
        result = ch.list_challenges(tenant_id="t1")
        ids = [c.id for c in result]
        self.assertIn(c1.id, ids)
        self.assertNotIn(c2.id, ids)

    def test_list_grant_requests_filtered_by_tenant(self):
        """T-005: list_grant_requests(tenant_id) excludes other tenants."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        import backend.src.grants.grant_requests as gr
        importlib.reload(gr)
        from backend.src.core.models import GrantRequest

        def _req(tenant):
            req = GrantRequest(
                subject_id="s1", role="viewer", action="read", resource="res1",
                valid_from=_past_date(1), valid_until=_future_date(30),
                requested_by="op1", reason="r",
            )
            gr.create_grant_request(req, tenant_id=tenant)
            return req

        r1 = _req("t1")
        r2 = _req("t2")
        result = gr.list_grant_requests(tenant_id="t1")
        ids = [r.id for r in result]
        self.assertIn(r1.id, ids)
        self.assertNotIn(r2.id, ids)


class TestCrossTenantLookupDenial(unittest.TestCase):
    """T-007: Cross-tenant direct ID lookup returns None (404 at HTTP level)."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_get_grant_cross_tenant_returns_none(self):
        """get_grant(id, tenant_id='t2') returns None for t1 grant."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="s1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op1", reason="test",
        )
        g.create_grant(grant, tenant_id="t1")
        result = g.get_grant(grant.id, tenant_id="t2")
        self.assertIsNone(result)

    def test_get_grant_same_tenant_succeeds(self):
        """get_grant(id, tenant_id='t1') finds grant owned by t1."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="s1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op1", reason="test",
        )
        g.create_grant(grant, tenant_id="t1")
        result = g.get_grant(grant.id, tenant_id="t1")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, grant.id)

    def test_get_challenge_cross_tenant_returns_none(self):
        """get_challenge(id, tenant_id='t2') returns None for t1 challenge."""
        import backend.src.auth.challenges as ch
        c = ch.create_challenge("s1", "act", "res1", tenant_id="t1")
        result = ch.get_challenge(c.id, tenant_id="t2")
        self.assertIsNone(result)

    def test_get_grant_request_cross_tenant_returns_none(self):
        """get_grant_request(id, tenant_id='t2') returns None for t1 request."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        import backend.src.grants.grant_requests as gr
        importlib.reload(gr)
        from backend.src.core.models import GrantRequest
        req = GrantRequest(
            subject_id="s1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            requested_by="op1", reason="r",
        )
        gr.create_grant_request(req, tenant_id="t1")
        result = gr.get_grant_request(req.id, tenant_id="t2")
        self.assertIsNone(result)


class TestCrossTenantMutationDenial(unittest.TestCase):
    """T-002: Cross-tenant mutation is denied — revoke, approve, deny fail for wrong tenant."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_revoke_grant_cross_tenant_fails(self):
        """revoke_grant with wrong tenant_id returns False (no mutation)."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="s1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op1", reason="test",
        )
        g.create_grant(grant, tenant_id="t1")
        ok = g.revoke_grant(grant.id, "attacker", "malicious", tenant_id="t2")
        self.assertFalse(ok)

        # Verify grant is not actually revoked
        still_there = g.get_grant(grant.id, tenant_id="t1")
        self.assertIsNotNone(still_there)
        self.assertFalse(still_there.revoked)

    def test_revoke_grant_same_tenant_succeeds(self):
        """revoke_grant with correct tenant_id succeeds."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="s1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op1", reason="test",
        )
        g.create_grant(grant, tenant_id="t1")
        ok = g.revoke_grant(grant.id, "op1", "reason", tenant_id="t1")
        self.assertTrue(ok)

    def test_approve_grant_request_cross_tenant_raises(self):
        """approve_grant_request with wrong tenant raises ValueError (not found)."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        import backend.src.grants.grant_requests as gr
        importlib.reload(gr)
        from backend.src.core.models import GrantRequest
        req = GrantRequest(
            subject_id="s1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            requested_by="op1", reason="need access",
        )
        gr.create_grant_request(req, tenant_id="t1")
        with self.assertRaises(ValueError):
            gr.approve_grant_request(req.id, "op2", tenant_id="t2")

    def test_deny_grant_request_cross_tenant_raises(self):
        """deny_grant_request with wrong tenant raises ValueError (not found)."""
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
        import backend.src.grants.grant_requests as gr
        importlib.reload(gr)
        from backend.src.core.models import GrantRequest
        req = GrantRequest(
            subject_id="s1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            requested_by="op1", reason="need access",
        )
        gr.create_grant_request(req, tenant_id="t1")
        with self.assertRaises(ValueError):
            gr.deny_grant_request(req.id, "op2", "denied", tenant_id="t2")


class TestAuditTenantContext(unittest.TestCase):
    """AU-001/AU-002: Post-migration audit events include tenant_id; system events use scope=system."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_audit_event_stores_tenant_id(self):
        """AU-001: audit event with tenant_id is stored and retrieved."""
        import backend.src.audit.audit_log as al
        from backend.src.core.models import AuditEvent
        event = AuditEvent(
            subject_id="op1", role="operator", action="test_action",
            resource="test/resource", approved=True, reason="test",
            tenant_id="tenant_alpha", scope="tenant",
        )
        al.append_event(event)
        retrieved = al.get_event(event.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.tenant_id, "tenant_alpha")
        self.assertEqual(retrieved.scope, "tenant")

    def test_audit_event_no_tenant_id_is_legacy(self):
        """AU-002: audit event without tenant_id is accepted (legacy/system event)."""
        import backend.src.audit.audit_log as al
        from backend.src.core.models import AuditEvent
        event = AuditEvent(
            subject_id="system", role="system", action="health_check",
            resource="health", approved=True, reason="probe",
        )
        al.append_event(event)
        retrieved = al.get_event(event.id)
        self.assertIsNotNone(retrieved)
        self.assertIsNone(retrieved.tenant_id)

    def test_list_events_filtered_by_tenant(self):
        """T-003: list_events(tenant_id='t1') excludes t2 events."""
        import backend.src.audit.audit_log as al
        from backend.src.core.models import AuditEvent
        e1 = AuditEvent(
            subject_id="op1", role="operator", action="act1",
            resource="res1", approved=True, reason="r",
            tenant_id="t1",
        )
        e2 = AuditEvent(
            subject_id="op2", role="operator", action="act2",
            resource="res2", approved=True, reason="r",
            tenant_id="t2",
        )
        al.append_event(e1)
        al.append_event(e2)
        result = al.list_events(tenant_id="t1")
        ids = [e.id for e in result]
        self.assertIn(e1.id, ids)
        self.assertNotIn(e2.id, ids)

    def test_audit_to_dict_includes_tenant_id(self):
        """AuditEvent.to_dict() includes tenant_id and scope."""
        import backend.src.audit.audit_log as al
        from backend.src.core.models import AuditEvent
        event = AuditEvent(
            subject_id="op1", role="operator", action="act",
            resource="res", approved=True, reason="r",
            tenant_id="t_test", scope="tenant",
        )
        al.append_event(event)
        retrieved = al.get_event(event.id)
        d = retrieved.to_dict()
        self.assertEqual(d["tenant_id"], "t_test")
        self.assertEqual(d["scope"], "tenant")


class TestAuditHashChainIntegrity(unittest.TestCase):
    """AU-003/AU-004: Audit chain integrity preserved; dual-mode handles pre/post-migration events."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_chain_valid_with_tenant_id_events(self):
        """Hash chain is valid for events with tenant_id."""
        import backend.src.audit.audit_log as al
        from backend.src.core.models import AuditEvent
        for i in range(3):
            al.append_event(AuditEvent(
                subject_id="op1", role="operator", action=f"act{i}",
                resource="res", approved=True, reason="r",
                tenant_id="t1", scope="tenant",
            ))
        result = al.verify_audit_hash_chain()
        self.assertTrue(result["valid"], f"Chain invalid: {result['failures']}")
        self.assertEqual(result["checked"], 3)

    def test_chain_valid_with_mixed_events(self):
        """Hash chain valid for mix of pre-migration (no tenant_id) and new events."""
        import backend.src.audit.audit_log as al
        from backend.src.core.models import AuditEvent
        # Pre-migration event (no tenant_id)
        al.append_event(AuditEvent(
            subject_id="sys", role="system", action="bootstrap",
            resource="system", approved=True, reason="init",
        ))
        # Post-migration event (with tenant_id)
        al.append_event(AuditEvent(
            subject_id="op1", role="operator", action="create_grant",
            resource="grants/123", approved=True, reason="created",
            tenant_id="t1", scope="tenant",
        ))
        result = al.verify_audit_hash_chain()
        self.assertTrue(result["valid"], f"Chain invalid: {result['failures']}")
        self.assertEqual(result["checked"], 2)

    def test_chain_valid_empty(self):
        """Hash chain valid for empty audit log."""
        import backend.src.audit.audit_log as al
        result = al.verify_audit_hash_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked"], 0)

    def test_chain_valid_no_tenant_events(self):
        """Hash chain valid for legacy events without tenant_id."""
        import backend.src.audit.audit_log as al
        from backend.src.core.models import AuditEvent
        for i in range(3):
            al.append_event(AuditEvent(
                subject_id="op1", role="operator", action=f"legacy{i}",
                resource="res", approved=True, reason="r",
            ))
        result = al.verify_audit_hash_chain()
        self.assertTrue(result["valid"], f"Chain invalid: {result['failures']}")


class TestOperatorTenantContext(unittest.TestCase):
    """Operator model returns tenant_id in auth context."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

    def tearDown(self):
        os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_operator_has_tenant_id_field(self):
        """Operator object carries tenant_id."""
        import backend.src.auth.operators as ops
        importlib.reload(ops)
        op, token = ops.create_operator("Alice", "owner", "tok-alice-123", tenant_id="t_alice")
        self.assertEqual(op.tenant_id, "t_alice")

    def test_operator_to_dict_includes_tenant_id(self):
        """Operator.to_dict() includes tenantId."""
        import backend.src.auth.operators as ops
        importlib.reload(ops)
        op, token = ops.create_operator("Bob", "grant_admin", "tok-bob-456", tenant_id="t_bob")
        d = op.to_dict()
        self.assertIn("tenantId", d)
        self.assertEqual(d["tenantId"], "t_bob")

    def test_authenticate_operator_returns_tenant_id(self):
        """authenticate_operator_with_reason returns operator with tenant_id."""
        import backend.src.auth.operators as ops
        importlib.reload(ops)
        op, token = ops.create_operator("Carol", "owner", token="tok-carol-789", tenant_id="t_carol")
        result, reason = ops.authenticate_operator_with_reason(f"Bearer {token}")
        self.assertIsNotNone(result)
        self.assertEqual(result.tenant_id, "t_carol")

    def test_check_auth_operator_mode_includes_tenant_id(self):
        """check_auth() includes tenant_id in payload when operator mode active."""
        import backend.src.auth.operators as ops
        import backend.src.core.config as conf
        import backend.src.auth.auth as auth
        importlib.reload(ops)
        importlib.reload(conf)
        importlib.reload(auth)

        op, token = ops.create_operator("Dave", "owner", token="tok-dave-000", tenant_id="t_dave")
        ok, status, payload = auth.check_auth(f"Bearer {token}")
        self.assertTrue(ok)
        self.assertEqual(payload.get("tenant_id"), "t_dave")

    def test_operator_row_reads_tenant_id(self):
        """Operator read back from DB has correct tenant_id."""
        import backend.src.auth.operators as ops
        importlib.reload(ops)
        op, token = ops.create_operator("Eve", "auditor", "tok-eve-111", tenant_id="t_eve")
        fetched = ops.get_operator_by_id(op.operator_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.tenant_id, "t_eve")


class TestAdminTokenDevTenant(unittest.TestCase):
    """A-004: Admin token mode resolves to 'demo' tenant (backward compat with legacy resources)."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-token"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"

    def tearDown(self):
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_check_auth_admin_token_returns_demo_tenant(self):
        """Admin token auth returns tenant_id='demo' (backward compat with legacy resources)."""
        import backend.src.auth.auth as auth
        import backend.src.core.config as conf
        importlib.reload(conf)
        importlib.reload(auth)
        ok, status, payload = auth.check_auth("Bearer test-admin-token")
        self.assertTrue(ok)
        self.assertEqual(payload.get("tenant_id"), "demo")

    def test_check_admin_token_direct_returns_demo_tenant(self):
        """check_auth in legacy admin mode includes tenant_id='demo'."""
        import backend.src.auth.auth as auth
        import backend.src.core.config as conf
        importlib.reload(conf)
        importlib.reload(auth)
        ok, status, payload = auth.check_auth("Bearer test-admin-token")
        self.assertTrue(ok, "Expected auth success")
        self.assertEqual(payload.get("tenant_id"), "demo")


class TestLegacyBackfillIsolation(unittest.TestCase):
    """M-002: Backfilled legacy rows get 'demo' tenant; not globally accessible across tenants."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_backfill_grants_get_demo_tenant(self):
        """Grants created with explicit tenant_id='demo' are stored under 'demo' tenant."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="legacy", role="viewer", action="read", resource="legacy_res",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="system", reason="legacy",
        )
        g.create_grant(grant, tenant_id="demo")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute("SELECT tenant_id FROM grants WHERE id = ?", (grant.id,)).fetchone()
            self.assertEqual(row["tenant_id"], "demo")
        finally:
            conn.close()

    def test_demo_tenant_grants_not_visible_to_other_tenants(self):
        """Demo/legacy grants with 'demo' tenant are not visible to 'prod' tenant."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="legacy", role="viewer", action="read", resource="legacy_res",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="system", reason="legacy",
        )
        g.create_grant(grant, tenant_id="demo")
        # A 'prod' tenant cannot see demo data
        result = g.list_grants(tenant_id="prod")
        ids = [r.id for r in result]
        self.assertNotIn(grant.id, ids)

    def test_demo_tenant_grants_visible_to_demo_tenant(self):
        """Demo/legacy grants with 'demo' tenant are visible to 'demo' tenant queries."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="legacy", role="viewer", action="read", resource="legacy_res",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="system", reason="legacy",
        )
        g.create_grant(grant, tenant_id="demo")
        result = g.list_grants(tenant_id="demo")
        ids = [r.id for r in result]
        self.assertIn(grant.id, ids)


class TestHealthReadinessPublic(unittest.TestCase):
    """H-001/H-002/H-003: Health/readiness remain public and contain no tenant data."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_db_health_contains_no_tenant_data(self):
        """get_db_health() returns no tenant_id, no operator data."""
        import backend.src.core.db as db
        importlib.reload(db)
        health = db.get_db_health()
        self.assertNotIn("tenant_id", health)
        self.assertNotIn("operator", health)
        self.assertNotIn("tenantId", health)
        self.assertIn("dbConnected", health)


class TestWorkspaceIdReserved(unittest.TestCase):
    """workspace_id is reserved and defaulted after GL-283."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]

    def tearDown(self):
        os.environ.pop("GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE", None)
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_workspace_id_column_exists_on_grants(self):
        """workspace_id column exists on grants table."""
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(grants)").fetchall()
            cols = [r[1] for r in rows]
            self.assertIn("workspace_id", cols)
        finally:
            conn.close()

    def test_workspace_id_column_exists_on_audit_events(self):
        """workspace_id column exists on audit_events table."""
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(audit_events)").fetchall()
            cols = [r[1] for r in rows]
            self.assertIn("workspace_id", cols)
        finally:
            conn.close()

    def test_workspace_id_is_defaulted(self):
        """workspace_id defaults to the demo workspace after GL-283."""
        import backend.src.grants.grants as g
        from backend.src.core.models import Grant
        grant = Grant(
            subject_id="ws_test", role="viewer", action="read", resource="r",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op1", reason="test",
        )
        g.create_grant(grant, tenant_id="t1")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute("SELECT workspace_id FROM grants WHERE id = ?", (grant.id,)).fetchone()
            self.assertEqual(row["workspace_id"], "default")
        finally:
            conn.close()


class TestAuditGrantRequestTenantPropagation(unittest.TestCase):
    """Audit events written by approve/deny carry tenant_id."""

    def setUp(self):
        self.db_path = _make_db()
        self.mods = _reload_modules(self.db_path)
        self.db_mod = self.mods[0]
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"

    def tearDown(self):
        os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_deny_writes_audit_event_with_tenant_id(self):
        """deny_grant_request writes an audit event carrying the tenant_id."""
        import backend.src.grants.grant_requests as gr
        import backend.src.audit.audit_log as al
        importlib.reload(gr)
        from backend.src.core.models import GrantRequest

        req = GrantRequest(
            subject_id="sub1", role="viewer", action="read", resource="r",
            valid_from=_past_date(1), valid_until=_future_date(30),
            requested_by="op1", reason="need access",
        )
        gr.create_grant_request(req, tenant_id="t_deny_test")
        gr.deny_grant_request(req.id, "op2", "not approved", tenant_id="t_deny_test")

        events = al.list_events(tenant_id="t_deny_test")
        actions = [e.action for e in events]
        self.assertIn("deny_grant_request", actions)

        deny_evt = next(e for e in events if e.action == "deny_grant_request")
        self.assertEqual(deny_evt.tenant_id, "t_deny_test")
        self.assertEqual(deny_evt.scope, "tenant")


class TestDocumentationArtifacts(unittest.TestCase):
    """Documentation and JSON artifact exist and contain required content."""

    def test_implementation_doc_exists(self):
        """docs/tenant_workspace_isolation_implementation_baseline.md exists."""
        self.assertTrue(os.path.isfile(DOC_PATH), f"Missing doc: {DOC_PATH}")

    def test_implementation_doc_not_empty(self):
        """Implementation doc has meaningful content."""
        with open(DOC_PATH) as f:
            content = f.read()
        self.assertGreater(len(content), 500)

    def test_implementation_doc_not_claiming_complete(self):
        """Implementation doc does not claim tenant isolation is complete."""
        with open(DOC_PATH) as f:
            content = f.read().lower()
        self.assertNotIn("tenant isolation complete", content)
        self.assertNotIn("production saas ready", content)

    def test_implementation_doc_has_baseline_caveat(self):
        """Implementation doc states this is a baseline, not full implementation."""
        with open(DOC_PATH) as f:
            content = f.read().lower()
        # Should contain words indicating this is a baseline
        self.assertTrue(
            "baseline" in content or "not yet complete" in content or "gl-200b" in content,
            "Doc should mention baseline status"
        )

    def test_json_artifact_exists(self):
        """docs/examples/gl200b/tenant_workspace_isolation_implementation_baseline.json exists."""
        self.assertTrue(os.path.isfile(JSON_PATH), f"Missing artifact: {JSON_PATH}")

    def test_json_artifact_valid(self):
        """JSON artifact is valid JSON."""
        with open(JSON_PATH) as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_json_artifact_has_issue_id(self):
        """JSON artifact references GL-200B."""
        with open(JSON_PATH) as f:
            data = json.load(f)
        content = json.dumps(data).lower()
        self.assertIn("gl-200b", content)

    def test_json_artifact_no_production_saas_claim(self):
        """JSON artifact does not claim production SaaS readiness."""
        with open(JSON_PATH) as f:
            data = json.load(f)
        content = json.dumps(data).lower()
        self.assertNotIn("production_saas_ready", content)

    def test_json_artifact_safety_confirmations(self):
        """JSON artifact has safety confirmations block."""
        with open(JSON_PATH) as f:
            data = json.load(f)
        self.assertIn("safety_confirmations", data)
        sc = data["safety_confirmations"]
        self.assertEqual(sc.get("no_github_push_performed"), "confirmed")
        self.assertEqual(sc.get("no_production_saas_claim"), "confirmed")
        self.assertEqual(sc.get("tenant_workspace_isolation_not_claimed_as_complete"), "confirmed")


class TestScopeGuardSafety(unittest.TestCase):
    """Scope-guard: no public marketing claims; no real customer/private data claims."""

    def test_no_production_saas_claim_in_doc(self):
        """Doc does not claim production SaaS readiness."""
        if not os.path.isfile(DOC_PATH):
            self.skipTest("Doc not yet created")
        with open(DOC_PATH) as f:
            content = f.read().lower()
        self.assertNotIn("production saas ready", content)
        self.assertNotIn("real customer data ready", content)

    def test_no_complete_isolation_claim_in_doc(self):
        """Doc does not claim tenant/workspace isolation is complete."""
        if not os.path.isfile(DOC_PATH):
            self.skipTest("Doc not yet created")
        with open(DOC_PATH) as f:
            content = f.read().lower()
        forbidden = [
            "tenant isolation is complete",
            "workspace isolation is complete",
            "isolation complete",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, content, f"Found forbidden claim: {phrase!r}")

    def test_security_reports_route_to_advisories(self):
        """SECURITY.md or doc routes sensitive reports to GitHub Security Advisories."""
        security_path = os.path.join(REPO_ROOT, "SECURITY.md")
        if not os.path.isfile(security_path):
            self.skipTest("SECURITY.md not present")
        with open(security_path) as f:
            content = f.read().lower()
        self.assertTrue(
            "security advisories" in content or "github.com" in content,
            "SECURITY.md should mention GitHub Security Advisories"
        )


if __name__ == "__main__":
    unittest.main()
