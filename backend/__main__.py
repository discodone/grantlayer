"""Entry point: python3 -m backend"""
import os
from backend.src.server import run

HOST = os.environ.get("GRANTLAYER_HOST", "127.0.0.1")
PORT = int(os.environ.get("GRANTLAYER_PORT", "8765"))

run(host=HOST, port=PORT)
