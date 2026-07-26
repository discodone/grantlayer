"""The api-group middleware must NOT consult request.state.rate_limit_override
(gl-412 fix C).

The per-workspace rate_limit_override gates ONLY the per-subject exercise
seam (which resolves the workspace row per-request). The api-group middleware
has no workspace context — its per-workspace dimension is the signature-
verified JWT plan_tier claim — so the request.state.rate_limit_override read
was a dead half-feature: read at app.py, written by nothing. This pins its
removal: even if some outer middleware DID set the attribute, the api-group
limiter ignores it.

RED before the fix: the dead read exists, so an injected state value IS
honored by the api-group limiter and the second request 429s.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(_FASTAPI_AVAILABLE, "FastAPI not installed")

if _FASTAPI_AVAILABLE:
    import backend.src.core.config as _cfg
    import backend.src.core.db as _db
    from backend.src.api.app import create_app


@_SKIP
class TestApiGroupIgnoresStateOverride(unittest.TestCase):
    def setUp(self):
        self._orig_db = _db.DB_PATH_OR_URL
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        app = create_app()

        # Outermost middleware (added last): injects the attribute the old
        # api-group code used to read. Post-fix this must have NO effect.
        @app.middleware("http")
        async def _inject_override(request, call_next):
            request.state.rate_limit_override = 1
            return await call_next(request)

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        _db.DB_PATH_OR_URL = self._orig_db
        _db.DB_PATH = self._orig_db
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def test_injected_state_override_does_not_gate_api_group(self):
        # Two unauthenticated /v1/ requests. With the dead read present, the
        # injected override=1 caps the api-group bucket at 1 and the second
        # request 429s. With the read removed, both pass the limiter (the
        # endpoint's own 401/403 is fine — just NOT 429).
        first = self.client.get("/v1/grants")
        self.assertNotEqual(first.status_code, 429, first.text)
        second = self.client.get("/v1/grants")
        self.assertNotEqual(
            second.status_code, 429,
            "api-group limiter must not consult request.state."
            "rate_limit_override — the workspace override is exercise-seam-only",
        )


if __name__ == "__main__":
    unittest.main()
