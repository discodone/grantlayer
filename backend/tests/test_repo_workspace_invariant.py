"""PARKED RED — the repo-layer workspace coercion is still load-bearing.

Desired invariant: a falsy workspace_id at the repository layer raises
ValueError instead of silently coercing to "default" (the six create()
implementations, sync + async, plus create_grant_execution()).

Implementing it turned the full suite red with 129 failures: a broad class
of existing regression tests (the tenant-context contracts in gl200c/gl215
among them) call the module-layer create functions without a workspace and
legitimately depend on the "default" coercion. Per the stop condition the
implementation was reverted and these contract tests are parked as strict
expected-failures. Un-parking requires first migrating those legacy-path
tests (and any real callers they represent) to explicit workspaces — a
decision and its own change, not a sweep.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import asyncio
import os
import tempfile
import unittest

import backend.src.core.db as _db

_TENANT = "tenant-invariant"


def _grant():
    from backend.src.core.models import Grant
    return Grant(
        subject_id="s", role="agent", action="a", resource="r",
        valid_from="2026-01-01T00:00:00Z", valid_until="2027-01-01T00:00:00Z",
        created_by="op", reason="repo invariant test",
    )


def _request():
    from backend.src.core.models import GrantRequest
    return GrantRequest(
        subject_id="s", role="agent", action="a", resource="r",
        valid_from="2026-01-01T00:00:00Z", valid_until="2027-01-01T00:00:00Z",
        requested_by="op", reason="repo invariant test",
    )


def _execution():
    from backend.src.core.models import GrantExecution
    return GrantExecution(action="a", resource="r")


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        self._orig_db = _db.DB_PATH_OR_URL
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

    def tearDown(self):
        _db.DB_PATH_OR_URL = self._orig_db
        _db.DB_PATH = self._orig_db
        try:
            os.unlink(self._db_path)
        except OSError:
            pass


class TestSyncReposRefuseFalsyWorkspace(_Base):
    def _repos(self, session):
        from backend.src.core.repositories_sqlalchemy import (
            SqlAlchemyGrantExecutionRepository,
            SqlAlchemyGrantRepository,
            SqlAlchemyGrantRequestRepository,
        )
        return (
            (SqlAlchemyGrantRepository(session), _grant),
            (SqlAlchemyGrantRequestRepository(session), _request),
            (SqlAlchemyGrantExecutionRepository(session), _execution),
        )

    @unittest.expectedFailure  # parked: coercion still load-bearing
    def test_create_raises_on_falsy_workspace(self):
        from backend.src.core.db import get_session_maker
        with get_session_maker()() as session:
            for repo, make in self._repos(session):
                for falsy in ("", None):
                    with self.subTest(repo=type(repo).__name__, workspace=falsy):
                        with self.assertRaises(ValueError):
                            repo.create(make(), _TENANT, falsy)  # type: ignore[arg-type]


class TestAsyncReposRefuseFalsyWorkspace(_Base):
    @unittest.expectedFailure  # parked: coercion still load-bearing
    def test_create_raises_on_falsy_workspace(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from backend.src.core.repositories_sqlalchemy import (
            SqlAlchemyAsyncGrantExecutionRepository,
            SqlAlchemyAsyncGrantRepository,
            SqlAlchemyAsyncGrantRequestRepository,
        )

        async def run():
            engine = create_async_engine(f"sqlite+aiosqlite:///{self._db_path}")
            maker = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with maker() as session:
                    repos = (
                        (SqlAlchemyAsyncGrantRepository(session), _grant),
                        (SqlAlchemyAsyncGrantRequestRepository(session), _request),
                        (SqlAlchemyAsyncGrantExecutionRepository(session), _execution),
                    )
                    for repo, make in repos:
                        for falsy in ("", None):
                            try:
                                await repo.create(make(), _TENANT, falsy)  # type: ignore[arg-type]
                            except ValueError:
                                continue
                            raise AssertionError(
                                f"{type(repo).__name__}.create accepted workspace_id={falsy!r}"
                            )
            finally:
                await engine.dispose()

        asyncio.run(run())


class TestModuleLayerExecutionFallbackRemoved(_Base):
    @unittest.expectedFailure  # parked: coercion still load-bearing
    def test_create_grant_execution_raises_on_none_workspace(self):
        from backend.src.grants.grant_executions import create_grant_execution
        with self.assertRaises(ValueError):
            create_grant_execution(_execution(), tenant_id=_TENANT, workspace_id=None)


if __name__ == "__main__":
    unittest.main()
