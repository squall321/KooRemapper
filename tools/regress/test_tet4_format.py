# TET4 출력 연결 순서(LS-DYNA N1 N2 N3 N4 N4 N4 N4 N4)와 자기 출력 재읽기 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_tet4_format.py <KooRemapper 바이너리>

배경
  - 뷰어 표시 문제로 TET4 를 n1 n2 n3 n3 n4 n4 n4 n4 로 쓰게 바뀌었다(f201b1a). LS-DYNA Vol I *ELEMENT_SOLID 는
    사면체를 N1, N2, N3, N4, N4, N4, N4, N4 로 규정하고 어기면 negative volume 으로 종료한다고 적는다.
  - KooRemapper KFileReader 도 n5=n6=n7=n8=n4 일 때만 TET4 로 읽어, 자기 출력을 다시 넣으면
    'TET10: no TET4 elements found' 로 사면체를 못 찾았다(elform 하향 → 상향 연쇄 실패).
"""
import os
import re
import subprocess
import sys
import tempfile

FAILS = []

# 면 하나를 공유하는 TET4 두 개 (examples/elform 의 입력과 같은 형상)
TET_MODEL = """*KEYWORD
*NODE
       1       0.000000       0.000000       0.000000
       2       1.000000       0.000000       0.000000
       3       0.500000       1.000000       0.000000
       4       0.500000       0.500000       1.000000
       5       0.500000       0.500000      -1.000000
*ELEMENT_SOLID
       1       1       1       2       3       4       4       4       4       4
       2       1       1       3       2       5       5       5       5       5
*PART
TET4 part
         1         1         1
*SECTION_SOLID
         1        13
*MAT_ELASTIC
         1  7.85E-09    210000       0.3
*END
"""


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def solid_rows(path):
    rows, inel = [], False
    for s in open(path, errors="replace"):
        if s.startswith("*"):
            inel = s.strip().upper() == "*ELEMENT_SOLID"
            continue
        if inel and not s.startswith("$"):
            rows.append(s.split())
    return rows


def assemble(binary, d, name, base, target):
    open(os.path.join(d, f"{name}.yaml"), "w").write(
        f"base_model: {base}\noutput: {name}\noperations:\n  - type: elform\n    target_elform: {target}\n")
    return run(binary, d, "assemble", f"{name}.yaml")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="tet4fmt_")
    open(os.path.join(d, "tet4.k"), "w").write(TET_MODEL)

    print("[elform] TET4 → TET10 → TET4 → TET10")
    rc, out = assemble(binary, d, "up1", "tet4.k", 16)
    check("TET4 → TET10 변환", rc == 0 and re.search(r"converted 2 elements", out), out[-300:])
    rc, out = assemble(binary, d, "down", "up1.k", 13)
    check("TET10 → TET4 하향 rc=0", rc == 0, out[-300:])
    if rc == 0:
        tets = [r for r in solid_rows(os.path.join(d, "down.k")) if len(r) == 10]
        check("하향 결과 사면체 2개", len(tets) == 2, str(tets))
        std = all(r[5] == r[6] == r[7] == r[8] == r[9] and r[4] != r[5] for r in tets)
        check("연결 순서 N1 N2 N3 N4 N4 N4 N4 N4", std and tets, str(tets))
        rc, out = assemble(binary, d, "up2", "down.k", 16)
        check("하향 출력을 다시 읽어 TET10 변환 (자기 출력 재사용)",
              rc == 0 and re.search(r"converted 2 elements", out), out[-300:])

    print()
    if FAILS:
        print(f"FAIL {len(FAILS)}")
        for f in FAILS:
            print("  -", f[:300])
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
