#!/usr/bin/env bash
# Generate a self-signed TLS cert for the nginx proxy.
# Idempotent: skips if both server.crt and server.key already exist (--force regenerates).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="$SCRIPT_DIR/../nginx/certs"
CRT="$CERT_DIR/server.crt"
KEY="$CERT_DIR/server.key"

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

if [ "$FORCE" -eq 0 ] && [ -f "$CRT" ] && [ -f "$KEY" ]; then
  echo "✓ certs already exist in $CERT_DIR (use --force to regenerate)"
  exit 0
fi

mkdir -p "$CERT_DIR"
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout "$KEY" -out "$CRT" \
  -subj "/CN=kooremapper.local"

chmod 600 "$KEY"
echo "✓ generated self-signed cert → $CRT"
