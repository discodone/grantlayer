#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -gt 1 ]; then
  echo "usage: scripts/verify-first-output.sh [output_path]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REFERENCE_PATH="${REPO_ROOT}/examples/first_verifiable_output.json"
OUTPUT_PATH="${1:-/tmp/grantlayer_first_output_verify.json}"

echo "Running first verifiable output generator..."
if ! python3 "${REPO_ROOT}/examples/first_verifiable_output.py" --output "${OUTPUT_PATH}"; then
  echo "ERROR: generator failed" >&2
  exit 1
fi

echo "Comparing generated output with committed reference..."
if cmp -s "${OUTPUT_PATH}" "${REFERENCE_PATH}"; then
  echo "MATCH: ${OUTPUT_PATH}"
  exit 0
fi

echo "MISMATCH: ${OUTPUT_PATH} does not match ${REFERENCE_PATH}" >&2
diff -u "${REFERENCE_PATH}" "${OUTPUT_PATH}" >&2 || true
exit 1
