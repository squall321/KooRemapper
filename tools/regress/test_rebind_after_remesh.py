#!/usr/bin/env python3
# 재메시 뒤 덧붙인 블록의 절점 번호를 (파트 이름, 좌표)로 새 덱 번호에 다시 묶는 op 의 회귀 시험
"""`rebind_entities_after_remesh` v1 (2026-10-16).

왜 이 시험이 있나.

  StepForge 덱은 메시 잡마다 파트 순서대로 **전역 재번호**해 통째로 다시 쓴다(저쪽 `BOUNDARY-DYNAFORGE.md` §3-6).
  우리가 덧붙인 세트·SPC·이력·CNRB 는 다음 메시 잡에서 번호가 어긋난다. 재결속은 우리 몫이고, 입력은 구간 표 +
  좌표 기준이다(Q12). 저쪽 작업 폴더에는 전후 덱 쌍이 남지 않아(메시 잡마다 덮어쓴다) **저쪽 꼴 그대로의 합성
  덱·구간 표**로 본다 — `coord_sha` 는 저쪽 식(`f"{x:16.9e}"` 정렬 · sha256 앞 16자) 그대로 여기서 잰다.

  옛 덱 — A(x 0..2, 절점 1..12) · B(x 2..4, 절점 13..24). 두 파트는 x=2 에서 **맞닿고 절점은 따로**다(저쪽 덱 꼴).
  새 덱 — B 를 앞에서 3칸으로 다시 구웠다(x = 2, 2.667, 3.333, 4 — 옛 x=3 자리가 사라졌다) · A 는 좌표 그대로
  번호만 밀렸다. **PID 도 바뀌었다**(A 1 → 5 · B 2 → 4 — 저쪽 `pid_renumber_possible`).
  v2(2026-10-16) — 파트(`*SET_PART` · 접촉 SSTYP 3 · `*CONSTRAINED_RIGID_BODIES`)는 `*PART` 제목으로, 요소
  (`*SET_SOLID` · `*DATABASE_HISTORY_SOLID`)는 (파트 제목, 요소 절점들의 좌표 집합)으로 짝을 찾는다.
  D절(2026-10-17) — 리더가 2차 솔리드의 절점 칸을 다 읽으므로 TET10 덱도 받는다(중간절점의 소속까지 본다).
  E·F·G절(2026-10-17) — `tolerance`(줄 때만 · 같은 파트 안 하나뿐인 짝) · 인클루드로 쪼갠 덱(닫힘을 다 읽어야) ·
  파트 감쇠·초기응력 카드(칸 자리는 정본 `IdRefs`).

usage: test_rebind_after_remesh.py <KooRemapper 바이너리>
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []
OP = "rebind_entities_after_remesh"


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:300]))
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n") as f:
        f.write(text)


def hexes(x0, nx, start_n, start_e, pid, dx):
    nodes, els, idx, nid = [], [], {}, start_n
    for k in (0, 1):
        for j in (0, 1):
            for i in range(nx + 1):
                idx[(i, j, k)] = nid
                nodes.append((nid, x0 + i * dx, float(j), float(k)))
                nid += 1
    for i in range(nx):
        c = [idx[(i, 0, 0)], idx[(i + 1, 0, 0)], idx[(i + 1, 1, 0)], idx[(i, 1, 0)],
             idx[(i, 0, 1)], idx[(i + 1, 0, 1)], idx[(i + 1, 1, 1)], idx[(i, 1, 1)]]
        els.append((start_e + i, pid, c))
    return nodes, els


def deck(path, parts):
    L = ["*KEYWORD", "*NODE"]
    for nodes, _els, _pid, _t in parts:
        L += ["%8d%16.6f%16.6f%16.6f" % (n, x, y, z) for n, x, y, z in nodes]
    L.append("*ELEMENT_SOLID")
    for _n, els, _pid, _t in parts:
        L += ["%8d%8d" % (e, p) + "".join("%8d" % v for v in c) for e, p, c in els]
    for _n, _e, pid, title in parts:
        L += ["*PART", title, "%10d%10d%10d" % (pid, 1, 1)]
    L += ["*SECTION_SOLID", "%10d%10d" % (1, 1),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
    write(path, "\n".join(L) + "\n")
    # 덱이 실제로 적은 좌표(%16.6f 를 되읽은 값) — 짝 찾기·coord_sha 는 덱 표기를 본다
    xyz = {n: tuple(float("%16.6f" % v) for v in (x, y, z)) for ns, _e, _p, _t in parts for n, x, y, z in ns}
    owner = {}
    for ns, els, pid, title in parts:
        for _e, _p, c in els:
            for v in c:
                owner[v] = title
    return xyz, owner, parts


def coord_sha(xyz, ids):
    rows = sorted("%16.9e%16.9e%16.9e" % xyz[n] for n in ids)
    return hashlib.sha256("\n".join(rows).encode("ascii")).hexdigest()[:16]


def expect_map(old, new):
    """옛 절점 → 새 절점 — (파트 이름, 좌표)가 정확히 같은 것. 없으면 들어가지 않는다."""
    oxyz, oown, _ = old
    nxyz, nown, _ = new
    idx = {}
    for n, p in nxyz.items():
        idx.setdefault((nown.get(n), p), []).append(n)
    return {o: idx[(oown.get(o), p)][0] for o, p in oxyz.items() if len(idx.get((oown.get(o), p), [])) == 1}


def card(*vals, w=10):
    return "".join(("%" + str(w) + "s") % v for v in vals)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="rbd_")
    try:
        A_old, B_old = hexes(0.0, 2, 1, 1, 1, 1.0), hexes(2.0, 2, 13, 3, 2, 1.0)
        old = deck(os.path.join(d, "v1.k"), [(A_old[0], A_old[1], 1, "A#1"), (B_old[0], B_old[1], 2, "B#2")])
        B_new, A_new = hexes(2.0, 3, 1, 1, 4, 2.0 / 3.0), hexes(0.0, 2, 21, 4, 5, 1.0)
        new = deck(os.path.join(d, "v2.k"), [(B_new[0], B_new[1], 4, "B#2"), (A_new[0], A_new[1], 5, "A#1")])
        m = expect_map(old, new)
        pmap = {1: 5, 2: 4}                                   # 제목으로 — A#1 1→5 · B#2 2→4

        def ekey(xyz, nodes_):
            return tuple(sorted(xyz[n] for n in set(nodes_)))
        new_e = {(1 if p_ == 5 else 2, ekey(new[0], c)): e for e, p_, c in A_new[1] + B_new[1]}
        emap = {e: new_e[(p_, ekey(old[0], c))] for e, p_, c in A_old[1] + B_old[1] if (p_, ekey(old[0], c)) in new_e}
        a_eids = [e for e, _p, _c in A_old[1]]
        b_eid_gone = [e for e, _p, _c in B_old[1] if e not in emap]
        a_ids = [n for n, _x, _y, _z in A_old[0]]
        iface = [n for n in a_ids if abs(old[0][n][0] - 2.0) < 1e-9]          # A 쪽 x=2 — B 절점과 같은 자리
        b_gone = [n for n, x, _y, _z in B_old[0] if abs(x - 3.0) < 1e-9]       # 다시 구운 B 에 없는 자리

        print("[A 다시 굽지 않은 파트를 가리키는 블록 — 새 번호로 다 묶는다]")
        ours = ["*KEYWORD", "$ 우리가 덧붙인 블록 — v1 번호",
                "*SET_NODE_LIST", card(50), card(*a_ids[:8]), card(*a_ids[8:]),
                "*SET_SEGMENT", card(51), card(a_ids[0], a_ids[1], a_ids[4], a_ids[3]),
                "*BOUNDARY_SPC_NODE", card(a_ids[0], 0, 1, 1, 1),
                "*DATABASE_HISTORY_NODE", card(iface[0], a_ids[5]),
                "*CONSTRAINED_NODAL_RIGID_BODY", card(900, 0, 50, iface[0]),
                "*DEFINE_COORDINATE_NODES", card(7, a_ids[0], a_ids[1], a_ids[3]),
                "*NODE", "%8d%16.6f%16.6f%16.6f" % (9001, -1.0, 0.0, 0.0),
                "*ELEMENT_MASS", "%8d%8d%16.6e%8d" % (9001, 9001, 0.5, 0) + "",
                "*ELEMENT_MASS", "%8d%8d%16.6e%8d" % (9002, a_ids[2], 0.25, 0),
                "*DEFINE_CURVE", card(31), "%20.6f%20.6f" % (0.0, 0.0), "%20.6f%20.6f" % (1.0, 1.0),
                "*BOUNDARY_SPC_SET", card(50, 0, 1, 1, 1),
                # v2 — 파트·요소 참조
                "*SET_PART_LIST", card(60), card(1, 2),
                "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID", card(77) + "A to seg",
                card(1, 51, 3, 0), "", "",
                "*SET_SOLID_LIST", card(61), card(*a_eids),
                "*DATABASE_HISTORY_SOLID", card(a_eids[0]),
                "*CONSTRAINED_RIGID_BODIES", card(1, 2),
                "*END"]
        write(os.path.join(d, "ours.k"), "\n".join(ours) + "\n")
        write(os.path.join(d, "rb.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: ours.k\noutput: ours_rebound.k\n")
        rc, out = run(binary, d, OP, "rb.yaml")
        ok = check("A-1 rc 0 · 산출이 있다", rc == 0 and os.path.exists(os.path.join(d, "ours_rebound.k")), out[-400:])
        if ok:
            got = open(os.path.join(d, "ours_rebound.k")).read().splitlines()
            src = open(os.path.join(d, "ours.k")).read().splitlines()
            # 기대 — 절점 칸만 m 으로 바뀐 줄
            exp = list(src)
            def sub(line, cols, w=10):
                s = line
                for c in cols:
                    v = int(s[c:c + w])
                    if v in m:
                        s = s[:c] + ("%" + str(w) + "d") % m[v] + s[c + w:]
                return s
            for i, l in enumerate(src):
                kw = None
                for j in range(i, -1, -1):
                    if src[j].startswith("*"):
                        kw = src[j].strip()
                        break
                if l.startswith("*") or l.startswith("$"):
                    continue
                if kw == "*SET_NODE_LIST" and l != card(50):
                    exp[i] = sub(l, range(0, len(l), 10))
                elif kw == "*SET_SEGMENT" and l != card(51):
                    exp[i] = sub(l, (0, 10, 20, 30))
                elif kw in ("*BOUNDARY_SPC_NODE",):
                    exp[i] = sub(l, (0,))
                elif kw == "*DATABASE_HISTORY_NODE":
                    exp[i] = sub(l, (0, 10))
                elif kw == "*CONSTRAINED_NODAL_RIGID_BODY":
                    exp[i] = sub(l, (30,))
                elif kw == "*DEFINE_COORDINATE_NODES":
                    exp[i] = sub(l, (10, 20, 30))
                elif kw == "*ELEMENT_MASS":
                    exp[i] = sub(l, (8,), w=8)
                elif kw in ("*SET_PART_LIST", "*SET_SOLID_LIST") and l not in (card(60), card(61)):
                    mp = pmap if kw == "*SET_PART_LIST" else emap
                    exp[i] = "".join("%10d" % mp[int(l[c:c + 10])] for c in range(0, len(l), 10))
                elif kw == "*DATABASE_HISTORY_SOLID":
                    exp[i] = "%10d" % emap[int(l[:10])]
                elif kw == "*CONSTRAINED_RIGID_BODIES":
                    exp[i] = "%10d%10d" % (pmap[int(l[:10])], pmap[int(l[10:20])])
                elif kw == "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID" and l == card(1, 51, 3, 0):
                    exp[i] = card(pmap[1], 51, 3, 0)
            check("A-2 ★절점 칸만 (파트, 좌표) 짝의 새 번호로 바뀌고 나머지 바이트는 그대로", got == exp,
                  [(a, b) for a, b in zip(got, exp) if a != b][:3])
            check("A-3 블록 자신의 절점(9001)과 그것을 쓰는 집중질량은 그대로", any(
                l.startswith("%8d%8d" % (9001, 9001)) for l in got), [l for l in got if "9001" in l])
            check("A-4 맞닿은 자리(x=2)의 A 절점은 B 가 아니라 A 의 새 절점으로", any(
                l == card(900, 0, 50, m[iface[0]]) for l in got) and new[1][m[iface[0]]] == "A#1",
                  (iface[0], m.get(iface[0])))
            write(os.path.join(d, "master.k"), "*KEYWORD\n*INCLUDE\nv2.k\n*INCLUDE\nours_rebound.k\n*END\n")
            rc2, out2 = run(binary, d, "info", "master.k", "--strict")
            check("A-5 새 덱 + 산출을 인클루드한 덱이 `info --strict` 의 참조 검사를 통과한다",
                  "·절점 미정의 참조 0건" in out2 and "정의되지 않은 것을" not in out2, out2[-400:])
            check("A-6 무엇을 몇 곳 바꿨는지 말한다", "다 묶었다" in out and "*SET_NODE_LIST" in out, out[-300:])
            check("A-7 ★v2 — 파트는 제목으로(1→5 · 2→4) · 접촉 SSTYP 3 칸 · 강체 묶음 · 요소 세트·이력은 좌표 집합으로",
                  card(pmap[1], pmap[2]) in got and card(pmap[1], 51, 3, 0) in got and
                  card(*[emap[e] for e in a_eids]) in got, [l for l in got if l.strip()[:2].isdigit()][-6:])

        print("[B 다시 구운 파트의 사라진 자리 — 못 풀면 쓰지 않는다]")
        write(os.path.join(d, "ours_b.k"), "*KEYWORD\n*SET_NODE_LIST\n%s\n%s\n*SET_SOLID_LIST\n%s\n%s\n*END\n" % (
            card(52), card(a_ids[0], b_gone[0]), card(62), card(a_eids[0], b_eid_gone[0])))
        # 구간 표 — 저쪽 꼴 그대로(행 키 = 덱 파트 이름 · coords.before/after = coord_sha)
        rows = []
        for title, pid, ob, nb in (("A#1", 1, A_old, A_new), ("B#2", 2, B_old, B_new)):
            sb = coord_sha(old[0], [n for n, *_ in ob[0]])
            sa = coord_sha(new[0], [n for n, *_ in nb[0]])
            rows.append({"part": title, "before": {"node_start": ob[0][0][0], "node_count": len(ob[0]),
                                                   "elem_start": ob[1][0][0], "elem_count": len(ob[1]), "pid": pid},
                         "after": {"node_start": nb[0][0][0], "node_count": len(nb[0]),
                                   "elem_start": nb[1][0][0], "elem_count": len(nb[1]), "pid": pid},
                         "state": "resized" if title == "B#2" else "moved", "moved": True,
                         "resized": title == "B#2", "delta_nodes": len(nb[0]) - len(ob[0]),
                         "delta_elems": len(nb[1]) - len(ob[1]),
                         "coords": {"before": sb, "after": sa, "same": sb == sa}})
        rd = {"parts": rows, "counts": {"same": 0, "moved": 2, "resized": 1, "added": 0, "removed": 0},
              "coords": {"identical": 1, "changed": 1, "unknown": 0}, "snapshot": {}, "basis": "시험"}
        write(os.path.join(d, "rd.json"), json.dumps(rd, ensure_ascii=False, indent=2))
        write(os.path.join(d, "rb_b.yaml"),
              "old_deck: v1.k\nnew_deck: v2.k\nentities: ours_b.k\noutput: ours_b_out.k\nrange_diff: rd.json\n")
        rc, out = run(binary, d, OP, "rb_b.yaml")
        check("B-1 rc 1", rc == 1, out[-300:])
        check("B-2 그 절점과 까닭(같은 파트·같은 자리 절점이 없다)을 댄다",
              ("절점 %d" % b_gone[0]) in out and "같은 자리 절점이 없다" in out, out[-400:])
        check("B-3 구간 표가 그 파트를 다시 구웠다고 말한다(resized)", "resized" in out, out[-400:])
        check("B-4 ★산출을 쓰지 않는다", not os.path.exists(os.path.join(d, "ours_b_out.k")))
        check("B-5 구간 표를 두 덱에서 다시 재어 대조했다", "coord_sha 4개" in out, out[-400:])
        check("B-6 ★v2 — 다시 구운 B 의 요소도 짝이 없다고 짚는다(요소)",
              ("요소 %d" % b_eid_gone[0]) in out and "같은 파트·같은 절점 자리의 요소가 없다" in out, out[-500:])

        print("[C 거절 — 모르는 카드 · 번호 충돌 · 구간 표 불일치 · 단정 못 하는 칸 · 자유형식]")
        cases = [
            ("C-1 접촉 Card 1 의 서명(STYP 0..6)이 안 맞는다 — 칸을 단정 못 한다",
             "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n%s\n\n\n" % card(1, 51, "x", 0), "단정하지 못한"),
            ("C-2 `*SET_PART_LIST_GENERATE`(옛 번호의 범위)", "*SET_PART_LIST_GENERATE\n%s\n%s\n" % (card(60), card(1, 2)),
             "옮기지 못하는 카드"),
            ("C-2b `*INITIAL_STRESS_SOLID`(요소 — 카드 줄 수가 데이터에 달렸다)",
             "*INITIAL_STRESS_SOLID\n%s\n" % card(1, 1), "옮기지 못하는 카드"),
            ("C-3 블록의 `*NODE` 가 새 덱 절점 번호와 겹친다", "*NODE\n%8d%16.6f%16.6f%16.6f\n" % (25, 9.0, 9.0, 9.0),
             "겹친다"),
            ("C-4 CNRB PID 가 새 덱 파트와 겹친다", "*CONSTRAINED_NODAL_RIGID_BODY\n%s\n" % card(4, 0, 50, 0), "겹친다"),
            ("C-5 강제운동 Card 3(|DOF|=9) — 칸을 단정 못 한다", "*BOUNDARY_PRESCRIBED_MOTION_NODE\n%s\n%s\n" % (
                card(a_ids[0], 9, 0, 0, "1.0"), card("0.0", "0.0", 0, a_ids[1], 0)), "단정하지 못한"),
            ("C-6 자유형식 줄은 제자리에 못 바꾼다", "*BOUNDARY_SPC_NODE\n%d,0,1,1,1\n" % a_ids[0], "자유형식"),
        ]
        for name, body, needle in cases:
            if os.path.exists(os.path.join(d, "c_out.k")):
                os.remove(os.path.join(d, "c_out.k"))
            write(os.path.join(d, "c.k"), "*KEYWORD\n*SET_NODE_LIST\n%s\n%s\n%s*END\n" % (card(50), card(a_ids[0]), body))
            write(os.path.join(d, "c.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: c.k\noutput: c_out.k\n")
            rc, out = run(binary, d, OP, "c.yaml")
            check(name + " → rc 1 · 까닭", rc == 1 and needle in out and not os.path.exists(os.path.join(d, "c_out.k")),
                  (rc, out[-300:]))
        if os.path.exists(os.path.join(d, "c_out.k")):
            os.remove(os.path.join(d, "c_out.k"))
        bad = json.loads(json.dumps(rd))
        bad["parts"][0]["coords"]["after"] = "0" * 16
        write(os.path.join(d, "rd_bad.json"), json.dumps(bad))
        write(os.path.join(d, "c.k"), "*KEYWORD\n*SET_NODE_LIST\n%s\n%s\n*END\n" % (card(50), card(a_ids[0])))
        write(os.path.join(d, "c.yaml"),
              "old_deck: v1.k\nnew_deck: v2.k\nentities: c.k\noutput: c_out.k\nrange_diff: rd_bad.json\n")
        rc, out = run(binary, d, OP, "c.yaml")
        check("C-7 구간 표의 coord_sha 가 덱과 다르면 거절(이 표의 덱이 아니다)",
              rc == 1 and "맞지 않는다" in out and not os.path.exists(os.path.join(d, "c_out.k")), out[-300:])
        write(os.path.join(d, "c.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: c.k\noutput: c_out.k\nmodel: v1.k\n")
        rc, out = run(binary, d, OP, "c.yaml")
        check("C-8 모르는 YAML 키(model)는 거절", rc == 1 and "모르는 키" in out, out[-200:])
        write(os.path.join(d, "c.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: c.k\noutput: c.k\n")
        rc, out = run(binary, d, OP, "c.yaml")
        check("C-9 output 이 entities 와 같으면 거절(원본을 덮어쓰지 않는다)", rc == 1 and "덮어쓰지" in out, out[-200:])
        print("[C2 접촉 머리 카드 — ID · MPP 1 · `&` MPP 2 · 빈 MPP 1 뒤의 Card 1 을 읽는다(10-24 정본으로 모음)]")
        # IdRefs 는 접촉 Card 1 자리를 따로 셌다(맞게 셌다). 10-24 부터 contact 정본(ct_parseContacts)이 센다 — 이 절은 그 자리를 지킨다.
        C23 = "%s\n%s\n" % (card("0.2", "0.2"), card("1.0", "1.0"))
        want = {999: card(1, 999, 3, 3), 998: card(2, 998, 3, 3), 997: card(997, 1, 3, 3), 996: card(996, 2, 3, 3)}
        body = ("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID\n%s\n%s\n" % (card(11) + "idc", want[999]) + C23 +
                "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MPP\n%s\n%s\n" % (card(0, 200), want[998]) + C23 +
                "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID_MPP\n%s\n%s\n&        0\n%s\n" % (card(12) + "both", card(2, 200, 0, 3), want[997]) + C23 +
                "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MPP\n\n%s\n" % want[996] + C23)
        write(os.path.join(d, "dct.k"), "*KEYWORD\n*SET_NODE_LIST\n%s\n%s\n%s*END\n" % (card(50), card(a_ids[0]), body))
        write(os.path.join(d, "dct.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: dct.k\noutput: dct_out.k\n")
        rc, out = run(binary, d, OP, "dct.yaml")
        dl = open(os.path.join(d, "dct.k")).read().splitlines()
        for pid, c1 in want.items():
            ln = dl.index(c1) + 1
            check("C2-%d Card 1(line %d)이 가리키는 없는 파트 %d 을 짚는다" % (pid, ln, pid),
                  ("line %d *CONTACT" % ln) in out and ("파트 %d" % pid) in out, out[-500:])
        check("C2-5 rc 1 · 산출 없음", rc == 1 and not os.path.exists(os.path.join(d, "dct_out.k")), out[-200:])
        print("[E 공차 — 줄 때만(2026-10-17) · 정확 일치가 기본]")
        # 새 덱의 A 를 x 로 2e-4 밀었다(재메시가 남긴 미세한 어긋남) — 정확 일치로는 못 푼다
        A_sh = ([(n, x + 2e-4, y, z) for n, x, y, z in A_new[0]], A_new[1])
        deck(os.path.join(d, "v2s.k"), [(B_new[0], B_new[1], 4, "B#2"), (A_sh[0], A_sh[1], 5, "A#1")])
        tol_ours = ["*KEYWORD", "*BOUNDARY_SPC_NODE", card(a_ids[0], 0, 1, 1, 1), card(a_ids[5], 0, 1, 1, 1),
                    "*DATABASE_HISTORY_SOLID", card(a_eids[0]), "*END"]
        write(os.path.join(d, "tol.k"), "\n".join(tol_ours) + "\n")
        write(os.path.join(d, "e0.yaml"), "old_deck: v1.k\nnew_deck: v2s.k\nentities: tol.k\noutput: e0_out.k\n")
        rc, out = run(binary, d, OP, "e0.yaml")
        check("E-1 공차 없이는 못 푼다(rc 1 · 같은 자리 절점이 없다)", rc == 1 and "같은 자리 절점이 없다" in out, out[-300:])
        write(os.path.join(d, "e1.yaml"), "old_deck: v1.k\nnew_deck: v2s.k\nentities: tol.k\noutput: e1_out.k\ntolerance: 1.0e-3\n")
        rc, out = run(binary, d, OP, "e1.yaml")
        got = open(os.path.join(d, "e1_out.k")).read().splitlines() if os.path.exists(os.path.join(d, "e1_out.k")) else []
        check("E-2 ★tolerance 1e-3 이면 같은 파트 안 하나뿐인 짝으로 묶는다(절점 · 요소 둘 다)",
              rc == 0 and card(m[a_ids[0]], 0, 1, 1, 1) in got and card(m[a_ids[5]], 0, 1, 1, 1) in got and
              card(emap[a_eids[0]]) in got, (rc, got, out[-300:]))
        check("E-3 공차로 짝지은 수와 가장 큰 거리를 말한다", "공차로 짝지은 절점 2곳" in out and "0.0002" in out, out[-300:])
        write(os.path.join(d, "e2.yaml"), "old_deck: v1.k\nnew_deck: v2s.k\nentities: tol.k\noutput: e2_out.k\ntolerance: 1.5\n")
        rc, out = run(binary, d, OP, "e2.yaml")
        check("E-4 공차가 격자보다 크면 짝이 여럿이라 못 푼다(rc 1 · 쓰지 않는다)",
              rc == 1 and "공차 1.5 안 절점이" in out and not os.path.exists(os.path.join(d, "e2_out.k")), out[-300:])
        write(os.path.join(d, "e3.yaml"), "old_deck: v1.k\nnew_deck: v2s.k\nentities: tol.k\noutput: e3_out.k\ntolerance: -1\n")
        rc, out = run(binary, d, OP, "e3.yaml")
        check("E-5 음수 공차는 거절한다", rc == 1 and "tolerance 는 0 이상" in out, out[-200:])

        print("[F 인클루드로 쪼갠 덱 — 닫힘을 다 읽으면 받는다(2026-10-17)]")
        for tag, src_ in (("v1", "v1.k"), ("v2", "v2.k")):
            body = [l for l in open(os.path.join(d, src_)).read().splitlines() if l.strip() not in ("*KEYWORD", "*END")]
            write(os.path.join(d, "%s_body.k" % tag), "\n".join(body) + "\n")
            write(os.path.join(d, "%s_master.k" % tag), "*KEYWORD\n*INCLUDE\n%s_body.k\n*END\n" % tag)
        write(os.path.join(d, "f.yaml"), "old_deck: v1_master.k\nnew_deck: v2_master.k\nentities: ours.k\noutput: f_out.k\n")
        rc, out = run(binary, d, OP, "f.yaml")
        same = (os.path.exists(os.path.join(d, "f_out.k")) and os.path.exists(os.path.join(d, "ours_rebound.k")) and
                open(os.path.join(d, "f_out.k")).read() == open(os.path.join(d, "ours_rebound.k")).read())
        check("F-1 ★인클루드 마스터 둘로 돌려도 한 파일 덱과 산출이 **바이트로 같다**", rc == 0 and same, out[-300:])
        check("F-2 인클루드를 함께 읽었다고 말한다", "인클루드 닫힘을 함께 읽었다" in out, out[-200:])
        write(os.path.join(d, "v1_broken.k"), "*KEYWORD\n*INCLUDE\nv1_body.k\n*INCLUDE\nnope.k\n*END\n")
        write(os.path.join(d, "f2.yaml"), "old_deck: v1_broken.k\nnew_deck: v2_master.k\nentities: ours.k\noutput: f2_out.k\n")
        rc, out = run(binary, d, OP, "f2.yaml")
        check("F-3 닫힘을 다 못 읽으면 거절한다(못 본 파일의 절점을 「없다」로 읽지 않는다)",
              rc == 1 and "닫힘을 다 읽지 못했다" in out and "nope.k" in out and not os.path.exists(os.path.join(d, "f2_out.k")),
              out[-300:])

        print("[G 파트 감쇠 · 초기응력 카드 — 칸 자리는 정본 IdRefs(2026-10-17)]")
        g_ours = ["*KEYWORD",
                  "*DAMPING_PART_STIFFNESS", card(1, "0.05"),
                  "*DAMPING_PART_MASS", card(1, 31, "1.0", 1), card("1.0", "1.0", "0.0", "0.0", "0.0", "0.0"),
                  "*INITIAL_STRESS_SOLID", card(a_eids[0], 1, 0, 0, 0, 0, 0, 0),
                  card("1.0", "2.0", "3.0", "0.0", "0.0", "0.0", "0.0"),
                  "*DEFINE_CURVE", card(31), "%20.6f%20.6f" % (0.0, 1.0), "%20.6f%20.6f" % (1.0, 1.0),
                  "*END"]
        write(os.path.join(d, "g.k"), "\n".join(g_ours) + "\n")
        write(os.path.join(d, "g.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: g.k\noutput: g_out.k\n")
        rc, out = run(binary, d, OP, "g.yaml")
        got = open(os.path.join(d, "g_out.k")).read().splitlines() if os.path.exists(os.path.join(d, "g_out.k")) else []
        check("G-1 ★파트 감쇠 둘의 PID 1 → 5(제목으로) · MASS 의 Card 2 는 손대지 않는다",
              rc == 0 and card(5, "0.05") in got and card(5, 31, "1.0", 1) in got and
              card("1.0", "1.0", "0.0", "0.0", "0.0", "0.0") in got, (rc, got, out[-300:]))
        check("G-2 ★초기응력의 EID 가 같은 자리 새 요소로 · 응력 줄은 그대로",
              card(emap[a_eids[0]], 1, 0, 0, 0, 0, 0, 0) in got and
              card("1.0", "2.0", "3.0", "0.0", "0.0", "0.0", "0.0") in got, got)
        bad = ["*KEYWORD", "*INITIAL_STRESS_SOLID", card(a_eids[0], 2, 0, 0, 0, 0, 0, 0),
               card("1.0", "2.0", "3.0", "0.0", "0.0", "0.0", "0.0"), "*END"]   # NINT 2 인데 응력 줄이 하나 — 세트가 모자란다
        write(os.path.join(d, "g2.k"), "\n".join(bad) + "\n")
        write(os.path.join(d, "g2.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: g2.k\noutput: g2_out.k\n")
        rc, out = run(binary, d, OP, "g2.yaml")
        check("G-3 카드 세트 길이가 맞지 않는 초기응력은 단정하지 않고 거절한다",
              rc == 1 and "*INITIAL_STRESS_SOLID" in out and not os.path.exists(os.path.join(d, "g2_out.k")), out[-300:])
        print("[D 2차 솔리드 덱 — 중간절점의 소속까지 본다(2026-10-17 · 그 전에는 2차 덱을 거절했다)]")
        # 10절점 사면체 하나 — 옛 덱은 절점 1..10, 새 덱은 같은 자리를 101..110 으로 거꾸로 매겼다(파트 제목 그대로 · PID 3)
        cs = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        pts = list(cs) + [tuple((cs[a][k] + cs[b][k]) / 2 for k in range(3))
                          for a, b in ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))]

        def tet10_deck(path, ids, eid, pid, split=False):
            L = ["*KEYWORD", "*NODE"] + ["%8d%16.6f%16.6f%16.6f" % (ids[i], *pts[i]) for i in range(10)]
            L += ["*ELEMENT_SOLID", "%8d%8d" % (eid, pid)]
            conn = "".join("%8d" % ids[i] for i in range(10))
            L += [conn[:64], conn[64:]] if split else [conn]
            L += ["*PART", "T#1", "%10d%10d%10d" % (pid, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 16),
                  "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
            write(os.path.join(d, path), "\n".join(L) + "\n")
        old_ids = list(range(1, 11))
        new_ids = list(range(110, 100, -1))
        tet10_deck("t_v1.k", old_ids, 1, 1)
        tet10_deck("t_v2.k", new_ids, 7, 3)
        # SPC 를 중간절점 5(n1–n2 가운데 · 다섯째 칸)와 코너 1 에 건다 — 새 덱에서는 같은 자리 106 · 110 이다
        write(os.path.join(d, "t_ours.k"), "*KEYWORD\n*BOUNDARY_SPC_NODE\n" + card(5, 0, 1, 1, 1, 0, 0, 0) + "\n" +
              card(1, 0, 1, 1, 1, 0, 0, 0) + "\n*END\n")
        write(os.path.join(d, "t.yaml"), "old_deck: t_v1.k\nnew_deck: t_v2.k\nentities: t_ours.k\noutput: t_out.k\n")
        rc, out = run(binary, d, OP, "t.yaml")
        check("D-1 ★TET10 덱을 받는다(rc 0 — 예전에는 「2차 솔리드」 로 거절)", rc == 0, out[-300:])
        spc = []
        if os.path.exists(os.path.join(d, "t_out.k")):
            on = False
            for l in open(os.path.join(d, "t_out.k")).read().splitlines():
                if l.startswith("*"):
                    on = l.strip() == "*BOUNDARY_SPC_NODE"
                    continue
                if on and l.strip() and not l.startswith("$"):
                    spc.append(int(l[:10]))
        check("D-2 ★중간절점 5 → 같은 자리 새 중간절점 106 · 코너 1 → 110", spc == [106, 110], spc)
        tet10_deck("t_split.k", old_ids, 1, 1, split=True)
        write(os.path.join(d, "ts.yaml"), "old_deck: t_split.k\nnew_deck: t_v2.k\nentities: t_ours.k\noutput: ts_out.k\n")
        rc, out = run(binary, d, OP, "ts.yaml")
        check("D-3 노드를 8+2 로 쪼갠 덱은 거절한다(절점 칸이 모자란 2차 요소)",
              rc == 1 and "모자란" in out and not os.path.exists(os.path.join(d, "ts_out.k")), out[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
