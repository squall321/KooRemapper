#!/bin/sh
# 시험용 실행기 — 첫 인자를 노드 이름으로 `.job_<id>.node` 에 적고 이 자리에서 원래 명령이 된다(HWAX 답신 ③ 안 A).
node="$1"; shift
id=""
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  [ "$1" = "--reap" ] && exit 0
  [ "$1" = "--job-id" ] && id="$2"
  shift
done
[ $# -gt 0 ] || { echo "[launcher] no '--'" >&2; exit 125; }
shift
printf '%s\n' "$node" > ".job_${id}.node"
exec "$@"
