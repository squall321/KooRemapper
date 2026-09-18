# 단독 명령 안전장치 회귀 시험 — 빈 output·블록 리스트·비유한 값·열 0 operations 를 실제 바이너리로 확인
"""
사용: python3 tools/regress/test_standalone_guards.py <KooRemapper 바이너리>

배경(감사에서 릴리스 바이너리로 재현된 결함)
  - A2  단독 op 은 output 이 비면 model 경로를 출력 이름으로 써 사용자 원본을 그 자리에서 덮어썼다.
        assemble 은 같은 설정을 rc=1 로 거부했다.
  - A3  offset 의 material_cards 를 키와 같은 열의 '- |' 블록 목록으로 쓰면(PyYAML 은 정상 파싱)
        조용히 버려져 rc=0 인데 덱의 *MAT 은 원본 1개뿐, 층 *PART 는 없는 MID 를 가리켰다.
  - A16 단독 restack 이 층의 title·num_elements·element_type 을 무시해 같은 YAML 본문인데
        assemble 과 다른 덱(제목 'Restack Layer N', 솔리드 100개 vs 250개)을 냈다.
  - A17a restack 의 direction 은 허용값 검사가 없어 엉뚱한 값이 조용히 auto 로 떨어졌다.
  - A18  비유한 값이 검증을 통과해 'nan' 토큰이 덱에 써지고도 rc=0 이었다.
  - A20  열 0 에 쓴 operations 목록이 'No operations defined' 로 끝나, 단독 명령의
        'assemble <파일> 로 실행하세요' 안내가 막다른 길이었다.
  - A36  대시 들여쓰기가 들쭉날쭉한 operations 목록(PyYAML 은 ParserError)을 절반만 적용했다.
"""
import hashlib
import os
import subprocess
import sys
import tempfile

FAILS = []

BOX = ("output: flat.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\n"
       "pid: 1\nmid: 1\nsecid: 1\n")

RESTACK_BODY = """target_pid: 1
direction: z
element_type: solid
interface_contact: tied
layers:
  - title: Glass_Top
    thickness: 0.7
    num_elements: 3
    element_type: solid
    material_card: |
      *MAT_ELASTIC
               @MID@   2.5E-9     71000      0.23
  - title: Adhesive
    thickness: 0.2
    num_elements: 2
    element_type: solid
    material_card: |
      *MAT_ELASTIC
               @MID@   1.1E-9      3000      0.35
"""

