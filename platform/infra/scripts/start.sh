#!/usr/bin/env bash
# Start postgres + api as Apptainer instances (Phase 1).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer
"$SCRIPT_DIR/build.sh"

# Link the bundled gmsh next to the binary so meshfix works (optional — warn,
# don't fail, if gmsh isn't present since it's only needed for meshfix).
"$SCRIPT_DIR/setup-gmsh.sh" || echo "  ⚠ gmsh not linked — meshfix will be unavailable (see setup-gmsh.sh)"

NET_ARGS=()
if [ "${KOORM_APPT_HOST_NET:-0}" = "1" ]; then
  NET_ARGS=(--net --network=host)
fi

start_instance() {
  local name="$1" sif="$2"; shift 2
  if instance_running "$name"; then echo "✓ $name already running"; return 0; fi
  echo "→ start $name"
  "$APPTAINER" instance start "${NET_ARGS[@]}" "$@" "$sif" "$name"
}

# ── postgres ────────────────────────────────────────────────────────
# Stale lock cleanup when the instance is not running but a dead PID holds the lock.
if ! instance_running "$INST_POSTGRES"; then
  for f in "$DATA_DIR/postgres-run/.s.PGSQL.${POSTGRES_PORT}.lock" \
           "$DATA_DIR/postgres/pgdata/postmaster.pid"; do
    [ -e "$f" ] || continue
    pid="$(head -n1 "$f" 2>/dev/null | tr -dc '0-9')"
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
      echo "  → removing stale postgres lock: $(basename "$f")"
      rm -f "$f"
    fi
  done
fi

start_instance "$INST_POSTGRES" "$POSTGRES_SIF" \
  --bind "$DATA_DIR/postgres:/var/lib/postgresql/data" \
  --bind "$DATA_DIR/postgres-run:/var/run/postgresql" \
  --env "POSTGRES_USER=${POSTGRES_USER}" \
  --env "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
  --env "POSTGRES_DB=${POSTGRES_DB}" \
  --env "PGPORT=${POSTGRES_PORT}" \
  --env "PGDATA=/var/lib/postgresql/data/pgdata" \
  --env "LANG=C.UTF-8" --env "LC_ALL=C.UTF-8"

echo "→ waiting for postgres…"
for _i in $(seq 1 40); do
  if "$APPTAINER" exec instance://"$INST_POSTGRES" \
        pg_isready -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1; then
    echo "✓ postgres ready"; break
  fi
  sleep 1
done

# Rootless /dev/shm flakiness → mmap shared memory (idempotent).
PGCONF="$DATA_DIR/postgres/pgdata/postgresql.conf"
if [ -f "$PGCONF" ] && ! grep -qE '^[[:space:]]*dynamic_shared_memory_type[[:space:]]*=[[:space:]]*mmap' "$PGCONF"; then
  echo "→ patching postgresql.conf: shared memory → mmap"
  sed -i -E 's/^[[:space:]]*#?[[:space:]]*shared_memory_type[[:space:]]*=.*/shared_memory_type = mmap/' "$PGCONF" || true
  sed -i -E 's/^[[:space:]]*#?[[:space:]]*dynamic_shared_memory_type[[:space:]]*=.*/dynamic_shared_memory_type = mmap/' "$PGCONF"
  grep -q '^dynamic_shared_memory_type = mmap' "$PGCONF" || echo 'dynamic_shared_memory_type = mmap' >> "$PGCONF"
  "$APPTAINER" instance stop "$INST_POSTGRES" 2>/dev/null || true
  start_instance "$INST_POSTGRES" "$POSTGRES_SIF" \
    --bind "$DATA_DIR/postgres:/var/lib/postgresql/data" \
    --bind "$DATA_DIR/postgres-run:/var/run/postgresql" \
    --env "POSTGRES_USER=${POSTGRES_USER}" --env "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
    --env "POSTGRES_DB=${POSTGRES_DB}" --env "PGPORT=${POSTGRES_PORT}" \
    --env "PGDATA=/var/lib/postgresql/data/pgdata" \
    --env "LANG=C.UTF-8" --env "LC_ALL=C.UTF-8"
  for _i in $(seq 1 40); do
    "$APPTAINER" exec instance://"$INST_POSTGRES" pg_isready -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1 && break
    sleep 1
  done
