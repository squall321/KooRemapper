#!/usr/bin/env python3
# 절점을 옮기는 op 이 그 줄의 TC · RC 칸을 지키는지 — 공용 쓰기 길이 번호와 x · y · z 만 다시 써서 구속 칸이 사라졌다
"""옮긴 절점의 TC · RC 칸 (2026-11-07).

왜 이 시험이 있나.

  `ModelAssembler::writeOutput` 은 옮긴 절점 줄을 `formatNodeLine(id, x, y, z)` 로 **새로 썼다** — 번호와 좌표 셋뿐이라
  그 줄의 TC(병진 구속) · RC(회전 구속) 칸이 조용히 사라졌다. `update` · `applyfold` · 평행이동이 모두 이 길을 쓴다.
  덱은 돌지만 구속이 풀린다(실수가 있어도 아무 말이 없다). 이월 적용(`apply_carryover_plan`)을 짓다 C++ 조사에서 찾았다.

  고친 뒤 — 좌표를 새로 쓰고, 리더가 그 줄에서 읽어 둔 TC · RC 를 섹션 칸 폭으로 붙인다(둘 다 0 이면 붙이지 않는다).
  줄을 열 위치로 다시 자르지 않는다 — 번호를 10칸에 적은 표준 폭 덱(예제 replace_test)에서 z 의 끝을 TC 로 읽었다.
  안 옮긴 절점 줄은 예전처럼 바이트 그대로다.

usage: test_node_tail_kept.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []


def check(name, cond, detail=""):
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))


def node_line(nid, x, y, z, tail=""):
    return "%8d%16.9e%16.9e%16.9e%s" % (nid, x, y, z, tail)


# 단위 육면체 하나 — 절점 1 은 TC 7 · RC 7, 절점 2 는 TC 3 만, 절점 3 은 쉼표 줄(TC 1 · RC 2), 나머지는 구속 칸 없음
DECK = "\n".join([
    "*KEYWORD",
    "*NODE",
    node_line(1, 0.0, 0.0, 0.0, "       7       7"),
    node_line(2, 1.0, 0.0, 0.0, "       3"),
    "3,1.0,1.0,0.0,1,2",
    node_line(4, 0.0, 1.0, 0.0),
    node_line(5, 0.0, 0.0, 1.0),
    node_line(6, 1.0, 0.0, 1.0),
    node_line(7, 1.0, 1.0, 1.0),
    node_line(8, 0.0, 1.0, 1.0),
    "*ELEMENT_SOLID",
    "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d" % (1, 1, 1, 2, 3, 4, 5, 6, 7, 8),
    "*PART",
    "box",
    "%10d%10d%10d" % (1, 1, 1),
    "*SECTION_SOLID",
    "%10d%10d" % (1, 1),
    "*MAT_ELASTIC",
    "%10d%10.3e%10.3e%10.3e" % (1, 7.85e-9, 2.1e5, 0.3),
    "*END",
    "",
])

# 옮길 좌표 — 1 · 2 · 3 · 4 를 z 로 0.5 올린다(4 는 구속 칸이 없는 줄)
DYNAIN = "\n".join([
    "*KEYWORD",
    "*NODE",
    node_line(1, 0.0, 0.0, 0.5),
    node_line(2, 1.0, 0.0, 0.5),
    node_line(3, 1.0, 1.0, 0.5),
    node_line(4, 0.0, 1.0, 0.5),
    "*END",
    "",
])


def node_lines(path):
    out, kw = {}, None
    for ln in open(path, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if ln.startswith("*"):
            kw = ln.strip().upper()
            continue
        if kw == "*NODE" and ln.strip() and not ln.startswith("$"):
            nid = int(ln.split(",")[0]) if "," in ln else int(ln[:8])
            out[nid] = ln
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="node_tail_")
    try:
        open(os.path.join(d, "deck.k"), "w", newline="\n").write(DECK)
        open(os.path.join(d, "moved.dynain"), "w", newline="\n").write(DYNAIN)
        with open(os.path.join(d, "update.yaml"), "w", newline="\n") as f:
            f.write("model: deck.k\ndynain: moved.dynain\noutput: out.k\n")
        p = subprocess.run([binary, "update", "update.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
        check("update rc 0", p.returncode == 0, p.stdout + p.stderr)
        if p.returncode != 0:
            return 1
        got = node_lines(os.path.join(d, "out.k"))
        print("[update — 옮긴 절점의 구속 칸]")
        check("절점 1 — TC 7 · RC 7 이 남는다", got[1][56:].split() == ["7", "7"], repr(got.get(1)))
        check("절점 1 — z 가 0.5 로 옮겨졌다", abs(float(got[1][40:56]) - 0.5) < 1e-9, repr(got.get(1)))
        check("절점 2 — TC 3 이 남는다(RC 는 0 — 기본값과 같다)", got[2][56:].split() == ["3", "0"], repr(got.get(2)))
        check("절점 3(쉼표 줄) — TC 1 · RC 2 가 고정 칸으로 남는다", got[3][56:].split() == ["1", "2"], repr(got.get(3)))
        check("절점 4 — 구속 칸이 없던 줄에 칸을 지어 붙이지 않는다", got[4][56:].strip() == "", repr(got.get(4)))
        check("절점 5 — 안 옮긴 줄은 바이트 그대로", got[5] == node_line(5, 0.0, 0.0, 1.0), repr(got.get(5)))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("\n%s — 실패 %d" % ("PASS" if not FAILS else "FAIL", len(FAILS)))
    for f in FAILS:
        print("  - " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
