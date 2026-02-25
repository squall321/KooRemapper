#!/bin/bash
# Run all implicit YAML examples with KooRemapper.
# Usage: ./run_all.sh [path/to/KooRemapper]
# Default: looks for KooRemapper in PATH, then ../../build/bin/Release/KooRemapper

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve KooRemapper binary
if [[ $# -ge 1 ]]; then
    KR="$1"
elif command -v KooRemapper &>/dev/null; then
    KR="KooRemapper"
elif [[ -x "$SCRIPT_DIR/../../build/bin/Release/KooRemapper" ]]; then
    KR="$SCRIPT_DIR/../../build/bin/Release/KooRemapper"
else
    echo "ERROR: KooRemapper not found. Pass path as argument: $0 /path/to/KooRemapper"
    exit 1
fi

echo "KooRemapper: $KR"
echo "Directory  : $SCRIPT_DIR"
echo "----------------------------------------"

PASS=0
FAIL=0
SKIP=0

run_yaml() {
    local yaml="$1"
    local name
    name="$(basename "$yaml")"

    # Skip documentation-only files that have no real model
    case "$name" in
        implicit_full.yaml|implicit_minimal.yaml)
            printf "  %-36s  SKIP (doc only)\n" "$name"
            (( SKIP++ )) || true
            return
            ;;
    esac

    printf "  %-36s  " "$name"
    if "$KR" implicit "$yaml" >/dev/null 2>&1; then
        echo "PASS"
        (( PASS++ )) || true
    else
        echo "FAIL"
        (( FAIL++ )) || true
    fi
}

# Static levels
echo "[Static]"
for f in "$SCRIPT_DIR"/level{1,2,3,4,5,6,7,8}.yaml; do
    [[ -f "$f" ]] && run_yaml "$f"
done

echo ""
echo "[Dynamic]"
for f in "$SCRIPT_DIR"/dynamic_lv{1,2,3,4,5,6,7,8}.yaml; do
    [[ -f "$f" ]] && run_yaml "$f"
done

echo ""
echo "[Other]"
for f in "$SCRIPT_DIR"/implicit_minimal.yaml "$SCRIPT_DIR"/implicit_full.yaml; do
    [[ -f "$f" ]] && run_yaml "$f"
done

echo "----------------------------------------"
printf "PASS: %d  FAIL: %d  SKIP: %d\n" "$PASS" "$FAIL" "$SKIP"
[[ $FAIL -eq 0 ]]
