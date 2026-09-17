# 단독 명령의 YAML 상대 경로 해석·다중 operations 거부 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_standalone_paths_multiop.py <KooRemapper 바이너리>

배경
  - 단독 명령(offset·convert·update·warpage…)은 '/' 가 없는 이름만 YAML 폴더 기준으로 풀었다. 그래서
    'base_model: ../arc30/arc30_flat.k' 처럼 폴더가 붙은 상대 경로는 실행 폴더에서 찾아,
    저장소 루트에서 'KooRemapper offset examples/offset/06_czm_connection.yaml' 이 'Cannot open file' 로 죽었다
    (같은 YAML 을 assemble 로 돌리면 정상). output·dynain·dat_file 도 같은 규칙을 탄다.
  - operations 가 여러 개인 YAML 을 단독 명령에 주면 항목들이 한 op 로 합쳐져 마지막 값만 남았다
    (quad8 다음 tria6 → tria6 만 적용, 종료 코드 0). 조용히 하나만 하지 말고 assemble 로 안내해야 한다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

BOX = "output: flat.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 4\nny: 2\nnz: 1\npid: 1\nmid: 1\nsecid: 1\n"


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="standalone_paths_")
    root = os.path.join(tmp, "root")
    os.makedirs(os.path.join(root, "models"))
    os.makedirs(os.path.join(root, "cfg"))
    os.makedirs(os.path.join(root, "out"))
    write(os.path.join(root, "models", "box.yaml"), BOX)
    run(binary, os.path.join(root, "models"), "generate", "box", "box.yaml")

    print("[폴더가 붙은 상대 경로 — 저장소 루트에서 실행]")
    write(os.path.join(root, "cfg", "conv.yaml"),
          "base_model: ../models/flat.k\noutput: conv_out\noperations:\n  - type: hex20\n")
    rc, out = run(binary, root, "convert", "cfg/conv.yaml")
    check("convert: model '../models/flat.k' 를 YAML 폴더 기준으로 찾음",
          rc == 0 and os.path.exists(os.path.join(root, "cfg", "conv_out.k")), f"rc={rc} {out[-200:]}")

    write(os.path.join(root, "cfg", "conv_out2.yaml"),
          "base_model: flat.k\noutput: ../out/conv_out2\noperations:\n  - type: hex20\n")
    shutil.copy(os.path.join(root, "models", "flat.k"), os.path.join(root, "cfg", "flat.k"))
    rc, out = run(binary, root, "convert", "cfg/conv_out2.yaml")
    check("convert: output '../out/conv_out2' 도 YAML 폴더 기준으로 씀",
          rc == 0 and os.path.exists(os.path.join(root, "out", "conv_out2.k")), f"rc={rc} {out[-200:]}")

    # update 의 dynain — 노드 3개짜리 최소 dynain
    lines = open(os.path.join(root, "models", "flat.k")).read().splitlines()
    i = lines.index("*NODE") if "*NODE" in lines else -1
    nodes, j = [], i + 1
    while 0 <= i and j < len(lines) and not lines[j].startswith("*"):
        if not lines[j].startswith("$"):
            nodes.append(lines[j])
        j += 1
    write(os.path.join(root, "models", "dr.dynain"), "*KEYWORD\n*NODE\n" + "\n".join(nodes[:3]) + "\n*END\n")
    write(os.path.join(root, "cfg", "upd.yaml"),
          "base_model: ../models/flat.k\noutput: upd_out\noperations:\n  - type: update\n    dynain: ../models/dr.dynain\n")
    rc, out = run(binary, root, "update", "cfg/upd.yaml")
    check("update: model·dynain 의 '../models/...' 를 YAML 폴더 기준으로 찾음",
          rc == 0 and os.path.exists(os.path.join(root, "cfg", "upd_out.k")), f"rc={rc} {out[-200:]}")

    os.makedirs(os.path.join(root, "mesh"))
    for f in ("warpage_test_mesh.k", "warpage_cylindrical.dat"):
        shutil.copy(os.path.join(REPO, "tests", f), os.path.join(root, "mesh"))
    write(os.path.join(root, "cfg", "warp.yaml"),
          "base_model: ../mesh/warpage_test_mesh.k\noutput: warp_out\nmaterial:\n  E: 210000.0\n  nu: 0.3\n"
          "operations:\n  - type: warpage\n    target_pid: 1\n    dat_file: ../mesh/warpage_cylindrical.dat\n"
          "    plane: xy\n    deflection_axis: +z\n    unit: mm\n    mode: prestress\n    outside_behavior: clamp\n")
    rc, out = run(binary, root, "warpage", "cfg/warp.yaml")
    check("warpage: model·dat_file 의 '../mesh/...' 를 YAML 폴더 기준으로 찾음",
          rc == 0 and os.path.exists(os.path.join(root, "cfg", "warp_out.k")), f"rc={rc} {out[-300:]}")

    print("[절대 경로·같은 폴더 이름은 그대로]")
    write(os.path.join(root, "cfg", "abs.yaml"),
          "base_model: %s\noutput: %s\noperations:\n  - type: hex20\n"
          % (os.path.join(root, "models", "flat.k"), os.path.join(root, "out", "abs_out")))
    rc, out = run(binary, tmp, "convert", "root/cfg/abs.yaml")
    check("convert: 절대 경로는 YAML 폴더를 붙이지 않음",
          rc == 0 and os.path.exists(os.path.join(root, "out", "abs_out.k")), f"rc={rc} {out[-200:]}")
    write(os.path.join(root, "cfg", "plain.yaml"),
          "base_model: flat.k\noutput: plain_out\noperations:\n  - type: hex20\n")
    rc, out = run(binary, root, "convert", "cfg/plain.yaml")
    check("convert: 폴더 없는 이름(flat.k)은 예전처럼 YAML 폴더에서 찾음",
          rc == 0 and os.path.exists(os.path.join(root, "cfg", "plain_out.k")), f"rc={rc} {out[-200:]}")

    print("[operations 가 여러 개인 YAML 은 거부]")
    write(os.path.join(root, "cfg", "multi.yaml"),
          "base_model: flat.k\noutput: multi_out\noperations:\n  - type: hex20\n  - type: tet10\n")
    rc, out = run(binary, root, "convert", "cfg/multi.yaml")
    check("convert: 2개 operations → 오류(rc=1), 파일명과 assemble 안내",
          rc == 1 and "cfg/multi.yaml" in out and "assemble cfg/multi.yaml" in out, f"rc={rc} {out[-300:]}")
    check("convert: 2개 operations → 마지막 항목을 조용히 적용하지 않음",
          "TET10" not in out and not os.path.exists(os.path.join(root, "cfg", "multi_out.k")), out[-300:])

    write(os.path.join(root, "cfg", "multi_off.yaml"),
          "base_model: flat.k\noutput: multi_off_out\noperations:\n"
          "  - type: offset\n    source_pid: 1\n    thickness: 0.5\n    num_layers: 1\n"
          "    offset_direction: +z\n    new_pid: 10\n"
          "  - type: offset\n    source_pid: 1\n    thickness: 0.5\n    num_layers: 1\n"
          "    offset_direction: +x\n    new_pid: 11\n")
    rc, out = run(binary, root, "offset", "cfg/multi_off.yaml")
    check("offset: 2개 operations → 오류(rc=1), assemble 안내",
          rc == 1 and "assemble cfg/multi_off.yaml" in out, f"rc={rc} {out[-300:]}")

    rc, out = run(binary, root, "assemble", "cfg/multi.yaml")
    check("assemble: 같은 2개 operations YAML 은 그대로 실행 (rc=0)",
          rc == 0 and os.path.exists(os.path.join(root, "cfg", "multi_out.k")), f"rc={rc} {out[-300:]}")

    print("[operations 1개·목록이 중첩된 YAML 은 그대로 동작]")
    rc, out = run(binary, root, "convert", "cfg/plain.yaml")
    check("convert: operations 1개면 그 항목(hex20)을 적용", rc == 0 and "HEX20" in out, f"rc={rc} {out[-300:]}")

    write(os.path.join(root, "cfg", "restack.yaml"),
          "base_model: flat.k\noutput: restack_out\noperations:\n  - type: restack\n"
          "    target_pid: 1\n    direction: z\n    element_type: solid\n    layers:\n"
          "      - thickness: 1.0\n        material_card: |\n          *MAT_ELASTIC\n"
          "               MAT01  7.85E-09    210000       0.3\n"
          "      - thickness: 1.0\n        material_card: |\n          *MAT_ELASTIC\n"
          "               MAT02  7.85E-09    140000       0.3\n")
    rc, out = run(binary, root, "restack", "cfg/restack.yaml")
    check("restack: 항목 안의 layers 목록을 operations 로 세지 않음 (rc=0)",
          rc == 0 and os.path.exists(os.path.join(root, "cfg", "restack_out.k")), f"rc={rc} {out[-300:]}")

    write(os.path.join(root, "cfg", "flatstyle.yaml"),
          "model: flat.k\noutput: flatstyle_out\ntype: hex20\n")
    rc, out = run(binary, root, "convert", "cfg/flatstyle.yaml")
    check("convert: operations 없는 평면 YAML 도 그대로 동작 (rc=0)",
          rc == 0 and os.path.exists(os.path.join(root, "cfg", "flatstyle_out.k")), f"rc={rc} {out[-300:]}")

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