MAT_CARDS_SAME_COLUMN = """source_pid: 1
thickness: 1.0
num_layers: 2
offset_direction: +z
new_pid: 10
material_cards:
- |
  *MAT_ELASTIC
           @MID@       2.0     12000      0.25
- |
  *MAT_ELASTIC
           @MID@       3.0     20000      0.30
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


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def part_titles(path):
    """*PART 다음 제목 줄만 모은다 ($ 주석 줄은 건너뛴다)."""
    out = []
    lines = open(path).read().splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == "*PART":
            for nxt in lines[i + 1:]:
                if nxt.startswith("$"):
                    continue
                out.append(nxt.strip())
                break
    return out


def solid_lines(path):
    n, inside = 0, False
    for ln in open(path):
        ln = ln.rstrip("\n")
        if ln.startswith("*"):
            inside = ln.startswith("*ELEMENT_SOLID")
            continue
        if inside and ln.strip() and not ln.startswith("$"):
            n += 1
    return n


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="standalone_guards_")
    write(d, "box.yaml", BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    if rc != 0:
        print("생성 실패:", out[-400:])
        return 2

    # ── A2: output 이 비면 입력 모델을 덮어쓰지 않고 거부 ────────────────────────
    print("[A2] 빈 output 은 입력 모델을 덮어쓰지 않는다")
    src = os.path.join(d, "src2.k")
    open(src, "w").write(open(os.path.join(d, "flat.k")).read())
    before = md5(src)
    write(d, "a2.yaml", "model: src2.k\noutput:\ntype: hex20\ntarget_pid: 1\n")
    rc, out = run(binary, d, "convert", "a2.yaml")
    check("convert: 빈 output 을 rc=1 로 거부", rc == 1 and "output" in out, f"rc={rc} {out[-200:]}")
    check("convert: 입력 모델이 그대로 남음 (md5 동일)", md5(src) == before, "src2.k 가 바뀌었다")
    write(d, "a2b.yaml", "model: src2.k\noutput: \nsource_pid: 1\nthickness: 1.0\n")
    rc, out = run(binary, d, "offset", "a2b.yaml")
    check("offset: 빈 output 을 rc=1 로 거부", rc == 1 and "output" in out, f"rc={rc} {out[-200:]}")
    check("offset: 입력 모델이 그대로 남음 (md5 동일)", md5(src) == before, "src2.k 가 바뀌었다")

    # ── A3: material_cards 블록 목록의 대시가 키와 같은 열 ─────────────────────
    print("[A3] material_cards 대시가 키와 같은 열이어도 읽는다")
    write(d, "a3.yaml", "model: flat.k\noutput: a3out\n" + MAT_CARDS_SAME_COLUMN)
    rc, out = run(binary, d, "offset", "a3.yaml")
    deck = os.path.join(d, "a3out.k")
    mats = open(deck).read().count("\n*MAT") if os.path.exists(deck) else -1
    check("offset 단독: 카드 2장이 덱에 들어간다 (*MAT 3개)", rc == 0 and mats == 3,
          f"rc={rc} mats={mats} {out[-200:]}")
    # 층 *PART 가 가리키는 MID 가 덱에 실제로 있어야 LS-DYNA 가 돈다
    mids = set()
    if os.path.exists(deck):
        lines = open(deck).read().splitlines()
        for i, ln in enumerate(lines):
            if ln.startswith("*MAT"):
                for nxt in lines[i + 1:]:
                    if nxt.startswith("$") or nxt.startswith("*"):
                        continue
                    tok = nxt.split()
                    if tok:
                        mids.add(tok[0])
                    break
    check("offset 단독: 층 카드의 MID 2·3 이 덱에 있다", {"2", "3"} <= mids, str(sorted(mids)))

    asm_body = "base_model: flat.k\noutput: a3asm\noperations:\n  - type: offset\n" + \
               "".join("    " + ln + "\n" for ln in MAT_CARDS_SAME_COLUMN.splitlines())
    write(d, "a3asm.yaml", asm_body)
    rc, out = run(binary, d, "assemble", "a3asm.yaml")
    asmdeck = os.path.join(d, "a3asm.k")
    amats = open(asmdeck).read().count("\n*MAT") if os.path.exists(asmdeck) else -1
    check("assemble: 같은 열 대시도 카드 2장 (*MAT 3개)", rc == 0 and amats == 3,
          f"rc={rc} mats={amats} {out[-200:]}")
    write(d, "a3bad.yaml", "model: flat.k\noutput: a3bad\nsource_pid: 1\nthickness: 1.0\n"
                           "num_layers: 1\noffset_direction: +z\nnew_pid: 10\n"
                           "material_cards:\n  - \"*MAT_ELASTIC\"\n")
    rc, out = run(binary, d, "offset", "a3bad.yaml")
    check("offset: material_cards 에 '- |' 항목이 없으면 rc=1", rc == 1 and "material_cards" in out,
          f"rc={rc} {out[-200:]}")

    # ── A16: 단독 restack 이 assemble 과 같은 층 키를 읽는다 ───────────────────
    print("[A16] 단독 restack 과 assemble 의 결과가 같다")
    write(d, "rs_sa.yaml", "model: flat.k\noutput: rs_sa\n" + RESTACK_BODY)
    write(d, "rs_asm.yaml", "base_model: flat.k\noutput: rs_asm\noperations:\n  - type: restack\n" +
          "".join("    " + ln + "\n" for ln in RESTACK_BODY.splitlines()))
    rc1, o1 = run(binary, d, "restack", "rs_sa.yaml")
    rc2, o2 = run(binary, d, "assemble", "rs_asm.yaml")
    sa, asmk = os.path.join(d, "rs_sa.k"), os.path.join(d, "rs_asm.k")
    ok = rc1 == 0 and rc2 == 0 and os.path.exists(sa) and os.path.exists(asmk)
    check("restack 단독·assemble 둘 다 rc=0", ok, f"rc={rc1}/{rc2} {o1[-150:]} {o2[-150:]}")
    if ok:
        check("restack 단독: 층 title 이 PART 제목으로 (Glass_Top·Adhesive)",
              "Glass_Top" in part_titles(sa) and "Adhesive" in part_titles(sa), str(part_titles(sa)))
        check("restack 단독: num_elements 대로 층을 나눔 (assemble 과 같은 솔리드 수)",
              solid_lines(sa) == solid_lines(asmk) and solid_lines(sa) > 200,
              f"단독={solid_lines(sa)} assemble={solid_lines(asmk)}")
        check("restack: 두 명령의 덱이 완전히 같다",
              open(sa).read() == open(asmk).read(), "덱이 다르다")

    # ── A17a: restack direction 허용값 ────────────────────────────────────────
    print("[A17a] restack direction 허용값 검사")
    for val in ("z", "+z", "-z", "x", "auto"):
        write(d, "rsd.yaml", "model: flat.k\noutput: rsd\n" +
              RESTACK_BODY.replace("direction: z", "direction: " + val))
        rc, out = run(binary, d, "restack", "rsd.yaml")
        check(f"restack: direction '{val}' 는 허용 (rc=0)", rc == 0, f"rc={rc} {out[-200:]}")
    for val in ("bogus", "zz", "+w"):
        write(d, "rsd.yaml", "model: flat.k\noutput: rsd\n" +
              RESTACK_BODY.replace("direction: z", "direction: " + val))
        rc, out = run(binary, d, "restack", "rsd.yaml")
        check(f"restack: direction '{val}' 는 허용값 목록과 함께 rc=1",
              rc == 1 and "invalid direction" in out and "+z" in out, f"rc={rc} {out[-200:]}")

    # ── A18: 비유한 값은 파일로 남지 않는다 ───────────────────────────────────
    print("[A18] nan/inf 는 덱에 써지지 않는다")
    write(d, "bnan.yaml", "model: flat.k\noutput: bnan\ntarget_pid: 1\nplane: xy\nmode: deform\n"
                          "source: formula\nexpression: sqrt(-x1)\n")
    rc, out = run(binary, d, "bend", "bnan.yaml")
    check("bend: nan 좌표를 만드는 수식은 rc=1", rc == 1, f"rc={rc} {out[-250:]}")
    check("bend: nan 덱이 파일로 남지 않는다", not os.path.exists(os.path.join(d, "bnan.k")))
    write(d, "bok.yaml", "model: flat.k\noutput: bok\ntarget_pid: 1\nplane: xy\nmode: deform\n"
                         "source: formula\nexpression: 0.1*x1\n")
    rc, out = run(binary, d, "bend", "bok.yaml")
    check("bend: 정상 수식은 그대로 rc=0", rc == 0 and os.path.exists(os.path.join(d, "bok.k")),
          f"rc={rc} {out[-200:]}")
    write(d, "idnan.yaml", "model: flat.k\noutput: idnan\ntarget_pid: 1\nplane: xy\ndirection: -z\n"
                           "depth: nan\nr1: 1.0\nr2: 0.5\nshape:\n  type: polygon\n  points:\n"
                           "    - [2,2]\n    - [8,2]\n    - [8,6]\n")
    rc, out = run(binary, d, "indent", "idnan.yaml")
    check("indent: depth: nan 은 rc=1", rc == 1 and "finite" in out, f"rc={rc} {out[-200:]}")
    check("indent: nan 덱이 파일로 남지 않는다", not os.path.exists(os.path.join(d, "idnan.k")))
    write(d, "ofnan.yaml", "model: flat.k\noutput: ofnan\nsource_pid: 1\nthickness: nan\n"
                           "num_layers: 1\noffset_direction: +z\nnew_pid: 10\nmaterial_card: |\n"
                           "  *MAT_ELASTIC\n           @MID@       2.0     12000      0.25\n")
    rc, out = run(binary, d, "offset", "ofnan.yaml")
    check("offset: thickness: nan 은 rc=1", rc == 1 and "finite" in out, f"rc={rc} {out[-200:]}")
    check("offset: nan 덱이 파일로 남지 않는다", not os.path.exists(os.path.join(d, "ofnan.k")))
    write(d, "bdiv.yaml", "model: flat.k\noutput: bdiv\ntarget_pid: 1\nplane: xy\nmode: deform\n"
                          "source: formula\nexpression: 1/0\n")
    rc, out = run(binary, d, "bend", "bdiv.yaml")
    check("bend: 0 나누기 경로는 예전처럼 rc=1", rc == 1 and "Division by zero" in out,
          f"rc={rc} {out[-200:]}")

    # ── A20: 열 0 operations 목록 ─────────────────────────────────────────────
    print("[A20] 열 0 에 쓴 operations 목록도 읽는다")
    write(d, "col0.yaml", "base_model: flat.k\noutput: col0out\noperations:\n"
                          "- type: quad8\n  target_pid: 1\n- type: tria6\n  target_pid: 1\n")
    rc, out = run(binary, d, "convert", "col0.yaml")
    check("convert: operations 2개라 assemble 로 안내 (rc=1)",
          rc == 1 and "assemble" in out, f"rc={rc} {out[-200:]}")
    rc, out = run(binary, d, "assemble", "col0.yaml")
    check("assemble: 안내대로 돌리면 실제로 동작 (rc=0)",
          rc == 0 and os.path.exists(os.path.join(d, "col0out.k")), f"rc={rc} {out[-250:]}")
    write(d, "rs_col0.yaml", "base_model: flat.k\noutput: rs_col0\noperations:\n- type: restack\n" +
          "".join("  " + ln + "\n" for ln in RESTACK_BODY.splitlines()))
    rc, out = run(binary, d, "assemble", "rs_col0.yaml")
    col0 = os.path.join(d, "rs_col0.k")
    check("assemble: 열 0 항목의 하위 목록(layers)도 그대로 읽는다",
          rc == 0 and os.path.exists(col0) and "Glass_Top" in part_titles(col0),
          f"rc={rc} {out[-250:]}")

    # ── A36: 들쭉날쭉한 대시 들여쓰기 ─────────────────────────────────────────
    print("[A36] 대시 들여쓰기가 일관되지 않으면 거부한다")
    write(d, "mixed4.yaml", "model: flat.k\noutput: mixedout\noperations:\n"
                            "  - type: quad8\n    target_pid: 1\n"
                            "    - type: tria6\n      target_pid: 1\n")
    rc, out = run(binary, d, "convert", "mixed4.yaml")
    check("convert: 절반만 적용하지 않고 rc=1 로 거부", rc == 1 and "들여쓰기" in out,
          f"rc={rc} {out[-250:]}")
    check("convert: 절반 적용된 출력이 남지 않는다", not os.path.exists(os.path.join(d, "mixedout.k")))
    # 정상 하위 목록은 거부되지 않아야 한다
    write(d, "ok_sub.yaml", "model: flat.k\noutput: ok_sub\noperations:\n  - type: restack\n" +
          "".join("    " + ln + "\n" for ln in RESTACK_BODY.splitlines()))
    rc, out = run(binary, d, "restack", "ok_sub.yaml")
    check("restack: operations 1개 + layers 하위 목록은 그대로 rc=0",
          rc == 0 and os.path.exists(os.path.join(d, "ok_sub.k")), f"rc={rc} {out[-250:]}")

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
