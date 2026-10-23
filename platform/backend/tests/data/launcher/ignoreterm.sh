#!/bin/sh
# 시험용 실행기(TERM 무시판) — SIGTERM 을 무시한 채 원래 명령이 된다. 무시는 exec 너머로 이어진다(SIGKILL 이 와야 끝난다)
trap '' TERM
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  [ "$1" = "--reap" ] && exit 0
  shift
done
[ $# -gt 0 ] || { echo "[launcher] no '--'" >&2; exit 125; }
shift
exec "$@"
