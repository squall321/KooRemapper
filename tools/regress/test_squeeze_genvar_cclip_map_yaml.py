# squeeze·generate-var·cclip·map(YAML) 미니 파서의 인라인 # 주석·따옴표 처리와 generate-var --no-scale 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_squeeze_genvar_cclip_map_yaml.py <KooRemapper 바이너리>

배경
  - squeeze 는 섹션 머리를 줄 전체로 비교해 'parts:   # 주석' 이면 'No parts defined', 'material:   # 주석' 이면
    E/nu 를, 'relax:   # 주석' 이면 DR 카드를 조용히 버렸다. 'strain_mode: true   # 주석'(examples/squeeze/ex03)·
    relax 의 'enabled/mode/d3drlf: …   # 주석'(ex05) 은 false/explicit 로 읽혔고 mode: "implicit" 따옴표도 남았다.
  - generate-var 파서는 주석을 전혀 떼지 않아 'variable_density:   # 주석' 같은 블록 머리·type: curved·
    centerline_points 항목이 모두 깨졌다.
  - cclip 은 이미 trim 된 값 맨 앞 '#' 을 놓쳐 'material:   # 주석' 블록·calibration 의 'point:/curve:   # 주석' 블록을
    버렸다(rc=1 또는 재질 무시).
  - generate-var --no-scale 은 기준 길이 0 으로 생성해 모든 노드가 원점(0,0,0)에 모였다. 그 뒤에는
    reference.dimensions 를 적어도 --no-scale 이면 무시해 length_j/length_k 가 1.0 으로 뭉개졌다.
  - map <config.yaml> 은 줄의 첫 '#' 에서 잘라 output: "map # kept.k" 가 '"map' 파일, map#1.k 가 'map' 파일이 됐다.
"""
import os
import re
import subprocess
import sys
import tempfile

FAILS = []
KV = re.compile(r"^(\s*(?:-\s+)?[A-Za-z_][\w.\-]*\s*:)(.*)$")

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")
BOARD = ("output: clip_board.k\nlx: 3.0\nly: 1.5\nlz: 0.5\nnx: 6\nny: 3\nnz: 1\nrho: 8.36e-9\nE: 131000.0\nnu: 0.3\n"
         "mid: 2\nsecid: 2\npid: 2\npart_title: CCLIP_ANT_01\n")
GV_FLAT = """type: flat
reference:
  dimensions:
    length_i: 120.0
    length_j: 12.0
    length_k: 3.0
elements_j: 4
elements_k: 2
variable_density:
  zone1_dense_start:
    length: 10.0
    num_elements: 10
  zone2_increasing:
    length: 20.0
    num_elements: 8
    growth_type: geometric
  zone3_sparse:
    length: 40.0
    num_elements: 8
  zone4_decreasing:
    length: 20.0
    num_elements: 8
  zone5_dense_end:
    length: 10.0
    num_elements: 10
options:
  center_at_origin: true
"""
GV_CURVED = """type: curved
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
GV_CAT = """type: flat
reference:
  dimensions:
    length_i: 100.0
    length_j: 10.0
    length_k: 2.0
elements_j: 5
elements_k: 2
variable_density:
  zone1_dense_start:
    length: 10.0
    num_elements: 10
  zone2_increasing:
    length: 20.0
    num_elements: 8
  zone3_sparse:
    length: 40.0
    num_elements: 8
  zone4_decreasing:
    length: 20.0
    num_elements: 8
  zone5_dense_end:
    length: 10.0
    num_elements: 10
"""


def check(name, cond, detail=""):
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def commented(text):
    """모든 'key:' 줄(값이 비어 있는 블록 머리 포함)과 '- [..]' 항목 뒤에 '   # note' 를 붙인다."""
    out = []
    for ln in text.split("\n"):
        if KV.match(ln) or ln.lstrip().startswith("- ["):
            out.append(ln.rstrip() + "   # note")
        else:
            out.append(ln)
    return "\n".join(out)


def body(path):
    """'$' 주석 줄을 뺀 내용 (없으면 None)."""
    try:
        return [l for l in open(path, errors="replace").read().splitlines() if not l.startswith("$")]
    except OSError:
        return None


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


def write(d, name, text):
    open(os.path.join(d, name), "w").write(text)


