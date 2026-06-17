#!/usr/bin/env bash
# Seed an initial system-admin user (idempotent). Reads admin creds from .env or args.
#   KOORM_ADMIN_EMAIL / KOORM_ADMIN_PASSWORD  (defaults: admin@kooremapper.local / admin)
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

[ -f "$API_SIF" ] || "$SCRIPT_DIR/build.sh"

echo "→ seeding admin user"
"$APPTAINER" exec \
  --bind "$REPO_ROOT:/workspace" \
  --env "KOORM_DATABASE_URL=${KOORM_DATABASE_URL}" \
  --env "KOORM_JWT_SECRET=${KOORM_JWT_SECRET}" \
  --env "KOORM_ADMIN_EMAIL=${KOORM_ADMIN_EMAIL:-admin@kooremapper.local}" \
  --env "KOORM_ADMIN_PASSWORD=${KOORM_ADMIN_PASSWORD:-admin}" \
  "$API_SIF" \
  sh -c 'cd /workspace/platform/backend && python -m app.seed'
echo "✓ seed complete"
