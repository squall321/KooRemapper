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

# 로그 회전. 크론이 `>> supervisor.log` 로 **끝없이 붙이므로** 감독자 자신이 줄여야 한다
# (실측 712KB / 18,216줄, 회전 장치 없음). logrotate 를 새로 걸지 않는 이유 — 이 스택의 다른
# 크론들과 모양을 맞추고 루트 권한 없이 돌아야 한다.
#
# ⚠ 잠금을 잡기 **전에** 돌린다. 잠금 안에서 파일을 갈면 같은 회차의 뒷부분이 새 파일에 쓰이고
# 앞부분이 옛 파일에 남아 한 회차가 두 파일로 갈린다.
# ⚠ `cp` + `truncate` 로 한다. `mv` 하면 크론의 `>>` 가 **옛 inode 를 계속 붙잡아** 새 파일이
# 비어 있게 된다(리다이렉션이 이미 열려 있다).
KOORM_SUPERVISE_LOG_MAX="${KOORM_SUPERVISE_LOG_MAX:-2000000}"   # 2MB
rotate_log() {
  local log="${KOORM_SUPERVISE_LOG:-$REPO_ROOT/platform/infra/data/supervisor.log}"
  [ -f "$log" ] || return 0
  local sz
  sz=$(stat -c %s "$log" 2>/dev/null) || return 0
  [ "$sz" -le "$KOORM_SUPERVISE_LOG_MAX" ] && return 0
  cp -p "$log" "$log.1" 2>/dev/null || return 0
  : > "$log"
  echo "[$(date '+%F %T')] 로그를 회전했다(${sz} bytes → $(basename "$log").1)"
}

# 감독자는 **하나만** 돈다. 둘이면 서로의 재기동을 밟는다 — 한쪽이 stop 한 인스턴스를 다른 쪽이
# "없음" 으로 보고 다시 start 해 `already exists` 가 난다. 매분 도는 --once 가 앞 회차와 겹치는 것도 막는다.
#
# ⚠ 프로세스 이름 매칭으로는 못 막는다(실측): 크론은 `bash /abs/…/supervisor.sh` 로 뜨는데
# README 가 권하는 방식은 `bash ./infra/scripts/supervisor.sh` 라서 절대경로 pgrep 패턴이 빗나간다.
#
# ⚠⚠ **flock 도 못 쓴다.** `exec 9>파일` 로 잡은 fd 는 **자식이 물려받는다.** 감독자가 띄운
# apptainer 인스턴스는 영원히 살아 있으므로 그 fd 를 들고 잠금을 놓지 않는다 —
# 2026-09-21 01:26 에 실제로 그렇게 됐다(koorm_mcp 가 fd 9 를 쥐고, 이후 모든 회차가
# "이미 돌고 있다" 로 물러나 **감시가 멈췄다**). 잠금 하나 잘못 잡아 감시를 죽인 셈이다.
#
# 그래서 mkdir 로 잡는다 — 원자적이고 **fd 를 남기지 않아** 자식에게 새지 않는다.
# 죽은 감독자가 남긴 잠금은 pid 로 알아보고 걷어낸다(이름이 아니라 우리가 적은 pid 가 근거다).
mkdir -p "$DATA_DIR"
LOCK_DIR="$DATA_DIR/supervisor.lock.d"
LOCK_PID="$LOCK_DIR/pid"

