#!/usr/bin/env bash
# 스택을 자동 기동+감시하도록 crontab 항목을 설치한다(멱등). Uninstall with --remove.
#
# ⚠ 예전에는 `@reboot` 한 줄로 감독자 **루프**를 띄웠다. 두 구멍이 있었다(요청서 ③):
#   · 설치~다음 재부팅 사이에는 감시가 없다. 설치는 보통 "지금 스택이 이상하다" 에서 하는 일이라,
#     그 공백이 정확히 필요한 때에 비어 있었다.
#   · 그 루프가 죽으면 **되살리는 주체가 없다.** 다음 재부팅까지 감시가 사라진다.
# 그래서 매분 도는 `--once` 로 바꾼다 — 부팅과 루프 사망이 한 번에 해결되고, 다른 스택
# (HEAXHub·AIDataHub)의 watchdog 크론과 모양이 같아진다. 겹쳐 도는 것은 supervisor.sh 의
# 파일 잠금이 막는다(프로세스 이름 매칭은 기동 방식마다 빗나가서 못 쓴다).
set -euo pipefail
. "$(dirname "$0")/_common.sh"

MARK="# koorm-autostart"
LOG="$DATA_DIR/supervisor.log"
LINE="* * * * * cd $REPO_ROOT && bash $SCRIPT_DIR/supervisor.sh --once >> $LOG 2>&1  $MARK"

current="$(crontab -l 2>/dev/null || true)"

if [ "${1:-}" = "--remove" ]; then
  echo "$current" | grep -v "$MARK" | crontab - 2>/dev/null || true
  echo "✓ removed koorm autostart from crontab"
  # 크론만 떼고 끝내면 돌고 있는 루프가 남아 감시가 계속된다 — 해제라고 말했으면 실제로 멈춘다.
  # 근거는 잠금 파일에 적힌 pid 다(이름 매칭은 기동 방식마다 빗나가고 남의 스크립트까지 잡는다).
  _pid="$(head -n1 "$DATA_DIR/supervisor.pid" 2>/dev/null | tr -dc '0-9')"
  # pid 는 재사용된다 — 정말 우리 감독자인지 명령줄로 한 번 더 확인한 뒤에 죽인다.
  if [ -n "$_pid" ] && kill -0 "$_pid" 2>/dev/null \
     && tr '\0' ' ' < "/proc/$_pid/cmdline" 2>/dev/null | grep -q 'supervisor\.sh'; then
    kill "$_pid" 2>/dev/null && echo "  ✓ 돌고 있던 감독자도 멈췄다(pid $_pid)"
  else
    echo "  · 돌고 있는 감독자는 없다"
  fi
  exit 0
fi

# 옛 @reboot 줄이 남아 있으면 함께 걷어낸다 — 같은 MARK 라 한 번에 갈린다(재설치가 곧 이관이다).
printf '%s\n%s\n' "$(echo "$current" | grep -v "$MARK" || true)" "$LINE" | sed '/^$/d' | crontab -
echo "✓ installed watchdog cron (매분 supervisor.sh --once, logs: $LOG)"
echo "  재부팅 뒤에도, 감시가 멈춰도 다음 1분 안에 되살아난다."
echo "  remove with: $0 --remove"

# 다음 정각까지 최대 1분을 기다리지 않는다 — 설치한 그 자리에서 한 번 돌린다.
mkdir -p "$DATA_DIR"
if bash "$SCRIPT_DIR/supervisor.sh" --once >> "$LOG" 2>&1; then
  echo "✓ 지금 한 번 점검했다 — 기다리지 않는다(로그: $LOG)"
else
  rc=$?   # ② 와 같은 이유로 **첫 문장**에서 받는다 — 앞에 무엇이든 끼면 그 종료코드가 찍힌다
  echo "✗ 즉시 점검이 실패했다(rc=$rc) — $LOG 를 확인하라" >&2
  exit 1
fi
