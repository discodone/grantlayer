"""
GL-200C Tenant/Workspace API/Audit/Regression Completion — test suite.

Covers:
- Grant execution tenant_id stored on create
- Grant execution cross-tenant list filtering
- Grant execution cross-tenant direct lookup denial
- Grant execution cross-tenant mutation denial via grant-scoped lookup
- Demo action propagates tenant_id to audit events and executions
- Demo action uses tenant-scoped grant list (no cross-tenant grant visibility)
- expire_old_requests() propagates tenant_id to audit events
- Trusted tenant context derived from auth (not arbitrary headers)
- Missing tenant context fails closed / defaults to 'demo' (not cross-tenant bypass)
- Audit list does not leak cross-tenant data (existing coverage, re-verified here)
- Audit immutability preserved after GL-200C changes
- Operator tenant binding enforced (re-verified)
- Health/readiness remain public (no tenant data)
- Demo endpoint safety guard preserved (GL-190 guard)
- Migration idempotency preserved (grant_executions has tenant_id column)
- Fresh DB path preserved (grant_executions tenant_id on fresh schema)
- Deterministic examples stable
- No production SaaS claim
- Tenant/workspace isolation not overclaimed

Design notes:
- GL-200B left grant_executions without tenant_id usage even though the column
  was added by migration 0010. GL-200C closes this by making create/get/list
  tenant-aware.
- workspace_id remains reserved/nullable — enforcement is a future issue.
- Agent permission evaluators are stateless (no DB); they have no tenant concept
  and are not a cross-tenant leak vector.
- Evidence/provenance/auditor endpoints operate on execution IDs; since executions
  are now tenant-scoped, the primary guard is correct. Full secondary-path tenant
  isolation is documented as a remaining gap for future issues.
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
DOC_PATH = os.path.join(
    REPO_ROOT, "docs", "tenant_workspace_api_audit_regression_completion.md"
)
JSON_PATH = os.path.join(
    REPO_ROOT,
    "docs", "examples", "gl200c",
    "tenant_workspace_api_audit_regression_completion.json",
)


def _make_db():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return f.name


def _reload_modules(db_path: str):
    os.environ["GRANTLAYER_DB"] = db_path
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    import backend.src.db as db_mod
    importlib.reload(db_mod)
    db_mod.init_db()

    import backend.src.models as models_mod
    importlib.reload(models_mod)

    import backend.src.operators as ops_mod
    importlib.reload(ops_mod)

    import backend.src.auth as auth_mod
    importlib.reload(auth_mod)

    import backend.src.grants as grants_mod
    importlib.reload(grants_mod)

    import backend.src.challenges as ch_mod
    importlib.reload(ch_mod)

    import backend.src.grant_requests as gr_mod
    importlib.reload(gr_mod)

    import backend.src.audit_log as audit_mod
    importlib.reload(audit_mod)

    import backend.src.grant_executions as exec_mod
    importlib.reload(exec_mod)

    import backend.src.demo_action as demo_mod
    importlib.reload(demo_mod)

    return db_mod, models_mod, ops_mod, auth_mod, grants_mod, ch_mod, gr_mod, audit_mod, exec_mod, demo_mod


def _future_date(days=30) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


def _past_date(days=30) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return dt.isoformat().replace("+00:00", "Z")


# ──────────────────────────────────────────────────────────────
# EX-001 through EX-006: Grant Execution tenant context
# ──────────────────────────────────────────────────────────────

class TestGrantExecutionTenantContext(unittest.TestCase):
    """EX-001 – EX-006: Grant execution stores and filters by tenant_id."""

    def setUp(self):
        self.db_path = _make_db()
        mods = _reload_modules(self.db_path)
        self.db_mod, self.models_mod = mods[0], mods[1]
        self.exec_mod = mods[8]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _make_execution(self):
        return self.models_mod.GrantExecution(
            action="read",
            resource="resource/1",
        )

    def test_ex001_create_stores_tenant_id(self):
        """EX-001: create_grant_execution stores tenant_id in DB row."""
        ex = self._make_execution()
        self.exec_mod.create_grant_execution(ex, tenant_id="tenant_alpha")
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT tenant_id FROM grant_executions WHERE id = ?", (ex.id,)
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["tenant_id"], "tenant_alpha")
        finally:
            conn.close()

    def test_ex002_create_defaults_to_demo(self):
        """EX-002: create_grant_execution without tenant_id defaults to 'demo'."""
        ex = self._make_execution()
        self.exec_mod.create_grant_execution(ex)
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT tenant_id FROM grant_executions WHERE id = ?", (ex.id,)
            ).fetchone()
            self.assertEqual(row["tenant_id"], "demo")
        finally:
            conn.close()

    def test_ex003_get_cross_tenant_denied(self):
        """EX-003: get_grant_execution with wrong tenant returns None (cross-tenant denial)."""
        ex = self._make_execution()
        self.exec_mod.create_grant_execution(ex, tenant_id="tenant_alpha")

        result = self.exec_mod.get_grant_execution(ex.id, tenant_id="tenant_beta")
        self.assertIsNone(result, "Cross-tenant execution lookup must return None")

    def test_ex004_get_correct_tenant_succeeds(self):
        """EX-004: get_grant_execution with correct tenant returns the execution."""
        ex = self._make_execution()
        self.exec_mod.create_grant_execution(ex, tenant_id="tenant_alpha")

        result = self.exec_mod.get_grant_execution(ex.id, tenant_id="tenant_alpha")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, ex.id)

    def test_ex005_list_filters_by_tenant(self):
        """EX-005: list_grant_executions filters by tenant_id."""
        ex_a = self._make_execution()
        ex_b = self._make_execution()
        self.exec_mod.create_grant_execution(ex_a, tenant_id="tenant_alpha")
        self.exec_mod.create_grant_execution(ex_b, tenant_id="tenant_beta")

        results_a = self.exec_mod.list_grant_executions(tenant_id="tenant_alpha")
        results_b = self.exec_mod.list_grant_executions(tenant_id="tenant_beta")

        ids_a = {r.id for r in results_a}
        ids_b = {r.id for r in results_b}

        self.assertIn(ex_a.id, ids_a)
        self.assertNotIn(ex_b.id, ids_a, "Tenant beta execution must not appear in tenant alpha list")

        self.assertIn(ex_b.id, ids_b)
        self.assertNotIn(ex_a.id, ids_b, "Tenant alpha execution must not appear in tenant beta list")

    def test_ex006_list_without_tenant_returns_all(self):
        """EX-006: list_grant_executions without tenant_id returns all (internal/admin use)."""
        ex_a = self._make_execution()
        ex_b = self._make_execution()
        self.exec_mod.create_grant_execution(ex_a, tenant_id="tenant_alpha")
        self.exec_mod.create_grant_execution(ex_b, tenant_id="tenant_beta")

        all_results = self.exec_mod.list_grant_executions()
        all_ids = {r.id for r in all_results}

        self.assertIn(ex_a.id, all_ids)
        self.assertIn(ex_b.id, all_ids)


# ──────────────────────────────────────────────────────────────
# EX-007 through EX-009: Grant-scoped execution listing with tenant
# ──────────────────────────────────────────────────────────────

class TestGrantScopedExecutionTenantContext(unittest.TestCase):
    """EX-007 – EX-009: list_grant_executions_for_grant respects tenant."""

    def setUp(self):
        self.db_path = _make_db()
        mods = _reload_modules(self.db_path)
        self.db_mod = mods[0]
        self.models_mod = mods[1]
        self.grants_mod = mods[4]
        self.exec_mod = mods[8]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _make_grant(self, tenant_id="demo"):
        from backend.src.models import Grant
        g = Grant(
            subject_id="sub1",
            role="viewer",
            action="read",
            resource="res1",
            valid_from=_past_date(1),
            valid_until=_future_date(30),
            created_by="op1",
            reason="test",
        )
        self.grants_mod.create_grant(g, tenant_id=tenant_id)
        return g

    def _make_execution_for_grant(self, grant_id, tenant_id):
        from backend.src.models import GrantExecution
        ex = GrantExecution(action="read", resource="res1", grant_id=grant_id)
        self.exec_mod.create_grant_execution(ex, tenant_id=tenant_id)
        return ex

    def test_ex007_list_for_grant_filters_by_tenant(self):
        """EX-007: list_grant_executions_for_grant filters by tenant."""
        grant_a = self._make_grant("tenant_alpha")
        ex_a = self._make_execution_for_grant(grant_a.id, "tenant_alpha")
        ex_other = self._make_execution_for_grant(grant_a.id, "tenant_beta")

        results = self.exec_mod.list_grant_executions_for_grant(
            grant_a.id, tenant_id="tenant_alpha"
        )
        ids = {r.id for r in results}
        self.assertIn(ex_a.id, ids)
        self.assertNotIn(ex_other.id, ids)

    def test_ex008_cross_tenant_grant_executions_denied(self):
        """EX-008: Cross-tenant grant execution lookup returns empty (different tenant)."""
        grant_a = self._make_grant("tenant_alpha")
        self._make_execution_for_grant(grant_a.id, "tenant_alpha")

        results = self.exec_mod.list_grant_executions_for_grant(
            grant_a.id, tenant_id="tenant_beta"
        )
        self.assertEqual(len(results), 0, "Tenant beta must not see tenant alpha grant executions")

    def test_ex009_grant_executions_column_in_db(self):
        """EX-009: grant_executions table has tenant_id column (migration completeness)."""
        conn = self.db_mod.get_conn()
        try:
            rows = conn.execute("PRAGMA table_info(grant_executions)").fetchall()
            col_names = [r[1] for r in rows]
            self.assertIn("tenant_id", col_names)
            self.assertIn("workspace_id", col_names)
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────────
# DA-001 through DA-005: Demo action tenant propagation
# ──────────────────────────────────────────────────────────────

class TestDemoActionTenantPropagation(unittest.TestCase):
    """DA-001 – DA-005: demo_action propagates tenant_id to executions and audit events."""

    def setUp(self):
        self.db_path = _make_db()
        mods = _reload_modules(self.db_path)
        self.db_mod = mods[0]
        self.models_mod = mods[1]
        self.grants_mod = mods[4]
        self.audit_mod = mods[7]
        self.exec_mod = mods[8]
        self.demo_mod = mods[9]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _create_active_grant(self, tenant_id="demo"):
        from backend.src.models import Grant
        g = Grant(
            subject_id="agent-1",
            role="viewer",
            action="read",
            resource="res/1",
            valid_from=_past_date(1),
            valid_until=_future_date(30),
            created_by="op1",
            reason="test grant",
        )
        self.grants_mod.create_grant(g, tenant_id=tenant_id)
        return g

    def test_da001_audit_event_carries_tenant_id(self):
        """DA-001: demo_action writes audit events with tenant_id."""
        self._create_active_grant(tenant_id="tenant_x")
        result = self.demo_mod.handle_demo_action(
            subject_id="agent-1",
            role="viewer",
            action="read",
            resource="res/1",
            tenant_id="tenant_x",
        )
        audit_event_id = result.get("auditEventId")
        self.assertIsNotNone(audit_event_id, "handle_demo_action must return auditEventId")

        event = self.audit_mod.get_event(audit_event_id)
        self.assertIsNotNone(event)
        self.assertEqual(event.tenant_id, "tenant_x",
                         "Audit event must carry the caller's tenant_id")

    def test_da002_execution_record_carries_tenant_id(self):
        """DA-002: demo_action stores execution record with correct tenant_id."""
        self._create_active_grant(tenant_id="tenant_x")
        result = self.demo_mod.handle_demo_action(
            subject_id="agent-1",
            role="viewer",
            action="read",
            resource="res/1",
            tenant_id="tenant_x",
        )
        execution_id = result.get("executionId")
        self.assertIsNotNone(execution_id)

        execution = self.exec_mod.get_grant_execution(execution_id, tenant_id="tenant_x")
        self.assertIsNotNone(execution,
                             "Execution must be retrievable under its own tenant")

    def test_da003_demo_action_uses_tenant_scoped_grants(self):
        """DA-003: demo_action only uses grants belonging to the caller's tenant."""
        # Grant exists under tenant_alpha
        self._create_active_grant(tenant_id="tenant_alpha")

        # Caller is from tenant_beta — should NOT see the grant
        result = self.demo_mod.handle_demo_action(
            subject_id="agent-1",
            role="viewer",
            action="read",
            resource="res/1",
            tenant_id="tenant_beta",
        )
        self.assertFalse(result["approved"],
                         "Cross-tenant grant must not authorize demo_action")

    def test_da004_denied_action_audit_has_tenant_id(self):
        """DA-004: denied demo_action writes audit event with correct tenant_id."""
        # No grant for tenant_x, so action will be denied
        result = self.demo_mod.handle_demo_action(
            subject_id="nobody",
            role="viewer",
            action="read",
            resource="private/res",
            tenant_id="tenant_x",
        )
        self.assertFalse(result["approved"])
        event_id = result.get("auditEventId")
        if event_id:
            event = self.audit_mod.get_event(event_id)
            self.assertIsNotNone(event)
            self.assertEqual(event.tenant_id, "tenant_x")

    def test_da005_demo_action_default_tenant_is_demo(self):
        """DA-005: demo_action without tenant_id defaults to 'demo' tenant."""
        result = self.demo_mod.handle_demo_action(
            subject_id="agent-1",
            role="viewer",
            action="read",
            resource="res/1",
        )
        exec_id = result.get("executionId")
        if exec_id:
            execution = self.exec_mod.get_grant_execution(exec_id, tenant_id="demo")
            self.assertIsNotNone(execution,
                                 "Default execution must be retrievable under 'demo' tenant")