lock_holder_alive() {
  local p
  p="$(head -n1 "$LOCK_PID" 2>/dev/null | tr -dc '0-9')"
  [ -n "$p" ] || return 1
  kill -0 "$p" 2>/dev/null || return 1
  # pid 는 재사용된다 — 정말 감독자인지 명령줄로 확인한다
  tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q 'supervisor\.sh'
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  if lock_holder_alive; then
    echo "[$(date '+%F %T')] 이미 감독자가 돌고 있다 — 이번 호출은 아무것도 하지 않는다"
    exit 0
  fi
  echo "[$(date '+%F %T')] 죽은 감독자가 남긴 잠금을 걷어낸다"
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR" 2>/dev/null || { echo "[$(date '+%F %T')] 잠금 확보 실패 — 이번 회차 건너뜀"; exit 0; }
fi
printf '%s\n' "$$" > "$LOCK_PID"
trap 'rm -rf "$LOCK_DIR"' EXIT

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

# postgres 가 **실제로 접속을 받는가** — 인스턴스 목록에 있다는 것만으로는 모른다. 10-17 09:32 ~ 10-18 03:53, 같은 이름의 셸이
# 겹친 뒤 postgres 없는 셸이 목록에 남아 감독자가 18시간 동안 매분 ✓ 를 찍었고 :5436 은 비어 있었다(사람별 로그인 500 31건 — HWAX
# 포털 수정 제안서 K1). 인스턴스 안의 pg_isready 로 유닉스소켓을 본다(그 소켓은 우리 데이터 폴더라 남의 postmaster 가 아니다 — start.sh
# 의 pg_id 와 같은 근거).  0 받는다 · 1 기동·종료 중(이번 회차는 기다린다) · 2 응답 없음 · 3 판정 불가(목록 실패처럼 '모름' — 손대지 않는다).
KOORM_MCP_RECHECK_S="${KOORM_MCP_RECHECK_S:-5}"   # MCP 무응답을 한 번 더 볼 때까지(초)
# MCP 가 연결을 받는가 — HTTP 코드가 오면(406 · 405 · 200 …) 산 것이고, 연결이 안 되면 000 이다. 띄울 때 쓴 MCP_HOST 그대로 본다.
mcp_code() {
  local host="${MCP_HOST:-127.0.0.1}"
  [ "$host" = "0.0.0.0" ] && host=127.0.0.1
  curl -s -o /dev/null -w '%{http_code}' -m3 "http://${host}:${KOORM_MCP_PORT}/mcp" 2>/dev/null || true
}
KOORM_PG_RECHECK_S="${KOORM_PG_RECHECK_S:-5}"   # 응답 없음을 한 번 더 볼 때까지(초) — 한 번의 깜박임으로 내리지 않는다
pg_state() {
  local rc=0
  "$APPTAINER" exec instance://"$INST_POSTGRES" pg_isready -q -h /var/run/postgresql -p "$POSTGRES_PORT" >/dev/null 2>&1 || rc=$?
  case "$rc" in
    0) return 0 ;;
    1) return 1 ;;
    2) return 2 ;;
    *) return 3 ;;    # 3(인자 오류) · 126/127(pg_isready 없음) · 255(인스턴스에 못 붙음) — 죽었다는 증거가 아니다
  esac
}
# 같은 이름의 인스턴스 셸 수 — 둘 이상이면 apptainer 의 인스턴스 기록이 하나만 가리켜, 무엇을 내리든 다른 셸이 남는다(10-17 사고의 시작).
pg_shells() {
  local n
  n="$(pgrep -c -f "Apptainer instance: $(id -un) \\[$INST_POSTGRES\\]" 2>/dev/null || true)"
  printf '%s' "${n:-0}" | tr -dc '0-9'
}
# start.sh 가 rc 0 이어도 postgres 가 받는지 다시 본다 — '복구 성공' 은 그 뒤에만 적는다(K1 ②).
pg_ready_after_start() {
  local _i rc
  for _i in 1 2 3 4 5 6; do
    rc=0; pg_state || rc=$?   # ⚠ `f; rc=$?` 는 set -e(_common.sh) 아래서 f 가 0 이 아니면 거기서 끝난다
    [ "$rc" -eq 0 ] && return 0
    sleep "$KOORM_PG_RECHECK_S"
  done
  return 1
}
pg_start() {   # $1: 까닭 — start.sh 로 띄우고 postgres 가 받는지까지 확인해 결과를 적는다
  if "$SCRIPT_DIR/start.sh" >/tmp/koorm-supervise-start.log 2>&1; then
    if pg_ready_after_start; then
      echo "[$(date '+%F %T')] postgres 복구 성공($1 — 접속 확인)"
    else
      echo "[$(date '+%F %T')] postgres 복구 실패($1) — start.sh 는 rc 0 인데 postgres 가 접속을 받지 않는다 · /tmp/koorm-supervise-start.log"
    fi
  else
    local rc=$?
    echo "[$(date '+%F %T')] postgres 복구 실패($1 · rc=$rc) — /tmp/koorm-supervise-start.log"
    tail -5 /tmp/koorm-supervise-start.log | sed 's/^/    /'
  fi
}

