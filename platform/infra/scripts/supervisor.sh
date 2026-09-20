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

# 감독자는 **하나만** 돈다. 둘이면 서로의 재기동을 밟는다 — 한쪽이 stop 한 인스턴스를 다른 쪽이
# "없음" 으로 보고 다시 start 해 `already exists` 가 난다.
# ⚠ 프로세스 이름 매칭으로는 못 막는다(실측): 크론은 `bash /abs/…/supervisor.sh` 로 뜨는데
# README 가 권하는 방식(`nohup infra/scripts/supervisor.sh &`)은 `bash ./infra/scripts/supervisor.sh`
# 라서 절대경로 pgrep 패턴이 빗나간다. 파일 잠금은 **어떻게 띄우든** 통한다.
# 매분 도는 `--once` 가 앞 회차와 겹치는 것도 이 잠금이 막는다.
mkdir -p "$DATA_DIR"
exec 9>"$DATA_DIR/supervisor.lock"
if ! flock -n 9; then
  echo "[$(date '+%F %T')] 이미 감독자가 돌고 있다 — 이번 호출은 아무것도 하지 않는다"
  exit 0
fi

# 인스턴스가 **확실히 없는가** — 재기동은 파괴적 행동이라 "모름" 을 근거로 삼으면 안 된다.
# `instance_running` 은 0 있음 · 1 없음 · **2 알 수 없음**(목록 조회 실패)을 낸다(_common.sh 주석 참조).
# 옛 코드는 1 과 2 를 같은 "없음" 으로 읽었고, 그래서 조회가 실패할 때마다 멀쩡한 API 를 내렸다.
# 2 면 이번 회차는 건너뛴다 — 다음 회차(30초 뒤)에 다시 본다. 정말 죽었으면 그때도 1 이다.
gone_for_sure() {
  local rc
  instance_running "$1"; rc=$?
  [ "$rc" -eq 1 ] && return 0
  [ "$rc" -eq 2 ] && echo "[$(date '+%F %T')] $1 판정 보류 — 인스턴스 목록 조회 실패(이번 회차 건너뜀)"
  return 1
}
# 같은 구분이 감독자 밖에서도 필요해 `_common.sh:instance_absent_for_sure` 로 올렸다.
# 여기 gone_for_sure 는 "이번 회차 건너뜀" 을 **로그로 남기는** 얇은 겹이다(감독자만 그 로그가 쓸모 있다).

