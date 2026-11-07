#!/usr/bin/env python3
# 새 절점 번호를 내는 단독 op 이 스칼라 절점(*NODE_SCALAR · _VALUE)의 번호를 다시 내지 않는지, 정의 판정이 스칼라 절점을 아는지 보는 회귀 시험
"""스칼라 절점은 절점 번호를 차지한다 (2026-11-07 · 셋째 묶음).

왜 이 시험이 있나.

  `*NODE_SCALAR` · `_VALUE` 의 NID 는 `*NODE` 의 번호와 겹치면 안 된다(Vol_I 214757 「unique relative to other nodes」).
  보 `_WARPAGE` 의 SN1 · SN2 가 그 절점을 가리킨다. 그런데 리더(`KFileReader`)는 `*NODE` 만 담아, 새 절점 번호를 내는 단독 op 이
  스칼라 절점 번호를 몰랐다 — 「`*NODE` 최대 + 1」 이 스칼라 절점 번호와 같으면 LS-DYNA 가 덱에서 멈춘다.
    · tetremesh · meshfix · cclip — 주 덱(리더) · 인클루드(`include_closure::readerMax`)의 `*NODE` 최대 위로만 냈다
    · cnrb2spring — 고정 번호대의 충돌 검사가 `*NODE` 번호만 보았다
  (assemble 계열 · id_floor 는 6341aac 가 고쳤다 · cnrb2solid 는 `*NODE` 로 시작하는 블록을 다 세어 이미 그 위였다 — 여기서 지킨다.)

무엇을 보나.
  op 마다 주 덱(또는 인클루드)에 `*NODE` 최대 + 1 … + 20 을 스칼라 절점으로 두고 돌린다 — 새 절점이 그 번호와 겹치지 않고 그 위다
  (cnrb2spring 은 번호대 안의 스칼라 절점을 「겹친다」 로 거절한다). `info --strict` 는 스칼라 절점을 가리키는 세트 · SPC 를 미정의로
  세지 않는다(정의 판정 `noderefs::defined` 가 `*NODE` 계열 블록의 첫 칸을 다 센다 — 지킴이).

usage: test_scalar_node_ids.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples")
sys.path.insert(0, HERE)
from test_assembler_include_ids import deck_ids, read_lines, split_and_inline, out_path   # noqa: E402

FAILS, OKS = [], []
K = 20   # 둘 스칼라 절점 수 — 새 절점의 첫 번호들과 겹치게


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-86s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def gmsh_path():
    g = os.environ.get("KOOREMAPPER_GMSH") or os.environ.get("KOOREMAPPER_TEST_GMSH")
    if g and os.path.exists(g):
        return g
    g = os.path.join(REPO, "dist", "gmsh", "gmsh")
    return g if os.path.exists(g) else None


def run(binary, cwd, *args):
    env = dict(os.environ)
    if gmsh_path():
        env["KOOREMAPPER_GMSH"] = gmsh_path()
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, p.stdout + p.stderr


def scalar_block(ids):
    return ["*NODE_SCALAR"] + ["%8d%8d" % (v, 1) for v in ids]


def with_scalars(lines, ids):
    """`*KEYWORD` 바로 뒤에 스칼라 절점 블록을 둔다."""
    k = next(i for i, l in enumerate(lines) if l.upper().startswith("*KEYWORD"))
    return lines[:k + 1] + scalar_block(ids) + lines[k + 1:]


def issuer(binary, label, op, base, yaml_tmpl, extra_files=()):
    print("[%s]" % label)
    mx = max(deck_ids(base)["NODE"])
    scal = list(range(mx + 1, mx + 1 + K))
    d = tempfile.mkdtemp(prefix="sni_")
    try:
        for f in extra_files:
            shutil.copy2(f, d)
        main_s = with_scalars(base, scal)                                      # 주 덱에
        x = ["*KEYWORD"] + scalar_block(scal) + ["*END"]
        incl_s, _ = split_and_inline(base, x)                                   # 인클루드에(readerMax 길)
        open(os.path.join(d, "x.k"), "w", encoding="utf-8").write("\n".join(x) + "\n")
        for tag, lines in (("main", main_s), ("incl", incl_s)):
            open(os.path.join(d, tag + ".k"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
            open(os.path.join(d, tag + ".yaml"), "w", encoding="utf-8").write(
                yaml_tmpl.replace("@MODEL@", tag + ".k").replace("@OUT@", "o_" + tag))
            rc, log = run(binary, d, op, tag + ".yaml")
            op_path = out_path(d, "o_" + tag)
            if not check("%s %s — rc 0 · 산출" % (label, tag), rc == 0 and op_path, log[-400:]):
                continue
            new = deck_ids(read_lines(op_path))["NODE"] - deck_ids(lines)["NODE"]
            hit = sorted(new & set(scal))
            check("%s %s ★새 절점(%d)이 스칼라 절점 번호(%d..%d)와 겹치지 않고 그 위다" % (label, tag, len(new), scal[0], scal[-1]),
                  new and not hit and min(new) > scal[-1], (sorted(new)[:5], hit[:5]))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])

    tet_src = open(os.path.join(HERE, "test_misc_ops_yaml_parsing.py"), encoding="utf-8").read()
    s = tet_src.index('TET_MODEL = """') + len('TET_MODEL = """')
    tet = tet_src[s:tet_src.index('"""', s)].splitlines()
    issuer(binary, "tetremesh", "tetremesh", tet,
           "model: @MODEL@\noutput: @OUT@.k\nbackend: localimprove\nquality:\n  min_jacobian: 0.9\n")

    g = tempfile.mkdtemp(prefix="sni_cc_")
    try:
        shutil.copy2(os.path.join(EX, "cclip", "gen_board.yaml"), g)
        run(binary, g, "generate", "box", "gen_board.yaml")
        board = read_lines(os.path.join(g, "clip_board.k"))
    finally:
        shutil.rmtree(g, ignore_errors=True)
    cc_yaml = open(os.path.join(EX, "cclip", "cclip.yaml"), encoding="utf-8").read().replace(
        "model: clip_board.k", "model: @MODEL@").replace("output: clip_board_cclip", "output: @OUT@")
    issuer(binary, "cclip", "cclip", board, cc_yaml)

    if gmsh_path():
        g = tempfile.mkdtemp(prefix="sni_mf_")
        try:
            run(binary, g, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo")
            arc_tet = read_lines(os.path.join(g, "demo_flat_tet.k"))
        finally:
            shutil.rmtree(g, ignore_errors=True)
        issuer(binary, "meshfix", "meshfix", arc_tet, "model: @MODEL@\noutput: @OUT@.k\npid: 1\nlc_target: 5.0\n")
    else:
        print("[meshfix] SKIP — gmsh 실행 파일이 없다(KOOREMAPPER_GMSH · KOOREMAPPER_TEST_GMSH · dist/gmsh/gmsh)")

    bolt = read_lines(os.path.join(EX, "cnrb2solid", "bolt_simple.k"))
    issuer(binary, "cnrb2solid(지킴이)", "cnrb2solid", bolt,
           "model: @MODEL@\noutput: @OUT@\nE: 200000.0\nPR: 0.3\nRHO: 7.85e-9\nradius_scale: 0.999\nnum_circum_nodes: 8\n"
           "inner_radius_ratio: 0.3\naxis_direction: auto\nz_tolerance: 0.1\nr_tolerance: 0.5\n")

    # cnrb2spring — 고정 번호대(node_id_start 90000001 …) 안의 스칼라 절점은 「겹친다」 로 거절해야 한다
    print("[cnrb2spring — 고정 번호대 충돌 검사]")
    from test_cnrb2spring import shell_deck   # noqa: E402 — 그 시험이 쓰는 덱 그대로
    d = tempfile.mkdtemp(prefix="sni_c2sp_")
    try:
        base_cs = shell_deck().splitlines()
        for tag, lines in (("main", with_scalars(base_cs, [90000001])),
                           ("incl", split_and_inline(base_cs, ["*KEYWORD"] + scalar_block([90000001]) + ["*END"])[0])):
            open(os.path.join(d, "x.k"), "w").write("\n".join(["*KEYWORD"] + scalar_block([90000001]) + ["*END"]) + "\n")
            open(os.path.join(d, tag + ".k"), "w").write("\n".join(lines) + "\n")
            open(os.path.join(d, tag + ".yaml"), "w").write(
                "model: %s.k\noutput: o_%s.k\naxis: z\ntarget_pids: [1201]\n" % (tag, tag))
            rc, out = run(binary, d, "cnrb2spring", tag + ".yaml")
            check("cnrb2spring %s ★번호대 안의 스칼라 절점 90000001 → 겹친다고 거절(rc 1)" % tag,
                  rc == 1 and "노드 ID 가 원본 덱과 겹칩니다" in out, (rc, out[-300:]))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 정의 판정 — 스칼라 절점을 가리키는 세트 · SPC · 보 WARPAGE 의 SN 을 미정의로 세지 않는다(지킴이 — 정의 판정은 이미 안다)
    print("[info --strict — 스칼라 절점을 가리키는 참조(지킴이)]")
    d = tempfile.mkdtemp(prefix="sni_info_")
    try:
        L = ["*KEYWORD", "*NODE"] + ["%8d%16.6f%16.6f%16.6f" % (n, float(n), 0.0, 0.0) for n in (101, 102, 103)]
        L += ["*NODE_SCALAR", "%8d%8d" % (201, 1), "*NODE_SCALAR_VALUE", "%8d%16s%16s%16s%8d" % (202, "0.0", "0.0", "0.0", 1)]
        L += ["*ELEMENT_BEAM_WARPAGE", "%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103), "%10d%10d" % (201, 202)]
        L += ["*SET_NODE_LIST", "%10d" % 50, "%10d%10d" % (201, 101), "*BOUNDARY_SPC_NODE",
              "%10d%10d%10d%10d%10d%10d%10d%10d" % (202, 0, 1, 1, 1, 0, 0, 0)]
        L += ["*PART", "beam", "%10d%10d%10d" % (9, 9, 9), "*SECTION_BEAM", "%10d%10d" % (9, 1),
              "*MAT_ELASTIC", "%10d%10s%10s%10s" % (9, "7.85E-9", "210000.", "0.3"), "*END"]
        open(os.path.join(d, "s.k"), "w").write("\n".join(L) + "\n")
        rc, out = run(binary, d, "info", "s.k", "--strict")
        check("info --strict — 스칼라 절점 201 · 202 를 가리키는 세트 · SPC · WARPAGE SN 을 미정의로 세지 않는다",
              "정의되지 않았습니다" not in out and "참조 무결성 OK" in out, out[-400:])
        bad = [l.replace("%10d%10d" % (201, 101), "%10d%10d" % (777, 101)) for l in L]
        open(os.path.join(d, "b.k"), "w").write("\n".join(bad) + "\n")
        rc, out = run(binary, d, "info", "b.k", "--strict")
        check("info --strict 대조 — 정의되지 않은 절점 777 을 가리키는 세트는 잡는다(rc 1)",
              rc == 1 and "절점 777 이 정의되지 않았습니다" in out, out[-400:])
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
