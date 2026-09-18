# assemble 경로의 nan/inf 그물과 enum 검증 회귀 시험 — 빌드 바이너리로 실제 실행해 확인
"""
사용: python3 tools/regress/test_assemble_guards.py <KooRemapper 바이너리>

배경(감사에서 재현된 결함)
  - Y1 단독 명령은 결과에 nan/inf 가 있으면 rc=1 로 죽고 출력 파일을 지우는데, 같은 bend 설정
        (expression: sqrt(-x1))을 assemble 로 돌리면 rc=0 에 nan 199줄짜리 덱이 그대로 나왔다.
  - Y2 restack 의 element_type 이 shell/tshell 이 아니면 어떤 문자열이든(hex, 오타 포함) 조용히
        solid 로 떨어졌다. 층(layer)별 element_type 도 같았다.
  - Y3 damping_preset 이 인식되지 않는 문자열도 조용히 삼켰다(프리셋 없음으로 떨어지면서 묵은
        *DAMPING_PART_* 제거만 촉발했다).
  - Y4 boundary/rbe 의 select 값 검증이 없어, boundary 는 'all' 같은 값이 조용히 direction 이 되고
        rbe 는 반대로 오타가 조용히 'all'(면 전체)이 됐다.
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILS = []

BOX = ("output: flat.k\nlx: 10.0\nly: 10.0\nlz: 1.0\nnx: 10\nny: 10\nnz: 1\n"
       "pid: 1\nmid: 1\nsecid: 1\n")

BEND = """base_model: flat.k
output: %s
material:
  E: 210000
  nu: 0.3
operations:
  - type: bend
    target_pid: 1
    plane: xy
    mode: deform
    source: formula
    expression: %s
"""

RESTACK = """base_model: flat.k
output: rs
material:
  E: 210000
  nu: 0.3
operations:
  - type: restack
    target_pid: 1
    direction: z
    element_type: %s
    layers:
      - thickness: 0.5
%s        material_card: |
          *MAT_ELASTIC
                 MID001   2.5E-9     71000      0.23
      - thickness: 0.5
        material_card: |
          *MAT_ELASTIC
                 MID002   2.5E-9     71000      0.23
"""

MATDB = """base_model: flat.k
output: md
operations:
  - type: matdb
%s"""

BOUNDARY = """base_model: flat.k
output: bc
operations:
  - type: boundary
    boundaries:
      - part: 1
        dof: xyz
        select: %s
        direction: [0, 0, -1]
"""

RBE = """base_model: flat.k
output: rb
operations:
  - type: rbe
    constraints:
      - part: 1
        select: %s
        direction: [0, 0, -1]
        type: rbe3
        mode: spider
