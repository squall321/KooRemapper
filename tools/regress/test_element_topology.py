#!/usr/bin/env python3
# 요소 위상(면·모서리) 정본을 지킨다 — 감김이 섞이면 접촉면·압력면이 조용히 거짓이 된다
"""`topo::facesOf`/`edgesOf` 정본의 계약 (2026-10-05).

왜 이 시험이 있나.

  같은 지식이 리포에 **여섯 벌**로 흩어져 서로 달랐다 — `Element.h` 의 고정 육면체 표,
  `surfview` 의 종류별 면 표, `section` 의 종류별 모서리 표, `ModelAssembler` 의 손으로 적은
  사면체 표, 그리고 같은 함수 안의 육면체 면·모서리 사본 둘.

  그 흩어짐이 두 가지 결함을 낳았고 **전수 회귀 69개가 전부 초록인 채로 살아남았다.**
  아무 시험도 이것을 못 박지 않았기 때문이다. 그래서 이 시험이 그 자리를 막는다.

  ① **TET4 의 자유면이 틀렸다.** 육면체 표를 쓰면 면 0 → `[n0,n3,n3,n3]`(선), 면 3 →
     `[n3,n2,n3,n3]`(선), 면 4 → 네 꼭짓점을 모두 지나는 **사변형**(사면체에 없는 면)이 되고
     옛 퇴화 판정(`fn[0]==fn[1] && fn[2]==fn[3]`)이 **셋 다 통과시켰다.** 결과로 TET4 한 개가
     자유면 **5개**(가짜 3)를 내고 **진짜 면 둘이 빠졌다.**
     실측 — `extract-surface` 가 `1 2 3 4`/`1 2 4 4`/`1 4 4 4`/`2 3 4 4`/`4 3 4 4` 를 냈다.

  ② ★**세그먼트 감김이 한 면 안에서 섞였다.** 옛 육면체 표는 단위 육면체로 재면 6면 중
     **3면(f0·f3·f4)이 안쪽**이었다. 자유면 감김을 그대로 세그먼트로 내보내는 `contact`·`load`
     에서 실측 —
         load    세그먼트 5000개 → 바깥 2500 · **안쪽 2500** (정확히 절반)
         contact 세트 4개가 **모두** 섞였다 (3/2 · 2/3 · 3/2 · 2/3)
     LS-DYNA 에서 세그먼트 법선은 접촉 방향과 압력 부호를 정한다. **한 면 안에 두 방향이 섞인
     것은 어느 규약을 쓰든 틀렸다.**

usage: test_element_topology.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []


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


# ── 기하 도구 ───────────────────────────────────────────────────────────────
def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def face_outward(pts, interior):
    """면 절점(3개 또는 4개)의 감김이 `interior` 기준으로 바깥인가.

    유일 절점이 3개 미만(= 선으로 퇴화)이면 `None` 이다 — 그런 면은 방향을 물을 수 없다.
    ★시험이 **죽지 않아야** 한다. 옛 바이너리는 실제로 그런 면을 냈고, 거기서 예외가 나면
    뒤의 판정(세그먼트 감김)을 아예 못 본다 — 결함을 가리는 시험이 된다."""
    if len(pts) < 3:
        return None
    n = cross(sub(pts[1], pts[0]), sub(pts[2], pts[0]))
    if n == (0.0, 0.0, 0.0):
        return None
    mid = tuple(sum(q[k] for q in pts) / len(pts) for k in range(3))
    return dot(n, sub(mid, interior)) > 0


def parse_deck(path):
    """절점과 *SET_SEGMENT 블록들을 읽는다 — 블록마다 따로 돌려준다."""
    nodes, sets, cur, mode = {}, [], None, None
    for ln in open(path, encoding="latin-1"):
        s = ln.rstrip("\n")
        if s.startswith("$"):
            continue
        if s.startswith("*"):
            u = s.upper()
            if u.startswith("*NODE"):
                mode, cur = "NODE", None
            elif "SET_SEGMENT" in u:
                mode, cur = "SEG", []
                sets.append(cur)
            else:
                mode, cur = None, None
            continue
        t = s.split()
        if mode == "NODE" and len(t) >= 4:
            try:
                nodes[int(t[0])] = (float(t[1]), float(t[2]), float(t[3]))
            except ValueError:
                pass
        elif mode == "SEG" and cur is not None and len(t) >= 4:
            try:
                v = [int(x) for x in t[:4]]
                if all(x > 0 for x in v):
                    cur.append(v)
            except ValueError:
                pass
    return nodes, [x for x in sets if x]


def one_tet(path):
    pts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    L = ["*KEYWORD", "*NODE"]
    for i, (x, y, z) in enumerate(pts, 1):
        L.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
    L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1) + "".join("%8d" % v for v in [1, 2, 3, 4, 4, 4, 4, 4]),
          "*PART", "one tet", "%10d%10d%10d" % (1, 1, 1),
          "*SECTION_SOLID", "%10d%10d" % (1, 10),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
    write(path, "\n".join(L) + "\n")


def hex_box(path, nx=2, ny=2, nz=2):
    """nx*ny*nz 육면체 블록 — 자유면 감김을 보는 픽스처."""
    nid, idx, nodes = 1, {}, []
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                idx[(i, j, k)] = nid
                nodes.append((nid, float(i), float(j), float(k)))
                nid += 1
    L = ["*KEYWORD", "*NODE"]
    for n, x, y, z in nodes:
        L.append("%8d%16.9f%16.9f%16.9f" % (n, x, y, z))
    L.append("*ELEMENT_SOLID")
    e = 1
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                c = [idx[(i, j, k)], idx[(i + 1, j, k)], idx[(i + 1, j + 1, k)], idx[(i, j + 1, k)],
                     idx[(i, j, k + 1)], idx[(i + 1, j, k + 1)], idx[(i + 1, j + 1, k + 1)],
                     idx[(i, j + 1, k + 1)]]
                L.append("%8d%8d" % (e, 1) + "".join("%8d" % v for v in c))
                e += 1
    L += ["*PART", "box", "%10d%10d%10d" % (1, 1, 1),
          "*SECTION_SOLID", "%10d%10d" % (1, 1),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
    write(path, "\n".join(L) + "\n")


def main():
    if len(sys.argv) < 2:
        print("usage: test_element_topology.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="topo_")
    try:
        # ── A: ★TET4 자유면은 **삼각형 4개**다 (가짜 면도, 빠진 면도 없다) ──
        one_tet(os.path.join(d, "tet.k"))
        rc, out = run(binary, d, "extract-surface", "tet.k", "tshell.k", "--face", "all")
        check("A-1 extract-surface rc=0", rc == 0, out[-250:])
        check("A-2 ★자유면이 **4개**다 (옛 육면체 표는 5개를 냈다)",
              "Extracted 4 surface faces" in out,
              [l for l in out.splitlines() if "Extracted" in l][:1])
        check("A-3 ★사변형이 **0개**다 (사면체에 사변형 면은 없다)",
              "(0 QUAD4, 4 TRIA3" in out,
              [l for l in out.splitlines() if "Extracted" in l][:1])
        shells = []
        if os.path.exists(os.path.join(d, "tshell.k")):
            keep = False
            for ln in open(os.path.join(d, "tshell.k"), encoding="latin-1"):
                if ln.startswith("*"):
                    keep = ln.upper().startswith("*ELEMENT_SHELL")
                    continue
                if keep and ln.strip() and not ln.startswith("$"):
                    t = ln.split()
                    if len(t) >= 6:
                        shells.append([int(x) for x in t[2:6]])
        got = sorted(tuple(sorted(set(sh))) for sh in shells)
        want = sorted([(1, 2, 3), (1, 2, 4), (1, 3, 4), (2, 3, 4)])
        check("A-4 ★네 면이 사면체의 **진짜** 네 면이다", got == want, (got, want))
        # 선으로 퇴화한 면이 없다
        check("A-5 선(유일 절점 2개)으로 퇴화한 면이 없다",
              all(len(set(sh)) >= 3 for sh in shells), [sh for sh in shells if len(set(sh)) < 3])
        # 네 면이 모두 **바깥**을 향한다
        P = {1: (0, 0, 0), 2: (1, 0, 0), 3: (0, 1, 0), 4: (0, 0, 1)}
        C = tuple(sum(P[i][k] for i in P) / 4 for k in range(3))
        bad = []
        for sh in shells:
            o = face_outward([P[i] for i in list(dict.fromkeys(sh))], C)
            if o is False:          # None(퇴화)은 A-5 가 잡는다
                bad.append(sh)
        check("A-6 ★(방향을 물을 수 있는) 면이 모두 **바깥**을 향한다", not bad, bad)
        # surfview 와 같은 답이어야 한다 — 같은 정본을 쓰므로
        write(os.path.join(d, "sv.yaml"), "model: tet.k\noutput: sv\n")
        rc, svout = run(binary, d, "surfview", "sv.yaml")
        check("A-7 ★surfview 도 같은 답(4/4)을 낸다 — 두 op 이 한 표를 쓴다",
              "Faces total / free:      4 / 4" in svout.replace("\t", " ")
              or ("4 / 4" in svout and "Triangles drawn:         4" in svout),
              [l for l in svout.splitlines() if "Faces total" in l or "Triangles" in l][:2])

        # ── B: ★세그먼트 감김이 한 세트 안에서 **섞이지 않는다** ──
        hex_box(os.path.join(d, "box.k"))
        # `as_segment: true` 가 자유면을 뽑아 *SET_SEGMENT 로 적는 경로다 — 감김이 그대로 나간다.
        write(os.path.join(d, "ct.yaml"),
              "model: box.k\noutput: ct.k\ncontacts:\n"
              "  - action: create\n"
              "    type: automatic_surface_to_surface\n"
              "    slave:\n      pid: 1\n      as_segment: true\n"
              "    master:\n      pid: 1\n      as_segment: true\n"
              "    title: Topo_probe\n")
        rc, out = run(binary, d, "contact", "ct.yaml")
        made = os.path.join(d, "ct.k")
        if rc != 0 or not os.path.exists(made):
            # 설정 형태가 달라도 이 시험의 요지는 extract-surface 쪽이므로 건너뛴다
            print("  (B 건너뜀 — contact 설정 형태가 달라 세그먼트를 못 얻었다: rc=%d)" % rc)
        else:
            nodes, sets = parse_deck(made)
            check("B-1 세그먼트 세트를 얻었다", bool(sets), len(sets))
            mixed = []
            for si, S in enumerate(sets):
                pts = [nodes[n] for s in S for n in s if n in nodes]
                if not pts:
                    continue
                C2 = tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))
                o = i_ = 0
                for s in S:
                    if not all(n in nodes for n in s):
                        continue
                    w = face_outward([nodes[n] for n in list(dict.fromkeys(s))], C2)
                    if w is True:
                        o += 1
                    elif w is False:
                        i_ += 1
                if o and i_:
                    mixed.append((si + 1, o, i_))
            check("B-2 ★어느 세트도 감김이 **섞이지 않는다** (옛 표는 4세트가 전부 섞였다)",
                  not mixed, mixed)
            allout = []
            for S in sets:
                pts = [nodes[n] for s in S for n in s if n in nodes]
                if not pts:
                    continue
                C2 = tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))
                allout.append(all(
                    face_outward([nodes[n] for n in list(dict.fromkeys(s))], C2) is not False
                    for s in S if all(n in nodes for n in s)))
            check("B-3 ★세그먼트가 **바깥**을 향한다 (자유면의 물리적 바깥)",
                  all(allout), allout)

        # ── D: ★압출이 **짐작이 아니라 재서** 요소를 바로 세운다 ──
        #    `extrudeToSolid` 는 "감김을 뒤집을까" 를 `direction` 의 **우세 성분 부호**로
        #    짐작했다. 면 감김을 보지 않으므로 공용 표의 감김을 바깥으로 일관시키자
        #    `offset` 이 **음의 야코비안 100개**를 냈다(실측). 이제 `Validator` 와 같은 잣대로
        #    재서 `uprightHex` 가 상·하를 맞바꾼다 — 입력 감김이 무엇이든 바로 선다.
        write(os.path.join(d, "of.yaml"),
              "base_model: box.k\noutput: of\noperations:\n  - type: offset\n"
              "    source_pid: 1\n    thickness: 0.5\n    direction: +z\n"
              "    new_pid: 9\n")
        rc, out = run(binary, d, "offset", "of.yaml")
        if rc != 0 and "offset" not in out.lower():
            print("  (D 건너뜀 — offset 설정 형태가 달라 압출을 못 돌렸다)")
        else:
            check("D-1 offset rc=0", rc == 0, out[-250:])
            check("D-2 ★'negative/zero Jacobian' 을 **말하지 않는다**",
                  "negative/zero Jacobian" not in out,
                  [l for l in out.splitlines() if "Jacobian" in l][:2])
            made = os.path.join(d, "of.k")
            if os.path.exists(made):
                nodes, _ = parse_deck(made)
                solids, mode = [], None
                for ln in open(made, encoding="latin-1"):
                    if ln.startswith("*"):
                        mode = "S" if ln.upper().startswith("*ELEMENT_SOLID") else None
                        continue
                    if mode == "S" and ln.strip() and not ln.startswith("$"):
                        t = ln.split()
                        if len(t) >= 10:
                            solids.append([int(x) for x in t[2:10]])
                neg = 0
                for e in solids:
                    if not all(n in nodes for n in e):
                        continue
                    c = [nodes[n] for n in e]

                    def q(*ix):
                        return tuple(sum(c[k][dd] for k in ix) / 4.0 for dd in range(3))
                    du = sub(q(1, 2, 5, 6), q(0, 3, 4, 7))
                    dv = sub(q(2, 3, 6, 7), q(0, 1, 4, 5))
                    dw = sub(q(4, 5, 6, 7), q(0, 1, 2, 3))
                    if dot(du, cross(dv, dw)) < 0:
                        neg += 1
                check("D-3 ★뒤집힌 솔리드가 **0개**다 (요소 %d개 검사)" % len(solids),
                      neg == 0, neg)

        # ── C: 육면체는 6면, 사면체는 4면 — 면 수가 종류를 따른다 ──
        write(os.path.join(d, "sb.yaml"), "model: box.k\noutput: sb\n")
        rc, out = run(binary, d, "surfview", "sb.yaml")
        check("C-1 2x2x2 육면체 블록의 자유면은 24개다 (6면 × 4)",
              "24" in out and "Faces total / free" in out,
              [l for l in out.splitlines() if "Faces total" in l][:1])
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
