#!/usr/bin/env bash
# SmartTwinPreprocessor.sif 가 구워 갈 **스테이징 사본**을 최신 바이너리로 갱신한다.
#
# 왜 이 스크립트가 있나 (실측 2026-10-02, 재확인 2026-10-06).
#   `BuildSmartTwinPreprocessor.sh` 는 `appt313/opt/kooremapper/bin` 을 **그대로 복사**할 뿐이고
#   그 스테이징 사본을 갱신하는 장치가 없었다. 그래서 SIF 를 다시 구워도 **구 바이너리가 그대로
#   나갔다** — 10-02 의 재bake 가 09-28 바이너리를 구웠고 SIF 날짜만 새로워서 안 보였다.
#   10-06 에 또 같은 상태였다(스테이징 10-02 본, 배포 SIF 가 세 그림 op 을 0개 알았다).
#   그 자리를 사람이 기억하는 대신 **빌드가 하게** 만든다.
#
# 쓰는 곳
#   · `BuildSmartTwinPreprocessor.sh` 가 굽기 **전에** 부른다(그게 이 스크립트의 요점이다).
#   · 손으로: `bash scripts/stage-to-appt313.sh [--check] [--with-cli-sif]`
#
# 규율
#   · 백업은 `bin/` **밖**(`bin-backups/`)에 둔다 — `bin/` 은 통째로 구워져 SIF 에 두 번째
#     바이너리가 들어간다(실측으로 그 실수를 했다).
#   · glibc 요구를 **검사한다** — 실사용 소비자 중 최솟값이 SmartTwinPreprocessor.sif 의 2.35 다.
#     그보다 신형을 요구하는 바이너리를 구우면 컨테이너 안에서 아예 돌지 않는다.
#   · 소스를 못 찾으면 **조용히 넘기지 않고** 지금 구워질 사본의 sha·날짜를 크게 적는다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
STAGE="${KOOREMAPPER_APPT313:-/home/koopark/serviceApptainers/appt313/opt/kooremapper}"
MAX_GLIBC_ALLOWED="2.35"

CHECK_ONLY=0
WITH_SIF=0
for a in "$@"; do
  case "$a" in
    --check)         CHECK_ONLY=1 ;;
    --with-cli-sif)  WITH_SIF=1 ;;
    *) echo "✗ 알 수 없는 인자: $a  (--check | --with-cli-sif)" >&2; exit 1 ;;
  esac
done

[ -d "$STAGE/bin" ] || { echo "✗ 스테이징이 없다: $STAGE/bin  (KOOREMAPPER_APPT313 로 바꿀 수 있다)" >&2; exit 1; }

sha() { sha256sum "$1" | cut -d' ' -f1; }
sha8() { sha "$1" | cut -c1-8; }

# ── 0. 통합 셰임(kooremapper_module.py · README.md) — 바이너리와 같이 늙는다 ──
#   실측 10-06: 바이너리는 자동 갱신됐지만 이 둘은 07-05 본이 석 달째 구워지고 있었다
#   (리포는 09-21 카드 직렬화 경화본). run.sh 는 스테이징 전용(cli.sif 경로)이라 안 건드린다.
SHIM_SRC="$REPO/platform/integrations/pykoocae"
SHIM_STALE=0
for f in kooremapper_module.py README.md; do
  [ -f "$SHIM_SRC/$f" ] || continue
  [ -f "$STAGE/$f" ] && [ "$(sha "$SHIM_SRC/$f")" = "$(sha "$STAGE/$f")" ] && continue
  if [ "$CHECK_ONLY" = "1" ]; then
    echo "→ --check: $f 갱신 필요($(sha8 "$STAGE/$f") → $(sha8 "$SHIM_SRC/$f"))"; SHIM_STALE=1
  else
    install -m 644 "$SHIM_SRC/$f" "$STAGE/$f"; echo "✓ $f 교체: $(sha8 "$STAGE/$f")"
  fi
done

# ── 1. 소스 고르기. 명시 > 리포 compat 빌드 > 게시 슬롯 ──
SRC="${KOOREMAPPER_BIN:-}"
if [ -z "$SRC" ]; then
  for c in "$REPO/build/linux/bin/KooRemapper" "$REPO/platform/backend/bin/KooRemapper"; do
    [ -x "$c" ] && { SRC="$c"; break; }
  done
fi

STAGED="$STAGE/bin/KooRemapper"
echo "  스테이징 현재: $(sha8 "$STAGED")  $(date -r "$STAGED" -u +%Y-%m-%dT%H:%MZ)"

