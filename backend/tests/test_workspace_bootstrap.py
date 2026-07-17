"""Workspace bootstrap — RED tests: deliberate creation of ONE real workspace.

These reference not-yet-existing code, so each test fails at import FIRST
(the import is the first statement in every method):
  - backend.src.workspaces.bootstrap.bootstrap_workspace
  - backend.src.workspaces.bootstrap.OwnerOperatorInvalid
  - backend.src.workspaces.bootstrap.WorkspaceBootstrapConflict

Pinned contract:
  result = bootstrap_workspace(
      session,
      tenant_id=..., name=..., slug=..., owner_operator_id=...,
      description=None, plan_tier="free",
  )
  - creates the workspaces row (id = uuid4 string, status "active"),
  - creates the owner workspace_members row (role "workspace_owner"),
  - appends EXACTLY TWO audit events (workspace_created, workspace_member_added)
    on the SAME session/transaction, both with workspace_id = the new uuid,
  - commits itself; ANY failure (including an audit-write failure) rolls back
    everything — no partial workspace,
  - identical re-run: {"status": "already_exists"}, writes nothing,
  - same (tenant_id, slug) but different name/owner: WorkspaceBootstrapConflict,
  - missing / inactive / wrong-tenant owner operator: OwnerOperatorInvalid,
    nothing written (fail-closed, no orphan owners).

Stable patch seam the GREEN code must expose:
  backend.src.workspaces.bootstrap.append_event  (module attribute)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_TENANT = "hofer"
_NAME = "hofercloud"
_SLUG = "hofercloud"


def _make_db_maker():
    """Temp-file SQLite sessionmaker with all ORM tables created."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.src.core.orm import Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False), path


def _insert_operator(
    maker,
    *,
    tenant_id: str = _TENANT,
    active: int = 1,
    role: str = "owner",
) -> str:
    """Insert an operator row directly (the bootstrap must not create operators)."""
    from backend.src.core.orm import Operator

    op_id = str(uuid.uuid4())
    with maker() as s:
        s.add(
            Operator(
                id=op_id,
                name="anton",
                role=role,
                token_hash="x" * 64,
                active=active,
                created_at="2026-07-17T00:00:00Z",
                tenant_id=tenant_id,
            )
        )
        s.commit()
    return op_id


def _counts(maker, workspace_id: str | None = None) -> dict:
    from sqlalchemy import text

    with maker() as s:
        ws = s.execute(text("SELECT COUNT(*) FROM workspaces")).scalar()
        mem = s.execute(text("SELECT COUNT(*) FROM workspace_members")).scalar()
        if workspace_id is None:
            ev = s.execute(text("SELECT COUNT(*) FROM audit_events")).scalar()
        else:
            ev = s.execute(
                text("SELECT COUNT(*) FROM audit_events WHERE workspace_id = :w"),
                {"w": workspace_id},
            ).scalar()
        return {"workspaces": ws, "members": mem, "events": ev}


def _run_bootstrap(maker, op_id: str, **overrides):
    from backend.src.workspaces.bootstrap import bootstrap_workspace

    kwargs = dict(
        tenant_id=_TENANT,
        name=_NAME,
        slug=_SLUG,
        owner_operator_id=op_id,
        description="Hofercloud production workspace",
    )
    kwargs.update(overrides)
    with maker() as session:
        return bootstrap_workspace(session, **kwargs)


