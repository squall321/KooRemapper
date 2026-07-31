#!/bin/bash
# modelmeta 예제 — cclip 예제의 박스 모델을 재사용한다.
set -e
cd "$(dirname "$0")"
BIN=${KOOREMAPPER:-../../build/linux/bin/KooRemapper}
cp ../cclip/gen_board.yaml .
"$BIN" generate box gen_board.yaml
"$BIN" modelmeta modelmeta.yaml
python3 -m json.tool clip_board_modelmeta.json | head -40
