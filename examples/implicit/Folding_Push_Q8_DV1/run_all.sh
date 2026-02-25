#!/bin/bash
# Run all implicit YAML examples for Folding_Push_Q8_DV1_AdvancedRubber.k
# Usage: ./run_all.sh [path/to/KooRemapper[.exe]]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve KooRemapper binary
if [[ $# -ge 1 ]]; then
    KR="$1"
elif command -v KooRemapper &>/dev/null; then
    KR="KooRemapper"
elif command -v KooRemapper.exe &>/dev/null; then
    KR="KooRemapper.exe"
elif [[ -x "$SCRIPT_DIR/../../../../build/bin/Release/KooRemapper.exe" ]]; then
    KR="$SCRIPT_DIR/../../../../build/bin/Release/KooRemapper.exe"
else
    echo "ERROR: KooRemapper not found. Pass path as argument: $0 /path/to/KooRemapper"
    exit 1
fi

echo "KooRemapper : $KR"
echo "Model       : Folding_Push_Q8_DV1_AdvancedRubber.k"
echo "Directory   : $SCRIPT_DIR"
echo "========================================================"

PASS=0; FAIL=0

run() {
    local yaml="$1"
    local name; name="$(basename "$yaml")"
    printf "  %-36s  " "$name"
    if "$KR" implicit "$yaml" >/dev/null 2>&1; then
        echo "PASS"; (( PASS++ )) || true
    else
        echo "FAIL"; (( FAIL++ )) || true
    fi
}

echo "[Static  Lv1~8]"
for lv in 1 2 3 4 5 6 7 8; do
    run "$SCRIPT_DIR/static_level${lv}.yaml"
done

echo ""
echo "[Dynamic Lv1~8]"
for lv in 1 2 3 4 5 6 7 8; do
    run "$SCRIPT_DIR/dynamic_lv${lv}.yaml"
done

echo ""
echo "[Full Options]"
run "$SCRIPT_DIR/implicit_full.yaml"

echo ""
echo "========================================================"
printf "PASS: %d  FAIL: %d  TOTAL: %d\n" "$PASS" "$FAIL" $(( PASS + FAIL ))
[[ $FAIL -eq 0 ]]
