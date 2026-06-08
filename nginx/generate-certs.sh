#!/usr/bin/env bash
# GL-230: Generate a self-signed TLS certificate for local development.
# Run once before `docker compose up`.
# Production: replace nginx/certs/tls.crt + tls.key with a real cert.
set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")/certs" && pwd)"

if [[ -f "$CERT_DIR/tls.crt" && -f "$CERT_DIR/tls.key" ]]; then
    echo "Certs already exist at $CERT_DIR — skipping generation."
    echo "Delete them and re-run this script to regenerate."
    exit 0
fi

mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:4096 -nodes \
    -keyout "$CERT_DIR/tls.key" \
    -out    "$CERT_DIR/tls.crt" \
    -days 365 \
    -subj "/CN=localhost/O=GrantLayer Dev/C=DE" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "Self-signed cert generated:"
echo "  $CERT_DIR/tls.crt"
echo "  $CERT_DIR/tls.key"
echo
echo "NOTE: Browsers will warn about this cert. Add -k to curl or import"
echo "      tls.crt into your browser's trusted CAs for a cleaner experience."
