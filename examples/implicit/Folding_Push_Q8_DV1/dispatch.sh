#!/bin/bash
# dispatch.sh - K 파일별로 폴더를 만들고 run.sh를 실행합니다.
#
# 전제 조건 (현재 디렉토리에 있어야 함):
#   - *.k          변환된 implicit K 파일들
#   - run.sh       LS-DYNA 실행 스크립트 (./run.sh <kfile> <configfile>)
#   - config.json  솔버 설정 파일
#
# Usage:
#   ./dispatch.sh               # 순차 실행
#   ./dispatch.sh --parallel    # 병렬 실행 (모든 job 동시 시작)

set -uo pipefail

PARALLEL=false
[[ "${1:-}" == "--parallel" ]] && PARALLEL=true

ROOT="$(pwd)"

# ── 전제 조건 확인 ────────────────────────────────────────────
if [[ ! -f "$ROOT/run.sh" ]]; then
    echo "ERROR: run.sh not found in current directory ($ROOT)"
    exit 1
fi
if [[ ! -f "$ROOT/config.json" ]]; then
    echo "ERROR: config.json not found in current directory ($ROOT)"
    exit 1
fi

shopt -s nullglob
KFILES=("$ROOT"/*.k)
if [[ ${#KFILES[@]} -eq 0 ]]; then
    echo "ERROR: No .k files found in $ROOT"
    exit 1
fi

echo "================================================================"
echo "  dispatch.sh"
echo "  Root    : $ROOT"
echo "  K-files : ${#KFILES[@]}"
echo "  Mode    : $( $PARALLEL && echo PARALLEL || echo SEQUENTIAL )"
echo "================================================================"

# ── 개별 job 실행 함수 ───────────────────────────────────────
run_one() {
    local kfile="$1"
    local kname; kname="$(basename "$kfile")"
    local jobname="${kname%.k}"
    local jobdir="$ROOT/$jobname"
    local logfile="$jobdir/run.log"

    # 폴더 생성 및 파일 복사
    mkdir -p "$jobdir"
    cp "$ROOT/run.sh"      "$jobdir/"
    cp "$ROOT/config.json" "$jobdir/"
    cp "$kfile"            "$jobdir/"

    printf "  [%-30s] starting...\n" "$jobname"

    # 해당 폴더에서 실행, 로그 저장
    (
        cd "$jobdir"
        ./run.sh "$kname" config.json
    ) > "$logfile" 2>&1
    local ret=$?

    if [[ $ret -eq 0 ]]; then
        printf "  [%-30s] DONE   → %s\n" "$jobname" "$logfile"
    else
        printf "  [%-30s] FAILED (exit %d) → %s\n" "$jobname" "$ret" "$logfile"
    fi
    return $ret
}

# ── 실행 ─────────────────────────────────────────────────────
FAIL=0

if $PARALLEL; then
    PIDS=()
    for kfile in "${KFILES[@]}"; do
        run_one "$kfile" &
        PIDS+=($!)
    done
    for pid in "${PIDS[@]}"; do
        wait "$pid" || (( FAIL++ )) || true
    done
else
    for kfile in "${KFILES[@]}"; do
        run_one "$kfile" || (( FAIL++ )) || true
    done
fi

# ── 결과 요약 ─────────────────────────────────────────────────
TOTAL=${#KFILES[@]}
PASS=$(( TOTAL - FAIL ))
echo "================================================================"
printf "  PASS: %d  FAIL: %d  TOTAL: %d\n" "$PASS" "$FAIL" "$TOTAL"
echo "================================================================"

[[ $FAIL -eq 0 ]]
