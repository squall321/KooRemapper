#!/usr/bin/env bash
# KooRemapper prod 배포 아티팩트를 Google Drive(rclone)에서 받아 제자리에 푼다 — HEAXHub
# dist-from-drive 와 동일 패턴. 이후 start.sh 가 바이너리·dist 를 존재 전제로 인스턴스를 띄운다.
#
# 받는 것:  platform/backend/bin/  (KooRemapper 바이너리+gmsh),  platform/frontend/dist/,
#           platform/infra/apptainer/cli.sif (있으면)
#
# platform/.env 필요:  KOORM_DRIVE_REMOTE=<rclone remote>:KooRemapper/dist
# 이후:  bash platform/infra/scripts/start.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$(cd "$PLATFORM_ROOT/.." && pwd)"
cd "$REPO_ROOT"

env_get() { [ -f platform/.env ] && sed -n "s/^$1=//p" platform/.env | tail -1 | sed 's/^["'"'"']//; s/["'"'"']$//'; }
KOORM_DRIVE_REMOTE="${KOORM_DRIVE_REMOTE:-$(env_get KOORM_DRIVE_REMOTE)}"

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

STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
rclone copy --progress "$SRC/" "$STAGE/"
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
  cp -f "$STAGE/BUILD_INFO.txt" platform/backend/bin/BUILD_INFO.txt
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
  cp -f "$s" "platform/infra/apptainer/$(basename "$s")"; echo "  ✓ $(basename "$s") 반입"
done
shopt -u nullglob

echo "✓ 아티팩트 반입 완료. 다음: bash platform/infra/scripts/start.sh"
