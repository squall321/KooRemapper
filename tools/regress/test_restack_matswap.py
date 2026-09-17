# restack 재질 라벨 MID(숫자·MAT01·MID001) 와 matswap 3필드 PART 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_restack_matswap.py <KooRemapper 바이너리>

배경
  - restack material_card 의 mid 칸이 MID<숫자> 자리표시가 아니면 PART mid=0 이 되고 두 번째 층 재질 카드가 빠졌다.
  - matswap 은 PART 카드에 5필드(PID SECID MID EOSID HGID)가 있어야만 파트를 찾아 generate box 모델에서 실패했다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAILS = []

BOX = """output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 10
ny: 5
nz: 2
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
"""


def check(name, cond, detail=""):
    print("  %-64s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def parts(path):
    """[(pid, secid, mid)]"""
    lines = open(path).read().splitlines()
    out = []
    for i, ln in enumerate(lines):
        if ln.upper().strip() == "*PART":
            j = i + 2
            while j < len(lines) and lines[j].startswith("$"):
                j += 1
            f = [lines[j][k:k + 10].strip() for k in range(0, 30, 10)]
            out.append(tuple(int(x) if x else 0 for x in f))
    return out


def mat_ids(path):
    lines = open(path).read().splitlines()
    ids = []
    for i, ln in enumerate(lines):
        if ln.upper().startswith("*MAT_"):
            j = i + 1
            if ln.upper().endswith("_TITLE"):
                j += 1
            while j < len(lines) and lines[j].startswith("$"):
                j += 1
            ids.append(int(lines[j][:10]))
    return ids


def restack_case(binary, label1, label2, title):
    d = tempfile.mkdtemp(prefix="rs_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    cfg = f"""base_model: box.k
output: stack
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
          {label1:>10s}  7.85E-09  2.10E+05       0.3
      - thickness: 0.2
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
          {label2:>10s}  1.20E-09  3.00E+03      0.45
"""
    open(os.path.join(d, "rs.yaml"), "w").write(cfg)
    rc, out = run(binary, d, "restack", "rs.yaml")
    k = os.path.join(d, "stack.k")
    if rc != 0 or not os.path.exists(k):
        check(f"restack {title} 실행", False, out[-400:])
        return
    ps = parts(k)
    mids = mat_ids(k)
    layer = [p for p in ps if p[0] != 1]
    check(f"restack {title}: 층 PART 2개, mid ≠ 0", len(layer) == 2 and all(p[2] > 0 for p in layer), str(ps))
    check(f"restack {title}: 층 mid 가 서로 다르고 재질 카드가 모두 있음",
          len({p[2] for p in layer}) == 2 and all(p[2] in mids for p in layer), f"parts={ps} mats={mids}")
    # 재질 카드 값 보존 (E 칸)
    txt = open(k).read()
    check(f"restack {title}: 두 재질 E 값 보존", "2.10E+05" in txt and "3.00E+03" in txt)


def main():
    binary = os.path.abspath(sys.argv[1])

    print("[restack 라벨 MID]")
    restack_case(binary, "MID001", "MID002", "MID001 자리표시(기존)")
    restack_case(binary, "11", "12", "숫자")
    restack_case(binary, "MAT01", "MAT02", "MAT01 라벨")

    d = tempfile.mkdtemp(prefix="rs_share_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    card = lambda lbl, e: f"""        material_card: |
          *MAT_ELASTIC
          {lbl:>10s}  7.85E-09  {e}       0.3
"""
    open(os.path.join(d, "rs.yaml"), "w").write("""base_model: box.k
output: stack
operations:
  - type: restack
    target_pid: 1
    direction: z
    element_type: solid
    layers:
      - thickness: 0.3
""" + card("7", "2.10E+05") + "      - thickness: 0.3\n" + card("7", "2.10E+05"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    ps = [p for p in parts(os.path.join(d, "stack.k")) if p[0] != 1] if rc == 0 else []
    mids = mat_ids(os.path.join(d, "stack.k")) if rc == 0 else []
    check("restack 같은 라벨 두 층 → mid 공유, 재질 카드 1번", len(ps) == 2 and ps[0][2] == ps[1][2] > 0
          and mids.count(ps[0][2]) == 1, f"{ps} {mids}")

    print("[matswap 3필드 PART]")
    d = tempfile.mkdtemp(prefix="ms_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    shutil.copy(os.path.join(ROOT, "examples", "matswap", "rubber.k"), d)
    open(os.path.join(d, "swap.yaml"), "w").write("model: box.k\noutput: box_rubber.k\nswaps:\n  - bundle: rubber.k\n    pid: 1\n")
    rc, out = run(binary, d, "matswap", "swap.yaml")
    ok = rc == 0 and os.path.exists(os.path.join(d, "box_rubber.k"))
    check("generate box 모델 matswap 성공", ok, out[-400:])
    if ok:
        ps = parts(os.path.join(d, "box_rubber.k"))
        mids = mat_ids(os.path.join(d, "box_rubber.k"))
        txt = open(os.path.join(d, "box_rubber.k")).read()
        check("PID 1 의 mid 가 새 재질(MAT_SIMPLIFIED_RUBBER) 을 가리킴",
              ps and ps[0][2] in mids and "*MAT_SIMPLIFIED_RUBBER" in txt, f"{ps} {mids}")
        check("기존 MAT_ELASTIC 1 은 고아라 제거", "*MAT_ELASTIC" not in txt)

    d = tempfile.mkdtemp(prefix="ms5_")
    for f in ("two_cubes.k", "rubber.k", "01_single_pid.yaml"):
        shutil.copy(os.path.join(ROOT, "examples", "matswap", f), d)
    rc, out = run(binary, d, "matswap", "01_single_pid.yaml")
    check("기존 5필드 PART 예제(two_cubes) 그대로 성공", rc == 0, out[-300:])

    print()
    if FAILS:
        print(f"FAIL {len(FAILS)} 건")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
