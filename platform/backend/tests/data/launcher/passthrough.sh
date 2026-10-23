#!/bin/sh
# 시험용 실행기 — 노드를 고르지 않고 이 자리에서 원래 명령이 된다.
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  [ "$1" = "--reap" ] && exit 0
  shift
done
[ $# -gt 0 ] || { echo "[launcher] no '--'" >&2; exit 125; }
shift
exec "$@"
