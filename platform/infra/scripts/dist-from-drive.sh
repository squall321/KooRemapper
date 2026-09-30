#!/usr/bin/env bash
# KooRemapper prod 배포 아티팩트를 Google Drive(rclone)에서 받아 제자리에 푼다 — HEAXHub
# dist-from-drive 와 동일 패턴. 이후 start.sh 가 바이너리·dist 를 존재 전제로 인스턴스를 띄운다.
#
# 받는 것:  platform/backend/bin/  (KooRemapper 바이너리+gmsh),  platform/frontend/dist/,
#           platform/infra/apptainer/cli.sif (있으면)
#
# platform/.env 필요:  KOORM_DRIVE_REMOTE=<rclone remote>:KooRemapper/dist
#
# 쓰는 법:
#   bash platform/infra/scripts/dist-from-drive.sh            # 반입만
#   bash platform/infra/scripts/dist-from-drive.sh --restart   # 반입 + 기동/마이그레이션 + API 재기동
#
# ⚠ `--restart` 가 있는 이유. 반입만 하면 **새 코드가 안 올라간다.** 반입 뒤 `start.sh` 를 돌려도
# 그 안의 `start_instance` 는 이미 떠 있으면 `✓ already running` 으로 건너뛰므로, 아티팩트와 코드는
# 새것인데 API 는 옛 코드로 계속 돈다. 그 상태는 겉으로 성공처럼 보이고(헬스 200) 새 기능만 조용히
# 없어서, "게시가 안 됐다" 로 오해하기 쉽다. 세 줄을 순서대로, 그중 하나는 함정까지 기억해야 하는
# 절차는 언젠가 틀린다 — 그래서 한 줄로 만든다.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$(cd "$PLATFORM_ROOT/.." && pwd)"
cd "$REPO_ROOT"

env_get() { [ -f platform/.env ] && sed -n "s/^$1=//p" platform/.env | tail -1 | sed 's/^["'"'"']//; s/["'"'"']$//'; }
KOORM_DRIVE_REMOTE="${KOORM_DRIVE_REMOTE:-$(env_get KOORM_DRIVE_REMOTE)}"

DO_RESTART=0
for a in "$@"; do
  case "$a" in
    --restart) DO_RESTART=1 ;;
    *) echo "✗ 알 수 없는 인자: $a  (--restart)"; exit 1 ;;
  esac
done

command -v rclone >/dev/null 2>&1 || { echo "✗ rclone 미설치 (https://rclone.org/install/)"; exit 1; }
REMOTE="${KOORM_DRIVE_REMOTE:-}"
[ -n "$REMOTE" ] || { echo "✗ KOORM_DRIVE_REMOTE 미설정 (예: HeaxDrive:KooRemapper/dist)"; exit 1; }
REMOTE="${REMOTE%/}"

SRC="$REMOTE/latest"
# 파이프+조기종료(grep -q)는 pipefail 아래서 SIGPIPE(141) 오판을 만든다 — 출력을 먼저 받는다(_common.sh:instance_running 주석).
_listing="$(rclone lsf "$SRC/" 2>/dev/null || true)"
case $'\n'"$_listing"$'\n' in
  *$'\n'koorm-bin.tar.gz$'\n'*) _have_bin=1 ;;
  *) _have_bin=0 ;;
esac
if [ "$_have_bin" = "0" ]; then
  NEWEST="$(rclone lsf --dirs-only "$REMOTE/" 2>/dev/null | sed 's#/$##' | grep -E '^dist-' | sort | tail -n 1 || true)"
  [ -n "$NEWEST" ] || { echo "✗ $REMOTE 에 dist 없음. 온라인 호스트에서: bash platform/infra/scripts/dist-to-drive.sh --build"; exit 1; }
  SRC="$REMOTE/$NEWEST"
fi
echo "→ source: $SRC"