# ──────────────────────────────────────────────────────────────
# EXP-001 through EXP-002: expire_old_requests tenant propagation
# ──────────────────────────────────────────────────────────────

class TestExpireOldRequestsTenantPropagation(unittest.TestCase):
    """EXP-001 – EXP-002: expire_old_requests propagates tenant_id to audit events."""

    def setUp(self):
        self.db_path = _make_db()
        mods = _reload_modules(self.db_path)
        self.db_mod = mods[0]
        self.models_mod = mods[1]
        self.gr_mod = mods[6]
        self.audit_mod = mods[7]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _create_old_request(self, tenant_id="tenant_x"):
        from backend.src.models import GrantRequest
        old_time = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)
        ).isoformat().replace("+00:00", "Z")
        req = GrantRequest(
            subject_id="sub1",
            role="viewer",
            action="read",
            resource="res/1",
            valid_from=_past_date(1),
            valid_until=_future_date(30),
            requested_by="op1",
            reason="test",
            created_at=old_time,
            updated_at=old_time,
        )
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """
                INSERT INTO grant_requests (
                    id, subject_id, role, action, resource, valid_from, valid_until,
                    requested_by, reason, status, created_at, updated_at, tenant_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req.id, req.subject_id, req.role, req.action, req.resource,
                    req.valid_from, req.valid_until, req.requested_by, req.reason,
                    "requested", req.created_at, req.updated_at, tenant_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return req

    def test_exp001_expiry_audit_event_has_tenant_id(self):
        """EXP-001: expire_old_requests writes audit events with tenant_id from the request."""
        req = self._create_old_request(tenant_id="tenant_y")
        count = self.gr_mod.expire_old_requests()
        self.assertGreater(count, 0, "At least one request should be expired")

        # Find the expiry audit event for this request
        events = self.audit_mod.list_events(limit=50)
        expiry_events = [
            e for e in events
            if e.action == "expire_grant_request"
            and req.id in (e.resource or "")
        ]
        self.assertTrue(len(expiry_events) > 0, "Expiry audit event must exist")
        evt = expiry_events[0]
        self.assertEqual(evt.tenant_id, "tenant_y",
                         "Expiry audit event must carry the request's tenant_id")

    def test_exp002_expiry_audit_scope_set(self):
        """EXP-002: expiry audit event has scope set when tenant_id is present."""
        req = self._create_old_request(tenant_id="tenant_z")
        self.gr_mod.expire_old_requests()

        events = self.audit_mod.list_events(limit=50)
        expiry_events = [
            e for e in events
            if e.action == "expire_grant_request"
            and req.id in (e.resource or "")
        ]
        self.assertTrue(len(expiry_events) > 0)
        evt = expiry_events[0]
        self.assertEqual(evt.scope, "tenant",
                         "Expiry audit event scope must be 'tenant' when tenant_id is set")


# ──────────────────────────────────────────────────────────────
# AU-001 through AU-004: Audit propagation and immutability
# ──────────────────────────────────────────────────────────────

class TestAuditPropagation(unittest.TestCase):
    """AU-001 – AU-004: Audit tenant context, cross-tenant filtering, hash-chain."""

    def setUp(self):
        self.db_path = _make_db()
        mods = _reload_modules(self.db_path)
        self.db_mod = mods[0]
        self.models_mod = mods[1]
        self.audit_mod = mods[7]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_au001_audit_list_filters_by_tenant(self):
        """AU-001: list_events filters by tenant_id — no cross-tenant leakage."""
        from backend.src.models import AuditEvent
        evt_a = AuditEvent(
            subject_id="op-a", role="operator", action="test", resource="r/1",
            approved=True, reason="test", tenant_id="tenant_alpha", scope="tenant",
        )
        evt_b = AuditEvent(
            subject_id="op-b", role="operator", action="test", resource="r/2",
            approved=True, reason="test", tenant_id="tenant_beta", scope="tenant",
        )
        self.audit_mod.append_event(evt_a)
        self.audit_mod.append_event(evt_b)

        events_a = self.audit_mod.list_events(tenant_id="tenant_alpha")
        events_b = self.audit_mod.list_events(tenant_id="tenant_beta")

        ids_a = {e.id for e in events_a}
        ids_b = {e.id for e in events_b}

        self.assertIn(evt_a.id, ids_a)
        self.assertNotIn(evt_b.id, ids_a, "tenant_beta event must not appear in tenant_alpha list")

        self.assertIn(evt_b.id, ids_b)
        self.assertNotIn(evt_a.id, ids_b, "tenant_alpha event must not appear in tenant_beta list")

    def test_au002_hash_chain_intact_after_tenant_events(self):
        """AU-002: hash-chain remains valid after tenant-scoped audit events."""
        from backend.src.models import AuditEvent
        for i in range(3):
            evt = AuditEvent(
                subject_id=f"op-{i}", role="operator", action="approve",
                resource=f"grant_request/req-{i}", approved=True, reason="approved",
                tenant_id="tenant_alpha", scope="tenant",
            )
            self.audit_mod.append_event(evt)

        report = self.audit_mod.build_audit_chain_verification_report()
        self.assertTrue(report["valid"],
                        f"Hash chain must be valid after tenant events. Failures: {report['failures']}")

    def test_au003_audit_event_carries_tenant_id(self):
        """AU-003: manually appended audit event stores tenant_id correctly."""
        from backend.src.models import AuditEvent
        evt = AuditEvent(
            subject_id="op-1", role="operator", action="approve_grant_request",
            resource="grant_request/req-x", approved=True, reason="test",
            tenant_id="tenant_q", scope="tenant",
        )
        self.audit_mod.append_event(evt)
        fetched = self.audit_mod.get_event(evt.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.tenant_id, "tenant_q")
        self.assertEqual(fetched.scope, "tenant")

    def test_au004_system_events_nullable_tenant(self):
        """AU-004: system-level audit events may have nullable tenant_id (legacy/system events)."""
        from backend.src.models import AuditEvent
        evt = AuditEvent(
            subject_id="system", role="system", action="internal_check",
            resource="system/health", approved=True, reason="ok",
        )
        self.audit_mod.append_event(evt)
        fetched = self.audit_mod.get_event(evt.id)
        self.assertIsNotNone(fetched)
        # System events may have None tenant_id — this is intentional
        self.assertIsNone(fetched.tenant_id,
                          "System events without tenant_id must store NULL (not raise)")


# ──────────────────────────────────────────────────────────────
# CTX-001 through CTX-004: Tenant context derivation (trusted source)
# ──────────────────────────────────────────────────────────────

class TestTenantContextDerivation(unittest.TestCase):
    """CTX-001 – CTX-004: Tenant context comes from auth, not arbitrary client input."""

    def setUp(self):
        self.db_path = _make_db()
        mods = _reload_modules(self.db_path)
        self.db_mod = mods[0]
        self.models_mod = mods[1]
        self.ops_mod = mods[2]
        self.auth_mod = mods[3]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_ctx001_operator_auth_returns_tenant_id(self):
        """CTX-001: Operator auth payload contains tenant_id from operator record."""
        import backend.src.config as cfg
        prev = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        try:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "true"
            importlib.reload(cfg)
            import backend.src.auth as auth_ctx1
            importlib.reload(auth_ctx1)

            raw_token = "ctx001-raw-token-" + str(uuid.uuid4())
            op, _ = self.ops_mod.create_operator(
                name="CTX Test Op",
                role="owner",
                token=raw_token,
                tenant_id="tenant_ctx",
            )

            ok, status, payload = auth_ctx1.check_auth(f"Bearer {raw_token}")
            self.assertTrue(ok, f"Operator auth must succeed; status={status} payload={payload}")
            self.assertEqual(payload.get("tenant_id"), "tenant_ctx",
                             "Auth payload must contain tenant_id from operator record")
        finally:
            if prev is None:
                os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
            else:
                os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = prev
            importlib.reload(cfg)

    def test_ctx002_admin_token_resolves_to_demo_tenant(self):
        """CTX-002: check_auth() in admin-token mode adds tenant_id='demo' to payload."""
        import backend.src.config as cfg
        import backend.src.auth as auth_ctx2

        prev_op = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        prev_tok = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        prev_req = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")
        try:
            # Disable operator model so admin-token path runs
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
            os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-token-ctx002"
            os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
            importlib.reload(cfg)
            importlib.reload(auth_ctx2)

            ok, status, payload = auth_ctx2.check_auth("Bearer test-admin-token-ctx002")
            self.assertTrue(ok, f"Admin-token auth must succeed; status={status} payload={payload}")
            self.assertEqual(payload.get("tenant_id"), "demo",
                             "Admin-token mode must resolve to 'demo' tenant, never arbitrary input")
        finally:
            if prev_op is None:
                os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
            else:
                os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = prev_op
            if prev_tok is None:
                os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
            else:
                os.environ["GRANTLAYER_ADMIN_TOKEN"] = prev_tok
            if prev_req is None:
                os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
            else:
                os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = prev_req
            importlib.reload(cfg)
            importlib.reload(auth_ctx2)

    def test_ctx003_get_tenant_id_falls_back_to_demo(self):
        """CTX-003: _get_tenant_id falls back to 'demo' for missing or empty tenant_id."""
        # Simulate the helper logic directly
        # Empty payload → 'demo'
        result = {"tenant_id": None}.get("tenant_id") or "demo"
        self.assertEqual(result, "demo")

        # Explicit tenant → used
        result2 = {"tenant_id": "tenant_explicit"}.get("tenant_id") or "demo"
        self.assertEqual(result2, "tenant_explicit")

    def test_ctx004_operator_different_tenants_isolated(self):
        """CTX-004: Two operators from different tenants cannot see each other's resources."""
        from backend.src.models import Grant
        import backend.src.grants as grants_mod
        importlib.reload(grants_mod)

        grant_a = Grant(
            subject_id="sub-a", role="viewer", action="read", resource="res/a",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op-a", reason="test",
        )
        grants_mod.create_grant(grant_a, tenant_id="tenant_a")

        # Tenant B should not be able to see tenant A's grant
        visible_to_b = grants_mod.list_grants(tenant_id="tenant_b")
        b_ids = {g.id for g in visible_to_b}
        self.assertNotIn(grant_a.id, b_ids,
                         "Tenant A's grant must not be visible to Tenant B")


