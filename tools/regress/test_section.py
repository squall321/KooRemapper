#!/usr/bin/env python3
# section op 의 단면 다각형을 닫힌식과 맞춘다 — 그림이 조용히 거짓말하는 것을 막는 관문
"""`section` 의 기하 계약 (2026-10-03).

왜 이 시험이 있나.

  **그림은 조용히 틀린다.** 숫자는 틀리면 이상해 보이지만 그림은 그럴듯해 보인다. 그래서 이
  시험은 픽셀을 비교하지 않는다(폰트·버전에 깨진다). 보는 것은 둘이다.

    ① 단면 다각형의 **면적을 닫힌식**과 맞춘다. 모서리∩평면은 1차 방정식이라 정확해야 한다.
    ② **매니페스트의 숫자**를 검사한다 — 축 선택 근거·맞은 파트 수·절점 적중·ε 비킴·최소 피처.
       그림이 거짓말하지 않게 하는 장치가 바로 그 숫자들이다.

  ⚠ 요소 종류를 전수로 본다. 면 테이블(`Element.h:99-124`)로 짜면 **TET4 가 틀린다** —
  TET4 는 `n5..n8 = n4` 로 저장되고 `isFaceDegenerate` 는 `fn[0]==fn[1] && fn[2]==fn[3]` 만
  보므로 면 0 `[n0,n3,n3,n3]`·면 3 `[n3,n2,n3,n3]` 이 **가짜 면으로 통과한다.** 그래서 이 op 은
  모서리 기반이고, 육면체 12 모서리 표를 TET 에 쓰면 모서리 `(n0,n2)` 가 빠지므로 종류별 표를
  쓴다. 이 시험이 그 둘을 지킨다.

usage: test_section.py <KooRemapper 바이너리>
"""
import json
import math
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


def near(a, b, tol=1e-9):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return abs(a - b) <= tol * max(1.0, abs(b))


