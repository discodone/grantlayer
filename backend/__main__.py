"""Entry point: python3 -m backend — starts FastAPI via uvicorn."""
import os
import uvicorn

HOST = os.environ.get("GRANTLAYER_HOST", "127.0.0.1")
PORT = int(os.environ.get("GRANTLAYER_PORT", "8765"))

uvicorn.run(
    "backend.src.api.app:app",
    host=HOST,
    port=PORT,
    access_log=False,
)
