# 재질 카드 블록(YAML |) 읽기·assemble 출력 이름 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_card_blocks.py <KooRemapper 바이너리>

배경
  - assemble: 마지막 층 카드 뒤 빈 줄이 카드 내용에 남아, 같은 라벨·같은 내용 카드가 "다른 카드"로 판정돼
    MID 가 따로 발급됐다(examples/assemble_display/gen_al_box.yaml 의 PSA7).
  - 단독 restack: 카드 안에 ':' 가 든 줄(예: 제목 'Steel: SUS304')에서 블록이 끊겨 층 PART mid 가 0 이 되고
    재질 카드가 제목 없이 빠졌다.
  - 단독 restack·offset: 블록 들여쓰기를 '키 + 2칸'으로 가정해, 더 깊게 들여쓴 카드는 앞 공백이 남아
    10열 칸이 밀렸다(assemble 은 첫 내용 줄 들여쓰기를 쓴다).
  - assemble: output 에 .k 를 붙이면 name.k.k 가 생겼다(다른 명령은 .k 를 떼어 냄). 단독 squeeze 접두어도 같았다.
  - prestress: 출력 이름을 x.k 로 주면 dynain 과 변형 메시 사본이 같은 x.k 에 써져 dynain 이 사라지고
    x.k 가 자기 자신을 *INCLUDE 했다.
"""
import os
import re
import subprocess
import sys
import tempfile

FAILS = []

BOX = """output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 4
ny: 2
nz: 1
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


