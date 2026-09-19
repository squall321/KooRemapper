#!/usr/bin/env bash
# 재부팅 후 스택을 자동 기동+감시하도록 @reboot crontab 항목을 설치한다(멱등).
# Install a @reboot crontab entry that brings the KooRemapper stack up after a
# host reboot and keeps it supervised. Idempotent. Uninstall with --remove.
set -euo pipefail
. "$(dirname "$0")/_common.sh"

MARK="# koorm-autostart"
LOG="$DATA_DIR/supervisor.log"
# supervisor.sh start.sh's the full stack when it's down, then watches — so a
# single @reboot entry covers both boot-start and ongoing restart.
LINE="@reboot cd $REPO_ROOT && nohup bash $SCRIPT_DIR/supervisor.sh >> $LOG 2>&1 &  $MARK"

# 지금 감독자를 띄운다 — **크론만 넣으면 다음 재부팅까지 감시가 없다.**
# 설치는 보통 "지금 스택이 이상하다" 에서 하는 일이라, 그 공백이 정확히 필요한 때에 비어 있었다.
# 이미 돌고 있으면 띄우지 않는다 — 감독자가 둘이면 서로의 재기동을 밟는다(30초 간격이 겹친다).
start_supervisor_now() {
  if pgrep -f "bash $SCRIPT_DIR/supervisor.sh" >/dev/null 2>&1; then
    _pids="$(pgrep -f "bash $SCRIPT_DIR/supervisor.sh" || true)"
    echo "✓ supervisor 이미 실행 중 — 중복 기동하지 않는다(pid ${_pids%%$'\n'*})"
    return 0
  fi
  mkdir -p "$DATA_DIR"
  # ⚠ **서브셸로 감싸지 않는다** — `( … & )` 는 호출자를 자식 수명만큼 붙든다(실측: 스텁 감독자
  # sleep 4 에 호출이 4.0초, sleep 6 에 6.0초). 출력을 받아 가는 자동화·설치 래퍼에서는 그 말이
  # **영원히 안 끝난다**는 뜻이다. `nohup … &` + `disown` 이면 즉시 돌아온다(실측 0.0초).
  # cwd 는 걱정하지 않아도 된다 — `_common.sh` 가 자기 위치에서 REPO_ROOT 로 `cd` 한다.
  nohup bash "$SCRIPT_DIR/supervisor.sh" >> "$LOG" 2>&1 &
  disown
  sleep 1
  if pgrep -f "bash $SCRIPT_DIR/supervisor.sh" >/dev/null 2>&1; then
    echo "✓ supervisor 지금 띄웠다 — 재부팅을 기다리지 않는다(로그: $LOG)"
  else
    echo "✗ supervisor 기동 실패 — $LOG 를 확인하라" >&2
    return 1
  fi
}

current="$(crontab -l 2>/dev/null || true)"

if [ "${1:-}" = "--remove" ]; then
  echo "$current" | grep -v "$MARK" | crontab - 2>/dev/null || true
  echo "✓ removed koorm autostart from crontab"
  exit 0
fi

if echo "$current" | grep -qF "$MARK"; then
  echo "✓ autostart already installed (crontab has $MARK)"
  # 크론이 있다고 감독자가 돌고 있는 것은 아니다(재부팅 전이거나 죽었을 수 있다) — 여기서도 확인한다
  start_supervisor_now
  exit $?
fi

printf '%s\n%s\n' "$current" "$LINE" | sed '/^$/d' | crontab -
echo "✓ installed @reboot autostart → supervisor.sh (logs: $LOG)"
echo "  the stack will come up automatically after a reboot and stay supervised."
echo "  remove with: $0 --remove"
start_supervisor_now