check_once() {
  # postgres (start full stack if its instance is gone — start.sh is idempotent)
  if gone_for_sure "$INST_POSTGRES"; then
    echo "[$(date '+%F %T')] postgres down → start.sh"
    # ② 와 같은 이유로 결과를 남긴다 — 옛 코드는 `|| true` 로 성공·실패를 똑같이 삼켜,
    # 매번 같은 이유로 실패하는 상태와 정상 복구를 로그로 구분할 수 없었다.
    if "$SCRIPT_DIR/start.sh" >/tmp/koorm-supervise-start.log 2>&1; then
      echo "[$(date '+%F %T')] postgres 복구 성공"
    else
      rc=$?
      echo "[$(date '+%F %T')] postgres 복구 실패(rc=$rc) — /tmp/koorm-supervise-start.log"
      tail -5 /tmp/koorm-supervise-start.log | sed 's/^/    /'
    fi
    return
  fi
  # api: restart if instance gone OR health endpoint not answering
  # 재기동 '이유'와 '결과'를 전부 버리고 있었다 — 인스턴스가 없어서인지 헬스가 안 붙어서인지,
  # 재기동이 성공했는지 실패했는지가 로그에 없다. 그래서 5주간 1,459회가 원인 없이 쌓였고
  # 같은 실패를 매분 반복하는 상태와 정상 복구를 구분할 수 없었다.
  #
  # ⚠ **헬스를 먼저 본다.** 옛 순서는 인스턴스 목록을 먼저 보고, 없다고 하면 헬스는 보지도 않고 재기동했다.
  # 그런데 목록 판정이 틀릴 수 있다는 것이 이번 ① 의 사고다 — 09-18 의 `restart 성공` 106회는
  # 헬스가 200 이던 API 를 목록 오판만 근거로 내린 것이다. 원인(SIGPIPE)은 고쳤지만, **순서가 그대로면
  # 같은 꼴의 오판이 또 나올 때 다시 파괴적 행동으로 번진다.** 헬스 200 은 "API 가 실제로 일하고 있다" 는
  # 직접 증거이므로, 그때는 목록이 무어라 하든 손대지 않는다.
  _api_reason=""
  if _api_code="$(curl -s -o /dev/null -w '%{http_code}' -m3 "http://127.0.0.1:${KOORM_API_PORT}/api/health" 2>/dev/null)"; then
    case "${_api_code:-000}" in 2??|3??) : ;; *) _api_reason="헬스 HTTP ${_api_code:-000}" ;; esac
  else
    _api_reason="헬스 조회 실패"
  fi
  # 인스턴스 유무는 **이유를 정확히 적기 위해서만** 본다 — 행동(재기동)은 헬스로 이미 정해졌다.
  if [ -n "$_api_reason" ] && gone_for_sure "$INST_API"; then
    _api_reason="인스턴스 없음"
  fi
  if [ -n "$_api_reason" ]; then
    echo "[$(date '+%F %T')] api down ($_api_reason) → restart-api-only.sh"
    if "$SCRIPT_DIR/restart-api-only.sh" >/tmp/koorm-restart-api.log 2>&1; then
      echo "[$(date '+%F %T')] api restart 성공"
    else
      # ⚠ `rc=$?` 가 **첫 문장**이어야 한다 — `$(date …)` 가 먼저 돌면 그 종료코드(늘 0)가 찍힌다.
      # 그래서 로그의 `실패(rc=0)` 436줄이 전부 거짓이었다(실패 가지인데 rc 가 0 일 수는 없다).
      rc=$?
      echo "[$(date '+%F %T')] api restart 실패(rc=$rc) — /tmp/koorm-restart-api.log"
      tail -5 /tmp/koorm-restart-api.log | sed 's/^/    /'
    fi
  fi
  # mcp: restart instance if gone
  if gone_for_sure "$INST_MCP"; then
    echo "[$(date '+%F %T')] mcp down → start"
    local net=(); [ "${KOORM_APPT_HOST_NET:-0}" = "1" ] && net=(--net --network=host)
    "$APPTAINER" instance start "${net[@]}" --bind "$REPO_ROOT:/workspace" \
      --env "KOOREMAPPER_API_BASE=http://127.0.0.1:${KOORM_API_PORT}" \
      --env "KOORM_MCP_PORT=${KOORM_MCP_PORT}" --env "MCP_HOST=${MCP_HOST:-127.0.0.1}" \
      --env "MCP_ALLOWED_HOSTS=${MCP_ALLOWED_HOSTS:-}" "$MCP_SIF" "$INST_MCP" >/tmp/koorm-restart-mcp.log 2>&1 \
      && echo "[$(date '+%F %T')] mcp restart 성공" \
      || { rc=$?; echo "[$(date '+%F %T')] mcp restart 실패(rc=$rc) — /tmp/koorm-restart-mcp.log"; tail -5 /tmp/koorm-restart-mcp.log | sed 's/^/    /'; }
  fi
  # nginx (only when enabled): restart instance if gone
  if [ "${KOORM_ENABLE_NGINX:-0}" = "1" ] && gone_for_sure "$INST_NGINX"; then
    echo "[$(date '+%F %T')] nginx down → start"
    local net2=(); [ "${KOORM_APPT_HOST_NET:-0}" = "1" ] && net2=(--net --network=host)
    [ -f "$PLATFORM_ROOT/infra/nginx/certs/server.crt" ] || "$SCRIPT_DIR/gen-certs.sh" >/dev/null 2>&1 || true
    # ② 와 같은 이유 — `>/dev/null … || true` 는 실패를 통째로 삼킨다. dev 는 KOORM_ENABLE_NGINX=1 이라
    # 살아 있는 경로인데, nginx 가 매 회차 같은 이유로 못 뜨는 상태를 로그로 알 길이 없었다.
    "$APPTAINER" instance start "${net2[@]}" \
      --bind "$PLATFORM_ROOT/infra/nginx/certs:/etc/nginx/certs:ro" \
      "$NGINX_SIF" "$INST_NGINX" >/tmp/koorm-restart-nginx.log 2>&1 \
      && echo "[$(date '+%F %T')] nginx restart 성공" \
      || { rc=$?; echo "[$(date '+%F %T')] nginx restart 실패(rc=$rc) — /tmp/koorm-restart-nginx.log"; tail -5 /tmp/koorm-restart-nginx.log | sed 's/^/    /'; }
  fi
}

if [ "$ONCE" = 1 ]; then check_once; echo "✓ supervise check done"; exit 0; fi

echo "→ supervisor started (interval ${INTERVAL}s). Ctrl-C to stop."
while true; do check_once; sleep "$INTERVAL"; done
