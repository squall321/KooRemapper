#!/usr/bin/env python3
# surfview 의 자유면 수를 닫힌식과 맞춘다 — 면 테이블로 짜면 TET4 가 틀린다
"""`surfview` 의 기하 계약 (2026-10-03).

왜 이 시험이 있나.

  **자유면 판정이 조용히 틀린다.** 공용 면 테이블은 육면체 기준이고 `isFaceDegenerate` 는
  `fn[0]==fn[1] && fn[2]==fn[3]` 만 본다. TET4 는 `n5..n8 = n4` 로 저장되므로
    · 면 0 `[n0,n3,n3,n3]`·면 3 `[n3,n2,n3,n3]` 는 **변으로 찌그러진 가짜 면**인데 통과하고
    · 면 4 `[n0,n1,n2,n3]` 는 사면체의 네 꼭짓점을 잇는 **비평면 사각형**이다
  그래서 그 표로 자유면을 세면 TET 덱의 표면이 틀린다 — 실측으로 `extract-surface` 가 TET4
  하나에서 **자유면 5개**를 내고 그중 **3개가 가짜**다(진짜 면 `(1,2,3)`·`(1,3,4)` 는 빠진다).

  이 시험은 종류별 면 테이블이 맞는지를 **닫힌식**으로 못 박는다.
    · HEX8 하나 → 자유면 **6**면 · 삼각형 **12**개
    · TET4 하나 → 자유면 **4**면 · 삼각형 **4**개   ← 여기가 갈리는 자리다
    · PENTA6 하나 → 자유면 **5**면 · 삼각형 **8**개 (삼각 2 + 사각 3 → 2 + 6)
  그리고 닫힌 볼록체는 **등진 삼각형이 정확히 절반**이어야 한다.

usage: test_surfview.py <KooRemapper 바이너리>
"""
import os
import re
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


def kv(out, key):
    for line in out.splitlines():
        if line.startswith(key + ":"):
            return line[len(key) + 1:].strip()
    return None


