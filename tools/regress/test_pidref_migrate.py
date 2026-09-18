# restack·merge 가 옮길 수 있는 죽은 PID 참조를 실제로 옮기는지 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_pidref_migrate.py <KooRemapper 바이너리>

배경
  - 앞 판은 탐지·보고까지였다. 이 판은 옮길 수 있는 것을 실제로 옮긴다.
      · 체적 의미로 쓰이는 *SET_PART_* : 죽은 PID → 층 PID 전부(한 줄 8개 규칙을 지켜 줄을 늘린다)
      · tied 계열 접촉                 : 상대측 기하를 적층 축에 투영해 층이 유일할 때만 그 층으로
      · 한 세트를 tied 와 체적이 함께 쓰면 : 세트를 복제해 tied 쪽만 한 층으로 가른다
      · 그 밖의 접촉                    : 모든 층이 solid 면 층 전부를 담은 세트로(STYP 3→2)
  - 층을 하나로 정하지 못하면 옮기지 않고 이유와 함께 보고한다 — 전 층으로 펴면 내부 계면까지
    묶여 층간 상대 전단이 죽는다(낙하 굽힘 응력 과대평가).
  - LS-DYNA 라이선스가 없어 덱을 풀 수 없다 — 덱 구조(세트 구성원·카드 1 칸)를 직접 읽어 확인한다.

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

MAT_LAYER = ("    material_card: |\n"
             "      *MAT_ELASTIC\n"
             "      $#     mid        ro         e        pr\n"
             "        MID%03d  7.85E-09    210000       0.3\n")


def restack_yaml(model, out, nlayers=2):
    y = "model: %s\noutput: %s\ntarget_pid: 1\ndirection: z\nlayers:\n" % (model, out)
    t = 2.0 / nlayers
    for i in range(nlayers):
        y += "  - title: L%d\n    thickness: %.6f\n    num_elements: 1\n" % (i + 1, t)
        y += MAT_LAYER % (i + 1)
    return y


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


def read(path):
    return open(path, encoding="utf-8", errors="replace").read()


def box_dir(binary, tag):
    d = tempfile.mkdtemp(prefix="pidmig_%s_" % tag, dir=scratch_root(binary))
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    return d


def with_cards(d, name, cards, base="box.k"):
    """base 의 *END 앞에 카드를 끼운 덱을 만든다."""
    txt = read(os.path.join(d, base)).replace("*END", cards + "*END", 1)
    open(os.path.join(d, name), "w").write(txt)
    return name


# ── 덱 읽기 도우미 ──────────────────────────────────────────────────────────
def fields(line):
    return [line[i:i + 10].strip() for i in range(0, max(len(line), 10), 10)]


def data_lines(deck, keyword, occurrence=0):
    """keyword 블록의 데이터 줄(주석 제외)."""
    lines = deck.splitlines()
    hits = []
    for i, ln in enumerate(lines):
        if ln.strip().upper() == keyword.upper():
            out = []
            for j in range(i + 1, len(lines)):
                t = lines[j].strip()
                if t.startswith("*"):
                    break
                if t.startswith("$") or not t:
                    continue
                out.append(lines[j])
            hits.append(out)
    return hits[occurrence] if occurrence < len(hits) else []


def contact_card1(deck, kw_contains, occurrence=0):
    """이름에 kw_contains 가 든 *CONTACT 블록의 카드 1 칸들."""
    lines = deck.splitlines()
    hits = []
    for i, ln in enumerate(lines):
        t = ln.strip().upper()
        if t.startswith("*CONTACT") and kw_contains.upper() in t:
            for j in range(i + 1, len(lines)):
                s = lines[j].strip()
                if s.startswith("$"):
                    continue
                if s.startswith("*") or not s:
                    break
                hits.append(fields(lines[j]))
                break
    return hits[occurrence] if occurrence < len(hits) else []


