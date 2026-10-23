#!/bin/sh
# 시험용 실행기(환경 이름판) — 받은 환경의 **이름만** 첫 인자 파일에 적고 원래 명령이 된다(값은 적지 않는다)
out="$1"; shift
env | cut -d= -f1 | sort > "$out"
while [ $# -gt 0 ] && [ "$1" != "--" ]; do shift; done
shift
exec "$@"