def run(binary, cwd, cfg):
    p = subprocess.run([binary, "section", cfg], capture_output=True, text=True,
                       timeout=900, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def write_cfg(path, **kw):
    with open(path, "w", newline="\n") as f:
        for k, v in kw.items():
            f.write("%s: %s\n" % (k, v))


def deck(path, nodes, elems, parts, shell=False, thickness=None):
    """nodes = [(x,y,z)] 1-기반, elems = [(pid, [8개 절점])]"""
    L = ["*KEYWORD", "*NODE"]
    for i, (x, y, z) in enumerate(nodes, start=1):
        L.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
    L.append("*ELEMENT_SHELL" if shell else "*ELEMENT_SOLID")
    for e, (pid, c) in enumerate(elems, start=1):
        L.append("%8d%8d" % (e, pid) + "".join("%8d" % v for v in c))
    for pid in parts:
        L += ["*PART", "p%d" % pid, "%10d%10d%10d" % (pid, pid, pid)]
        if shell:
            L += ["*SECTION_SHELL", "%10d%10d" % (pid, 2)]
            t = thickness if thickness else 0.05
            L += ["%10.6g%10.6g%10.6g%10.6g" % (t, t, t, t)]
        else:
            L += ["*SECTION_SOLID", "%10d%10d" % (pid, 1)]
        L += ["*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (pid, 7.85e-9, 210000.0, 0.3)]
    L.append("*END")
    open(path, "w", newline="\n").write("\n".join(L) + "\n")


def poly_area(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def load(d, stem):
    return json.load(open(os.path.join(d, stem + "_section.json"), encoding="utf-8"))


def main():
    if len(sys.argv) < 2:
        print("usage: test_section.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="sec_")
    try:
        # ── A: HEX8 — 단위 정육면체를 z=0.5 로 ──
        deck(os.path.join(d, "hex.k"),
             [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
             [(1, [1, 2, 3, 4, 5, 6, 7, 8])], [1])
        write_cfg(os.path.join(d, "a.yaml"), model="hex.k", output="a", axis="z", at=0.5)
        rc, out = run(binary, d, "a.yaml")
        check("A-1 rc=0", rc == 0, out[-300:])
        j = load(d, "a")
        check("A-2 다각형 1개", j["polygons"] == 1, j["polygons"])
        check("A-3 꼭짓점 4개", len(j["polys"][0]["pts"]) == 4, j["polys"][0]["pts"])
        check("A-4 면적 = 1 (닫힌식)", near(poly_area(j["polys"][0]["pts"]), 1.0), 
              poly_area(j["polys"][0]["pts"]))
        check("A-5 단위를 주장하지 않는다", "unknown" in j["units"], j["units"])

        # ── B: ★TET4 — 면 기반이면 틀리는 자리 ──
        deck(os.path.join(d, "tet.k"),
             [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)],
             [(1, [1, 2, 3, 4, 4, 4, 4, 4])], [1])
        for at, want in ((0.25, (1 - 0.25) ** 2 / 2), (0.5, (1 - 0.5) ** 2 / 2),
                         (0.75, (1 - 0.75) ** 2 / 2)):
            write_cfg(os.path.join(d, "b.yaml"), model="tet.k", output="b", axis="z", at=at)
            rc, out = run(binary, d, "b.yaml")
            if rc != 0:
                check("B TET4 z=%g rc=0" % at, False, out[-200:])
                continue
            j = load(d, "b")
            ok = j["polygons"] == 1 and len(j["polys"][0]["pts"]) == 3
            check("B TET4 z=%g — 삼각형 1개 · 면적 %.9g (닫힌식)" % (at, want),
                  ok and near(poly_area(j["polys"][0]["pts"]), want),
                  (j["polygons"], poly_area(j["polys"][0]["pts"]) if j["polygons"] else None))

        # ── C: PENTA6 (쐐기, n3=n4·n7=n8) ──
        deck(os.path.join(d, "penta.k"),
             [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1)],
             [(1, [1, 2, 3, 3, 4, 5, 6, 6])], [1])
        write_cfg(os.path.join(d, "c.yaml"), model="penta.k", output="c", axis="z", at=0.5)
        rc, out = run(binary, d, "c.yaml")
        check("C-1 rc=0", rc == 0, out[-300:])
        j = load(d, "c")
        check("C-2 z 단면 = 삼각형, 면적 0.5 (쐐기는 z 로 일정)",
              j["polygons"] == 1 and len(j["polys"][0]["pts"]) == 3
              and near(poly_area(j["polys"][0]["pts"]), 0.5),
              (j["polygons"], poly_area(j["polys"][0]["pts"])))
        write_cfg(os.path.join(d, "c2.yaml"), model="penta.k", output="c2", axis="x", at=0.25)
        rc, out = run(binary, d, "c2.yaml")
        j = load(d, "c2")
        check("C-3 x=0.25 단면 = 사각형, 면적 0.75 (닫힌식)",
              len(j["polys"][0]["pts"]) == 4 and near(poly_area(j["polys"][0]["pts"]), 0.75),
              (len(j["polys"][0]["pts"]), poly_area(j["polys"][0]["pts"])))

        # ── D: 셸(QUAD4) — 선분이 나오고 두께는 *SECTION_SHELL 에서 ──
        deck(os.path.join(d, "sh.k"),
             [(0, 0, 0), (2, 0, 0), (2, 1, 0), (0, 1, 0)],
             [(1, [1, 2, 3, 4])], [1], shell=True, thickness=0.07)
        write_cfg(os.path.join(d, "e.yaml"), model="sh.k", output="e", axis="x", at=1.0)
        rc, out = run(binary, d, "e.yaml")
        check("D-1 rc=0", rc == 0, out[-300:])
        j = load(d, "e")
        check("D-2 셸은 선분이다(점 2개)",
              j["polygons"] == 1 and j["polys"][0]["shell"] is True
              and len(j["polys"][0]["pts"]) == 2, j["polys"])
        pi = j["parts"][0]
        check("D-3 두께를 *SECTION_SHELL 에서 읽었다 (0.07)", near(pi["thickness"], 0.07),
              pi.get("thickness"))
        check("D-4 두께 출처를 **말한다** (메시가 아니다)",
              "SECTION_SHELL" in (pi.get("thickness_note") or ""), pi.get("thickness_note"))

        # ── E: ★평면이 절점층에 정확히 걸리면 ε 비켜 다시 자른다 ──
        # 3층 적층. 층 경계 z=0.2 는 사용자가 가장 보고 싶은 자리이고 동시에 퇴화 케이스다.
        nodes, elems, nid, idx = [], [], 1, {}
        zs = [0.0, 0.2, 0.5, 0.6]
        for k, z in enumerate(zs):
            for j_ in (0, 1):
                for i_ in (0, 1):
                    nodes.append((i_ * 1.0, j_ * 1.0, z))
                    idx[(i_, j_, k)] = nid
                    nid += 1
        for k in range(3):
            c = [idx[(0,0,k)], idx[(1,0,k)], idx[(1,1,k)], idx[(0,1,k)],
                 idx[(0,0,k+1)], idx[(1,0,k+1)], idx[(1,1,k+1)], idx[(0,1,k+1)]]
            elems.append((k + 1, c))
        deck(os.path.join(d, "stk.k"), nodes, elems, [1, 2, 3])
        write_cfg(os.path.join(d, "f.yaml"), model="stk.k", output="f", axis="z", at=0.2)
        rc, out = run(binary, d, "f.yaml")
        check("E-1 rc=0", rc == 0, out[-300:])
        jb = load(d, "f")
        check("E-2 평면 위 절점을 **세서 알린다**", jb["node_plane_hits"] > 0, jb["node_plane_hits"])
        check("E-3 ε 만큼 비켰다", jb["nudge"] > 0 and jb["at"] > 0.2, (jb["nudge"], jb["at"]))
        write_cfg(os.path.join(d, "g.yaml"), model="stk.k", output="g", axis="z", at=0.1)
        rc, out = run(binary, d, "g.yaml")
        ji = load(d, "g")
        check("E-4 비킨 결과가 층 내부와 **같은 다각형 수** (두 배가 안 됐다)",
              jb["polygons"] == ji["polygons"], (jb["polygons"], ji["polygons"]))
        check("E-5 층 내부에서는 비키지 않는다", ji["nudge"] == 0 and ji["node_plane_hits"] == 0,
              (ji["nudge"], ji["node_plane_hits"]))

        # ── F: ★축 자동선택 — "적층 방향에 수직" 이 규칙이 아니다 ──
        write_cfg(os.path.join(d, "h.yaml"), model="stk.k", output="h", axis="auto")
        rc, out = run(binary, d, "h.yaml")
        check("F-1 rc=0", rc == 0, out[-300:])
        ja = load(d, "h")
        check("F-2 적층은 z 를 고르지 않는다 (z 는 층 하나만 만난다)", ja["axis"] != "z", ja["axis"])
        check("F-3 세 층을 모두 만난다", ja["parts_hit"] == 3, (ja["parts_hit"], ja["parts_total"]))
        check("F-4 고른 까닭을 **숫자로** 적는다",
              "파트" in ja["axis_chosen_because"] and "다각형" in ja["axis_chosen_because"],
              ja["axis_chosen_because"])

        # ── G: 최소 피처 — 그리는 쪽이 축척을 정하는 입력 ──
        check("G-1 최소 피처를 낸다", ja.get("min_feature", 0) > 0, ja.get("min_feature"))
        # stk.k 의 층 두께는 0.2 / 0.3 / 0.1 → 최소 0.1
        check("G-2 최소 피처 = 0.1 (가장 얇은 층)", near(ja["min_feature"], 0.1, 1e-6),
              ja.get("min_feature"))
        check("G-3 파트마다 단면 안 2D 범위를 낸다",
              all("thin" in p and "extent" in p for p in ja["parts"]), ja["parts"][:1])

        # ── H: 빈 단면·퇴화는 그림을 내지 않는다 ──
        write_cfg(os.path.join(d, "i.yaml"), model="hex.k", output="i", axis="z", at=9.0)
        rc, out = run(binary, d, "i.yaml")
        check("H-1 아무것도 안 잘리면 rc=1", rc == 1, out[-200:])
        check("H-2 까닭을 말한다", "자르지 않는다" in out or "아무 요소도" in out, out[-200:])
        check("H-3 JSON 을 쓰지 않는다", not os.path.exists(os.path.join(d, "i_section.json")))

        for name, args in (("H-4 model 누락은 rc=1", dict(output="x", axis="z")),
                           ("H-5 output 누락은 rc=1", dict(model="hex.k", axis="z")),
                           ("H-6 모르는 axis 는 rc=1", dict(model="hex.k", output="x", axis="q"))):
            write_cfg(os.path.join(d, "j.yaml"), **args)
            rc, out = run(binary, d, "j.yaml")
            check(name, rc == 1, out[-200:])

        # ── I: 기하가 없는 *INCLUDE 마스터 덱 — 빈 그림이 아니라 거절 ──
        with open(os.path.join(d, "master.k"), "w", newline="\n") as f:
            f.write("*KEYWORD\n*INCLUDE\nmesh_geometry.k\n*INCLUDE\nmaterials.k\n*END\n")
        write_cfg(os.path.join(d, "k.yaml"), model="master.k", output="k", axis="auto")
        rc, out = run(binary, d, "k.yaml")
        check("I-1 기하가 없으면 rc=1", rc == 1, out[-200:])
        check("I-2 빈 그림을 내지 않는다고 말한다", "빈 그림" in out, out[-300:])
        check("I-3 **어느 파일**을 지목해야 하는지 알려 준다",
              "mesh_geometry.k" in out, out[-400:])
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
