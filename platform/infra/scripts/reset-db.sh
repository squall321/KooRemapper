#!/usr/bin/env bash
# DESTRUCTIVE — stop postgres and wipe its data dir, then restart fresh.
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

read -rp "This deletes ALL postgres data in $DATA_DIR/postgres. Type 'yes' to continue: " ans
[ "$ans" = "yes" ] || { echo "aborted"; exit 1; }

instance_running "$INST_POSTGRES" && "$APPTAINER" instance stop "$INST_POSTGRES" || true
rm -rf "$DATA_DIR/postgres" "$DATA_DIR/postgres-run"
mkdir -p "$DATA_DIR/postgres" "$DATA_DIR/postgres-run"
echo "✓ postgres data wiped — run start.sh to recreate"
