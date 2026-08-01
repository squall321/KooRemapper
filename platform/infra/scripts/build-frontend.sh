#!/usr/bin/env bash
# Build the React SPA into platform/frontend/dist (served by the API instance).
# 두 번 빌드한다: standalone(base /) + HEAX 포탈 서브패스(base /apps/kooremapper/).
# 포탈 빌드의 해시드 자산은 dist/assets 에 합치고 index 는 index.portal.html 로 —
# 백엔드가 게이트웨이 헤더 유무로 어느 index 를 줄지 고른다 (main.py).
set -euo pipefail
. "$(dirname "$0")/_common.sh"

FE="$PLATFORM_ROOT/frontend"
PORTAL_BASE="${KOORM_PORTAL_BASE:-/apps/kooremapper/}"
cd "$FE"
if ! command -v pnpm >/dev/null 2>&1; then
  echo "✗ pnpm not found — install Node 18+ and pnpm to build the frontend"
  exit 1
fi
echo "→ pnpm install"
pnpm install
echo "→ pnpm build (standalone, base /)"
pnpm build
echo "→ pnpm build (portal, base $PORTAL_BASE)"
VITE_BASE="$PORTAL_BASE" pnpm exec vite build --outDir dist-portal
# 자산 병합(해시 파일명이라 충돌 없음) + 포탈 index 보존
cp -f dist-portal/assets/* dist/assets/
cp -f dist-portal/index.html dist/index.portal.html
rm -rf dist-portal
echo "✓ SPA built at $FE/dist (+ index.portal.html) — restart api to serve it"
