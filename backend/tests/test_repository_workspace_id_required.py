"""Repository-layer invariant: create() requires an explicit, non-empty workspace_id.

Since the workspace-bootstrap series, every caller resolves a concrete workspace
before reaching the repository layer. A falsy workspace_id ("" or None) at
create() is therefore a server-side invariant violation, not a demo convenience —
it must RAISE, never be silently coerced to the demo "default" workspace.

The guard is the first statement in every create(), before any DB access, so
these tests exercise it with a mock session (no database is touched).
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from backend.src.core.repositories_sqlalchemy import (
    SqlAlchemyAsyncGrantExecutionRepository,
    SqlAlchemyAsyncGrantRepository,
    SqlAlchemyAsyncGrantRequestRepository,
    SqlAlchemyGrantExecutionRepository,
    SqlAlchemyGrantRepository,
    SqlAlchemyGrantRequestRepository,
)

_FALSY_WORKSPACES = ("", None)


class TestSyncRepositoryRequiresWorkspaceId(unittest.TestCase):
    """The three synchronous create() sites reject a falsy workspace_id."""

    def test_grant_create_rejects_falsy_workspace(self) -> None:
        repo = SqlAlchemyGrantRepository(MagicMock())
        for bad in _FALSY_WORKSPACES:
            with self.assertRaises(ValueError):
                repo.create(MagicMock(), "tenant-a", bad)  # type: ignore[arg-type]

    def test_grant_request_create_rejects_falsy_workspace(self) -> None:
        repo = SqlAlchemyGrantRequestRepository(MagicMock())
        for bad in _FALSY_WORKSPACES:
            with self.assertRaises(ValueError):
                repo.create(MagicMock(), "tenant-a", bad)  # type: ignore[arg-type]

    def test_grant_execution_create_rejects_falsy_workspace(self) -> None:
        repo = SqlAlchemyGrantExecutionRepository(MagicMock())
        for bad in _FALSY_WORKSPACES:
            with self.assertRaises(ValueError):
                repo.create(MagicMock(), "tenant-a", bad)  # type: ignore[arg-type]

    def test_valid_workspace_reaches_db_layer(self) -> None:
        """A non-empty workspace_id passes the guard and hits session.execute()."""
        session = MagicMock()
        repo = SqlAlchemyGrantExecutionRepository(session)
        grant_exec = MagicMock()
        repo.create(grant_exec, "tenant-a", "ws-real")
        session.execute.assert_called_once()


class TestAsyncRepositoryRequiresWorkspaceId(unittest.TestCase):
    """The three asynchronous create() sites reject a falsy workspace_id."""

    def _assert_async_raises(self, coro_factory) -> None:
        for bad in _FALSY_WORKSPACES:
            with self.assertRaises(ValueError):
                asyncio.run(coro_factory(bad))

    def test_async_grant_create_rejects_falsy_workspace(self) -> None:
        repo = SqlAlchemyAsyncGrantRepository(MagicMock())
        self._assert_async_raises(
            lambda bad: repo.create(MagicMock(), "tenant-a", bad)
        )

    def test_async_grant_request_create_rejects_falsy_workspace(self) -> None:
        repo = SqlAlchemyAsyncGrantRequestRepository(MagicMock())
        self._assert_async_raises(
            lambda bad: repo.create(MagicMock(), "tenant-a", bad)
        )

    def test_async_grant_execution_create_rejects_falsy_workspace(self) -> None:
        repo = SqlAlchemyAsyncGrantExecutionRepository(MagicMock())
        self._assert_async_raises(
            lambda bad: repo.create(MagicMock(), "tenant-a", bad)
        )


if __name__ == "__main__":
    unittest.main()
