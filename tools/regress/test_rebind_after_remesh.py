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
  번호만 밀렸다.

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
        B_new, A_new = hexes(2.0, 3, 1, 1, 2, 2.0 / 3.0), hexes(0.0, 2, 21, 4, 1, 1.0)
        new = deck(os.path.join(d, "v2.k"), [(B_new[0], B_new[1], 2, "B#2"), (A_new[0], A_new[1], 1, "A#1")])
        m = expect_map(old, new)
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

        print("[B 다시 구운 파트의 사라진 자리 — 못 풀면 쓰지 않는다]")
        write(os.path.join(d, "ours_b.k"), "*KEYWORD\n*SET_NODE_LIST\n%s\n%s\n*END\n" % (card(52), card(a_ids[0], b_gone[0])))
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

        print("[C 거절 — 모르는 카드 · 번호 충돌 · 구간 표 불일치 · 단정 못 하는 칸 · 자유형식]")
        cases = [
            ("C-1 접촉(요소·파트 번호)", "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n%s\n\n\n" % card(51, 51, 0, 0),
             "옮기지 못하는 카드"),
            ("C-2 `*SET_PART_LIST`", "*SET_PART_LIST\n%s\n%s\n" % (card(60), card(1)), "옮기지 못하는 카드"),
            ("C-3 블록의 `*NODE` 가 새 덱 절점 번호와 겹친다", "*NODE\n%8d%16.6f%16.6f%16.6f\n" % (25, 9.0, 9.0, 9.0),
             "겹친다"),
            ("C-4 CNRB PID 가 새 덱 파트와 겹친다", "*CONSTRAINED_NODAL_RIGID_BODY\n%s\n" % card(2, 0, 50, 0), "겹친다"),
            ("C-5 강제운동 Card 3(|DOF|=9) — 칸을 단정 못 한다", "*BOUNDARY_PRESCRIBED_MOTION_NODE\n%s\n%s\n" % (
                card(a_ids[0], 9, 0, 0, "1.0"), card("0.0", "0.0", 0, a_ids[1], 0)), "단정하지 못한"),
            ("C-6 자유형식 줄은 제자리에 못 바꾼다", "*BOUNDARY_SPC_NODE\n%d,0,1,1,1\n" % a_ids[0], "자유형식"),
        ]
        for name, body, needle in cases:
            write(os.path.join(d, "c.k"), "*KEYWORD\n*SET_NODE_LIST\n%s\n%s\n%s*END\n" % (card(50), card(a_ids[0]), body))
            write(os.path.join(d, "c.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: c.k\noutput: c_out.k\n")
            rc, out = run(binary, d, OP, "c.yaml")
            check(name + " → rc 1 · 까닭", rc == 1 and needle in out and not os.path.exists(os.path.join(d, "c_out.k")),
                  (rc, out[-300:]))
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