"""


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def write(d, name, body):
    open(os.path.join(d, name), "w").write(body)
    return name


def exists(d, name):
    return os.path.exists(os.path.join(d, name))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="assemble_guards_")
    write(d, "box.yaml", BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    if rc != 0:
        print("생성 실패:", out[-400:])
        return 2

    # ── Y1: assemble 도 nan/inf 를 쓰지 않는다 ────────────────────────────────
    print("[Y1] assemble 결과의 nan/inf 는 파일로 나가지 않는다")
    write(d, "aok.yaml", BEND % ("aok", "0.01*x1"))
    rc, out = run(binary, d, "assemble", "aok.yaml")
    check("assemble bend 정상: .k 와 .dynain 이 나온다 (rc=0)",
          rc == 0 and exists(d, "aok.k") and exists(d, "aok.dynain"), f"rc={rc} {out[-200:]}")

    write(d, "anan.yaml", BEND % ("anan", "sqrt(-x1)"))
    rc, out = run(binary, d, "assemble", "anan.yaml")
    check("assemble bend nan: rc=1", rc == 1, f"rc={rc} {out[-250:]}")
    check("assemble bend nan: .k 가 만들어지지 않는다", not exists(d, "anan.k"))
    check("assemble bend nan: .dynain 도 만들어지지 않는다", not exists(d, "anan.dynain"))
    check("assemble bend nan: 쓰지 않은 파일 이름을 메시지에 적는다",
          "anan.k" in out and "anan.dynain" in out, out[-250:])

    # 같은 이름으로 다시 돌리면 지난 실행의 결과가 남지 않는다(단독 nan 정리와 같은 끝 상태)
    write(d, "anan2.yaml", BEND % ("aok", "sqrt(-x1)"))
    rc, out = run(binary, d, "assemble", "anan2.yaml")
    check("assemble bend nan: 같은 경로의 지난 .k 가 남지 않는다",
          rc == 1 and not exists(d, "aok.k"), f"rc={rc} {out[-250:]}")
    check("assemble bend nan: 같은 경로의 지난 .dynain 도 남지 않는다", not exists(d, "aok.dynain"))

    # ── Y2: restack element_type ──────────────────────────────────────────────
    print("[Y2] restack 의 element_type 은 허용값만 받는다")
    for val in ("solid", "tshell", "shell"):
        write(d, "rs.yaml", RESTACK % (val, ""))
        rc, out = run(binary, d, "assemble", "rs.yaml")
        check(f"restack: element_type '{val}' 는 그대로 rc=0", rc == 0, f"rc={rc} {out[-250:]}")
    for val in ("hex", "sold", "SOLID"):
        write(d, "rs.yaml", RESTACK % (val, ""))
        rc, out = run(binary, d, "assemble", "rs.yaml")
        check(f"restack: element_type '{val}' 는 허용값 목록과 함께 rc=1",
              rc == 1 and "element_type" in out and "solid, tshell, shell" in out,
              f"rc={rc} {out[-250:]}")
    write(d, "rs.yaml", RESTACK % ("solid", "        element_type: shell\n"))
    rc, out = run(binary, d, "assemble", "rs.yaml")
    check("restack: 층의 element_type 'shell' 은 rc=0", rc == 0, f"rc={rc} {out[-250:]}")
    write(d, "rs.yaml", RESTACK % ("solid", "        element_type: hex\n"))
    rc, out = run(binary, d, "assemble", "rs.yaml")
    check("restack: 층의 element_type 'hex' 는 층 번호와 함께 rc=1",
          rc == 1 and "layers[0]" in out and "solid, tshell, shell" in out, f"rc={rc} {out[-250:]}")

    # ── Y3: damping_preset ────────────────────────────────────────────────────
    print("[Y3] matdb 의 damping_preset 은 허용값만 받는다")
    os.symlink(os.path.join(ROOT, "materials"), os.path.join(d, "materials"))
    for val in ("smartphone_drop", "smartphone_drop_aggressive", "quasi_static", "off"):
        write(d, "md.yaml", MATDB % ("    damping_preset: %s\n" % val))
        rc, out = run(binary, d, "assemble", "md.yaml")
        check(f"matdb: damping_preset '{val}' 는 그대로 rc=0", rc == 0, f"rc={rc} {out[-250:]}")
    write(d, "md.yaml", MATDB % "")
    rc, out = run(binary, d, "assemble", "md.yaml")
    check("matdb: damping_preset 키를 아예 빼면 rc=0", rc == 0, f"rc={rc} {out[-250:]}")
    for val in ("light", "moderate", "heavy", "custom", "smartphone-drop"):
        write(d, "md.yaml", MATDB % ("    damping_preset: %s\n" % val))
        rc, out = run(binary, d, "assemble", "md.yaml")
        check(f"matdb: damping_preset '{val}' 는 허용값 목록과 함께 rc=1",
              rc == 1 and "damping_preset" in out and "quasi_static, off" in out,
              f"rc={rc} {out[-250:]}")

    # ── Y4: boundary/rbe 의 select ────────────────────────────────────────────
    print("[Y4] boundary/rbe 의 select 는 허용값만 받는다")
    write(d, "bc.yaml", BOUNDARY % "direction")
    rc, out = run(binary, d, "assemble", "bc.yaml")
    check("boundary: select 'direction' 은 그대로 rc=0", rc == 0, f"rc={rc} {out[-250:]}")
    for val in ("all", "tied", "bogus"):
        write(d, "bc.yaml", BOUNDARY % val)
        rc, out = run(binary, d, "assemble", "bc.yaml")
        check(f"boundary: select '{val}' 는 허용값 목록과 함께 rc=1",
              rc == 1 and "select" in out and "direction, set" in out, f"rc={rc} {out[-250:]}")
    # select: set 은 값 자체는 허용값이다 — 거절 사유가 enum 이 아니라 set_id 여야 한다
    write(d, "bc.yaml", BOUNDARY % "set")
    rc, out = run(binary, d, "assemble", "bc.yaml")
    check("boundary: select 'set' 은 enum 이 아니라 set_id 로 걸린다",
          rc == 1 and "set_id" in out, f"rc={rc} {out[-250:]}")

    for val in ("direction", "all"):
        write(d, "rb.yaml", RBE % val)
        rc, out = run(binary, d, "assemble", "rb.yaml")
        check(f"rbe: select '{val}' 는 그대로 rc=0", rc == 0, f"rc={rc} {out[-250:]}")
    for val in ("set", "tied", "bogus"):
        write(d, "rb.yaml", RBE % val)
        rc, out = run(binary, d, "assemble", "rb.yaml")
        check(f"rbe: select '{val}' 는 허용값 목록과 함께 rc=1",
              rc == 1 and "select" in out and "direction, all" in out, f"rc={rc} {out[-250:]}")

    # 단독 boundary/rbe 도 같은 경로를 지난다
    write(d, "sbc.yaml", "model: flat.k\noutput: sbc\nboundaries:\n  - part: 1\n"
                         "    dof: xyz\n    select: all\n    direction: [0, 0, -1]\n")
    rc, out = run(binary, d, "boundary", "sbc.yaml")
    check("단독 boundary: select 'all' 도 같은 규칙으로 rc=1",
          rc == 1 and "direction, set" in out, f"rc={rc} {out[-250:]}")

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