# 배포가 도는 중인가 — 표지 둘을 본다(KR-04, 2026-10-27).
#   ① $DATA_DIR/deploy.lock.d/pid 에 **산** PID (포털 deploy-all 이 stop 전에 만들고 start 뒤 trap 으로 지운다 — HP-01)
#   ② /tmp/hwax-update-all.*.lock 을 **누가 잡고** 있다(flock -n 로 못 잡으면 잡혀 있는 것)
# 둘 중 하나라도 참이면 배포 중이다. 표지가 아직 없으면(포털 HP-01 전) 늘 거짓이라 예전과 똑같이 동작한다.
_deploy_in_progress() {
  local dpid f
  dpid="$(head -n1 "$DATA_DIR/deploy.lock.d/pid" 2>/dev/null | tr -dc '0-9' || true)"
  if [ -n "$dpid" ] && kill -0 "$dpid" 2>/dev/null; then
    return 0
  fi
  for f in /tmp/hwax-update-all.*.lock; do
    [ -e "$f" ] || continue
    if ! flock -n "$f" -c true 2>/dev/null; then
      return 0
    fi
  done
  return 1
}

check_once() {
  # 배포 중이면 **아무것도 하지 않는다** — stop 과 start 사이에 끼면 start 가 겹쳐 띄워져
  # `instance … already exists` 가 난다(KR-04 · 10-09·10-17 사고). 재기동은 배포 쪽이 끝내고 한다.
  if _deploy_in_progress; then
    echo "[$(date '+%F %T')] 배포 중 — 건너뜀"
    return
  fi
  # postgres — 같은 이름의 셸이 겹쳤으면 알리고 손대지 않는다(K1 ④). 무엇을 내리든 다른 셸이 남아 다음 회차가 또 겹쳐 띄운다.
  local _shells _pg
  _shells="$(pg_shells)"
  if [ "${_shells:-0}" -ge 2 ] 2>/dev/null; then
    echo "[$(date '+%F %T')] ⚠ $INST_POSTGRES 인스턴스 셸이 ${_shells}개다 — 손대지 않는다. 사람이: 감시 cron 을 빼고 stop.sh 로 등록된 것을" \
         "내린 뒤 남은 빈 셸을 치우고 start.sh, 그다음 cron 을 되돌린다(같은 이름의 빈 셸을 먼저 끝내면 기록이 지워져 감시가 겹쳐 띄운다)"
  elif gone_for_sure "$INST_POSTGRES"; then
    # start full stack if its instance is gone — start.sh is idempotent
    echo "[$(date '+%F %T')] postgres down → start.sh"
    # ② 와 같은 이유로 결과를 남긴다 — 옛 코드는 `|| true` 로 성공·실패를 똑같이 삼켜,
    # 매번 같은 이유로 실패하는 상태와 정상 복구를 로그로 구분할 수 없었다.
    pg_start "인스턴스 없음"
    return
  else
    # 인스턴스는 있다 — 접속을 받는가(K1 ①). 응답 없음은 KOORM_PG_RECHECK_S 뒤 한 번 더 보고도 그러면 내리고 다시 띄운다.
    # ⚠ `pg_state; _pg=$?` 로 받지 않는다 — _common.sh 가 set -e 라 0 이 아닌 답에서 감독자가 말없이 끝난다(if 조건 안의
    #   gone_for_sure 는 errexit 가 쉬어 괜찮았다). 시험이 잡았다(10-18).
    _pg=0; pg_state || _pg=$?
    if [ "$_pg" -eq 2 ]; then
      sleep "$KOORM_PG_RECHECK_S"
      _pg=0; pg_state || _pg=$?
    fi
    case "$_pg" in
      0) : ;;
      1) echo "[$(date '+%F %T')] postgres 기동·종료 중(pg_isready 1) — 다음 회차에 다시 본다" ;;
      2) echo "[$(date '+%F %T')] postgres 무응답(인스턴스는 있다 — ${KOORM_PG_RECHECK_S}초 간격 두 번) → stop → start.sh"
         "$APPTAINER" instance stop "$INST_POSTGRES" >/tmp/koorm-supervise-pgstop.log 2>&1 \
           || echo "[$(date '+%F %T')] postgres 인스턴스 stop 실패 — /tmp/koorm-supervise-pgstop.log(그래도 start.sh 를 부른다)"
         pg_start "인스턴스는 있는데 무응답"
         return ;;
      *) echo "[$(date '+%F %T')] postgres 판정 보류 — 인스턴스 안에서 pg_isready 를 못 돌렸다(이번 회차 건너뜀)" ;;
    esac
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
  # 헬스가 DB 를 본다(K1 ③ — DB 가 죽으면 503 · database.ok=false). 그때 API 를 다시 띄워도 고쳐지지 않는다 — 위 postgres 판정이 맡는다.
  if [ "${_api_code:-}" = "503" ] && [ "$_api_reason" = "헬스 HTTP 503" ]; then
    _api_body="$(curl -s -m3 "http://127.0.0.1:${KOORM_API_PORT}/api/health" 2>/dev/null || true)"
    case "$_api_body" in
      *'"database":{"ok":false'*)
        echo "[$(date '+%F %T')] api 는 떠 있고 DB 가 응답하지 않는다(헬스 503 · database.ok=false) — api 는 다시 띄우지 않는다"
        _api_reason="" ;;
    esac
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
  # mcp: 인스턴스는 **확실히 있는데** 포트가 연결조차 안 받으면 인스턴스를 내린다 — 바로 아래 '없으면 띄운다' 가 같은 회차에 다시 띄운다.
  # 10-18 07:11 UTC earlyoom 이 인스턴스 안의 서버만 죽여(SIGTERM) 인스턴스는 남았고, 이 감시는 '있다' 만 보고 14시간 매분 ✓ 를
  # 찍었다(HWAXPortal docs/followups-1017 FU-D22). 000(연결 안 됨)만, 두 번 보고 판정한다. 목록 조회가 실패한 '모름'(2)은 손대지 않는다.
  # ⚠ `f; rc=$?` 꼴로 받지 않는다 — set -e(_common.sh) 아래서 f 가 1(없음)·2(모름)면 거기서 스크립트가 끝나 아래 '없으면 띄운다' 에 닿지
  #   못했다(559f582 ~ 10-25, 위 118행 pg_state 와 같은 함정 — HWAXPortal 10-25 cae00 점검).
  _mcp_rc=0; instance_running "$INST_MCP" || _mcp_rc=$?
  if [ "$_mcp_rc" -eq 0 ] && [ "$(mcp_code)" = "000" ]; then
    sleep "$KOORM_MCP_RECHECK_S"
    if [ "$(mcp_code)" = "000" ]; then
      echo "[$(date '+%F %T')] mcp 무응답(인스턴스는 있다 — :${KOORM_MCP_PORT} 연결 안 됨, 두 번) → 인스턴스를 내리고 다시 띄운다"
      "$APPTAINER" instance stop "$INST_MCP" >/tmp/koorm-stop-mcp.log 2>&1 \
        || { rc=$?; echo "[$(date '+%F %T')] mcp instance stop 실패(rc=$rc) — /tmp/koorm-stop-mcp.log"; }
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

if [ "$ONCE" = 1 ]; then
  check_once
  # ⚠ 이 심장박동 줄에 **시각이 없었다.** 매분 크론이 붙이므로 로그의 59%(실측 10,695 / 18,216줄)가
  # 같은 글자였고, "언제 죽었나" 를 로그에서 못 읽었다. 다른 echo 는 처음부터 시각이 있었다.
  echo "[$(date '+%F %T')] ✓ supervise check done"
  rotate_log
  exit 0
fi

echo "[$(date '+%F %T')] → supervisor started (interval ${INTERVAL}s). Ctrl-C to stop."
while true; do check_once; sleep "$INTERVAL"; done
