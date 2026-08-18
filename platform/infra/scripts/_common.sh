#!/usr/bin/env bash
# Shared env for KooRemapper Platform Apptainer orchestration.
set -euo pipefail

# Absolute dir of the scripts (stable regardless of CWD or how $0 was invoked).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# platform/infra/scripts -> repo root (KooRemapper/)
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PLATFORM_ROOT="$REPO_ROOT/platform"
cd "$REPO_ROOT"

[ -f "$PLATFORM_ROOT/.env" ] || {
  echo "✗ platform/.env not found. Run: cp platform/.env.example platform/.env"
  exit 1
}
set -a; . "$PLATFORM_ROOT/.env"; set +a

# Placeholder secret guard (skip with ALLOW_PLACEHOLDER_SECRETS=1).
if [ "${ALLOW_PLACEHOLDER_SECRETS:-0}" != "1" ]; then
  if grep -qE '^(POSTGRES_PASSWORD|KOORM_JWT_SECRET)=CHANGE_ME_' "$PLATFORM_ROOT/.env" \
     || grep -qE '^KOORM_DATABASE_URL=[^/]*//[^:]*:CHANGE_ME_' "$PLATFORM_ROOT/.env"; then
    echo "✗ platform/.env still has CHANGE_ME_* placeholders — rotate POSTGRES_PASSWORD / KOORM_JWT_SECRET"
    echo "  (and the password inside KOORM_DATABASE_URL). Bypass with ALLOW_PLACEHOLDER_SECRETS=1 for throwaway envs."
    exit 1
  fi
  # 비밀번호가 .env 안에 두 번 적힌다 — POSTGRES_PASSWORD 는 컨테이너 초기화용,
  # KOORM_DATABASE_URL 안의 것은 API 가 붙을 때 쓰는 값이다. 한쪽만 고치면 기동은
  # 멀쩡히 되고 API 만 'password authentication failed for user "koorm"' 로 죽는다.
  # 정합을 아무도 안 봐서 cae00 에서 실제로 이 상태가 됐다(2026-08-12). 포트도 같은 이유로 본다.
  if ! python3 - "$PLATFORM_ROOT/.env" <<'PY'
import re, sys, urllib.parse
env = {}
for line in open(sys.argv[1]):
    m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)', line)
    if m:
        env[m.group(1)] = m.group(2).strip().strip('"\'')
dsn = env.get("KOORM_DATABASE_URL")
if not dsn:
    sys.exit(0)                       # DSN 미지정이면 앱 기본값 — 이 검사의 대상이 아니다
u = urllib.parse.urlparse(dsn)
bad = []
if urllib.parse.unquote(u.password or "") != (env.get("POSTGRES_PASSWORD") or ""):
    bad.append("비밀번호가 POSTGRES_PASSWORD 와 KOORM_DATABASE_URL 에서 다르다")
if env.get("POSTGRES_PORT") and str(u.port) != env["POSTGRES_PORT"]:
    bad.append(f"포트가 다르다 (POSTGRES_PORT={env['POSTGRES_PORT']}, DSN={u.port})")
if env.get("POSTGRES_USER") and u.username != env["POSTGRES_USER"]:
    bad.append(f"사용자가 다르다 (POSTGRES_USER={env['POSTGRES_USER']}, DSN={u.username})")
if bad:
    print("✗ platform/.env 불일치 — " + " / ".join(bad), file=sys.stderr)
    sys.exit(1)
PY
  then
    echo "  두 값은 반드시 같아야 한다. 이미 DB 가 만들어져 있으면 .env 만 고치는 걸로는 부족하고,"
    echo "  실행 중인 postgres 의 롤 비밀번호도 함께 맞춰야 한다(데이터는 지우지 말 것):"
    echo "    apptainer exec instance://koorm_postgres psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" \\"
    echo "      -h /var/run/postgresql -p \"\$POSTGRES_PORT\" -c \"ALTER ROLE \$POSTGRES_USER WITH PASSWORD '<새 비번>';\""
    exit 1
  fi
fi

# ── Paths ───────────────────────────────────────────────────────────
APPT_DIR="$PLATFORM_ROOT/infra/apptainer"
DATA_DIR="$PLATFORM_ROOT/infra/data"
mkdir -p "$DATA_DIR/postgres" "$DATA_DIR/postgres-run"

POSTGRES_SIF="$APPT_DIR/postgres.sif"
API_SIF="$APPT_DIR/api.sif"
MCP_SIF="$APPT_DIR/mcp.sif"
NGINX_SIF="$APPT_DIR/nginx.sif"

INST_POSTGRES=koorm_postgres
INST_API=koorm_api
INST_MCP=koorm_mcp
INST_NGINX=koorm_nginx

# 기본 DB 포트 — 5433 이 아니라 5436 이다. 5433 은 Debian/Ubuntu 계열에서 apt 로 깔린 두 번째
# PostgreSQL 클러스터가 쓰는 포트라, 그런 박스에서는 우리 컨테이너가 IPv4 바인드에 실패하고
# IPv6·유닉스소켓으로만 뜬다. 증상은 한참 뒤 alembic 의 'password authentication failed' 로
# 나타나 원인과 전혀 달라 보인다(cae00 2026-08-19: 시스템 postgres pid 1539 가 점유).
# app/config.py 의 기본 DSN 도 5436 이다 — 둘은 반드시 같아야 한다.
# 서비스별 포트 배정은 HWAXPortal/docs/PORT-MAP.md 에 있다. 새 박스는 거기부터 보라.
: "${POSTGRES_PORT:=5436}"
: "${KOORM_API_PORT:=8700}"
: "${KOORM_MCP_PORT:=8701}"
: "${KOORM_HTTPS_PORT:=8443}"
: "${KOORM_HTTP_PORT:=8080}"

# Prefer a local extracted apptainer (no D-Bus / systemd-cgroups requirement).
if [ -z "${APPTAINER:-}" ]; then
  for _c in "$APPT_DIR"/bin-*/usr/bin/apptainer \
            "$HOME"/claude/HWAXPortal/infra/apptainer/bin-*/usr/bin/apptainer \
            "$HOME"/claude/MXWhitePaper/infra/apptainer/bin-*/usr/bin/apptainer; do
    [ -x "$_c" ] && { APPTAINER="$_c"; break; }
  done
fi
: "${APPTAINER:=apptainer}"

require_apptainer() {
  command -v "$APPTAINER" >/dev/null 2>&1 || { echo "✗ '$APPTAINER' not found"; exit 1; }
}

instance_running() {
  "$APPTAINER" instance list --json 2>/dev/null | grep -q "\"instance\": *\"$1\"" || return 1
}