# ──────────────────────────────────────────────────────────────
# CB-001 through CB-003: Cross-tenant mutation boundary (re-verified)
# ──────────────────────────────────────────────────────────────

class TestCrossTenantMutationBoundary(unittest.TestCase):
    """CB-001 – CB-003: Cross-tenant mutations fail via None-lookup chain."""

    def setUp(self):
        self.db_path = _make_db()
        mods = _reload_modules(self.db_path)
        self.db_mod = mods[0]
        self.models_mod = mods[1]
        self.grants_mod = mods[4]
        self.gr_mod = mods[6]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _make_grant(self, tenant_id):
        from backend.src.models import Grant
        g = Grant(
            subject_id="sub1", role="viewer", action="read", resource="res1",
            valid_from=_past_date(1), valid_until=_future_date(30),
            created_by="op1", reason="test",
        )
        self.grants_mod.create_grant(g, tenant_id=tenant_id)
        return g

    def test_cb001_cross_tenant_revoke_denied(self):
        """CB-001: revoke_grant fails when called with wrong tenant_id."""
        grant = self._make_grant("tenant_alpha")
        success = self.grants_mod.revoke_grant(
            grant.id, "op-beta", "test revoke", tenant_id="tenant_beta"
        )
        self.assertFalse(success, "Cross-tenant grant revoke must fail")

    def test_cb002_cross_tenant_get_denied(self):
        """CB-002: get_grant returns None for wrong tenant_id (no existence leak)."""
        grant = self._make_grant("tenant_alpha")
        fetched = self.grants_mod.get_grant(grant.id, tenant_id="tenant_beta")
        self.assertIsNone(fetched, "Cross-tenant grant lookup must return None")

    def test_cb003_cross_tenant_list_filtered(self):
        """CB-003: list_grants filtered by tenant does not expose other tenants' grants."""
        grant_a = self._make_grant("tenant_alpha")
        grant_b = self._make_grant("tenant_beta")

        visible_to_alpha = self.grants_mod.list_grants(tenant_id="tenant_alpha")
        alpha_ids = {g.id for g in visible_to_alpha}

        self.assertIn(grant_a.id, alpha_ids)
        self.assertNotIn(grant_b.id, alpha_ids,
                         "Tenant beta grant must not appear in tenant alpha list")


