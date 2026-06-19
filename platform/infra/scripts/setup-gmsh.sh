#!/usr/bin/env bash
# Make the bundled gmsh discoverable by meshfix: KooRemapper's findGmshExe looks
# for <binary_dir>/gmsh/gmsh.exe. Symlink it to dist/gmsh/gmsh (relative, so it
# resolves inside the api container at /workspace too). gmsh runtime libs are in
# api.def. Run once after the binary is built/copied into platform/backend/bin/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BIN="$ROOT/platform/backend/bin"
[ -f "$ROOT/dist/gmsh/gmsh" ] || { echo "✗ dist/gmsh/gmsh not found"; exit 1; }
[ -d "$BIN" ] || { echo "✗ $BIN missing — build with -DKOOREMAPPER_PLATFORM_BIN first"; exit 1; }
mkdir -p "$BIN/gmsh"
ln -sf ../../../../dist/gmsh/gmsh "$BIN/gmsh/gmsh.exe"
echo "✓ gmsh linked at $BIN/gmsh/gmsh.exe (meshfix ready)"