def test_squeeze(binary):
    print("[squeeze — 섹션 머리·값 뒤 주석, 따옴표]")
    d = tempfile.mkdtemp(prefix="sq_cmt_")
    write(d, "box.yaml", BOX)
    run(binary, d, "generate", "box", "box.yaml")

    def sq(tag, yaml):
        write(d, tag + ".yaml", yaml)
        rc, out = run(binary, d, "squeeze", "box.k", tag + ".yaml", tag)
        return rc, out, body(os.path.join(d, tag + ".k")), body(os.path.join(d, tag + ".dynain"))

    parts = "parts:\n  - pid: 1\n    eps_x: -0.01\n    eps_y: -0.01\n    eps_z: 0.0\n"
    rc, out, _, _ = sq("parts_c", parts.replace("parts:\n", "parts:   # note\n"))
    check("'parts:   # 주석' 머리 → 파트 인식 (rc=0)", rc == 0, f"rc={rc} {out[-200:]}")

    mat = "material:\n  E: 70000.0\n  nu: 0.3\n"
    _, _, _, dyn_nomat = sq("nomat", parts)
    rc, out, _, dyn_mat = sq("mat", parts + mat)
    rc2, out2, _, dyn_mat_c = sq("mat_c", parts + mat.replace("material:\n", "material:   # note\n"))
    check("(전제) material E 가 k 파일 재질과 다르면 dynain 이 달라짐", dyn_mat is not None and dyn_mat != dyn_nomat)
    check("'material:   # 주석' 머리 → E/nu 적용 (주석 없는 것과 dynain 동일)", rc2 == 0 and dyn_mat_c == dyn_mat,
          f"rc={rc2} {out2[-200:]}")

    rc, out, _, dyn = sq("strain_c", "strain_mode: true   # 재료 없이 변형률 직접 삽입\n\n" + parts)
    check("'strain_mode: true   # 주석' → *INITIAL_STRAIN_SOLID", rc == 0 and dyn is not None
          and "*INITIAL_STRAIN_SOLID" in dyn, f"rc={rc} {out[-200:]}")

    rc, out, k, _ = sq("relax_c", parts + mat + "relax:   # note\n  level: 2\n")
    check("'relax:   # 주석' 머리 → *CONTROL_DYNAMIC_RELAXATION 삽입", rc == 0 and k is not None
          and "*CONTROL_DYNAMIC_RELAXATION" in k, f"rc={rc} {out[-200:]}")
    rc, out, k, _ = sq("relax_en", parts + mat + "relax:\n  enabled: true   # note\n  level: 2\n")
    check("relax 'enabled: true   # 주석' → DR 카드 삽입", rc == 0 and k is not None
          and "*CONTROL_DYNAMIC_RELAXATION" in k, f"rc={rc} {out[-200:]}")
    rc, out, k, _ = sq("relax_imp", parts + mat + "relax:\n  mode: implicit   # IDRFLG=5\n")
    check("relax 'mode: implicit   # 주석' → *CONTROL_IMPLICIT_GENERAL", rc == 0 and k is not None
          and "*CONTROL_IMPLICIT_GENERAL" in k, f"rc={rc} {out[-200:]}")
    rc, out, k, _ = sq("relax_q", parts + mat + "relax:\n  mode: \"implicit\"\n")
    check("relax 'mode: \"implicit\"' 따옴표 → *CONTROL_IMPLICIT_GENERAL", rc == 0 and k is not None
          and "*CONTROL_IMPLICIT_GENERAL" in k, f"rc={rc} {out[-200:]}")
    rc, out, k, _ = sq("relax_d3", parts + mat + "relax:\n  enabled: true\n  d3drlf: true   # note\n")
    check("relax 'd3drlf: true   # 주석' → *DATABASE_BINARY_D3DRLF", rc == 0 and k is not None
          and "*DATABASE_BINARY_D3DRLF" in k, f"rc={rc} {out[-200:]}")

    full = "strain_mode: false\n" + parts + mat + "relax:\n  enabled: true\n  level: 3\n  mode: implicit\n  drterm: 0.0\n" \
           "  endtime: 1.0\n  d3drlf: false\n  nrcyck: 120\n"
    # 출력 이름이 .k 안 *INCLUDE 에 들어가므로 같은 prefix 로 각각 다른 폴더에서 돌린다
    outs = []
    for yaml in (full, commented(full)):
        w = tempfile.mkdtemp(prefix="sq_full_")
        write(w, "box.yaml", BOX)
        run(binary, w, "generate", "box", "box.yaml")
        write(w, "s.yaml", yaml)
        rc, out = run(binary, w, "squeeze", "box.k", "s.yaml", "out")
        outs.append((rc, out, body(os.path.join(w, "out.k")), body(os.path.join(w, "out.dynain"))))
    (_, _, k0, d0), (rc, out, k1, d1) = outs
    check("모든 키 뒤 주석 → 주석 없는 설정과 .k/.dynain 동일", rc == 0 and k0 is not None and d0 is not None
          and k0 == k1 and d0 == d1, f"rc={rc} {out[-200:]}")


