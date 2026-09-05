#!/usr/bin/env bash
# Restart ONLY the api instance (source is bind-mounted; no SIF rebuild, no
# postgres/mcp churn, no migrations). Use for backend code changes.
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

[ -f "$API_SIF" ] || { echo "✗ api.sif missing — run build.sh first"; exit 1; }

if instance_running "$INST_API"; then
  echo "→ stop $INST_API"
  "$APPTAINER" instance stop "$INST_API" || true
  sleep 1
fi

KOORM_SPA_DIST=""
if [ -f "$REPO_ROOT/platform/frontend/dist/index.html" ]; then
  KOORM_SPA_DIST=/workspace/platform/frontend/dist
fi

NET_ARGS=()
[ "${KOORM_APPT_HOST_NET:-0}" = "1" ] && NET_ARGS=(--net --network=host)

# /data 레지스트리 바인드(D9 storage 마이그레이션) — storage 가 /data/svc/kooremapper 로 이전됐고
# platform/storage 는 그쪽 심링크라, 컨테이너에 바인드하지 않으면 심링크가 깨져 기동 실패한다.
# start.sh 와 동일하게 맞춘다(이 줄들이 없어 restart-api-only 만 D9 후 깨졌었다).
KOORM_DATA_BINDS=(); _r="${HWAX_DATA_ROOT:-/data}"; case "$_r" in /*) ;; *) _r=/data ;; esac
_d="$_r/svc/kooremapper"; [ -d "$_d" ] && KOORM_DATA_BINDS+=(--bind "$_d:$_d")

echo "→ start $INST_API"
"$APPTAINER" instance start "${NET_ARGS[@]}" \
  ${KOORM_DATA_BINDS[@]+"${KOORM_DATA_BINDS[@]}"} ${KOORM_STORAGE_DIR:+--env "KOORM_STORAGE_DIR=$KOORM_STORAGE_DIR"} \
  --bind "$REPO_ROOT:/workspace" \
  --env "KOORM_API_PORT=${KOORM_API_PORT}" \
  --env "KOORM_DATABASE_URL=${KOORM_DATABASE_URL}" \
  --env "KOORM_JWT_SECRET=${KOORM_JWT_SECRET}" \
  --env "KOORM_CORS_ORIGINS=${KOORM_CORS_ORIGINS}" \
  --env "KOORM_SERVE_FRONTEND_DIST=${KOORM_SPA_DIST}" \
  --env "KOORM_WORKER_CONCURRENCY=${KOORM_WORKER_CONCURRENCY:-4}" \
  --env "KOORM_JOB_TIMEOUT_SEC=${KOORM_JOB_TIMEOUT_SEC:-1800}" \
  --env "KOORM_MAX_UPLOAD_MB=${KOORM_MAX_UPLOAD_MB:-512}" \
  --env "KOORM_MAX_REPORT_MB=${KOORM_MAX_REPORT_MB:-2048}" \
  --env "KOORM_HEAX_GATEWAY_SECRET=${KOORM_HEAX_GATEWAY_SECRET:-}" \
  --env "KOORM_APP_ENV=${KOORM_APP_ENV:-development}" \
  "$API_SIF" "$INST_API"
echo "✓ api restarted on :${KOORM_API_PORT}"
