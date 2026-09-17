# 단독 명령 YAML 파싱 회귀 시험 — operations 항목 첫 줄('- key: 값')의 키와 목록 항목 인라인 주석을 실제 실행으로 확인
"""
사용: python3 tools/regress/test_standalone_yaml_parsing.py <KooRemapper 바이너리>

배경
  - 단독 convert·refine·elform·disconnect·offset·wrap·update·bend·formstrain·warpage·restack·indent 는
    operations 항목 첫 줄('- type: hex20')의 키를 '- type' 으로 읽어 그 키를 조용히 버렸다. help convert 예시는
    hex20 대신 tet10 기본값('TET10: no TET4 elements found')으로 원본을 그대로 썼고, '- ratio: 3' 은 무시,
    '- source_pid: 1' 은 'source_pid required', '- target_elform: 2' 는 'Unknown ELFORM alias',
    '- dat_file:' 은 'dat_file is required', bend·formstrain '- target_pid:' 는 무시(모든 파트)됐다.
  - 목록 항목 값의 인라인 주석을 떼지 않아 restack '- material_card: |  # 메모' 층은 카드 없음,
    '- thickness: "0.2"  # 메모' 는 잘못된 두께, indent '- [6, 3]  # 메모' 점은 조용히 빠졌고,
    offset material_cards '- |  # 메모' 는 목록이 끊겨 층 재질이 빠졌다.
  - 대시 항목을 따로 읽는 목록(restack layers·iga targets·indent points·offset material_cards)은 그대로여야 한다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

BOX = "output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\npid: 1\nmid: 1\nsecid: 1\n"

RESTACK = """base_model: box.k
output: {out}
operations:
  - type: restack
    target_pid: 1
    direction: z
    element_type: solid
    layers:
      - thickness: 0.5
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
              MID001  7.85E-09  2.10E+05       0.3
      - thickness: 0.2
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
              MID002  1.20E-09  3.00E+03      0.45
"""

# 층의 첫 키가 material_card 인(대시 줄에 블록 리터럴이 오는) 같은 뜻의 YAML — 값 뒤에 인라인 주석
RESTACK_CARD_FIRST = """base_model: box.k
output: {out}
operations:
  - type: restack
    target_pid: 1
    direction: z
    element_type: solid
    layers:
      - material_card: |   # 층 1 재질
          *MAT_ELASTIC
          $#     mid        ro         e        pr
              MID001  7.85E-09  2.10E+05       0.3
        thickness: 0.5
      - material_card: |   # 층 2 재질
          *MAT_ELASTIC
          $#     mid        ro         e        pr
              MID002  1.20E-09  3.00E+03      0.45
        thickness: 0.2
"""

INDENT = """base_model: box.k
output: {out}
operations:
  - type: indent
    target_pid: 1
    plane: xy
    direction: -z
    depth: 0.5
    r1: 0.5
    r2: 1.0
    shape:
      type: polygon
      points:
        - [6, 3]
        - [12, 3]
        - [12, 7]
        - [6, 7]
        - [5, 5]
"""

OFFSET = """base_model: box.k
output: {out}
operations:
  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: 2
    offset_direction: +z
    connection_mode: tied
    new_pid: 10
    new_secid: 20
    new_mid: 30
    material_cards:
      - |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
             @MID@       2.0      1000      0.35
      - |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
             @MID@       3.0      3000      0.30
