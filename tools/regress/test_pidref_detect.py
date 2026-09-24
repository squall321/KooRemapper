# restack·merge 가 비운 PID·지운 요소·지운 노드 참조 탐지(3축)와 곁가지 결함 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_pidref_detect.py <KooRemapper 바이너리>

배경
  - restack/merge 는 원 *PART 카드를 그대로 두고 그 파트의 요소만 지운다. 그래서 빈 파트를 가리키는
    *SET_PART·*CONTACT, 지워진 요소를 가리키는 *SET_SOLID·*INITIAL_STRESS_SOLID, restack 이 지운
    중간면 노드를 가리키는 *SET_NODE·*BOUNDARY_SPC_NODE·*SET_SEGMENT 가 바이트 그대로 남았다.
    그런 덱이 rc=0 으로 나가면 자동화(종료 코드만 본다)는 성공으로 읽고 체인이 솔버까지 간다.
  - *CONTACT 카드 1 을 공백으로 쪼개면 고정폭 빈 칸이 사라져 SSTYP 를 MSID 자리로 읽었다.
  - maxSetId_ 초기화 스캔이 *SET_..._TITLE 의 제목 줄을 못 넘겨 새 세트가 기존 세트와 같은 번호로 났다.
  - 강체 파트를 restack 하면 경고 없이 변형체 여러 층이 됐다.
  - 새 층이 원 파트의 ELFORM·HGID·TMID 를 물려받지 못했다.

임시 산출물은 /tmp 가 아니라 저장소 build/scratch/regress 아래에 만든다.
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
nx: 2
ny: 2
nz: 2
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
"""

RESTACK_YAML = """model: {model}
output: {out}
target_pid: 1
direction: z
layers:
  - title: L1
    thickness: 1.0
    num_elements: 1
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
        MID001  7.85E-09    210000       0.3
  - title: L2
    thickness: 1.0
    num_elements: 1
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
        MID002  2.50E-09     70000       0.33
"""


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s %s" % (name, detail))


def scratch_root(binary):
    root = os.path.join(os.path.dirname(os.path.abspath(binary)), "..", "..", "scratch", "regress")
    root = os.path.normpath(root)
    os.makedirs(root, exist_ok=True)
    return root


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def box_dir(binary, tag):
    d = tempfile.mkdtemp(prefix="pidref_%s_" % tag, dir=scratch_root(binary))
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    return d


def read(path):
    return open(path, encoding="utf-8", errors="replace").read()


def with_cards(d, name, cards):
    """box.k 의 *END 앞에 카드를 끼운 덱을 만든다."""
    txt = read(os.path.join(d, "box.k")).replace("*END", cards + "*END", 1)
    open(os.path.join(d, name), "w").write(txt)
    return name


# box.k(2x2x2): 중간면 노드는 10..18, 요소는 1..8.
REF_CARDS = """*SET_PART_LIST_TITLE
plate parts
       500
         1
*CONTACT_TIED_SURFACE_TO_SURFACE
$#    ssid      msid     sstyp     mstyp
         2         1                   3
*SET_NODE_LIST_TITLE
mid plane nodes
       700
        10        11        14
*BOUNDARY_SPC_NODE
        13         0         1         1         1
*SET_SEGMENT
       701       0.0       0.0       0.0       0.0
        10        11        14        13
*CONSTRAINED_NODAL_RIGID_BODY
        99         0       700
*SET_SOLID_LIST
       702
         1         2
*DATABASE_HISTORY_SOLID
         3         4
*DAMPING_PART_STIFFNESS
         1       0.1
*MAT_ADD_THERMAL_EXPANSION
         1         0       1.0
       1.0
*RIGIDWALL_PLANAR
         1         0
*LOAD_SEGMENT_SET
         1         1       1.0
