#!/usr/bin/env bash
# Shared env for KooRemapper Platform Apptainer orchestration.
set -euo pipefail

# 사내망 프록시(http_proxy) 환경에서 로컬 헬스체크가 프록시를 타면 안 된다 — 프록시가
# 127.0.0.1 에 못 닿아 curl 이 000 을 내고(실사고: cae00 update-forges), 스크립트가
# 서비스를 죽은 것으로 오판한다. 바깥용(git·rclone) http_proxy 는 그대로 두고 로컬만 우회한다.
export NO_PROXY="127.0.0.1,localhost,::1${NO_PROXY:+,$NO_PROXY}"
export no_proxy="$NO_PROXY"

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

# 인스턴스가 떠 있는가 — **0 있음 · 1 없음 · 2 알 수 없음**(목록 조회 자체가 실패했다).
#
# ⚠ 예전 구현은 `"$APPTAINER" instance list --json | grep -q …` 였다. 이 파일을 읽는 스크립트들이
# `pipefail` 을 켜는데, `grep -q` 는 **첫 매칭에서 바로 끝나고** 그러면 아직 쓰고 있던 apptainer 가
# **SIGPIPE(141)** 로 죽는다. pipefail 이 파이프라인 전체를 실패로 만들므로 **떠 있는 인스턴스를
# "없다"로** 판정했다. 감독자는 그 판정을 믿고 멀쩡한 API 를 stop/start 했다(09-18 하루 168회).
#
# 실측(2026-09-19, dev) — **유휴에서는 400회 중 0회**다. 하지만 같은 박스에서 다른 프로세스가
# 동시에 `instance list` 를 부르는 동안(허브 워커가 45초마다, 배포 스크립트가 수시로) **600회 중
# 81회(13.5%)** 가 rc=141 로 거짓 음성이었다. "유휴에서 재현 안 되니 원인이 아니다" 는 그래서 틀린
# 판정이다 — 감독자는 30초마다 도니 하루 2,880회이고, 실제 관측치(하루 28~168회)와 자릿수가 맞는다.
#
# 고침은 둘이다.
#   ㉮ **파이프를 없앤다** — 출력을 통째로 받으면 조기 종료가 없어 SIGPIPE 가 날 자리가 없다.
#   ㉯ **조회 실패와 부재를 가른다** — 옛 구현은 둘을 같은 1 로 뭉갰고 그 뭉갬이 사고의 본질이다.
#      한 번 더 시도해 보고도 실패하면 2(모름)를 낸다. 단순 호출부(`if ! instance_running …`)에서는
#      2 도 0 이 아니라 종전과 똑같이 동작하고, **감독자만** 2 를 "이번 회차 건너뜀" 으로 다룬다.
#      모르는 것을 "없다" 로 읽으면 재기동이라는 파괴적 행동이 따라붙기 때문이다.
instance_running() {
  local out rc i
  rc=1
  for i in 1 2; do
    if out="$("$APPTAINER" instance list --json 2>/dev/null)"; then rc=0; else rc=$?; fi
    [ "$rc" -eq 0 ] && [ -n "$out" ] && break
    [ "$i" -eq 1 ] && sleep 0.5
  done
  if [ "$rc" -ne 0 ] || [ -z "${out:-}" ]; then
    return 2
  fi
  # apptainer 판에 따라 `"instance": "x"` 와 `"instance":"x"` 둘 다 나올 수 있다
  case "$out" in
    *"\"instance\": \"$1\""*|*"\"instance\":\"$1\""*) return 0 ;;
    *) return 1 ;;
  esac
}
