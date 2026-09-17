# ale·cnrb2solid·tetremesh·meshfix·modelmeta·battery 의 YAML 값 파싱(인라인 주석·따옴표)과 실패 처리 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_misc_ops_yaml_parsing.py <KooRemapper 바이너리>

배경
  - 이 명령들의 미니 YAML 파서는 값의 첫 '#' 에서 잘라 'model: "bolt.k"' 를 못 열고(따옴표도 안 뗌),
    'output: solid#1.k' 는 'solid' 로 썼다. tetremesh·meshfix 는 줄 전체를 잘라 'output: "mf # x.k"' 가
    '"mf' 로 남았고, 그 짝 안 맞는 따옴표가 셸 인자를 뭉개 gmsh 가 -parse_and_exit 없이 떠서 멈췄다.
  - ale 은 주석 본문의 '- pid' 까지 새 항목으로 세어 fsi_pids 를 삼켰고, '- material' 로 시작한 항목은
    "YAML missing 'ale_parts' entries" 로 거부했으며, 블록 스타일 'fsi_pids:' 목록을 조용히 무시했다.
    모르는 재료는 [ERROR] 만 찍고 rc 0 으로 재료 없는 출력을 썼다.
  - meshfix 의 MathEval 크기장은 음수 bbox 코너를 '(y--1.000000e+01)' 로 적어 gmsh 가 식을 통째로 버렸다.
  - modelmeta 는 따옴표 상태를 값 어디의 홑따옴표에나 뒤집어 "it's_meta   # note" 의 주석을 이름에 남겼고,
    battery 는 줄 단위로 ' #' 앞만 잘라 탭 앞 주석('stacked<TAB># note')을 값에 그대로 뒀다.
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# 면 하나를 공유하는 TET4 두 개 — bbox 가 z 음수를 포함한다(MathEval 음수 코너 확인용)
TET_MODEL = """*KEYWORD
*NODE
       1       0.000000       0.000000       0.000000
       2       1.000000       0.000000       0.000000
       3       0.500000       1.000000       0.000000
       4       0.500000       0.500000       1.000000
       5       0.500000       0.500000      -1.000000
*ELEMENT_SOLID
       1       1       1       2       3       4       4       4       4       4
       2       1       1       3       2       5       5       5       5       5
*PART
TET4 part
         1         1         1
*SECTION_SOLID
         1        13
*MAT_ELASTIC
         1  7.85E-09    210000       0.3
*END
"""

# gmsh 대역 — 받은 인자를 그대로 적고 실패한다(.geo 는 남아 검사할 수 있다)
GMSH_STUB = """#!/bin/sh
printf '%s\\n' "$#" > {args}
for a in "$@"; do printf '%s\\n' "$a" >> {args}; done
exit 1
"""


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300, env=e)
    return p.returncode, p.stdout + p.stderr


