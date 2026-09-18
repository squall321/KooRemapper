#!/bin/bash
# modelmeta 예제 — cclip 의 박스 생성 YAML 을 이 폴더로 복사해 입력 clip_board.k 를 직접 만든다.
set -e
cd "$(dirname "$0")"
BIN="${KOOREMAPPER_BIN:-../../build/linux/bin/KooRemapper}"
cp ../cclip/gen_board.yaml .
"$BIN" generate box gen_board.yaml
"$BIN" modelmeta modelmeta.yaml
python3 -m json.tool clip_board_modelmeta.json | head -40
