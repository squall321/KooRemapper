#!/usr/bin/env bash
# Restart the api instance to pick up code changes (source is bind-mounted).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

# 모르면 stop 을 시도한다 — 건너뛰면 뒤이은 start 가 `already exists` 로 실패한다(요청서 ① 의 62회).
if ! instance_absent_for_sure "$INST_API"; then
  wait_uploads_drained || exit 1              # 진행 중 올리기가 끝난 뒤에 내린다(운영 11-26) — 넘기면 내리지 않고 rc 1
  echo "→ stop $INST_API"
  "$APPTAINER" instance stop "$INST_API" || true
  wait_instance_gone "$INST_API" || exit 1   # 내려가는 중인 인스턴스 위에 start.sh 를 걸지 않는다(R-04)
fi
"$SCRIPT_DIR/start.sh"
