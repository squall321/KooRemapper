#!/usr/bin/env bash
# glibc 2.36 호환 리눅스 빌드 — debian:12 빌더 컨테이너에서 빌드해 api/cli 컨테이너·HPC 노드에서 실행 가능한 바이너리 생산.
# (호스트 glibc가 2.36보다 신형이면 호스트 빌드 바이너리는 컨테이너 안에서 돌지 않는다.)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
BUILDER_DEF="$ROOT/platform/infra/apptainer/builder.def"
BUILDER_SIF="$ROOT/platform/infra/apptainer/builder.sif"
BUILD_DIR="build/linux-compat"

if ! command -v apptainer >/dev/null 2>&1; then
    echo "ERROR: apptainer not found"; exit 1
fi

if [ ! -f "$BUILDER_SIF" ] || [ "$BUILDER_DEF" -nt "$BUILDER_SIF" ]; then
    echo "[0/3] builder.sif 빌드 (최초 1회)..."
    ( cd "$(dirname "$BUILDER_DEF")" && apptainer build --force "$(basename "$BUILDER_SIF")" "$(basename "$BUILDER_DEF")" )
fi

echo "[1/3] configure + build (debian:12, glibc 2.36)..."
apptainer exec --bind "$ROOT:$ROOT" --pwd "$ROOT" "$BUILDER_SIF" \
    sh -c "cmake -DCMAKE_BUILD_TYPE=Release -S . -B '$BUILD_DIR' >/dev/null && cmake --build '$BUILD_DIR' -j\$(nproc)"

BIN="$ROOT/$BUILD_DIR/bin/KooRemapper"
echo "[2/3] glibc 요구 검증..."
MAXG=$(objdump -T "$BIN" | grep -oE 'GLIBC_[0-9.]+' | sort -uV | tail -1)
echo "  최고 요구: ${MAXG:-none} (허용: <= GLIBC_2.36)"
case "$MAXG" in
    GLIBC_2.3[7-9]*|GLIBC_2.[4-9]*) echo "ERROR: 컨테이너 비호환 glibc 요구"; exit 1 ;;
esac

echo "[3/3] 설치: build/linux/bin + platform/backend/bin..."
install -m 755 "$BIN" "$ROOT/build/linux/bin/KooRemapper"
install -m 755 "$BIN" "$ROOT/platform/backend/bin/KooRemapper"
echo "✓ done: $ROOT/build/linux/bin/KooRemapper ($MAXG)"