def write(d, name, body):
    with open(os.path.join(d, name), "w") as f:
        f.write(body)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="misc_yaml_")
    shutil.copy(os.path.join(REPO, "examples", "ale", "explicit.k"), d)
    shutil.copy(os.path.join(REPO, "examples", "cnrb2solid", "bolt_simple.k"), os.path.join(d, "bolt.k"))
    shutil.copy(os.path.join(d, "bolt.k"), os.path.join(d, "bolt # x.k"))
    write(d, "tet.k", TET_MODEL)
    shutil.copy(os.path.join(d, "tet.k"), os.path.join(d, "tet#2.k"))
    shutil.copy(os.path.join(d, "tet.k"), os.path.join(d, "tet # x.k"))

    print("[ale: 값 따옴표·주석·항목 인식]")
    write(d, "ale_q.yaml", 'model: explicit.k\noutput: "o # q.k"\n'
                           'ale_parts:\n  - pid: 3\n    material: "air"   # 공기 프리셋\n')
    rc, out = run(binary, d, "ale", "ale_q.yaml")
    check("ale: 따옴표 재료 + 인라인 주석 → air 프리셋, 이름의 '#' 유지",
          rc == 0 and "*MAT_NULL" in out and os.path.exists(os.path.join(d, "o # q.k")),
          f"rc={rc} {out[-200:]}")

    write(d, "ale_dash.yaml", 'model: explicit.k\noutput: o_dash.k\n'
                              'ale_parts:\n  - pid: 3\n    material: air   # - pid 참고\nfsi_pids: [1]\n')
    rc, out = run(binary, d, "ale", "ale_dash.yaml")
    check("ale: 주석 속 '- pid' 가 새 항목을 열지 않음 (fsi_pids 살아있음)",
          rc == 0 and "FSI PIDs : 1" in out and "*EOS_LINEAR_POLYNOMIAL" in out, f"rc={rc} {out[-200:]}")

    write(d, "ale_mfirst.yaml", 'model: explicit.k\noutput: o_mfirst.k\n'
                                'ale_parts:\n  - material: air\n    pid: 3\n')
    rc, out = run(binary, d, "ale", "ale_mfirst.yaml")
    check("ale: '- material' 로 시작한 항목도 인식 (키 순서 무관)",
          rc == 0 and "ALE PIDs : 3 (air)" in out and os.path.exists(os.path.join(d, "o_mfirst.k")),
          f"rc={rc} {out[-200:]}")

    write(d, "ale_block.yaml", 'model: explicit.k\noutput: o_block.k\n'
                               'ale_parts:\n  - pid: 3\n    material: air\n'
                               'fsi_pids:\n  - 1\n  - 2   # 프레임\n')
    rc, out = run(binary, d, "ale", "ale_block.yaml")
    check("ale: 블록 스타일 'fsi_pids:' 목록도 커플링에 반영",
          rc == 0 and "FSI PIDs : 1, 2" in out and "*CONSTRAINED_LAGRANGE_IN_SOLID" in out,
          f"rc={rc} {out[-200:]}")

    write(d, "ale_bad.yaml", 'model: explicit.k\noutput: o_bad.k\n'
                             'ale_parts:\n  - pid: 3\n    material: unobtanium\n')
    rc, out = run(binary, d, "ale", "ale_bad.yaml")
    check("ale: 모르는 재료 → rc=1, 출력 파일 없음",
          rc == 1 and not os.path.exists(os.path.join(d, "o_bad.k")), f"rc={rc} {out[-200:]}")

    print("[cnrb2solid: 값 따옴표·붙은 '#']")
    write(d, "cn_q.yaml", 'model: "bolt.k"\noutput: "bolt_solid.k"   # 솔리드 볼트\n')
    rc, out = run(binary, d, "cnrb2solid", "cn_q.yaml")
    check("cnrb2solid: 따옴표 model/output → 실행 (rc=0)",
          rc == 0 and os.path.exists(os.path.join(d, "bolt_solid.k")), f"rc={rc} {out[-200:]}")

    write(d, "cn_h.yaml", 'model: bolt.k\noutput: solid#1.k\n')
    rc, out = run(binary, d, "cnrb2solid", "cn_h.yaml")
    check("cnrb2solid: 공백 없이 붙은 '#' 은 이름의 일부 (solid#1.k)",
          rc == 0 and os.path.exists(os.path.join(d, "solid#1.k")) and not os.path.exists(os.path.join(d, "solid")),
          f"rc={rc} {out[-200:]}")

    print("[tetremesh: 줄 전체 주석 자르기]")
    write(d, "tr_q.yaml", 'model: "tet # x.k"   # 입력\noutput: "tet # 1.k"\n'
                          'backend: localimprove   # 기본\nquality:   # 품질 기준\n  min_jacobian: 0.2   # 목표\n')
    rc, out = run(binary, d, "tetremesh", "tr_q.yaml")
    check("tetremesh: 따옴표 안 '#' 유지 + 섹션 주석 (rc=0)",
          rc == 0 and os.path.exists(os.path.join(d, "tet # 1.k")), f"rc={rc} {out[-200:]}")

    write(d, "tr_h.yaml", 'model: tet#2.k\noutput: tet#1.k\n')
    rc, out = run(binary, d, "tetremesh", "tr_h.yaml")
    check("tetremesh: 붙은 '#' 은 이름의 일부 (tet#1.k)",
          rc == 0 and os.path.exists(os.path.join(d, "tet#1.k")), f"rc={rc} {out[-200:]}")

    print("[meshfix: 출력 이름·gmsh 명령·MathEval 식]")
    mf = tempfile.mkdtemp(prefix="misc_yaml_mf_")
    write(mf, "tet.k", TET_MODEL)
    args_path = os.path.join(mf, "args.txt")
    stub = os.path.join(mf, "gmsh_stub.sh")
    with open(stub, "w") as f:
        f.write(GMSH_STUB.format(args=args_path))
    os.chmod(stub, 0o755)
    write(mf, "mf.yaml", 'model: tet.k\noutput: "mf # x.k"   # 결과\npid: 1\nlc_target: 0.5\n')
    rc, out = run(binary, mf, "meshfix", "mf.yaml", env={"KOOREMAPPER_GMSH": stub})
    check("meshfix: 따옴표 안 '#' 을 살린 임시 파일 이름",
          os.path.exists(os.path.join(mf, "mf # x__mf.stl")), f"rc={rc} {sorted(os.listdir(mf))}")
    argv = open(args_path).read().splitlines() if os.path.exists(args_path) else []
    check("meshfix: gmsh 인자가 어긋나지 않음 (.geo 하나 + -v 3 -parse_and_exit)",
          len(argv) == 5 and argv[0] == "4" and argv[1].endswith(".geo")
          and os.path.exists(os.path.join(mf, argv[1])) and argv[4] == "-parse_and_exit",
          f"argv={argv}")
    geos = sorted(glob.glob(os.path.join(mf, "*.geo")))
    geo = open(geos[0]).read() if geos else ""
    check("meshfix: 음수 bbox 코너가 '(z+1...)' — 빼기 두 번('--') 없음",
          bool(geos) and "--" not in geo and "(z+1" in geo,
          f"geos={[os.path.basename(g) for g in geos]} {geo[:160]}")

    print("[modelmeta: 홑따옴표·붙은 '#']")
    write(d, "mm_q.yaml", "model: tet.k\noutput: it's_meta   # 메모\n")
    rc, out = run(binary, d, "modelmeta", "mm_q.yaml")
    check("modelmeta: 값 속 홑따옴표가 주석 판정을 뒤집지 않음",
          rc == 0 and os.path.exists(os.path.join(d, "it's_meta_modelmeta.json")), f"rc={rc} {out[-200:]}")

    write(d, "mm_h.yaml", "model: tet#2.k\noutput: h_meta\n")
    rc, out = run(binary, d, "modelmeta", "mm_h.yaml")
    check("modelmeta: 붙은 '#' 이 든 모델 이름을 그대로 읽음",
          rc == 0 and os.path.exists(os.path.join(d, "h_meta_modelmeta.json")), f"rc={rc} {out[-200:]}")

    print("[battery: 탭 앞 주석·따옴표 값]")
    BAT = "tier: -1\nphase: 1\ngeometry:\n  cell_width: 30\n  cell_height: 30\n  n_unit_cells: 1\n"
    write(d, "bat_tab.yaml", "output: bat_tab\nmodel_type: stacked\t# 적층\n" + BAT)
    rc, out = run(binary, d, "battery", "bat_tab.yaml")
    check("battery: 탭 앞 인라인 주석도 값에서 떨어짐 (rc=0)",
          rc == 0 and os.path.exists(os.path.join(d, "bat_tab_tier-1_phase1.k")), f"rc={rc} {out[-200:]}")

    write(d, "bat_q.yaml", 'output: "bat_q # kept"\nmodel_type: "stacked"\n' + BAT)
    rc, out = run(binary, d, "battery", "bat_q.yaml")
    check("battery: 따옴표 값 — model_type 인식 + 이름의 '#' 유지",
          rc == 0 and os.path.exists(os.path.join(d, "bat_q # kept_tier-1_phase1.k")), f"rc={rc} {out[-200:]}")

    print()
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