# 같은 내용이면 손대지 않는다 — 살아 있는 apptainer 인스턴스 밑의 SIF 를 덮어쓰면 squashfs 가 깨지고, cp 는 mtime 을 리셋해 포털 update-all 의
# 재기동 판정(지문: 이름·크기·mtime)이 매번 달라진다. 영구 캐시(rclone 이 안 바뀐 파일을 건너뛴다)와 짝이다. HWAXPortal docs/update-all-skip-unchanged.
_install_if_changed() { if [ -f "$2" ] && cmp -s "$1" "$2"; then echo "  · $(basename "$2") 같음 — 그대로"; return 0; fi; cp -p "$1" "$2" || { echo "  ✗ $(basename "$2") 설치 실패 — $2 에 쓸 수 없다(권한·소유자·디스크). 옛 파일이 그대로다" >&2; return 2; }; }
# 영구 캐시 — 임시 디렉터리면 rclone 이 비교할 것이 없어 매번 전량 전송이다. 캐시에 받으면 안 바뀐 파일은 전송 0.
STAGE="${KOORM_DRIVE_CACHE:-platform/infra/apptainer/.drive-cache}"; mkdir -p "$STAGE"
rclone sync --progress "$SRC/" "$STAGE/"    # sync — 원격에서 뺀 파일이 캐시에 남지 않게
[ -f "$STAGE/SHA256SUMS" ] && { ( cd "$STAGE" && sha256sum -c SHA256SUMS ) && echo "  ✓ checksums OK" || { echo "✗ checksum 실패"; exit 1; }; }

# 바이너리 + gmsh
if [ -f "$STAGE/koorm-bin.tar.gz" ]; then
  mkdir -p platform/backend
  tar -C platform/backend -xzf "$STAGE/koorm-bin.tar.gz"
  chmod +x platform/backend/bin/KooRemapper 2>/dev/null || true
  # build/linux/bin 에도 사본 (build-cli.sh 등 참조 경로 호환)
  mkdir -p build/linux/bin && cp -f platform/backend/bin/KooRemapper build/linux/bin/KooRemapper 2>/dev/null || true
  # ⚠ `sort -uV` 다. 예전엔 `sort -u`(사전순)여서 GLIBC_2.38 을 요구하는 바이너리를 받고도
  # "GLIBC_2.4" 라고 찍었다("2.38" < "2.4" 가 사전순이다). 받는 쪽 readout 이 거짓말을 하면
  # 운영에서 되짚을 근거가 없다. 패턴도 올리는 쪽(dist-to-drive.sh)과 같은 것을 쓴다.
  echo "  ✓ bin/KooRemapper 반입 ($(objdump -T platform/backend/bin/KooRemapper 2>/dev/null | grep -oE 'GLIBC_[0-9.]+' | sort -uV | tail -1))"
fi
# BUILD_INFO.txt — **바이너리와 같은 자리에 내려놓는다.** 예전에는 스테이지에만 받아 두고
# 스테이지째로 지워서(mktemp + trap) 받는 쪽 디스크에 **한 번도 내려앉지 않았다.** 그래서
# 운영에서 "지금 도는 바이너리가 어느 커밋인가" 를 물을 곳이 없었다. /api/health 가 이 파일을 읽는다.
if [ -f "$STAGE/BUILD_INFO.txt" ]; then
  mkdir -p platform/backend/bin
  _install_if_changed "$STAGE/BUILD_INFO.txt" platform/backend/bin/BUILD_INFO.txt   # cp -f 는 mtime 을 리셋해 포털의 재기동 판정 지문이 매번 달라졌다
  echo "  ✓ BUILD_INFO.txt 반입 ($(sed -n 's/^commit *: //p' platform/backend/bin/BUILD_INFO.txt | cut -c1-12))"
fi
# frontend dist
if [ -f "$STAGE/koorm-frontend-dist.tar.gz" ]; then
  mkdir -p platform/frontend
  tar -C platform/frontend -xzf "$STAGE/koorm-frontend-dist.tar.gz"
  echo "  ✓ frontend/dist 반입 (portal index: $([ -f platform/frontend/dist/index.portal.html ] && echo yes || echo no))"
