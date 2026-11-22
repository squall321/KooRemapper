#!/usr/bin/env python3
# info --strict 의 SECID · MID · SID 겹침과 섹션 번호 훑기가 쌓인 묶음 · 빈 제목 줄 · 들여 쓴 제목을 바로 읽는지 보는 회귀 시험(3차 3판 L-09)
"""쌓인 묶음 · 빈 `_TITLE` 줄 · 들여 쓴 `*` 제목 (2026-11-22 · 미룬 결함 3차 3판 L-09).

왜 이 시험이 있나.

  `info --strict` 의 SECID · MID 겹침 검사는 블록마다 **첫 정의만** 보아 한 키워드 아래 쌓인 묶음(매뉴얼 Card Sets)의 겹침을 놓쳤고,
  `_TITLE` 의 빈 제목 줄을 건너뛰어 Card 1 을 제목으로 · 둘째 카드를 번호로 읽었다(`*MAT_RIGID_TITLE` 의 CMO `1` 을 MID 1 겹침으로).
  `*SET_*_TITLE` 도 같아 첫 멤버를 SID 로 읽었다(없는 SID 겹침 · 진짜 SID 를 가리키는 참조를 미정의로).
  섹션 번호 훑기(카드 묶음 셈 · 옛 첫 카드 셈)는 들여 쓴 `*` 줄(제목 「  *front」)에서 블록을 끊어 그 SECID 를 못 보았다 — 새 섹션이
  그 번호를 다시 냈다. LS-DYNA · 리더는 1열의 `*` 만 키워드다(Vol_I 17940).

무엇을 보나(상자 덱 — PID 1 · SECID 1 · MID 1 — 에 카드를 덧붙인다).
  S 들여 쓴 제목 — offset 의 새 SECID 가 제목 「  *front」 · 「  $5 tube」 인 섹션 2 위로 간다 · 그 섹션이 SECID 1 이면 겹침
  T 빈 제목 — `*SET_NODE_LIST_TITLE` 의 빈 제목 · `*MAT_RIGID_TITLE` 의 빈 제목이 거짓 겹침 · 거짓 미정의를 내지 않는다
  U 쌓인 묶음 — 블록을 건넌 · 한 블록 안의 SECID · MID 겹침을 잡는다 · 열 재질 · 덧붙임 · `*MAT_NONLOCAL` 은 겹침이 아니다

usage: test_strict_stacked_duplicates.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []

BOX = """output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 4
ny: 2
nz: 1
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
"""
OFFSET = """base_model: box.k
output: out
operations:
  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: 1
    offset_direction: +z
    connection_mode: tied
    new_pid: 10
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
           @MID@  7.85E-09  2.10E+05       0.3
