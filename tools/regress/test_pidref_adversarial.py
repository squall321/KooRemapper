# 적대적 검토에서 재현된 죽은 참조 이관 결함 6 건 — 빌드 바이너리를 실제로 실행해 막는다
"""
사용: python3 tools/regress/test_pidref_adversarial.py <KooRemapper 바이너리>

막는 결함
  A  pid_refs 를 읽는 자리가 없어 rc=1 강제의 탈출구(`pid_refs: warn`)가 통하지 않았다.
  B  *CONTACT_CONSTRAINT_* 를 tied 가 아니라고 보아 전 층으로 펴, 내부 계면까지 묶였다.
  C  *INCLUDE 로 나뉜 덱은 tied 소비자가 안 보이는데도 세트를 전 층으로 펴고 rc=0 이었다.
  D  제목 줄이 빈 *SET_..._TITLE 은 옮기지도 보고하지도 않았고, maxSetId_ 도 어긋났다.
  E  '모르는 자리'(maybe) 오탐(*BOUNDARY_SPC_SET 의 DOF 플래그 등)으로 멀쩡한 덱이 rc=1 이 됐다.
  F  merge 가 합치는 두 파트 사이의 접촉을 자기 자신을 가리키는 축퇴 카드로 바꿨다.

LS-DYNA 라이선스가 없어 덱을 풀 수 없다 — 덱 구조(세트 구성원·카드 1 칸)와 rc 를 직접 읽는다.
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


def restack_yaml(model, out, nlayers=2, extra=""):
    y = "model: %s\noutput: %s\ntarget_pid: 1\ndirection: z\n%slayers:\n" % (model, out, extra)
    t = 2.0 / nlayers
    for i in range(nlayers):
        y += "  - title: L%d\n    thickness: %.6f\n    num_elements: 1\n" % (i + 1, t)
        y += MAT_LAYER % (i + 1)
    return y


def check(name, cond, detail=""):
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
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
    d = tempfile.mkdtemp(prefix="pidadv_%s_" % tag, dir=scratch_root(binary))
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    return d


def with_cards(d, name, cards, base="box.k"):
    txt = read(os.path.join(d, base)).replace("*END", cards + "*END", 1)
    open(os.path.join(d, name), "w").write(txt)
    return name


def above_part(pid=2, nid0=101, eid=101, z0=2.0, z1=3.0):
    """적층 위쪽(z=2..3)에 놓인 이웃 파트 — tied 층 선택이 유일해지는 상대측이다."""
    s = "*PART\nNB%d\n%10d%10d%10d\n" % (pid, pid, 1, 1)
    s += "*NODE\n"
    pts = [(0.0, 0.0, z0), (10.0, 0.0, z0), (10.0, 5.0, z0), (0.0, 5.0, z0),
           (0.0, 0.0, z1), (10.0, 0.0, z1), (10.0, 5.0, z1), (0.0, 5.0, z1)]
    for k, (x, y, z) in enumerate(pts):
        s += "%8d%16.9e%16.9e%16.9e\n" % (nid0 + k, x, y, z)
    s += "*ELEMENT_SOLID\n"
    s += "%8d%8d" % (eid, pid) + "".join("%8d" % (nid0 + k) for k in range(8)) + "\n"
    return s


def fields(line):
    return [line[i:i + 10].strip() for i in range(0, max(len(line), 10), 10)]


def contact_card1(deck, kw_contains, occurrence=0):
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
    """덱의 *SET_PART_LIST[_TITLE] → {sid: [구성원 PID]} (제목 줄은 비어 있을 수 있다)"""
    lines = deck.splitlines()
    out = {}
    for i, ln in enumerate(lines):
        t = ln.strip().upper()
        if t not in ("*SET_PART_LIST", "*SET_PART_LIST_TITLE"):
            continue
        rows = []
        for j in range(i + 1, len(lines)):
            s = lines[j].strip()
            if s.startswith("*"):
                break
            if s.startswith("$"):
                continue
            rows.append(lines[j])
        while rows and not rows[-1].strip():
            rows.pop()
        if t.endswith("_TITLE") and rows:
            rows = rows[1:]          # 제목 줄(비어 있어도 한 줄이다)
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
        if len(rows) < 2 or not rows[0].strip().startswith("L"):
            continue
        try:
            got[rows[0].strip()] = int(fields(rows[1])[0])
        except (ValueError, IndexError):
            pass
    return [got[k] for k in sorted(got, key=lambda s: int(s[1:]))]


def pidref_block(deck):
    return [ln for ln in deck.splitlines() if ln.startswith("$ KOOREMAPPER-PIDREF")]


# ── A. pid_refs 리더 ────────────────────────────────────────────────────────
def pid_refs_reader(binary):
    print("[A pid_refs — strict 기본, warn 탈출구, 오타 거부]")
    d = box_dir(binary, "reader")
    with_cards(d, "sc.k", "*DAMPING_PART_MASS\n         1         0     1.000\n")

    open(os.path.join(d, "s1.yaml"), "w").write(restack_yaml("sc.k", "s1.k"))
    rc, out = run(binary, d, "restack", "s1.yaml")
    check("단독 restack: 기본은 strict → rc=1", rc == 1, out[-400:])

    open(os.path.join(d, "s2.yaml"), "w").write(
        restack_yaml("sc.k", "s2.k", extra="pid_refs: warn\n"))
    rc, out = run(binary, d, "restack", "s2.yaml")
    check("단독 restack: pid_refs: warn → rc=0 (예전엔 읽는 자리가 없어 rc=1)",
          rc == 0 and os.path.exists(os.path.join(d, "s2.k")), out[-400:])

    open(os.path.join(d, "s3.yaml"), "w").write(
        restack_yaml("sc.k", "s3.k", extra="pid_refs: nonsense\n"))
    rc, out = run(binary, d, "restack", "s3.yaml")
    check("단독 restack: 모르는 값은 조용히 strict 로 떨구지 않고 거부한다",
          rc == 1 and "invalid pid_refs" in out, out[-400:])

    asm = ("base_model: sc.k\noutput: a1\noperations:\n  - type: restack\n"
           "    target_pid: 1\n    direction: z\n    pid_refs: warn\n    layers:\n")
    for i in range(2):
        asm += "      - title: L%d\n        thickness: 1.0\n        num_elements: 1\n" % (i + 1)
        asm += ("        material_card: |\n          *MAT_ELASTIC\n"
                "          $#     mid        ro         e        pr\n"
                "            MID%03d  7.85E-09    210000       0.3\n" % (i + 1))
    open(os.path.join(d, "a1.yaml"), "w").write(asm)
    rc, out = run(binary, d, "assemble", "a1.yaml")
    check("assemble op 키 pid_refs: warn 도 통한다", rc == 0, out[-400:])


# ── B. *CONTACT_CONSTRAINT_* 는 tied ───────────────────────────────────────
def constraint_is_tied(binary):
    print("[B *CONTACT_CONSTRAINT_* — 전 층으로 펴지 않는다]")
    for kw in ("*CONTACT_CONSTRAINT_SURFACE_TO_SURFACE",
               "*CONTACT_CONSTRAINT_NODES_TO_SURFACE"):
        tag = kw.rsplit("_CONSTRAINT_", 1)[1][:5].lower()
        d = box_dir(binary, "cc" + tag)
        with_cards(d, "cc.k", above_part() +
                   "%s\n         1         2         3         3\n       0.2       0.2\n" % kw)
        open(os.path.join(d, "cc.yaml"), "w").write(restack_yaml("cc.k", "cc_out.k"))
        rc, out = run(binary, d, "restack", "cc.yaml")
        deck = read(os.path.join(d, "cc_out.k"))
        pids = layer_pids(deck)
        card = contact_card1(deck, "CONSTRAINT")
        # 상대측(PID 2)은 적층 위에 있다 → 층이 유일하게 정해져 최대측 층 하나로 간다.
        check("%s: 층 하나(PID %s)로 간다" % (kw, pids[-1] if pids else "?"),
              bool(card) and card[0] == str(pids[-1]) and card[2] == "3", str(card))
        check("%s: 층 전부를 담은 새 세트로 펴지 않는다" % kw,
              not any(set(mem) == set(pids) for mem in part_sets(deck).values()),
              str(part_sets(deck)))
        check("%s: rc=0" % kw, rc == 0, out[-300:])


# ── C. *INCLUDE ────────────────────────────────────────────────────────────
def include_stops_spread(binary):
    print("[C *INCLUDE — 못 본 것을 밝히고 세트를 펴지 않는다]")
    d = box_dir(binary, "incl")
    with_cards(d, "inc_main.k", above_part() +
               "*SET_PART_LIST\n       300\n         1\n*INCLUDE\ninc_ct.k\n")
    open(os.path.join(d, "inc_ct.k"), "w").write(
        "*KEYWORD\n*CONTACT_TIED_SURFACE_TO_SURFACE\n"
        "       300         2         2         3\n       0.2       0.2\n*END\n")
    open(os.path.join(d, "inc.yaml"), "w").write(restack_yaml("inc_main.k", "inc_out.k"))
    rc, out = run(binary, d, "restack", "inc.yaml")
    deck = read(os.path.join(d, "inc_out.k"))
    check("세트 300 은 그대로 죽은 PID 1 만 담는다(전 층으로 펴지 않는다)",
          part_sets(deck).get(300) == [1], str(part_sets(deck)))
    blk = pidref_block(deck)
    check("인클루드를 읽지 않았다고 밝힌다",
          any("*INCLUDE" in ln and "읽지 않았습니다" in ln for ln in blk), "\n".join(blk))
    check("strict 에서 rc=1 (예전엔 rc=0 으로 솔버까지 갔다)", rc == 1, out[-400:])


# ── D. 제목 줄이 빈 *SET_..._TITLE ─────────────────────────────────────────
def blank_title_set(binary):
    print("[D 제목 줄이 빈 *SET_..._TITLE — 옮기고, 새 세트 번호도 부딪치지 않는다]")
    d = box_dir(binary, "blank")
    with_cards(d, "bt.k", above_part() +
               "*SET_PART_LIST_TITLE\n" + " " * 20 + "\n       400\n         1\n"
               "*LOAD_BODY_PARTS\n       400\n"
               "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
               "         1         2         3         3\n")
    open(os.path.join(d, "bt.yaml"), "w").write(restack_yaml("bt.k", "bt_out.k"))
    rc, out = run(binary, d, "restack", "bt.yaml")
    deck = read(os.path.join(d, "bt_out.k"))
    sets = part_sets(deck)
    pids = layer_pids(deck)
    check("세트 400 의 죽은 PID 가 층 PID 전부로 바뀐다(예전엔 완전 무음)",
          sets.get(400) == pids, "%s / layers=%s" % (sets, pids))
    new_sids = [s for s in sets if s != 400]
    check("새로 낸 세트 번호가 덱의 400 보다 크다(maxSetId_ 가 구성원을 SID 로 읽지 않는다)",
          bool(new_sids) and min(new_sids) > 400, str(sorted(sets)))
    check("rc=0", rc == 0, out[-400:])


# ── E. maybe 오탐은 rc 를 올리지 않는다 ────────────────────────────────────
def maybe_not_rc(binary):
    print("[E '모르는 자리' 오탐 — 보고는 하되 rc 는 올리지 않는다]")
    d = box_dir(binary, "maybe")
    with_cards(d, "mb.k",
               "*BOUNDARY_SPC_SET\n"
               "       900         0         1         1         1         1         1         1\n"
               "*DATABASE_HISTORY_NODE\n         1\n"
               "*DEFINE_BOX\n"
               "         1       0.0      10.0       0.0       5.0       0.0      10.0\n")
    open(os.path.join(d, "mb.yaml"), "w").write(restack_yaml("mb.k", "mb_out.k"))
    rc, out = run(binary, d, "restack", "mb.yaml")
    deck = read(os.path.join(d, "mb_out.k"))
    blk = pidref_block(deck)
    check("maybe 로 보고는 남는다", sum(1 for ln in blk if "(maybe)" in ln) >= 3, "\n".join(blk))
    check("maybe 만 남으면 rc=0 (예전엔 target_pid 1 인 멀쩡한 덱이 rc=1)", rc == 0, out[-500:])


# ── F. merge — 두 면이 모두 합쳐지는 접촉 ──────────────────────────────────
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
    txt = ("\n".join(out) + "\n").replace("*END", extra + "*END", 1)
    open(os.path.join(d, "two.k"), "w").write(txt)


def merge_both_sides_dead(binary):
    print("[F merge — 두 면이 모두 합쳐지면 카드를 고치지 않는다]")
    d = box_dir(binary, "mgboth")
    make_two_part(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
                     "         1         2         3         3\n")
    open(os.path.join(d, "mg.yaml"), "w").write(MERGE_YAML)
    rc, out = run(binary, d, "assemble", "mg.yaml")
    deck_path = os.path.join(d, "merged.k")
    if not os.path.exists(deck_path):
        check("merge 실행", False, out[-800:])
        return
    deck = read(deck_path)
    card = contact_card1(deck, "AUTOMATIC_SURFACE_TO_SURFACE")
    check("카드 1 은 그대로다 — 자기 자신을 가리키는 축퇴 카드로 바꾸지 않는다",
          card[:4] == ["1", "2", "3", "3"], str(card))
    blk = pidref_block(deck)
    check("계면이 사라졌으니 카드를 지우라고 알린다",
          any("(left)" in ln and "계면이 사라졌" in ln for ln in blk), "\n".join(blk))
    check("strict 에서 rc=1", rc == 1, out[-500:])

    # 한쪽만 죽은 카드는 그대로 합친 PID 로 옮긴다(이관을 통째로 끄지 않았다)
    d2 = box_dir(binary, "mgone")
    make_two_part(d2, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
                      "         1        99         3         3\n")
    open(os.path.join(d2, "mg.yaml"), "w").write(MERGE_YAML + "    pid_refs: warn\n")
    rc, out = run(binary, d2, "assemble", "mg.yaml")
    deck = read(os.path.join(d2, "merged.k"))
    card = contact_card1(deck, "AUTOMATIC_SURFACE_TO_SURFACE")
    check("한쪽만 죽으면 합친 PID 로 옮긴다",
          bool(card) and card[0] not in ("1", "") and card[1] == "99", "%s rc=%d" % (card, rc))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: %s" % binary)
        return 2
    pid_refs_reader(binary)
    constraint_is_tied(binary)
    include_stops_spread(binary)
    blank_title_set(binary)
    maybe_not_rc(binary)
    merge_both_sides_dead(binary)
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
