"""GL-291 — FastAPI DI completeness scope guard.

Verifies that API router files do not call get_conn() or import
_ConnectionWrapper directly. Business logic uses the module-level
query helpers (query_one/query_all/execute) which are backed by
SQLAlchemy via get_engine().connect(), or receives a Session via
Depends(get_db).

Remaining legitimate get_conn() callers:
  - backend/src/core/db.py (definition + init_db for migration runner)
  - backend/tests/* (direct DB inspection fixtures — separate concern)
"""
import pathlib

import pytest

ROUTERS_DIR = pathlib.Path("backend/src/api/routers")
FORBIDDEN_IN_ROUTERS = {"get_conn", "_ConnectionWrapper"}
SRC_DIR = pathlib.Path("backend/src")


@pytest.mark.scope_guard
class TestFastAPIDIComplete:
    def test_no_get_conn_in_routers(self):
        """No router may import or call get_conn / _ConnectionWrapper."""
        violations: list[str] = []
        for path in ROUTERS_DIR.glob("*.py"):
            source = path.read_text()
            for name in FORBIDDEN_IN_ROUTERS:
                if name in source:
                    violations.append(f"{path}: contains '{name}'")
        assert not violations, "\n".join(violations)

    def test_grants_router_uses_depends_get_db(self):
        """grants.py router must inject Session via Depends(get_db)."""
        grants_router = ROUTERS_DIR / "grants.py"
        source = grants_router.read_text()
        assert "Depends(get_db)" in source, "grants.py missing Depends(get_db)"
        assert "from ...core.db import get_db" in source, "grants.py missing get_db import"

    def test_get_conn_only_in_db_module(self):
        """get_conn() in backend/src must only appear in core/db.py (definition + init_db)."""
        violations: list[str] = []
        for path in SRC_DIR.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            if path == SRC_DIR / "core" / "db.py":
                continue
            source = path.read_text()
            if "get_conn" in source:
                violations.append(str(path))
        assert not violations, (
            f"Unexpected get_conn() usage outside core/db.py: {violations}\n"
            "Migrate these callers to Session = Depends(get_db) or get_engine().connect()."
        )

    def test_api_layer_has_no_raw_query_calls(self):
        """API router files must not call query_one/query_all/execute from db module."""
        forbidden = {"query_one", "query_all"}
        violations: list[str] = []
        for path in ROUTERS_DIR.glob("*.py"):
            source = path.read_text()
            for name in forbidden:
                if name in source:
                    violations.append(f"{path}: direct '{name}' call")
        assert not violations, "\n".join(violations)