fi

# ── migrate ─────────────────────────────────────────────────────────
"$SCRIPT_DIR/migrate.sh"

# ── api ─────────────────────────────────────────────────────────────
# Serve the built SPA from the API (single origin) when dist exists.
KOORM_SPA_DIST=""
if [ -f "$REPO_ROOT/platform/frontend/dist/index.html" ]; then
  KOORM_SPA_DIST=/workspace/platform/frontend/dist
  echo "  → API will also serve SPA from frontend/dist"
fi
start_instance "$INST_API" "$API_SIF" \
  --bind "$REPO_ROOT:/workspace" \
  --env "KOORM_API_PORT=${KOORM_API_PORT}" \
  --env "KOORM_DATABASE_URL=${KOORM_DATABASE_URL}" \
  --env "KOORM_JWT_SECRET=${KOORM_JWT_SECRET}" \
  --env "KOORM_CORS_ORIGINS=${KOORM_CORS_ORIGINS}" \
  --env "KOORM_SERVE_FRONTEND_DIST=${KOORM_SPA_DIST}" \
  --env "KOORM_WORKER_CONCURRENCY=${KOORM_WORKER_CONCURRENCY:-4}" \
  --env "KOORM_JOB_TIMEOUT_SEC=${KOORM_JOB_TIMEOUT_SEC:-1800}" \
  --env "KOORM_MAX_UPLOAD_MB=${KOORM_MAX_UPLOAD_MB:-512}" \
  --env "KOORM_HEAX_GATEWAY_SECRET=${KOORM_HEAX_GATEWAY_SECRET:-}" \
  --env "KOORM_APP_ENV=${KOORM_APP_ENV:-development}"

# ── mcp ─────────────────────────────────────────────────────────────
start_instance "$INST_MCP" "$MCP_SIF" \
  --bind "$REPO_ROOT:/workspace" \
  --env "KOOREMAPPER_API_BASE=http://127.0.0.1:${KOORM_API_PORT}" \
  --env "KOORM_MCP_PORT=${KOORM_MCP_PORT}" \
  --env "MCP_HOST=${MCP_HOST:-127.0.0.1}" \
  --env "MCP_ALLOWED_HOSTS=${MCP_ALLOWED_HOSTS:-}"

# ── nginx (optional TLS reverse proxy) ──────────────────────────────
if [ "${KOORM_ENABLE_NGINX:-0}" = "1" ]; then
  [ -f "$NGINX_SIF" ] || "$APPTAINER" build "$NGINX_SIF" "$APPT_DIR/nginx.def"
  [ -f "$PLATFORM_ROOT/infra/nginx/certs/server.crt" ] || "$SCRIPT_DIR/gen-certs.sh"
  start_instance "$INST_NGINX" "$NGINX_SIF" \
    --bind "$PLATFORM_ROOT/infra/nginx/certs:/etc/nginx/certs:ro"
fi

echo
echo "✓ stack started"
echo "  postgres : 127.0.0.1:${POSTGRES_PORT}"
echo "  api      : http://127.0.0.1:${KOORM_API_PORT}/api/docs"
echo "  mcp      : http://127.0.0.1:${KOORM_MCP_PORT}/mcp"
[ "${KOORM_ENABLE_NGINX:-0}" = "1" ] && echo "  nginx    : https://127.0.0.1:${KOORM_HTTPS_PORT}/  (TLS, /api + /mcp 프록시)"
echo "  web(SPA) : http://127.0.0.1:${KOORM_API_PORT}/  (when frontend dist is built + KOORM_SERVE_FRONTEND_DIST set)"