def test_generate_var(binary):
    print("[generate-var — 블록 머리·값·목록 항목 뒤 주석]")
    d = tempfile.mkdtemp(prefix="gv_cmt_")
    for tag, yaml in (("flat", GV_FLAT), ("curved", GV_CURVED)):
        write(d, tag + ".yaml", yaml)
        write(d, tag + "_c.yaml", commented(yaml))
        rc0, out0 = run(binary, d, "generate-var", tag + ".yaml", tag + ".k")
        rc1, out1 = run(binary, d, "generate-var", tag + "_c.yaml", tag + "_c.k")
        b0, b1 = body(os.path.join(d, tag + ".k")), body(os.path.join(d, tag + "_c.k"))
        check(f"{tag}: 주석 붙인 YAML → 주석 없는 것과 출력 동일 (rc=0)", rc0 == 0 and rc1 == 0 and b0 is not None
              and b0 == b1, f"rc={rc0}/{rc1} {out1[-200:]}")

    print("[generate-var --no-scale]")
    write(d, "var.yaml", GV_CAT)
    rc, out = run(binary, d, "generate-var", "--no-scale", "var.yaml", "var_ns.k")
    ok = rc == 0 and os.path.exists(os.path.join(d, "var_ns.k"))
    pts = nodes(os.path.join(d, "var_ns.k")) if ok else []
    ext = [max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)] if pts else [0, 0, 0]
    check("--no-scale: 노드가 원점에 모이지 않음 (I 길이 = zone 길이 합 100)", ok and abs(ext[0] - 100.0) < 1e-6,
          f"rc={rc} extent={ext}")
    # 예전 단언은 'J/K 는 스케일 없음 기본값 1.0' 이었다 — 사용자가 적은 dimensions 를 무시하는 버그를 옳다고 봤다.
    # --no-scale 은 '기준 모델에 맞춘 자동 스케일' 만 끄므로 명시된 length_j/length_k 는 그대로 나와야 한다.
    check("--no-scale: 명시한 dimensions 를 그대로 지킴 (J=10, K=2)",
          ok and abs(ext[1] - 10.0) < 1e-6 and abs(ext[2] - 2.0) < 1e-6, f"extent={ext}")

    # dimensions 를 안 적은 설정에서는 여전히 J/K 기본값 1.0
    write(d, "var_nodim.yaml", "\n".join(l for l in GV_CAT.split("\n")
                                        if not (l.startswith("reference:") or l.startswith("  dimensions:")
                                                or l.startswith("    length_"))))
    rc, out = run(binary, d, "generate-var", "--no-scale", "var_nodim.yaml", "var_nd.k")
    ok2 = rc == 0 and os.path.exists(os.path.join(d, "var_nd.k"))
    pts2 = nodes(os.path.join(d, "var_nd.k")) if ok2 else []
    ext2 = [max(p[i] for p in pts2) - min(p[i] for p in pts2) for i in range(3)] if pts2 else [0, 0, 0]
    check("--no-scale + dimensions 없음: J/K 기본값 1.0 유지", ok2 and abs(ext2[0] - 100.0) < 1e-6
          and abs(ext2[1] - 1.0) < 1e-6 and abs(ext2[2] - 1.0) < 1e-6, f"rc={rc} extent={ext2}")


