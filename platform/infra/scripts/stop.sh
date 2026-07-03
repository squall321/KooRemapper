#!/usr/bin/env bash
# Stop all KooRemapper instances (nginx, mcp, api, postgres — reverse start order).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

for inst in "$INST_NGINX" "$INST_MCP" "$INST_API" "$INST_POSTGRES"; do
  if instance_running "$inst"; then
    echo "→ stop $inst"
    "$APPTAINER" instance stop "$inst" || true
  else
    echo "✓ $inst not running"
  fi
done
