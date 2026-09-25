#!/usr/bin/env bash
# postgres DB 를 infra/data/backups/ 로 덤프한다(인스턴스 안에서 pg_dump).
#
# 되돌리기:
#   gunzip -c <파일> | apptainer exec instance://koorm_postgres \
#     psql -U $POSTGRES_USER -p $POSTGRES_PORT $POSTGRES_DB
#   ⚠ 되돌린 뒤 코드를 그 시점 alembic 리비전에 맞춰야 한다. 최신 코드에 옛 스키마를 붙이면
#     UndefinedColumn 으로 죽는다(09-24 에 실제로 그랬다 — shared_affiliation 미적용).
#
# ⚠ **부분 덤프를 백업처럼 남기지 않는다**(2026-09-25). 예전 구현은 `pg_dump | gzip > OUT` 이라,
#   pg_dump 가 중간에 죽어도 그 자리에 파일이 남았다. gzip 스트림 자체는 정상 종료되므로
#   `gzip -t` 로도 안 걸리고, 14개 보관 정책 아래서 **멀쩡한 백업을 밀어낸다.** 실패가 성공처럼
#   생기는 자리다. 그래서 `.part` 로 받고 **pg_dump 의 완료 표식까지 확인한 뒤** 이름을 바꾼다.
set -euo pipefail
. "$(dirname "$0")/_common.sh"
require_apptainer

_rc=0; instance_running "$INST_POSTGRES" || _rc=$?   # `; _rc=$?` 는 set -e 아래서 여기서 끝난다
case "$_rc" in
  0) ;;
  1) echo "✗ $INST_POSTGRES not running"; exit 1 ;;
  *) echo "✗ 인스턴스 목록을 못 읽었다 — $INST_POSTGRES 상태를 알 수 없어 백업하지 않는다"; exit 1 ;;
esac

BACKUP_DIR="$DATA_DIR/backups"
mkdir -p "$BACKUP_DIR"
# 지난번에 깨진 채 남은 조각을 먼저 걷어낸다 — 보관 정책의 glob 에는 안 걸리므로 계속 쌓인다.
find "$BACKUP_DIR" -maxdepth 1 -name 'koorm_*.sql.gz.part' -mmin +60 -delete 2>/dev/null || true

TS="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/koorm_${TS}.sql.gz"
TMP="$OUT.part"

echo "→ dumping $POSTGRES_DB → $OUT"
if ! "$APPTAINER" exec instance://"$INST_POSTGRES" \
     pg_dump -U "$POSTGRES_USER" -p "$POSTGRES_PORT" "$POSTGRES_DB" | gzip > "$TMP"; then
  rm -f "$TMP"
  echo "✗ pg_dump 가 실패했다 — 부분 파일을 지웠다(이번 백업 없음)" >&2
  exit 1
fi

if ! gzip -t "$TMP" 2>/dev/null; then
  rm -f "$TMP"; echo "✗ gzip 스트림이 깨졌다 — 지웠다" >&2; exit 1
fi
# ⚠ 이 검사가 핵심이다. pg_dump 가 중간에 죽으면 gzip 은 **정상 종료**하므로 위 검사는 통과한다.
# 마지막 줄의 완료 표식만이 "끝까지 떴다" 를 말해 준다.
# 꼬리를 20줄 보는 이유 — 표식 뒤에 오는 줄 수가 pg 판마다 다르다. pg18 은 `\unrestrict …` 를
# 더 붙여 표식이 끝에서 5번째가 된다(`tail -n 5` 면 경계에 딱 걸려 다음 판에서 깨진다).
if ! gunzip -c "$TMP" | tail -n 20 | grep -q 'PostgreSQL database dump complete'; then
  rm -f "$TMP"
  echo "✗ 덤프가 끝까지 안 떴다(완료 표식 없음) — 지웠다" >&2
  exit 1
fi

mv "$TMP" "$OUT"
echo "✓ backup written: $OUT ($(du -h "$OUT" | cut -f1))"

# keep the 14 most recent
ls -1t "$BACKUP_DIR"/koorm_*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
echo "· 보관 중: $(ls -1 "$BACKUP_DIR"/koorm_*.sql.gz 2>/dev/null | wc -l)개"