def part_sets(deck):
    """덱의 모든 *SET_PART_LIST[_TITLE] → {sid: [구성원 PID]}"""
    lines = deck.splitlines()
    out = {}
    for i, ln in enumerate(lines):
        t = ln.strip().upper()
        if not (t == "*SET_PART_LIST" or t == "*SET_PART_LIST_TITLE"):
            continue
        rows = []
        for j in range(i + 1, len(lines)):
            s = lines[j].strip()
            if s.startswith("*"):
                break
            if s.startswith("$") or not s:
                continue
            rows.append(lines[j])
        if t.endswith("_TITLE"):
            rows = rows[1:]
        if not rows:
            continue
        try:
            sid = int(fields(rows[0])[0])
        except (ValueError, IndexError):
            continue
        mem = []
        for r in rows[1:]:
            for f in fields(r):
                if f:
                    mem.append(int(f))
        out[sid] = mem
    return out


def layer_pids(deck):
    """restack 이 낸 층 *PART 의 PID 를 층 순서(L1, L2, …)대로."""
    lines = deck.splitlines()
    got = {}
    for i, ln in enumerate(lines):
        if ln.strip().upper() != "*PART":
            continue
        rows = []
        for j in range(i + 1, len(lines)):
            s = lines[j].strip()
            if s.startswith("*"):
                break
            if s.startswith("$"):
                continue
            rows.append(lines[j])
        if len(rows) < 2:
            continue
        title = rows[0].strip()
        if not title.startswith("L"):
            continue
        try:
            got[title] = int(fields(rows[1])[0])
        except (ValueError, IndexError):
            pass
    return [got[k] for k in sorted(got, key=lambda s: int(s[1:]))]


def pidref_block(deck):
    return [ln for ln in deck.splitlines() if ln.startswith("$ KOOREMAPPER-PIDREF")]


# ── 이웃 파트(덱 구성용) ────────────────────────────────────────────────────
def neighbour_cards():
    """PID 2(위 z=2..3), PID 3(아래 z=-1..0), PID 4(옆 x=20..30, z=0..2)."""
    def blk(pid, nid0, eid, z0, z1, x0=0.0, x1=10.0):
        s = "*PART\nNB%d\n%10d%10d%10d\n" % (pid, pid, 1, 1)
        s += "*NODE\n"
        pts = [(x0, 0.0, z0), (x1, 0.0, z0), (x1, 5.0, z0), (x0, 5.0, z0),
               (x0, 0.0, z1), (x1, 0.0, z1), (x1, 5.0, z1), (x0, 5.0, z1)]
        for k, (x, y, z) in enumerate(pts):
            s += "%8d%16.9e%16.9e%16.9e\n" % (nid0 + k, x, y, z)
        s += "*ELEMENT_SOLID\n"
        s += "%8d%8d" % (eid, pid) + "".join("%8d" % (nid0 + k) for k in range(8)) + "\n"
        return s
    return (blk(2, 101, 101, 2.0, 3.0) +
            blk(3, 111, 102, -1.0, 0.0) +
            blk(4, 121, 103, 0.0, 2.0, 20.0, 30.0))


