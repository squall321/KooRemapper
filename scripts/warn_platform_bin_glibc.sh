#!/usr/bin/env bash
# 배포용 자리에 복사된 바이너리가 컨테이너에서 돌 수 있나 — 빌드 때 시끄럽게 알린다
#
# 왜 있나 (2026-09-25):
#   `-DKOOREMAPPER_PLATFORM_BIN` 이 켜진 빌드 트리에서 평범한 `cmake --build` 를 돌리면
#   POST_BUILD 복사가 **배포용 바이너리(platform/backend/bin/KooRemapper)를 덮어쓴다.**
#   호스트 glibc 가 컨테이너보다 신형이면 그 순간 그 바이너리는 컨테이너에서 실행 자체가 안 된다.
#   09-24 에 한 번, 09-25 에 또 한 번 이 일이 있었다 — 두 번 다 **아무 말 없이** 일어났다.
#
#   막는 것이 아니라 **말하는 것**이 여기 몫이다. 순수 CLI 개발은 호스트 glibc 로 해도 되고,
#   진짜 관문은 게시 쪽에 있다(`platform/infra/scripts/dist-to-drive.sh` 가 거절한다).
#   여기서 빌드를 실패시키면 컨테이너와 무관한 작업까지 막힌다.
#
# 사용: warn_platform_bin_glibc.sh <바이너리> <상한(예: 2.35)>
set -uo pipefail
BIN="${1:-}"; MAX="${2:-2.35}"
[ -f "$BIN" ] || exit 0
command -v objdump >/dev/null 2>&1 || exit 0   # binutils 없는 호스트 — 조용히 넘어간다

G="$(objdump -T "$BIN" 2>/dev/null | grep -oE 'GLIBC_[0-9.]+' | sort -uV | tail -1 || true)"
G="${G#GLIBC_}"
[ -n "$G" ] || exit 0

if [ "$(printf '%s\n%s\n' "$G" "$MAX" | sort -V | head -1)" != "$G" ]; then
  echo ""
  echo "  ⚠⚠ 이 바이너리는 GLIBC_$G 를 요구한다 — 실사용 컨테이너 상한은 $MAX 다."
  echo "     $BIN"
  echo "     지금 이 파일은 SmartTwinPreprocessor.sif(2.35)·cli.sif(2.36) 안에서 실행되지 않는다."
  echo "     배포용으로 쓰려면: bash scripts/build_linux_compat.sh   (debian:12 빌더)"
  echo "     (게시는 어차피 막힌다 — dist-to-drive.sh 가 거절한다)"
  echo ""
fi
exit 0