"""
SHELL2 = "         2         2\n       1.0       1.0       1.0       1.0\n"


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:500]))
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def box(binary, tmp, name, before_end):
    d = os.path.join(tmp, name)
    os.makedirs(d)
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    assert rc == 0, out[-400:]
    p = os.path.join(d, "box.k")
    body = open(p, encoding="utf-8").read()
    open(p, "w", encoding="utf-8").write(body.replace("*END", before_end + "*END"))
    return d


def new_secid(binary, d):
    open(os.path.join(d, "off.yaml"), "w").write(OFFSET)
    rc, out = run(binary, d, "assemble", "off.yaml")
    m = re.search(r"New IDs: PID=\d+, SECID=(\d+)", out)
    return rc, (int(m.group(1)) if m else None), out


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="strict_stacked_")
    try:
        print("[S 들여 쓴 제목 — 1열의 `*` · `$` 만 키워드 · 주석]")
        d = box(binary, tmp, "s1", "*SECTION_SHELL_TITLE\n  *front panel\n" + SHELL2)
        rc, sec, out = new_secid(binary, d)
        check("S-1 제목 「  *front panel」 섹션 2 — offset 의 새 SECID 는 3", rc == 0 and sec == 3, (rc, sec, out[-300:]))
        d = box(binary, tmp, "s2", "*SECTION_SHELL_TITLE\n  $5 tube\n" + SHELL2)
        rc, sec, out = new_secid(binary, d)
        check("S-2 제목 「  $5 tube」 섹션 2 — offset 의 새 SECID 는 3", rc == 0 and sec == 3, (rc, sec, out[-300:]))
        d = box(binary, tmp, "s3", "*SECTION_SHELL_TITLE\n  *front panel\n         1         2\n       1.0       1.0       1.0       1.0\n")
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("S-3 제목 「  *front panel」 섹션 1 — 상자의 섹션 1 과 겹침(--strict rc 1)", rc == 1 and "ID 1 가 line" in out, out[-300:])

        print("[T 빈 `_TITLE` 줄은 제목이다]")
        d = box(binary, tmp, "t1", "*SET_NODE_LIST_TITLE\n\n         5\n         1         2         3         4\n"
                                   "*SET_NODE_LIST\n         1\n         5         6\n*BOUNDARY_SPC_SET\n         5         0         1         1         1\n")
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("T-1 빈 제목 세트 5 · 세트 1 — 거짓 SID 겹침 없음 · 세트 5 참조는 정의됨(--strict rc 0)",
              rc == 0 and "SID 1 가" not in out and "세트 5" not in out, out[-400:])
        d = box(binary, tmp, "t2", "*MAT_RIGID_TITLE\n\n         5   7.85E-9    210000       0.3\n         1         0         0\n"
                                   "       0.0       0.0       0.0       0.0       0.0       0.0\n")
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("T-2 빈 제목 *MAT_RIGID_TITLE 5(Card 2 CMO 1) — MID 1 겹침이 아니다(--strict rc 0)", rc == 0 and "ID 1 가" not in out, out[-300:])
        d = box(binary, tmp, "t3", "*SECTION_SHELL_TITLE\n\n" + SHELL2)
        rc, sec, out = new_secid(binary, d)
        check("T-3 빈 제목 섹션 2 — offset 의 새 SECID 는 3", rc == 0 and sec == 3, (rc, sec, out[-300:]))

        print("[U 쌓인 묶음의 겹침]")
        d = box(binary, tmp, "u1", "*SECTION_SOLID\n         2         1\n         3         1\n*SECTION_SOLID\n         3         2\n")
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("U-1 쌓인 둘째 묶음 SECID 3 · 다른 블록 SECID 3 — 겹침(--strict rc 1)", rc == 1 and "ID 3 가 line" in out, out[-300:])
        d = box(binary, tmp, "u2", "*SECTION_SOLID\n         4         1\n         4         2\n")
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("U-2 한 블록 안의 SECID 4 둘 — 겹침(--strict rc 1)", rc == 1 and "ID 4 가 line" in out, out[-300:])
        d = box(binary, tmp, "u3", "*MAT_ELASTIC\n         2   7.85E-9    210000       0.3\n         3   7.85E-9    210000       0.3\n"
                                   "*MAT_ELASTIC\n         3   2.70E-9     70000      0.33\n")
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("U-3 쌓인 둘째 재질 MID 3 · 다른 블록 MID 3 — 겹침(--strict rc 1)", rc == 1 and "ID 3 가 line" in out, out[-300:])
        d = box(binary, tmp, "u4", "*MAT_THERMAL_ISOTROPIC\n         1       0.0       0.0       0.0\n       1.0       1.0\n"
                                   "*MAT_ADD_EROSION\n         1         0       0.0       0.0       0.0       0.0       0.0       0.0\n"
                                   "       0.0       0.0       0.0       0.0       0.0       0.0       0.0       0.0\n"
                                   "*MAT_NONLOCAL\n         1         1         0       0.0       0.0\n")
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("U-4 열 재질 1 · *MAT_ADD_EROSION 1 · *MAT_NONLOCAL 1 — MID 1 겹침이 아니다", "ID 1 가 line" not in out, out[-300:])
        d = box(binary, tmp, "u5", "")
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("U-5 대조 — 상자만 rc 0", rc == 0 and "겹칩니다" not in out, out[-300:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("결과: %d 통과 · %d 실패" % (len(OKS), len(FAILS)))
    for f in FAILS:
        print("  FAIL " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
