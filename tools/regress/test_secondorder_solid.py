#!/usr/bin/env python3
# 2차 솔리드를 그림 op 이 거절하는지 — 중간절점이 코너로 읽히면 그림이 조용히 71% 틀린다
"""**2차 솔리드를 각 op 이 정직하게 다루나** (2026-10-05).

왜 이 시험이 있나.

  리더는 `*ELEMENT_SOLID` 노드 칸의 **앞 8개만** 저장하고 TET4/PENTA6 만 판정한다. 그래서
  10절점 사면체(ELFORM 16·17)는 **중간절점 넷이 코너 자리(n5..n8)로** 들어온 육면체가 된다.
  `case ElementType::TET10` 이 `section.cpp`·`surfview.cpp` 에 있지만 **그 타입을 아무도
  대입하지 않아서** 죽은 코드였다.

  증상이 조용하다. 이것이 이 시험의 요지다.

    · 같은 기하를 KooRemapper **자신의** `convert type: tet10` 으로 바꾸면 단면 총면적이
      0.665 → **0.19** 가 된다(오차 71%). **다각형 수는 둘 다 2개**라 알아볼 수가 없다.
    · 자유면이 6면/삼각형 12개로 나온다(TET4 참값 4면/4개).
    · 표준 레이아웃(`eid pid` + 노드 10칸 **한 줄**)에서는 요소 수는 맞고 **기하만** 틀린다.
      노드를 **8+2 로 쪼갠** 덱은 둘째 줄을 다음 요소의 카드 1 로 읽어 **요소가 사라진다** —
      실측으로 TET10 둘이 하나로 읽혔다. 두 레이아웃을 모두 거절해야 한다.

  그림이 조용히 거짓이 되는 것을 막는 것이 이 캠페인의 원칙이므로 세 op 이 **거절한다.**

  ★거짓 거절도 막아야 한다. 20절점 **육면체**(ELFORM 23)는 코너가 앞 8칸이라 **맞게 읽힌다** —
  실측으로 1차 원본과 단면이 120 다각형·총면적 4.712178200 으로 **완전히 같다.** 그것을
  거절하면 쓸 수 있는 덱을 막는 것이다. 그래서 이 시험은 거절과 **비거절**을 함께 지킨다.

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

        # ── B: ★convert 가 만든 ELFORM 17 덱을 세 op 이 **거절**한다 ──
        write(os.path.join(d, "cv.yaml"),
              "base_model: lin.k\noutput: t10\noperations:\n  - type: tet10\n")
        rc, out = run(binary, d, "convert", "cv.yaml")
        check("B-1 convert type: tet10 이 ELFORM 17 로 바꾼다", rc == 0 and "ELFORM -> 17" in out,
              out[-250:])
        for op in OPS:
            write(os.path.join(d, "b.yaml"), "model: t10.k\noutput: b_%s\n" % op)
            rc, out = run(binary, d, op, "b.yaml")
            check("B-2 %s 가 2차 솔리드를 rc=1 로 거절한다" % op, rc == 1, out[-250:])
            check("B-3 %s 가 '2차 솔리드' 와 PID·ELFORM 을 말한다" % op,
                  "2차 솔리드" in out and "ELFORM 17" in out, out[-300:])
            check("B-4 %s 가 1차 덱을 쓰라고 안내한다" % op, "1차 요소 덱" in out, out[-300:])
        for op, suffix in (("section", "_section.svg"), ("surfview", "_surface.svg"),
                           ("stackdiagram", "_stackdiagram.svg")):
            check("B-5 %s 가 거절하면서 그림을 쓰지 않는다" % op,
                  not os.path.exists(os.path.join(d, "b_%s%s" % (op, suffix))))
        # ★거절이 왜 필요한가 — 거절이 없으면 얼마나 틀리나를 이 시험이 **직접 보여준다**
        write(os.path.join(d, "s0.yaml"), "model: lin.k\noutput: s0\naxis: z\nat: 0.3\n")
        rc, _ = run(binary, d, "section", "s0.yaml")
        if rc == 0:
            n0, a0 = section_total_area(os.path.join(d, "s0_section.json"))
            check("B-6 1차 원본 단면: 2 다각형 · 총면적 0.665", n0 == 2 and abs(a0 - 0.665) < 1e-9,
                  (n0, a0))

        # ── C: ★두 줄 카드 TET10 — 요소가 사라지는 쪽도 거절한다 ──
        tet10_two_line(os.path.join(d, "two.k"))
        for op in OPS:
            write(os.path.join(d, "c.yaml"), "model: two.k\noutput: c_%s\n" % op)
            rc, out = run(binary, d, op, "c.yaml")
            check("C-1 %s 가 두 줄 카드 TET10(ELFORM 16)도 거절한다" % op, rc == 1, out[-250:])
            check("C-2 %s 가 ELFORM 16 을 지목한다" % op, "ELFORM 16" in out, out[-250:])
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
            write(os.path.join(d, "cs.yaml"), "model: std.k\noutput: cs_%s\n" % op)
            rc, out = run(binary, d, op, "cs.yaml")
            check("C'-2 %s 는 요소를 안 잃는 꼴도 거절한다 (기하가 틀리므로)" % op,
                  rc == 1 and "2차 솔리드" in out, out[-250:])

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
                      rc == 0 and "2차 솔리드" not in out, out[-250:])
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
            check("F-4 %s — 콘솔이 %s" % (tag, "경고한다" if want else "조용하다"),
                  ("코너 8개만" in out) is want, out[-250:])
            if want:
                check("F-5 ELFORM 을 수로 적는다 (어느 파트가 왜인지 보인다)",
                      pids[0].get("elform") == 16 and pids[0].get("pid") == 1, pids)
                check("F-6 conventions 가 '쓰지 말라' 고 적는다",
                      "쓰지 말라" in md["conventions"].get("second_order", ""),
                      md["conventions"].get("second_order"))
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

        # ── G: ★매뉴얼 꼴 TET10 — 잘라 읽기가 중간절점을 **거짓 고아**로 만든다 ──────────
        # 참값은 절점 14 · 고아 0 인데 n9·n10 을 못 봐 고아 2 로 셌다(실측). 센 값은 상한일 뿐이다.
        tet10_two_line(os.path.join(d, "mm_t10.k"), split_8_2=False)
        write(os.path.join(d, "mm.yaml"), "model: mm_t10.k\noutput: mm_t10\n")
        rc, out = run(binary, d, "modelmeta", "mm.yaml")
        jp = os.path.join(d, "mm_t10_modelmeta.json")
        md = _json.load(open(jp)) if rc == 0 and os.path.exists(jp) else {}
        m = md.get("model", {})
        check("G-1 TET10 덱에서 고아 수를 null 로 낸다 (거짓 고아 2 를 숫자로 내지 않는다)",
              "orphan_nodes" in m and m["orphan_nodes"] is None, m.get("orphan_nodes", "없음"))
        check("G-2 고아 사유가 상한과 센 값을 적는다",
              "상한" in (m.get("orphan_nodes_reason") or "") and "2개" in (m.get("orphan_nodes_reason") or ""),
              m.get("orphan_nodes_reason"))
        check("G-3 TET10 의 n_node 를 null 로 낸다 (12 는 틀렸다 — 참값 14)",
              md.get("parts") and md["parts"][0].get("n_node", "없음") is None,
              md["parts"][0].get("n_node", "없음") if md.get("parts") else md)
        tet4_deck(os.path.join(d, "mm_lin2.k"))
        write(os.path.join(d, "mm.yaml"), "model: mm_lin2.k\noutput: mm_lin2\n")
        rc, out = run(binary, d, "modelmeta", "mm.yaml")
        jp = os.path.join(d, "mm_lin2_modelmeta.json")
        m = (_json.load(open(jp)) if rc == 0 and os.path.exists(jp) else {}).get("model", {})
        check("G-4 1차 덱의 고아 수는 숫자이고 사유는 null",
              m.get("orphan_nodes") == 0 and m.get("orphan_nodes_reason", "없음") is None,
              (m.get("orphan_nodes"), m.get("orphan_nodes_reason", "없음")))

        # ── H: ★`info` 도 같은 뿌리다 — 거짓 고아와 거짓 「음의 야코비안」을 말없이 냈다 ──
        # 매뉴얼 꼴 TET10 둘은 코너 부피가 둘 다 양수인데 「Negative Jacobian elements: 2」,
        # 고아 0 인데 「Orphan nodes: 2」 였다(실측). 판정은 같은 함수다.
        tet10_two_line(os.path.join(d, "info_t10.k"), split_8_2=False)
        tet4_deck(os.path.join(d, "info_lin.k"))
        rc, out = run(binary, d, "info", "info_t10.k")
        check("H-1 info 가 TET10 덱에서 2차 솔리드라고 경고한다", rc == 0 and "**2차 솔리드**" in out, out[-300:])
        orph = [l for l in out.splitlines() if l.startswith("Orphan nodes")]
        check("H-2 고아 줄에 '상한' 을 단다 (2 는 참값이 아니다)", orph and "상한" in orph[0], orph)
        check("H-3 ★2차 솔리드의 야코비안을 재지 않는다 — 거짓 '음수' 를 내지 않는다",
              "Negative Jacobian" not in out and "2차 솔리드 2개" in out,
              [l for l in out.splitlines() if "Jacobian" in l])
        rc, out = run(binary, d, "info", "info_lin.k")
        check("H-4 1차 덱에서는 경고·표시가 없고 야코비안을 잰다",
              rc == 0 and "2차 솔리드" not in out and "Min Jacobian" in out, out[-300:])
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
