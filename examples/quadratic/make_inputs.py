# quadratic 예제 입력(사각형+삼각형 혼합 셸, TET4 블록)을 KooRemapper 명령으로 재현 생성
"""
사용 (examples/quadratic 에서):  python3 make_inputs.py <KooRemapper 바이너리>

만드는 파일
  shell_mixed.k  PID 1 QUAD4(박스 윗면 25개) + PID 2 TRIA3(사면체 블록 윗면) — quad8·tria6·combined·refine_quad 입력
  tet4_block.k   TET4 솔리드 블록 — refine_tet 입력

예전 입력 이름(shell_test.k·tet_test.k)은 .gitignore 의 '*_test.k'(시험 산출물용)에 걸려 한 번도 커밋되지 않아
예제가 입력 없이 실패했다. 입력은 이 이름으로 커밋한다.
"""
import os
import shutil
import subprocess
import sys
import tempfile


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"실패: {' '.join(args)}\n{p.stdout}{p.stderr}")


def read_shell(path):
    """(노드 {nid: (x,y,z)}, 요소 [(eid, n1..n4)])"""
    nodes, elems, sec = {}, [], None
    for s in open(path).read().splitlines():
        if s.startswith("*"):
            sec = s.strip().upper()
            continue
        if not s.strip() or s.startswith("$"):
            continue
        if sec == "*NODE":
            nodes[int(s[0:8])] = (float(s[8:24]), float(s[24:40]), float(s[40:56]))
        elif sec == "*ELEMENT_SHELL":
            elems.append(tuple(int(s[k:k + 8]) for k in (0, 16, 24, 32, 40)))
    return nodes, elems


def main():
    binary = os.path.abspath(sys.argv[1])
    here = os.path.dirname(os.path.abspath(__file__))
    tmp = tempfile.mkdtemp(prefix="quad_inputs_")

    open(os.path.join(tmp, "box.yaml"), "w").write(
        "output: box.k\nlx: 10.0\nly: 10.0\nlz: 2.0\nnx: 5\nny: 5\nnz: 1\n"
        "rho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\npart_title: BOX\n")
    run(binary, tmp, "generate", "box", "box.yaml")
    run(binary, tmp, "extract-surface", "box.k", "quad.k", "--face", "top")
    run(binary, tmp, "generate", "--dim-i", "4", "--dim-j", "2", "--dim-k", "2", "arc", "demo")
    run(binary, tmp, "extract-surface", "demo_flat_tet.k", "tri.k", "--face", "top")

    qn, qe = read_shell(os.path.join(tmp, "quad.k"))
    tn, te = read_shell(os.path.join(tmp, "tri.k"))
    noff, eoff = max(qn), max(e[0] for e in qe)
    xs = min(x for x, _, _ in tn.values())
    dx = max(x for x, _, _ in qn.values()) + 5.0 - xs  # 삼각형 영역을 박스 옆으로 옮겨 겹치지 않게

    out = ["*KEYWORD", "*PART", "QUAD_REGION", "$#     pid     secid       mid",
           "         1         1         1", "*PART", "TRIA_REGION", "$#     pid     secid       mid",
           "         2         1         1", "*SECTION_SHELL", "$#   secid    elform",
           "         1         2", "$#      t1        t2        t3        t4",
           "       1.0       1.0       1.0       1.0", "*MAT_ELASTIC", "$#     mid        ro         e        pr",
           "         1  7.85E-09  2.10E+05       0.3", "*NODE"]
    for nid, (x, y, z) in sorted(qn.items()):
        out.append(f"{nid:8d}{x:16.7e}{y:16.7e}{z:16.7e}")
    for nid, (x, y, z) in sorted(tn.items()):
        out.append(f"{nid + noff:8d}{x + dx:16.7e}{y:16.7e}{z:16.7e}")
    out.append("*ELEMENT_SHELL")
    for eid, *ns in qe:
        out.append(f"{eid:8d}{1:8d}" + "".join(f"{n:8d}" for n in ns))
    for eid, *ns in te:
        out.append(f"{eid + eoff:8d}{2:8d}" + "".join(f"{n + noff:8d}" for n in ns))
    out.append("*END")
    open(os.path.join(here, "shell_mixed.k"), "w").write("\n".join(out) + "\n")
    shutil.copy(os.path.join(tmp, "demo_flat_tet.k"), os.path.join(here, "tet4_block.k"))
    print(f"shell_mixed.k: QUAD4 {len(qe)} + TRIA3 {len(te)} / tet4_block.k")


if __name__ == "__main__":
    main()
