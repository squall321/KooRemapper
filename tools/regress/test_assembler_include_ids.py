#!/usr/bin/env python3
# assemble 경로의 번호 커서가 인클루드 닫힘까지 세는지 보는 회귀 시험 — 쪼갠 덱 = 쪼개지 않은 덱
"""assemble 경로의 번호 커서가 **인클루드 닫힘까지** 세는가 — 쪼갠 덱 = 쪼개지 않은 덱.

왜 이 시험이 있나 (2026-10-16, 장부 P1-3 「ModelAssembler 커서」).

  `ModelAssembler` 의 커서(멤버 일곱 + op 안의 지역 커서)는 **주 덱 파일만** 셌다. `KFileReader` 도
  rawLines_ 도 `*INCLUDE` 안을 읽지 않는다. 실사용 인클루드 덱 88장 중 83장에서 주 덱만 센 NODE·ELEM
  최대값이 닫힘의 최대값보다 작았다(SET 은 38장). 그래서 새 번호가 인클루드에 이미 있는 번호와 겹칠
  수 있었다 — 같은 종류의 ID 가 둘이면 LS-DYNA 는 키워드 단계에서 멈춘다. 경고(P0-6)만 했었다.
  지금은 닫힘을 읽어 **주 덱과 같은 스캐너**로 인클루드 파일마다 센 값 위로 낸다.

신탁 — 둘 다 「LS-DYNA 는 인클루드를 그 자리에 펼쳐 읽는다」에서 나온다.
  ① **쪼갠 덱 M**(주 덱 + `*INCLUDE x.k`)과 **쪼개지 않은 덱 U**(x.k 본문을 그 자리에 둔 덱)는 같은
     모델이다. 그러니 op 이 새로 내는 번호도 같아야 한다.
  ② M 에서 새로 낸 번호가 x.k 에 정의된 번호와 **겹치지 않는다.**
  x.k 는 레인마다 「주 덱 최대값 + 1」 자리에 그 op 이 낼 종류의 번호를 미리 둔다 — 옛 커서가 정확히
  그 번호를 낸다. 레인마다 실제로 번호를 냈는지도 본다(안 내면 헛통과다).

레인 — 커서마다 그것을 쓰는 op 하나.
  czm(NODE·ELEM·PART·SECTION·MAT) · mefem(SET_NODE) · contact+load(SET_SEGMENT·CONTACT·CURVE) ·
  boundary(SET_NODE) · rbe2(SET_NODE·CNRB) · rbe3(SET_NODE·ICID) · matswap(HOURGLASS·CURVE·SECTION·MAT) ·
  matdb(MAT, `loadRawOnly` 길) · restack(NODE·ELEM·PART·SECTION·MAT·SET 한 통)
  단독 발행자(자기 덱을 직접 읽는다) — hfdamp(SET_PART, selective) · cnrb2solid(NODE·ELEM·SECTION·MAT) ·
  ale(MAT·EOS·HGID) · matswap 위치 인자판(HGID·LCID·SECID·MID) · tetremesh(NODE·ELEM) · cclip(NODE·ELEM) ·
  cnrb2spring(고정 대역 — 인클루드의 대역 안 번호를 쪼갠 덱에서도 거절하나) · meshfix(NODE·ELEM, gmsh 있을 때)
덧붙여 보는 것.
  W 인클루드 `*KEYWORD` 의 폭이 주 덱과 다르면 노드·요소 번호를 단정하지 못한다고 말한다(rc 0)
  P `*INCLUDE +` 도 같다(그 파일의 폭을 바꾼다 — Vol_I 19350)
  B 못 읽은 인클루드는 「읽지 않았습니다」를 **한 번** · 이름으로 말하고, 다 읽었으면 조용하다

usage: test_assembler_include_ids.py <KooRemapper 바이너리>
"""
import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples")
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:400]))
    print("  %-66s %s" % (name[:66], "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


# ── 덱에서 번호를 뽑는다 ─────────────────────────────────────────────────────
def _lead(s):
    m = re.match(r"\s*(-?\d+)", s)
    return int(m.group(1)) if m else None


def deck_ids(lines):
    """종류 → 정의된 번호 집합. 키워드마다 그 종류의 ID 가 있는 자리만 본다(1줄 요소 카드 전제)."""
    out = collections.defaultdict(set)
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].startswith("*"):
            i += 1
            continue
        tok = lines[i].split()[0].upper().rstrip("%+-")
        j, data = i + 1, []
        while j < n and not lines[j].startswith("*"):
            s = lines[j]
            if s.strip() and not s.lstrip().startswith("$"):
                data.append(s)
            j += 1
        body = data[1:] if "_TITLE" in tok else data
        first = _lead(body[0]) if body else None

        def put(ns, v):
            if v is not None:
                out[ns].add(v)
        if tok == "*NODE":
            for s in data:
                put("NODE", _lead(s))
        elif tok in ("*ELEMENT_SOLID", "*ELEMENT_SHELL", "*ELEMENT_TSHELL"):
            for s in data:
                put("ELEMENT", _lead(s))
        elif tok == "*PART":
            for k in range(1, len(data), 2):
                put("PART", _lead(data[k]))
        elif tok.startswith("*SECTION_"):
            put("SECTION", first)
        elif tok.startswith("*MAT_") and not tok.startswith("*MAT_ADD"):
            put("MAT", first)
        elif tok.startswith("*SET_"):
            put("SET_" + tok[5:].split("_")[0], first)
            put("SET", first)
        elif tok in ("*DEFINE_CURVE", "*DEFINE_CURVE_TITLE"):
            put("CURVE", first)
        elif tok.startswith("*CONTACT_") and re.search(r"_ID(_|$)", tok):
            put("CONTACT", first)
        elif tok.startswith("*HOURGLASS"):
            put("HOURGLASS", first)
        elif tok.startswith("*EOS_"):
            put("EOS", first)
        elif tok.startswith("*CONSTRAINED_NODAL_RIGID_BODY"):
            put("CNRB", first)
        elif tok.startswith("*CONSTRAINED_INTERPOLATION") and "SPOTWELD" not in tok:
            put("ICID", first)
        i = j
    return out


def read_lines(p):
    return open(p, encoding="utf-8", errors="replace").read().splitlines()


# ── 미리 둘 번호(x.k) ────────────────────────────────────────────────────────
def blockers(ids, kinds, extra_set_node=(), kw="*KEYWORD"):
    """주 덱 `ids` 의 최대값 + 1 자리에 `kinds` 의 번호를 둔 인클루드 본문.

    노드·요소 카드는 `%`(I10)로 쓴다 — 주 덱 폭과 무관하게 같은 칸으로 읽힌다(Vol_I 19353).
    세트는 **그 종류의 최대 + 1** 과 **모든 종류 한 통의 최대 + 1** 둘 다 둔다 — 지역 커서는 종류별로,
    멤버 커서(`maxSetId_`)는 한 통으로 센다.
    """
    mx = lambda ns: max(ids.get(ns, {0}) or {0})
    L = [kw]
    nodes = [mx("NODE") + k for k in range(1, 9)]
    if "mesh" in kinds:
        P, S, M, E = mx("PART") + 1, mx("SECTION") + 1, mx("MAT") + 1, mx("ELEMENT") + 1
        L.append("*NODE %")
        for k, nid in enumerate(nodes):
            x, y, z = 1.0e4 + (k & 1), 1.0e4 + ((k >> 1) & 1), 1.0e4 + ((k >> 2) & 1)
            L.append("%10d%16.6f%16.6f%16.6f" % (nid, x, y, z))
        L += ["*PART", "include blocker", "%10d%10d%10d" % (P, S, M),
              "*SECTION_SOLID", "%10d%10d" % (S, 1),
              "*MAT_ELASTIC", "%10d%10s%10s%10s" % (M, "7.85E-9", "210000.", "0.3"),
              "*ELEMENT_SOLID %", "%10d%10d" % (E, P) + "".join("%10d" % nodes[k] for k in (0, 1, 3, 2, 4, 5, 7, 6))]
    if "SECTION" in kinds and "mesh" not in kinds:
        L += ["*SECTION_SOLID", "%10d%10d" % (mx("SECTION") + 1, 1)]
    if "MAT" in kinds and "mesh" not in kinds:
        L += ["*MAT_ELASTIC", "%10d%10s%10s%10s" % (mx("MAT") + 1, "7.85E-9", "210000.", "0.3")]
    member = 1   # 세트 구성원 — 주 덱 절점 1..4 를 쓴다(인클루드도 주 덱 절점을 가리킬 수 있다)
    for ns, kwd in (("SET_NODE", "*SET_NODE_LIST"), ("SET_SEGMENT", "*SET_SEGMENT"), ("SET_PART", "*SET_PART_LIST")):
        if ns not in kinds:
            continue
        sids = {mx(ns) + 1, mx("SET") + 1} | (set(extra_set_node) if ns == "SET_NODE" else set())
        for sid in sorted(sids):
            L += [kwd, "%10d" % sid]
            # 세트 구성원 — 절점·세그먼트는 주 덱 절점 1..4, 파트 세트는 주 덱 파트 1
            L.append("%10d" % 1 if ns == "SET_PART" else
                     "%10d%10d%10d%10d" % (member, member + 1, member + 2, member + 3))
    if "CURVE" in kinds:
        L += ["*DEFINE_CURVE", "%10d" % (mx("CURVE") + 1), "%20.6f%20.6f" % (0.0, 0.0), "%20.6f%20.6f" % (1.0, 1.0)]
    if "CONTACT" in kinds:
        seg = mx("SET_SEGMENT") + 1
        L += ["*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID", "%10d%s" % (mx("CONTACT") + 1, "include blocker"),
              "%10d%10d%10d%10d" % (seg, seg, 0, 0), "", ""]
    if "EOS" in kinds:
        L += ["*EOS_LINEAR_POLYNOMIAL", "%10d%10s%10s" % (mx("EOS") + 1, "0.0", "0.0"), "%10s%10s" % ("0.0", "1.0")]
    if "HOURGLASS" in kinds:
        L += ["*HOURGLASS", "%10d%10d%10s" % (mx("HOURGLASS") + 1, 5, "0.05")]
    if "CNRB" in kinds:
        L += ["*CONSTRAINED_NODAL_RIGID_BODY", "%10d%10d%10d" % (mx("CNRB") + 1, 0, mx("SET_NODE") + 1)]
    if "ICID" in kinds:
        L += ["*CONSTRAINED_INTERPOLATION", "%10d%10d%10d%10d%10d" % (mx("ICID") + 1, 1, 123456, 0, 1),
              "%10d%10d%10s" % (mx("SET_NODE") + 1, 123, "1.0")]
    L.append("*END")
    return L


def split_and_inline(main_lines, x_lines, inc_card="*INCLUDE"):
    """M(주 덱 + *INCLUDE x.k)과 U(그 자리에 x.k 본문)를 만든다 — 자리는 `*KEYWORD` 바로 뒤."""
    k = next(i for i, l in enumerate(main_lines) if l.upper().startswith("*KEYWORD"))
    body = [l for l in x_lines if not l.upper().startswith(("*KEYWORD", "*END"))]
    m = main_lines[:k + 1] + [inc_card, "x.k"] + main_lines[k + 1:]
    u = main_lines[:k + 1] + body + main_lines[k + 1:]
    return m, u


def out_path(d, name):
    for p in (os.path.join(d, name), os.path.join(d, name + ".k")):
        if os.path.exists(p):
            return p
    return None


def lane(binary, label, cmd, base_lines, yaml_tmpl, kinds, extra_files=(), extra_set_node=()):
    print("[%s]" % label)
    ids_main = deck_ids(base_lines)
    kw = next(l for l in base_lines if l.upper().startswith("*KEYWORD")).strip()
    x = blockers(ids_main, kinds, extra_set_node, kw=kw)
    m_lines, u_lines = split_and_inline(base_lines, x)
    x_ids = deck_ids(x)
    res = {}
    d = tempfile.mkdtemp(prefix="aii_")
    try:
        for f in extra_files:
            shutil.copy2(f, d)
        open(os.path.join(d, "x.k"), "w", encoding="utf-8").write("\n".join(x) + "\n")
        for tag, lines in (("M", m_lines), ("U", u_lines)):
            open(os.path.join(d, tag + ".k"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
            sub = lambda s: s.replace("@MODEL@", tag + ".k").replace("@OUT@", "o" + tag)
            if yaml_tmpl is None:                    # 위치 인자 op — 명령줄 틀에 그대로 넣는다
                rc, log = run(binary, d, *[sub(a) for a in cmd])
            else:
                open(os.path.join(d, tag + ".yaml"), "w", encoding="utf-8").write(sub(yaml_tmpl))
                rc, log = run(binary, d, *(cmd + [tag + ".yaml"]))
            op = out_path(d, "o" + tag)
            if not check("%s %s — rc 0 · 산출" % (label, tag), rc == 0 and op, log[-400:]):
                return
            res[tag] = (deck_ids(read_lines(op)), deck_ids(lines), log)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    def issued(tag):
        after, before, _ = res[tag]
        return {ns: after[ns] - before.get(ns, set()) for ns in after if after[ns] - before.get(ns, set())}
    im, iu = issued("M"), issued("U")
    want = LANE_ISSUES[label]
    check("%s — 실제로 번호를 냈다(%s)" % (label, ",".join(sorted(iu))), all(iu.get(w) for w in want),
          "U 가 낸 것=%s · 기대=%s" % (sorted(iu), want))
    same = {ns for ns in set(im) | set(iu) if im.get(ns, set()) != iu.get(ns, set())}
    check("%s ① 쪼갠 덱 = 쪼개지 않은 덱" % label, not same,
          {ns: (sorted(im.get(ns, ()))[:6], sorted(iu.get(ns, ()))[:6]) for ns in sorted(same)})
    hit = {ns: sorted(im[ns] & x_ids[ns])[:6] for ns in im if ns in x_ids and im[ns] & x_ids[ns]}
    check("%s ② 인클루드의 번호와 겹치지 않는다" % label, not hit, hit)
    # 로더의 문구만 본다 — PIDREF 검사(restack)는 인클루드 안을 아직 안 찾아 자기 문구로 그렇다고 말한다
    check("%s — 다 읽었으면 로더가 조용하다" % label, "곳을 읽지 않았습니다" not in res["M"][2],
          res["M"][2][-300:])


# 레인이 반드시 내야 하는 종류(헛통과 막이). 키는 레인 이름.
LANE_ISSUES = {
    "czm": ["NODE", "ELEMENT", "PART", "SECTION", "MAT"],
    "mefem": ["SET_NODE"],
    "contact+load": ["SET_SEGMENT", "CONTACT", "CURVE"],
    "boundary": ["SET_NODE"],
    "rbe2": ["SET_NODE", "CNRB", "NODE"],
    "rbe3": ["ICID", "NODE"],          # spider rbe3 은 세트를 안 만들고 중심 노드 하나를 낸다(실측)
    "matswap": ["HOURGLASS", "CURVE", "SECTION", "MAT"],
    "matdb": ["MAT"],
    "restack": ["NODE", "ELEMENT", "PART", "SECTION", "MAT", "SET"],
    # ── 단독 발행자(자기 덱을 직접 읽는다) ──
    "hfdamp": ["SET_PART"],
    "cnrb2solid": ["NODE", "ELEMENT", "SECTION", "MAT"],
    "ale": ["MAT", "EOS", "HOURGLASS"],
    "matswap(위치 인자)": ["HOURGLASS", "CURVE", "SECTION", "MAT"],
    "tetremesh": ["NODE", "ELEMENT"],
    "cclip": ["NODE", "ELEMENT"],
    "meshfix": ["NODE", "ELEMENT"],
}

BOX = ("output: flat.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\n"
       "pid: 1\nmid: 1\nsecid: 1\n")
RESTACK = """base_model: @MODEL@
output: @OUT@
operations:
  - type: restack
    target_pid: 1
    direction: z
    element_type: solid
    interface_contact: tied
    pid_refs: warn          # 인클루드 덱에서 PIDREF 검사가 strict 로 거절한다 — 이 시험의 대상이 아니다
    layers:
      - title: Top
        thickness: 0.7
        num_elements: 2
        element_type: solid
        material_card: |
          *MAT_ELASTIC
                   @MID@   2.5E-9     71000      0.23
      - title: Glue
        thickness: 0.2
        num_elements: 1
        element_type: shell     # 셸 층이 끼어야 접촉 세트를 `maxSetId_` 로 낸다(솔리드끼리는 세트가 없다)
        material_card: |
          *MAT_ELASTIC
                   @MID@   1.1E-9      3000      0.35
      - title: Bottom
        thickness: 0.5
        num_elements: 1
        element_type: solid
        material_card: |
          *MAT_ELASTIC
                   @MID@   2.5E-9     71000      0.23
"""


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    two_hex = read_lines(os.path.join(EX, "disconnect", "two_hex_2part.k"))
    mesh = read_lines(os.path.join(EX, "load", "mesh.k"))
    cubes = read_lines(os.path.join(EX, "matswap", "two_cubes.k"))
    rubber = os.path.join(EX, "matswap", "rubber.k")
    mdb = os.path.join(REPO, "materials", "material_db.json")
    asm = ["assemble"]

    lane(binary, "czm", asm, two_hex,
         "base_model: @MODEL@\noutput: @OUT@\noperations:\n  - type: disconnect\n    mode: czm\n    target_pid: 0\n",
         ["mesh"])
    # mefem 의 관례 바닥은 「PID 최대 + 1000」 — 옛 커서가 정확히 그 번호를 낸다
    lane(binary, "mefem", asm, two_hex,
         "base_model: @MODEL@\noutput: @OUT@\noperations:\n  - type: disconnect\n    mode: mefem\n    target_pid: 0\n",
         ["SET_NODE"], extra_set_node=[max(deck_ids(two_hex)["PART"]) + 1000])
    lane(binary, "contact+load", asm, mesh,
         "base_model: @MODEL@\noutput: @OUT@\noperations:\n"
         "  - type: contact\n    actions:\n      - action: detect\n        scope: all\n        type: tied\n"
         "        auto_create: true\n        tolerance: 0.1\n        title_prefix: AUTO\n"
         "  - type: load\n    loads:\n      - part: 10\n        mode: pressure\n        value: 1.0\n"
         "        direction: [0, 0, 1]\n        select: tied\n        angle: 45.0\n"
         "        curve:\n          - [0.0, 0.0]\n          - [0.001, 1.0]\n",
         ["SET_SEGMENT", "CONTACT", "CURVE"])
    lane(binary, "boundary", asm, mesh,
         "base_model: @MODEL@\noutput: @OUT@\noperations:\n  - type: boundary\n    boundaries:\n"
         "      - part: 9\n        dof: all\n        direction: [0, 0, -1]\n        select: direction\n"
         "        angle: 45.0\n",
         ["SET_NODE"])
    for t in ("rbe2", "rbe3"):
        lane(binary, t, ["rbe"], mesh,
             "model: @MODEL@\noutput: @OUT@.k\nrbe:\n  - part: 9\n    select: direction\n"
             "    direction: [0, 0, -1]\n    angle: 45.0\n    type: %s\n    mode: spider\n" % t,
             ["mesh", "SET_NODE", "CNRB" if t == "rbe2" else "ICID"])
    lane(binary, "matswap", ["matswap"], cubes,
         "model: @MODEL@\noutput: @OUT@\nswaps:\n  - bundle: rubber.k\n    pid: 1\n",
         ["HOURGLASS", "CURVE", "SECTION", "MAT"], extra_files=[rubber])
    lane(binary, "matdb", ["matdb"], cubes,
         "model: @MODEL@\noutput: @OUT@\ndatabase: material_db.json\nmat_type: MAT_ELASTIC\n"
         "materials:\n  - match_part: \"*\"\n    mid: 1\n",
         ["MAT"], extra_files=[mdb])

    # restack — 생성한 상자 위에서(세트 멤버 커서 `maxSetId_` 를 쓰는 길)
    g = tempfile.mkdtemp(prefix="aii_box_")
    try:
        open(os.path.join(g, "box.yaml"), "w").write(BOX)
        run(binary, g, "generate", "box", "box.yaml")
        flat = read_lines(os.path.join(g, "flat.k"))
    finally:
        shutil.rmtree(g, ignore_errors=True)
    lane(binary, "restack", asm, flat, RESTACK, ["mesh", "SET_SEGMENT"])

    # ── 단독 발행자 — 자기 덱을 직접 읽는 op 도 같은 신탁으로 본다(2026-10-16) ──
    box = read_lines(os.path.join(EX, "assemble", "box.k"))
    lane(binary, "hfdamp", ["hfdamp"], box,
         "model: @MODEL@\noutput: @OUT@\ndt_target: 1.0e-3\ncdamp: 0.99\nfhigh_ratio: 100.0\n"
         "mode: selective\ntssfac: 0.9\n", ["SET_PART"])
    bolt = read_lines(os.path.join(EX, "cnrb2solid", "bolt_simple.k"))
    lane(binary, "cnrb2solid", ["cnrb2solid"], bolt,
         "model: @MODEL@\noutput: @OUT@\nE: 200000.0\nPR: 0.3\nRHO: 7.85e-9\nradius_scale: 0.999\n"
         "num_circum_nodes: 8\ninner_radius_ratio: 0.3\naxis_direction: auto\nz_tolerance: 0.1\n"
         "r_tolerance: 0.5\n", ["mesh"])
    ale_deck = read_lines(os.path.join(EX, "ale", "explicit.k"))
    lane(binary, "ale", ["ale"], ale_deck,
         "model: @MODEL@\noutput: @OUT@\nale_parts:\n  - pid: 3\n    material: air\n",
         ["MAT", "EOS", "HOURGLASS", "SECTION"])
    lane(binary, "matswap(위치 인자)", ["matswap", "@MODEL@", "rubber.k", "1", "@OUT@.k"], cubes, None,
         ["HOURGLASS", "CURVE", "SECTION", "MAT"], extra_files=[rubber])
    tet_src = open(os.path.join(HERE, "test_misc_ops_yaml_parsing.py"), encoding="utf-8").read()
    s = tet_src.index('TET_MODEL = """') + len('TET_MODEL = """')
    tet = tet_src[s:tet_src.index('"""', s)].splitlines()
    lane(binary, "tetremesh", ["tetremesh"], tet,
         "model: @MODEL@\noutput: @OUT@.k\nbackend: localimprove\nquality:\n  min_jacobian: 0.9\n", ["mesh"])
    g = tempfile.mkdtemp(prefix="aii_cc_")
    try:
        shutil.copy2(os.path.join(EX, "cclip", "gen_board.yaml"), g)
        run(binary, g, "generate", "box", "gen_board.yaml")
        board = read_lines(os.path.join(g, "clip_board.k"))
    finally:
        shutil.rmtree(g, ignore_errors=True)
    cc_yaml = open(os.path.join(EX, "cclip", "cclip.yaml"), encoding="utf-8").read().replace(
        "model: clip_board.k", "model: @MODEL@").replace("output: clip_board_cclip", "output: @OUT@")
    lane(binary, "cclip", ["cclip"], board, cc_yaml, ["mesh"])

    # meshfix — gmsh 가 있어야 돈다(없으면 건너뛰고 그렇다고 말한다)
    gm = os.path.join(REPO, "dist", "gmsh", "gmsh")
    if os.path.exists(gm):
        os.environ["KOOREMAPPER_GMSH"] = gm
    if os.path.exists(gm) or shutil.which("gmsh"):
        g = tempfile.mkdtemp(prefix="aii_mf_")
        try:
            run(binary, g, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo")
            arc_tet = read_lines(os.path.join(g, "demo_flat_tet.k"))
        finally:
            shutil.rmtree(g, ignore_errors=True)
        lane(binary, "meshfix", ["meshfix"], arc_tet,
             "model: @MODEL@\noutput: @OUT@.k\npid: 1\nlc_target: 5.0\n", ["mesh"])
    else:
        print("[meshfix] SKIP — gmsh 실행 파일이 없다(dist/gmsh/gmsh · PATH)")

    # ── cnrb2spring — 「최대 + 1」이 아니라 **고정 대역 + 충돌 검사**다 ─────────────────
    # 신탁이 다르다 — 인클루드에 대역 안 번호가 있으면 쪼갠 덱도 쪼개지 않은 덱처럼 **거절**해야 한다
    # (옛 판은 인클루드를 검사 코퍼스에 안 넣어 「겹침 없음」으로 지나갔다).
    print("[cnrb2spring — 고정 대역 충돌 검사]")
    sys.path.insert(0, HERE)
    from test_cnrb2spring import shell_deck                     # 그 시험이 쓰는 덱 그대로
    d = tempfile.mkdtemp(prefix="aii_c2sp_")
    try:
        base_cs = shell_deck().splitlines()
        x_cs = ["*KEYWORD", "*NODE", "%8d%16.6f%16.6f%16.6f" % (90000001, 5.0e3, 5.0e3, 5.0e3), "*END"]
        m_cs, u_cs = split_and_inline(base_cs, x_cs)
        open(os.path.join(d, "x.k"), "w").write("\n".join(x_cs) + "\n")
        res_cs = {}
        for tag, lines in (("M", m_cs), ("U", u_cs)):
            open(os.path.join(d, tag + ".k"), "w").write("\n".join(lines) + "\n")
            open(os.path.join(d, tag + ".yaml"), "w").write(
                "model: %s.k\noutput: o%s.k\naxis: z\ntarget_pids: [1201]\n" % (tag, tag))
            res_cs[tag] = run(binary, d, "cnrb2spring", tag + ".yaml")
        clash = lambda out: "노드 ID 가 원본 덱과 겹칩니다" in out
        check("cnrb2spring U — 인라인 대역 충돌을 거절한다(rc 1)", res_cs["U"][0] == 1 and clash(res_cs["U"][1]),
              res_cs["U"][1][-300:])
        check("cnrb2spring ① 쪼갠 덱도 같은 이유로 거절한다", res_cs["M"][0] == 1 and clash(res_cs["M"][1]),
              res_cs["M"][1][-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ── W · P · B — 단정 못 하는 자리를 말하나 ───────────────────────────────
    print("[W·P·B 경고]")
    d = tempfile.mkdtemp(prefix="aii_w_")
    try:
        ids = deck_ids(mesh)
        yaml = ("base_model: @MODEL@\noutput: @OUT@\noperations:\n  - type: boundary\n    boundaries:\n"
                "      - part: 9\n        dof: all\n        direction: [0, 0, -1]\n        select: direction\n"
                "        angle: 45.0\n")

        def go(tag, main_lines, files):
            open(os.path.join(d, tag + ".k"), "w").write("\n".join(main_lines) + "\n")
            for name, body in files.items():
                open(os.path.join(d, name), "w").write(body)
            open(os.path.join(d, tag + ".yaml"), "w").write(
                yaml.replace("@MODEL@", tag + ".k").replace("@OUT@", "o" + tag))
            return run(binary, d, "assemble", tag + ".yaml")

        x_plain = blockers(ids, ["mesh"], kw="*KEYWORD")        # 주 덱은 i10 — 폭이 갈린다
        m, _ = split_and_inline(mesh, x_plain)
        rc, out = go("w", m, {"x.k": "\n".join(x_plain) + "\n"})
        check("W 폭이 갈리면 노드·요소 번호를 단정 못 한다고 말한다(rc 0)",
              rc == 0 and "단정하지" in out and "x.k" in out, out[-300:])
        x_i10 = blockers(ids, ["mesh"], kw=next(l for l in mesh if l.upper().startswith("*KEYWORD")))
        m, _ = split_and_inline(mesh, x_i10, inc_card="*INCLUDE +")
        rc, out = go("p", m, {"x.k": "\n".join(x_i10) + "\n"})
        check("P `*INCLUDE +` 도 단정 못 한다고 말한다(rc 0)",
              rc == 0 and "단정하지" in out and "*INCLUDE +" in out, out[-300:])
        m, _ = split_and_inline(mesh, x_i10)
        rc, out = go("ok", m, {"x.k": "\n".join(x_i10) + "\n"})
        check("W 폭이 같으면 조용하다", rc == 0 and "단정하지" not in out, out[-300:])
        k = next(i for i, l in enumerate(mesh) if l.upper().startswith("*KEYWORD"))
        rc, out = go("b", mesh[:k + 1] + ["*INCLUDE", "gone.k"] + mesh[k + 1:], {})
        check("B 못 읽은 인클루드 — 「읽지 않았습니다」 한 번 · 이름 · rc 0",
              rc == 0 and out.count("읽지 않았습니다") == 1 and "못 본 인클루드" in out and "gone.k" in out,
              "n=%d rc=%d %s" % (out.count("읽지 않았습니다"), rc, out[-300:]))
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
