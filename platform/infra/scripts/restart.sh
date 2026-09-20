#!/usr/bin/env bash
# Restart the api instance to pick up code changes (source is bind-mounted).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

# 모르면 stop 을 시도한다 — 건너뛰면 뒤이은 start 가 `already exists` 로 실패한다(요청서 ① 의 62회).
if ! instance_absent_for_sure "$INST_API"; then
  echo "→ stop $INST_API"
  "$APPTAINER" instance stop "$INST_API" || true
  sleep 1
fi
"$SCRIPT_DIR/start.sh"
