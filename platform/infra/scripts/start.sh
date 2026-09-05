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
# ⚠ pg_isready 는 인증을 하지 않는다 — "접속을 받는다"까지만 본다. 인스턴스는 호스트
# 네트워크를 공유하므로, 같은 포트를 이미 물고 있는 *다른* postmaster 가 있으면 이 검사는
# 그 남의 서버를 보고 초록을 찍는다. 그때 우리 postgres 는 IPv4 바인드에 실패하고
# ("could not bind IPv4 address ... Address already in use") IPv6·유닉스소켓으로만 뜬다.
# 실패는 30줄 뒤 alembic 의 'password authentication failed for user koorm' 로 나타나,
# 원인과 증상이 완전히 달라 보인다(cae00 2026-08-18 실제 사고).
# 그래서 두 경로를 따로 확인한다 — 유닉스소켓은 우리 것이 확실하고, TCP 는 아닐 수 있다.
pg_id() {  # $1: -h 값 → 그 서버의 클러스터 식별자. 못 붙거나 인증 실패면 빈 문자열.
  # 인증 통과만으로는 부족하다 — 남의 postmaster 가 trust 로 받으면 그것도 통과한다.
  # system_identifier 는 데이터디렉토리(클러스터)마다 다르므로 '같은 서버인가'를 정확히 가른다.
  APPTAINERENV_PGPASSWORD="$POSTGRES_PASSWORD" "$APPTAINER" exec instance://"$INST_POSTGRES" \
    psql -h "$1" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -Atc 'select system_identifier from pg_control_system()' 2>/dev/null | tr -dc '0-9' || true
  # ⚠ || true 가 핵심이다. 이 파일은 set -euo pipefail 이라, psql 이 실패하면 pipefail 로
  # 파이프라인이 비0 이 되고 _id="$(pg_id …)" 대입이 비0 → set -e 가 그 자리에서 스크립트를
  # 죽인다. 아래 진단문이 한 줄도 못 나온 채 끝난다(cae00 2026-08-18: "waiting for postgres…"
  # 다음이 그냥 없었다). 붙는 데 실패하는 것은 이 함수의 정상 결과다 — 빈 문자열로 알린다.
}
_sock_id=""
for _i in $(seq 1 40); do
  _sock_id="$(pg_id /var/run/postgresql)"
  [ -n "$_sock_id" ] && break
  sleep 1
done
if [ -z "$_sock_id" ]; then
  echo "✗ postgres 가 뜨지 않았다 (유닉스소켓으로도 응답 없음) — 인스턴스 로그를 보라:"
  echo "    $APPTAINER instance list; $APPTAINER logs $INST_POSTGRES"
  exit 1
fi
_tcp_id="$(pg_id 127.0.0.1)"
# TCP 가 어긋났을 때 원인은 둘인데 조치가 정반대다.
#   (a) 다른 postmaster 가 포트를 물고 있다        → 그것을 멈춰야 한다
#   (b) 포트는 지금 비었는데 우리가 IPv4 를 못 잡았다 → 우리를 재기동하면 된다
# postgres 는 기동 때 한 번만 바인드한다. 그래서 기동 순간 남이 물고 있었으면 IPv6·소켓으로만
# 뜨고, 그 남이 나중에 사라져도 우리는 영영 IPv4 에 안 붙는다. 이때 '남이 물고 있다'고만
# 말하면 사람이 있지도 않은 범인을 찾는다(cae00 2026-08-18: 소켓 정상 · TCP 응답없음).
if [ "$_tcp_id" != "$_sock_id" ] && [ -z "$_tcp_id" ] \
   && ! (exec 3<>"/dev/tcp/127.0.0.1/${POSTGRES_PORT}") 2>/dev/null; then
  echo "  · 포트 ${POSTGRES_PORT} 는 지금 비어 있다 — 기동 순간에만 막혔던 것이다. 재기동한다."
  "$APPTAINER" instance stop "$INST_POSTGRES" >/dev/null 2>&1 || true
  start_instance "$INST_POSTGRES" "$POSTGRES_SIF" \
    --bind "$DATA_DIR/postgres:/var/lib/postgresql/data" \
    --bind "$DATA_DIR/postgres-run:/var/run/postgresql" \
    --env "POSTGRES_USER=${POSTGRES_USER}" --env "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
    --env "POSTGRES_DB=${POSTGRES_DB}" --env "PGPORT=${POSTGRES_PORT}" \
    --env "PGDATA=/var/lib/postgresql/data/pgdata" \
    --env "LANG=C.UTF-8" --env "LC_ALL=C.UTF-8"
  for _i in $(seq 1 40); do
    _sock_id="$(pg_id /var/run/postgresql)"; [ -n "$_sock_id" ] && break
    sleep 1
  done
  _tcp_id="$(pg_id 127.0.0.1)"