"""


def axis_lines(out, axis):
    return [ln for ln in out.splitlines() if ("[%s] line " % axis) in ln]


def three_axes(binary):
    print("[A 3축 탐지 + rc 정책 + 덱 주석 블록]")
    d = box_dir(binary, "axes")
    with_cards(d, "ref.k", REF_CARDS)
    open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_YAML.format(model="ref.k", out="out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")

    check("rc=1 (pid_refs strict 기본)", rc == 1, out[-300:])
    deck = os.path.join(d, "out.k")
    check("덱은 그래도 쓴다", os.path.exists(deck))

    check("PID 축: *SET_PART_LIST_TITLE 을 찾는다",
          any("*SET_PART_LIST_TITLE" in ln for ln in axis_lines(out, "PID")), out[-900:])
    check("EID 축: *SET_SOLID_LIST 를 찾는다",
          any("*SET_SOLID_LIST" in ln for ln in axis_lines(out, "EID")), out[-900:])
    check("EID 축: *DATABASE_HISTORY_SOLID 를 찾는다",
          any("*DATABASE_HISTORY_SOLID" in ln for ln in axis_lines(out, "EID")), out[-900:])
    check("노드 축: *SET_NODE_LIST_TITLE 을 찾는다",
          any("*SET_NODE_LIST_TITLE" in ln for ln in axis_lines(out, "NODE")), out[-900:])
    check("노드 축: *BOUNDARY_SPC_NODE 를 찾는다",
          any("*BOUNDARY_SPC_NODE" in ln for ln in axis_lines(out, "NODE")), out[-900:])
    check("노드 축: *SET_SEGMENT 를 찾는다",
          any("*SET_SEGMENT" in ln for ln in axis_lines(out, "NODE")), out[-900:])
    check("노드 축: 지워진 노드가 든 세트를 쓰는 *CONSTRAINED_NODAL_RIGID_BODY 를 찾는다",
          any("*CONSTRAINED_NODAL_RIGID_BODY" in ln for ln in axis_lines(out, "NODE")), out[-900:])

    check("등급 manual: *DAMPING_PART_STIFFNESS 에 `_SET` 변형을 권한다",
          "*DAMPING_PART_STIFFNESS" in out and "_SET` 변형" in out, out[-900:])
    check("등급 manual: *MAT_ADD_THERMAL_EXPANSION 은 카드 복제를 권한다",
          "*MAT_ADD_THERMAL_EXPANSION" in out and "복제" in out, out[-900:])
    check("등급 unknown: *RIGIDWALL_PLANAR 는 칸 자리 미확정으로 알린다",
          "*RIGIDWALL_PLANAR" in out and "(unknown)" in out, out[-900:])
    check("등급 maybe: 화이트리스트 밖 줄은 '모르는 자리' 로 접는다",
          "(maybe)" in out and "모르는 자리" in out, out[-900:])

    body = read(deck)
    check("덱 머리에 $ KOOREMAPPER-PIDREF 블록을 박는다", "$ KOOREMAPPER-PIDREF" in body)
    check("블록은 *KEYWORD 바로 뒤에 온다",
          body.splitlines()[0].strip() == "*KEYWORD" and
          body.splitlines()[1].startswith("$ KOOREMAPPER-PIDREF"), body[:200])
    check("블록이 끝을 표시한다", "$ KOOREMAPPER-PIDREF-END" in body)
    check("블록에 줄 번호가 있다", "] line " in body)
    check("블록에 원문이 있다", "$ KOOREMAPPER-PIDREF   |" in body)
    # 죽은 PID 는 *SET_PART 안의 1 뿐 — 원 *PART·*ELEMENT 카드가 '모르는 자리' 로 쏟아지면 안 된다
    check("*ELEMENT_SOLID·*PART 는 '모르는 자리' 로 세지 않는다",
          "*ELEMENT_SOLID (maybe)" not in out and "*PART (maybe)" not in out, out[-900:])


def blank_field_contact(binary):
    print("[B *CONTACT 카드 1 의 고정폭 빈 칸]")
    # SSTYP 칸이 비어 있고 MSTYP=3, MSID=1(죽은 PID). 공백 분해로 읽으면 STYP 가 한 칸 밀려 못 찾는다.
    d = box_dir(binary, "blank")
    with_cards(d, "c.k",
               "*CONTACT_TIED_SURFACE_TO_SURFACE\n"
               "$#    ssid      msid     sstyp     mstyp\n"
               "         2         1                   3\n")
    open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_YAML.format(model="c.k", out="c_out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    check("빈 칸이 있어도 master part 로 찾는다",
          "*CONTACT_TIED_SURFACE_TO_SURFACE" in out and "master part" in out, out[-600:])
    check("rc=1", rc == 1, out[-300:])

    # 콤마 자유 형식도 같게 읽는다
    d2 = box_dir(binary, "comma")
    with_cards(d2, "c.k", "*CONTACT_TIED_SURFACE_TO_SURFACE\n2,1,,3\n")
    open(os.path.join(d2, "rs.yaml"), "w").write(RESTACK_YAML.format(model="c.k", out="c_out.k"))
    rc2, out2 = run(binary, d2, "restack", "rs.yaml")
    check("콤마 자유 형식의 빈 칸도 같게 읽는다", "master part" in out2, out2[-600:])


def title_set_id(binary):
    print("[C *SET_..._TITLE 제목 줄과 maxSetId_]")
    # 제목 줄을 못 넘기면 SID 500 을 못 봐 새로 만드는 *SET_SEGMENT 가 1 번부터 난다.
    d = box_dir(binary, "setid")
    with_cards(d, "s.k",
               "*SET_SEGMENT_TITLE\ntop face\n"
               "       500       0.0       0.0       0.0       0.0\n"
               "        19        20        23        22\n")
    # 이 덱의 세트는 살아 있는 윗면 노드만 가리킨다 — 발견 0 건이라 rc 도 0 이다.
    yaml = ("model: s.k\noutput: s_out.k\ntarget_pid: 1\ndirection: z\nlayers:\n"
            "  - title: L1\n    thickness: 1.0\n    element_type: solid\n    material_card: |\n"
            "      *MAT_ELASTIC\n      $#     mid        ro         e        pr\n"
            "        MID001  7.85E-09    210000       0.3\n"
            "  - title: L2\n    thickness: 0.5\n    element_type: shell\n    material_card: |\n"
            "      *MAT_ELASTIC\n      $#     mid        ro         e        pr\n"
            "        MID002  7.85E-09    210000       0.3\n"
            "  - title: L3\n    thickness: 0.5\n    element_type: solid\n    material_card: |\n"
            "      *MAT_ELASTIC\n      $#     mid        ro         e        pr\n"
            "        MID003  7.85E-09    210000       0.3\n")
    open(os.path.join(d, "s.yaml"), "w").write(yaml)
    rc, out = run(binary, d, "restack", "s.yaml")
    check("rc=0 (살아 있는 노드만 가리키는 세트라 발견이 없다)", rc == 0, out[-400:])
    deck = os.path.join(d, "s_out.k")
    if not os.path.exists(deck):
        check("restack 실행", False, out[-500:])
        return
    lines = read(deck).splitlines()
    sids = []
    for i, ln in enumerate(lines):
        if ln.strip().upper() == "*SET_SEGMENT":
            j = i + 1
            while j < len(lines) and lines[j].startswith("$"):
                j += 1
            try:
                sids.append(int(lines[j][:10]))
            except ValueError:
                pass
    check("새 *SET_SEGMENT 번호가 기존 세트(500) 위다", sids and min(sids) > 500, str(sids))
    check("새 세트 번호가 서로 겹치지 않는다", len(sids) == len(set(sids)), str(sids))


def clean_deck(binary):
    print("[D 발견 0 건이면 덱에 한 줄도 늘지 않는다]")
    d = box_dir(binary, "clean")
    open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_YAML.format(model="box.k", out="clean.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    check("rc=0", rc == 0, out[-400:])
    body = read(os.path.join(d, "clean.k"))
    check("$ KOOREMAPPER-PIDREF 블록을 쓰지 않는다", "KOOREMAPPER-PIDREF" not in body)
    check("덱 첫 줄은 그대로 *KEYWORD", body.splitlines()[0].strip() == "*KEYWORD")


def fold_top20(binary):
    print("[E 콘솔은 상위 20 건까지만 낸다]")
    d = box_dir(binary, "fold")
    # 죽은 노드 10..18 을 한 줄에 하나씩 가리키는 *BOUNDARY_SPC_NODE 를 잔뜩 만든다
    cards = "*BOUNDARY_SPC_NODE\n"
    for _ in range(3):
        for n in range(10, 19):
            cards += "%10d         0         1         1         1\n" % n
        cards += "*BOUNDARY_SPC_NODE\n"
    with_cards(d, "many.k", cards)
    open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_YAML.format(model="many.k", out="many_out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    shown = len([ln for ln in out.splitlines() if "] line " in ln and ln.startswith("    [")])
    check("콘솔에 낸 건수가 20 을 넘지 않는다", shown <= 20, str(shown))
    check("나머지는 개수로 접는다", "그 밖" in out and "건은 출력 덱" in out, out[-600:])
    body = read(os.path.join(d, "many_out.k"))
    check("덱 블록에는 접지 않고 전부 적는다",
          body.count("$ KOOREMAPPER-PIDREF [") > 20, str(body.count("$ KOOREMAPPER-PIDREF [")))


MERGE_YAML = """base_model: two.k
output: merged
operations:
  - type: merge
    target_pids: [1, 2]
    direction: z
    method: vrh
