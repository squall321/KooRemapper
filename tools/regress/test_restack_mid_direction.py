# restack direction 부호 표기·MID001 자리표시 층별 MID, offset 의 *MAT_..._TITLE 카드 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_restack_mid_direction.py <KooRemapper 바이너리>

배경
  - restack direction 은 'x'/'y'/'z' 만 비교해 '+x'·'-z' 같은 부호 표기를 조용히 무시하고 자동 탐지로
    떨어졌다. 20x10x2 박스에서 'x' 는 X-axis, '+x' 는 경고 없이 Z-axis 로 압출됐다.
  - 매뉴얼 §12 예제처럼 두 층이 같은 MID001 자리표시를 쓰면 자리표시 문자열만 보고 MID 하나로 묶어
    둘째 층 재질 카드(알루미늄)가 조용히 사라졌다. 카드 내용이 다르면 MID 를 따로 줘야 한다.
  - offset 은 *MAT_ELASTIC_TITLE 의 제목 줄을 데이터 줄로 읽어 restack 이 받는 카드를 거부했다
    ('Expected at least 4 fields (MID, RO, E, PR), found 1').
"""
import os
import subprocess
import sys
import tempfile

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
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def box_dir(binary, tag):
    d = tempfile.mkdtemp(prefix=f"rsmd_{tag}_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    return d


def parts(path):
    """[(pid, secid, mid)]"""
    lines = open(path).read().splitlines()
    out = []
    for i, ln in enumerate(lines):
        if ln.strip().upper() in ("*PART", "*PART_TITLE"):
            j = i + 2
            while j < len(lines) and lines[j].startswith("$"):
                j += 1
            f = [lines[j][k:k + 10].strip() for k in range(0, 30, 10)]
            out.append(tuple(int(x) if x else 0 for x in f))
    return out


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
    return {int(b[2][:10]): b[2][20:30].strip() for b in mat_blocks(path)
            if b[0].startswith("*MAT_ELASTIC")}


def layer_parts(path):
    return sorted(p for p in parts(path) if p[0] != 1)


RESTACK_HEAD = """base_model: box.k
output: stack
operations:
  - type: restack
    target_pid: 1
    direction: "{dir}"
    element_type: solid
    layers:
"""

ONE_LAYER = """      - thickness: 1.0
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
            MID001  7.85E-09    210000       0.3
"""


def axis_of(out):
    """'  Restack Part 1 (X-axis): ...' → 'X'. 못 찾으면 None"""
    for ln in out.splitlines():
        if "Restack Part" in ln and "-axis)" in ln:
            return ln.split("(")[1][0]
    return None


def direction_cases(binary):
    # 20x10x2 박스의 자동 탐지 축은 Z (두께 요소 2개). 'x' 는 X 로 강제되므로 부호 표기도 같아야 한다.
    for dirval, want in (("x", "X"), ("+x", "X"), ("-x", "X"),
                         ("y", "Y"), ("+y", "Y"), ("-y", "Y"),
                         ("z", "Z"), ("+z", "Z"), ("-z", "Z"),
                         ("auto", "Z")):
        d = box_dir(binary, "dir")
        open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_HEAD.format(dir=dirval) + ONE_LAYER)
        rc, out = run(binary, d, "restack", "rs.yaml")
        got = axis_of(out)
        check(f"restack direction '{dirval}' → {want}-axis", rc == 0 and got == want,
              f"rc={rc} axis={got} {out[-300:] if rc else ''}")


MANUAL_LAYERS = """      - thickness: 0.3
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
            MID001  7.85E-09    210000       0.3
      - thickness: 0.5
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
            MID001  2.50E-09     70000       0.33
"""

SAME_CARD_LAYERS = """      - thickness: 0.3
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
            MID001  7.85E-09    210000       0.3
      - thickness: 0.3
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
            MID001  7.85E-09    210000       0.3
