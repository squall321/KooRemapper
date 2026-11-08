#!/usr/bin/env python3
# 주 덱 폴더 기준 상대 경로 셈이 util/RelPath 한 곳에만 있는지(이월 적용 · assemble battery 가 그것을 부르는지) 보는 소스 회귀 시험
"""상대 경로 셈 한 곳 (2026-11-08).

왜 이 시험이 있나.

  이월 적용(CarryoverApply.cpp 의 `relpathOf` — 판 2 `deck.includes` 의 relpath)과 assemble 의 battery `*INCLUDE` 이름
  (ModelAssembler.cpp 의 `ma_includeName`)이 같은 셈(`fs::absolute` → `lexically_normal` → `lexically_relative`)을 따로 두었다.
  하나를 고치면 다른 하나가 남아 같은 파일이 두 이름으로 적힌다. 셈을 `util::relpathOf`(include/util/RelPath.h ·
  src/util/RelPath.cpp)로 모았으니, `lexically_relative` 를 부르는 자리가 그 파일 하나뿐인지 · 두 소비자가 그것을 부르는지 본다.

  동작은 같다 — 이월 적용의 회귀(test_apply_carryover_plan*.py)와 battery 의 *INCLUDE 회귀(test_yaml_dir_paths.py A 칸)가
  그대로 지난다. 셈 자체는 단위 시험(tests/test_RelPath.cpp)이 본다.

usage: test_relpath_single.py [<KooRemapper 바이너리, 무시>]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, detail))
    print("  %-90s %s" % (name, "OK" if cond else "FAIL"))


def code_of(path):
    """주석을 뗀 소스(// 줄 끝 · /* */) — 주석 속 낱말을 세지 않는다."""
    s = open(path, encoding="utf-8", errors="replace").read()
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"//[^\n]*", "", s)


def main():
    sites = []
    for top in ("src", "include"):
        for r, _, fs in os.walk(os.path.join(REPO, top)):
            for f in fs:
                if f.endswith((".cpp", ".h", ".hpp")):
                    p = os.path.join(r, f)
                    if "lexically_relative" in code_of(p):
                        sites.append(os.path.relpath(p, REPO))
    check("★lexically_relative 를 부르는 자리는 src/util/RelPath.cpp 하나(예전엔 CarryoverApply · ModelAssembler 둘)",
          sites == ["src/util/RelPath.cpp"], sites)
    for rel in ("src/assembly/CarryoverApply.cpp", "src/assembly/ModelAssembler.cpp"):
        check("%s 가 util::relpathOf 를 부른다" % rel, "util::relpathOf(" in code_of(os.path.join(REPO, rel)))
    print()
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
