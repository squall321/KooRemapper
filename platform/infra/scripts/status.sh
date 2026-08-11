#!/usr/bin/env bash
# Show running KooRemapper instances + service health.
set -uo pipefail
. "$(dirname "$0")/_common.sh"

echo "── instances ──────────────────────────────────"
"$APPTAINER" instance list 2>/dev/null | grep -E "INSTANCE|$INST_POSTGRES|$INST_API|$INST_MCP|$INST_NGINX" || echo "(none running)"

echo "── health ─────────────────────────────────────"
if "$APPTAINER" exec instance://"$INST_POSTGRES" pg_isready -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1; then
  echo "  ✓ postgres ready (:$POSTGRES_PORT)"
else
  echo "  ✗ postgres not ready (:$POSTGRES_PORT)"
fi
if curl -fsS -m3 "http://127.0.0.1:${KOORM_API_PORT}/api/health" >/dev/null 2>&1; then
  echo "  ✓ api ready (http://127.0.0.1:${KOORM_API_PORT})"
else
  echo "  ✗ api not responding (:${KOORM_API_PORT})"
fi
# curl -fsS 는 MCP 의 406(스트림 협상 필요)을 실패로 보므로 이 프로브는 항상 실패했고,
# 판정은 사실상 `|| ss` 즉 '포트 점유 여부'만으로 이뤄졌다. 프로세스가 포트를 물고 있지만
# MCP 로는 응답하지 않는 상태를 '✓ listening' 으로 통과시킨다.
# MCP 는 406/400 도 '서버가 프로토콜을 말하고 있다'는 증거이므로 상태코드로 판정한다.
_mcp_code="$(curl -s -o /dev/null -w '%{http_code}' -m3 "http://127.0.0.1:${KOORM_MCP_PORT}/mcp" 2>/dev/null)"
case "${_mcp_code:-000}" in
  2??|400|406)
    echo "  ✓ mcp responding (:${KOORM_MCP_PORT}, HTTP ${_mcp_code})" ;;
  000)
    if ss -ltn 2>/dev/null | grep -q ":${KOORM_MCP_PORT}"; then
      echo "  ✗ mcp 포트는 열려 있으나 응답 없음 (:${KOORM_MCP_PORT}) — 프로세스가 먹통이다"
    else
      echo "  ✗ mcp not listening (:${KOORM_MCP_PORT})"
    fi ;;
  *)
    echo "  ✗ mcp 이상 응답 (:${KOORM_MCP_PORT}, HTTP ${_mcp_code})" ;;
esac
if instance_running "$INST_NGINX"; then
  if curl -fsSk -m3 -o /dev/null "https://127.0.0.1:${KOORM_HTTPS_PORT}/" 2>/dev/null; then
    echo "  ✓ nginx TLS ready (https://127.0.0.1:${KOORM_HTTPS_PORT})"
  else
    echo "  ✗ nginx running but https not answering (:${KOORM_HTTPS_PORT})"
  fi
else
  echo "  · nginx not running (optional; KOORM_ENABLE_NGINX=1 to enable)"
fi
