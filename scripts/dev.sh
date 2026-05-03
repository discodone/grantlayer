#!/usr/bin/env bash
# Start GrantLayer MVP backend (serves dashboard too)
set -e
cd "$(dirname "$0")/.."
HOST="${GRANTLAYER_HOST:-127.0.0.1}"
PORT="${GRANTLAYER_PORT:-8765}"
echo "Starting GrantLayer MVP on http://$HOST:$PORT ..."
python3 -m backend
