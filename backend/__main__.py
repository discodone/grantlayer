"""Entry point: python3 -m backend — starts FastAPI via uvicorn."""
import os
import sys

import uvicorn

HOST = os.environ.get("GRANTLAYER_HOST", "127.0.0.1")
PORT = int(os.environ.get("GRANTLAYER_PORT", "8765"))
_SKIP_STARTUP_CHECK_MODES = {"test", "local"}

runtime_mode = os.environ.get("GRANTLAYER_RUNTIME_MODE", "local").strip().lower()
if runtime_mode not in _SKIP_STARTUP_CHECK_MODES:
    from backend.src.core.config import startup_errors
    errors = startup_errors()
    if errors:
        for msg in errors:
            print(msg, file=sys.stderr)
        sys.exit(1)

uvicorn.run(
    "backend.src.api.app:app",
    host=HOST,
    port=PORT,
    access_log=False,
)
