#!/usr/bin/env python3
# contact 카드 결함(10-23) — 카드 순서 · 빈 줄 · MPP · 자유 형식 · Card C 열 · 필수 카드 · 반올림 · 음수 · 엄격한 숫자 · detect · optimize · stabilize
"""왜 이 시험이 있나 (2026-10-23).

contact op 의 키 112개를 매뉴얼(Vol_I R16)과 대조하다가 설명만으로는 못 고치는 **코드 결함**이 나왔고, 고치며 더 나왔다
(`docs/01-plan/features/contact-card-defects-1023.findings.md` · `contact-cards-1023.plan.md`). 전부 덱을 **조용히** 틀리게 썼다.

  매뉴얼 카드 순서 — ID → MPP 1 → (MPP 2, 첫 칸 `&`) → Card 1 · 2 · 3 → Card 4(형마다) → THRM → ORFR → 선택 카드 A, B, …
  빈 줄도 카드다(「Optional Cards A … may be blank lines」). 줄에 쉼표가 있으면 자유 형식이다.

항마다 옛 바이너리(배포 252bd444 · 그 전 cd07c327)에서 빨갛고 새 바이너리에서 초록이어야 한다 — 그래야 그 결함을 잡는 시험이다.
솔버로는 재지 않는다(카드 칸 · 순서 · 값만 본다).

usage: test_contact_cards.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_set_add_resolution import base_deck  # noqa: E402 — 같은 4파트 셸 덱(z = 0.05·pid 로 층)

FAILS = []
BIN = ""


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))
    return cond


def run(d, *args):
    p = subprocess.run([BIN, *args], cwd=d, capture_output=True, text=True, timeout=300,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def fld(line, k):
    """고정 10칸의 k번째(0-기준) 칸 글자."""
    return line[10 * k:10 * k + 10].strip() if line is not None else ""


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def cblocks(path):
    """덱의 *CONTACT 블록 — (키워드, 카드 줄들) 차례대로. `$` 주석만 빼고 빈 줄은 카드로 둔다(LS-DYNA 와 같다)."""
    if not os.path.exists(path):
        return []
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    out, i = [], 0
    while i < len(lines):
        t = lines[i].strip()
        if t.upper().startswith("*CONTACT_"):
            cards, j = [], i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("*"):
                if not lines[j].lstrip().startswith("$"):
                    cards.append(lines[j])
                j += 1
            out.append((t.upper(), cards))
            i = j
            continue
        i += 1
    return out


def card(blocks, b, k):
    try:
        return blocks[b][1][k]
    except IndexError:
        return None


C123 = ("         1         3         3         3\n"
        "       0.2       0.1\n"
        "       1.0       1.0\n")


def deck(d, *contacts, name="m.k"):
    open(os.path.join(d, name), "w").write(base_deck() + "".join(contacts) + "*END\n")


def yml(d, name, body, model="m.k"):
    open(os.path.join(d, name + ".yaml"), "w").write(
        "model: %s\noutput: %s.k\ncontacts:\n%s" % (model, name, body))
    return name + ".yaml"


def contact_run(d, name, body, model="m.k"):
    rc, out = run(d, "contact", yml(d, name, body, model))
    return rc, out, cblocks(os.path.join(d, name + ".k"))


def main():
    global BIN
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    BIN = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="ctcards_")
    try:
        sections(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print()
    if FAILS:
        print("--- 실패 %d건 ---" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("ALL PASS")
    return 0


def sections(d):
    print("[A 자유 형식(쉼표) 카드 — D19]")
    deck(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n1,3,3,3\n0.3,0.2\n1.0,1.0\n")
    rc, out = run(d, "contact", yml(d, "a0", "  - action: analyze\n"))
    check("A-1 `1,3,3,3` 을 PID 1 대 PID 3 으로 읽는다", "Slave:  PID 1" in out and "Master: PID 3" in out, out[-400:])
    check("A-2 `0.3,0.2` 의 FD 를 0.2 로 읽는다", "FD=0.2" in out, out[-200:])
    rc, out, b = contact_run(d, "a1", "  - action: modify\n    contact_index: 0\n    friction: 0.5\n")
    c2 = card(b, 0, 1)
    check("A-3 쉼표 줄을 고치면 고정폭으로 바꿔 FS 만 바꾼다(FD 0.2 그대로)",
          rc == 0 and num(fld(c2, 0)) == 0.5 and num(fld(c2, 1)) == 0.2, repr(c2))

    print("[B `_MPP` — MPP 1 · MPP 2 는 Card 1 앞 — D9]")
    mpp1, mpp2 = "         0       200", "&         0       1.0         1"
    deck(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MPP\n%s\n%s\n%s" % (mpp1, mpp2, C123))
    rc, out = run(d, "contact", yml(d, "b0", "  - action: analyze\n"))
    check("B-1 MPP 카드를 건너뛰고 Card 1 을 PID 1 대 PID 3 으로 읽는다",
          "Slave:  PID 1" in out and "Master: PID 3" in out, out[-400:])
    rc, out, b = contact_run(d, "b1", "  - action: modify\n    contact_index: 0\n    friction: 0.4\n")
    check("B-2 MPP 1 · MPP 2 줄 그대로", card(b, 0, 0) == mpp1 and card(b, 0, 1) == mpp2, repr(b[0][1][:2] if b else b))
    check("B-3 Card 1 그대로(마찰이 SSID 칸에 들어가지 않는다)", fld(card(b, 0, 2), 0) == "1", repr(card(b, 0, 2)))
    check("B-4 마찰은 Card 2 의 FS 칸에", num(fld(card(b, 0, 3), 0)) == 0.4, repr(card(b, 0, 3)))

    print("[C 빈 줄은 카드 — D8]")
    deck(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n" + C123 +
         "         1\n"                     # Card A (SOFT 1)
         "\n"                               # Card B — 빈 줄(기본값)
         "         1         2\n")          # Card C (IGAP 1 · IGNORE 2)
    rc, out, b = contact_run(d, "c0", "  - action: modify\n    contact_index: 0\n    depth: 3\n")
    opt = b[0][1][3:] if b else []
    check("C-1 빈 Card B 뒤의 Card C 가 Card C 로 남는다(IGNORE 2)", len(opt) >= 3 and fld(opt[2], 1) == "2", repr(opt))
    check("C-2 Card A 에 DEPTH 3 · SOFT 1 그대로", len(opt) >= 1 and fld(opt[0], 5) == "3" and fld(opt[0], 0) == "1", repr(opt[:1]))

    print("[D TIEBREAK Card 4 는 선택 카드 앞 · 고쳐도 남는다 — D7 · D2]")
    card4 = "         2      10.0      50.0"
    deck(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK\n" + C123 + card4 + "\n         1\n")
    rc, out, b = contact_run(d, "d0", "  - action: modify\n    contact_index: 0\n    depth: 3\n")
    check("D-1 Card 4 가 한 글자도 안 바뀐다", card(b, 0, 3) == card4, repr(card(b, 0, 3)))
    check("D-2 그 뒤 Card A 에 DEPTH 3", fld(card(b, 0, 4), 5) == "3" and fld(card(b, 0, 4), 0) == "1", repr(card(b, 0, 4)))
    rc, out, b = contact_run(d, "d1", "  - action: modify\n    contact_index: 0\n    nfls: 20\n")
    check("D-3 modify 가 Card 4 칸(NFLS)을 그 자리에서 고친다", rc == 0 and num(fld(card(b, 0, 3), 1)) == 20, repr(card(b, 0, 3)))
    rc, out, b = contact_run(d, "d2", "  - action: modify\n    contact_index: 0\n    k: 5\n")
    check("D-4 THRM 이 없는 접촉의 열 칸 modify 는 거절(rc 1)", rc != 0 and "THRM" in out, out[-200:])

    print("[E create tiebreak — OPTION 은 필수 · Card 4 는 Card A 앞 — D4 · D2]")
    deck(d)
    side = "    slave: {pid: 1}\n    master: {pid: 3}\n    title: tb\n"
    rc, out, b = contact_run(d, "e0", "  - action: create\n    type: tiebreak\n" + side +
                             "    option: 2\n    nfls: 10\n    sfls: 50\n    soft: 1\n")
    check("E-1 rc 0", rc == 0, out[-300:])
    # _ID 카드 · Card 1 · 2 · 3 · Card 4 · Card A
    check("E-2 Card 4(OPTION 2 · NFLS 10)가 Card 3 바로 뒤", fld(card(b, 0, 4), 0) == "2" and num(fld(card(b, 0, 4), 1)) == 10,
          repr(card(b, 0, 4)))
    check("E-3 Card A(SOFT 1)는 Card 4 뒤", fld(card(b, 0, 5), 0) == "1", repr(card(b, 0, 5)))
    rc, out, _ = contact_run(d, "e1", "  - action: create\n    type: tiebreak\n" + side + "    nfls: 10\n    sfls: 50\n")
    check("E-4 option 없이는 거절(rc 1 · 매뉴얼 required)", rc != 0 and "option" in out, out[-300:])
    rc, out, _ = contact_run(d, "e2", "  - action: create\n    type: tiebreak\n" + side + "    option: 2\n    nfls: 10\n")
    check("E-5 파손 OPTION 에 sfls 가 없으면 거절", rc != 0 and "sfls" in out, out[-300:])
    rc, out, _ = contact_run(d, "e3", "  - action: create\n    type: tiebreak\n" + side +
                             "    option: 13\n    nfls: 10\n    sfls: 50\n")
    check("E-6 OPTION 13(추가 카드 필요)은 거절", rc != 0, out[-200:])
    rc, out, _ = contact_run(d, "e4", "  - action: create\n    type: tiebreak\n" + side +
                             "    option: 2\n    nfls: 10\n    sfls: 50\n    soft: 2\n")
    check("E-7 tiebreak + SOFT 2 는 거절(매뉴얼 Remark 2)", rc != 0 and "SOFT" in out, out[-200:])

    print("[F 열 접촉 — 6번째 칸은 FTOSA(기본 0) — D3]")
    rc, out, b = contact_run(d, "f0", "  - action: create\n    type: tied_thermal\n" + side + "    k: 100\n")
    th = card(b, 0, 4)
    check("F-1 THRM 1 이 Card 3 뒤 · FTOSA 0(예전 1.0)", rc == 0 and num(fld(th, 0)) == 100 and num(fld(th, 5)) == 0, repr(th))
    rc, out, b = contact_run(d, "f1", "  - action: create\n    type: tied_thermal\n" + side + "    k: 100\n    ftosa: 0.3\n")
    check("F-2 키 ftosa", num(fld(card(b, 0, 4), 5)) == 0.3, repr(card(b, 0, 4)))
    rc, out, b = contact_run(d, "f2", "  - action: create\n    type: tied_thermal\n" + side + "    k: 100\n    chlm: 0.5\n")
    check("F-3 옛 키 chlm 도 같은 칸", num(fld(card(b, 0, 4), 5)) == 0.5, repr(card(b, 0, 4)))

    print("[G tied_mortar 는 있는 키워드로 — D5]")
    rc, out, b = contact_run(d, "g0", "  - action: create\n    type: tied_mortar\n" + side)
    check("G-1 *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MORTAR_TIED_ID",
          b and b[0][0] == "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MORTAR_TIED_ID", b[0][0] if b else out[-200:])
    check("G-2 「모르는 키워드」 경고 없음", "not a known contact keyword" not in out, out[-200:])

    print("[H 필수 Card 4 형 — ERODING 은 쓰고, 꼴을 모르는 형은 거절 — D6]")
    rc, out, b = contact_run(d, "h0", "  - action: create\n    type: eroding\n" + side)
    c4 = card(b, 0, 4)
    check("H-1 ERODING Card 4(ISYM 0 · EROSOP 1 · IADJ 0)", rc == 0 and (fld(c4, 0), fld(c4, 1), fld(c4, 2)) == ("0", "1", "0"),
          repr(c4))
    for i, t in enumerate(["automatic_surface_to_surface_tiebreak_user", "drawbead",
                           "tied_surface_to_surface_thermal_friction", "tiebreak_surface_to_surface"]):
        rc, out, b = contact_run(d, "h%d" % (i + 1), "  - action: create\n    type: %s\n" % t + side)
        check("H-%d %s 는 거절(필수 카드를 못 쓴다)" % (i + 2, t), rc != 0 and not b, out[-200:])

    print("[I Card C — FLANGL 7열 · CID_RCF 8열 — D1]")
    rc, out, b = contact_run(d, "i0", "  - action: create\n    type: auto\n" + side + "    flangl: 0.5\n    cid_rcf: 9\n")
    cc = card(b, 0, 6)   # ID · 1 · 2 · 3 · A · B · C
    check("I-1 6열 공란 · 7열 FLANGL 0.5 · 8열 CID_RCF 9",
          fld(cc, 5) == "" and num(fld(cc, 6)) == 0.5 and fld(cc, 7) == "9", repr(cc))
    deck(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n" + C123 + "         1\n\n"
         "         1         0       0.0       0.0       0.0                 0.5         9\n")
    rc, out, b = contact_run(d, "i1", "  - action: modify\n    contact_index: 0\n    soft: 2\n")
    cc = card(b, 0, 5)   # 1 · 2 · 3 · A · B · C
    check("I-2 올바른 Card C 를 modify 왕복해도 FLANGL · CID_RCF 그대로", num(fld(cc, 6)) == 0.5 and fld(cc, 7) == "9", repr(cc))
    deck(d)

    print("[J Card A 의 안 준 칸은 0(= 형의 기본) — D10]")
    rc, out, b = contact_run(d, "j0", "  - action: create\n    type: auto\n" + side + "    soft: 1\n")
    ca = card(b, 0, 4)
    check("J-1 SOFSCL · MAXPAR · SBOPT · DEPTH · FRCFRQ = 0(예전 0.1 · 1.025 · 2 · 2 · 1)",
          [num(fld(ca, k)) for k in (1, 3, 4, 5, 7)] == [0, 0, 0, 0, 0], repr(ca))

    print("[K 뜻 있는 음수 — D11]")
    rc, out, b = contact_run(d, "k0", "  - action: create\n    type: auto\n" + side +
                             "    bt: -0.5\n    sast: -0.3\n    depth: -12\n    sboxid: -4\n")
    check("K-1 BT −0.5(동적 이완 중에도 따른다)", num(fld(card(b, 0, 2), 6)) == -0.5, repr(card(b, 0, 2)))
    check("K-2 SAST −0.3(TIED 판정 거리)", num(fld(card(b, 0, 3), 2)) == -0.3, repr(card(b, 0, 3)))
    check("K-3 DEPTH −12(곡선)", fld(card(b, 0, 4), 5) == "-12", repr(card(b, 0, 4)))
    check("K-4 SBOXID −4(접촉 부피)", fld(card(b, 0, 1), 4) == "-4", repr(card(b, 0, 1)))

    print("[L 값을 반올림하지 않는다 — D15]")
    rc, out, b = contact_run(d, "l0", "  - action: create\n    type: auto\n" + side + "    friction: 0.125\n    bt: 0.0005\n")
    check("L-1 FS 0.125(예전 0.13) · BT 0.0005(예전 0.00)",
          num(fld(card(b, 0, 2), 0)) == 0.125 and num(fld(card(b, 0, 2), 6)) == 0.0005, repr(card(b, 0, 2)))
    rc, out, b = contact_run(d, "l1", "  - action: create\n    type: tiebreak\n" + side +
                             "    option: 2\n    nfls: 123.456\n    sfls: 50\n")
    check("L-2 NFLS 123.456(예전 123)", num(fld(card(b, 0, 4), 1)) == 123.456, repr(card(b, 0, 4)))
    deck(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n" + C123)
    rc, out, b = contact_run(d, "l2", "  - action: modify\n    contact_index: 0\n    friction: 0.125\n")
    check("L-3 modify 도 FS 0.125", num(fld(card(b, 0, 1), 0)) == 0.125, repr(card(b, 0, 1)))
    deck(d)

    print("[M 못 읽는 숫자는 rc 1 — D16]")
    rc, out, b = contact_run(d, "m0", "  - action: create\n    type: auto\n" + side + "    friction: 0,3\n")
    check("M-1 friction: 0,3 → rc 1", rc != 0 and "friction" in out, out[-200:])
    rc, out, b = contact_run(d, "m1", "  - action: create\n    type: auto\n" + side + "    soft: two\n")
    check("M-2 soft: two → rc 1", rc != 0 and "soft" in out, out[-200:])

    print("[N modify 가 Card 1 확장 칸을 쓴다 — D17]")
    deck(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n" + C123)
    rc, out, b = contact_run(d, "n0", "  - action: modify\n    contact_index: 0\n    sboxid: 5\n")
    check("N-1 SBOXID 5", fld(card(b, 0, 0), 4) == "5", repr(card(b, 0, 0)))

    print("[O remove 뒤의 modify 가 줄을 밀어도 맞는 접촉을 지운다 — D21]")
    c1 = "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n         1         2         3         3\n       0.2\n       1.0\n"
    c2 = "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n         3         4         3         3\n       0.3\n       1.0\n"
    deck(d, c1, c2)
    rc, out, b = contact_run(d, "o0", "  - action: remove\n    contact_index: 1\n"
                                      "  - action: modify\n    contact_index: 0\n    soft: 1\n")
    txt = open(os.path.join(d, "o0.k")).read() if os.path.exists(os.path.join(d, "o0.k")) else ""
    check("O-1 접촉 하나만 남는다(1 대 2)", len(b) == 1 and fld(card(b, 0, 0), 1) == "2", [x[0] for x in b])
    check("O-2 남은 접촉에 Card A(SOFT 1)", len(b) == 1 and fld(card(b, 0, 3), 0) == "1", repr(b[0][1] if b else b))
    check("O-3 지운 접촉의 카드가 흩어져 남지 않는다(*END 앞 줄이 Card A)",
          txt.rstrip().endswith("*END") and "0.3" not in txt.split("*CONTACT_")[-1], txt[-300:])

    print("[P detect 도 필수 카드를 쓴다 — D12]")
    deck(d)
    rc, out, b = contact_run(d, "p0", "  - action: detect\n    slave: {pid: 1}\n    master: {pid: 2}\n"
                                      "    contact_type: tied_thermal\n    auto_create: true\n    k: 50\n")
    check("P-1 detect tied_thermal 이 THRM 1 을 Card 3 뒤에 쓴다", rc == 0 and num(fld(card(b, 0, 4), 0)) == 50, repr(b[0][1] if b else out[-200:]))
    rc, out, b = contact_run(d, "p1", "  - action: detect\n    slave: {pid: 1}\n    master: {pid: 2}\n"
                                      "    contact_type: tiebreak\n    auto_create: true\n")
    check("P-2 detect tiebreak 에 option 이 없으면 거절", rc != 0 and "option" in out, out[-200:])

    print("[Q detect 의 skip_existing · subtract_existing 가 SET_SEGMENT 접촉을 안다 — D13]")
    rc, out, b1 = contact_run(d, "q0", "  - action: detect\n    scope: all\n    contact_type: tied\n    auto_create: true\n")
    n1 = len(b1)
    check("Q-1 첫 detect 가 접촉을 만든다", rc == 0 and n1 >= 1, out[-200:])
    rc, out, b2 = contact_run(d, "q1", "  - action: detect\n    scope: all\n    contact_type: tied\n    auto_create: true\n"
                                       "    skip_existing: all\n", model="q0.k")
    check("Q-2 skip_existing 로 다시 돌리면 중복을 만들지 않는다(%d 그대로)" % n1, rc == 0 and len(b2) == n1, len(b2))
    rc, out, b3 = contact_run(d, "q2", "  - action: detect\n    scope: all\n    contact_type: tied\n    auto_create: true\n"
                                       "    subtract_existing: true\n", model="q0.k")
    check("Q-3 subtract_existing 가 묶인 세그먼트를 빼 새 접촉을 만들지 않는다", rc == 0 and len(b3) == n1,
          "%d 블록 · %s" % (len(b3), out[-200:]))

    print("[R optimize 는 파서가 찾은 Card A 를 고친다]")
    deck(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK\n" + C123 + card4 +
         "\n         1       0.1         0       0.0         1\n")
    open(os.path.join(d, "r0.yaml"), "w").write(
        "model: m.k\noutput: r0.k\noptimize: rubber\npids: [1]\nanalysis_type: explicit\n")
    rc, out = run(d, "optimize", "r0.yaml")
    b = cblocks(os.path.join(d, "r0.k"))
    check("R-1 Card 4(OPTION 2)를 Card A 로 고치지 않는다", card(b, 0, 3) == card4, repr(card(b, 0, 3)))
    check("R-2 Card A 의 SOFT 1→0 · SBOPT 1→2", fld(card(b, 0, 4), 0) == "0" and fld(card(b, 0, 4), 4) == "2", repr(card(b, 0, 4)))

    print("[S stabilize Lv8 — TIEBREAK 엔 SOFT 2 를 안 쓰고 · MAXPAR 1.15 를 안 쓴다 — D18]")
    deck(d, "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK\n" + C123 + card4 + "\n",
         "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n         2         4         3         3\n       0.2\n       1.0\n")
    open(os.path.join(d, "s0.yaml"), "w").write("model: m.k\noutput: s0.k\nstabilize: explicit\nlevel: 8\n")
    rc, out = run(d, "stabilize", "s0.yaml")
    b = cblocks(os.path.join(d, "s0.k"))
    tb = [x for x in b if "TIEBREAK" in x[0]]
    pl = [x for x in b if "TIEBREAK" not in x[0]]
    tb_soft = fld(tb[0][1][4], 0) if tb and len(tb[0][1]) > 4 else ""
    check("S-1 rc 0 · 접촉 둘", rc == 0 and len(tb) == 1 and len(pl) == 1, out[-300:])
    check("S-2 TIEBREAK 접촉의 Card 4 그대로", tb and len(tb[0][1]) > 3 and tb[0][1][3] == card4, repr(tb[0][1] if tb else tb))
    check("S-3 TIEBREAK 접촉엔 SOFT 2 를 쓰지 않는다", tb_soft in ("", "0", "1"), repr(tb_soft))
    pa = pl[0][1][3] if pl and len(pl[0][1]) > 3 else None
    check("S-4 보통 접촉은 SOFT 2 · MAXPAR 1.15 아님", fld(pa, 0) == "2" and num(fld(pa, 3)) != 1.15, repr(pa))


if __name__ == "__main__":
    sys.exit(main())