def workdir(binary, tag):
    d = tempfile.mkdtemp(prefix=f"cards_{tag}_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    return d


def parts_and_mats(path):
    """{pid: mid}, {mid: (keyword, title, data_line)}"""
    L = open(path, errors="replace").read().splitlines()
    parts, mats = {}, {}
    i = 0
    while i < len(L):
        u = L[i].strip().upper()
        if u in ("*PART", "*PART_TITLE"):
            j = i + 2
            while j < len(L) and L[j].startswith("$"):
                j += 1
            f = [L[j][k:k + 10].strip() for k in range(0, 30, 10)]
            parts[int(f[0])] = int(f[2] or 0)
        elif u.startswith("*MAT_"):
            j = i + 1
            title = ""
            if u.endswith("_TITLE"):
                title = L[j]
                j += 1
            while j < len(L) and L[j].startswith("$"):
                j += 1
            try:
                mats[int(L[j][:10])] = (u, title, L[j])
            except ValueError:
                mats.setdefault(-1, (u, title, L[j] if j < len(L) else ""))
        i += 1
    return parts, mats


def test_assemble_trailing_blank(binary):
    print("[assemble restack] 마지막 층 카드 뒤 빈 줄")
    d = workdir(binary, "blank")
    card = """        material_card: |
          *MAT_ELASTIC_TITLE
          PSA
                  14 1.100E-09 8.000E+02       0.3
"""
    y = ("base_model: box.k\noutput: out\noperations:\n  - type: restack\n    target_pid: 1\n"
         "    direction: z\n    element_type: solid\n    layers:\n"
         "      # A\n      - thickness: 1.0\n" + card +
         "      # B\n      - thickness: 1.0\n" + card +
         "\n  # 다음 op\n  - type: control\n    endtime: 0.001\n")
    open(os.path.join(d, "a.yaml"), "w").write(y)
    rc, out = run(binary, d, "assemble", "a.yaml")
    check("실행 rc=0", rc == 0, out[-300:])
    if rc != 0:
        return
    parts, mats = parts_and_mats(os.path.join(d, "out.k"))
    layer_mids = [parts.get(p) for p in (2, 3)]
    check("같은 라벨·같은 내용 두 층이 MID 공유", layer_mids[0] == layer_mids[1] and layer_mids[0], str(layer_mids))
    check("'different card' 안내 없음", "different card" not in out, out[-300:])
    txt = open(os.path.join(d, "out.k")).read()
    check("카드 데이터 줄 뒤 빈 줄 없음", not re.search(r"8\.000E\+02 +0\.3\n\n", txt))


def test_standalone_restack_colon(binary):
    print("[restack 단독] 카드 제목 줄의 ':'")
    d = workdir(binary, "colon")
    y = """model: box.k
output: out
target_pid: 1
direction: z
element_type: solid
layers:
  - thickness: 1.0
    material_card: |
      *MAT_ELASTIC_TITLE
      Steel: SUS304
      $#     mid        ro         e        pr
              14  7.85E-09    210000       0.3
  - thickness: 1.0
    material_card: |
      *MAT_ELASTIC_TITLE
      - dash title
      $#     mid        ro         e        pr
              15  2.70E-09     70000      0.33
"""
    open(os.path.join(d, "r.yaml"), "w").write(y)
    rc, out = run(binary, d, "restack", "r.yaml")
    check("실행 rc=0", rc == 0, out[-300:])
    if rc != 0:
        return
    parts, mats = parts_and_mats(os.path.join(d, "out.k"))
    for pid, title in ((2, "Steel: SUS304"), (3, "- dash title")):
        mid = parts.get(pid, 0)
        check(f"층 PART {pid} mid != 0", mid != 0, str(parts))
        check(f"층 PART {pid} 재질 카드 제목 '{title}' 유지", mid in mats and mats[mid][1] == title, str(mats.get(mid)))


def test_deep_indent(binary):
    print("[단독 restack·offset] 키보다 4칸 더 들여쓴 카드")
    d = workdir(binary, "indent")
    r = """model: box.k
output: rs
target_pid: 1
direction: z
element_type: solid
layers:
  - thickness: 1.0
    material_card: |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
                14  7.85E-09    210000       0.3
  - thickness: 1.0
    material_card: |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
                15  2.70E-09     70000      0.33
"""
    open(os.path.join(d, "r.yaml"), "w").write(r)
    rc, out = run(binary, d, "restack", "r.yaml")
    check("restack 실행 rc=0", rc == 0, out[-300:])
    if rc == 0:
        parts, mats = parts_and_mats(os.path.join(d, "rs.k"))
        for pid in (2, 3):
            mid = parts.get(pid, 0)
            check(f"restack 층 PART {pid} MID 가 재질 카드 1~10열과 일치", mid != 0 and mid in mats, f"{parts} {list(mats)}")
    for tag, body in (
        ("material_card", """material_card: |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
                10       2.0     12000      0.25
"""),
        ("material_cards", """material_cards:
  - |
        *MAT_ELASTIC
        $#     mid        ro         e        pr
                10       2.0     12000      0.25
"""),
    ):
        o = f"""model: box.k
output: of_{tag}
source_pid: 1
element_type: solid
thickness: 1.0
num_layers: 1
offset_direction: +z
connection_mode: tied
new_pid: 10
{body}"""
        open(os.path.join(d, f"o_{tag}.yaml"), "w").write(o)
        rc, out = run(binary, d, "offset", f"o_{tag}.yaml")
        check(f"offset {tag} 실행 rc=0", rc == 0, out[-300:])
        if rc == 0:
            parts, mats = parts_and_mats(os.path.join(d, f"of_{tag}.k"))
            mid = parts.get(10, 0)
            check(f"offset {tag} PART 10 MID 가 재질 카드 1~10열과 일치", mid != 0 and mid in mats, f"{parts} {list(mats)}")


def test_assemble_output_ext(binary):
    print("[assemble] output 에 .k")
    d = workdir(binary, "ext")
    open(os.path.join(d, "e.yaml"), "w").write(
        "base_model: box.k\noutput: named.k\noperations:\n  - type: control\n    endtime: 0.001\n")
    rc, out = run(binary, d, "assemble", "e.yaml")
    check("실행 rc=0", rc == 0, out[-300:])
    check("named.k 생성", os.path.exists(os.path.join(d, "named.k")))
    check("named.k.k 없음", not os.path.exists(os.path.join(d, "named.k.k")))


def test_positional_output_ext(binary):
    print("[squeeze·prestress] 위치 인자 출력에 .k")
    d = workdir(binary, "posext")
    open(os.path.join(d, "sq.yaml"), "w").write("parts:\n  - pid: 1\n    eps_x: -0.01\n    eps_y: 0.0\n    eps_z: 0.0\n"
                                                "material:\n  E: 210000.0\n  nu: 0.3\n")
    rc, out = run(binary, d, "squeeze", "box.k", "sq.yaml", "sq_out.k")
    check("squeeze rc=0", rc == 0, out[-300:])
    check("squeeze: sq_out.k·sq_out.dynain 생성, .k.k 없음",
          os.path.exists(os.path.join(d, "sq_out.k")) and os.path.exists(os.path.join(d, "sq_out.dynain"))
          and not os.path.exists(os.path.join(d, "sq_out.k.k")), str(sorted(os.listdir(d))))
    # prestress: 변형 메시 = x 방향 1% 늘린 박스
    open(os.path.join(d, "def.yaml"), "w").write(BOX.replace("output: box.k", "output: def.k").replace("lx: 20.0", "lx: 20.2"))
    run(binary, d, "generate", "box", "def.yaml")
    rc, out = run(binary, d, "prestress", "--E", "210000", "--nu", "0.3", "box.k", "def.k", "pre.k")
    check("prestress rc=0", rc == 0, out[-300:])
    k = os.path.join(d, "pre.k")
    dyn = os.path.join(d, "pre.dynain")
    ok = os.path.exists(k) and os.path.exists(dyn)
    check("prestress: pre.k(메시) + pre.dynain(응력) 분리 생성", ok, str(sorted(os.listdir(d))))
    if ok:
        txt = open(k).read()
        check("pre.k 가 pre.dynain 을 *INCLUDE (자기 자신 아님)", re.search(r"\*INCLUDE\s*\npre\.dynain", txt) is not None
              and "*NODE" in txt, txt[-120:])
        check("pre.dynain 에 *INITIAL_STRESS_SOLID", "*INITIAL_STRESS_SOLID" in open(dyn).read())


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    test_assemble_trailing_blank(binary)
    test_standalone_restack_colon(binary)
    test_deep_indent(binary)
    test_assemble_output_ext(binary)
    test_positional_output_ext(binary)
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
