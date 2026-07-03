#!/usr/bin/env bash
# 배치/HPC job용 경량 KooRemapper CLI SIF(자체완결)를 빌드한다.
# Build the stateless CLI SIF (binary + gmsh + material DB baked in).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

CLI_SIF="$APPT_DIR/cli.sif"
[ -f "$REPO_ROOT/build/linux/bin/KooRemapper" ] || {
  echo "✗ build/linux/bin/KooRemapper missing — build the base tool first"; exit 1; }

echo "→ build cli.sif (self-contained CLI for batch jobs)"
# Build from the def dir so relative %files (../../../build, dist, materials) resolve.
( cd "$APPT_DIR" && "$APPTAINER" build --force cli.sif cli.def )
echo "✓ $CLI_SIF"
echo "  run: apptainer run --bind \"\$PWD:/work\" --pwd /work $CLI_SIF <op> [args...]"
