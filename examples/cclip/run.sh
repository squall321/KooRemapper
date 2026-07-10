#!/usr/bin/env bash
# cclip 예제 실행기 — 박스 생성 → C-clip 치환(analytic) → 자기일관성 검사.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${KOOREMAPPER_BIN:-$HERE/../../build/linux/bin/KooRemapper}"
cd "$HERE"

echo "=== 1/3 입력 박스 생성 ==="
"$BIN" generate box gen_board.yaml

echo "=== 2/3 cclip (analytic) ==="
"$BIN" cclip cclip.yaml

echo "=== 3/3 자기일관성 검사 ==="
python3 ../../tools/cclip_check.py clip_board_cclip.k clip_board_cclip_cclip_report.json

echo ""
echo "deck 모드 변형: $BIN cclip cclip_deck.yaml"