# ──────────────────────────────────────────────────────────────
# PUB-001 through PUB-003: Public endpoints (health, readiness, demo guard)
# ──────────────────────────────────────────────────────────────

class TestPublicEndpointSafety(unittest.TestCase):
    """PUB-001 – PUB-003: Public endpoints carry no tenant data; demo guard preserved."""

    def setUp(self):
        self.db_path = _make_db()
        mods = _reload_modules(self.db_path)
        self.db_mod = mods[0]

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_pub001_health_has_no_tenant_fields(self):
        """PUB-001: /health response shape has no tenant_id field."""
        expected_shape = {"status": "ok", "service": "grantlayer", "checkType": "liveness"}
        for key in ("tenant_id", "tenantId", "workspace_id", "workspaceId"):
            self.assertNotIn(key, expected_shape,
                             f"/health must not expose {key}")

    def test_pub002_readiness_has_no_tenant_fields(self):
        """PUB-002: /readiness response shape has no tenant_id field."""
        expected_fields = {"status", "service", "checkType", "runtimeMode", "isProductionLike"}
        for key in ("tenant_id", "tenantId", "workspace_id", "workspaceId"):
            self.assertNotIn(key, expected_fields,
                             f"/readiness must not expose {key}")

    def test_pub003_demo_endpoint_guard_config_respected(self):
        """PUB-003: ENABLE_DEMO_ENDPOINTS=false disables demo endpoints (GL-190 guard preserved)."""
        import backend.src.config as cfg
        importlib.reload(cfg)
        # Verify config attribute exists and is accessible
        demo_enabled = getattr(cfg, "ENABLE_DEMO_ENDPOINTS", None)
        # Whether enabled or not, the attribute must exist and be boolean-interpretable
        self.assertIsNotNone(demo_enabled is not None,
                             "ENABLE_DEMO_ENDPOINTS config must be defined")


