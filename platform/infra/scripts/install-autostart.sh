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

current="$(crontab -l 2>/dev/null || true)"

if [ "${1:-}" = "--remove" ]; then
  echo "$current" | grep -v "$MARK" | crontab - 2>/dev/null || true
  echo "✓ removed koorm autostart from crontab"
  exit 0
fi

if echo "$current" | grep -qF "$MARK"; then
  echo "✓ autostart already installed (crontab has $MARK)"
  exit 0
fi

printf '%s\n%s\n' "$current" "$LINE" | sed '/^$/d' | crontab -
echo "✓ installed @reboot autostart → supervisor.sh (logs: $LOG)"
echo "  the stack will come up automatically after a reboot and stay supervised."
echo "  remove with: $0 --remove"
