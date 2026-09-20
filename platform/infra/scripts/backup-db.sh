#!/usr/bin/env bash
# Dump the postgres DB to infra/data/backups/ (pg_dump inside the instance).
# Restore: gunzip -c <file> | apptainer exec instance://koorm_postgres psql -U $POSTGRES_USER -p $POSTGRES_PORT $POSTGRES_DB
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
# timestamp from the running postgres (scripts can't call date in some sandboxes,
# but this is a normal shell — date is fine here).
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/koorm_${TS}.sql.gz"

echo "→ dumping $POSTGRES_DB → $OUT"
"$APPTAINER" exec instance://"$INST_POSTGRES" \
  pg_dump -U "$POSTGRES_USER" -p "$POSTGRES_PORT" "$POSTGRES_DB" | gzip > "$OUT"
echo "✓ backup written: $OUT ($(du -h "$OUT" | cut -f1))"

# keep the 14 most recent
ls -1t "$BACKUP_DIR"/koorm_*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