def test_cclip(binary):
    print("[cclip — 값이 비고 주석만 있는 블록 머리]")
    d = tempfile.mkdtemp(prefix="cc_cmt_")
    write(d, "board.yaml", BOARD)
    run(binary, d, "generate", "box", "board.yaml")
    cases = {
        "topmat": "model: clip_board.k\noutput: OUT\nmaterial:\n  E: 200000.0\n  nu: 0.28\n  sigy: 1500.0\n"
                  "calibration:\n  point: {deflection: 0.15, force: 1.2}\nclips:\n  - pid: 2\n",
        "point": "model: clip_board.k\noutput: OUT\ncalibration:\n  point:\n    deflection: 0.15\n    force: 1.2\n"
                 "  tolerance: 0.05\nclips:\n  - pid: 2\n    overtravel: 0.15\n",
        "curve": "model: clip_board.k\noutput: OUT\ncalibration:\n  curve:\n    - [0.05, 0.40]\n    - [0.10, 0.80]\n"
                 "    - [0.15, 1.20]\n  operating_deflection: 0.15\nclips:\n  - pid: 2\n    overtravel: 0.2\n",
        "clipmat": "model: clip_board.k\noutput: OUT\ncalibration:\n  point: {deflection: 0.15, force: 1.2}\nclips:\n"
                   "  - pid: 2\n    material:\n      E: 200000.0\n      nu: 0.28\n      sigy: 1500.0\n",
    }
    labels = {"topmat": "'material:   # 주석' 최상위 블록", "point": "calibration 'point:   # 주석' 블록",
              "curve": "calibration 'curve:   # 주석' 블록", "clipmat": "clips 항목 'material:   # 주석' 블록"}
    for tag, yaml in cases.items():
        write(d, tag + ".yaml", yaml.replace("OUT", tag))
        write(d, tag + "_c.yaml", commented(yaml.replace("OUT", tag + "_c")))
        rc0, out0 = run(binary, d, "cclip", tag + ".yaml")
        rc1, out1 = run(binary, d, "cclip", tag + "_c.yaml")
        b0, b1 = body(os.path.join(d, tag + ".k")), body(os.path.join(d, tag + "_c.k"))
        check(f"{labels[tag]} → 주석 없는 것과 출력 동일 (rc=0)", rc0 == 0 and rc1 == 0 and b0 is not None
              and b0 == b1, f"rc={rc0}/{rc1} {out1[-200:]}")
    write(d, "q.yaml", cases["point"].replace("output: OUT", 'output: "clip # kept"   # note'))
    rc, out = run(binary, d, "cclip", "q.yaml")
    check("output: \"clip # kept\"   # 주석 → 'clip # kept.k' (따옴표 안 # 유지)", rc == 0
          and os.path.exists(os.path.join(d, "clip # kept.k")), f"rc={rc} {out[-200:]}")


def test_map(binary):
    print("[map <config.yaml> — 따옴표 안·공백 없이 붙은 #]")
    d = tempfile.mkdtemp(prefix="map_cmt_")
    run(binary, d, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo")
    write(d, "plain.yaml", "bent: demo_bent.k\nflat: demo_flat.k\noutput: plain.k\n")
    run(binary, d, "map", "plain.yaml")
    ref = body(os.path.join(d, "plain.k"))
    check("(전제) 주석 없는 map YAML 출력", ref is not None)

    write(d, "q.yaml", "bent: demo_bent.k\nflat: demo_flat.k\noutput: \"map # kept.k\"\n")
    rc, out = run(binary, d, "map", "q.yaml")
    check("output: \"map # kept.k\" → 'map # kept.k' (따옴표 안 # 유지)", rc == 0
          and body(os.path.join(d, "map # kept.k")) == ref and not os.path.exists(os.path.join(d, '"map')),
          f"rc={rc} files={sorted(os.listdir(d))}")
    write(d, "h.yaml", "bent: demo_bent.k\nflat: demo_flat.k\noutput: map#1.k\n")
    rc, out = run(binary, d, "map", "h.yaml")
    check("output: map#1.k → 'map#1.k' (공백 없이 붙은 # 는 값)", rc == 0
          and body(os.path.join(d, "map#1.k")) == ref and not os.path.exists(os.path.join(d, "map")),
          f"rc={rc} files={sorted(os.listdir(d))}")
    write(d, "c.yaml", "# 전체 줄 주석: bent: nope.k\nbent: demo_bent.k   # note\n  # 들여쓴 주석\n"
                       "flat: 'demo_flat.k'   # note\noutput: c.k\t# note\n")
    rc, out = run(binary, d, "map", "c.yaml")
    check("전체 줄 주석·값 뒤 주석·작은따옴표 → 출력 동일", rc == 0 and body(os.path.join(d, "c.k")) == ref
          and "Unknown YAML key" not in out, f"rc={rc} {out[-200:]}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    test_squeeze(binary)
    test_generate_var(binary)
    test_cclip(binary)
    test_map(binary)

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
