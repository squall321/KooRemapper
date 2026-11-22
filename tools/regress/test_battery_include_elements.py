#!/usr/bin/env python3
# 요소가 인클루드에만 있는 주 덱에 assemble battery 를 얹으면 battery 요소 번호가 인클루드의 요소 번호를 피하는지 보는 회귀 시험(3차 4판 L-18)
"""인클루드에만 있는 요소와 battery 번호 (2026-11-22 · 미룬 결함 3차 4판 L-18 — 요소 카드 걸음).

왜 이 시험이 있나.

  assemble 의 리더는 주 덱만 읽는다 — 요소가 인클루드 파일에만 있으면 battery 가 피할 「이미 쓰는 요소 번호」 는 덱 줄을 훑는 걸음
  (`batteryTakenSpans` 의 요소 번호 모으기)만 안다. 그 걸음을 색인 없이 다시 지었으므로(L-18) 이 꼴을 지킨다 — 빠지면 battery 요소가
  1 부터 나가 인클루드의 요소 1 과 겹친다(LS-DYNA 는 같은 족의 같은 번호에서 멈춘다).

무엇을 보나 — 주 덱(절점 · 파트 · 섹션 · 재질 · `*INCLUDE elems.k`) + elems.k(솔리드 1) + 적층 battery.
  rc 0 · 「요소 +1」 로 옮겼다 · 산출(주 덱 + 인클루드 + battery 덱)의 info --strict 에 겹침이 없다

usage: test_battery_include_elements.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-80s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run(["prlimit", "--as=8589934592", binary, *args], cwd=d, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="kr_bat_incl_")
    try:
        t = open(os.path.join(REPO, "examples", "battery", "swell", "stacked", "stacked_swell.yaml"), encoding="utf-8").read()
        open(os.path.join(d, "bat.yaml"), "w").write(re.sub(r"^output:.*$", "output: bt", t, count=1, flags=re.M))
        L = ["*KEYWORD", "*NODE"] + ["%8d%16.4f%16.4f%16.4f" % (i + 1, i % 2, (i // 2) % 2, i // 4) for i in range(8)]
        L += ["*PART", "p", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*MAT_ELASTIC", "         1   7.85E-9    210000       0.3", "*INCLUDE", "elems.k", "*END"]
        open(os.path.join(d, "box.k"), "w").write("\n".join(L) + "\n")
        open(os.path.join(d, "elems.k"), "w").write("*KEYWORD\n*ELEMENT_SOLID\n%8d%8d\n%s\n*END\n" % (1, 1, "".join("%8d" % n for n in range(1, 9))))
        open(os.path.join(d, "a.yaml"), "w").write("base_model: box.k\noutput: ba\noperations:\n  - type: battery\n    config: bat.yaml\n")
        rc, out = run(binary, d, "assemble", "a.yaml")
        check("assemble battery — rc 0 · 요소 번호를 옮겼다(요소 +1)", rc == 0 and re.search(r"요소 \+1\b", out), out[-300:])
        rc, out = run(binary, d, "info", "--strict", "ba.k")
        check("산출(주 덱 + 인클루드 + battery 덱) — info --strict rc 0 · 요소 번호 겹침 없음", rc == 0 and "겹" not in out, out[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL — %d 항 실패 / %d" % (len(FAILS), len(FAILS) + len(OKS)))
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