"""


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def run_yaml(binary, d, cmd, name, body):
    open(os.path.join(d, name + ".yaml"), "w").write(body)
    return run(binary, d, cmd, name + ".yaml")


def kbody(d, name):
    """'$' 주석 줄을 뺀 출력 k 내용 — 없으면 None"""
    p = os.path.join(d, name + ".k")
    if not os.path.exists(p):
        return None
    return [ln for ln in open(p).read().splitlines() if not ln.startswith("$")]


def same_as(binary, d, cmd, ref, name, body, what):
    """같은 뜻의 YAML 두 벌 — 바뀐 쪽도 실행되고 기준과 같은 k 를 써야 한다"""
    rc, out = run_yaml(binary, d, cmd, name, body)
    ref_k, new_k = kbody(d, ref), kbody(d, name)
    check(f"{cmd}: {what} (rc=0, 기준과 같은 출력)", rc == 0 and ref_k is not None and ref_k == new_k,
          f"rc={rc} {out[-250:]}")
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="standalone_yaml_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    for f in ("examples/disconnect/two_hex_2part.k", "examples/wrap/cylinder_2layer.k",
              "examples/formstrain/bent_shell.k"):
        shutil.copy(os.path.join(REPO, f), d)

    print("[operations 항목 첫 줄 '- key: 값' 의 키]")
    rc, out = run_yaml(binary, d, "convert", "cv", "base_model: box.k\noutput: cv\noperations:\n"
                       "  - type: hex20\n    elform: 23\n")
    check("convert: '- type: hex20' → HEX20 변환 (tet10 기본값 아님)",
          rc == 0 and "Type: hex20" in out and "HEX20: converted" in out, f"rc={rc} {out[-250:]}")
    rc, out = run_yaml(binary, d, "refine", "rf", "base_model: box.k\noutput: rf\noperations:\n  - ratio: 3\n")
    check("refine: '- ratio: 3' → 1:3 세분화", rc == 0 and "Refine 1:3" in out, f"rc={rc} {out[-250:]}")
    rc, out = run_yaml(binary, d, "elform", "ef", "base_model: box.k\noutput: ef\noperations:\n"
                       "  - target_elform: 2\n")
    check("elform: '- target_elform: 2' → ELFORM 2", rc == 0 and "changed to 2" in out, f"rc={rc} {out[-250:]}")
    rc, out = run_yaml(binary, d, "disconnect", "dc", "base_model: two_hex_2part.k\noutput: dc\noperations:\n"
                       "  - mode: czm\n    target_pid: 0\n")
    check("disconnect: '- mode: czm' → czm 모드 (full 기본값 아님)", rc == 0 and "Disconnect (czm)" in out,
          f"rc={rc} {out[-250:]}")
    of_common = ("    thickness: 1.0\n    num_layers: 1\n    offset_direction: +z\n    new_pid: 10\n"
                 "    material_card: |\n      *MAT_ELASTIC\n               @MID@       2.0     12000      0.25\n")
    run_yaml(binary, d, "offset", "of_ref", "base_model: box.k\noutput: of_ref\noperations:\n  - type: offset\n"
             "    source_pid: 1\n" + of_common)
    same_as(binary, d, "offset", "of_ref", "of_dash",
            "base_model: box.k\noutput: of_dash\noperations:\n  - source_pid: 1\n" + of_common,
            "'- source_pid: 1' 첫 줄")
    rc, out = run_yaml(binary, d, "wrap", "wr", "model: cylinder_2layer.k\noutput: wr\nmaterial:\n  E: 210000.0\n"
                       "  nu: 0.3\noperations:\n  - target_pid: [1, 2]\n    axis: z\n    tension: 100.0\n")
    check("wrap: '- target_pid: [1, 2]' → 두 층 와인딩", rc == 0 and "2 layers" in out, f"rc={rc} {out[-250:]}")
    open(os.path.join(d, "sq.yaml"), "w").write(
        "parts:\n  - pid: 1\n    eps_x: -0.01\n    eps_y: -0.01\n    eps_z: 0.0\nmaterial:\n  E: 210000.0\n  nu: 0.3\n")
    run(binary, d, "squeeze", "box.k", "sq.yaml", "box_sq")
    rc, out = run_yaml(binary, d, "update", "up", "model: box.k\noutput: up\noperations:\n  - dynain: box_sq.k\n")
    check("update: '- dynain: box_sq.k' → 좌표 갱신", rc == 0 and "198/198 nodes updated" in out,
          f"rc={rc} {out[-250:]}")
    rc, out = run_yaml(binary, d, "bend", "bd", "base_model: box.k\noutput: bd\nmaterial:\n  E: 210000\n  nu: 0.3\n"
                       "operations:\n  - target_pid: 1\n    plane: xy\n    mode: deform\n    source: formula\n"
                       "    expression: \"0.5 * sin(pi*x1/L1) * sin(pi*x2/L2)\"\n")
    check("bend: '- target_pid: 1' → Part 1 만 (ALL 아님)", rc == 0 and "Bend Part 1 (" in out,
          f"rc={rc} {out[-250:]}")
    rc, out = run_yaml(binary, d, "formstrain", "fs", "base_model: bent_shell.k\noutput: fs\ndynain_embed: true\n"
                       "operations:\n  - target_pid: 99\n")
    check("formstrain: '- target_pid: 99' 를 읽음 (없는 파트로 거부)", rc == 1 and "target PID 99 not found" in out,
          f"rc={rc} {out[-250:]}")
    open(os.path.join(d, "warp.dat"), "w").write("0 0 0 0 0\n0 50 100 50 0\n0 0 0 0 0\n")
    rc, out = run_yaml(binary, d, "warpage", "wp", "base_model: box.k\noutput: wp\nmaterial:\n  E: 210000\n  nu: 0.3\n"
                       "operations:\n  - dat_file: warp.dat\n    target_pid: 1\n    plane: xy\n"
                       "    deflection_axis: +z\n    unit: um\n    mode: deform\n")
    check("warpage: '- dat_file: warp.dat' → 실행 (dat_file is required 아님)",
          rc == 0 and "dat_file is required" not in out and os.path.exists(os.path.join(d, "wp.k")),
          f"rc={rc} {out[-250:]}")
    run_yaml(binary, d, "restack", "rs_ref", RESTACK.format(out="rs_ref"))
    same_as(binary, d, "restack", "rs_ref", "rs_dash",
            RESTACK.format(out="rs_dash").replace("  - type: restack\n    target_pid: 1\n", "  - target_pid: 1\n"),
            "'- target_pid: 1' 첫 줄")
    run_yaml(binary, d, "indent", "in_ref", INDENT.format(out="in_ref"))
    same_as(binary, d, "indent", "in_ref", "in_dash",
            INDENT.format(out="in_dash").replace("  - type: indent\n    target_pid: 1\n", "  - target_pid: 1\n"),
            "'- target_pid: 1' 첫 줄")

    print("[목록 항목 값의 인라인 주석]")
    same_as(binary, d, "restack", "rs_ref", "rs_cmt_card",
            RESTACK_CARD_FIRST.format(out="rs_cmt_card"), "'- material_card: |  # 메모' 층 카드")
    same_as(binary, d, "restack", "rs_ref", "rs_cmt_thk",
            RESTACK.format(out="rs_cmt_thk").replace("      - thickness: 0.2\n", "      - thickness: \"0.2\"   # 얇은 층\n"),
            "'- thickness: \"0.2\"  # 메모' 두께")
    same_as(binary, d, "indent", "in_ref", "in_cmt",
            INDENT.format(out="in_cmt").replace("- [12, 3]\n", "- [12, 3]   # 우하\n").replace("- [5, 5]\n", "- [5, 5]   # 다섯째\n"),
            "'- [12, 3]  # 메모' 점을 버리지 않음")
    run_yaml(binary, d, "offset", "om_ref", OFFSET.format(out="om_ref"))
    out = same_as(binary, d, "offset", "om_ref", "om_cmt",
                  OFFSET.format(out="om_cmt").replace("      - |\n", "      - |   # 층 재질\n"),
                  "material_cards '- |  # 메모' 목록")
    check("offset: material_cards 주석 달린 두 항목 → 2 층", "Multi-material mode: 2 layers" in out, out[-250:])

    print("[대시 항목을 따로 읽는 목록은 그대로]")
    rc, out = run_yaml(binary, d, "iga", "iga", "base_model: box.k\noutput: iga\noperations:\n  - type: iga\n"
                       "    targets:\n      - target_pid: 1   # 상자\n        element_size: 4.0\n")
    check("iga: '- target_pid: 1  # 메모' 대상 1개 (rc=0)", rc == 0 and "[iga] Targets: 1" in out, f"rc={rc} {out[-250:]}")
    rc, out = run(binary, d, "restack", "rs_ref.yaml")
    check("restack: layers 의 '- thickness:' 항목 두 층", rc == 0 and "2 layers -> 2 layers" in out, f"rc={rc} {out[-250:]}")
    rc, out = run(binary, d, "offset", "om_ref.yaml")
    check("offset: material_cards '- |' 두 항목 → 2 층", rc == 0 and "Multi-material mode: 2 layers" in out,
          f"rc={rc} {out[-250:]}")
    rc, out = run_yaml(binary, d, "wrap", "wr_top", "model: cylinder_2layer.k\noutput: wr_top\nmaterial:\n"
                       "  E: 210000.0\n  nu: 0.3\ntarget_pid: [1, 2]\naxis: z\ntension: 100.0\n")
    check("wrap: 최상위 target_pid: [1, 2] 그대로", rc == 0 and "2 layers" in out, f"rc={rc} {out[-250:]}")

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
