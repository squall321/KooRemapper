#!/usr/bin/env bash
# squeeze 예제 실행기 — 동봉한 squeeze_box.k 로 ex01~ex05 를 순서대로 돌린다.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${KOOREMAPPER_BIN:-$HERE/../../build/linux/bin/KooRemapper}"
cd "$HERE"

if [ "${1:-}" = "clean" ]; then
    rm -f out_ex0*.k out_ex0*.dynain
    echo "Done."; exit 0
fi

for y in ex01_stress_yaml_material ex02_stress_kfile_material ex03_strain_no_material \
         ex04_swelling ex05_mixed_with_dr; do
    echo "=== $y ==="
    "$BIN" squeeze squeeze_box.k "$y.yaml" "out_${y%%_*}"
done

echo
echo "출력: out_ex01..ex05 의 .k (LS-DYNA 입력) 와 .dynain (초기 응력/변형률)"
