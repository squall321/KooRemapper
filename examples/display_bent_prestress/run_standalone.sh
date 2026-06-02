#!/usr/bin/env bash
# ============================================================
#  Display Bent Prestress  —  legacy 2-command chain (POSIX)
# ------------------------------------------------------------
#  Direct 3D HEX8 path via `map` + `prestress`. No assemble,
#  no YAML, no extract-surface prep.
#
#  Inputs / outputs / cleanup: see run_standalone.bat
# ============================================================
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

EXE="${KOOREMAPPER:-}"
if [ -z "$EXE" ]; then
    for cand in \
        "$HERE/../../build/bin/KooRemapper" \
        "$HERE/../../build/bin/Release/KooRemapper" \
        "$HERE/../../build/KooRemapper" \
        "KooRemapper"; do
        if command -v "$cand" >/dev/null 2>&1 || [ -x "$cand" ]; then
            EXE="$cand"; break
        fi
    done
fi
[ -z "$EXE" ] && EXE="KooRemapper"

if [ "${1:-}" = "clean" ]; then
    echo "Cleaning generated files..."
    rm -f detail_bent_display.k detail_bent_display.dynain
    echo "Done."; exit 0
fi

[ -f simple_bent_display.k ] || { echo "[ERROR] simple_bent_display.k not found in $HERE"; exit 1; }
[ -f detail_flat_display.k ] || { echo "[ERROR] detail_flat_display.k not found in $HERE"; exit 1; }

echo
echo "=== Step 1/2 ===  map  (3D bent ref + 3D flat detail -> 3D bent detail)"
"$EXE" map simple_bent_display.k detail_flat_display.k detail_bent_display.k

echo
echo "=== Step 2/2 ===  prestress  (flat + bent -> *INITIAL_STRESS_SOLID dynain)"
"$EXE" prestress detail_flat_display.k detail_bent_display.k detail_bent_display.dynain

echo
echo "============================================================"
echo " Done."
echo "   detail_bent_display.k        <- feed this to LS-DYNA"
echo "                                   (contains *INCLUDE detail_bent_display.dynain)"
echo "   detail_bent_display.dynain   <- *INITIAL_STRESS_SOLID"
echo "============================================================"
