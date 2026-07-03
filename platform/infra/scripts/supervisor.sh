#!/usr/bin/env bash
# Watchdog: periodically ensure postgres/api/mcp instances are up + healthy,
# restarting any that died. Survives idle reaping / crashes.
#   ./supervisor.sh           # loop forever (default 30s interval)
#   ./supervisor.sh --once    # single check (for testing/cron)
#   KOORM_SUPERVISE_INTERVAL=15 ./supervisor.sh
set -uo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

INTERVAL="${KOORM_SUPERVISE_INTERVAL:-30}"
ONCE=0; [ "${1:-}" = "--once" ] && ONCE=1

check_once() {
  # postgres (start full stack if its instance is gone — start.sh is idempotent)
  if ! instance_running "$INST_POSTGRES"; then
    echo "[$(date '+%F %T')] postgres down → start.sh"
    "$SCRIPT_DIR/start.sh" >/dev/null 2>&1 || true
    return
  fi
  # api: restart if instance gone OR health endpoint not answering
  if ! instance_running "$INST_API" || ! curl -fsS -m3 "http://127.0.0.1:${KOORM_API_PORT}/api/health" >/dev/null 2>&1; then
    echo "[$(date '+%F %T')] api down → restart-api-only.sh"
    "$SCRIPT_DIR/restart-api-only.sh" >/dev/null 2>&1 || true
  fi
  # mcp: restart instance if gone
  if ! instance_running "$INST_MCP"; then
    echo "[$(date '+%F %T')] mcp down → start"
    local net=(); [ "${KOORM_APPT_HOST_NET:-0}" = "1" ] && net=(--net --network=host)
    "$APPTAINER" instance start "${net[@]}" --bind "$REPO_ROOT:/workspace" \
      --env "KOOREMAPPER_API_BASE=http://127.0.0.1:${KOORM_API_PORT}" \
      --env "KOORM_MCP_PORT=${KOORM_MCP_PORT}" --env "MCP_HOST=${MCP_HOST:-127.0.0.1}" \
      --env "MCP_ALLOWED_HOSTS=${MCP_ALLOWED_HOSTS:-}" "$MCP_SIF" "$INST_MCP" >/dev/null 2>&1 || true
  fi
  # nginx (only when enabled): restart instance if gone
  if [ "${KOORM_ENABLE_NGINX:-0}" = "1" ] && ! instance_running "$INST_NGINX"; then
    echo "[$(date '+%F %T')] nginx down → start"
    local net2=(); [ "${KOORM_APPT_HOST_NET:-0}" = "1" ] && net2=(--net --network=host)
    [ -f "$PLATFORM_ROOT/infra/nginx/certs/server.crt" ] || "$SCRIPT_DIR/gen-certs.sh" >/dev/null 2>&1 || true
    "$APPTAINER" instance start "${net2[@]}" \
      --bind "$PLATFORM_ROOT/infra/nginx/certs:/etc/nginx/certs:ro" \
      "$NGINX_SIF" "$INST_NGINX" >/dev/null 2>&1 || true
  fi
}

if [ "$ONCE" = 1 ]; then check_once; echo "✓ supervise check done"; exit 0; fi

echo "→ supervisor started (interval ${INTERVAL}s). Ctrl-C to stop."
while true; do check_once; sleep "$INTERVAL"; done
