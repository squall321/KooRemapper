#!/usr/bin/env bash
# Stop all KooRemapper instances (nginx, mcp, api, postgres — reverse start order).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

for inst in "$INST_NGINX" "$INST_MCP" "$INST_API" "$INST_POSTGRES"; do
  # 확실히 없을 때만 건너뛴다. 모르면 stop 을 시도한다 — 없는 인스턴스에 대한 stop 은 무해하지만,
  # 살아 있는 것을 "✓ not running" 으로 넘기면 배포가 옛 인스턴스 위에서 계속된다(거짓 성공).
  if instance_absent_for_sure "$inst"; then
    echo "✓ $inst not running"
  else
    echo "→ stop $inst"
    "$APPTAINER" instance stop "$inst" || true
  fi
done
