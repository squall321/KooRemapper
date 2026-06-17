#!/usr/bin/env bash
# Run Alembic migrations inside the api image against the running postgres.
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

[ -f "$API_SIF" ] || "$SCRIPT_DIR/build.sh"

echo "→ alembic upgrade head"
"$APPTAINER" exec \
  --bind "$REPO_ROOT:/workspace" \
  --env "KOORM_DATABASE_URL=${KOORM_DATABASE_URL}" \
  "$API_SIF" \
  sh -c 'cd /workspace/platform/backend && alembic upgrade head'
echo "✓ migrations applied"