fi
if [ "$_tcp_id" != "$_sock_id" ]; then
  echo "✗ 127.0.0.1:${POSTGRES_PORT} 가 우리 postgres 가 아니다."
  echo "    유닉스소켓 클러스터=${_sock_id}  /  TCP 클러스터=${_tcp_id:-(응답없음·인증실패)}"
  echo "  그 포트를 다른 프로세스가 물고 있어서 우리 쪽은 IPv4 바인드에 실패했다"
  echo "  (postgres 로그의 'could not bind IPv4 address ... Address already in use')."
  echo "  이대로 두면 alembic 이 'password authentication failed for user ${POSTGRES_USER}' 로 죽는다."
  # 사람에게 명령을 시키지 말고 여기서 바로 찍는다 — 이 왕복이 세 번 반복됐다.
  # 한 박스에 postgres 인스턴스가 대여섯 개씩 뜨므로(aidh·mxwp·heax·sf·axwb…) 이름이 곧 답이다.
  echo "  포트 ${POSTGRES_PORT} 를 잡고 있는 것:"
  { ss -lptnH "sport = :${POSTGRES_PORT}" 2>/dev/null \
    || lsof -iTCP:"${POSTGRES_PORT}" -sTCP:LISTEN -Pn 2>/dev/null; } | sed 's/^/    /' \
    || echo "    (권한 부족으로 프로세스명을 못 봤다 — sudo ss -lptn 로 다시 보라)"
  echo "  이 박스의 postgres 인스턴스:"
  "$APPTAINER" instance list 2>/dev/null | grep -i postgres | awk '{printf "    %-24s pid=%s\n",$1,$2}' \
    || echo "    (없음)"
  # 소유자가 안 보이면(=users: 가 비어 있으면) 남의 계정 프로세스다. 그 사실을 말해 주지 않으면
  # 사람이 ss 를 아무리 다시 돌려도 범인 이름을 못 본다(cae00 2026-08-19 실측).
  if ! ss -lptnH "sport = :${POSTGRES_PORT}" 2>/dev/null | grep -q 'users:('; then
    echo "  ⚠ 소유자가 안 보인다 = 다른 사용자(root 등)의 프로세스다. 이름을 보려면:"
    echo "      sudo ss -lptn 'sport = :${POSTGRES_PORT}'"
  fi
  # 그 프로세스를 못 건드릴 수도 있으므로, 우리가 비켜 갈 포트를 바로 제안한다.
  _free=""
  for _p in $(seq $((POSTGRES_PORT+1)) $((POSTGRES_PORT+20))); do
    ss -lntH "sport = :${_p}" 2>/dev/null | grep -q . && continue
    _free="$_p"; break
  done
  if [ -n "$_free" ]; then
    echo "  그 프로세스를 멈출 수 없으면 koorm 을 비어 있는 포트로 옮겨라 — ${_free} 가 비어 있다."
    echo "    platform/.env 의 두 값을 함께 고쳐야 한다(둘이 어긋나면 기동 전 검사에서 걸린다):"
    echo "      POSTGRES_PORT=${_free}"
    echo "      KOORM_DATABASE_URL=…@127.0.0.1:${_free}/…"
  else
    echo "  koorm 것이 아니면 그 서비스의 포트를 바꾸거나, koorm 의 POSTGRES_PORT 를 옮겨라."
  fi
  exit 1