if [ -z "$SRC" ]; then
  # ★조용히 넘기지 않는다 — 이 경고가 없어서 구 바이너리가 두 번 나갔다.
  echo "⚠ ────────────────────────────────────────────────────────────────────" >&2
  echo "⚠ 최신 KooRemapper 바이너리를 **못 찾았다**. 스테이징 사본을 그대로 굽는다." >&2
  echo "⚠   찾아본 곳: \$KOOREMAPPER_BIN · $REPO/build/linux/bin · $REPO/platform/backend/bin" >&2
  echo "⚠   구워질 것: $(sha "$STAGED")" >&2
  echo "⚠   그 날짜  : $(date -r "$STAGED" -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  echo "⚠ 의도한 것이 아니면 멈추고 \`scripts/build_linux_compat.sh\` 를 먼저 돌려라." >&2
  echo "⚠ ────────────────────────────────────────────────────────────────────" >&2
  exit 0
fi

echo "  소스        : $SRC  ($(sha8 "$SRC"))"

# ── 2. glibc 검사 — 신형을 요구하면 컨테이너에서 아예 안 돈다 ──
if command -v objdump >/dev/null 2>&1; then
  MAXG=$(objdump -T "$SRC" 2>/dev/null | grep -oE 'GLIBC_[0-9.]+' | sort -uV | tail -1 || true)
  echo "  glibc 최고  : ${MAXG:-없음} (허용 <= GLIBC_${MAX_GLIBC_ALLOWED})"
  case "${MAXG:-}" in
    GLIBC_2.3[6-9]*|GLIBC_2.[4-9]*|GLIBC_[3-9]*)
      echo "✗ 컨테이너 비호환 glibc 요구 — SmartTwinPreprocessor.sif(2.35)에서 돌지 않는다." >&2
      echo "  scripts/build_linux_compat.sh (debian:12 빌더)로 빌드한 바이너리를 쓰라." >&2
      exit 1 ;;
  esac
else
  echo "  glibc 최고  : (objdump 없음 — 검사 못 함)"
fi

if [ "$(sha "$SRC")" = "$(sha "$STAGED")" ]; then
  echo "✓ 바이너리 스테이징은 이미 최신이다 — 바꿀 것이 없다."
  [ "$WITH_SIF" = "1" ] || exit "$(( SHIM_STALE ? 2 : 0 ))"
fi

if [ "$CHECK_ONLY" = "1" ]; then
  echo "→ --check: 바꾸지 않는다. 갱신이 **필요하다**($(sha8 "$STAGED") → $(sha8 "$SRC"))."
  exit 2
fi

# ── 3. 백업(bin 밖!) → 교체 → BUILD_INFO ──
mkdir -p "$STAGE/bin-backups"
if [ "$(sha "$SRC")" != "$(sha "$STAGED")" ]; then
  OLD8=$(sha8 "$STAGED")
  BK="$STAGE/bin-backups/KooRemapper.bak-${OLD8}-$(date -u +%Y%m%d%H%M%S)"
  cp -p "$STAGED" "$BK"
  install -m 755 "$SRC" "$STAGED"
  echo "✓ 바이너리 교체: $OLD8 → $(sha8 "$STAGED")   (백업 $(basename "$BK"))"

  COMMIT=$(cd "$REPO" && git rev-parse HEAD 2>/dev/null || echo "(git 없음)")
  BRANCH=$(cd "$REPO" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
  DIRTY=$(cd "$REPO" && { git diff --quiet HEAD -- src include CMakeLists.txt 2>/dev/null && echo clean || echo "dirty(src)"; })
  cat > "$STAGE/bin/KooRemapper.BUILD_INFO.txt" <<EOF
KooRemapper (SmartTwinPreprocessor.sif 스테이징 사본)
  교체일   : $(date -u +%Y-%m-%dT%H:%M:%SZ)
  교체주체 : scripts/stage-to-appt313.sh (빌드가 자동 갱신)
  소스 커밋: $COMMIT
  브랜치   : $BRANCH ($DIRTY)
  소스 경로: $SRC
  빌드 방법: scripts/build_linux_compat.sh (debian:12 빌더)
  sha256   : $(sha "$STAGED")
  크기     : $(stat -c%s "$STAGED") bytes
  glibc 최고: ${MAXG:-?}
  이전 사본: $(basename "$BK")
EOF
  echo "✓ BUILD_INFO 기록"
fi

# ── 4. cli.sif (bake 에는 안 들어간다 — run_example.sh 의 ALT 경로용) ──
if [ "$WITH_SIF" = "1" ]; then
  NEWSIF="$REPO/platform/infra/apptainer/cli.sif"
  if [ -f "$NEWSIF" ] && [ "$(sha "$NEWSIF")" != "$(sha "$STAGE/cli.sif")" ]; then
    cp -p "$STAGE/cli.sif" "$STAGE/cli.sif.bak.$(date +%s)"
    install -m 755 "$NEWSIF" "$STAGE/cli.sif"
    echo "✓ cli.sif 교체: $(sha8 "$STAGE/cli.sif")"
  else
    echo "✓ cli.sif 는 이미 최신이거나 소스가 없다"
  fi
fi

echo "✓ 스테이징 준비 완료 — 구워질 바이너리 sha256 $(sha "$STAGED")"
