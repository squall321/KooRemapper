# load·boundary·rbe·strip·merge 단독 YAML 목록 파싱(인라인 주석·곡선 목록 끝) 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_load_strip_yaml_parsing.py <KooRemapper 바이너리>

배경
  - load 곡선 점 '- [0.0, 0.0]   # 주석' 은 ']' 로 끝나지 않는다고 조용히 버려졌다.
  - load 곡선 목록 뒤의 다음 하중 항목 '- part: 1' 이 곡선 점으로 삼켜져, 두 번째 하중의 하위 키가
    첫 하중을 덮어써 하중 케이스가 하나로 합쳐졌다.
  - 대시 줄 첫 키 값에서 주석을 떼지 않았다 — load '- mode: force   # 주석' 이 압력으로, '- part: PLATE   # 주석'
    은 'Cannot resolve part', boundary '- dof: xyz   # 주석' 이 6자유도 전부 구속, rbe '- mode: spider   # 주석'
    이 face 로, '- select: direction   # 주석' 이 무시돼 전체 면으로 돌았다.
  - strip 목록 '- "*NODE"   # 주석' 이 주석째 키워드가 돼 아무것도 지우지 못했다(302 → 0줄).
  - merge pids 블록 목록 '- 1   # 주석' 도 주석째 읽었다(stoi 가 앞 숫자만 읽어 드러나진 않음 — 일관성 확인).
