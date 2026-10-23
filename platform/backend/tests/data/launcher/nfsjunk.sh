#!/bin/sh
# 시험용 실행기 — NFS 가 열린 채 지운 파일에 붙이는 `.nfs<16진수>` 찌꺼기를 cwd 에 남기고 원래 명령이 된다.
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  [ "$1" = "--reap" ] && exit 0
  shift
done
[ $# -gt 0 ] || { echo "[launcher] no '--'" >&2; exit 125; }
shift
printf 'x' > .nfs000000000badc0de00000001
exec "$@"
