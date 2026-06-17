#!/usr/bin/env bash
# Show running KooRemapper instances + service health.
set -uo pipefail
. "$(dirname "$0")/_common.sh"

echo "── instances ──────────────────────────────────"
"$APPTAINER" instance list 2>/dev/null | grep -E "INSTANCE|$INST_POSTGRES|$INST_API|$INST_MCP" || echo "(none running)"

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
if curl -fsS -m3 -o /dev/null "http://127.0.0.1:${KOORM_MCP_PORT}/mcp" 2>/dev/null \
   || ss -ltn 2>/dev/null | grep -q ":${KOORM_MCP_PORT}"; then
  echo "  ✓ mcp listening (:${KOORM_MCP_PORT})"
else
  echo "  ✗ mcp not listening (:${KOORM_MCP_PORT})"
fi
