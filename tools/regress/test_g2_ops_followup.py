# squeeze/map 의 쉘 EID 중복·stabilize level 0·load 도움말 진위·merge 미지원 재질 안내·assemble loads 검증·곡면 generate-var 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_g2_ops_followup.py <KooRemapper 바이너리>

배경
  - writeFileWithSource 는 *ELEMENT_SOLID 만 갈아끼우는데 KFileReader 는 *ELEMENT_SHELL/*ELEMENT_TSHELL 도
    mesh.elements 에 넣어, squeeze/map/shellmap 출력 한 덱에 같은 EID 가 두 번 나왔다(rc=0 으로 조용히).
    *ELEMENT_SOLID_ORTHO 는 파서가 읽지 않는데 블록째 skip 돼 통째로 사라졌다.
  - stabilize 의 level: 0 은 examples/explicit/full_manual.yaml 과 MCP 카탈로그가 안내하는 수동 모드인데
    허용값을 1~12 로 좁히면서 rc=1 로 막혔다.
  - `help load` 는 mode: gravity / select: all 을 안내하는데 같은 바이너리가 그 값을 rc=1 로 거절했다.
  - merge 재질 파서는 *MAT_ELASTIC/024/076/020 만 알아 *MAT_PLASTIC_KINEMATIC 등이 걸리면 rc=1 인데
    'MID 3 not found in material DB' 라고만 찍고, 실패가 확정된 그룹의 Homogenized 요약까지 찍었다.
  - 같은 loads 조각이 단독 load 에서는 rc=1, assemble 안에서는 rc=0 으로 통과했다.
  - generate-var --no-scale 은 곡면(type: curved) 경로도 reference.dimensions 를 그대로 쓴다
    (도움말이 "use YAML lengths as-is" 라 반대로 읽혔다).
"""
import os
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRATCH = os.path.join(REPO, "build", "scratch")

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 4\nny: 2\nnz: 1\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")

SQ = "parts:\n  - pid: 1\n    eps_x: 0.0\n    eps_y: 0.0\n    eps_z: -0.01\nmaterial:\n  E: 210000.0\n  nu: 0.3\n"

SHELL_BLOCK = """*PART
Shell_Part
       2       2       2
*SECTION_SHELL
       2       2
       1.0       1.0       1.0       1.0
*MAT_ELASTIC
       2 7.850E-09  210000.0       0.3
*ELEMENT_SHELL
    9001       2       1       2       7       6
    9002       2       2       3       8       7
"""

TSHELL_BLOCK = """*ELEMENT_TSHELL
    8001       1       1       2       7       6      11      12      17      16
"""

ORTHO_BLOCK = """*ELEMENT_SOLID_ORTHO
    6001       1
       1       2       7       6      11      12      17      16
       1.0       0.0       0.0
       0.0       1.0       0.0
"""

GV_CURVED = """type: curved
reference:
  dimensions:
    length_i: 100.0
    length_j: 20.0
    length_k: 4.0
centerline_points:
  - [0, 0]
  - [50, 0]
  - [100, 50]
interpolation: linear
cross_section:
  width: 10.0
  thickness: 2.0
elements_along_curve: 20
elements_j: 3
elements_k: 2
"""


def check(name, cond, detail=""):
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def mkd(prefix):
    os.makedirs(SCRATCH, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=SCRATCH)


def write(d, name, text):
    open(os.path.join(d, name), "w").write(text)


def append(d, name, text):
    """*END 앞에 블록을 끼워 넣은 새 .k 를 만든다."""
    src = open(os.path.join(d, name)).read()
    i = src.rindex("*END")
    return src[:i] + text + src[i:]


def eids_under(path, keyword):
    """주어진 *KEYWORD 블록 안 데이터 줄들의 첫 필드(EID) 목록."""
    out = []
    inblk = False
    for l in open(path, errors="replace").read().splitlines():
        if l.startswith("*"):
            inblk = l.split()[0].upper() == keyword
            continue
        if not inblk or l.startswith("$") or not l.strip():
            continue
        try:
            out.append(int(l[:8]))
        except ValueError:
            pass
    return out


def nodes(path):
    xs = []
    lines = open(path).read().splitlines()
    i = lines.index("*NODE")
    for l in lines[i + 1:]:
        if l.startswith("*"):
            break
        if l.startswith("$") or not l.strip():
            continue
        xs.append((float(l[8:24]), float(l[24:40]), float(l[40:56])))
    return xs


def extent(path):
    p = nodes(path)
    return [max(x[i] for x in p) - min(x[i] for x in p) for i in range(3)]


def test_squeeze_element_ids(binary):
    print("[squeeze — 쉘/티쉘이 있어도 EID 가 중복되지 않는다]")
    d = mkd("g2_eid_")
    write(d, "box.yaml", BOX)
    run(binary, d, "generate", "box", "box.yaml")
    write(d, "sq.yaml", SQ)

    solids = len(eids_under(os.path.join(d, "box.k"), "*ELEMENT_SOLID"))
    check("기준: 생성한 box.k 에 솔리드 요소가 있다", solids > 0, f"solids={solids}")

    write(d, "box_shell.k", append(d, "box.k", SHELL_BLOCK))
    rc, out = run(binary, d, "squeeze", "box_shell.k", "sq.yaml", "sh")
    shp = os.path.join(d, "sh.k")
    ok = rc == 0 and os.path.exists(shp)
    check("쉘이 있는 덱도 rc=0 + 출력 생성", ok, f"rc={rc} {out[-200:]}")
    if ok:
        sol = eids_under(shp, "*ELEMENT_SOLID")
        shl = eids_under(shp, "*ELEMENT_SHELL")
        check("쉘 EID 9001/9002 는 *ELEMENT_SHELL 에만 (예전엔 *ELEMENT_SOLID 에도 찍혀 덱에 2번)",
              sorted(shl) == [9001, 9002] and 9001 not in sol and 9002 not in sol,
              f"solid={sol[:5]}... shell={shl}")
        check("덱 전체에 중복 EID 없음", len(sol + shl) == len(set(sol + shl)),
              f"n={len(sol+shl)} uniq={len(set(sol+shl))}")
        check("솔리드 요소는 하나도 빠지지 않음", len(sol) == solids, f"{len(sol)} != {solids}")

    write(d, "box_ts.k", append(d, "box.k", TSHELL_BLOCK))
    rc, out = run(binary, d, "squeeze", "box_ts.k", "sq.yaml", "ts")
    tsp = os.path.join(d, "ts.k")
    ok = rc == 0 and os.path.exists(tsp)
    check("티쉘이 있는 덱도 rc=0 + 출력 생성", ok, f"rc={rc} {out[-200:]}")
    if ok:
        sol = eids_under(tsp, "*ELEMENT_SOLID")
        tsh = eids_under(tsp, "*ELEMENT_TSHELL")
        check("티쉘 EID 8001 은 *ELEMENT_TSHELL 에만 (예전엔 *ELEMENT_SOLID 에도)",
              tsh == [8001] and 8001 not in sol, f"solid={sol[:5]}... tshell={tsh}")

    write(d, "box_or.k", append(d, "box.k", ORTHO_BLOCK))
    rc, out = run(binary, d, "squeeze", "box_or.k", "sq.yaml", "or")
    orp = os.path.join(d, "or.k")
    ok = rc == 0 and os.path.exists(orp)
    check("*ELEMENT_SOLID_ORTHO 가 있는 덱도 rc=0", ok, f"rc={rc} {out[-200:]}")
    if ok:
        txt = open(orp, errors="replace").read()
        check("*ELEMENT_SOLID_ORTHO 블록이 그대로 남는다 (예전엔 블록째 사라졌다)",
              "*ELEMENT_SOLID_ORTHO" in txt and "    6001" in txt, txt[-300:])


def test_stabilize_level_zero(binary):
    print("[stabilize — 문서에 적힌 수동 모드 level: 0]")
    d = mkd("g2_stab_")
    write(d, "box.yaml", BOX)
    run(binary, d, "generate", "box", "box.yaml")

    write(d, "st0.yaml", "model: box.k\noutput: st0.k\nstabilize: explicit\ntssfac: 0.80\nihq: 4\nlevel: 0\n")
    rc, out = run(binary, d, "stabilize", "st0.yaml")
    p = os.path.join(d, "st0.k")
    check("level: 0 은 수동 모드로 rc=0 + 출력 생성", rc == 0 and os.path.exists(p), f"rc={rc} {out[-200:]}")
    if os.path.exists(p):
        txt = open(p, errors="replace").read()
        check("level: 0 출력에 *CONTROL_TIMESTEP 이 1개", txt.count("*CONTROL_TIMESTEP") == 1,
              str(txt.count("*CONTROL_TIMESTEP")))

    for lv in ("-1", "13", "abc"):
        write(d, f"stx{lv}.yaml", f"model: box.k\noutput: stx{lv}.k\nstabilize: explicit\nlevel: {lv}\n")
        rc, out = run(binary, d, "stabilize", f"stx{lv}.yaml")
        check(f"level: {lv} 는 여전히 rc=1 + 0~12 안내", rc == 1 and "0~12" in out
              and not os.path.exists(os.path.join(d, f"stx{lv}.k")), f"rc={rc} {out[-200:]}")


def test_load_help_truth(binary):
    print("[load — 도움말이 안내하는 값이 실제로 통과한다]")
    d = mkd("g2_help_")
    rc, out = run(binary, d, "help", "load")
    check("help load 는 구현 안 된 mode: gravity 를 더는 안내하지 않는다", "gravity" not in out.lower(),
          out[:400])
    check("help load 는 select: all 을 더는 안내하지 않는다",
          "| all" not in out and "All exposed faces" not in out, out[:400])
    check("help load 가 실제 허용값 normal_pressure / set 을 안내한다",
          "normal_pressure" in out and "set" in out, out[:400])

    write(d, "box.yaml", BOX)
    run(binary, d, "generate", "box", "box.yaml")
    for mode in ("pressure", "force", "normal_pressure"):
        for sel in ("direction", "tied"):
            name = f"l_{mode}_{sel}"
            write(d, name + ".yaml",
                  f"model: box.k\noutput: {name}.k\nloads:\n  - part: 1\n    mode: {mode}\n"
                  f"    value: 1.0\n    direction: [0, 0, 1]\n    select: {sel}\n    angle: 45.0\n")
            rc, out = run(binary, d, "load", name + ".yaml")
            check(f"help 가 적은 조합 mode: {mode} / select: {sel} → rc=0", rc == 0, f"rc={rc} {out[-200:]}")

    write(d, "l_set.yaml", "model: box.k\noutput: l_set.k\nloads:\n  - part: 1\n    mode: pressure\n"
                           "    value: 1.0\n    direction: [0, 0, 1]\n    select: set\n    set_id: 1\n")
    rc, out = run(binary, d, "load", "l_set.yaml")
    check("help 가 적은 select: set (+ set_id) → rc=0", rc == 0, f"rc={rc} {out[-200:]}")


def test_merge_unknown_material(binary):
    print("[merge — 재질 파서가 모르는 *MAT 은 이유를 알려준다]")
    d = mkd("g2_merge_")
    src = open(os.path.join(REPO, "examples", "merge", "three_layer.k"), errors="replace").read()
    check("기준 덱에 *MAT_PIECEWISE_LINEAR_PLASTICITY 가 있다",
          "*MAT_PIECEWISE_LINEAR_PLASTICITY" in src.upper(), "")
    swapped = src.replace("*MAT_PIECEWISE_LINEAR_PLASTICITY", "*MAT_PLASTIC_KINEMATIC")
    write(d, "pk.k", swapped)
    write(d, "pk.yaml", "model: pk.k\noutput: pk_out.k\ndirection: z\nmethod: vrh\n"
                        "merge:\n  - pids: [1, 2, 3]\n    name: H\n")
    rc, out = run(binary, d, "merge", "pk.yaml")
    check("모르는 재질이 걸린 그룹은 rc=1 + 출력 없음",
          rc == 1 and not os.path.exists(os.path.join(d, "pk_out.k")), f"rc={rc} {out[-300:]}")
    check("오류가 문제의 *MAT 키워드 이름을 찍는다 (예전엔 'not found in material DB' 뿐)",
          "MAT_PLASTIC_KINEMATIC" in out, out[-500:])
    check("오류가 지원하는 재질 목록을 함께 찍는다",
          "MAT_ELASTIC" in out and "076" in out and "020" in out, out[-500:])
    check("실패가 확정된 그룹의 Homogenized 요약을 찍지 않는다", "Homogenized:" not in out, out[-500:])

    # 알아보는 재질만 있는 덱은 그대로 성공해야 한다
    write(d, "ok.k", src)
    write(d, "ok.yaml", "model: ok.k\noutput: ok_out.k\ndirection: z\nmethod: vrh\n"
                        "merge:\n  - pids: [1, 2, 3]\n    name: H\n")
    rc, out = run(binary, d, "merge", "ok.yaml")
    check("아는 재질만 있는 덱은 그대로 rc=0 + Homogenized 요약",
          rc == 0 and os.path.exists(os.path.join(d, "ok_out.k")) and "Homogenized:" in out,
          f"rc={rc} {out[-300:]}")


def test_assemble_load_validation(binary):
    print("[assemble — loads 의 mode/select 를 단독 load 와 같게 판정한다]")
    d = mkd("g2_asm_")
    write(d, "box.yaml", BOX)
    run(binary, d, "generate", "box", "box.yaml")

    head = "base_model: box.k\noutput: %s\n\noperations:\n  - type: load\n    loads:\n      - part: 1\n"
    write(d, "grav.yaml", (head % "asm_grav.k") +
          "        mode: gravity\n        value: 1.0\n        direction: [0, 0, 1]\n"
          "        select: direction\n        angle: 45.0\n")
    rc, out = run(binary, d, "assemble", "grav.yaml")
    check("assemble 안의 mode: gravity 도 rc=1 + 출력 없음 (예전엔 조용히 압력 하중)",
          rc == 1 and not os.path.exists(os.path.join(d, "asm_grav.k")), f"rc={rc} {out[-300:]}")
    check("오류가 허용값 목록을 찍는다", "pressure, force, normal_pressure" in out, out[-300:])

    write(d, "sel.yaml", (head % "asm_sel.k") +
          "        mode: pressure\n        value: 1.0\n        direction: [0, 0, 1]\n"
          "        select: all\n        angle: 45.0\n")
    rc, out = run(binary, d, "assemble", "sel.yaml")
    check("assemble 안의 select: all 도 rc=1 + 출력 없음",
          rc == 1 and not os.path.exists(os.path.join(d, "asm_sel.k")), f"rc={rc} {out[-300:]}")
    check("오류가 select 허용값 목록을 찍는다", "direction, set, tied" in out, out[-300:])

    write(d, "ok.yaml", (head % "asm_ok.k") +
          "        mode: pressure\n        value: 1.0\n        direction: [0, 0, 1]\n"
          "        select: direction\n        angle: 45.0\n")
    rc, out = run(binary, d, "assemble", "ok.yaml")
    check("유효한 loads 는 그대로 rc=0 + *LOAD_SEGMENT 생성", rc == 0
          and os.path.exists(os.path.join(d, "asm_ok.k"))
          and "*LOAD_SEGMENT" in open(os.path.join(d, "asm_ok.k"), errors="replace").read(),
          f"rc={rc} {out[-300:]}")


def test_generate_var_curved_no_scale(binary):
    print("[generate-var — 곡면도 --no-scale 이 dimensions 를 지킨다]")
    d = mkd("g2_gvc_")
    write(d, "curved.yaml", GV_CURVED)
    rc, out = run(binary, d, "generate-var", "--no-scale", "curved.yaml", "c_ns.k")
    ok = rc == 0 and os.path.exists(os.path.join(d, "c_ns.k"))
    check("곡면 + --no-scale 은 rc=0", ok, f"rc={rc} {out[-200:]}")
    ext_ns = extent(os.path.join(d, "c_ns.k")) if ok else [0, 0, 0]
    # 예전엔 --no-scale 이면 dimensions 를 버려 cross_section 의 width 10 / thickness 2 로 나왔다.
    # 곡선이 XZ 평면에서 휘므로 두께는 Z 범위에 섞인다 — 세 축 범위를 통째로 단언한다.
    check("--no-scale 이어도 dimensions 를 그대로 쓴다 (폭 20, 범위 83.479/20/44.446)",
          ok and all(abs(a - b) < 1e-3 for a, b in zip(ext_ns, [83.47854125, 20.0, 44.44637741])),
          f"extent={ext_ns}")

    rc, out = run(binary, d, "generate-var", "curved.yaml", "c_sc.k")
    ok2 = rc == 0 and os.path.exists(os.path.join(d, "c_sc.k"))
    ext_sc = extent(os.path.join(d, "c_sc.k")) if ok2 else [1, 1, 1]
    check("dimensions 가 있으면 --no-scale 유무로 결과가 갈리지 않는다",
          ok2 and all(abs(a - b) < 1e-6 for a, b in zip(ext_ns, ext_sc)), f"{ext_ns} vs {ext_sc}")

    nodim = "\n".join(l for l in GV_CURVED.split("\n")
                      if not (l.startswith("reference:") or l.startswith("  dimensions:")
                              or l.startswith("    length_")))
    write(d, "curved_nodim.yaml", nodim)
    rc, out = run(binary, d, "generate-var", "--no-scale", "curved_nodim.yaml", "c_nd.k")
    ok3 = rc == 0 and os.path.exists(os.path.join(d, "c_nd.k"))
    ext_nd = extent(os.path.join(d, "c_nd.k")) if ok3 else [0, 0, 0]
    check("dimensions 가 없으면 cross_section 의 width 10 / thickness 2 를 쓴다 (범위 100.707/10/51.707)",
          ok3 and all(abs(a - b) < 1e-3 for a, b in zip(ext_nd, [100.7071068, 10.0, 51.70710678])),
          f"extent={ext_nd}")

    rc, out = run(binary, d, "help", "generate-var")
    check("--no-scale 도움말이 reference.dimensions 는 그대로 쓴다고 알린다",
          "dimensions" in out and "as-is" not in out, out[:600])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    test_squeeze_element_ids(binary)
    test_stabilize_level_zero(binary)
    test_load_help_truth(binary)
    test_merge_unknown_material(binary)
    test_assemble_load_validation(binary)
    test_generate_var_curved_no_scale(binary)

    print()
    if FAILS:
        print(f"FAIL {len(FAILS)}")
        for f in FAILS:
            print("  -", f[:300])
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
