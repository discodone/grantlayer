#!/usr/bin/env bash
# Idempotent developer environment setup for GrantLayer.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> GrantLayer dev setup"

# --- virtualenv ---
if [ ! -d ".venv" ]; then
    echo "  Creating .venv..."
    python3 -m venv .venv
fi
source .venv/bin/activate
echo "  venv: $(python3 --version)"

# --- pip install ---
echo "  Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet -r requirements-dev.txt

# --- pre-commit ---
if command -v pre-commit &>/dev/null || pip show pre-commit &>/dev/null; then
    echo "  Installing pre-commit hooks..."
    pre-commit install --install-hooks
    pre-commit install --hook-type commit-msg
else
    pip install --quiet pre-commit
    pre-commit install --install-hooks
    pre-commit install --hook-type commit-msg
fi

# --- .env ---
if [ ! -f ".env" ]; then
    echo "  Copying .env.example → .env"
    cp .env.example .env
    echo "  !! Edit .env and set GRANTLAYER_JWT_SECRET or RS256 keys before running."
fi

# --- DB init ---
echo "  Initialising local SQLite DB..."
python3 -c "from backend.src.core.db import init_db; init_db()" 2>/dev/null || true

echo ""
echo "==> Setup complete."
echo "    Activate venv:  source .venv/bin/activate"
echo "    Start server:   python3 -m backend"
echo "    Run tests:      make test"