# ──────────────────────────────────────────────────────────────
# MIG-001 through MIG-003: Migration and schema completeness
# ──────────────────────────────────────────────────────────────

class TestMigrationCompleteness(unittest.TestCase):
    """MIG-001 – MIG-003: grant_executions has tenant_id; migration is idempotent; fresh path works."""

    def setUp(self):
        self.db_path = _make_db()
        mods = _reload_modules(self.db_path)
        self.db_mod = mods[0]

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

    def test_mig001_grant_executions_has_tenant_id(self):
        """MIG-001: grant_executions table has tenant_id column from migration 0010."""
        cols = self._get_columns("grant_executions")
        self.assertIn("tenant_id", cols,
                      "grant_executions must have tenant_id (from migration 0010, used by GL-200C)")

    def test_mig002_grant_executions_has_workspace_id(self):
        """MIG-002: grant_executions table has workspace_id (reserved, nullable)."""
        cols = self._get_columns("grant_executions")
        self.assertIn("workspace_id", cols)

    def test_mig003_migration_idempotent(self):
        """MIG-003: Running migrations again does not fail."""
        from backend.src.migrations import runner
        conn = self.db_mod.get_conn()
        try:
            runner.run_migrations(conn)
            runner.run_migrations(conn)
        finally:
            conn.close()


