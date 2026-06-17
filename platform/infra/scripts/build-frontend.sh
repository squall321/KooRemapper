#!/usr/bin/env bash
# Build the React SPA into platform/frontend/dist (served by the API instance).
set -euo pipefail
. "$(dirname "$0")/_common.sh"

FE="$PLATFORM_ROOT/frontend"
cd "$FE"
if ! command -v pnpm >/dev/null 2>&1; then
  echo "✗ pnpm not found — install Node 18+ and pnpm to build the frontend"
  exit 1
fi
echo "→ pnpm install"
pnpm install
echo "→ pnpm build"
pnpm build
echo "✓ SPA built at $FE/dist — restart api to serve it: infra/scripts/restart.sh"
