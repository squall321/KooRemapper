#!/usr/bin/env bash
# Stop all KooRemapper instances (nginx, mcp, api, postgres — reverse start order).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

# 인스턴스마다 정말 사라질 때까지 기다린 뒤 다음으로 간다(R-04) — api 가 사라진 뒤에 postgres 를 내린다. 하나라도 상한을 넘기면 나머지도
# 끝까지 시도하고 rc 1 로 끝낸다 — 「멈췄다」 를 믿고 SIF 를 바꾸거나 start 로 넘어가는 쪽이 멈추게.
rc=0
for inst in "$INST_NGINX" "$INST_MCP" "$INST_API" "$INST_POSTGRES"; do
  # 확실히 없을 때만 건너뛴다. 모르면 stop 을 시도한다 — 없는 인스턴스에 대한 stop 은 무해하지만,
  # 살아 있는 것을 "✓ not running" 으로 넘기면 배포가 옛 인스턴스 위에서 계속된다(거짓 성공).
  if instance_absent_for_sure "$inst"; then
    echo "✓ $inst not running"
  else
    echo "→ stop $inst"
    "$APPTAINER" instance stop "$inst" || true
    wait_instance_gone "$inst" || rc=1
  fi
done
exit "$rc"
