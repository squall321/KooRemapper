# assemble YAML 파서(인라인 주석·따옴표·indent points 목록 끝·generate pid)와 공용 주석 제거 규칙 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_assemble_yaml_parsing.py <KooRemapper 바이너리>

배경
  - assemble 의 load·contact·boundary·rbe 목록 값은 주석을 떼지 않았다. '- mode: force   # 주석' 은 pressure 로,
    'direction: [0, 0, 1]   # 주석' 은 방향 없음(rc=1)으로, 곡선 점 '- [0.0, 0.0]   # 주석' 은 버려졌고,
    '- action: create   # 주석' 은 모르는 action, '- type: automatic_surface_to_surface   # 주석' 은 틀린 키워드가 됐다.
    offset material_cards 의 '- |   # 주석' 은 카드 시작으로 보지 않았다.
  - 최상위 키·오퍼레이션 하위 키는 따옴표를 떼지 않아 'output: "qa"' 가 '"qa".k' 로 써졌다.
  - 공용 주석 제거(util/YamlComment.h)는 맨 앞 따옴표만 봐 'keywords: ["*NODE # x", "*ELEMENT_SOLID"]' 가 '"*NODE' 로 잘렸다.
  - indent 의 shape points 목록이 뒤따르는 '- type:' 오퍼레이션까지 점으로 삼켜 그 op 가 사라졌다.
  - generate 의 pid 가 target_pid 로 가서 무시돼 늘 PID 1 파트를 만들었다.
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []

BOX = "output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\npid: 1\nmid: 1\nsecid: 1\npart_title: PLATE\n"
HEAD = "base_model: box.k\noutput: out\noperations:\n"

LOAD = HEAD + """  - type: load
    loads:
      - mode: force
        part: 1
        value: 5.0
        direction: [1, 0, 0]
        select: direction
        angle: 30.0
      - part: 1
        mode: pressure
        value: 2.0
        direction: [0, 0, 1]
        select: direction
        angle: 30.0
        curve:
          - [0.0, 0.0]
          - [0.002, 1.0]
          - [0.01, 1.0]
"""

CONTACT = HEAD + """  - type: contact
    contacts:
      - action: create
        type: automatic_single_surface
        slave:
          pid: 1
        friction: 0.25
        title: SelfC
      - type: automatic_surface_to_surface
        action: create
        slave: 1
        master:
          pids: [1]
          as_segment: true
        title: S2S
"""

BOUNDARY = HEAD + """  - type: boundary
    boundaries:
      - dof: xyz
        part: 1
        direction: [0, 0, -1]
        select: direction
        angle: 45.0
      - select: direction
        part: 1
        dof: x
        direction: [-1, 0, 0]
        angle: 10.0
"""

RBE = HEAD + """  - type: rbe
    constraints:
      - type: rbe2
        part: 1
        select: direction
        direction: [1, 0, 0]
        angle: 45.0
        mode: spider
      - select: direction
        part: 1
        type: rbe3
        direction: [0, -1, 0]
"""

OFFSET = HEAD + """  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: 2
    offset_direction: +z
    connection_mode: tied
    new_pid: 10
    material_cards:
      - |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
               @MID@  7.85E-09  2.10E+05       0.3
      - |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
               @MID@  2.70E-09  7.00E+04      0.33
"""

INDENT_THEN_SQUEEZE = HEAD + """  - type: indent
    target_pid: 1
    plane: xy
    direction: -z
    depth: 0.5
    r1: 0.5
    r2: 1.0
    shape:
      type: polygon
      points:
        - [6, 3]
        - [12, 3]
        - [12, 7]
        - [6, 7]
  - type: squeeze
    target_pid: 1
    eps_x: -0.01
material:
  E: 210000.0
  nu: 0.3
"""

RESTACK = """base_model: box.k
output: out
operations:
  - type: restack
    target_pid: 1
    direction: z
    element_type: solid
    layers:
      - thickness: 1.0
        num_elements: 1
        title: "L1"
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
              MID001  7.85E-09  2.10E+05       0.3
      - thickness: 1.0
        title: L2
        material_card: |
          *MAT_ELASTIC
          $#     mid        ro         e        pr
              MID002  1.20E-09  3.00E+03      0.45
material:
  E: 210000.0
  nu: 0.3
"""


def check(name, cond, detail=""):
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def body(path):
    """'$' 주석 줄을 뺀 k 파일 본문 — 없으면 None"""
    if not os.path.exists(path):
        return None
    return [l for l in open(path, errors="replace").read().splitlines() if not l.startswith("$")]


def part_cards(path):
    """*PART 블록의 (제목, PID) 목록"""
    out, lines = [], body(path) or []
    for i, l in enumerate(lines):
        if l.strip().upper() == "*PART" and i + 2 < len(lines):
            fields = lines[i + 2].split()
            out.append((lines[i + 1].strip(), int(fields[0]) if fields and fields[0].lstrip("-").isdigit() else None))
    return out


