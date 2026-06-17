#!/usr/bin/env bash
# Build the postgres + api .sif images. Idempotent (skips existing; --force rebuilds).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

build_one() {
  local sif="$1" def="$2"
  if [ "$FORCE" -eq 1 ] || [ ! -f "$sif" ]; then
    echo "→ build $(basename "$sif")"
    "$APPTAINER" build --force "$sif" "$def"
  else
    echo "✓ skip $(basename "$sif") (exists)"
  fi
}

build_one "$POSTGRES_SIF" "$APPT_DIR/postgres.def"
build_one "$API_SIF"      "$APPT_DIR/api.def"
build_one "$MCP_SIF"      "$APPT_DIR/mcp.def"
echo "✓ images ready in $APPT_DIR"
