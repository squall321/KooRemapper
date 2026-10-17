#!/usr/bin/env python3
# 2차 솔리드를 그림 op 이 거절하는지 — 중간절점이 코너로 읽히면 그림이 조용히 71% 틀린다
"""**2차 솔리드를 각 op 이 정직하게 다루나** (2026-10-05 · 2026-10-17 뒤집음).

왜 이 시험이 있나.

  2026-10-16 까지 리더는 `*ELEMENT_SOLID` 노드 칸의 **앞 8개만** 담았다. 그래서 10절점 사면체(ELFORM 16·17)는
  중간절점 넷이 코너 자리(n5..n8)로 들어온 육면체가 됐고, 증상이 조용했다 —
    · KooRemapper **자신의** `convert type: tet10` 덱의 단면 총면적이 0.665 → **0.19**(오차 71%) · 다각형 수는 같았다.
    · 자유면이 6면/삼각형 12개(TET4 참값 4면/4개) · 고아 0 인데 2 · 코너 부피가 양수인데 「음의 야코비안 2」.
  그래서 그림 셋은 거절했고 modelmeta 는 null 을 냈다(이 시험이 그 거절을 지켰다).

  ★2026-10-17 — 리더가 절점 칸을 **다** 읽고 코너를 제자리에 놓는다(TET10 은 N1..N4 · 매뉴얼 Fig 19-31). 이제 이 시험은
  **값이 맞는지**를 지킨다 — 같은 기하의 1차 덱과 단면 총면적 · 부피 · 고아 · 야코비안이 같아야 한다.

  거절이 남는 자리도 함께 지킨다.
    · 코너 차례를 매뉴얼 본문이 적지 않은 ELFORM(25·26·27·28 — 「그림을 보라」뿐 · Remark 16 「개발 중」) — 짐작해 그리지 않는다.
    · 절점 칸이 모자란 2차 카드(노드를 8+2 로 쪼갠 덱 · 옛 한 줄 꼴) — 매뉴얼 Card 2 는 N1..N10 한 장이다. 8+2 덱은 둘째
      줄이 다음 요소의 Card 1 로 읽혀 **요소가 사라진다**(LS-DYNA 도 그렇게 읽는다 — 실측 둘 → 하나).

  거짓 거절도 막는다 — 20절점 **육면체**(ELFORM 23)는 코너가 앞 8칸이라 예전부터 맞게 읽혔다(1차 원본과 단면이
  120 다각형·총면적 4.712178200 으로 **같다**).

usage: test_secondorder_solid.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []
OPS = ("section", "surfview", "stackdiagram")


def check(name, cond, detail=""):
    print("  %-64s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], capture_output=True, text=True, timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n") as f:
        f.write(text)


def tet4_deck(path, elform=10):
    """TET4 둘 — LS-DYNA 관례(n5..n8 = n4)로 적은 축퇴 육면체."""
    pts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)]
    els = [[1, 2, 3, 4], [2, 3, 4, 5]]
    L = ["*KEYWORD", "*NODE"]
    for i, (x, y, z) in enumerate(pts, 1):
        L.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
    L.append("*ELEMENT_SOLID")
    for e, c in enumerate(els, 1):
        L.append("%8d%8d" % (e, 1) + "".join("%8d" % v for v in c + [c[3]] * 4))
    L += ["*PART", "tets", "%10d%10d%10d" % (1, 1, 1),
          "*SECTION_SOLID", "%10d%10d" % (1, elform),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
    write(path, "\n".join(L) + "\n")


def tet10_two_line(path, split_8_2=True):
    """10절점 사면체 둘.

    `split_8_2=False` 가 **표준**이다 — `eid pid` 카드 뒤에 노드 10칸이 **한 줄**로 온다.
    그 꼴에서는 요소 수가 맞고 **기하만** 틀린다.
    `split_8_2=True` 는 노드를 8+2 로 쪼갠 덱이다 — 둘째 줄이 다음 요소의 카드 1 로 읽혀
    **요소가 사라진다**(실측 둘 → 하나). 두 꼴을 모두 거절해야 한다."""
    corners = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)]
    nodes = list(corners)

    def nid(p):
        if p not in nodes:
            nodes.append(p)
        return nodes.index(p) + 1

    def mid(a, b):
        return tuple((a[k] + b[k]) / 2 for k in range(3))

    els = []
    for cs in ([0, 1, 2, 3], [1, 2, 3, 4]):
        c = [corners[i] for i in cs]
        ten = [nid(c[0]), nid(c[1]), nid(c[2]), nid(c[3])]
        for a, b in ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)):
            ten.append(nid(mid(c[a], c[b])))
        els.append(ten)
    L = ["*KEYWORD", "*NODE"]
    for i, (x, y, z) in enumerate(nodes, 1):
        L.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
    L.append("*ELEMENT_SOLID (ten nodes format)")
    for e, ten in enumerate(els, 1):
        L.append("%8d%8d" % (e, 1))
        if split_8_2:
            L.append("".join("%8d" % n for n in ten[:8]))
            L.append("".join("%8d" % n for n in ten[8:]))
        else:
            L.append("".join("%8d" % n for n in ten))      # 표준 — 10칸 한 줄
    L += ["*PART", "tet10x2", "%10d%10d%10d" % (1, 1, 1),
          "*SECTION_SOLID", "%10d%10d" % (1, 16),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
    write(path, "\n".join(L) + "\n")


def section_total_area(path):
    d = json.load(open(path, encoding="utf-8"))

    def a(p):
        return abs(sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1]
                       for i in range(len(p)))) / 2
    return len(d["polys"]), sum(a(p["pts"]) for p in d["polys"])


def main():
    if len(sys.argv) < 2:
        print("usage: test_secondorder_solid.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    flat = os.path.join(repo, "examples", "stackwrap", "flat_stack.k")

    d = tempfile.mkdtemp(prefix="so2_")
    try:
        # ── A: 1차 TET4 는 세 op 이 다 그린다 (거짓 거절이 없어야 한다) ──
        tet4_deck(os.path.join(d, "lin.k"))
        for op in OPS:
            write(os.path.join(d, "a.yaml"), "model: lin.k\noutput: a_%s\n" % op)
            rc, out = run(binary, d, op, "a.yaml")
            check("A-1 1차 TET4 를 %s 가 그린다 (거짓 거절 없음)" % op, rc == 0, out[-250:])

        # ── B: ★convert 가 만든 ELFORM 17 덱을 세 op 이 **코너로 그린다**(2026-10-17 — 예전에는 거절) ──
        write(os.path.join(d, "cv.yaml"),
              "base_model: lin.k\noutput: t10\noperations:\n  - type: tet10\n")
        rc, out = run(binary, d, "convert", "cv.yaml")
        check("B-1 convert type: tet10 이 ELFORM 17 로 바꾼다", rc == 0 and "ELFORM -> 17" in out,
              out[-250:])
        for op in OPS:
            write(os.path.join(d, "b.yaml"), "model: t10.k\noutput: b_%s\naxis: z\nat: 0.3\n" % op)
            rc, out = run(binary, d, op, "b.yaml")
            check("B-2 %s 가 TET10 을 그린다(rc 0 · 거절하지 않는다)" % op, rc == 0 and "믿을 수 없는" not in out, out[-250:])
            check("B-3 %s 가 「코너로 그린다」고 PID·ELFORM 과 함께 말한다" % op,
                  "코너로 그린다" in out and "ELFORM 17" in out, out[-300:])
        for op, suffix in (("section", "_section.svg"), ("surfview", "_surface.svg"),
                           ("stackdiagram", "_stackdiagram.svg")):
            check("B-5 %s 가 그림을 쓴다" % op, os.path.exists(os.path.join(d, "b_%s%s" % (op, suffix))))
        write(os.path.join(d, "s0.yaml"), "model: lin.k\noutput: s0\naxis: z\nat: 0.3\n")
        rc, _ = run(binary, d, "section", "s0.yaml")
        if rc == 0:
            n0, a0 = section_total_area(os.path.join(d, "s0_section.json"))
            check("B-6 1차 원본 단면: 2 다각형 · 총면적 0.665", n0 == 2 and abs(a0 - 0.665) < 1e-9,
                  (n0, a0))
            try:
                n1, a1 = section_total_area(os.path.join(d, "b_section_section.json"))
                check("B-7 ★TET10 단면이 1차 원본과 **같다**(예전 0.19 — 오차 71%)",
                      n1 == n0 and abs(a1 - a0) < 1e-9, ((n0, a0), (n1, a1)))
            except (OSError, KeyError, ValueError) as e:
                check("B-7 TET10 단면 매니페스트를 읽었다", False, str(e))
        rc, out = run(binary, d, "surfview", "b.yaml")
        drawn = [l for l in out.splitlines() if l.strip().startswith("Triangles drawn")]
        check("B-8 ★자유면 삼각형이 6개다(사면체 둘이 한 면을 나눈다 · 예전 12)",
              bool(drawn) and drawn[0].split()[-1] == "6", drawn[:1])

        # ── C: ★두 줄 카드 TET10 — 요소가 사라지는 쪽도 거절한다 ──
        tet10_two_line(os.path.join(d, "two.k"))
        for op in OPS:
            write(os.path.join(d, "c.yaml"), "model: two.k\noutput: c_%s\n" % op)
            rc, out = run(binary, d, op, "c.yaml")
            check("C-1 %s 가 노드를 8+2 로 쪼갠 TET10(ELFORM 16)을 거절한다" % op, rc == 1, out[-250:])
            check("C-2 %s 가 ELFORM 16 과 「칸이 모자란」 까닭을 댄다" % op,
                  "ELFORM 16" in out and "모자란" in out, out[-250:])
        rc, out = run(binary, d, "info", "two.k")
        check("C-3 (근거) 노드를 8+2 로 쪼갠 덱은 TET10 둘을 **하나**로 읽는다",
              "Elements:" in out and [l for l in out.splitlines()
                                      if l.strip().startswith("Elements:")][0].split()[-1] == "1",
              [l for l in out.splitlines() if "Elements:" in l][:1])

        # ── C': ★표준 레이아웃(노드 10칸 한 줄) — 요소는 **안 잃지만** 그래도 거절한다 ──
        tet10_two_line(os.path.join(d, "std.k"), split_8_2=False)
        rc, out = run(binary, d, "info", "std.k")
        got = [l for l in out.splitlines() if l.strip().startswith("Elements:")]
        check("C'-1 ★표준 레이아웃은 요소를 **잃지 않는다**(둘 그대로) — 기하만 틀린다",
              bool(got) and got[0].split()[-1] == "2", got[:1])
        for op in OPS:
            write(os.path.join(d, "cs.yaml"), "model: std.k\noutput: cs_%s\naxis: z\nat: 0.3\n" % op)
            rc, out = run(binary, d, op, "cs.yaml")
            check("C'-2 %s 는 표준 레이아웃 TET10 을 코너로 그린다" % op,
                  rc == 0 and "코너로 그린다" in out, out[-250:])
        try:
            n2, a2 = section_total_area(os.path.join(d, "cs_section_section.json"))
            check("C'-3 ★표준 레이아웃 TET10 단면도 1차와 같다(2 다각형 · 0.665)",
                  n2 == 2 and abs(a2 - 0.665) < 1e-9, (n2, a2))
        except (OSError, KeyError, ValueError) as e:
            check("C'-3 단면 매니페스트를 읽었다", False, str(e))

        # ── D: ★ELFORM 23(HEX20)은 거절하지 않고, 1차와 **같은** 단면을 낸다 ──
        if os.path.exists(flat):
            shutil.copy(flat, os.path.join(d, "flat.k"))
            write(os.path.join(d, "cv2.yaml"),
                  "base_model: flat.k\noutput: h20\noperations:\n  - type: hex20\n")
            rc, out = run(binary, d, "convert", "cv2.yaml")
            check("D-1 convert type: hex20 이 ELFORM 23 으로 바꾼다",
                  rc == 0 and "ELFORM -> 23" in out, out[-250:])
            for op in OPS:
                write(os.path.join(d, "dd.yaml"), "model: h20.k\noutput: d_%s\naxis: z\n" % op)
                rc, out = run(binary, d, op, "dd.yaml")
                check("D-2 %s 가 HEX20 을 **거절하지 않는다**" % op,
                      rc == 0 and "믿을 수 없는" not in out and "코너로 그린다" in out, out[-250:])
            write(os.path.join(d, "e1.yaml"), "model: flat.k\noutput: e1\naxis: z\nat: 0.3\n")
            write(os.path.join(d, "e2.yaml"), "model: h20.k\noutput: e2\naxis: z\nat: 0.3\n")
            run(binary, d, "section", "e1.yaml")
            run(binary, d, "section", "e2.yaml")
            try:
                n1, a1 = section_total_area(os.path.join(d, "e1_section.json"))
                n2, a2 = section_total_area(os.path.join(d, "e2_section.json"))
                check("D-3 ★HEX20 단면이 1차 원본과 **완전히 같다** (거절하지 않는 근거)",
                      n1 == n2 and abs(a1 - a2) < 1e-12, ((n1, a1), (n2, a2)))
                check("D-4 그 값이 120 다각형 · 총면적 4.712178200",
                      n1 == 120 and abs(a1 - 4.7121782) < 1e-6, (n1, a1))
            except (OSError, KeyError, ValueError) as e:
                check("D-3 두 단면 매니페스트를 읽었다", False, str(e))
        else:
            print("  (D 건너뜀 — examples/stackwrap/flat_stack.k 가 없다)")

        # ── E: ★`restack` 이 **정확한 까닭**으로 거절한다 ──
        #    ELFORM 16·17 이 `solidNodesFromElform` 표에 없어서 `0`(모름)으로 떨어졌고, 그래서
        #    고차 거절 문턱(`> 10`)을 지나 뒤에서 "유효한 압출이 아니다" 라는 **엉뚱한 까닭**으로
        #    멈췄다. 사유는 "요소마다 8 절점만 담는다" 이고 그것은 10절점 사면체에도 그대로다.
        write(os.path.join(d, "rs.yaml"),
              "base_model: std.k\noutput: rsout\noperations:\n  - type: restack\n"
              "    target_pid: 1\n    layers:\n      - title: L1\n        thickness: 0.5\n"
              "        num_elements: 1\n        material_card: |\n"
              "          *MAT_ELASTIC_TITLE\n          L1\n"
              "          $#     mid        ro         e        pr\n"
              "                  90  7.85e-09   2.1e+05      0.30\n")
        rc, out = run(binary, d, "restack", "rs.yaml")
        check("E-1 restack 이 TET10 파트를 rc=1 로 거절한다", rc == 1, out[-250:])
        check("E-2 ★'10 절점 고차 요소 파트' 라고 **정확한** 까닭을 댄다",
              "10 절점 고차 요소 파트" in out, out[-300:])
        check("E-3 '유효한 압출이 아니다' 라는 엉뚱한 까닭을 대지 않는다",
              "valid extrusion" not in out and "압출" not in out, out[-300:])
        check("E-4 틀린 덱을 내지 않는다", not os.path.exists(os.path.join(d, "rsout.k")))

        # ── F: ★`modelmeta` 는 거절하지 않지만 **틀렸다고 적어야** 한다 ──────────
        # 그림 셋은 거절한다. `modelmeta` 는 인벤토리라 거절하면 TET10 덱의 메타 경로를
        # 통째로 막는다 — 그래서 값을 내되 **쓰지 말라고 적는다**. 적지 않으면 소비자가
        # 부피를 그대로 읽고, 그 부피는 실측 -48.4% 다. (④ 에서 신호가 플랫폼까지 끊겨
        # 있었던 것과 같은 자리라서, 파트별 플래그도 함께 둔다.)
        import json as _json
        tet4_deck(os.path.join(d, "mm_lin.k"))
        tet4_deck(os.path.join(d, "mm_2nd.k"), elform=16)
        for tag, model, want in (("1차", "mm_lin.k", False), ("2차(ELFORM 16)", "mm_2nd.k", True)):
            write(os.path.join(d, "mm.yaml"),
                  "model: %s\noutput: mm_%s\n" % (model, "2" if want else "1"))
            rc, out = run(binary, d, "modelmeta", "mm.yaml")
            jp = os.path.join(d, "mm_%s_modelmeta.json" % ("2" if want else "1"))
            ok = (rc == 0 and os.path.exists(jp))
            md = _json.load(open(jp)) if ok else {}
            check("F-1 %s 덱에서 modelmeta 가 돈다 (거절하지 않는다)" % tag, ok, out[-250:])
            if not ok:
                continue
            pids = md["model"].get("second_order_solid_pids")
            check("F-2 %s — model.second_order_solid_pids 가 %s" % (tag, "있다" if want else "비었다"),
                  isinstance(pids, list) and (len(pids) == 1) == want, pids)
            check("F-3 %s — 파트에도 second_order 플래그가 붙는다 (파트만 읽는 소비자가 본다)" % tag,
                  md["parts"] and md["parts"][0].get("second_order") is want,
                  md["parts"][0].get("second_order") if md["parts"] else None)
            # 이 덱은 옛 한 줄 꼴(EID PID N1..N8)에 ELFORM 16 이다 — 그 꼴은 4-8절점만 받으므로 칸이 모자란 2차 카드다
            check("F-4 %s — 콘솔이 %s" % (tag, "경고한다(칸이 모자란 2차 카드)" if want else "조용하다"),
                  ("모자란 2차 요소" in out) is want, out[-250:])
            if want:
                check("F-5 ELFORM 을 수로 적는다 (어느 파트가 왜인지 보인다)",
                      pids[0].get("elform") == 16 and pids[0].get("pid") == 1, pids)
                check("F-6 conventions 가 「코너로 잰 값」과 null 이 되는 자리를 적는다",
                      "코너로 잰 값" in md["conventions"].get("second_order", "") and
                      "모자란" in md["conventions"].get("second_order", ""),
                      md["conventions"].get("second_order"))
                check("F-6b 그 파트의 geometry_basis 는 null 이다(기하를 믿을 수 없다)",
                      md["parts"][0].get("geometry_basis", "없음") is None and
                      pids[0].get("geometry_basis", "없음") is None, (md["parts"][0].get("geometry_basis", "없음"), pids))
            # ★틀린 줄 아는 값은 숫자로 내지 않는다(2026-10-16) — 플래그를 안 읽는 소비자
            #   (DataHub 적재 · 리스크 앱 어댑터)가 그 부피를 그대로 실었다. null + 까닭이다.
            p0 = md["parts"][0]
            geo = ("volume", "area_ext", "proj", "edge_len", "n_node", "mass")
            if want:
                check("F-7 ★2차 — 기하 여섯 칸이 null 이다 (틀린 숫자를 내지 않는다)",
                      all(p0.get(k, "없음") is None for k in geo), {k: p0.get(k, "없음") for k in geo})
                check("F-8 2차 — geometry_reason·mass_reason 이 ELFORM 과 함께 까닭을 댄다",
                      "ELFORM 16" in (p0.get("geometry_reason") or "") and
                      "ELFORM 16" in (p0.get("mass_reason") or "") and p0.get("mass_basis") is None,
                      (p0.get("geometry_reason"), p0.get("mass_reason"), p0.get("mass_basis")))
                check("F-9 2차 — 맞는 칸(n_elems·bbox)은 그대로 낸다",
                      p0.get("n_elems") == 2 and p0.get("bbox_min") == [0, 0, 0] and
                      p0.get("bbox_max") == [1, 1, 1], (p0.get("n_elems"), p0.get("bbox_min")))
                check("F-10 2차지만 센 고아가 0 이면 0 은 참이라 그대로 낸다",
                      md["model"].get("orphan_nodes") == 0 and
                      md["model"].get("orphan_nodes_reason") is None,
                      (md["model"].get("orphan_nodes"), md["model"].get("orphan_nodes_reason")))
            else:
                check("F-7 1차 — 기하 여섯 칸이 숫자다 · geometry_reason 은 null",
                      all(isinstance(p0.get(k), (int, float, dict)) for k in geo) and
                      p0.get("geometry_reason", "없음") is None,
                      {k: p0.get(k, "없음") for k in geo + ("geometry_reason",)})

        # ── G: ★매뉴얼 꼴 TET10 — 중간절점까지 세어 고아·n_node 가 **정확**하고, 기하는 코너로 잰다 ──────────
        # 예전 리더는 n9·n10 을 못 봐 고아 2 · n_node 12 로 셌다(참값 고아 0 · 절점 14) — 그래서 null 로 냈다.
        tet10_two_line(os.path.join(d, "mm_t10.k"), split_8_2=False)
        write(os.path.join(d, "mm.yaml"), "model: mm_t10.k\noutput: mm_t10\n")
        rc, out = run(binary, d, "modelmeta", "mm.yaml")
        jp = os.path.join(d, "mm_t10_modelmeta.json")
        md = _json.load(open(jp)) if rc == 0 and os.path.exists(jp) else {}
        m = md.get("model", {})
        p0 = (md.get("parts") or [{}])[0]
        check("G-1 ★TET10 덱의 고아 수가 0 이다(중간절점까지 센다 · 예전 거짓 2)",
              m.get("orphan_nodes") == 0 and m.get("orphan_nodes_reason", "없음") is None,
              (m.get("orphan_nodes", "없음"), m.get("orphan_nodes_reason", "없음")))
        check("G-2 2차 파트 목록에 geometry_basis = corners 로 실린다",
              m.get("second_order_solid_pids") == [{"pid": 1, "elform": 16, "geometry_basis": "corners"}],
              m.get("second_order_solid_pids"))
        check("G-3 ★TET10 의 n_node 가 14 다(참값 · 예전 12)", p0.get("n_node") == 14, p0.get("n_node", "없음"))
        check("G-4 ★second_order · geometry_basis = corners · 부피 = 1차와 같은 0.5",
              p0.get("second_order") is True and p0.get("geometry_basis") == "corners" and
              isinstance(p0.get("volume"), (int, float)) and abs(p0["volume"] - 0.5) < 1e-6,
              (p0.get("second_order"), p0.get("geometry_basis"), p0.get("volume")))
        check("G-5 질량이 부피×밀도로 나온다(mass_basis volume*rho)",
              p0.get("mass_basis") == "volume*rho" and isinstance(p0.get("mass"), (int, float)),
              (p0.get("mass"), p0.get("mass_basis"), p0.get("mass_reason")))
        check("G-6 모서리 길이 — 단위 사면체 둘이라 1 .. √2",
              isinstance(p0.get("edge_len"), dict) and abs(p0["edge_len"]["min"] - 1) < 1e-5 and
              abs(p0["edge_len"]["max"] - 2 ** 0.5) < 1e-5, p0.get("edge_len"))
        # ★모서리 표는 위상 정본(사면체 6모서리)이다 — 예전 육면체 12모서리 사본은 TET4 꼴에서 n1–n3 을 **빠뜨렸다**.
        #   가장 긴 모서리가 n1–n3(10.0)인 사면체로 잰다 — 1차(ELFORM 10)와 2차(ELFORM 16) 둘 다(예전 1차 값 9.055).
        corners = [(0, 0, 0), (1, 1, 0), (10, 0, 0), (1, 0, 1)]
        for ef, tag in ((10, "1차"), (16, "2차")):
            nodes = list(corners)
            ids = [1, 2, 3, 4]
            if ef == 16:
                for a, b in ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)):
                    nodes.append(tuple((corners[a][k] + corners[b][k]) / 2 for k in range(3)))
                ids = list(range(1, 11))
            L = ["*KEYWORD", "*NODE"] + ["%8d%16.9f%16.9f%16.9f" % (i + 1, *q) for i, q in enumerate(nodes)]
            L += ["*ELEMENT_SOLID"]
            if ef == 16:
                L += ["%8d%8d" % (1, 1), "".join("%8d" % n for n in ids)]
            else:
                L += ["%8d%8d" % (1, 1) + "".join("%8d" % n for n in [1, 2, 3, 4, 4, 4, 4, 4])]
            L += ["*PART", "t", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, ef),
                  "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
            write(os.path.join(d, "long13_%d.k" % ef), "\n".join(L) + "\n")
            write(os.path.join(d, "mm.yaml"), "model: long13_%d.k\noutput: mm_l13_%d\n" % (ef, ef))
            rc, out = run(binary, d, "modelmeta", "mm.yaml")
            jp = os.path.join(d, "mm_l13_%d_modelmeta.json" % ef)
            el = ((_json.load(open(jp)) if rc == 0 and os.path.exists(jp) else {}).get("parts") or [{}])[0].get("edge_len")
            check("G-6b ★%s 사면체 — 가장 긴 모서리 n1–n3 = 10.0 을 잰다(예전 9.055)" % tag,
                  isinstance(el, dict) and abs(el["max"] - 10.0) < 1e-5, el)
        tet4_deck(os.path.join(d, "mm_lin2.k"))
        write(os.path.join(d, "mm.yaml"), "model: mm_lin2.k\noutput: mm_lin2\n")
        rc, out = run(binary, d, "modelmeta", "mm.yaml")
        jp = os.path.join(d, "mm_lin2_modelmeta.json")
        m = (_json.load(open(jp)) if rc == 0 and os.path.exists(jp) else {}).get("model", {})
        check("G-7 1차 덱의 고아 수는 숫자이고 사유는 null",
              m.get("orphan_nodes") == 0 and m.get("orphan_nodes_reason", "없음") is None,
              (m.get("orphan_nodes"), m.get("orphan_nodes_reason", "없음")))

        # ── H: ★`info` — 고아는 중간절점까지 세어 정확하고, 야코비안은 코너로 잰다 ──
        # 예전에는 매뉴얼 꼴 TET10 둘이 코너 부피가 둘 다 양수인데 「Negative Jacobian elements: 2」, 고아 0 인데
        # 「Orphan nodes: 2」 였다(실측). 판정은 그림 셋 · modelmeta 와 같은 함수다.
        tet10_two_line(os.path.join(d, "info_t10.k"), split_8_2=False)
        tet4_deck(os.path.join(d, "info_lin.k"))
        rc, out = run(binary, d, "info", "info_t10.k")
        check("H-1 info 가 TET10 을 「코너로」 잰다고 말한다", rc == 0 and "코너로 그린다" in out and "믿을 수 없는" not in out,
              out[-300:])
        orph = [l for l in out.splitlines() if l.startswith("Orphan nodes")]
        check("H-2 ★고아 줄이 없다(고아 0 — 예전 거짓 2)", not orph, orph)
        jl = {l.split(":")[0].strip(): l.split(":")[1].strip() for l in out.splitlines()
              if l.startswith(("Min Jacobian", "Max Jacobian"))}
        check("H-3 ★야코비안을 코너로 잰다 — 6V = 1 · 2(예전 거짓 「음수 2」)",
              "Negative Jacobian" not in out and abs(float(jl.get("Min Jacobian", "nan")) - 1.0) < 1e-9 and
              abs(float(jl.get("Max Jacobian", "nan")) - 2.0) < 1e-9, jl)
        rc, out = run(binary, d, "info", "info_lin.k")
        check("H-4 1차 덱에서는 경고·표시가 없고 야코비안을 잰다",
              rc == 0 and "2차 솔리드" not in out and "Min Jacobian" in out, out[-300:])
        # ── I: ★코너 차례를 모르는 ELFORM 26(15절점 사면체)은 거절한다 — 그러나 절점은 다 센다 ──
        L = ["*KEYWORD", "*NODE"]
        for i in range(1, 16):
            L.append("%8d%16.9f%16.9f%16.9f" % (i, (i % 4) * 0.25, (i % 3) * 0.3, (i // 5) * 0.2))
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1), "".join("%8d" % n for n in range(1, 11)),
              "".join("%8d" % n for n in range(11, 16)),
              "*PART", "t15", "%10d%10d%10d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 26),
              "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
        write(os.path.join(d, "t15.k"), "\n".join(L) + "\n")
        for op in OPS:
            write(os.path.join(d, "i.yaml"), "model: t15.k\noutput: i_%s\naxis: z\nat: 0.1\n" % op)
            rc, out = run(binary, d, op, "i.yaml")
            check("I-1 %s 가 ELFORM 26 을 거절한다(코너 차례가 매뉴얼 본문에 없다)" % op,
                  rc == 1 and "ELFORM 26" in out and "코너 차례" in out, out[-250:])
        write(os.path.join(d, "mm.yaml"), "model: t15.k\noutput: mm_t15\n")
        rc, out = run(binary, d, "modelmeta", "mm.yaml")
        jp = os.path.join(d, "mm_t15_modelmeta.json")
        md = _json.load(open(jp)) if rc == 0 and os.path.exists(jp) else {}
        p0 = (md.get("parts") or [{}])[0]
        check("I-2 modelmeta — 기하는 null · geometry_basis null · n_node 15(절점은 다 센다) · 고아 0",
              p0.get("volume", "없음") is None and p0.get("geometry_basis", "없음") is None and
              p0.get("n_node") == 15 and md.get("model", {}).get("orphan_nodes") == 0,
              (p0.get("volume", "없음"), p0.get("geometry_basis", "없음"), p0.get("n_node"),
               md.get("model", {}).get("orphan_nodes")))
        rc, out = run(binary, d, "info", "t15.k")
        els = [l for l in out.splitlines() if l.strip().startswith("Elements:")]
        check("I-3 info — 요소 1 (두 카드를 한 요소로 읽는다) · 고아 줄 없음",
              els and els[0].split()[-1] == "1" and not [l for l in out.splitlines() if l.startswith("Orphan nodes")],
              (els, [l for l in out.splitlines() if l.startswith("Orphan")]))
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