class Work:
    def __init__(self, binary):
        self.binary = binary
        self.root = tempfile.mkdtemp(prefix="asm_yaml_")
        open(os.path.join(self.root, "box.yaml"), "w").write(BOX)
        run(binary, self.root, "generate", "box", "box.yaml")
        self.n = 0

    def assemble(self, text):
        """새 폴더에 box.k 와 YAML 을 두고 assemble — (rc, 출력, 폴더)"""
        self.n += 1
        d = os.path.join(self.root, "c%02d" % self.n)
        os.makedirs(d)
        shutil.copy(os.path.join(self.root, "box.k"), d)
        open(os.path.join(d, "asm.yaml"), "w").write(text)
        rc, out = run(self.binary, d, "assemble", "asm.yaml")
        return rc, out, d


def variant(text, old, new, count=1):
    assert text.count(old) >= count, old
    return text.replace(old, new, count)


def same_as_plain(w, label, plain, commented):
    rc0, out0, d0 = w.assemble(plain)
    rc1, out1, d1 = w.assemble(commented)
    b0, b1 = body(os.path.join(d0, "out.k")), body(os.path.join(d1, "out.k"))
    check(label, rc0 == 0 and rc1 == 0 and b0 is not None and b0 == b1,
          f"rc={rc0}/{rc1} {out1[-300:]}")
    return out1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    w = Work(binary)
    C = "   # 주석: 값 아님"

    print("[load·contact·boundary·rbe 목록 값의 인라인 주석 — 주석 없는 YAML 과 출력이 같아야]")
    same_as_plain(w, "load: '- mode: force   # 주석' (목록 첫 키)", LOAD,
                  variant(LOAD, "      - mode: force\n", "      - mode: force" + C + "\n"))
    same_as_plain(w, "load: 'direction: [0, 0, 1]   # 주석' (하위 키)", LOAD,
                  variant(LOAD, "direction: [0, 0, 1]\n", "direction: [0, 0, 1]" + C + "\n"))
    same_as_plain(w, "load: 곡선 점 '- [0.0, 0.0]   # 주석'", LOAD,
                  variant(LOAD, "- [0.0, 0.0]\n", "- [0.0, 0.0]" + C + "\n"))
    same_as_plain(w, "contact: '- action: create   # 주석' (목록 첫 키)", CONTACT,
                  variant(CONTACT, "      - action: create\n", "      - action: create" + C + "\n"))
    same_as_plain(w, "contact: '- type: automatic_surface_to_surface   # 주석'", CONTACT,
                  variant(CONTACT, "- type: automatic_surface_to_surface\n",
                          "- type: automatic_surface_to_surface" + C + "\n"))
    sub = CONTACT
    for k in ("type: automatic_single_surface", "title: S2S", "pids: [1]", "as_segment: true"):
        sub = variant(sub, k + "\n", k + C + "\n")
    same_as_plain(w, "contact: 하위 키 type·title·pids·as_segment 뒤 주석", CONTACT, sub)
    same_as_plain(w, "boundary: '- dof: xyz   # 주석' (목록 첫 키)", BOUNDARY,
                  variant(BOUNDARY, "- dof: xyz\n", "- dof: xyz" + C + "\n"))
    same_as_plain(w, "boundary: 'direction: [0, 0, -1]   # 주석' (하위 키)", BOUNDARY,
                  variant(BOUNDARY, "direction: [0, 0, -1]\n", "direction: [0, 0, -1]" + C + "\n"))
    same_as_plain(w, "rbe: '- select: direction   # 주석' (목록 첫 키)", RBE,
                  variant(RBE, "      - select: direction\n", "      - select: direction" + C + "\n"))
    sub = RBE
    for k in ("direction: [1, 0, 0]", "mode: spider", "type: rbe3", "        select: direction"):
        sub = variant(sub, k + "\n", k + C + "\n")
    same_as_plain(w, "rbe: 하위 키 direction·mode·type·select 뒤 주석", RBE, sub)
    same_as_plain(w, "offset: material_cards 항목 '- |   # 주석'", OFFSET,
                  variant(OFFSET, "      - |\n", "      - |" + C + "\n", count=2))

    print("[따옴표 값]")
    rc, out, d = w.assemble(variant(variant(LOAD, "base_model: box.k", 'base_model: "box.k"'), "output: out", 'output: "qa"'))
    check("최상위 base_model/output: \"…\" → qa.k (따옴표 없는 이름)",
          rc == 0 and os.path.exists(os.path.join(d, "qa.k")) and not os.path.exists(os.path.join(d, '"qa".k')),
          f"rc={rc} files={sorted(os.listdir(d))}")
    same_as_plain(w, "오퍼레이션 '- type: \"load\"' 를 load 로", LOAD, variant(LOAD, "- type: load", '- type: "load"'))
    gen = ("output: out\noperations:\n  - type: generate\n    lx: 10.0\n    ly: 5.0\n    lz: 2.0\n"
           "    nx: 5\n    ny: 2\n    nz: 1\n    part_title: \"GEN BOX\"\n")
    rc, out, d = w.assemble(gen)
    parts = part_cards(os.path.join(d, "out.k"))
    check("generate part_title: \"GEN BOX\" → *PART 제목에 따옴표 없음", rc == 0 and parts and parts[0][0] == "GEN BOX",
          f"rc={rc} parts={parts}")
    rc, out, d = w.assemble(RESTACK)
    titles = [t for t, _ in part_cards(os.path.join(d, "out.k"))]
    check("restack 층 title: \"L1\" → *PART 제목 L1", rc == 0 and "L1" in titles and '"L1"' not in titles,
          f"rc={rc} titles={titles}")

    print("[공용 주석 제거 규칙(util/YamlComment.h)]")
    s = os.path.join(w.root, "strip")
    os.makedirs(s)
    shutil.copy(os.path.join(w.root, "box.k"), s)
    open(os.path.join(s, "st.yaml"), "w").write(
        "model: box.k\noutput: st.k\nkeywords: [\"*NODE # not-a-comment\", \"*ELEMENT_SOLID\"]   # 주석\n")
    rc, out = run(binary, s, "strip", "st.yaml")
    b = body(os.path.join(s, "st.k")) or []
    check("strip: 인라인 목록의 따옴표 안 '#' 뒤 항목(*ELEMENT_SOLID)도 지움",
          rc == 0 and b and not any(l.strip().upper().startswith("*ELEMENT_SOLID") for l in b) and "*NODE" in b,
          f"rc={rc} {out[-300:]}")
    rc, out, d = w.assemble(HEAD + "  - type: strip\n    keywords: [\"*PART # x\", \"*SECTION_SOLID\"]   # 주석\n")
    b = body(os.path.join(d, "out.k")) or []
    check("assemble strip op: 인라인 목록의 따옴표 안 '#' 뒤 항목도 지움",
          rc == 0 and b and "*SECTION_SOLID" not in b and "*PART" in b, f"rc={rc} {out[-300:]}")
    for outval, fname in (('"qa # not-a-comment"   # 주석', "qa # not-a-comment.k"),
                          ("q#1", "q#1.k"),
                          ("qb   # 주석", "qb.k"),
                          ("'qc # x'", "qc # x.k")):
        rc, out, d = w.assemble(variant(LOAD, "output: out", "output: " + outval))
        check(f"assemble output: {outval} → '{fname}'",
              rc == 0 and os.path.exists(os.path.join(d, fname)), f"rc={rc} files={sorted(os.listdir(d))}")
    r = os.path.join(w.root, "restack")
    os.makedirs(r)
    shutil.copy(os.path.join(w.root, "box.k"), r)
    open(os.path.join(r, "rs.yaml"), "w").write(
        "model: box.k\noutput: \"rs # x\"   # 주석\ntarget_pid: 1   # 대상\ndirection: z\nlayers:\n"
        "  - thickness: 1.0   # 아래층\n    material_card: |\n      *MAT_ELASTIC\n"
        "          MID001  7.85E-09  2.10E+05       0.3\n"
        "  - thickness: 1.0\n    material_card: |   # 위층\n      *MAT_ELASTIC\n"
        "          MID002  1.20E-09  3.00E+03      0.45\n")
    rc, out = run(binary, r, "restack", "rs.yaml")
    mids = []
    b = body(os.path.join(r, "rs # x.k")) or []
    for i, l in enumerate(b):
        if l.strip().upper() == "*PART" and i + 2 < len(b):
            mids.append(b[i + 2].split()[2] if len(b[i + 2].split()) > 2 else "")
    check("restack 단독: 재질 라벨 MID001/MID002 → 층마다 0 아닌 MID, 'rs # x.k'",
          rc == 0 and len(mids) >= 2 and all(m not in ("", "0") for m in mids) and len(set(mids)) == len(mids),
          f"rc={rc} mids={mids} {out[-300:]}")

    print("[indent points 목록 끝·generate pid]")
    rc, out, d = w.assemble(INDENT_THEN_SQUEEZE)
    check("indent 뒤 '- type: squeeze' 가 points 에 먹히지 않음 (2 operation)",
          rc == 0 and "Config: 2 operation(s)" in out, f"rc={rc} {out[-300:]}")
    rc, out, d = w.assemble(gen.replace("    part_title", "    pid: 7\n    part_title"))
    parts = part_cards(os.path.join(d, "out.k"))
    check("generate pid: 7 → *PART PID 7", rc == 0 and parts and parts[0][1] == 7, f"rc={rc} parts={parts}")
    rc, out, d = w.assemble(gen.replace("    part_title", "    pid: 7\n    part_title") +
                            "  - type: squeeze\n    target_pid: 7\n    eps_x: -0.01\n")
    check("generate pid: 7 뒤 squeeze target_pid: 7 가 파트를 찾음", rc == 0, f"rc={rc} {out[-300:]}")

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