fi
# 서비스 SIF + cli.sif — build.sh 는 멱등이라 존재 시 스킵하고 바로 start.
mkdir -p platform/infra/apptainer
shopt -s nullglob
for s in "$STAGE"/*.sif; do
  _install_if_changed "$s" "platform/infra/apptainer/$(basename "$s")"; echo "  ✓ $(basename "$s") 반입"
done
shopt -u nullglob

if [ "$DO_RESTART" = "0" ]; then
  echo "✓ 아티팩트 반입 완료. 다음: bash platform/infra/scripts/start.sh"
  echo "  ⚠ 그런데 그것만으로는 **새 코드가 안 올라간다** — `start.sh` 의 `start_instance` 는 이미"
  echo "    떠 있으면 건너뛴다. 한 줄로 끝내려면: bash platform/infra/scripts/dist-from-drive.sh --restart"
  exit 0
fi

# ── --restart: 반입 뒤 끝까지 세운다 ────────────────────────────────────────
# 순서가 중요하다. `start.sh` 는 postgres → **alembic upgrade head** → api 순서라(start.sh:44·179·194)
# 스키마가 API 보다 먼저 선다. 다만 api 가 **이미 떠 있으면 건너뛰므로**, 마이그레이션 뒤에
# api 만 따로 재기동해야 새 컬럼과 새 코드가 같이 선다.
echo "→ start.sh (없는 인스턴스 기동 + alembic upgrade head)"
bash "$SCRIPT_DIR/start.sh"
echo "→ restart-api-only.sh (start.sh 는 살아 있는 api 를 재기동하지 않는다)"
bash "$SCRIPT_DIR/restart-api-only.sh"

# ── 확인 — "성공했다" 를 스스로 말하지 않는다 ───────────────────────────────
# ⚠ `/` 가 아니라 `/api/health` 를 보고 **200 을 요구한다.** `/` 는 SPA 라 백엔드가 고장나도
# 200 을 준다. 그리고 로컬 헬스체크는 사내 프록시를 타면 안 된다(curl 000 오판).
export NO_PROXY="127.0.0.1,localhost,::1${NO_PROXY:+,$NO_PROXY}"; export no_proxy="$NO_PROXY"
PORT="$(env_get KOORM_API_PORT)"; PORT="${PORT:-8700}"
_code=000
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 2
  _code="$(curl -s -o /tmp/koorm-health.$$ -w '%{http_code}' -m 5 \
           "http://127.0.0.1:$PORT/api/health" 2>/dev/null || echo 000)"
  [ "$_code" = "200" ] && break
done
if [ "$_code" != "200" ]; then
  echo "✗ /api/health → $_code — 반입은 됐지만 서비스가 서지 않았다."
  echo "  볼 곳: ~/.apptainer/instances/logs/*/*/koorm_api.err (마지막 30줄)"
  rm -f /tmp/koorm-health.$$
  exit 1
fi
python3 - "/tmp/koorm-health.$$" <<'PY' || cat "/tmp/koorm-health.$$"
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8")).get("data", {})
print("✓ /api/health 200")
for k in ("revision", "published_utc", "binary_sha256", "revision_matches_binary"):
    v = d.get(k)
    print("    %-24s %s" % (k, (v[:12] if k == "binary_sha256" and isinstance(v, str) else v)))
g = d.get("gmsh") or {}
print("    %-24s available=%s version=%s" % ("gmsh", g.get("available"), g.get("version")))
# ⚠ 이것이 어긋나면 revision 을 믿을 수 없다 — BUILD_INFO 와 실물 바이너리가 다른 상태다.
if d.get("revision_matches_binary") is False:
    print("  ⚠ BUILD_INFO 의 해시와 실제 바이너리가 어긋난다 — 반입이 반쪽이다.")
PY
rm -f /tmp/koorm-health.$$
echo "✓ 반입 + 기동 + 확인 완료"