"""
import os
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def body(d, name):
    """'$' 주석 줄을 뺀 산출 k 본문 (없으면 None)"""
    path = os.path.join(d, name + ".k")
    if not os.path.exists(path):
        return None
    return [l for l in open(path).read().splitlines() if not l.startswith("$")]


def cfg(binary, d, cmd, name, text):
    open(os.path.join(d, name + ".yaml"), "w").write(text.replace("@OUT@", name + ".k"))
    return run(binary, d, cmd, name + ".yaml")


def same_as_plain(binary, d, cmd, name, plain, commented):
    """주석 없는 설정과 주석 붙인 설정의 rc·산출 k 가 같은지"""
    rc0, out0 = cfg(binary, d, cmd, name + "_plain", plain)
    rc1, out1 = cfg(binary, d, cmd, name + "_cmt", commented)
    b0, b1 = body(d, name + "_plain"), body(d, name + "_cmt")
    return rc0 == 0 and rc1 == 0 and b0 is not None and b0 == b1, f"rc={rc0},{rc1} {out1[-300:]}"


def curve_points(lines):
    """첫 *DEFINE_CURVE 의 점 수"""
    if lines is None or "*DEFINE_CURVE" not in lines:
        return -1
    i = lines.index("*DEFINE_CURVE") + 2
    n = 0
    while i < len(lines) and not lines[i].startswith("*"):
        n += 1
        i += 1
    return n


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="load_strip_yaml_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")

    print("[load 곡선 목록]")
    rc, out = cfg(binary, d, "load", "l_curve", "model: box.k\noutput: @OUT@\nloads:\n"
                  "  - part: 1\n    mode: pressure\n    value: 1.0\n    direction: [0, 0, 1]\n    select: direction\n"
                  "    curve:\n      - [0.0, 0.0]   # 시작\n      -   # 나중에 채움\n      - [0.001, 1.0]\n")
    n = curve_points(body(d, "l_curve"))
    check("load: 주석 붙은 곡선 점도 읽음 (점 2개, 빈 대시 줄은 건너뜀)", rc == 0 and n == 2, f"rc={rc} points={n} {out[-200:]}")

    rc, out = cfg(binary, d, "load", "l_next", "model: box.k\noutput: @OUT@\nloads:\n"
                  "  - part: 1\n    mode: pressure\n    value: 1.0\n    direction: [0, 0, 1]\n    select: direction\n"
                  "    curve:\n      - [0.0, 0.0]\n      - [0.001, 1.0]\n"
                  "  - part: 1\n    mode: force\n    value: 5.0\n    direction: [0, 0, -1]\n    select: direction\n")
    b = body(d, "l_next") or []
    nset = sum(1 for l in b if l.startswith("*LOAD_SEGMENT_SET"))
    check("load: 곡선 목록 뒤 다음 하중 항목을 곡선 점으로 삼키지 않음 (케이스 2)",
          rc == 0 and "Load cases: 2" in out and nset == 2 and "mode=pressure" in out and "mode=force" in out,
          f"rc={rc} LOAD_SEGMENT_SET={nset} {out[-300:]}")
    check("load: 첫 하중 곡선 점은 그대로 (점 2개)", curve_points(b) == 2, f"points={curve_points(b)}")

    rc, out = cfg(binary, d, "load", "l_compact", "model: box.k\noutput: @OUT@\nloads:\n"
                  "  - part: 1\n    mode: pressure\n    direction: [0, 0, 1]\n    curve:\n    - [0.0, 0.0]\n"
                  "    - [0.001, 1.0]\n    - [0.01, 1.0]\n    value: 2.5\n")
    check("load: 'curve:' 와 같은 들여쓰기 점·목록 뒤 하위 키 (예전과 동일)",
          rc == 0 and curve_points(body(d, "l_compact")) == 3 and "SF=2.5" in out, f"rc={rc} {out[-300:]}")

    print("[대시 줄 첫 키 주석 — 주석 없는 설정과 산출 동일]")
    load_mode = "model: box.k\noutput: @OUT@\nloads:\n  - mode: force%s\n    part: 1\n    value: 5.0\n" \
                "    direction: [0, 0, 1]\n    select: direction\n"
    ok, det = same_as_plain(binary, d, "load", "l_mode", load_mode % "", load_mode % "   # 힘")
    check("load: '- mode: force   # 주석' → force", ok, det)
    load_part = "model: box.k\noutput: @OUT@\nloads:\n  - part: PLATE%s\n    mode: pressure\n    value: 1.0\n" \
                "    direction: [0, 0, 1]\n"
    ok, det = same_as_plain(binary, d, "load", "l_part", load_part % "", load_part % "   # 판")
    check("load: '- part: PLATE   # 주석' → 파트 이름 찾음", ok, det)

    bc_part = "model: box.k\noutput: @OUT@\nboundaries:\n  - part: PLATE%s\n    dof: z\n    direction: [0, 0, -1]\n" \
              "    select: direction\n"
    ok, det = same_as_plain(binary, d, "boundary", "b_part", bc_part % "", bc_part % "   # 판")
    check("boundary: '- part: PLATE   # 주석' → 파트 이름 찾음", ok, det)
    bc_dof = "model: box.k\noutput: @OUT@\nboundaries:\n  - dof: xyz%s\n    part: 1\n    direction: [0, 0, -1]\n" \
             "    select: direction\n"
    ok, det = same_as_plain(binary, d, "boundary", "b_dof", bc_dof % "", bc_dof % "   # 병진만")
    check("boundary: '- dof: xyz   # 주석' → 병진 3자유도만 구속", ok, det)

    rbe_mode = "model: box.k\noutput: @OUT@\nrbe:\n  - mode: spider%s\n    part: 1\n    type: rbe3\n" \
               "    direction: [0, 0, 1]\n    select: direction\n"
    ok, det = same_as_plain(binary, d, "rbe", "r_mode", rbe_mode % "", rbe_mode % "   # 중심 1개")
    check("rbe: '- mode: spider   # 주석' → spider (face 아님)", ok, det)
    rbe_sel = "model: box.k\noutput: @OUT@\nrbe:\n  - select: direction%s\n    part: 1\n    type: rbe2\n" \
              "    mode: spider\n    direction: [0, 0, 1]\n"
    ok, det = same_as_plain(binary, d, "rbe", "r_sel", rbe_sel % "", rbe_sel % "   # 윗면만")
    check("rbe: '- select: direction   # 주석' → 방향 선택 (전체 면 아님)", ok, det)

    print("[strip 키워드 목록]")
    rc, out = cfg(binary, d, "strip", "s_cmt", "model: box.k\noutput: @OUT@\nkeywords:\n"
                  "  - \"*NODE\"   # 절점\n  - *ELEMENT_SOLID   # 요소\n")
    b = body(d, "s_cmt") or []
    check("strip: '- \"*NODE\"   # 주석' 목록 항목도 지움",
          rc == 0 and b and "*NODE" not in b and "*ELEMENT_SOLID" not in b and "*PART" in b,
          f"rc={rc} {out[-300:]}")
    rc, out = cfg(binary, d, "strip", "s_hash", "model: box.k\noutput: @OUT@\nkeywords:\n  - \"*NODE\"\n  - \"*PART # x\"\n")
    b = body(d, "s_hash") or []
    check("strip: 따옴표 안 '#' 은 값 (주석 없는 항목은 예전과 동일)",
          rc == 0 and b and "*NODE" not in b and "*PART" in b and "strip: *PART # x" in out, f"rc={rc} {out[-300:]}")

    print("[merge pids 블록 목록]")
    tl = os.path.join(REPO, "examples", "merge", "three_layer.k")
    merge = "model: " + tl + "\noutput: @OUT@\ndirection: z\nmethod: vrh\nmerge:\n  - pids:\n" \
            "      - 1%s\n      - 2%s\n      - 3\n    name: \"Homogenized_Stack\"\n"
    ok, det = same_as_plain(binary, d, "merge", "m_pids", merge % ("", ""), merge % ("   # 강", "   # 폴리머"))
    check("merge: '- 1   # 주석' pid 항목 → 주석 없는 설정과 동일", ok, det)

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