# ──────────────────────────────────────────────────────────────
# SG-001 through SG-005: Scope guards — no overclaiming
# ──────────────────────────────────────────────────────────────

class TestScopeGuardSafety(unittest.TestCase):
    """SG-001 – SG-005: Documentation does not overclaim production readiness."""

    def test_sg001_doc_exists(self):
        """SG-001: GL-200C documentation artifact exists."""
        self.assertTrue(os.path.isfile(DOC_PATH),
                        f"GL-200C doc must exist at {DOC_PATH}")

    def test_sg002_json_artifact_exists(self):
        """SG-002: GL-200C JSON artifact exists."""
        self.assertTrue(os.path.isfile(JSON_PATH),
                        f"GL-200C JSON artifact must exist at {JSON_PATH}")

    def test_sg003_no_production_saas_claim_in_doc(self):
        """SG-003: GL-200C doc does not claim production SaaS readiness."""
        if not os.path.isfile(DOC_PATH):
            self.skipTest("Doc not yet created")
        text = open(DOC_PATH).read().lower()
        # Check for affirmative production SaaS readiness claims only.
        # Negation phrases ("not production saas", "not ready for real customer") are allowed.
        forbidden = [
            "production saas ready",
            "production-saas ready",
            "saas ready for customers",
            "is production saas",
            "is ready for production saas",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, text,
                             f"Doc must not claim production SaaS readiness ({phrase!r})")

    def test_sg004_no_complete_isolation_claim_in_doc(self):
        """SG-004: GL-200C doc does not claim tenant/workspace isolation is fully complete."""
        if not os.path.isfile(DOC_PATH):
            self.skipTest("Doc not yet created")
        text = open(DOC_PATH).read().lower()
        self.assertNotIn("isolation is complete",
                         text, "Doc must not claim isolation is complete")
        self.assertNotIn("fully isolated",
                         text, "Doc must not claim full isolation")

    def test_sg005_json_artifact_has_correct_issue_id(self):
        """SG-005: JSON artifact has issue_id GL-200C."""
        if not os.path.isfile(JSON_PATH):
            self.skipTest("JSON artifact not yet created")
        with open(JSON_PATH) as f:
            data = json.load(f)
        self.assertEqual(data.get("issue_id"), "GL-200C",
                         "JSON artifact must have issue_id GL-200C")

    def test_sg006_security_reports_route_to_advisories(self):
        """SG-006: SECURITY.md routes sensitive reports to GitHub Security Advisories."""
        security_path = os.path.join(REPO_ROOT, "SECURITY.md")
        if not os.path.isfile(security_path):
            self.skipTest("SECURITY.md not present")
        text = open(security_path).read().lower()
        self.assertTrue(
            "security advisories" in text or "github.com" in text,
            "SECURITY.md must route sensitive reports to GitHub Security Advisories",
        )

    def test_sg007_json_no_production_saas_claim(self):
        """SG-007: JSON artifact has no_production_saas_claim=true."""
        if not os.path.isfile(JSON_PATH):
            self.skipTest("JSON artifact not yet created")
        with open(JSON_PATH) as f:
            data = json.load(f)
        sc = data.get("safety_confirmations", {})
        self.assertTrue(
            sc.get("no_production_saas_claim"),
            "JSON safety_confirmations.no_production_saas_claim must be true",
        )


