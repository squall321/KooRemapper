#!/usr/bin/env bash
# KooRemapper prod 배포 아티팩트를 Google Drive(rclone)로 publish 한다 — HEAXHub dist-to-drive 와
# 동일 패턴. 폐쇄망 운영서버(Docker Hub/PyPI/GitHub 차단, Drive 는 도달)가 git·빌드 없이
# 아티팩트를 받아 뜰 수 있게 한다.
#
# 올리는 것(모두 gitignore 라 git pull 로 안 감):
#   - platform/backend/bin/KooRemapper   (glibc≤2.35 compat 바이너리 — debian:12 빌더 산출)
#   - platform/frontend/dist             (standalone + portal(index.portal.html) 듀얼 빌드)
#   - platform/infra/apptainer/cli.sif   (배치잡용 자체완결 CLI, 있으면)
#
# 게시물에는 BUILD_INFO.txt 도 같이 올라간다 — 어느 소스로 만든 바이너리인지(커밋·브랜치·
# 해시·빌드 방법) 운영에서 되짚을 수 있게. 바이너리는 모두 'version 1.8.0' 만 찍으므로
# 이 파일이 유일한 추적 정보다.
#
# ONLINE 빌드 호스트에서, 빌드까지 한 번에:
#   bash platform/infra/scripts/dist-to-drive.sh --build   # compat 빌드+듀얼 프론트+cli.sif 후 publish
#   bash platform/infra/scripts/dist-to-drive.sh           # 이미 빌드된 산출물만 publish
#   bash platform/infra/scripts/dist-to-drive.sh --dry-run # 스테이지만 만들어 보여주고 업로드는 하지 않음
#   (glibc 를 확인 못 하는 호스트에서 알고 넘기려면 --allow-unknown-glibc)
#
# platform/.env 필요:  KOORM_DRIVE_REMOTE=<rclone remote>:KooRemapper/dist
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$(cd "$PLATFORM_ROOT/.." && pwd)"
cd "$REPO_ROOT"

# platform/.env 가 없을 때 &&-체인이 1 을 반환해 set -e 로 스크립트가 아무 말 없이 죽었다 — return 0 으로 끊는다.
env_get() { [ -f platform/.env ] || return 0; sed -n "s/^$1=//p" platform/.env | tail -1 | sed 's/^["'"'"']//; s/["'"'"']$//'; }
KOORM_DRIVE_REMOTE="${KOORM_DRIVE_REMOTE:-$(env_get KOORM_DRIVE_REMOTE)}"
KOORM_DRIVE_RETAIN="${KOORM_DRIVE_RETAIN:-$(env_get KOORM_DRIVE_RETAIN)}"

DO_BUILD=0; DRY_RUN=0; ALLOW_UNKNOWN_GLIBC=0
for a in "$@"; do
  case "$a" in
    --build)   DO_BUILD=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --allow-unknown-glibc) ALLOW_UNKNOWN_GLIBC=1 ;;
    *) echo "✗ 알 수 없는 인자: $a  (--build | --dry-run | --allow-unknown-glibc)"; exit 1 ;;
  esac
done

# 컨테이너 허용 glibc 상한 — **실사용 소비자 중 최솟값**이다(2026-09-25 실측 `ldd --version`).
#   SmartTwinPreprocessor.sif  2.35   ← pyKooCAE REMAP 체인이 돌리는 그것. 가장 낮다
#   cli.sif                    2.36
#   api.sif / mcp.sif          2.41   (Debian 13 trixie)
# ⚠ 계획서가 적은 "2.37 이상 거절" 은 **두 칸 느슨하다.** 2.36 을 요구하는 바이너리는 그 관문을
# 통과하고도 REMAP 체인에서 실행 자체가 안 된다. 그래서 최솟값을 택한다. 소비자가 바뀌면
# 이 숫자와 위 표를 같이 고쳐야 한다 — 숫자만 조용히 바꾸지 마라.
MAX_GLIBC="2.35"

