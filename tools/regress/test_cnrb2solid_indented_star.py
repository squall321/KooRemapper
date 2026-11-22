#!/usr/bin/env python3
# cnrb2solid 가 들여 쓴 `*` 줄(제목 등)을 키워드로 읽지 않는지 — 리더의 1열 규칙과 같은지 보는 회귀 시험
"""cnrb2solid 의 1열 규칙 (2026-11-22 · 3차 5판 L-14).

왜 이 시험이 있나.

  cnrb2solid 의 덱 훑기는 앞 공백을 지운 줄이 `*` 로 시작하면 키워드로 보았다. 리더(LS-DYNA 도)는 1열의 `*` 만 키워드로 읽어 들여 쓴
  `*` 줄은 앞 블록의 데이터다. 세트 제목이 `  *Bolt_NodeSet` 이면 cnrb2solid 는 거기서 세트 블록을 닫아 멤버를 못 읽고
  「NSID=1 not found or empty」 로 CNRB 를 건너뛴 채 rc 0 이었다(바꾼 것 0). 이제 아홉 자리 모두 공용 1열 규칙을 쓴다.

무엇을 보나.
  ★예제 bolt_simple.k 의 세트 제목 · CNRB 제목을 들여 쓴 `*` 로 — rc 0 · CNRB 1 개를 바꾼다 · 건너뛴다는 경고 없음
  대조 — 예제 그대로 rc 0 · 1 개

usage: test_cnrb2solid_indented_star.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples", "cnrb2solid")
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="cnstar_")
    try:
        src = open(os.path.join(EX, "bolt_simple.k"), encoding="utf-8").read()
        assert "\nBolt_NodeSet\n" in src and "Bolt_M6\n" in src
        cases = (("plain", src, "대조 — 예제 그대로 → rc 0 · CNRB 1 개를 바꾼다"),
                 ("star", src.replace("\nBolt_NodeSet\n", "\n  *Bolt_NodeSet\n")
                             .replace(" " * 69 + "Bolt_M6\n", " " * 67 + "*Bolt_M6\n"),
                  "★세트 · CNRB 제목이 들여 쓴 `*` → rc 0 · CNRB 1 개를 바꾼다(예전엔 세트를 못 읽어 0 개 · rc 0)"))
        for tag, text, name in cases:
            d = os.path.join(root, tag)
            os.makedirs(d)
            with open(os.path.join(d, "bolt_simple.k"), "w", encoding="utf-8") as f:
                f.write(text)
            shutil.copy2(os.path.join(EX, "basic.yaml"), d)
            p = subprocess.run([binary, "cnrb2solid", "basic.yaml"], cwd=d, capture_output=True, text=True, timeout=900,
                               encoding="utf-8", errors="replace")
            out = p.stdout + p.stderr
            check(name, p.returncode == 0 and "Converted 1 CNRB(s)" in out and "not found or empty" not in out,
                  (p.returncode, out[-400:]))
    finally:
        shutil.rmtree(root, ignore_errors=True)
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
