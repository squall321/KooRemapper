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
if ! rclone lsf "$SRC/" 2>/dev/null | grep -q '^koorm-bin\.tar\.gz$'; then
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
  echo "  ✓ bin/KooRemapper 반입 ($(objdump -T platform/backend/bin/KooRemapper 2>/dev/null | grep -oE 'GLIBC_2\.[0-9]+' | sort -u | tail -1))"
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
