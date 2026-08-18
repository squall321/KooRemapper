#!/usr/bin/env bash
# KooRemapper prod 배포 아티팩트를 Google Drive(rclone)로 publish 한다 — HEAXHub dist-to-drive 와
# 동일 패턴. 폐쇄망 운영서버(Docker Hub/PyPI/GitHub 차단, Drive 는 도달)가 git·빌드 없이
# 아티팩트를 받아 뜰 수 있게 한다.
#
# 올리는 것(모두 gitignore 라 git pull 로 안 감):
#   - platform/backend/bin/KooRemapper   (glibc≤2.36 compat 바이너리 — debian:12 빌더 산출)
#   - platform/frontend/dist             (standalone + portal(index.portal.html) 듀얼 빌드)
#   - platform/infra/apptainer/cli.sif   (배치잡용 자체완결 CLI, 있으면)
#
# ONLINE 빌드 호스트에서, 빌드까지 한 번에:
#   bash platform/infra/scripts/dist-to-drive.sh --build   # compat 빌드+듀얼 프론트+cli.sif 후 publish
#   bash platform/infra/scripts/dist-to-drive.sh           # 이미 빌드된 산출물만 publish
#
# platform/.env 필요:  KOORM_DRIVE_REMOTE=<rclone remote>:KooRemapper/dist
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$(cd "$PLATFORM_ROOT/.." && pwd)"
cd "$REPO_ROOT"

env_get() { [ -f platform/.env ] && sed -n "s/^$1=//p" platform/.env | tail -1 | sed 's/^["'"'"']//; s/["'"'"']$//'; }
KOORM_DRIVE_REMOTE="${KOORM_DRIVE_REMOTE:-$(env_get KOORM_DRIVE_REMOTE)}"
KOORM_DRIVE_RETAIN="${KOORM_DRIVE_RETAIN:-$(env_get KOORM_DRIVE_RETAIN)}"

command -v rclone >/dev/null 2>&1 || { echo "✗ rclone 미설치 (https://rclone.org/install/)"; exit 1; }
REMOTE="${KOORM_DRIVE_REMOTE:-}"
[ -n "$REMOTE" ] || { echo "✗ KOORM_DRIVE_REMOTE 미설정 (예: HeaxDrive:KooRemapper/dist)"; exit 1; }
REMOTE="${REMOTE%/}"
RETAIN="${KOORM_DRIVE_RETAIN:-3}"

if [ "${1:-}" = "--build" ]; then
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

TS="$(date -u +%Y%m%d-%H%M%SZ)"
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT

echo "  · binary + gmsh 번들 → koorm-bin.tar.gz"
# -h(심볼릭 링크 역참조)가 핵심이다. bin/gmsh/gmsh.exe 는 dist/gmsh/gmsh(87MB)를 가리키는
# 링크인데, -h 가 없으면 tar 가 '링크 자체'만 담는다. 받는 쪽엔 dist/gmsh 가 없으므로
# 깨진 링크가 풀리고, meshfix 는 영영 못 쓴다 — 주석은 'gmsh 번들'이라 적혀 있는데 실제로는
# 한 번도 실려 간 적이 없었다(cae00 이 매 배포마다 'gmsh not linked' 를 찍었다).
tar -C platform/backend -chzf "$STAGE/koorm-bin.tar.gz" bin
echo "  · frontend/dist → koorm-frontend-dist.tar.gz"
tar -C platform/frontend -czf "$STAGE/koorm-frontend-dist.tar.gz" dist
# 서비스 SIF(postgres/api/mcp/nginx) + cli.sif — 오프라인 prod 가 build.sh 없이 뜨도록
# (build.sh 는 멱등이라 SIF 존재 시 스킵). 있는 것만 올린다.
shopt -s nullglob
for s in platform/infra/apptainer/*.sif; do
  cp "$s" "$STAGE/"; echo "  · $(basename "$s") 포함"
done
shopt -u nullglob
( cd "$STAGE" && sha256sum ./* > SHA256SUMS )

DEST="$REMOTE/dist-$TS"
echo "→ publish: $DEST"
rclone copy --progress "$STAGE/" "$DEST/"
rclone copy --progress "$STAGE/" "$REMOTE/latest/"   # prod 는 latest/ 를 먼저 본다

# 오래된 dist-* 정리 (최근 RETAIN 개 유지)
mapfile -t OLD < <(rclone lsf --dirs-only "$REMOTE/" 2>/dev/null | sed 's#/$##' | grep -E '^dist-' | sort | head -n -"$RETAIN")
for d in "${OLD[@]:-}"; do [ -n "$d" ] && { rclone purge "$REMOTE/$d" 2>/dev/null && echo "  · 정리: $d"; }; done

echo "✓ publish 완료 ($TS). prod: bash platform/infra/scripts/dist-from-drive.sh"
