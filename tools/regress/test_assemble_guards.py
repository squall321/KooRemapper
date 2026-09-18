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

적대적 검토에서 다시 잡힌 것(같은 그물의 뒷면)
  - 그물이 '쓰기 전' 으로 올라갔는데도 출력 경로의 기존 파일을 지웠다 — output 이 base_model 과
        같으면 입력 메시가 사라지고, nan 이 입력 덱에서 온 경우엔 이 도구가 쓴 적 없는 파일이 지워졌다.
  - 문자열 그물이 토큰 단위라서, 자기가 쓰는 *INITIAL_STRESS_* 의 고정 칸(setw(10))처럼 음수 값이
        앞 칸에 붙으면('-nan-0.000e+00') nan 을 놓쳤다. dynain_embed 모드에는 텐서 검사도 없었다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILS = []

BOX = ("output: flat.k\nlx: 10.0\nly: 10.0\nlz: 1.0\nnx: 10\nny: 10\nnz: 1\n"
       "pid: 1\nmid: 1\nsecid: 1\n")

BEND = """base_model: %s
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

# 덱을 거의 그대로 통과시키는 op — 입력 덱에 있던 값이 출력으로 나가는 길을 본다
PASSTHRU = """base_model: %s
output: %s
operations:
  - type: boundary
    boundaries:
      - part: 1
        dof: xyz
        select: direction
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


def read(d, name):
    return open(os.path.join(d, name), "rb").read()


# *INITIAL_STRESS_SOLID 한 줄 — 첫 칸 값과 둘째 칸 앞 구분자를 골라 넣는다.
# 작성기(setw(10))가 내는 폭 그대로다: 음수 값은 정확히 10글자여서 앞 칸에 붙는다.
STRESS_BLOCK = ("*INITIAL_STRESS_SOLID\n"
                "$#    eid    nint   nhisv   large     ics   ncomp\n"
                "         1       1       0       0       0       0\n"
                "$#  sigxx     sigyy     sigzz     sigxy     sigyz     sigxz       eps\n"
                "%10s%s0.000e+00-0.000e+00 0.000e+00-0.000e+00-0.000e+00 0.000e+00\n")


def deck_with_stress(d, src, name, first, sep):
    """flat.k 의 *END 앞에 *INITIAL_STRESS_SOLID 블록을 끼운 덱을 만든다."""
    body = open(os.path.join(d, src)).read()
    block = STRESS_BLOCK % (first, sep)
    idx = body.rfind("*END")
    open(os.path.join(d, name), "w").write(body[:idx] + block + body[idx:])
    return name


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
    write(d, "aok.yaml", BEND % ("flat.k", "aok", "0.01*x1"))
    rc, out = run(binary, d, "assemble", "aok.yaml")
    check("assemble bend 정상: .k 와 .dynain 이 나온다 (rc=0)",
          rc == 0 and exists(d, "aok.k") and exists(d, "aok.dynain"), f"rc={rc} {out[-200:]}")

    write(d, "anan.yaml", BEND % ("flat.k", "anan", "sqrt(-x1)"))
    rc, out = run(binary, d, "assemble", "anan.yaml")
    check("assemble bend nan: rc=1", rc == 1, f"rc={rc} {out[-250:]}")
    check("assemble bend nan: .k 가 만들어지지 않는다", not exists(d, "anan.k"))
    check("assemble bend nan: .dynain 도 만들어지지 않는다", not exists(d, "anan.dynain"))
    check("assemble bend nan: 쓰지 않은 파일 이름을 메시지에 적는다",
          "anan.k" in out and "anan.dynain" in out, out[-250:])

    # 쓰기 전에 막으므로 이번 실행이 만든 파일은 하나도 없다 — 같은 경로에 있던 남의 파일도 지우지 않는다
    prev_k, prev_dyn = read(d, "aok.k"), read(d, "aok.dynain")
    write(d, "anan2.yaml", BEND % ("flat.k", "aok", "sqrt(-x1)"))
    rc, out = run(binary, d, "assemble", "anan2.yaml")
    check("assemble bend nan: 같은 경로의 지난 .k 를 지우지 않는다",
          rc == 1 and exists(d, "aok.k") and read(d, "aok.k") == prev_k, f"rc={rc} {out[-250:]}")
    check("assemble bend nan: 같은 경로의 지난 .dynain 도 그대로다",
          exists(d, "aok.dynain") and read(d, "aok.dynain") == prev_dyn)

    # in-place 출력(output == base_model): 입력 메시가 사라지면 수식을 고쳐 다시 돌릴 수도 없다
    shutil.copyfile(os.path.join(d, "flat.k"), os.path.join(d, "inplace.k"))
    src = read(d, "inplace.k")
    write(d, "ip.yaml", BEND % ("inplace.k", "inplace", "sqrt(-x1)"))
    rc, out = run(binary, d, "assemble", "ip.yaml")
    check("assemble bend nan: in-place 출력에서 입력 덱이 그대로 남는다",
          rc == 1 and exists(d, "inplace.k") and read(d, "inplace.k") == src, f"rc={rc} {out[-250:]}")

    # 고정 칸 서식(*INITIAL_STRESS_*)에서 음수 값은 앞 칸에 붙는다 — 붙어도 nan 을 잡아야 한다
    for tag, first, sep, want in (("붙은 칸", "-nan", "-", 1),
                                  ("떨어진 칸", "-nan", " ", 1),
                                  ("정상 값(붙은 칸)", "-0.000e+00", "-", 0)):
        name = "st_%d_%s" % (want, "abut" if sep == "-" else "sep")
        deck_with_stress(d, "flat.k", name + ".k", first, sep)
        write(d, name + ".yaml", PASSTHRU % (name + ".k", name + "out"))
        rc, out = run(binary, d, "assemble", name + ".yaml")
        if want:
            check(f"*INITIAL_STRESS_SOLID 의 nan — {tag} 도 rc=1",
                  rc == 1 and not exists(d, name + "out.k"), f"rc={rc} {out[-250:]}")
        else:
            check(f"*INITIAL_STRESS_SOLID — {tag} 은 그대로 rc=0",
                  rc == 0 and exists(d, name + "out.k"), f"rc={rc} {out[-250:]}")

    # dynain_embed 모드에도 같은 그물이 있다(초기 응력이 .k 본문으로 들어간다)
    write(d, "emok.yaml", "dynain_embed: true\n" + BEND % ("flat.k", "emok", "0.01*x1"))
    rc, out = run(binary, d, "assemble", "emok.yaml")
    check("dynain_embed 정상: .k 가 나온다 (rc=0)",
          rc == 0 and exists(d, "emok.k"), f"rc={rc} {out[-250:]}")
    write(d, "emnan.yaml", "dynain_embed: true\n" + BEND % ("flat.k", "emnan", "sqrt(-x1)"))
    rc, out = run(binary, d, "assemble", "emnan.yaml")
    check("dynain_embed + nan: rc=1 이고 .k 가 만들어지지 않는다",
          rc == 1 and not exists(d, "emnan.k"), f"rc={rc} {out[-250:]}")

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