"""


def placeholder_cases(binary):
    # 매뉴얼 §12 예제 그대로 — 같은 MID001 자리표시, 다른 물성 → MID 2·3 과 재질 카드 둘
    d = box_dir(binary, "manual")
    open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_HEAD.format(dir="z") + MANUAL_LAYERS)
    rc, out = run(binary, d, "restack", "rs.yaml")
    k = os.path.join(d, "stack.k")
    if rc != 0 or not os.path.exists(k):
        check("restack 매뉴얼 §12 예제 실행", False, out[-400:])
    else:
        e_of, lp = elastic_e(k), layer_parts(k)
        check("restack MID001 두 층·다른 물성 → 층마다 다른 MID",
              len(lp) == 2 and len({p[2] for p in lp}) == 2 and all(p[2] > 0 for p in lp), f"{lp}")
        check("restack MID001 두 층: 층마다 자기 재질(E)을 가리킴 (알루미늄 카드 유지)",
              [e_of.get(p[2]) for p in lp] == ["210000", "70000"], f"{lp} {e_of}")
        check("restack MID001 두 층: 별도 MID 안내 메시지",
              "reused with a different card -> separate MID" in out, out[-300:])

    # 자리표시·카드가 완전히 같으면 예전처럼 MID 하나를 공유하고 재질 카드도 한 번만 쓴다
    d = box_dir(binary, "share")
    open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_HEAD.format(dir="z") + SAME_CARD_LAYERS)
    rc, out = run(binary, d, "restack", "rs.yaml")
    k = os.path.join(d, "stack.k")
    if rc != 0 or not os.path.exists(k):
        check("restack MID001 같은 카드 두 층 실행", False, out[-400:])
    else:
        lp = layer_parts(k)
        mids = [int(b[2][:10]) for b in mat_blocks(k) if b[0].startswith("*MAT_ELASTIC")]
        check("restack MID001 같은 카드 두 층 → MID 공유, 재질 카드 1번",
              len(lp) == 2 and lp[0][2] == lp[1][2] > 0 and mids.count(lp[0][2]) == 1, f"{lp} {mids}")
        check("restack MID001 같은 카드 두 층: 별도 MID 메시지 없음",
              "reused with a different card" not in out, out[-300:])


TITLE_CARDS = {
    "*MAT_ELASTIC_TITLE": ("ALUMINUM_ELASTIC",
                           "         9  2.70E-09  7.00E+04      0.33"),
    "*MAT_PLASTIC_KINEMATIC_TITLE": ("STEEL_PK",
                                     "         9  7.85E-09  2.10E+05       0.3     300.0"),
}

OFFSET_YAML = """base_model: box.k
output: out
operations:
  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: 1
    offset_direction: +z
    connection_mode: tied
    new_pid: 10
    material_card: |
{card}"""


def title_card_cases(binary):
    for kw, (title, data) in TITLE_CARDS.items():
        card = "".join("      " + ln + "\n" for ln in (kw, title, data))
        # restack 과 offset 이 같은 카드에서 같은 답을 내야 한다
        d = box_dir(binary, "title")
        open(os.path.join(d, "rs.yaml"), "w").write(
            RESTACK_HEAD.format(dir="z") +
            "      - thickness: 1.0\n        material_card: |\n" +
            "".join("          " + ln + "\n" for ln in (kw, title, data)))
        rc_rs, out_rs = run(binary, d, "restack", "rs.yaml")
        check(f"restack {kw} 카드 성공", rc_rs == 0, out_rs[-300:])

        d = box_dir(binary, "titleoff")
        open(os.path.join(d, "off.yaml"), "w").write(OFFSET_YAML.format(card=card))
        rc, out = run(binary, d, "offset", "off.yaml")
        k = os.path.join(d, "out.k")
        check(f"offset {kw} 카드 성공 (제목 줄을 데이터로 읽지 않음)",
              rc == 0 and os.path.exists(k), out[-400:])
        check(f"offset {kw}: 필드 수 오류·경고 없음",
              not any(m in out for m in ("Expected at least 4 fields", "Expected at least 5 fields",
                                         "Expected at least 2 data lines", "No data line found")),
              out[-300:])
        if rc == 0 and os.path.exists(k):
            blocks = [b for b in mat_blocks(k) if b[0] == kw]
            mids = [int(b[2][:10]) for b in blocks]
            lp = [p for p in parts(k) if p[0] == 10]
            check(f"offset {kw}: 제목 보존 + PART 10 이 그 MID 를 가리킴",
                  len(blocks) == 1 and blocks[0][1] == title and len(lp) == 1 and lp[0][2] in mids,
                  f"{blocks} {lp}")


def main():
    binary = os.path.abspath(sys.argv[1])

    print("[restack direction 부호 표기]")
    direction_cases(binary)

    print("[restack MID001 자리표시 — 카드 내용별 MID]")
    placeholder_cases(binary)

    print("[*MAT_..._TITLE 카드 — restack/offset 동일 처리]")
    title_card_cases(binary)

    print()
    if FAILS:
        print(f"FAIL {len(FAILS)} 건")
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