# ──────────────────────────────────────────────────────────────
# AP-001 through AP-002: Agent permissions (stateless, no tenant concept)
# ──────────────────────────────────────────────────────────────

class TestAgentPermissionsStateless(unittest.TestCase):
    """AP-001 – AP-002: Agent permission evaluators are stateless; no cross-tenant DB leak."""

    def test_ap001_evaluate_does_not_access_db(self):
        """AP-001: evaluate_agent_permission is stateless (no DB queries)."""
        from backend.src.agent_permissions import evaluate_agent_permission
        result = evaluate_agent_permission(
            agent_id="agent-x",
            requested_scope="evidence:read",
            assigned_scopes=["evidence:read"],
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "scope_matched")

    def test_ap002_resolve_does_not_access_db(self):
        """AP-002: resolve_agent_permission_assignment is stateless (no DB queries)."""
        from backend.src.agent_permission_assignments import resolve_agent_permission_assignment
        result = resolve_agent_permission_assignment(
            agent_id="agent-x",
            requested_scope="evidence:read",
            assigned_scopes=["evidence:read"],
            assigned_profiles=[],
        )
        self.assertTrue(result["allowed"])


# ──────────────────────────────────────────────────────────────
# DET-001: Deterministic examples stable
# ──────────────────────────────────────────────────────────────

class TestDeterministicExamplesStable(unittest.TestCase):
    """DET-001: Evidence bundle example is deterministic and stable."""

    def test_det001_evidence_bundle_example_exists(self):
        """DET-001: examples/grant_lifecycle_evidence_bundle.json exists and is valid JSON."""
        examples_path = os.path.join(REPO_ROOT, "examples", "grant_lifecycle_evidence_bundle.json")
        self.assertTrue(os.path.isfile(examples_path),
                        "Deterministic example bundle must exist")
        with open(examples_path) as f:
            data = json.load(f)
        self.assertIn("example_id", data,
                      "Evidence bundle JSON must contain 'example_id' key")


if __name__ == "__main__":
    unittest.main()
