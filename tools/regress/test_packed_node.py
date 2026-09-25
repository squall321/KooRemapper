#!/usr/bin/env python3
"""칸이 꽉 찬 `*NODE` 카드를 자유형식으로 오독해 **좌표를 조용히 잃던 것**.

왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P1-2):

  `*NODE` 는 자유형식(공백 분해)이 **먼저**고 고정폭이 폴백이다(`KFileReader.cpp:401`).
  `*ELEMENT_SOLID` 와 순서가 정반대인데, 그 순서 자체는 리포의 자체 산출 덱들이 기대고 있어
  바꾸면 안 된다.

  문제는 판정이다. 표준 Vol_I 서식 `(I8, 3E16.0, 2I8)` 로 쓴 카드에서 좌표가 **부호로 붙으면**
  한 토큰이 숫자 세 개를 품는다. 그런데 TC/RC 칸의 `0` 두 개가 토큰 수를 4로 만들어
  자유형식 가지가 이겼다 — 실측이다.

      `       2 1.234567890E+01-2.345678900E+01-3.456789000E+01       0       0`
      토큰 ['2', '1.23…E+01-2.34…E+01-3.45…E+01', '0', '0']
      → x=12.345679 · y=0 · z=0      (참값 y=-23.456789 · z=-34.567890)

  **rc=0 이고 아무 말도 안 했다.** 잘못 만든 덱이 아니라 매뉴얼대로 쓴 덱인데 기하가 뭉개진다.
  TC/RC 는 구속 조건이라 실사용 덱에 흔하다.

  ⚠ 알려진 한계(고치지 않았다) — **가운데 좌표 칸이 빈** 고정형식 카드는 여전히 오독된다.
      `       1             1.0                             3.0       0       0`
      토큰 ['1','1.0','3.0','0','0'] — 붙은 숫자가 없어 이 가드가 못 잡는다.
      → (1, 3.0, 0)  (참값 (1, 0, 3))
    자유형식 덱과 구분할 신뢰할 만한 판별식을 못 찾았다. 지어내지 않고 여기 적어 둔다.

usage: test_packed_node.py <KooRemapper 바이너리>
"""
import os
import re
import subprocess
import sys
import tempfile

FAILS = []


def check(name, cond, detail=""):
    print("  %-62s %s" % (name[:62], "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:250]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def bounds(binary, cwd, deck):
    rc, out = run(binary, cwd, "info", deck)
    m = re.search(r"^Min bound:\s*\(([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\)", out, re.M)
    return (rc, tuple(round(float(m.group(i)), 5) for i in (1, 2, 3)) if m else None, out)


def write(path, lines):
    open(path, "w").write("\n".join(["*KEYWORD", "*NODE"] + lines + ["*END"]) + "\n")


def main():
    if len(sys.argv) < 2:
        print("usage: test_packed_node.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    d = tempfile.mkdtemp(prefix="pnode_")
    X, Y, Z = 12.3456789, -23.456789, -34.56789
    want = (0.0, round(Y, 5), round(Z, 5))

    print("[표준 고정형식 — 좌표가 부호로 붙는다]")
    # TC/RC 가 있으면 토큰이 4개가 되어 예전에는 자유형식이 이겼다 — 그것이 결함이었다.
    write(os.path.join(d, "tcrc.k"),
          ["%8d%16.9E%16.9E%16.9E%8d%8d" % (1, 0, 0, 0, 0, 0),
           "%8d%16.9E%16.9E%16.9E%8d%8d" % (2, X, Y, Z, 0, 0)])
    write(os.path.join(d, "notcrc.k"),
          ["%8d%16.9E%16.9E%16.9E" % (1, 0, 0, 0),
           "%8d%16.9E%16.9E%16.9E" % (2, X, Y, Z)])
    for name in ("tcrc", "notcrc"):
        rc, got, out = bounds(binary, d, name + ".k")
        check("%s: 좌표를 잃지 않는다" % name, got == want, "got=%s want=%s" % (got, want))
        check("%s: rc=0" % name, rc == 0, out[-150:])

    print("[자유형식 덱은 그대로 읽힌다 — 이 가드가 길을 막으면 안 된다]")
    write(os.path.join(d, "free.k"),
          ["1 0.0 0.0 0.0", "2 %.7f %.7f %.7f" % (X, Y, Z)])
    rc, got, out = bounds(binary, d, "free.k")
    check("자유형식(공백 분해)이 그대로 읽힌다", got == want, "got=%s" % (got,))

    print("[지수 표기의 부호를 '붙은 숫자' 로 오인하지 않는다]")
    # `1.0E-03` 의 `-` 는 지수 부호다. 이것을 붙은 숫자로 보면 자유형식 덱이 통째로 막힌다.
    write(os.path.join(d, "expo.k"),
          ["1 0.0 0.0 0.0", "2 1.23456789E+01 -2.3456789E+01 -3.456789E+01"])
    rc, got, out = bounds(binary, d, "expo.k")
    check("지수 부호가 있는 자유형식이 읽힌다", got == want, "got=%s" % (got,))
    write(os.path.join(d, "expo2.k"),
          ["1 0.0 0.0 0.0", "2 1.0E-03 2.0E-03 3.0E-03"])
    rc, got, out = bounds(binary, d, "expo2.k")
    check("작은 지수(1.0E-03)도 읽힌다", got == (0.0, 0.0, 0.0) and rc == 0, "got=%s" % (got,))

    print("[i10 덱의 꽉 찬 카드도 제 폭으로 읽힌다]")
    open(os.path.join(d, "i10.k"), "w").write(
        "*KEYWORD I10=Y\n*NODE\n"
        + "%10d%16.9E%16.9E%16.9E%10d%10d\n" % (1, 0, 0, 0, 0, 0)
        + "%10d%16.9E%16.9E%16.9E%10d%10d\n" % (22, X, Y, Z, 0, 0)
        + "*END\n")
    rc, got, out = bounds(binary, d, "i10.k")
    check("i10 꽉 찬 카드의 좌표가 맞다", got == want, "got=%s" % (got,))

    print("")
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