# ── 시험 ────────────────────────────────────────────────────────────────────
def volume_set(binary):
    print("[A 체적 의미 세트는 층 PID 전부로 편다 — 옮겼으면 rc=0]")
    d = box_dir(binary, "vol")
    with_cards(d, "v.k",
               "*SET_PART_LIST\n       300\n         1\n"
               "*LOAD_BODY_PARTS\n       300\n")
    open(os.path.join(d, "rs.yaml"), "w").write(restack_yaml("v.k", "v_out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    deck_path = os.path.join(d, "v_out.k")
    check("rc=0 (옮기지 못한 자리가 없다)", rc == 0, out[-600:])
    if not os.path.exists(deck_path):
        check("덱을 쓴다", False, out[-600:])
        return
    deck = read(deck_path)
    lp = layer_pids(deck)
    check("층 PID 를 둘 찾는다", len(lp) == 2, str(lp))
    sets = part_sets(deck)
    check("세트 300 의 구성원이 층 PID 전부다", sets.get(300) == lp, "%s vs %s" % (sets.get(300), lp))
    check("죽은 PID 1 은 세트에서 사라졌다", 1 not in sets.get(300, []), str(sets.get(300)))
    blk = pidref_block(deck)
    check("덱 블록에 moved 로 적는다", any("(moved)" in ln for ln in blk), "\n".join(blk[:6]))
    check("덱 블록에 left 가 없다", not any("(left)" in ln for ln in blk), "\n".join(blk[:6]))
    check("콘솔이 옮긴 건수를 알린다", "옮긴 것 1 건" in out, out[-600:])


def wrap_eight(binary):
    print("[B 구성원이 8개를 넘으면 줄을 늘린다]")
    d = box_dir(binary, "wrap")
    with_cards(d, "w.k",
               "*SET_PART_LIST\n       300\n         1\n"
               "*LOAD_BODY_PARTS\n       300\n")
    open(os.path.join(d, "rs.yaml"), "w").write(restack_yaml("w.k", "w_out.k", nlayers=9))
    rc, out = run(binary, d, "restack", "rs.yaml")
    deck_path = os.path.join(d, "w_out.k")
    if not os.path.exists(deck_path):
        check("restack 실행", False, out[-800:])
        return
    deck = read(deck_path)
    lp = layer_pids(deck)
    check("층 PID 9개", len(lp) == 9, str(lp))
    check("세트 구성원이 층 PID 9개", part_sets(deck).get(300) == lp, str(part_sets(deck).get(300)))
    rows = data_lines(deck, "*SET_PART_LIST")
    check("구성원 줄이 두 줄이다(SID 줄 + 8개 + 1개)", len(rows) == 3, str(rows))
    if len(rows) == 3:
        check("첫 구성원 줄은 8개까지만 담는다",
              len([f for f in fields(rows[1]) if f]) == 8, rows[1])
        check("남은 하나는 다음 줄에 담는다",
              len([f for f in fields(rows[2]) if f]) == 1, rows[2])
    check("rc=0", rc == 0, out[-600:])


def tied_layer_pick(binary):
    print("[C tied 접촉은 상대측 기하가 정하는 층으로만 간다]")
    d = box_dir(binary, "tied")
    cards = neighbour_cards()
    cards += ("*CONTACT_TIED_SURFACE_TO_SURFACE\n"
              "         2         1         3         3\n")
    cards += ("*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET\n"
              "         3         1         3         3\n")
    cards += ("*CONTACT_TIED_NODES_TO_SURFACE\n"
              "         4         1         3         3\n")
    cards += ("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
              "         2         1         3         3\n")
    # 상대측이 세그먼트 집합(STYP=0, 윗면 노드)·노드 집합(STYP=4, 아랫면 노드)인 경우
    cards += ("*SET_SEGMENT\n       400       0.0       0.0       0.0       0.0\n"
              "        19        20        23        22\n")
    cards += ("*CONTACT_TIED_SHELL_EDGE_TO_SURFACE\n"
              "       400         1         0         3\n")
    cards += "*SET_NODE_LIST\n       401\n         1         2         5         4\n"
    cards += ("*CONTACT_TIED_SURFACE_TO_SURFACE_BEAM_OFFSET\n"
              "       401         1         4         3\n")
    with_cards(d, "t.k", cards)
    open(os.path.join(d, "rs.yaml"), "w").write(restack_yaml("t.k", "t_out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    deck_path = os.path.join(d, "t_out.k")
    if not os.path.exists(deck_path):
        check("restack 실행", False, out[-800:])
        return
    deck = read(deck_path)
    lp = layer_pids(deck)
    check("층 PID 를 둘 찾는다", len(lp) == 2, str(lp))
    if len(lp) != 2:
        return
    bottom, top = lp[0], lp[1]

    c_top = contact_card1(deck, "TIED_SURFACE_TO_SURFACE")
    check("위쪽 파트와 묶인 tie 는 맨 위 층으로 간다",
          c_top[1] == str(top), "%s (top=%d)" % (c_top, top))
    c_bot = contact_card1(deck, "TIED_SURFACE_TO_SURFACE_OFFSET")
    check("아래쪽 파트와 묶인 tie 는 맨 아래 층으로 간다",
          c_bot[1] == str(bottom), "%s (bottom=%d)" % (c_bot, bottom))
    c_amb = contact_card1(deck, "TIED_NODES_TO_SURFACE")
    check("두 층에 걸친 상대와 묶인 tie 는 그대로 둔다", c_amb[1] == "1", str(c_amb))
    check("애매한 tie 는 이유와 함께 보고한다",
          any("(left)" in ln and "TIED_NODES_TO_SURFACE" in ln and "걸쳐" in ln
              for ln in pidref_block(deck)),
          "\n".join(pidref_block(deck)))

    c_seg = contact_card1(deck, "TIED_SHELL_EDGE_TO_SURFACE")
    check("상대측이 윗면 세그먼트 집합(STYP=0)이면 맨 위 층으로 간다",
          c_seg[1] == str(top), "%s (top=%d)" % (c_seg, top))
    c_nod = contact_card1(deck, "TIED_SURFACE_TO_SURFACE_BEAM_OFFSET")
    check("상대측이 아랫면 노드 집합(STYP=4)이면 맨 아래 층으로 간다",
          c_nod[1] == str(bottom), "%s (bottom=%d)" % (c_nod, bottom))

    c_auto = contact_card1(deck, "AUTOMATIC_SURFACE_TO_SURFACE")
    check("tied 가 아닌 접촉은 STYP 3→2 로 바뀐다", c_auto[3] == "2", str(c_auto))
    sets = part_sets(deck)
    newsid = int(c_auto[1]) if c_auto[1] else 0
    check("그 새 세트가 층 PID 전부를 담는다", sets.get(newsid) == lp,
          "%s: %s (층 %s)" % (newsid, sets.get(newsid), lp))

    check("rc=1 (애매한 tie 를 못 옮겼다)", rc == 1, out[-600:])
    blk = pidref_block(deck)
    check("덱 블록에 moved 와 left 가 함께 적힌다",
          any("(moved)" in ln for ln in blk) and any("(left)" in ln for ln in blk),
          "\n".join(blk[:10]))


def mixed_set_split(binary):
    print("[D 한 세트를 tied 와 체적이 함께 쓰면 세트를 복제해 가른다]")
    d = box_dir(binary, "mixed")
    cards = neighbour_cards()
    cards += "*SET_PART_LIST\n       300\n         1\n"
    cards += "*LOAD_BODY_PARTS\n       300\n"
    cards += ("*CONTACT_TIED_SURFACE_TO_SURFACE\n"
              "         2       300         3         2\n")
    with_cards(d, "m.k", cards)
    open(os.path.join(d, "rs.yaml"), "w").write(restack_yaml("m.k", "m_out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    deck_path = os.path.join(d, "m_out.k")
    if not os.path.exists(deck_path):
        check("restack 실행", False, out[-800:])
        return
    deck = read(deck_path)
    lp = layer_pids(deck)
    sets = part_sets(deck)
    check("원 세트 300 은 층 PID 전부로 편다(체적 소비자)", sets.get(300) == lp,
          "%s vs %s" % (sets.get(300), lp))
    card = contact_card1(deck, "TIED_SURFACE_TO_SURFACE")
    dup = int(card[1]) if card and card[1] else 0
    check("tied 접촉은 새 세트를 가리킨다", dup not in (0, 300), str(card))
    check("그 새 세트는 맨 위 층 하나만 담는다", sets.get(dup) == [lp[1]] if len(lp) == 2 else False,
          "%s: %s (층 %s)" % (dup, sets.get(dup), lp))
    check("rc=0", rc == 0, out[-600:])


def ambiguous_keeps_set(binary):
    print("[E 층을 못 정하면 세트도 접촉도 건드리지 않는다]")
    d = box_dir(binary, "amb")
    cards = neighbour_cards()
    cards += "*SET_PART_LIST\n       300\n         1\n"
    cards += ("*CONTACT_TIED_SURFACE_TO_SURFACE\n"
              "         4       300         3         2\n")
    with_cards(d, "a.k", cards)
    open(os.path.join(d, "rs.yaml"), "w").write(restack_yaml("a.k", "a_out.k"))
    rc, out = run(binary, d, "restack", "rs.yaml")
    deck_path = os.path.join(d, "a_out.k")
    if not os.path.exists(deck_path):
        check("restack 실행", False, out[-800:])
        return
    deck = read(deck_path)
    check("세트 300 은 그대로 죽은 PID 를 담고 있다", part_sets(deck).get(300) == [1],
          str(part_sets(deck).get(300)))
    check("접촉 카드도 그대로다", contact_card1(deck, "TIED_SURFACE_TO_SURFACE")[1] == "300",
          str(contact_card1(deck, "TIED_SURFACE_TO_SURFACE")))
    check("rc=1", rc == 1, out[-600:])
    blk = pidref_block(deck)
    check("세트와 접촉 둘 다 이유와 함께 left 로 적는다",
          sum(1 for ln in blk if "(left)" in ln) >= 2, "\n".join(blk))
    check("이유에 '내부 계면' 을 적는다", any("내부 계면" in ln for ln in blk), "\n".join(blk))


MERGE_YAML = """base_model: two.k
output: merged
operations:
  - type: merge
    target_pids: [1, 2]
    direction: z
    method: vrh
"""


def make_two_part(d, extra=""):
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
    txt = txt.replace("*END", extra + "*END", 1)
    open(os.path.join(d, "two.k"), "w").write(txt)


def merge_path(binary):
    print("[F merge — 세트와 비-tied 접촉은 합친 PID 로, tied 는 보고만]")
    d = box_dir(binary, "merge")
    make_two_part(d,
                  "*SET_PART_LIST\n       300\n         1         2\n"
                  "*LOAD_BODY_PARTS\n       300\n"
                  "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
                  "         1         0         3         0\n"
                  "*CONTACT_TIED_SURFACE_TO_SURFACE\n"
                  "         2         0         3         0\n")
    open(os.path.join(d, "mg.yaml"), "w").write(MERGE_YAML)
    rc, out = run(binary, d, "assemble", "mg.yaml")
    deck_path = os.path.join(d, "merged.k")
    if not os.path.exists(deck_path):
        check("merge 실행", False, out[-800:])
        return
    deck = read(deck_path)
    mem = part_sets(deck).get(300)
    check("세트 300 은 합친 PID 하나만 담는다", mem is not None and len(mem) == 1 and mem[0] > 2,
          str(mem))
    merged = mem[0] if mem else 0
    c_auto = contact_card1(deck, "AUTOMATIC_SURFACE_TO_SURFACE")
    check("tied 가 아닌 접촉은 합친 PID 를 가리킨다", c_auto[0] == str(merged), str(c_auto))
    c_tied = contact_card1(deck, "TIED_SURFACE_TO_SURFACE")
    check("tied 접촉은 그대로 둔다", c_tied[0] == "2", str(c_tied))
    blk = pidref_block(deck)
    check("tied 를 못 옮긴 이유를 적는다",
          any("(left)" in ln and "세그먼트 세트" in ln for ln in blk), "\n".join(blk))
    check("rc=1 (못 옮긴 tied 가 남았다)", rc == 1, out[-600:])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: %s" % binary)
        return 2
    volume_set(binary)
    wrap_eight(binary)
    tied_layer_pick(binary)
    mixed_set_split(binary)
    ambiguous_keeps_set(binary)
    merge_path(binary)
    print()
    if FAILS:
        print("FAILED %d" % len(FAILS))
        for f in FAILS:
            print("  - %s" % f)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
