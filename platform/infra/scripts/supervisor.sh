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
  # 재기동 '이유'와 '결과'를 전부 버리고 있었다 — 인스턴스가 없어서인지 헬스가 안 붙어서인지,
  # 재기동이 성공했는지 실패했는지가 로그에 없다. 그래서 5주간 1,459회가 원인 없이 쌓였고
  # 같은 실패를 매분 반복하는 상태와 정상 복구를 구분할 수 없었다.
  _api_reason=""
  if ! instance_running "$INST_API"; then
    _api_reason="인스턴스 없음"
  elif ! _api_code="$(curl -s -o /dev/null -w '%{http_code}' -m3 "http://127.0.0.1:${KOORM_API_PORT}/api/health" 2>/dev/null)"; then
    _api_reason="헬스 조회 실패"
  else
    case "${_api_code:-000}" in 2??|3??) : ;; *) _api_reason="헬스 HTTP ${_api_code:-000}" ;; esac
  fi
  if [ -n "$_api_reason" ]; then
    echo "[$(date '+%F %T')] api down ($_api_reason) → restart-api-only.sh"
    if "$SCRIPT_DIR/restart-api-only.sh" >/tmp/koorm-restart-api.log 2>&1; then
      echo "[$(date '+%F %T')] api restart 성공"
    else
      echo "[$(date '+%F %T')] api restart 실패(rc=$?) — /tmp/koorm-restart-api.log"
      tail -5 /tmp/koorm-restart-api.log | sed 's/^/    /'
    fi
  fi
  # mcp: restart instance if gone
  if ! instance_running "$INST_MCP"; then
    echo "[$(date '+%F %T')] mcp down → start"
    local net=(); [ "${KOORM_APPT_HOST_NET:-0}" = "1" ] && net=(--net --network=host)
    "$APPTAINER" instance start "${net[@]}" --bind "$REPO_ROOT:/workspace" \
      --env "KOOREMAPPER_API_BASE=http://127.0.0.1:${KOORM_API_PORT}" \
      --env "KOORM_MCP_PORT=${KOORM_MCP_PORT}" --env "MCP_HOST=${MCP_HOST:-127.0.0.1}" \
      --env "MCP_ALLOWED_HOSTS=${MCP_ALLOWED_HOSTS:-}" "$MCP_SIF" "$INST_MCP" >/tmp/koorm-restart-mcp.log 2>&1 \
      && echo "[$(date '+%F %T')] mcp restart 성공" \
      || { echo "[$(date '+%F %T')] mcp restart 실패 — /tmp/koorm-restart-mcp.log"; tail -5 /tmp/koorm-restart-mcp.log | sed 's/^/    /'; }
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
