# restack 재질 라벨 MID(숫자·MAT01·MID001·_TITLE·칸 불일치·EROSION) 와 matswap 3필드 PART 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_restack_matswap.py <KooRemapper 바이너리>

배경
  - restack material_card 의 mid 칸이 MID<숫자> 자리표시가 아니면 PART mid=0 이 되고 두 번째 층 재질 카드가 빠졌다.
  - 라벨 처리 1차 수정은 *MAT_…_TITLE 의 제목 줄을 MID 칸으로 착각했고(디스플레이 예제 PART 8/12 가 없는 MID 참조),
    칸이 안 맞는 카드에서 다음 값 첫 글자를 덮었고(밀도 5.5→2.5), 같은 라벨·다른 물성 층의 재질을 버렸고,
    *MAT_ADD_EROSION 의 MID 를 그대로 둬 참조가 끊겼다.
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


def run_restack(binary, tag, layers):
    """layers 는 'layers:' 아래 YAML 본문(들여쓰기 6칸). 결과 K 파일 경로, 실패하면 None."""
    d = tempfile.mkdtemp(prefix=f"rs_{tag}_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    open(os.path.join(d, "rs.yaml"), "w").write(
        "base_model: box.k\noutput: stack\noperations:\n  - type: restack\n"
        "    target_pid: 1\n    direction: z\n    element_type: solid\n    layers:\n" + layers)
    rc, out = run(binary, d, "restack", "rs.yaml")
    k = os.path.join(d, "stack.k")
    if rc != 0 or not os.path.exists(k):
        check(f"restack {tag} 실행", False, out[-400:])
        return None
    return k


def mat_blocks(path):
    """*MAT 블록마다 (키워드, 제목, 첫 데이터 줄). _TITLE 이면 제목 줄을 건너뛴다."""
    lines = open(path).read().splitlines()
    out = []
    for i, ln in enumerate(lines):
        if not ln.upper().startswith("*MAT"):
            continue
        j, title = i + 1, None
        while j < len(lines) and lines[j].startswith("$"):
            j += 1
        if ln.strip().upper().endswith("_TITLE"):
            title, j = lines[j].strip(), j + 1
            while j < len(lines) and lines[j].startswith("$"):
                j += 1
        out.append((ln.strip().upper(), title, lines[j]))
    return out


def elastic_e(path):
    """*MAT_ELASTIC(_TITLE) 의 mid → E 칸"""
    return {int(b[2][:10]): b[2][20:30].strip() for b in mat_blocks(path) if b[0].startswith("*MAT_ELASTIC")}


def layer_parts(path):
    return sorted(p for p in parts(path) if p[0] != 1)


def restack_edge_cases(binary):
    card10 = lambda kw, mid, rho, e, pr, title=None: (
        "      - thickness: 0.3\n        material_card: |\n"
        f"          {kw}\n" + (f"          {title}\n" if title else "") +
        f"          {mid:>10s}{rho:>10s}{e:>10s}{pr:>10s}\n")

    # _TITLE 카드 + 리터럴 mid(3·2·4)가 새로 매길 MID(2·3·4)와 겹침 — gen_al_box·b7 디스플레이 예제 유형.
    # 제목 줄을 MID 칸으로 착각하면 제목이 깨지고 데이터 mid 는 리터럴로 남아, 오류 없이 남의 재질을 가리킨다.
    k = run_restack(binary, "title",
                    card10("*MAT_ELASTIC_TITLE", "3", "7.85E-09", "2.10E+05", "0.3", "LAYER_A") +
                    card10("*MAT_ELASTIC_TITLE", "2", "2.70E-09", "7.00E+04", "0.33", "LAYER_B") +
                    card10("*MAT_ELASTIC_TITLE", "4", "1.20E-09", "3.00E+03", "0.45", "LAYER_C"))
    if k:
        titles = [b[1] for b in mat_blocks(k) if b[1]]
        e_of, lp = elastic_e(k), layer_parts(k)
        check("restack _TITLE 카드: 재질 제목 보존", all(t in titles for t in ("LAYER_A", "LAYER_B", "LAYER_C")),
              str(titles))
        check("restack _TITLE 카드: 층 PART 가 모두 정의된 MID 참조",
              len(lp) == 3 and all(p[2] in e_of for p in lp), f"{lp} {e_of}")
        check("restack _TITLE 카드: 층마다 자기 재질(E)을 가리킴 (리터럴 mid 와 새 MID 교차 없음)",
              [e_of.get(p[2]) for p in lp] == ["2.10E+05", "7.00E+04", "3.00E+03"],
              str([e_of.get(p[2]) for p in lp]))

    # 칸이 안 맞는 카드(help 예제식 '     10  5.5 1000 0.35') — 10열로 덮으면 밀도 5.5 가 2.5 로 바뀐다.
    k = run_restack(binary, "helpstyle", "      - thickness: 0.5\n        material_card: |\n"
                    "          *MAT_ELASTIC\n          $#  mid   ro    e   pr\n"
                    "               10  5.5 1000 0.35\n")
    if k:
        data = [b[2] for b in mat_blocks(k) if b[0] == "*MAT_ELASTIC"][-1]
        lp = layer_parts(k)
        check("restack 칸 안 맞는 카드: 밀도·E·PR 값 보존", data.split()[1:] == ["5.5", "1000", "0.35"], repr(data))
        check("restack 칸 안 맞는 카드: 첫 토큰이 층 PART mid",
              len(lp) == 1 and data.split()[0] == str(lp[0][2]), f"{lp} {data!r}")

    # 같은 라벨, 다른 물성 — 한 MID 로 묶으면 두 번째 층 재질이 조용히 사라진다.
    k = run_restack(binary, "samelabel",
                    card10("*MAT_ELASTIC", "10", "7.85E-09", "2.10E+05", "0.3") +
                    card10("*MAT_ELASTIC", "10", "2.70E-09", "7.00E+04", "0.33"))
    if k:
        e_of, lp = elastic_e(k), layer_parts(k)
        check("restack 같은 라벨·다른 물성 두 층 → MID 따로, 재질 둘 다 유지",
              [e_of.get(p[2]) for p in lp] == ["2.10E+05", "7.00E+04"], f"{lp} {e_of}")

    # 같은 MID 를 가리키는 *MAT_ADD_EROSION 도 함께 치환돼야 참조가 끊기지 않는다.
    k = run_restack(binary, "erosion", "      - thickness: 0.5\n        material_card: |\n"
                    "          *MAT_ELASTIC\n                  10  7.85E-09  2.10E+05       0.3\n"
                    "          *MAT_ADD_EROSION\n                  10       0.0       0.0\n")
    if k:
        lp = layer_parts(k)
        ero = [int(b[2][:10]) for b in mat_blocks(k) if b[0].startswith("*MAT_ADD_EROSION")]
        check("restack *MAT_ADD_EROSION 도 같은 새 MID 로 치환", len(lp) == 1 and ero == [lp[0][2]],
              f"{lp} erosion={ero}")


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

    print("[restack 라벨 MID 경계 — _TITLE·칸 불일치·같은 라벨 다른 물성·EROSION]")
    restack_edge_cases(binary)

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
