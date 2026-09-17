# 단독 명령 값 검증(assemble 과 동일 규칙)·현재 폴더 YAML 상대 경로 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_standalone_validation.py <KooRemapper 바이너리>

배경
  - 단독 bend·indent·offset·restack·iga 는 assemble 의 값 검증을 거치지 않았다. help bend 의 YAML 을 그대로
    넣으면(source 없음) SIGSEGV, indent 는 points·r1/r2 가 없으면 잡히지 않은 예외로 abort(134) 했고,
    offset connection_mode: shared·iga element_size: 0·restack 층 없음은 오류 없이 통과했다.
  - warpage dat_file·assemble update 의 dynain 은 YAML 이 현재 폴더에 있으면 '/파일'(루트)에서 찾았다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

BOX = "output: flat.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\npid: 1\nmid: 1\nsecid: 1\n"


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def rejects(binary, d, cmd, body, expect):
    name = f"{cmd}_{abs(hash(body)) % 100000}"
    open(os.path.join(d, name + ".yaml"), "w").write("model: flat.k\noutput: o_" + name + "\n" + body)
    rc, out = run(binary, d, cmd, name + ".yaml")
    check(f"{cmd}: '{expect}' 오류로 거부 (rc=1, 충돌 아님)", rc == 1 and expect in out, f"rc={rc} {out[-200:]}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="standalone_val_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")

    print("[단독 명령 값 검증]")
    rejects(binary, d, "bend", "target_pid: 1\nplane: xy\nmode: deform\nexpression: \"0.1*x1\"\n", "invalid source")
    rejects(binary, d, "bend", "target_pid: 1\nplane: xz\nmode: deform\nsource: formula\nexpression: \"0.1*x1\"\n",
            "invalid plane")
    rejects(binary, d, "indent", "target_pid: 1\ndepth: 0.5\nr1: 1.0\nr2: 0.5\n", "at least 3 points")
    rejects(binary, d, "indent", "target_pid: 1\ndepth: 0.5\nshape:\n  type: polygon\n  points:\n"
            "    - [1,1]\n    - [5,1]\n    - [5,5]\n", "r1 and r2 must be positive")
    rejects(binary, d, "offset", "source_pid: 1\nthickness: 1.0\nconnection_mode: shared\n", "connection_mode must be")
    rejects(binary, d, "iga", "targets:\n  - target_pid: 1\n    element_size: 0\n", "element_size must be positive")
    rejects(binary, d, "restack", "target_pid: 1\n", "no layers defined")

    print("[현재 폴더 YAML 의 상대 경로]")
    w = tempfile.mkdtemp(prefix="warp_cwd_")
    for f in ("warpage_test_mesh.k", "warpage_cylindrical.dat"):
        shutil.copy(os.path.join(REPO, "tests", f), w)
    open(os.path.join(w, "w.yaml"), "w").write(
        "base_model: warpage_test_mesh.k\noutput: wres\nmaterial:\n  E: 210000.0\n  nu: 0.3\noperations:\n"
        "  - type: warpage\n    target_pid: 1\n    dat_file: warpage_cylindrical.dat\n    plane: xy\n"
        "    deflection_axis: +z\n    unit: mm\n    mode: prestress\n    outside_behavior: clamp\n")
    for cmd in ("warpage", "assemble"):
        rc, out = run(binary, w, cmd, "w.yaml")
        check(f"{cmd}: dat_file 을 YAML 폴더(현재 폴더)에서 찾음", rc == 0 and "Cannot open file: /" not in out,
              f"rc={rc} {out[-200:]}")

    u = tempfile.mkdtemp(prefix="update_cwd_")
    open(os.path.join(u, "box.yaml"), "w").write(BOX)
    run(binary, u, "generate", "box", "box.yaml")
    nodes = []
    lines = open(os.path.join(u, "flat.k")).read().splitlines()
    i = lines.index("*NODE") if "*NODE" in lines else -1
    j = i + 1
    while 0 <= i and j < len(lines) and not lines[j].startswith("*"):
        if not lines[j].startswith("$"):
            nodes.append(lines[j])
        j += 1
    open(os.path.join(u, "dr.dynain"), "w").write("*KEYWORD\n*NODE\n" + "\n".join(nodes[:3]) + "\n*END\n")
    open(os.path.join(u, "u.yaml"), "w").write(
        "base_model: flat.k\noutput: upd\noperations:\n  - type: update\n    dynain: dr.dynain\n")
    rc, out = run(binary, u, "assemble", "u.yaml")
    check("assemble update: dynain 을 YAML 폴더(현재 폴더)에서 찾음", rc == 0 and "cannot open dynain" not in out,
          f"rc={rc} {out[-200:]}")

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
