#!/usr/bin/env python3
# ale 사용자 재질 파일의 *EOS_…_TITLE 에서 새 EOSID 를 제목 줄이 아니라 Card 1 에 쓰는지 보는 회귀 시험
"""ale 사용자 재질의 `*EOS_…_TITLE` (2026-11-23 · 3차 7판 L-26 · 사용자 결정 「고친다」).

왜 이 시험이 있나.

  ale 는 사용자 재질 파일의 첫 `*EOS_` 블록을 싣고 첫 데이터 줄의 1 ~ 10 열에 새 EOSID 를 쓴다. `_TITLE` 꼴이면 첫 데이터 줄이 제목이라
  제목 줄에 EOSID 를 쓰고 진짜 EOSID 줄(Card 1)은 옛 번호 그대로 두었다(rc 0). PART 는 새 EOSID 를 가리키니 옛 번호와 다르면 없는 EOS 를
  가리킨다. 이제 제목 줄은 그대로 두고 Card 1 의 EOSID 칸을 바꾼다(재질 `_TITLE` 처리 — 3판 L-12 — 와 같다).

무엇을 보나.
  ★EOS 원래 번호 7 · 제목 「Water_eos」 — rc 0 · 산출 EOS 의 제목 줄이 그대로 · Card 1 의 EOSID 가 로그의 새 EOSID 와 같다 · 옛 7 은 없다
  ★제목 앞에 `$` 주석 줄 — 같다(주석은 건너 제목을 찾는다)
  대조 — `_TITLE` 아닌 EOS 는 첫 데이터 줄의 EOSID 를 바꾼다(그대로)

usage: test_ale_eos_title.py <KooRemapper 바이너리>
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
CARD1 = "         7       0.0       0.0       0.0       0.0       0.4       0.4       0.0\n$       E0        V0\n    2.5E-4       1.0\n"


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="aleeos_")
    try:
        model = open(os.path.join(REPO, "examples", "ale", "explicit.k"), encoding="utf-8").read()
        for tag, eos in (("title", "*EOS_LINEAR_POLYNOMIAL_TITLE\nWater_eos\n" + CARD1),
                         ("title_comment", "*EOS_LINEAR_POLYNOMIAL_TITLE\n$ title comes next\nWater_eos\n$    EOSID        C0\n" + CARD1),
                         ("plain", "*EOS_LINEAR_POLYNOMIAL\n" + CARD1)):
            d = os.path.join(root, tag)
            os.makedirs(d)
            open(os.path.join(d, "explicit.k"), "w", encoding="utf-8").write(model)
            open(os.path.join(d, "mymat.k"), "w", encoding="utf-8").write(
                "*KEYWORD\n*MAT_NULL\n$      MID        RO\n         1  1.000E-9\n" + eos + "*END\n")
            open(os.path.join(d, "a.yaml"), "w", encoding="utf-8").write(
                "model: explicit.k\noutput: a.k\nale_parts:\n  - pid: 3\n    material: mymat.k\n")
            p = subprocess.run([binary, "ale", "a.yaml"], cwd=d, capture_output=True, text=True, timeout=900,
                               encoding="utf-8", errors="replace")
            out = open(os.path.join(d, "a.k"), encoding="utf-8").read() if os.path.exists(os.path.join(d, "a.k")) else ""
            new = re.search(r"EOSID=(\d+)", p.stdout + p.stderr)
            m = re.search(r"^\*EOS_LINEAR_POLYNOMIAL[^\n]*\n((?:[^*][^\n]*\n)*)", out, re.M)
            data = [l for l in (m.group(1).splitlines() if m else []) if not l.startswith("$")]
            title_ok = tag == "plain" or (bool(data) and data[0] == "Water_eos")
            card1 = data[1] if tag != "plain" and len(data) > 1 else (data[0] if data else "")
            check("%s%s — rc 0 · 제목 줄 그대로 · Card 1 EOSID = 새 번호 %s · 옛 7 없음" % ("★" if tag != "plain" else "", tag,
                                                                                    new.group(1) if new else "?"),
                  p.returncode == 0 and bool(new) and title_ok and card1[0:10].strip() == new.group(1) and new.group(1) != "7",
                  (p.returncode, data[:3], (p.stdout + p.stderr)[-200:]))
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
