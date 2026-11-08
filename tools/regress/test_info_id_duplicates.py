#!/usr/bin/env python3
# info 가 절점 · 요소 번호를 주 덱과 인클루드에서 두 번 정의한 것을 같은 종류끼리 망가진 카드로 짚는지(--strict rc 1) 보는 회귀 시험
"""info 의 절점 · 요소 번호 겹침 (2026-11-08 · 사용자 결정 「고친다」).

왜 이 시험이 있나.

  리더(KFileReader → Mesh::addNode · addElement 의 map[id] =)는 같은 번호를 뒤 정의로 덮어 앞 정의를 **말없이** 잃는다. 그래서
  상자(절점 1~198 · 솔리드 1~100) 위에 번호를 옮기지 않은 battery 덱을 끌어온 덱을 info 가 「Nodes 27558」로 세고 SECID · MID 겹침만
  짚었다(절점 198 · 요소 100 이 사라진 줄 몰랐다). 이제 같은 종류(절점 · 솔리드 · 셸 · 티쉘 · 보 족) 안의 겹침은 SECID · MID 처럼
  망가진 카드(--strict rc 1)이고 블록 짝마다 개수 · 범위를 적는다. 족을 건넌 겹침(셸 1 · 솔리드 1)은 LS-DYNA 가 받으므로 단정하지
  않는 알림이다. 리더가 덮은 수도 적는다(위 Nodes · Elements 는 그것을 뺀 수다).

무엇을 보나(상자 덱 + 인클루드 하나).
  D-1 인클루드가 상자 절점 1~5 를 다시 정의 → 망가진 카드(절점 · 5개 · 인클루드 · 주 덱 줄) · 덮은 수 · --strict rc 1
  D-2 인클루드가 솔리드 1~3 을 다시 정의 → 망가진 카드(솔리드 요소 · 3개) · --strict rc 1
  D-3 주 덱 안에서 절점 7 을 두 번 → 망가진 카드
  D-4 보 1 과 이산 1(보 족 — null beam 때문에 서로 달라야 한다) → 망가진 카드
  D-5 인클루드의 셸 1~2 가 상자 솔리드 1~2 와 번호만 같다 → 망가진 카드 아님 · 족을 건넌 알림 · --strict rc 0
  대조 C-1 상자만 · C-2 새 assemble battery(번호를 옮긴 덱) — 절점 · 요소 겹침 없음 · --strict rc 0

usage: test_info_id_duplicates.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
from ops_help import OPS  # noqa: E402

FAILS, OKS = [], []
BOX = {o["name"]: o for o in OPS}["warpage"]["files"]["box.yaml"]


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-500:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def node(nid, x, y, z):
    return "%8d%16.6f%16.6f%16.6f\n" % (nid, x, y, z)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="idup_")
    try:
        def deck(name, include=None, main_extra=""):
            d = os.path.join(root, name)
            os.makedirs(d)
            with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
                f.write(BOX)
            run(binary, d, "generate", "box", "box.yaml")
            p = os.path.join(d, "box.k")
            s = open(p, encoding="utf-8").read()
            tail = main_extra + ("*INCLUDE\ninc.k\n" if include is not None else "") + "*END"
            with open(p, "w", encoding="utf-8") as f:
                f.write(s.replace("*END", tail))
            if include is not None:
                with open(os.path.join(d, "inc.k"), "w", encoding="utf-8") as f:
                    f.write("*KEYWORD\n" + include + "*END\n")
            rc, out = run(binary, d, "info", "box.k")
            rcs, _ = run(binary, d, "info", "box.k", "--strict")
            return rc, rcs, out

        def damaged(out):
            m = re.search(r"망가진 카드 (\d+)건", out)
            return int(m.group(1)) if m else 0

        rc, rcs, out = deck("d1", "*NODE\n" + "".join(node(i, 100.0 + i, 0, 0) for i in range(1, 6)))
        check("★D-1 인클루드가 절점 1~5 를 다시 정의 → 망가진 카드(절점 5개 · 인클루드 · 주 덱 줄) · --strict rc 1(예전엔 말없이 덮었다)",
              rc == 0 and rcs == 1 and re.search(r"line \d+ \*NODE: 절점 ID 1 가 line \d+\(주 덱\) 과 겹칩니다 — 이 블록에서 겹친 "
                                                   r"절점 5개\(1~5\).* — 인클루드 inc\.k", out) is not None,
              (rc, rcs, out[-600:]))
        check("D-1   └ 리더가 덮은 수를 적는다(위 Nodes 는 그것을 뺀 수)", "덮인 절점 5개" in out, out[-400:])
        rc, rcs, out = deck("d2", "*NODE\n" + "".join(node(900 + i, 0, 0, 50.0 + i) for i in range(1, 9)) +
                            "*ELEMENT_SOLID\n" + "".join("%8d%8d" % (e, 1) + "".join("%8d" % (900 + k) for k in range(1, 9)) + "\n"
                                                         for e in range(1, 4)))
        check("★D-2 인클루드가 솔리드 1~3 을 다시 정의 → 망가진 카드(솔리드 요소 3개) · --strict rc 1",
              rcs == 1 and re.search(r"\*ELEMENT_SOLID: 솔리드 요소 ID 1 가 line \d+\(주 덱\) 과 겹칩니다 — 이 블록에서 겹친 솔리드 요소 "
                                     r"3개\(1~3\)", out) is not None, (rcs, out[-600:]))
        rc, rcs, out = deck("d3", main_extra="*NODE\n" + node(7, 5.0, 5.0, 5.0))
        check("★D-3 주 덱 안에서 절점 7 을 두 번 → 망가진 카드(인클루드 없이도)",
              rcs == 1 and re.search(r"\*NODE: 절점 ID 7 가 line \d+ 과 겹칩니다", out) is not None, (rcs, out[-500:]))
        rc, rcs, out = deck("d4", "*SECTION_BEAM\n       201         1\n*PART\nB\n       201       201         1\n"
                                  "*ELEMENT_BEAM\n       1     201       1       2\n"
                                  "*ELEMENT_DISCRETE\n       1     201       3       4\n")
        check("★D-4 보 1 과 이산 1(보 족) → 망가진 카드 · 상자 솔리드 1 과는 알림 없음(리더가 보를 담지 않는다)",
              rcs == 1 and re.search(r"\*ELEMENT_DISCRETE: 보 족 요소 ID 1 가 line \d+(\([^)]*\))? 과 겹칩니다", out) is not None
              and "족을 건너" not in out,   # 보 족은 리더가 담지 않아 솔리드 1 과 합치지 않는다 — 족을 건넌 알림이 없다
              (rcs, out[-500:]))
        rc, rcs, out = deck("d5", "*SECTION_SHELL\n       301         2\n       1.0       1.0       1.0       1.0\n"
                                  "*PART\nS\n       301       301         1\n"
                                  "*ELEMENT_SHELL\n       1     301       1       2      13      12\n"
                                  "       2     301       2       3      14      13\n")
        check("★D-5 셸 1~2 가 상자 솔리드 1~2 와 번호만 같다 → 망가진 카드 아님 · 족을 건넌 알림 · --strict rc 0",
              rcs == 0 and damaged(out) == 0 and re.search(r"알림 line \d+ \*ELEMENT_SHELL: 셸 요소 ID 1 이 솔리드 요소에도 있습니다 — "
                                                           r"족을 건너 겹친 번호 2개\(1~2\)", out) is not None,
              (rcs, damaged(out), out[-500:]))
        rc, rcs, out = deck("c1")
        check("C-1 대조 — 상자만: 망가진 카드 없음 · 알림 없음 · --strict rc 0",
              rc == 0 and rcs == 0 and damaged(out) == 0 and "족을 건너" not in out, (rc, rcs, out[-300:]))
        d = os.path.join(root, "c2")
        os.makedirs(d)
        with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
            f.write(BOX)
        run(binary, d, "generate", "box", "box.yaml")
        bat = open(os.path.join(REPO, "examples", "battery", "swell", "stacked", "stacked_swell.yaml"), encoding="utf-8").read()
        with open(os.path.join(d, "bat.yaml"), "w", encoding="utf-8") as f:
            f.write(re.sub(r"^output:.*$", "output: bt", bat, count=1, flags=re.M))
        with open(os.path.join(d, "a.yaml"), "w", encoding="utf-8") as f:
            f.write("base_model: box.k\noutput: ba\noperations:\n  - type: battery\n    config: bat.yaml\n")
        rca, _ = run(binary, d, "assemble", "a.yaml")
        rc, out = run(binary, d, "info", "ba.k")
        check("C-2 대조 — 새 assemble battery(번호를 옮긴 덱): 절점 · 요소 겹침 · 족을 건넌 알림 없음",
              rca == 0 and rc == 0 and "절점 ID" not in out and "요소 ID" not in out and "족을 건너" not in out, (rca, rc, out[-400:]))
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
