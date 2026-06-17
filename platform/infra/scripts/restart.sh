#!/usr/bin/env bash
# Restart the api instance to pick up code changes (source is bind-mounted).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

if instance_running "$INST_API"; then
  echo "→ stop $INST_API"
  "$APPTAINER" instance stop "$INST_API" || true
  sleep 1
fi
"$SCRIPT_DIR/start.sh"
