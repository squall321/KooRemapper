#!/bin/sh
# 시험용 실행기(정리 기록판) — `--reap <id>` 를 받으면 1초 뒤 시각과 id 를 첫 인자 파일에 적고 둘째 인자로 끝난다
# (둘째가 hang 이면 끝나지 않는다). 그 밖에는 passthrough 와 같다. 고정 인자로 받는 까닭 — 환경은 허용 목록이 거른다.
rec="$1"; how="$2"; shift 2
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  if [ "$1" = "--reap" ]; then
    [ "$how" = "hang" ] && exec sleep 30
    sleep 1
    echo "$(date +%s.%N) $2" >> "$rec"
    exit "$how"
  fi
  shift
done
[ $# -gt 0 ] || { echo "[launcher] no '--'" >&2; exit 125; }
shift
exec "$@"
