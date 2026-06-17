#!/usr/bin/env bash
# Shared env for KooRemapper Platform Apptainer orchestration.
set -euo pipefail

# Absolute dir of the scripts (stable regardless of CWD or how $0 was invoked).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# platform/infra/scripts -> repo root (KooRemapper/)
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PLATFORM_ROOT="$REPO_ROOT/platform"
cd "$REPO_ROOT"

[ -f "$PLATFORM_ROOT/.env" ] || {
  echo "✗ platform/.env not found. Run: cp platform/.env.example platform/.env"
  exit 1
}
set -a; . "$PLATFORM_ROOT/.env"; set +a

# Placeholder secret guard (skip with ALLOW_PLACEHOLDER_SECRETS=1).
if [ "${ALLOW_PLACEHOLDER_SECRETS:-0}" != "1" ]; then
  if grep -qE '^(POSTGRES_PASSWORD|KOORM_JWT_SECRET)=CHANGE_ME_' "$PLATFORM_ROOT/.env" \
     || grep -qE '^KOORM_DATABASE_URL=[^/]*//[^:]*:CHANGE_ME_' "$PLATFORM_ROOT/.env"; then
    echo "✗ platform/.env still has CHANGE_ME_* placeholders — rotate POSTGRES_PASSWORD / KOORM_JWT_SECRET"
    echo "  (and the password inside KOORM_DATABASE_URL). Bypass with ALLOW_PLACEHOLDER_SECRETS=1 for throwaway envs."
    exit 1
  fi
fi

# ── Paths ───────────────────────────────────────────────────────────
APPT_DIR="$PLATFORM_ROOT/infra/apptainer"
DATA_DIR="$PLATFORM_ROOT/infra/data"
mkdir -p "$DATA_DIR/postgres" "$DATA_DIR/postgres-run"

POSTGRES_SIF="$APPT_DIR/postgres.sif"
API_SIF="$APPT_DIR/api.sif"
MCP_SIF="$APPT_DIR/mcp.sif"

INST_POSTGRES=koorm_postgres
INST_API=koorm_api
INST_MCP=koorm_mcp

: "${POSTGRES_PORT:=5433}"
: "${KOORM_API_PORT:=8700}"
: "${KOORM_MCP_PORT:=8701}"

# Prefer a local extracted apptainer (no D-Bus / systemd-cgroups requirement).
if [ -z "${APPTAINER:-}" ]; then
  for _c in "$APPT_DIR"/bin-*/usr/bin/apptainer \
            "$HOME"/claude/HWAXPortal/infra/apptainer/bin-*/usr/bin/apptainer \
            "$HOME"/claude/MXWhitePaper/infra/apptainer/bin-*/usr/bin/apptainer; do
    [ -x "$_c" ] && { APPTAINER="$_c"; break; }
  done
fi
: "${APPTAINER:=apptainer}"

require_apptainer() {
  command -v "$APPTAINER" >/dev/null 2>&1 || { echo "✗ '$APPTAINER' not found"; exit 1; }
}

instance_running() {
  "$APPTAINER" instance list --json 2>/dev/null | grep -q "\"instance\": *\"$1\"" || return 1
}