# "$1 <= $2" (둘 다 2.35 꼴). 글롭 비교(`GLIBC_2.3[7-9]*`)를 쓰지 않는 이유 — 2.40 처럼
# minor 가 두 자리로 넘어가면 패턴이 통째로 빗나간다.
glibc_le() { [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -1)" = "$1" ]; }

if [ "$DRY_RUN" = "0" ]; then
  command -v rclone >/dev/null 2>&1 || { echo "✗ rclone 미설치 (https://rclone.org/install/)"; exit 1; }
fi
REMOTE="${KOORM_DRIVE_REMOTE:-}"
if [ -z "$REMOTE" ]; then
  [ "$DRY_RUN" = "1" ] || { echo "✗ KOORM_DRIVE_REMOTE 미설정 (예: HeaxDrive:KooRemapper/dist)"; exit 1; }
  REMOTE="(KOORM_DRIVE_REMOTE 미설정)"
fi
REMOTE="${REMOTE%/}"
RETAIN="${KOORM_DRIVE_RETAIN:-3}"

if [ "$DO_BUILD" = "1" ]; then
  echo "→ compat 바이너리 빌드 (debian:12 빌더, glibc≤2.36)"
  bash scripts/build_linux_compat.sh
  echo "→ 프론트 듀얼 빌드 (standalone + portal)"
  bash platform/infra/scripts/build-frontend.sh
  echo "→ cli.sif 빌드"
  bash platform/infra/scripts/build-cli.sh || echo "  ⚠ cli.sif 빌드 실패(비치명) — 배치잡만 영향"
fi

BIN="platform/backend/bin/KooRemapper"
DIST="platform/frontend/dist/index.html"
[ -f "$BIN" ] || { echo "✗ $BIN 없음 — --build 로 먼저 빌드하라"; exit 1; }
[ -f "$DIST" ] || { echo "✗ $DIST 없음 — --build 로 먼저 빌드하라"; exit 1; }

# 포털 배포용 index 가드 — index.portal.html 없으면 포털 서브패스에서 자산 404.
if [ ! -f platform/frontend/dist/index.portal.html ] && [ "${KOORM_DIST_ALLOW_NO_PORTAL:-0}" != "1" ]; then
  echo "✗ dist/index.portal.html 없음 — 포털(/apps/kooremapper/) 서브패스 자산이 깨진다."
  echo "  재빌드: bash platform/infra/scripts/build-frontend.sh (듀얼 빌드)"
  echo "  (의도적으로 standalone 만 배포하려면 KOORM_DIST_ALLOW_NO_PORTAL=1)"
  exit 1
fi

# ── glibc 관문 ────────────────────────────────────────────────────────────
# ⚠ 여기서 막지 않으면 아무도 막지 않는다. 09-24 에 다른 세션이 호스트 cmake 로 빌드해
# 이 자리의 바이너리가 GLIBC_2.38 을 요구하고 있었다 — 그대로 게시했으면 폐쇄망 운영에
# **실행 자체가 안 되는** 바이너리가 나갔다. 예전 구현은 값을 BUILD_INFO 에 적기만 했다.
#
# objdump 미설치(127)나 GLIBC 심볼 없는 바이너리면 grep 이 1 을 돌려주고, pipefail 이 그 값을
# 파이프라인 종료코드로 올려 set -e 가 여기서 스크립트를 아무 말 없이 끝냈다(폐쇄망 = binutils 없음).
# 종료코드를 삼켜 빈 값으로 흘리고, '알 수 없음' 을 **등급으로** 다룬다(커밋 b7e6bea 의 의도).
BIN_GLIBC="$(objdump -T "$BIN" 2>/dev/null | grep -oE 'GLIBC_[0-9.]+' | sort -uV | tail -1 || true)"
_bg="${BIN_GLIBC#GLIBC_}"
if [ -z "$_bg" ]; then
  if [ "$ALLOW_UNKNOWN_GLIBC" = "1" ]; then
    echo "  ⚠ glibc 요구를 확인할 수 없다(objdump 없음 또는 GLIBC 심볼 없음) — --allow-unknown-glibc 로 넘어간다"
  else
    echo "✗ 바이너리의 glibc 요구를 확인할 수 없다 — objdump(binutils)가 없거나 GLIBC 심볼이 없다."
    echo "  확인 못 한 것을 게시하지 않는다. binutils 를 깔거나, 알고 넘기려면 --allow-unknown-glibc."
    exit 1
  fi
elif ! glibc_le "$_bg" "$MAX_GLIBC"; then
  echo "✗ 이 바이너리는 GLIBC_$_bg 를 요구한다 — 실사용 컨테이너 상한은 $MAX_GLIBC 다."
  echo "  그대로 게시하면 SmartTwinPreprocessor.sif(2.35)에서 실행 자체가 안 된다."
  echo "  고치는 법: bash scripts/build_linux_compat.sh   (debian:12 빌더)"
  exit 1
else
  echo "  · glibc 요구 GLIBC_$_bg <= $MAX_GLIBC ✓"
fi

TS="$(date -u +%Y%m%d-%H%M%SZ)"
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT

echo "  · binary + gmsh 번들 → koorm-bin.tar.gz"
# -h(심볼릭 링크 역참조)가 핵심이다. bin/gmsh/gmsh.exe 는 dist/gmsh/gmsh(87MB)를 가리키는
# 링크인데, -h 가 없으면 tar 가 '링크 자체'만 담는다. 받는 쪽엔 dist/gmsh 가 없으므로
# 깨진 링크가 풀리고, meshfix 는 영영 못 쓴다 — 주석은 'gmsh 번들'이라 적혀 있는데 실제로는
# 한 번도 실려 간 적이 없었다(cae00 이 매 배포마다 'gmsh not linked' 를 찍었다).
# BUILD_INFO.txt 는 제외한다 — 그것은 스테이지에 **따로** 올라가고 받는 쪽이 bin/ 에 내려놓는다.
# 빼지 않으면 앞선 반입으로 bin/ 에 남은 **옛 것**이 tar 에 실려, 풀린 뒤 덮어쓰기 순서에 따라
# 어느 쪽이 남을지 헷갈린다.
tar -C platform/backend --exclude=bin/BUILD_INFO.txt -chzf "$STAGE/koorm-bin.tar.gz" bin
echo "  · frontend/dist → koorm-frontend-dist.tar.gz"
tar -C platform/frontend -czf "$STAGE/koorm-frontend-dist.tar.gz" dist
# 서비스 SIF(postgres/api/mcp/nginx) + cli.sif — 오프라인 prod 가 build.sh 없이 뜨도록
# (build.sh 는 멱등이라 SIF 존재 시 스킵). 있는 것만 올린다.
shopt -s nullglob
for s in platform/infra/apptainer/*.sif; do
  # builder.sif 는 **빌드 전용**(debian:12 툴체인, 171MB)이라 prod 가 쓸 일이 없다. glob 이 그것까지
  # 집어 가서 매 배포마다 폐쇄망 회선으로 171MB 가 헛나갔다(보관 3판이면 500MB). 위 주석이 적은
  # 의도('서비스 SIF + cli.sif')대로 걸러낸다.
  case "$(basename "$s")" in builder.sif) echo "  · builder.sif 제외(빌드 전용)"; continue ;; esac
  cp "$s" "$STAGE/"; echo "  · $(basename "$s") 포함"
done
shopt -u nullglob
echo "  · BUILD_INFO.txt (소스 커밋·바이너리 해시·빌드 방법)"
# 네 곳의 바이너리가 모두 'version 1.8.0' 만 찍어 운영에서 출처를 구분할 수 없었다.
# CMakeLists/C++ 은 건드리지 않고(윈도 빌드 영향) 여기서 git 으로 알아내 같이 올린다.
git_or() { git "$@" 2>/dev/null || true; }
GIT_SHA="$(git_or rev-parse HEAD)"
GIT_SUBJ="$(git_or log -1 --pretty=%s)"
GIT_BRANCH="$(git_or rev-parse --abbrev-ref HEAD)"
if [ "$GIT_BRANCH" = "HEAD" ]; then GIT_BRANCH="(detached HEAD)"; fi
GIT_DESCRIBE="$(git_or describe --tags --always --dirty)"
GIT_REMOTE="$(git_or config --get remote.origin.url)"
if [ -n "$(git_or status --porcelain)" ]; then GIT_STATE="dirty (커밋되지 않은 변경이 있다)"; else GIT_STATE="clean"; fi

BIN_MD5="$(md5sum "$BIN" | cut -d' ' -f1)"
BIN_SHA="$(sha256sum "$BIN" | cut -d' ' -f1)"
BIN_SIZE="$(stat -c %s "$BIN")"
BIN_MTIME="$(date -u -d "@$(stat -c %Y "$BIN")" +%Y-%m-%dT%H:%M:%SZ)"
COMPAT_OUT="build/linux-compat/bin/KooRemapper"
if [ "$DO_BUILD" = "1" ]; then
  BUILD_METHOD="scripts/build_linux_compat.sh (이 실행의 --build)"
elif [ -f "$COMPAT_OUT" ] && [ "$(md5sum "$COMPAT_OUT" | cut -d' ' -f1)" = "$BIN_MD5" ]; then
  BUILD_METHOD="scripts/build_linux_compat.sh (앞선 실행 — $COMPAT_OUT 와 동일)"
else
  BUILD_METHOD="알 수 없음 (사전 빌드 산출물 — build_linux_compat.sh 산출물과 일치하지 않음)"
fi

cat > "$STAGE/BUILD_INFO.txt" <<EOF
KooRemapper 배포 아티팩트 빌드 정보
published_utc : $(date -u +%Y-%m-%dT%H:%M:%SZ)
stage         : dist-$TS

[source]
commit        : ${GIT_SHA:-알 수 없음}
subject       : ${GIT_SUBJ:-알 수 없음}
branch        : ${GIT_BRANCH:-알 수 없음}
describe      : ${GIT_DESCRIBE:-알 수 없음}
remote        : ${GIT_REMOTE:-알 수 없음}
worktree      : $GIT_STATE

[binary] $BIN
size          : $BIN_SIZE bytes
mtime_utc     : $BIN_MTIME
md5           : $BIN_MD5
sha256        : $BIN_SHA
glibc_max     : ${BIN_GLIBC:-알 수 없음 (objdump 없음 또는 GLIBC 심볼 없음)} (실사용 상한: <= GLIBC_$MAX_GLIBC — SmartTwinPreprocessor.sif 기준)
build_method  : $BUILD_METHOD
EOF

( cd "$STAGE" && sha256sum ./* > SHA256SUMS )

DEST="$REMOTE/dist-$TS"
if [ "$DRY_RUN" = "1" ]; then
  echo "→ --dry-run: 업로드하지 않는다. 올라갈 내용은 아래와 같다 (대상이었다면 $DEST)"
  ls -l "$STAGE"
  echo "----- BUILD_INFO.txt -----"
  cat "$STAGE/BUILD_INFO.txt"
  echo "----- SHA256SUMS -----"
  cat "$STAGE/SHA256SUMS"
  exit 0
fi
echo "→ publish: $DEST"
rclone copy --progress "$STAGE/" "$DEST/"
rclone copy --progress "$STAGE/" "$REMOTE/latest/"   # prod 는 latest/ 를 먼저 본다

# 오래된 dist-* 정리 (최근 RETAIN 개 유지)
mapfile -t OLD < <(rclone lsf --dirs-only "$REMOTE/" 2>/dev/null | sed 's#/$##' | grep -E '^dist-' | sort | head -n -"$RETAIN")
for d in "${OLD[@]:-}"; do [ -n "$d" ] && { rclone purge "$REMOTE/$d" 2>/dev/null && echo "  · 정리: $d"; }; done

echo "✓ publish 완료 ($TS). prod: bash platform/infra/scripts/dist-from-drive.sh"
