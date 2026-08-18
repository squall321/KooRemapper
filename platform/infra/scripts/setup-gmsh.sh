#!/usr/bin/env bash
# Make the bundled gmsh discoverable by meshfix: KooRemapper's findGmshExe looks
# for <binary_dir>/gmsh/gmsh.exe. Symlink it to dist/gmsh/gmsh (relative, so it
# resolves inside the api container at /workspace too). gmsh runtime libs are in
# api.def. Run once after the binary is built/copied into platform/backend/bin/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BIN="$ROOT/platform/backend/bin"
# 배포본은 아티팩트에 gmsh 실체가 이미 들어 있다(dist-to-drive 가 -h 로 역참조해 담는다).
# 그 경우 링크할 것이 없고 이미 준비된 상태다 — 여기서 '없다'고 하면 되는 걸 안 된다고 말하게 된다.
if [ -f "$BIN/gmsh/gmsh.exe" ] && [ ! -L "$BIN/gmsh/gmsh.exe" ] && [ -s "$BIN/gmsh/gmsh.exe" ]; then
  echo "✓ gmsh 실체가 이미 $BIN/gmsh/gmsh.exe 에 있다 (meshfix ready)"; exit 0
fi
[ -f "$ROOT/dist/gmsh/gmsh" ] || { echo "✗ dist/gmsh/gmsh not found"; exit 1; }
[ -d "$BIN" ] || { echo "✗ $BIN missing — build with -DKOOREMAPPER_PLATFORM_BIN first"; exit 1; }
mkdir -p "$BIN/gmsh"
ln -sf ../../../../dist/gmsh/gmsh "$BIN/gmsh/gmsh.exe"
echo "✓ gmsh linked at $BIN/gmsh/gmsh.exe (meshfix ready)"