"""


def make_two_part(d):
    """box.k 의 위층 요소(5..8)를 PID 2 로 돌린 2 파트 덱."""
    lines = read(os.path.join(d, "box.k")).splitlines()
    out, inelem = [], False
    for ln in lines:
        if ln.startswith("*PART"):
            out += ["*MAT_ELASTIC", "         2  2.70e-09   7.0e+04      0.33",
                    "*SECTION_SOLID", "         2         1",
                    "*PART", "TOP", "         2         2         2"]
        if ln.startswith("*"):
            inelem = ln.strip().upper().startswith("*ELEMENT_SOLID")
            out.append(ln)
            continue
        if inelem and ln and ln[0] != "$" and 5 <= int(ln[0:8]) <= 8:
            ln = ln[:8] + "       2" + ln[16:]
        out.append(ln)
    txt = "\n".join(out) + "\n"
    txt = txt.replace("*END",
                      "*SET_PART_LIST\n       300\n         1         2\n"
                      "*DAMPING_PART_MASS\n         2       0.1\n"
                      "*SET_SOLID_LIST\n       301\n         6\n*END", 1)
    open(os.path.join(d, "two.k"), "w").write(txt)


def merge_path(binary):
    print("[F merge 도 같은 결함 — 같은 스캐너·보고·rc]")
    d = box_dir(binary, "merge")
    make_two_part(d)
    open(os.path.join(d, "mg.yaml"), "w").write(MERGE_YAML)
    rc, out = run(binary, d, "assemble", "mg.yaml")
    check("rc=1", rc == 1, out[-400:])
    check("덱은 그래도 쓴다", os.path.exists(os.path.join(d, "merged.k")))
    check("PID 축: *SET_PART_LIST 를 찾는다",
          any("*SET_PART_LIST" in ln for ln in axis_lines(out, "PID")), out[-900:])
    check("PID 축: *DAMPING_PART_MASS 를 찾는다",
          any("*DAMPING_PART_MASS" in ln for ln in axis_lines(out, "PID")), out[-900:])
    check("EID 축: *SET_SOLID_LIST 를 찾는다",
          any("*SET_SOLID_LIST" in ln for ln in axis_lines(out, "EID")), out[-900:])
    check("덱 머리에 블록을 박는다", "KOOREMAPPER-PIDREF" in read(os.path.join(d, "merged.k")))


def rigid_reject(binary):
    print("[G 강체 파트 restack 거부]")
    d = box_dir(binary, "rigid")
    box = read(os.path.join(d, "box.k"))
    open(os.path.join(d, "rigid.k"), "w").write(box.replace("*MAT_ELASTIC", "*MAT_RIGID", 1))
    open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_YAML.format(model="rigid.k", out="r_out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    check("*MAT_RIGID: rc=1", rc == 1, out[-400:])
    check("*MAT_RIGID: 이유를 알린다", "*MAT_RIGID" in out and "강체" in out, out[-400:])
    check("*MAT_RIGID: 덱을 내지 않는다", not os.path.exists(os.path.join(d, "r_out.k")))

    open(os.path.join(d, "inertia.k"), "w").write(box.replace("*PART\n", "*PART_INERTIA\n", 1))
    open(os.path.join(d, "ri.yaml"), "w").write(RESTACK_YAML.format(model="inertia.k", out="i_out.k"))
    rc2, out2 = run(binary, d, "restack", "ri.yaml")
    check("*PART_INERTIA: rc=1", rc2 == 1, out2[-400:])
    check("*PART_INERTIA: 이유를 알린다", "*PART_INERTIA" in out2, out2[-400:])
    check("*PART_INERTIA: 덱을 내지 않는다", not os.path.exists(os.path.join(d, "i_out.k")))


def part_cards(path):
    """[(pid, secid, mid, hgid, tmid)] — 데이터 줄을 10칸 고정폭으로 읽는다."""
    lines = read(path).splitlines()
    out = []
    for i, ln in enumerate(lines):
        if ln.strip().upper() not in ("*PART", "*PART_TITLE"):
            continue
        j = i + 2
        while j < len(lines) and lines[j].startswith("$"):
            j += 1
        if j >= len(lines):
            continue
        f = [lines[j][k:k + 10].strip() for k in range(0, 80, 10)]
        g = [int(x) if x else 0 for x in f]
        out.append((g[0], g[1], g[2], g[4], g[7]))
    return out


def section_elforms(path):
    """*SECTION_SOLID 의 {secid: elform}"""
    lines = read(path).splitlines()
    out = {}
    for i, ln in enumerate(lines):
        if not ln.strip().upper().startswith("*SECTION_SOLID"):
            continue
        j = i + 1
        while j < len(lines) and lines[j].startswith("$"):
            j += 1
        if j < len(lines):
            try:
                out[int(lines[j][:10])] = int(lines[j][10:20])
            except ValueError:
                pass
    return out


def inherit(binary):
    print("[H 새 층이 ELFORM·HGID·TMID 를 물려받는다]")
    d = box_dir(binary, "inherit")
    box = read(os.path.join(d, "box.k"))
    box = box.replace("*SECTION_SOLID\n$#   secid    elform\n         1         1\n",
                      "*SECTION_SOLID\n$#   secid    elform\n         1         2\n"
                      "*HOURGLASS\n         4         6       0.1\n")
    box = box.replace("*PART\nPLATE\n$#     pid     secid       mid\n"
                      "         1         1         1\n",
                      "*PART\nPLATE\n"
                      "$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid\n"
                      "         1         1         1         0         4         0         0         9\n")
    open(os.path.join(d, "inh.k"), "w").write(box)
    open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_YAML.format(model="inh.k", out="inh_out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    deck = os.path.join(d, "inh_out.k")
    if rc != 0 or not os.path.exists(deck):
        check("restack 실행", False, out[-400:])
        return
    secs = section_elforms(deck)
    layers = [p for p in part_cards(deck) if p[0] != 1]
    check("새 층 *SECTION_SOLID 의 ELFORM 이 2 다",
          bool(layers) and all(secs.get(p[1]) == 2 for p in layers), "%s %s" % (secs, layers))
    check("새 층 *PART 의 HGID 가 4 다", bool(layers) and all(p[3] == 4 for p in layers), str(layers))
    check("새 층 *PART 의 TMID 가 9 다", bool(layers) and all(p[4] == 9 for p in layers), str(layers))

    # 물려받을 것이 없으면 카드 모양이 바뀌지 않는다
    d2 = box_dir(binary, "plain")
    open(os.path.join(d2, "rs.yaml"), "w").write(RESTACK_YAML.format(model="box.k", out="p_out.k"))
    rc2, out2 = run(binary, d2, "restack", "rs.yaml")
    body = read(os.path.join(d2, "p_out.k"))
    check("물려받을 것이 없으면 세 칸짜리 *PART 카드를 그대로 쓴다",
          rc2 == 0 and "$#     pid     secid       mid\n" in body and
          "adpopt      tmid" not in body, out2[-300:])
    check("물려받을 것이 없으면 ELFORM 은 1 그대로", all(v == 1 for v in section_elforms(
        os.path.join(d2, "p_out.k")).values()), str(section_elforms(os.path.join(d2, "p_out.k"))))


def hist_set_variant(binary):
    """`_SET` 변형의 값은 **세트 ID** 다 — 요소 번호로 읽으면 오탐 + rc=1 이 난다.

    `*DATABASE_HISTORY_SOLID_SET 1` 에서 1 은 세트 ID 인데, EID 축이 그것을 요소 번호로 읽어
    "지워진 요소입니다" 를 찍고 rc=1 을 냈다(재현됨). PID 축의 histPart 에는 같은 `_SET` 제외가
    처음부터 있었다 — 한쪽만 빠져 있던 것이다.
    ⚠ 개수만 보면 안 된다. `maybe` 등급(칸 뜻 미확인)은 남아야 정직하다 — rc 에 반영되지 않는다.
    """
    print("[I _SET 변형을 요소 번호로 오독하지 않는다]")
    d = box_dir(binary, "histset")
    with_cards(d, "ref.k", "*DATABASE_HISTORY_SOLID_SET\n         1\n")
    open(os.path.join(d, "rs.yaml"), "w").write(RESTACK_YAML.format(model="ref.k", out="out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    eid = [ln for ln in axis_lines(out, "EID") if "DATABASE_HISTORY" in ln]
    check("_SET 변형이 EID 축에 안 올라온다", not eid, "\n".join(eid)[:300])
    check("그래서 rc=0", rc == 0, out[-300:])

    # 대조군 — `_SET` 없는 정상형은 여전히 잡아야 한다(제외를 너무 넓히지 않았나)
    d2 = box_dir(binary, "histplain")
    with_cards(d2, "ref.k", "*DATABASE_HISTORY_SOLID\n         1\n")
    open(os.path.join(d2, "rs.yaml"), "w").write(RESTACK_YAML.format(model="ref.k", out="out.k"))
    rc2, out2 = run(binary, d2, "restack", "rs.yaml")
    eid2 = [ln for ln in axis_lines(out2, "EID") if "DATABASE_HISTORY" in ln]
    check("정상형은 EID 축에 올라온다", bool(eid2), out2[-400:])
    check("그래서 rc=1", rc2 == 1, out2[-300:])


def main():
    if len(sys.argv) < 2:
        print("usage: test_pidref_detect.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    three_axes(binary)
    blank_field_contact(binary)
    title_set_id(binary)
    clean_deck(binary)
    fold_top20(binary)
    merge_path(binary)
    rigid_reject(binary)
    inherit(binary)
    hist_set_variant(binary)
    print("")
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