class TestBootstrapCreates(unittest.TestCase):
    def test_creates_workspace_row_with_correct_fields(self) -> None:
        from backend.src.core.orm import Workspace

        maker, _ = _make_db_maker()
        op_id = _insert_operator(maker)
        result = _run_bootstrap(maker, op_id)

        self.assertEqual(result["status"], "created")
        ws_id = result["workspace_id"]
        # opaque-uuid invariant: the id must parse as a UUID, not be the slug
        uuid.UUID(ws_id)
        self.assertNotEqual(ws_id, _SLUG)

        with maker() as s:
            row = s.get(Workspace, ws_id)
            self.assertIsNotNone(row)
            self.assertEqual(row.tenant_id, _TENANT)
            self.assertEqual(row.name, _NAME)
            self.assertEqual(row.slug, _SLUG)
            self.assertEqual(row.owner_id, op_id)
            self.assertEqual(row.status, "active")
            self.assertEqual(row.plan_tier, "free")
            self.assertEqual(row.description, "Hofercloud production workspace")
            self.assertTrue(row.created_at)
            self.assertEqual(row.created_at, row.updated_at)

    def test_creates_owner_membership_row(self) -> None:
        from sqlalchemy import select

        from backend.src.core.orm import WorkspaceMember

        maker, _ = _make_db_maker()
        op_id = _insert_operator(maker)
        ws_id = _run_bootstrap(maker, op_id)["workspace_id"]

        with maker() as s:
            rows = (
                s.execute(
                    select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws_id)
                )
                .scalars()
                .all()
            )
            self.assertEqual(len(rows), 1)
            mem = rows[0]
            self.assertEqual(mem.operator_id, op_id)
            self.assertEqual(mem.role, "workspace_owner")
            self.assertEqual(mem.status, "active")
            self.assertEqual(mem.invited_by, "bootstrap")
            self.assertTrue(mem.joined_at)

    def test_appends_exactly_two_audit_events(self) -> None:
        from sqlalchemy import text

        maker, _ = _make_db_maker()
        op_id = _insert_operator(maker)
        ws_id = _run_bootstrap(maker, op_id)["workspace_id"]

        with maker() as s:
            rows = s.execute(
                text(
                    "SELECT action, subject_id, approved, reason, tenant_id, "
                    "row_hash, prev_hash, seq FROM audit_events "
                    "WHERE workspace_id = :w ORDER BY seq ASC"
                ),
                {"w": ws_id},
            ).fetchall()
            total = s.execute(text("SELECT COUNT(*) FROM audit_events")).scalar()

        self.assertEqual(total, 2)  # exactly two — nothing else appended
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].action, "workspace_created")
        self.assertEqual(rows[1].action, "workspace_member_added")
        for row in rows:
            self.assertEqual(row.subject_id, op_id)
            self.assertEqual(row.approved, 1)
            self.assertEqual(row.tenant_id, _TENANT)
            self.assertTrue(row.row_hash)
        # entry 1 and entry 2 of the new chain: hash-linked in seq order
        self.assertEqual(rows[1].prev_hash, rows[0].row_hash)


class TestBootstrapAtomicity(unittest.TestCase):
    def test_audit_failure_rolls_back_everything(self) -> None:
        import backend.src.workspaces.bootstrap as bootstrap_mod
        from backend.src.workspaces.bootstrap import bootstrap_workspace

        maker, _ = _make_db_maker()
        op_id = _insert_operator(maker)

        real_append = bootstrap_mod.append_event
        calls: list[int] = []

        def _fail_on_second(event, conn=None):
            calls.append(1)
            if len(calls) >= 2:
                raise RuntimeError("simulated audit write failure")
            real_append(event, conn=conn)

        with mock.patch.object(bootstrap_mod, "append_event", _fail_on_second):
            with maker() as session:
                with self.assertRaises(RuntimeError):
                    bootstrap_workspace(
                        session,
                        tenant_id=_TENANT,
                        name=_NAME,
                        slug=_SLUG,
                        owner_operator_id=op_id,
                    )

        # full rollback: no workspace, no membership, no audit events at all
        self.assertEqual(
            _counts(maker), {"workspaces": 0, "members": 0, "events": 0}
        )


class TestBootstrapIdempotency(unittest.TestCase):
    def test_identical_rerun_reports_already_exists_and_writes_nothing(self) -> None:
        maker, _ = _make_db_maker()
        op_id = _insert_operator(maker)

        first = _run_bootstrap(maker, op_id)
        before = _counts(maker)
        second = _run_bootstrap(maker, op_id)

        self.assertEqual(first["status"], "created")
        self.assertEqual(second["status"], "already_exists")
        self.assertEqual(second["workspace_id"], first["workspace_id"])
        self.assertEqual(_counts(maker), before)  # not one row more, anywhere
        self.assertEqual(before["workspaces"], 1)
        self.assertEqual(before["members"], 1)
        self.assertEqual(before["events"], 2)

    def test_conflicting_existing_workspace_is_hard_error(self) -> None:
        from backend.src.workspaces.bootstrap import WorkspaceBootstrapConflict

        maker, _ = _make_db_maker()
        op_id = _insert_operator(maker)
        _run_bootstrap(maker, op_id)
        before = _counts(maker)

        # same (tenant_id, slug), different name → refuse, write nothing
        with self.assertRaises(WorkspaceBootstrapConflict):
            _run_bootstrap(maker, op_id, name="something-else")

        # same (tenant_id, slug), different owner → refuse, write nothing
        other_op = _insert_operator(maker)
        with self.assertRaises(WorkspaceBootstrapConflict):
            _run_bootstrap(maker, other_op)

        self.assertEqual(_counts(maker), before)