fi
echo "✓ postgres ready"

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
  # 재기동 뒤에도 같은 함정이 있다 — 인증까지 하는 프로브로 확인한다(위 주석 참조).
  # 재기동 뒤에도 같은 함정이 있다 — 같은 판별을 다시 한다(위 주석 참조).
  _sock_id=""
  for _i in $(seq 1 40); do
    _sock_id="$(pg_id /var/run/postgresql)"
    [ -n "$_sock_id" ] && break
    sleep 1
  done
  if [ -z "$_sock_id" ] || [ "$(pg_id 127.0.0.1)" != "$_sock_id" ]; then
    echo "✗ mmap 재기동 후 127.0.0.1:${POSTGRES_PORT} 가 우리 postgres 가 아니다 — 포트 점유 프로세스를 확인하라."
    exit 1
  fi
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
# /data 레지스트리 바인드(HWAXPortal docs/data-migration D9) — 컨테이너는 호스트 /data 를 못 본다(실측). 대상 디렉터리가
# **존재하면** 동일경로로 바인드한다(env 조건 없이 — 이관 도구가 디렉터리를 만든 뒤 재기동해 가시성을 확인한다).
# KOORM_STORAGE_DIR 는 레지스트리가 이동 뒤에만 주입한다(pydantic env_prefix KOORM_ 로 storage_dir 오버라이드).
KOORM_DATA_BINDS=(); _d="${HWAX_DATA_ROOT:-/data}/svc/kooremapper"; [ -d "$_d" ] && KOORM_DATA_BINDS+=(--bind "$_d:$_d")
start_instance "$INST_API" "$API_SIF" \
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

# ── 기동 확인 ───────────────────────────────────────────────────────
# instance start 는 '컨테이너를 띄웠다'까지만 말한다. 안의 프로세스가 부팅 중에 죽어도
# 성공으로 돌아오므로, 예전엔 api·mcp 가 통째로 죽은 상태에서도 "✓ stack started" 가
# 찍혔다. 그 거짓 초록은 한참 뒤 다른 얼굴로 나타난다 — 게이트웨이의 kr_ PAT 발급 실패,
# heax 앱 502, MCP 도구 0개. 전부 여기서 안 뜬 것이 원인인데 원인처럼 보이지 않는다.
wait_http() {  # $1: URL, $2: 이름 → 응답이 오면 0. 상태코드는 안 따진다(MCP 루트는 400/404 가 정상).
  for _i in $(seq 1 40); do
    curl -s -o /dev/null -m 3 "$1" && return 0
    sleep 1
  done
  return 1
}
_down=""
wait_http "http://127.0.0.1:${KOORM_API_PORT}/api/health" api || _down="$_down api(:${KOORM_API_PORT})"
wait_http "http://127.0.0.1:${KOORM_MCP_PORT}/mcp"        mcp || _down="$_down mcp(:${KOORM_MCP_PORT})"
if [ -n "$_down" ]; then
  echo
  echo "✗ 인스턴스는 떴는데 응답하지 않는다:$_down"
  echo "  안의 프로세스가 부팅 중에 죽은 것이다. 로그를 보라:"
  for _n in "$INST_API" "$INST_MCP"; do
    echo "    $APPTAINER logs $_n"
  done
  echo "  이 상태를 방치하면 게이트웨이 kr_ PAT 발급 실패·heax 앱 502·MCP 도구 0개로 나타난다."
  exit 1
fi

echo
echo "✓ stack started"
echo "  postgres : 127.0.0.1:${POSTGRES_PORT}"
echo "  api      : http://127.0.0.1:${KOORM_API_PORT}/api/docs"
echo "  mcp      : http://127.0.0.1:${KOORM_MCP_PORT}/mcp"
[ "${KOORM_ENABLE_NGINX:-0}" = "1" ] && echo "  nginx    : https://127.0.0.1:${KOORM_HTTPS_PORT}/  (TLS, /api + /mcp 프록시)"
echo "  web(SPA) : http://127.0.0.1:${KOORM_API_PORT}/  (when frontend dist is built + KOORM_SERVE_FRONTEND_DIST set)"
