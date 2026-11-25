#!/usr/bin/env bash
# DESTRUCTIVE — stop postgres and wipe its data dir, then restart fresh.
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

read -rp "This deletes ALL postgres data in $DATA_DIR/postgres. Type 'yes' to continue: " ans
[ "$ans" = "yes" ] || { echo "aborted"; exit 1; }

# ⚠ 여기서 "없다" 를 잘못 믿으면 **살아 있는 postmaster 위에서 pgdata 를 지운다.** 그러면 인스턴스는
# 삭제된 inode 로 계속 돌고, 안내대로 start.sh 를 돌려도 `✓ already running` 으로 그냥 돌아와
# 겉보기엔 멀쩡한데 내용이 없는 DB 가 된다. 그래서 여기만은 **확실할 때만** 진행한다.
_rc=0; instance_running "$INST_POSTGRES" || _rc=$?   # `; _rc=$?` 는 set -e 아래서 여기서 끝난다
case "$_rc" in
  0) echo "→ stop $INST_POSTGRES"; "$APPTAINER" instance stop "$INST_POSTGRES" || true
     # 내려가는 중인 postmaster 밑의 데이터를 지우지 않는다(R-04) — 정말 사라진 것을 본 뒤에만 지운다
     wait_instance_gone "$INST_POSTGRES" || { echo "✗ postgres 가 아직 사라지지 않았다 — 지우지 않는다."; exit 1; } ;;
  1) ;;  # 확실히 없다 — 그대로 진행
  *) echo "✗ 인스턴스 목록을 못 읽었다 — 살아 있는지 알 수 없어 지우지 않는다."
     echo "  apptainer instance list 가 되는지 확인한 뒤 다시 실행하라."; exit 1 ;;
esac
rm -rf "$DATA_DIR/postgres" "$DATA_DIR/postgres-run"
mkdir -p "$DATA_DIR/postgres" "$DATA_DIR/postgres-run"
echo "✓ postgres data wiped — run start.sh to recreate"