class TestBootstrapOperatorGate(unittest.TestCase):
    def test_missing_operator_refused(self) -> None:
        from backend.src.workspaces.bootstrap import OwnerOperatorInvalid

        maker, _ = _make_db_maker()
        with self.assertRaises(OwnerOperatorInvalid):
            _run_bootstrap(maker, str(uuid.uuid4()))
        self.assertEqual(
            _counts(maker), {"workspaces": 0, "members": 0, "events": 0}
        )

    def test_inactive_operator_refused(self) -> None:
        from backend.src.workspaces.bootstrap import OwnerOperatorInvalid

        maker, _ = _make_db_maker()
        op_id = _insert_operator(maker, active=0)
        with self.assertRaises(OwnerOperatorInvalid):
            _run_bootstrap(maker, op_id)
        self.assertEqual(
            _counts(maker), {"workspaces": 0, "members": 0, "events": 0}
        )

    def test_wrong_tenant_operator_refused(self) -> None:
        from backend.src.workspaces.bootstrap import OwnerOperatorInvalid

        maker, _ = _make_db_maker()
        op_id = _insert_operator(maker, tenant_id="demo")
        with self.assertRaises(OwnerOperatorInvalid):
            _run_bootstrap(maker, op_id)
        self.assertEqual(
            _counts(maker), {"workspaces": 0, "members": 0, "events": 0}
        )

    def test_invalid_plan_tier_refused(self) -> None:
        from backend.src.workspaces.bootstrap import WorkspaceBootstrapError

        maker, _ = _make_db_maker()
        op_id = _insert_operator(maker)
        with self.assertRaises(WorkspaceBootstrapError):
            _run_bootstrap(maker, op_id, plan_tier="platinum")
        self.assertEqual(
            _counts(maker), {"workspaces": 0, "members": 0, "events": 0}
        )


class TestBootstrapCli(unittest.TestCase):
    """The ceremony script: explicit args, env-driven DB, refuse-to-clobber."""

    def _run_cli(self, db_path: str, *extra: str) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "bootstrap_workspace.py"),
            *extra,
        ]
        env = {**os.environ, "GRANTLAYER_DB": db_path}
        env.pop("GRANTLAYER_DATABASE_URL", None)
        return subprocess.run(
            cmd, capture_output=True, text=True, env=env, cwd=str(_REPO_ROOT)
        )

    def test_cli_creates_then_noops_then_refuses_conflict(self) -> None:
        maker, db_path = _make_db_maker()
        op_id = _insert_operator(maker)
        args = [
            "--tenant-id", _TENANT,
            "--name", _NAME,
            "--slug", _SLUG,
            "--owner-operator-id", op_id,
        ]

        created = self._run_cli(db_path, *args)
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertIn("created", created.stdout.lower())
        self.assertEqual(_counts(maker)["workspaces"], 1)

        rerun = self._run_cli(db_path, *args)
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertIn("already exists", rerun.stdout.lower())
        self.assertEqual(_counts(maker)["workspaces"], 1)

        conflict = self._run_cli(
            db_path,
            "--tenant-id", _TENANT,
            "--name", "different-name",
            "--slug", _SLUG,
            "--owner-operator-id", op_id,
        )
        self.assertNotEqual(conflict.returncode, 0)
        self.assertEqual(_counts(maker)["workspaces"], 1)

    def test_cli_refuses_missing_operator(self) -> None:
        _, db_path = _make_db_maker()
        result = self._run_cli(
            db_path,
            "--tenant-id", _TENANT,
            "--name", _NAME,
            "--slug", _SLUG,
            "--owner-operator-id", str(uuid.uuid4()),
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
