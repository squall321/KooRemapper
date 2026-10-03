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
        # ── J: SVG — 그림이 거짓말하지 않게 하는 줄들이 **그림 안에** 있나 ──
        write_cfg(os.path.join(d, "sv.yaml"), model="stk.k", output="sv", axis="auto")
        rc, out = run(binary, d, "sv.yaml")
        check("J-1 rc=0", rc == 0, out[-300:])
        svgp = os.path.join(d, "sv_section.svg")
        check("J-2 SVG 를 썼다", os.path.exists(svgp))
        svg = open(svgp, encoding="utf-8").read() if os.path.exists(svgp) else ""
        check("J-3 다각형을 그렸다", svg.count("<polygon") >= 3, svg.count("<polygon"))
        for need, why in (("배 확대", "확대 배율을 적는다"), ("단위 없음", "단위를 주장하지 않는다"),
                          ("최소피처", "최소 피처를 적는다"), ("눈금", "눈금자를 둔다"),
                          ("단면 — 축", "무엇을 잘랐는지 적는다")):
            check("J-4 그림 안에 '%s' — %s" % (need, why), need in svg,
                  [l for l in svg.splitlines() if "text" in l][:2])
        check("J-5 범례를 그림 안에 굽는다 (색 견본 + 파트)",
              svg.count("<rect") >= 4, svg.count("<rect"))
        check("J-6 가로·세로 눈금자가 **둘** 다 있다", svg.count("눈금") >= 2, svg.count("눈금"))

        # ── K: ★등축으로 강제하면 "보이지 않는다" 고 말한다 ──
        write_cfg(os.path.join(d, "iso.yaml"), model="stk.k", output="iso", axis="auto",
                  isotropic="true", width=600, height=400)
        rc, out = run(binary, d, "iso.yaml")
        check("K-1 rc=0", rc == 0, out[-300:])
        check("K-2 등축이면 확대 배율이 1 이다", "x1.000000" in out,
              [l for l in out.splitlines() if "Magnified" in l])
        # 너무 작은 캔버스는 **앞에서** 거른다 — JSON 을 먼저 쓰고 실패하면 반쪽 산출물이 남는다
        write_cfg(os.path.join(d, "tiny.yaml"), model="stk.k", output="tiny", axis="z",
                  at=0.1, width=300, height=300)
        rc, out = run(binary, d, "tiny.yaml")
        check("K-3 캔버스가 작으면 rc=1", rc == 1, out[-200:])
        check("K-4 범례 자리가 필요하다고 말한다", "범례" in out, out[-200:])
        check("K-5 반쪽 산출물을 남기지 않는다 (JSON 도 안 쓴다)",
              not os.path.exists(os.path.join(d, "tiny_section.json")))
        # ★등축이면 실제 적층에서 층이 안 보인다 — 그 사실을 말하는지
        write_cfg(os.path.join(d, "thin.yaml"), model="stk.k", output="thin", axis="auto",
                  isotropic="true", width=430, height=240)
        rc, out = run(binary, d, "thin.yaml")
        check("K-6 최소피처를 **픽셀로** 보고한다", "Min feature in px" in out,
              [l for l in out.splitlines() if "px" in l][:2])

        # ── L: ★SVG 안전 — 파트 제목은 자유 텍스트다 ──
        evil = '<script>alert(1)</script>&"\'' + chr(1) + '한글 "따옴표"'
        nodes2 = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                  (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
        L = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(nodes2, start=1):
            L.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1) + "".join("%8d" % v for v in range(1, 9)),
              "*PART", evil, "%10d%10d%10d" % (1, 1, 1),
              "*SECTION_SOLID", "%10d%10d" % (1, 1),
              "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000.0, 0.3), "*END"]
        open(os.path.join(d, "evil.k"), "w", newline="\n", encoding="utf-8").write("\n".join(L) + "\n")
        write_cfg(os.path.join(d, "m.yaml"), model="evil.k", output="m", axis="z", at=0.5)
        rc, out = run(binary, d, "m.yaml")
        check("L-1 rc=0 (악성 제목에도 돈다)", rc == 0, out[-300:])
        ev = open(os.path.join(d, "m_section.svg"), encoding="utf-8").read()
        for tok in ("<script", "</script", "onload=", "onerror=", "<foreignObject", "javascript:"):
            check("L-2 SVG 에 '%s' 가 없다" % tok, tok not in ev,
                  [l for l in ev.splitlines() if tok in l][:1])
        check("L-3 `<` 를 이스케이프했다", "&lt;script" in ev, ev[:0])
        check("L-4 제어문자를 보이는 기호로 바꿨다",
              chr(1) not in ev and "제어문자" in ev, "제어문자" in ev)
        check("L-5 한글 제목이 그대로 남았다", "한글" in ev)
        # XML 로 실제 파싱되나 — 제어문자 하나로 SVG 가 통째로 안 읽히는 것을 막았는지
        import xml.etree.ElementTree as ET
        try:
            ET.fromstring(ev)
            parsed = True
            why = ""
        except Exception as e:
            parsed = False
            why = str(e)
        check("L-6 **XML 로 파싱된다** (제어문자 하나로 통째로 깨지지 않는다)", parsed, why)
        # JSON 쪽도 파싱되나
        try:
            json.load(open(os.path.join(d, "m_section.json"), encoding="utf-8"))
            jok, jwhy = True, ""
        except Exception as e:
            jok, jwhy = False, str(e)
        check("L-7 JSON 도 파싱된다", jok, jwhy)
        # ── M: 두 덱 — 두 칸(panels)과 겹침(overlay) ──
        # 같은 적층을 z 로 0.05 옮긴 것을 '변형 후' 로 쓴다(절점 번호가 같다)
        nodes3 = [(x, y, z + 0.05) for (x, y, z) in nodes]
        deck(os.path.join(d, "stk2.k"), nodes3, elems, [1, 2, 3])
        write_cfg(os.path.join(d, "pan.yaml"), model="stk.k", compare="stk2.k",
                  mode="panels", output="pan")
        rc, out = run(binary, d, "pan.yaml")
        check("M-1 panels rc=0", rc == 0, out[-400:])
        jp = load(d, "pan")
        check("M-2 mode 가 panels", jp["mode"] == "panels", jp.get("mode"))
        check("M-3 compare 매니페스트가 따로 있다", "compare" in jp and "polys" in jp["compare"],
              list(jp.keys()))
        check("M-4 두 덱 이름을 적는다",
              jp["deck"].endswith("stk.k") and jp["compare"]["deck"].endswith("stk2.k"),
              (jp.get("deck"), jp.get("compare", {}).get("deck")))
        check("M-5 단일 덱 모양이 그대로다 (기존 소비자 보호)",
              all(k in jp for k in ("axis", "at", "polygons", "parts", "polys", "min_feature")),
              list(jp.keys()))
        svgp = os.path.join(d, "pan_section.svg")
        sp = open(svgp, encoding="utf-8").read()
        check("M-6 두 칸에 두 덱 이름이 있다", "stk.k" in sp and "stk2.k" in sp)
        check("M-7 칸마다 확대 배율을 적는다", sp.count("배 확대") >= 1 and "·" in sp)
        check("M-8 두 칸의 보고가 각각 찍힌다 (A·B)",
              "Deck:" in out and out.count("Deck:") == 2, out.count("Deck:"))

        write_cfg(os.path.join(d, "ovl.yaml"), model="stk.k", compare="stk2.k",
                  mode="overlay", output="ovl")
        rc, out = run(binary, d, "ovl.yaml")
        check("M-9 overlay rc=0", rc == 0, out[-400:])
        jo = load(d, "ovl")
        check("M-10 mode 가 overlay", jo["mode"] == "overlay", jo.get("mode"))
        check("M-11 ★겹침은 **같은 평면**으로 자른다",
              jo["axis"] == jo["compare"]["axis"] and near(jo["at"], jo["compare"]["at"], 1e-12),
              (jo["axis"], jo["at"], jo["compare"]["axis"], jo["compare"]["at"]))
        check("M-12 같은 평면으로 잘랐다고 **말한다**", "같은 평면" in out, out[-300:])
        so = open(os.path.join(d, "ovl_section.svg"), encoding="utf-8").read()
        check("M-13 겹침은 B 를 점선으로 그린다", "stroke-dasharray" in so)
        check("M-14 겹침 SVG 에 두 덱 이름이 있다", "stk.k" in so and "stk2.k" in so)

        for name, args in (("M-15 모르는 mode 는 rc=1",
                            dict(model="stk.k", compare="stk2.k", mode="nope", output="x")),
                           ("M-16 없는 compare 덱은 rc=1",
                            dict(model="stk.k", compare="nope.k", output="x"))):
            write_cfg(os.path.join(d, "mm.yaml"), **args)
            rc, out = run(binary, d, "mm.yaml")
            check(name, rc == 1, out[-200:])

        # ── N: ★동점 규칙 — 다각형 수가 아니라 단면 넓이로 고른다 ──
        check("N-1 축 선택 근거에 **넓이**가 들어 있다", "넓이" in jp["axis_chosen_because"],
              jp["axis_chosen_because"])
        # ── O: ★제목이 UTF-8 이 아닌 덱(CP949) — 그림이 **죽지 않아야** 한다 ──
        # 실측 — 그대로 쓰면 UTF-8 선언 SVG 의 XML 파싱이 통째로 실패했다.
        head = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(nodes2, start=1):
            head.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
        head += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1) + "".join("%8d" % v for v in range(1, 9)),
                 "*PART", "@T@", "%10d%10d%10d" % (1, 1, 1),
                 "*SECTION_SOLID", "%10d%10d" % (1, 1),
                 "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000.0, 0.3), "*END"]
        raw = ("\n".join(head) + "\n").encode("ascii").replace(
            b"@T@", "알루미늄 집전체".encode("cp949"))
        open(os.path.join(d, "cp949.k"), "wb").write(raw)
        write_cfg(os.path.join(d, "cp.yaml"), model="cp949.k", output="cp", axis="z", at=0.5)
        rc, out = run(binary, d, "cp.yaml")
        check("O-1 rc=0 (CP949 제목에도 돈다)", rc == 0, out[-300:])
        svgraw = open(os.path.join(d, "cp_section.svg"), "rb").read()
        jsraw = open(os.path.join(d, "cp_section.json"), "rb").read()
        try:
            svgraw.decode("utf-8"); jsraw.decode("utf-8"); u8 = True
        except UnicodeDecodeError:
            u8 = False
        check("O-2 산출이 **유효한 UTF-8** 이다", u8)
        import xml.etree.ElementTree as ET
        try:
            ET.fromstring(svgraw); xok, xwhy = True, ""
        except Exception as e:
            xok, xwhy = False, str(e)
        check("O-3 ★SVG 가 XML 로 파싱된다 (제목 하나로 그림이 죽지 않는다)", xok, xwhy)
        jc = json.loads(jsraw.decode("utf-8"))
        pc = jc["parts"][0]
        check("O-4 UTF-8 이 아니었다고 **말한다**", pc.get("title_not_utf8") is True, pc)
        check("O-5 원본 바이트를 16진으로 남겨 **복원할 수 있다**",
              bytes.fromhex(pc.get("title_bytes_hex", "")).decode("cp949") == "알루미늄 집전체",
              pc.get("title_bytes_hex"))
        check("O-6 그림이 그 사실을 적는다", "UTF-8 이 아닌" in svgraw.decode("utf-8"),
              [l for l in svgraw.decode("utf-8").splitlines() if "UTF-8" in l][:1])

        # ── P: *PART 카드가 0개인 덱 — 범례가 조용히 비지 않게 ──
        noP = ["*KEYWORD", "*NODE"]
        for i, (x, y, z) in enumerate(nodes2, start=1):
            noP.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
        noP += ["*ELEMENT_SOLID", "%8d%8d" % (1, 7) + "".join("%8d" % v for v in range(1, 9)), "*END"]
        open(os.path.join(d, "nopart.k"), "w", newline="\n").write("\n".join(noP) + "\n")
        write_cfg(os.path.join(d, "np.yaml"), model="nopart.k", output="np", axis="z", at=0.5)
        rc, out = run(binary, d, "np.yaml")
        check("P-1 rc=0", rc == 0, out[-300:])
        jn = load(d, "np")
        check("P-2 *PART 수와 요소가 참조한 PID 수를 **둘 다** 낸다",
              jn["parts_total"] == 0 and jn["parts_referenced_by_elements"] == 1,
              (jn.get("parts_total"), jn.get("parts_referenced_by_elements")))
        check("P-3 둘이 다르면 **경고한다**", "*PART 카드는" in out, out[-300:])
        check("P-4 제목이 없으면 그 까닭을 적는다",
              "*PART 카드가 없다" in (jn["parts"][0].get("thickness_note") or ""),
              jn["parts"][0])

        # ── Q: I10=Y (10칸) 덱 — 고정폭을 가정하지 않는다 ──
        wide = ["*KEYWORD I10=Y", "*NODE"]
        for i, (x, y, z) in enumerate(nodes2, start=1):
            wide.append("%10d%16.9f%16.9f%16.9f" % (i, x, y, z))
        wide += ["*ELEMENT_SOLID", "%10d%10d" % (1, 1) + "".join("%10d" % v for v in range(1, 9)),
                 "*PART", "wide", "%10d%10d%10d" % (1, 1, 1),
                 "*SECTION_SOLID", "%10d%10d" % (1, 1),
                 "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000.0, 0.3), "*END"]
        open(os.path.join(d, "i10.k"), "w", newline="\n").write("\n".join(wide) + "\n")
        write_cfg(os.path.join(d, "iw.yaml"), model="i10.k", output="iw", axis="z", at=0.5)
        rc, out = run(binary, d, "iw.yaml")
        check("Q-1 rc=0", rc == 0, out[-300:])
        ji = load(d, "iw")
        check("Q-2 I10=Y 덱의 단면 면적 = 1 (닫힌식)",
              ji["polygons"] == 1 and near(poly_area(ji["polys"][0]["pts"]), 1.0),
              (ji["polygons"], poly_area(ji["polys"][0]["pts"]) if ji["polygons"] else None))
        # ── R: ★실제 비율(1:9,375) 픽스처 — `flat_stack.k` 로는 축척 결함이 안 잡힌다 ──
        # 실측: 실제 적층은 가로 75 / 최박층 0.008 이다. 그 비율을 가진 픽스처를 따로 만든다.
        LX, TH = 75.0, [0.012, 0.065, 0.020, 0.070, 0.008]
        nodesR, elemsR, nid, idxR = [], [], 1, {}
        zz = [0.0]
        for t in TH:
            zz.append(zz[-1] + t)
        for k, z in enumerate(zz):
            for j_ in (0, 1):
                for i_ in (0, 1):
                    nodesR.append((i_ * LX, j_ * 20.0, z))
                    idxR[(i_, j_, k)] = nid
                    nid += 1
        for k in range(len(TH)):
            c = [idxR[(0,0,k)], idxR[(1,0,k)], idxR[(1,1,k)], idxR[(0,1,k)],
                 idxR[(0,0,k+1)], idxR[(1,0,k+1)], idxR[(1,1,k+1)], idxR[(0,1,k+1)]]
            elemsR.append((k + 1, c))
        deck(os.path.join(d, "thin.k"), nodesR, elemsR, list(range(1, len(TH) + 1)))
        write_cfg(os.path.join(d, "r1.yaml"), model="thin.k", output="r1", axis="y")
        rc, out = run(binary, d, "r1.yaml")
        check("R-1 rc=0", rc == 0, out[-300:])
        jr = load(d, "r1")
        check("R-2 최소피처 = 0.008 (가장 얇은 층)", near(jr["min_feature"], 0.008, 1e-9),
              jr.get("min_feature"))
        ratio = max(jr["extent"]) / jr["min_feature"]
        check("R-3 ★실제 비율을 가진 픽스처다 (1:%d)" % round(ratio), ratio > 5000, ratio)
        check("R-4 비등방 기본이면 그 층이 **보인다** (경고 없음)",
              "1.5 px 미만" not in out, [l for l in out.splitlines() if "px" in l][:2])
        write_cfg(os.path.join(d, "r2.yaml"), model="thin.k", output="r2", axis="y",
                  isotropic="true")
        rc, out2 = run(binary, d, "r2.yaml")
        check("R-5 ★등축으로 강제하면 **보이지 않는다고 말한다**", "1.5 px 미만" in out2,
              [l for l in out2.splitlines() if "px" in l][:2])
        sr = open(os.path.join(d, "r2_section.svg"), encoding="utf-8").read()
        check("R-6 그림 안에도 그 사실을 적는다", "보이지 않는다" in sr,
              [l for l in sr.splitlines() if "px" in l][:1])

        # ── S: ★요소 종류가 **섞인** 덱 — 조사는 순수 HEX8 만 쟀다 ──
        # HEX8 + TET4 + PENTA6 를 한 덱에, z=0.5 로 자른 면적을 각각 닫힌식과 맞춘다.
        mix = ["*KEYWORD", "*NODE"]
        mv = []
        # HEX8 (x 0..1)
        mv += [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)]
        # TET4 (x 2..3) — 꼭짓점 (2,0,0)(3,0,0)(2,1,0)(2,0,1)
        mv += [(2,0,0),(3,0,0),(2,1,0),(2,0,1)]
        # PENTA6 (x 4..5)
        mv += [(4,0,0),(5,0,0),(4,1,0),(4,0,1),(5,0,1),(4,1,1)]
        for i, (x, y, z) in enumerate(mv, start=1):
            mix.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
        mix.append("*ELEMENT_SOLID")
        mix.append("%8d%8d" % (1, 1) + "".join("%8d" % v for v in [1,2,3,4,5,6,7,8]))
        mix.append("%8d%8d" % (2, 2) + "".join("%8d" % v for v in [9,10,11,12,12,12,12,12]))
        mix.append("%8d%8d" % (3, 3) + "".join("%8d" % v for v in [13,14,15,15,16,17,18,18]))
        for pid in (1, 2, 3):
            mix += ["*PART", "mix%d" % pid, "%10d%10d%10d" % (pid, pid, pid),
                    "*SECTION_SOLID", "%10d%10d" % (pid, 1),
                    "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (pid, 7.85e-9, 210000.0, 0.3)]
        mix.append("*END")
        open(os.path.join(d, "mix.k"), "w", newline="\n").write("\n".join(mix) + "\n")
        write_cfg(os.path.join(d, "s1.yaml"), model="mix.k", output="s1", axis="z", at=0.5)
        rc, out = run(binary, d, "s1.yaml")
        check("S-1 rc=0 (섞인 덱)", rc == 0, out[-300:])
        js = load(d, "s1")
        check("S-2 세 요소가 모두 잘렸다", js["polygons"] == 3 and js["parts_hit"] == 3,
              (js["polygons"], js["parts_hit"]))
        byp = {}
        for pl in js["polys"]:
            byp[pl["pid"]] = poly_area(pl["pts"])
        # 닫힌식 — HEX8 1.0 · TET4 (1-0.5)^2/2 = 0.125 · PENTA6 0.5(z 로 일정)
        for pid, want, nm in ((1, 1.0, "HEX8"), (2, 0.125, "TET4"), (3, 0.5, "PENTA6")):
            check("S-3 %s 단면 면적 = %.6g (닫힌식)" % (nm, want),
                  pid in byp and near(byp[pid], want), byp.get(pid))
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
