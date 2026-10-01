#!/usr/bin/env python3
# prestress 의 숫자를 해석해와 맞춘다 — 주응력 부호 버그를 다시 들이지 않기 위해
"""최소 탐침으로 `prestress` 의 수치 계약을 지킨다 (2026-10-02).

왜 이 시험이 있나.

  현장 보고(수정제안서 v1.0 §3-1e)가 "hex8 ×2, x 1% 인장, E 210000 ν 0.3 탐침에서 로컬 구현과
  KooRemapper 가 전단 반올림까지 일치했다 — 이 탐침을 회귀로 넣을 것을 권한다" 고 적었다.
  그 권고를 받아들이는데, 더 중요한 이유가 생겼다 — **그 보고를 검증하다 주응력 부호 버그를
  찾았다.**

  `λ³ - I1λ² + I2λ - I3 = 0` 에 `λ = t + I1/3` 을 넣으면 `t³ + Pt + Q = 0` 이고
  `Q = -2I1³/27 + I1I2/3 - I3` 다. `StressTensor`·`StrainCalculator` 가 그 **반대 부호**를 써서
  삼각해의 `acos` 인자가 뒤집히고 **편차 고유값이 음수로 뒤집혔다.** 증상이 조용했다 —
  von Mises 는 맞게 나오고(그쪽은 다른 경로다) CSV 의 주응력만 틀렸으며, 같은 응력 상태의 두
  요소가 서로 다른 값을 보고했다.

  그래서 이 시험은 **해석해**를 기준으로 쓴다. "값이 바뀌었나" 가 아니라 "이론과 같나" 를 본다.

1축 구속 인장(εyy=εzz=0)의 이론값 — ε = 0.01005(1% 늘림의 Green 변형률):
    σxx = E(1-ν)/((1+ν)(1-2ν))·ε = 210000·0.7/(1.3·0.4)·0.01005 = 2841.06
    σyy = σzz = Eν/((1+ν)(1-2ν))·ε = 210000·0.3/0.52·0.01005 = 1217.60
    von Mises = σxx - σyy = 1623.46

usage: test_prestress_probe.py <KooRemapper 바이너리>
"""
import csv
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


def near(a, b, rel=1e-5):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if b == 0:
        return abs(a) < rel
    return abs(a - b) / abs(b) < rel


def write_deck(path, sx):
    """2 x hex8 을 z 로 쌓은 블록. `sx` 로 x 를 늘린다."""
    nid, coord, nodes = 1, {}, []
    for k in (0, 1, 2):
        for j in (0, 1):
            for i in (0, 1):
                coord[(i, j, k)] = nid
                nodes.append((nid, i * 1.0 * sx, j * 1.0, k * 1.0))
                nid += 1
    L = ["*KEYWORD", "*NODE"]
    for i, x, y, z in nodes:
        L.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
    L.append("*ELEMENT_SOLID")
    for e, k in ((1, 0), (2, 1)):
        c = [coord[(0, 0, k)], coord[(1, 0, k)], coord[(1, 1, k)], coord[(0, 1, k)],
             coord[(0, 0, k + 1)], coord[(1, 0, k + 1)], coord[(1, 1, k + 1)], coord[(0, 1, k + 1)]]
        L.append("%8d%8d" % (e, 1) + "".join("%8d" % v for v in c))
    L += ["*PART", "probe", "%10d%10d%10d" % (1, 1, 1),
          "*SECTION_SOLID", "%10d%10d" % (1, 1),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
    open(path, "w", newline="\n").write("\n".join(L) + "\n")


def main():
    if len(sys.argv) < 2:
        print("usage: test_prestress_probe.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="pstprobe_")
    try:
        write_deck(os.path.join(d, "ref.k"), 1.00)
        write_deck(os.path.join(d, "def.k"), 1.01)
        p = subprocess.run([binary, "prestress", "ref.k", "def.k", "out.k", "--csv"],
                           capture_output=True, text=True, timeout=600, cwd=d)
        out = p.stdout + p.stderr
        check("A-1 prestress rc=0", p.returncode == 0, out[-300:])
        check("A-2 두 요소 모두 유효", "Valid elements:          2" in out
              or "Valid elements: 2" in out.replace("  ", " "), out[-400:])

        # von Mises — 해석해 1623.46
        vm = [l for l in out.splitlines() if "von Mises stress" in l]
        got_vm = None
        for l in vm:
            try:
                got_vm = float(l.split(":")[1].strip())
                break
            except (IndexError, ValueError):
                continue
        check("A-3 von Mises 응력 = 해석해 1623.46", near(got_vm, 1623.462, 1e-4),
              "got=%r / lines=%r" % (got_vm, vm[:1]))

        csvp = os.path.join(d, "out.csv")
        if not os.path.exists(csvp):
            check("B CSV 가 생겼다", False, sorted(os.listdir(d)))
            return 1 if FAILS else 0
        rows = list(csv.DictReader(open(csvp, encoding="utf-8")))
        check("B-1 CSV 에 요소 2개", len(rows) == 2, len(rows))

        # ★ 이 둘이 부호 버그를 지킨다. 1축 구속 인장의 주응력은 diag 성분과 같다.
        for i, r in enumerate(rows):
            check("B-2.%d maxPrincipalStress = 2841.06 (해석해)" % (i + 1),
                  near(r.get("maxPrincipalStress"), 2841.058, 1e-4),
                  r.get("maxPrincipalStress"))
            check("B-3.%d minPrincipalStress = 1217.60 (해석해)" % (i + 1),
                  near(r.get("minPrincipalStress"), 1217.596, 1e-4),
                  r.get("minPrincipalStress"))
        # 같은 응력 상태의 두 요소가 다른 값을 내면 그 자체가 결함이다(부호 버그의 실제 증상).
        if len(rows) == 2:
            check("B-4 같은 상태의 두 요소가 같은 주응력을 낸다",
                  near(rows[0].get("maxPrincipalStress"), rows[1].get("maxPrincipalStress"), 1e-9)
                  and near(rows[0].get("minPrincipalStress"), rows[1].get("minPrincipalStress"), 1e-9),
                  [rows[0].get("maxPrincipalStress"), rows[1].get("maxPrincipalStress")])
        # 주응력은 von Mises 와 맞물려야 한다 — 1축이면 vm = σmax - σmin.
        if rows:
            try:
                a = float(rows[0]["maxPrincipalStress"]); b = float(rows[0]["minPrincipalStress"])
                check("B-5 주응력과 von Mises 가 서로 맞는다 (vm = σmax - σmin)",
                      near(a - b, 1623.462, 1e-4), a - b)
            except (KeyError, ValueError) as e:
                check("B-5 주응력 칸을 읽었다", False, str(e))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    if FAILS:
        print("--- 실패 %d건 ---" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
