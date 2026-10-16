#!/usr/bin/env python3
# 없는 절점을 가리키는 세트·경계조건·이력을 `info --strict` 가 잡고 meshfix 가 그런 덱을 만들지 않는지 보는 회귀 시험
"""**없는 절점을 가리키는 카드** — `info --strict` 가 잡는가 · meshfix 가 만들지 않는가 (2026-10-16).

왜 이 시험이 있나.

  `generate arc` 의 `demo_flat_tet.k` 에 PID 1 절점을 가리키는 `*SET_NODE_LIST`·`*BOUNDARY_SPC_NODE`·
  `*DATABASE_HISTORY_NODE` 를 붙이고 `meshfix pid: 1` 을 돌렸다(실측).
    · meshfix — rc 0 · 경고 없음. 산출 덱에 그 절점이 **없는데** 세 카드가 번호를 그대로 가리켰다.
      → 지금은 같은 자리(`snap_tolerance`)의 새 절점으로 바꿔 쓰고(재결속), 못 풀면 쓰지 않는다. `preview: true` 는
        gmsh 없이 미리 짚는다.
    · `info --strict` — 「참조 무결성 OK」 · rc 0. 요소→절점만 보고 세트·경계조건→절점은 안 봤다.
  LS-DYNA 는 세트가 없는 절점을 가리키면 키워드 단계에서 멈춘다(현장 실측 Error 10233). 칸 자리는 정본
  하나(`parser/NodeRefs`)이고, 두 자리가 그것을 같이 쓴다.

  ★거짓 경보도 막아야 한다 — 오탐이 한 번 나면 아무도 이 보고를 안 믿는다. 그래서 갈래마다 「있는 절점이면
  조용하다」를 함께 보고, 절점이 아닌 칸(범위 세트 · 강제운동 Card 3 · 조인트 강성 · 조각 덱)을 따로 지킨다.

usage: test_dangling_node_refs.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:300]))
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args, env=None):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n") as f:
        f.write(text)


def gmsh_path():
    """meshfix 시험과 같은 규칙 — PATH 의 깨진 래퍼를 집지 않는다."""
    env = os.environ.get("KOOREMAPPER_GMSH")
    if env and os.path.exists(env):
        return env
    cand = os.path.join(REPO, "dist", "gmsh", "gmsh")
    return cand if os.path.exists(cand) else None


def box(i10=False, nodes=True):
    """육면체 둘(절점 1..12) · 파트 1. `*END` 는 붙이지 않는다."""
    iw = 10 if i10 else 8
    L = ["*KEYWORD" + (" I10=Y" if i10 else "")]
    if nodes:
        L.append("*NODE")
        nid = 0
        for z in (0.0, 1.0):
            for y in (0.0, 1.0):
                for x in (0.0, 1.0, 2.0):
                    nid += 1
                    L.append("%*d%16.6f%16.6f%16.6f" % (iw, nid, x, y, z))
        L.append("*ELEMENT_SOLID")
        L.append("".join("%*d" % (iw, v) for v in (1, 1, 1, 2, 5, 4, 7, 8, 11, 10)))
        L.append("".join("%*d" % (iw, v) for v in (2, 1, 2, 3, 6, 5, 8, 9, 12, 11)))
    L += ["*PART", "box", "%10d%10d%10d" % (1, 1, 1),
          "*SECTION_SOLID", "%10d%10d" % (1, 1),
          "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3),
          "*SET_NODE_LIST", "%10d" % 50, "%10d%10d" % (1, 2)]          # CNRB 가 가리킬 세트
    return L


# 갈래마다 (이름, 키워드, 카드 줄들(N 자리에 절점)). N 이 999 면 없는 절점, 3 이면 있는 절점.
FAMILIES = [
    ("SET_NODE_LIST", "*SET_NODE_LIST", ["%10d" % 60, "%10d%10s" % (1, "N")]),
    ("SET_NODE_LIST_TITLE", "*SET_NODE_LIST_TITLE", ["named set", "%10d" % 61, "%10d%10s" % (2, "N")]),
    ("SET_NODE_COLUMN", "*SET_NODE_COLUMN", ["%10d" % 62, "%10s%10.3f%10.3f%10.3f%10.3f" % ("N", 0, 0, 0, 0)]),
    ("SET_NODE_GENERAL(NODE)", "*SET_NODE_GENERAL", ["%10d" % 63, "%10s%10d%10s" % ("NODE", 1, "N")]),
    ("SET_SEGMENT", "*SET_SEGMENT", ["%10d" % 64, "%10d%10d%10d%10s" % (1, 2, 5, "N")]),
    ("BOUNDARY_SPC_NODE", "*BOUNDARY_SPC_NODE", ["%10s%10d%10d%10d%10d" % ("N", 0, 1, 1, 1)]),
    ("LOAD_NODE_POINT", "*LOAD_NODE_POINT", ["%10s%10d%10d%10.3f" % ("N", 3, 0, 1.0)]),
    ("INITIAL_VELOCITY_NODE", "*INITIAL_VELOCITY_NODE", ["%10s%10.3f%10.3f%10.3f" % ("N", 0, 0, -1.0)]),
    ("CONSTRAINED_EXTRA_NODES_NODE", "*CONSTRAINED_EXTRA_NODES_NODE", ["%10d%10s" % (1, "N")]),
    ("ELEMENT_MASS", "*ELEMENT_MASS", ["%8d%8s%16.6e%8d" % (100, "N", 0.001, 0)]),
    ("BOUNDARY_PRESCRIBED_MOTION_NODE", "*BOUNDARY_PRESCRIBED_MOTION_NODE",
     ["%10s%10d%10d%10d%10.3f" % ("N", 3, 0, 0, 1.0)]),
    ("DATABASE_HISTORY_NODE", "*DATABASE_HISTORY_NODE", ["%10d%10s" % (1, "N")]),
    ("CONSTRAINED_NODAL_RIGID_BODY(PNODE)", "*CONSTRAINED_NODAL_RIGID_BODY", ["%10d%10d%10d%10s" % (90, 0, 50, "N")]),
    ("DEFINE_COORDINATE_NODES", "*DEFINE_COORDINATE_NODES", ["%10d%10d%10d%10s" % (7, 1, 2, "N")]),
]


def deck_with(card_kw, card_lines, node, i10=False):
    L = box(i10=i10)
    L.append(card_kw)
    L += [l.replace("         N", "%10d" % node).replace("       N", "%8d" % node) for l in card_lines]
    L.append("*END")
    return "\n".join(L) + "\n"


def node_items(out):
    return re.findall(r"^  line (\d+) (\*\S+): 절점[^\n]*? (\d+) 이 정의되지 않았습니다", out, re.M)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="dnr_")
    try:
        print("[A 갈래마다 — 없는 절점은 잡고 · 있는 절점은 조용하다]")
        for name, kw, lines in FAMILIES:
            write(os.path.join(d, "bad.k"), deck_with(kw, lines, 999))
            rc, out = run(binary, d, "info", "bad.k", "--strict")
            items = node_items(out)
            check("A %-34s 없는 절점 999 → rc 1 · 그 카드를 짚는다" % name,
                  rc == 1 and any(k == kw and v == "999" for _, k, v in items), (rc, items, out[-300:]))
            write(os.path.join(d, "good.k"), deck_with(kw, lines, 3))
            rc, out = run(binary, d, "info", "good.k", "--strict")
            check("A %-34s 있는 절점 3 → rc 0 · 「·절점 미정의 참조 0건」" % name,
                  rc == 0 and not node_items(out) and "·절점 미정의 참조 0건" in out, (rc, out[-300:]))

        print("[B 절점이 아닌 칸은 절점으로 읽지 않는다 — 거짓 경보 없음]")
        cases = [
            ("B-1 `_GENERATE` 범위(빈 번호를 매뉴얼이 허용)", "*SET_NODE_LIST_GENERATE", ["%10d" % 70, "%10d%10d" % (1, 999)]),
            ("B-2 `_ADD` 의 멤버는 세트 ID", "*SET_NODE_ADD", ["%10d" % 71, "%10d" % 50]),
            ("B-3 조인트 강성의 첫 칸은 JSID", "*CONSTRAINED_JOINT_STIFFNESS_GENERALIZED",
             ["%10d%10d%10d%10d%10d%10d" % (999, 1, 1, 0, 0, 0)]),
        ]
        for name, kw, lines in cases:
            L = box() + [kw] + lines + ["*END"]
            write(os.path.join(d, "b.k"), "\n".join(L) + "\n")
            rc, out = run(binary, d, "info", "b.k", "--strict")
            check(name + " → 절점 미정의 0", not node_items(out), (rc, node_items(out), out[-300:]))
        # 강제운동 — |DOF| = 9 면 Card 3(OFFSET1 OFFSET2 LRB NODE1 NODE2)이 붙는다. 그 줄을 Card 1 로 읽으면
        # 실수 칸을 절점으로 읽는다. 그 뒤의 Card 1 은 다시 본다(걸음이 어긋나지 않는다).
        L = box() + ["*BOUNDARY_PRESCRIBED_MOTION_NODE",
                     "%10d%10d%10d%10d%10.3f" % (1, 9, 0, 0, 1.0),
                     "%10.3f%10.3f%10d%10d%10d" % (0.0, 0.0, 0, 888, 0),
                     "%10d%10d%10d%10d%10.3f" % (999, 3, 0, 0, 1.0), "*END"]
        write(os.path.join(d, "pm.k"), "\n".join(L) + "\n")
        rc, out = run(binary, d, "info", "pm.k", "--strict")
        items = node_items(out)
        check("B-4 강제운동 Card 3 을 건너뛰고 그 뒤 Card 1 의 999 를 잡는다",
              [v for _, _, v in items] == ["999"], (items, out[-300:]))
        # 조각 — 맨 `*NODE` 가 하나도 없으면 경계조건만 든 조각이라 단정하지 않는다
        write(os.path.join(d, "frag.k"), "*KEYWORD\n*BOUNDARY_SPC_NODE\n%10d%10d%10d\n*END\n" % (999, 0, 1))
        rc, out = run(binary, d, "info", "frag.k", "--strict")
        check("B-5 `*NODE` 가 없는 조각 덱은 절점 참조를 단정하지 않는다(rc 0)",
              rc == 0 and not node_items(out) and "·절점" not in out, (rc, out[-300:]))

        print("[C 칸 꼴 — 자유형식 · i10 · 인클루드]")
        L = box() + ["*BOUNDARY_SPC_NODE", "999,0,1,1,1,0,0,0", "*END"]
        write(os.path.join(d, "comma.k"), "\n".join(L) + "\n")
        rc, out = run(binary, d, "info", "comma.k", "--strict")
        check("C-1 콤마 자유형식 줄의 없는 절점도 잡는다", rc == 1 and node_items(out), (rc, out[-300:]))
        write(os.path.join(d, "i10.k"), deck_with("*SET_NODE_LIST", ["%10d" % 60, "%10d%10s" % (1, "N")], 999, i10=True))
        rc, out = run(binary, d, "info", "i10.k", "--strict")
        check("C-2 i10 덱 — 없는 절점을 잡는다", rc == 1 and [v for _, _, v in node_items(out)] == ["999"],
              (rc, out[-300:]))
        write(os.path.join(d, "i10g.k"), deck_with("*SET_NODE_LIST", ["%10d" % 60, "%10d%10s" % (1, "N")], 12, i10=True))
        rc, out = run(binary, d, "info", "i10g.k", "--strict")
        check("C-3 i10 덱 — 10칸 절점 번호를 정의로 읽어 거짓 경보가 없다", rc == 0 and not node_items(out),
              (rc, out[-300:]))
        # 인클루드 — 절점이 인클루드 안에 있으면 정의로 친다 · 그 안의 세트가 없는 절점을 가리키면 잡는다
        inc = box()
        write(os.path.join(d, "mesh_inc.k"), "\n".join(inc + ["*END"]) + "\n")
        write(os.path.join(d, "main_ok.k"), "*KEYWORD\n*INCLUDE\nmesh_inc.k\n*BOUNDARY_SPC_NODE\n%10d%10d%10d\n*END\n"
              % (12, 0, 1))
        rc, out = run(binary, d, "info", "main_ok.k", "--strict")
        check("C-4 인클루드 안의 절점을 가리키면 조용하다", rc == 0 and not node_items(out), (rc, out[-300:]))
        write(os.path.join(d, "main_bad.k"), "*KEYWORD\n*INCLUDE\nmesh_inc.k\n*BOUNDARY_SPC_NODE\n%10d%10d%10d\n*END\n"
              % (999, 0, 1))
        rc, out = run(binary, d, "info", "main_bad.k", "--strict")
        check("C-5 인클루드를 다 읽었으면 없는 절점을 단정한다(rc 1)", rc == 1 and node_items(out), (rc, out[-300:]))
        write(os.path.join(d, "main_miss.k"), "*KEYWORD\n*INCLUDE\nmesh_inc.k\n*INCLUDE\nnot_here.k\n"
              "*BOUNDARY_SPC_NODE\n%10d%10d%10d\n*END\n" % (999, 0, 1))
        rc, out = run(binary, d, "info", "main_miss.k", "--strict")
        check("C-6 못 읽은 인클루드가 있으면 단정하지 않는다(rc 0 · 경고)",
              rc == 0 and "못 찾았습니다" in out and not node_items(out), (rc, out[-400:]))

        print("[D meshfix — 같은 자리 새 절점으로 바꿔 쓰고(재결속), 못 풀면 덱을 쓰지 않는다 · preview]")
        g = gmsh_path()
        # ⚠ gmsh 가 없으면 skip 이 아니라 FAIL 이다 — meshfix 시험과 같은 규율(조용히 건너뛰면 결함이 숨는다).
        if not check("D-0 gmsh 를 찾았다(dist/gmsh/gmsh 또는 KOOREMAPPER_GMSH)", bool(g)):
            raise SystemExit
        env = dict(os.environ, KOOREMAPPER_GMSH=g)
        run(binary, d, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo")
        src = open(os.path.join(d, "demo_flat_tet.k")).read().splitlines()
        nodes, mode = {}, None
        for l in src:
            if l.startswith("*"):
                mode = l.strip().upper()
                continue
            if mode == "*NODE" and l.strip() and not l.startswith("$"):
                nodes[int(l[:8])] = tuple(float(l[8 + 16 * k:24 + 16 * k]) for k in range(3))
        lo = [min(p[k] for p in nodes.values()) for k in range(3)]
        hi = [max(p[k] for p in nodes.values()) for k in range(3)]
        corners = sorted(n for n, p in nodes.items()
                         if all(abs(p[k] - lo[k]) < 1e-9 or abs(p[k] - hi[k]) < 1e-9 for k in range(3)))
        endi = max(k for k, l in enumerate(src) if l.strip().upper() == "*END")

        def with_refs(name, ids):
            L = list(src)
            L[endi:endi] = ["*SET_NODE_LIST", "%10d" % 77, "".join("%10d" % n for n in ids[:8]),
                            "*BOUNDARY_SPC_NODE", "%10d%10d%10d%10d%10d" % (ids[0], 0, 1, 1, 1),
                            "*DATABASE_HISTORY_NODE", "".join("%10d" % n for n in ids[:2])]
            write(os.path.join(d, name), "\n".join(L) + "\n")

        with_refs("mf_free.k", corners)

        def coords(path):
            out, mode = {}, None
            for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
                if l.startswith("*"):
                    mode = l.strip().upper()
                    continue
                if mode == "*NODE" and l.strip() and not l.startswith("$"):
                    out[int(l[:8])] = tuple(round(float(l[8 + 16 * k:24 + 16 * k]), 6) for k in range(3))
            return out

        def members(path, kw):
            L = open(path, encoding="utf-8", errors="replace").read().splitlines()
            out, on = [], False
            for l in L:
                if l.startswith("*"):
                    on = (l.strip().upper() == kw)
                    continue
                if on and l.strip() and not l.startswith("$"):
                    out.append([int(x) for x in l.split()])
            return out

        # ★재결속(2026-10-16) — 지울 절점을 가리키는 칸은 **같은 자리의 새 절점**으로 바꿔 쓴다. 판 꼭짓점은 gmsh 가
        # 기하 꼭짓점이라 같은 자리에 절점을 둔다.
        write(os.path.join(d, "mf_free.yaml"), "model: mf_free.k\noutput: mf_free_out.k\npid: 1\nlc_target: 5.0\n")
        rc, out = run(binary, d, "meshfix", "mf_free.yaml", env=env)
        ok = check("D-1 `free`(기본) — 꼭짓점을 가리키는 세트·SPC·이력을 같은 자리 새 절점으로 바꿔 rc 0",
                   rc == 0 and "재결속" in out and os.path.exists(os.path.join(d, "mf_free_out.k")), out[-300:])
        if ok:
            src_xyz, dst_xyz = coords(os.path.join(d, "mf_free.k")), coords(os.path.join(d, "mf_free_out.k"))
            old_set = members(os.path.join(d, "mf_free.k"), "*SET_NODE_LIST")[1]
            new_set = members(os.path.join(d, "mf_free_out.k"), "*SET_NODE_LIST")[1]
            check("D-2 ★바꾼 번호는 원래 절점과 **같은 좌표**이고 옛 번호는 산출에 없다",
                  len(old_set) == len(new_set) and all(src_xyz[o] == dst_xyz[n] for o, n in zip(old_set, new_set)) and
                  not any(o in dst_xyz for o in old_set), (old_set, new_set))
            spc = members(os.path.join(d, "mf_free_out.k"), "*BOUNDARY_SPC_NODE")[0][0]
            check("D-3 SPC 도 같은 자리 새 절점으로", dst_xyz.get(spc) == src_xyz[corners[0]], (spc, corners[0]))
            rc2, out2 = run(binary, d, "info", "mf_free_out.k", "--strict")
            check("D-4 그 산출이 `info --strict` 를 통과한다", rc2 == 0 and not node_items(out2), (rc2, out2[-300:]))

        # 내부 절점 — 다시 짠 메시에 같은 자리 절점이 없다 → 멈추고 덱을 쓰지 않는다
        tm = open(os.path.join(REPO, "examples", "mesh", "tetramesh.k"), encoding="utf-8").read().splitlines()
        tets, mode, pend = [], None, None
        for l in tm:
            if l.startswith("*"):
                mode = l.strip().upper()
                pend = None
                continue
            if mode == "*ELEMENT_SOLID" and l.strip() and not l.startswith("$"):
                t = l.split()
                if len(t) == 2:
                    pend = t
                elif pend is not None:
                    tets.append([int(x) for x in t[:4]])
                    pend = None
        faces = {}
        for t in tets:
            for f in ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)):
                k = tuple(sorted(t[i] for i in f))
                faces[k] = faces.get(k, 0) + 1
        bnd = {n for k, c in faces.items() if c == 1 for n in k}
        interior = sorted({n for t in tets for n in t} - bnd)
        tme = max(k for k, l in enumerate(tm) if l.strip().upper() == "*END")
        tm2 = tm[:tme] + ["*BOUNDARY_SPC_NODE", "%10d%10d%10d%10d%10d" % (interior[len(interior) // 2], 0, 1, 1, 1)] + tm[tme:]
        write(os.path.join(d, "tm_int.k"), "\n".join(tm2) + "\n")
        write(os.path.join(d, "pv.yaml"), "model: tm_int.k\noutput: pv_out.k\npid: 1\nlc_target: 5.0\npreview: true\n")
        rc, out = run(binary, d, "meshfix", "pv.yaml", env=dict(os.environ, KOOREMAPPER_GMSH="/nonexistent/gmsh"))
        check("D-5 `preview` — gmsh 없이 돌고 내부 절점 SPC 를 「멈춘다」로 짚어 rc 1",
              rc == 1 and "내부 절점" in out and "Gmsh not found" not in out, out[-300:])
        check("D-6 `preview` 는 덱을 쓰지 않는다", not os.path.exists(os.path.join(d, "pv_out.k")))
        write(os.path.join(d, "pv2.yaml"), "model: mf_free.k\noutput: pv2_out.k\npid: 1\nlc_target: 5.0\npreview: true\n")
        rc, out = run(binary, d, "meshfix", "pv2.yaml", env=dict(os.environ, KOOREMAPPER_GMSH="/nonexistent/gmsh"))
        check("D-7 `preview` — 표면(꼭짓점)만 가리키면 멈출 칸 0 · rc 0", rc == 0 and "멈출 칸은 없다" in out, out[-300:])
        write(os.path.join(d, "ti.yaml"), "model: tm_int.k\noutput: ti_out.k\npid: 1\nlc_target: 5.0\n")
        rc, out = run(binary, d, "meshfix", "ti.yaml", env=env)
        check("D-8 실제 실행 — 내부 절점 SPC 는 짝이 없어 rc 1 · ★덱을 남기지 않는다",
              rc == 1 and "같은 자리" in out and not os.path.exists(os.path.join(d, "ti_out.k")), out[-300:])
        check("D-9 고칠 길을 말한다(fixed · preview)", "boundary_nodes: fixed" in out and "preview" in out, out[-300:])

        write(os.path.join(d, "mf_fixed.yaml"),
              "model: mf_free.k\noutput: mf_fixed_out.k\npid: 1\nlc_target: 5.0\nboundary_nodes: fixed\n")
        rc, out = run(binary, d, "meshfix", "mf_fixed.yaml", env=env)
        check("D-10 `fixed` — 꼭짓점(표면) 절점만 가리키면 번호가 남아 rc 0", rc == 0 and
              os.path.exists(os.path.join(d, "mf_fixed_out.k")), out[-300:])
        if os.path.exists(os.path.join(d, "mf_fixed_out.k")):
            rc, out = run(binary, d, "info", "mf_fixed_out.k", "--strict")
            check("D-11 그 산출이 `info --strict` 를 통과한다", rc == 0 and not node_items(out), (rc, out[-300:]))
    except SystemExit:
        pass
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
