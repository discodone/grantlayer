#!/usr/bin/env bash
# Run GrantLayer MVP tests
set -e
cd "$(dirname "$0")/.."
echo "Running GrantLayer MVP tests..."
python3 -m pytest backend/tests/ -v 2>/dev/null || python3 -m unittest discover -s backend/tests -v