def run(binary, cwd, cfg):
    p = subprocess.run([binary, "surfview", cfg], capture_output=True, text=True,
                       timeout=900, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def write_cfg(path, **kw):
    with open(path, "w", newline="\n") as f:
        for k, v in kw.items():
            f.write("%s: %s\n" % (k, v))


def deck(path, nodes, conn, pid=1, shell=False):
    L = ["*KEYWORD", "*NODE"]
    for i, (x, y, z) in enumerate(nodes, start=1):
        L.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
    L.append("*ELEMENT_SHELL" if shell else "*ELEMENT_SOLID")
    for e, c in enumerate(conn, start=1):
        L.append("%8d%8d" % (e, pid) + "".join("%8d" % v for v in c))
    L += ["*PART", "p%d" % pid, "%10d%10d%10d" % (pid, pid, pid)]
    L += (["*SECTION_SHELL", "%10d%10d" % (pid, 2), "%10.6g%10.6g%10.6g%10.6g" % (0.05,)*4]
          if shell else ["*SECTION_SOLID", "%10d%10d" % (pid, 1)])
    L += ["*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (pid, 7.85e-9, 210000.0, 0.3), "*END"]
    open(path, "w", newline="\n").write("\n".join(L) + "\n")


def nums(out):
    ft = kv(out, "Faces total / free") or ""
    m = re.match(r"(\d+)\s*/\s*(\d+)", ft)
    tri = kv(out, "Triangles drawn")
    back = kv(out, "Back-facing triangles")
    return (int(m.group(1)) if m else None, int(m.group(2)) if m else None,
            int(tri) if tri else None, int(back) if back else None)


def main():
    if len(sys.argv) < 2:
        print("usage: test_surfview.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="surf_")
    CUBE = [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)]
    try:
        # ── A: HEX8 하나 ──
        deck(os.path.join(d, "cube.k"), CUBE, [list(range(1, 9))])
        write_cfg(os.path.join(d, "a.yaml"), model="cube.k", output="a")
        rc, out = run(binary, d, "a.yaml")
        check("A-1 rc=0", rc == 0, out[-300:])
        tot, free, tri, back = nums(out)
        check("A-2 HEX8 자유면 6면 (닫힌식)", tot == 6 and free == 6, (tot, free))
        check("A-3 삼각형 12개 (사각면 → 2개씩)", tri == 12, tri)
        check("A-4 닫힌 볼록체는 등진 삼각형이 **정확히 절반**", back == 6, back)

        # ── B: ★TET4 — 면 테이블로 짜면 틀리는 자리 ──
        deck(os.path.join(d, "tet.k"), [(0,0,0),(1,0,0),(0,1,0),(0,0,1)],
             [[1,2,3,4,4,4,4,4]])
        write_cfg(os.path.join(d, "b.yaml"), model="tet.k", output="b")
        rc, out = run(binary, d, "b.yaml")
        check("B-1 rc=0", rc == 0, out[-300:])
        tot, free, tri, back = nums(out)
        check("B-2 ★TET4 자유면 **4**면 (면 테이블은 5개를 내고 3개가 가짜다)",
              tot == 4 and free == 4, (tot, free))
        check("B-3 삼각형 4개 (모두 삼각면)", tri == 4, tri)
        check("B-4 찌그러진 면을 건너뛰었다고 적는다", kv(out, "Degenerate faces skipped") is not None,
              kv(out, "Degenerate faces skipped"))

        # ── C: PENTA6 ──
        deck(os.path.join(d, "pen.k"), [(0,0,0),(1,0,0),(0,1,0),(0,0,1),(1,0,1),(0,1,1)],
             [[1,2,3,3,4,5,6,6]])
        write_cfg(os.path.join(d, "c.yaml"), model="pen.k", output="c")
        rc, out = run(binary, d, "c.yaml")
        tot, free, tri, back = nums(out)
        check("C-1 PENTA6 자유면 5면 · 삼각형 8개 (삼각2 + 사각3→6)",
              tot == 5 and free == 5 and tri == 8, (tot, free, tri))

        # ── D: 두 요소가 맞붙으면 그 면은 자유면이 아니다 ──
        two = CUBE + [(0,0,2),(1,0,2),(1,1,2),(0,1,2)]
        deck(os.path.join(d, "two.k"), two,
             [[1,2,3,4,5,6,7,8], [5,6,7,8,9,10,11,12]])
        write_cfg(os.path.join(d, "e.yaml"), model="two.k", output="e")
        rc, out = run(binary, d, "e.yaml")
        tot, free, tri, back = nums(out)
        check("D-1 맞붙은 면은 자유면이 아니다 (전체 11면 중 자유 10면)",
              tot == 11 and free == 10, (tot, free))
        check("D-2 삼각형 20개", tri == 20, tri)

        # ── E: ★ink_ratio 와 포화 경고 ──
        check("E-1 ink_ratio 를 낸다", kv(out, "ink_ratio (edges)") is not None,
              kv(out, "ink_ratio (edges)"))
        write_cfg(os.path.join(d, "w.yaml"), model="two.k", output="w", wire="true",
                  width=430, height=240)
        rc, outw = run(binary, d, "w.yaml")
        check("E-2 wire 모드도 rc=0", rc == 0, outw[-200:])

        # ── F: 그림이 거짓말하지 않게 하는 줄들이 **그림 안에** 있나 ──
        svg = open(os.path.join(d, "a_surface.svg"), encoding="utf-8").read()
        for need in ("자유면", "등축", "단위 없음", "등진 삼각형", "ink_ratio", "깊이정렬"):
            check("F 그림 안에 '%s'" % need, need in svg,
                  [l for l in svg.splitlines() if "text" in l][:1])
        check("F-2 범례를 그림 안에 굽는다", svg.count("<rect") >= 2, svg.count("<rect"))
        import xml.etree.ElementTree as ET
        try:
            ET.fromstring(svg.encode("utf-8")); xok, why = True, ""
        except Exception as ex:
            xok, why = False, str(ex)
        check("F-3 SVG 가 XML 로 파싱된다", xok, why)
        for tok in ("<script", "onload=", "<foreignObject"):
            check("F-4 '%s' 가 없다" % tok, tok not in svg)

        # ── G: 잘못된 입력 ──
        for name, args in (("G-1 model 누락은 rc=1", dict(output="x")),
                           ("G-2 output 누락은 rc=1", dict(model="cube.k")),
                           ("G-3 캔버스가 작으면 rc=1", dict(model="cube.k", output="x",
                                                        width=300, height=300))):
            write_cfg(os.path.join(d, "g.yaml"), **args)
            rc, outg = run(binary, d, "g.yaml")
            check(name, rc == 1, outg[-200:])
        # 기하가 없는 덱
        open(os.path.join(d, "empty.k"), "w", newline="\n").write("*KEYWORD\n*INCLUDE\nmesh.k\n*END\n")
        write_cfg(os.path.join(d, "h.yaml"), model="empty.k", output="h")
        rc, outh = run(binary, d, "h.yaml")
        check("G-4 기하가 없으면 rc=1 · 빈 그림을 내지 않는다", rc == 1 and "빈 그림" in outh,
              outh[-200:])
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
