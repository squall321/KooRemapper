#!/usr/bin/env python3
# 세트 합치기(_ADD·_INTERSECT·_COLLECT)를 가리키는 접촉이 modelmeta·contact·optimize 에서 바르게 풀리는가
"""세트 합치기 해석 (2026-10-23).

왜 이 시험이 있나.

  사용자 질문 「파트간의 컨택 관계로 그래프를 그리는게 가능한지」를 재다가, 연결도가 **조용히 틀리는**
  자리를 둘 찾았다(실측).
    · `*SET_PART_ADD` 를 가리키는 접촉 → 파트쌍 0개 · `unresolved_sides` 0. 파서가 `_ADD` 의 멤버(세트 ID)를
      개체로 오인하지 않으려고 `ids` 를 비워 두는데, 소비자가 그 빈 목록을 "멤버 없음" 으로 읽었다.
    · `*SET_SEGMENT_ADD` 는 더 나빴다 — SEGMENT 분기가 방언 검사보다 앞이라 멤버 **세트 ID 를 절점 번호로**
      읽었다. 정답 (1,3) 대신 (2,3) 을 냈다.
  같은 조회를 contact(면 모으기 · 세그먼트 펼치기 · 기존 TIED 판정)와 optimize(대상 파트 판정)도 따로 했다.
  지금은 정본 해석기 하나(`src/commands/set_members.h`)가 푼다. 규칙은 Vol_I `*SET_PART_ADD`(PSID 음수 =
  앞 칸부터의 범위 · 없는 세트는 무시)와 `*SET` COLLECT(모두 COLLECT 일 때만 합친다)다.

usage: test_set_add_resolution.py <KooRemapper 바이너리>
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILS = []


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:400]) if detail else ""))


def base_deck():
    """파트 넷 — 단위 사각 셸 하나씩, z = 0.05·pid 로 층을 쌓는다(절점 4p-3 … 4p 가 파트 p 의 것)."""
    lines = ["*KEYWORD", "*NODE"]
    for p in range(1, 5):
        for k, (x, y) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
            nid = 4 * (p - 1) + k + 1
            lines.append("%8d%16.4f%16.4f%16.4f" % (nid, x, y, 0.05 * p))
    lines.append("*ELEMENT_SHELL")
    for p in range(1, 5):
        n = [4 * (p - 1) + k + 1 for k in range(4)]
        lines.append("%8d%8d%8d%8d%8d%8d" % (p, p, n[0], n[1], n[2], n[3]))
    lines += ["*SECTION_SHELL", "         1", "       0.1",
              "*MAT_ELASTIC", "         1   7.85e-9  210000.0       0.3"]
    for p in range(1, 5):
        lines += ["*PART", "part%d" % p, "%10d%10d%10d" % (p, 1, 1)]
    return "\n".join(lines) + "\n"


def contact(title, ssid, msid, sstyp, mstyp, card_a=False, tied=False, cid=1):
    # ★`_ID` 꼴이다 — LS-DYNA `*CONTACT_*` 에는 `_TITLE` 옵션이 없다(info --strict 가 「망가진 카드」 로 잡는다).
    #   ID 카드는 CID(1~10칸) + 제목(11~80칸).
    kw = "*CONTACT_TIED_SURFACE_TO_SURFACE_ID" if tied else "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID"
    out = ("%s\n%10d%s\n%10d%10d%10d%10d         0         0         0         0\n"
           "       0.2       0.1       0.0       0.0       0.0         0       0.0  1.00E+20\n"
           "       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0\n"
           % (kw, cid, title, ssid, msid, sstyp, mstyp))
    if card_a:
        out += "         1       0.1         0      1.03       1.0         2        10         1\n"
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: test_set_add_resolution.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    d = tempfile.mkdtemp(prefix="setadd_")
    base = base_deck()

    def write(name, cards):
        p = os.path.join(d, name)
        open(p, "w", newline="\n").write(base + cards + "*END\n")
        return p

    def modelmeta(name, cards):
        write(name + ".k", cards)
        open(os.path.join(d, name + ".yaml"), "w").write("model: %s.k\noutput: %s\n" % (name, name))
        r = subprocess.run([binary, "modelmeta", name + ".yaml"], cwd=d,
                           capture_output=True, text=True, timeout=300)
        jp = os.path.join(d, name + "_modelmeta.json")
        if not os.path.exists(jp):
            return None, r.stdout + r.stderr
        return json.load(open(jp))["connectivity"], r.stdout + r.stderr

    def pairs(conn, _title=None):
        # 쌍은 접촉 순번(0 — 덱마다 접촉이 하나다)으로 고른다. 제목으로 고르면 세트 해석 시험이 `_ID` 제목 파싱에
        # 묶인다 — 그것은 A-1 의 제목 항목이 따로 잰다.
        return sorted((e["a"], e["b"]) for e in conn["contact_edges"] if e.get("contact") == 0)

    print("[A modelmeta — 세트를 가리키는 접촉의 파트쌍]")
    cases = [
        ("A-1 *SET_PART_ADD = {10:{1,2}, 11:{4}} ↔ 파트 3",
         "*SET_PART_LIST\n        10\n         1         2\n*SET_PART_LIST\n        11\n         4\n"
         "*SET_PART_ADD\n        20\n        10        11\n" + contact("T", 20, 3, 2, 3),
         [(1, 3), (2, 3), (3, 4)]),
        ("A-2 *SET_PART_ADD 의 음수 = 앞 칸부터의 범위(10 -12 → 10·11·12, 13 은 범위 밖)",
         "*SET_PART_LIST\n        10\n         1\n*SET_PART_LIST\n        11\n         2\n"
         "*SET_PART_LIST\n        12\n         4\n*SET_PART_LIST\n        13\n         3\n"
         "*SET_PART_ADD\n        20\n        10       -12\n" + contact("T", 20, 3, 2, 3),
         [(1, 3), (2, 3), (3, 4)]),
        ("A-3 *SET_PART_ADD 안의 *SET_PART_ADD",
         "*SET_PART_LIST\n        10\n         1\n*SET_PART_ADD\n        20\n        10\n"
         "*SET_PART_LIST\n        11\n         2\n*SET_PART_ADD\n        30\n        20        11\n"
         + contact("T", 30, 3, 2, 3),
         [(1, 3), (2, 3)]),
        ("A-4 *SET_PART_INTERSECT = {1,2} ∩ {2,4} ↔ 파트 3",
         "*SET_PART_LIST\n        10\n         1         2\n*SET_PART_LIST\n        11\n         2         4\n"
         "*SET_PART_INTERSECT\n        20\n        10        11\n" + contact("T", 20, 3, 2, 3),
         [(2, 3)]),
        ("A-5 *SET_PART_LIST_COLLECT 둘(같은 SID)을 합친다",
         "*SET_PART_LIST_COLLECT\n        10\n         1\n*SET_PART_LIST_COLLECT\n        10\n         2\n"
         + contact("T", 10, 3, 2, 3),
         [(1, 3), (2, 3)]),
        ("A-6 *SET_SEGMENT_ADD — 멤버를 절점으로 읽지 않는다(정답 (1,3), 예전 답 (2,3))",
         "*SET_SEGMENT\n        10\n         1         2         3         4\n"
         "*SET_SEGMENT_ADD\n        20\n        10         6\n" + contact("T", 20, 3, 0, 3),
         [(1, 3)]),
        ("A-7 *SET_NODE_ADD — 절점 세트를 합쳐 소유 파트로",
         "*SET_NODE_LIST\n        10\n         1         2\n*SET_NODE_LIST\n        11\n         5\n"
         "*SET_NODE_ADD\n        20\n        10        11\n" + contact("T", 20, 3, 4, 3),
         [(1, 3), (2, 3)]),
        ("A-8 평범한 *SET_PART_LIST 는 그대로(대조)",
         "*SET_PART_LIST\n        10\n         1         2\n" + contact("T", 10, 3, 2, 3),
         [(1, 3), (2, 3)]),
    ]
    for i, (name, cards, want) in enumerate(cases):
        conn, out = modelmeta("a%d" % i, cards)
        if conn is None:
            check(name, False, out[-300:])
            continue
        got = pairs(conn, "T")
        check(name, got == want, "쌍=%r 기대 %r" % (got, want))
        if i == 0:
            # `_ID` 카드는 칸대로 가른다 — 예전엔 제목이 `1T` 처럼 CID 와 붙어 나왔다
            e0 = conn["contact_edges"][0] if conn["contact_edges"] else {}
            check("   A-1 _ID 카드의 제목은 CID 와 갈라 나온다 · cid 1", e0.get("title") == "T" and e0.get("cid") == 1, e0)
        check("   " + name.split()[0] + " 미해석 0", conn["unresolved_sides"] == 0,
              conn.get("unresolved_detail"))

    print("[B 못 푸는 것은 **못 풀었다고** 센다 — 0쌍으로 조용히 사라지지 않는다]")
    unresolved = [
        ("B-1 *SET_PART_LIST_GENERAL(옵션 코드)",
         "*SET_PART_LIST_GENERAL\n        20\n       ALL\n" + contact("T", 20, 3, 2, 3), "GENERAL"),
        ("B-2 순환 — 20 ⊃ 30 ⊃ 20",
         "*SET_PART_ADD\n        20\n        30\n*SET_PART_ADD\n        30\n        20\n"
         + contact("T", 20, 3, 2, 3), "순환"),
        ("B-3 COLLECT 가 아닌 같은 SID 정의가 둘",
         "*SET_PART_LIST\n        10\n         1\n*SET_PART_LIST\n        10\n         2\n"
         + contact("T", 10, 3, 2, 3), "COLLECT"),
        ("B-4 없는 세트", contact("T", 77, 3, 2, 3), "없다"),
    ]
    for i, (name, cards, why) in enumerate(unresolved):
        conn, out = modelmeta("b%d" % i, cards)
        if conn is None:
            check(name, False, out[-300:])
            continue
        det = conn.get("unresolved_detail") or []
        check(name, conn["unresolved_sides"] == 1 and len(det) == 1 and why in det[0].get("why", ""),
              "unresolved=%r detail=%r" % (conn["unresolved_sides"], det))
        check("   " + name.split()[0] + " 파트쌍 0", pairs(conn, "T") == [], pairs(conn, "T"))
        check("   " + name.split()[0] + " 콘솔도 까닭을 말한다", why in out, out[-300:])

    add_sets = ("*SET_PART_LIST\n        10\n         1\n*SET_PART_LIST\n        11\n         2\n"
                "*SET_PART_ADD\n        20\n        10        11\n")

    print("[C contact — 목록 · 세그먼트로 바꾸기 · 기존 TIED 판정]")
    write("c0.k", add_sets + contact("ADD_side", 20, 3, 2, 3))
    open(os.path.join(d, "c0.yaml"), "w").write("model: c0.k\n\ncontacts:\n  - action: analyze\n")
    r = subprocess.run([binary, "contact", "c0.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    m = re.search(r"^\s+SET_PART_ADD\s+20:\s*(.*)$", out, re.M)
    check("C-1 세트 목록이 ADD 를 풀어 보인다(멤버 세트 [10, 11] → [1, 2])",
          bool(m) and "[10, 11]" in m.group(1) and "[1, 2]" in m.group(1), m.group(1) if m else out[-300:])
    check("   C-1 접촉의 슬레이브 멤버도 [1, 2]", re.search(r"Slave:\s+SET_PART 20 .*-> \[1, 2\]", out) is not None,
          out[-400:])

    write("c1.k", add_sets + contact("ADD_side", 20, 3, 2, 3))
    open(os.path.join(d, "c1.yaml"), "w").write(
        "model: c1.k\noutput: c1_out.k\n\ncontacts:\n  - action: convert\n    contact_index: 0\n"
        "    slave_to: segment\n")
    r = subprocess.run([binary, "contact", "c1.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    check("C-2 SET_PART_ADD 슬레이브를 세그먼트로 바꾼다(예전엔 말없이 그대로)",
          re.search(r"Slave SET_PART 20 -> SET_SEGMENT \d+ \(2 faces\)", out) is not None, out[-400:])

    write("c2.k", "*SET_PART_LIST_GENERAL\n        20\n       ALL\n" + contact("GEN_side", 20, 3, 2, 3))
    open(os.path.join(d, "c2.yaml"), "w").write(
        "model: c2.k\noutput: c2_out.k\n\ncontacts:\n  - action: convert\n    contact_index: 0\n"
        "    slave_to: segment\n")
    r = subprocess.run([binary, "contact", "c2.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    check("C-3 못 푸는 세트는 바꾸지 않고 말한다", "슬레이브를 세그먼트로 바꾸지 않는다" in out and "GENERAL" in out,
          out[-400:])

    # 파트 1·2 를 SET_PART_ADD 로 묶은 TIED 가 이미 있다 — detect 가 그 쌍을 다시 만들면 중복 접촉이다.
    write("c3.k", "*SET_PART_LIST\n        10\n         1\n*SET_PART_ADD\n        20\n        10\n"
                  + contact("Tied_1_2", 20, 2, 2, 3, tied=True))
    open(os.path.join(d, "c3.yaml"), "w").write(
        "model: c3.k\noutput: c3_out.k\n\ncontacts:\n  - action: detect\n    scope: all\n"
        "    tolerance: 0.06\n    auto_create: true\n    contact_type: auto\n    skip_existing: tied\n")
    r = subprocess.run([binary, "contact", "c3.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    check("C-4 ADD 로 묶인 기존 TIED 쌍(1,2)을 건너뛴다",
          re.search(r"PID 1 \(part1\) <-> PID 2 \(part2\): skipped \(existing tied\)", out) is not None,
          out[-500:])

    print("[D optimize — 대상 파트가 ADD 세트 안에 있는 접촉]")
    write("d0.k", add_sets + contact("ADD_side", 20, 3, 2, 3, card_a=True))
    open(os.path.join(d, "d0.yaml"), "w").write(
        "model: d0.k\noutput: d0_out.k\noptimize: rubber\npids: [1]\nanalysis_type: explicit\n")
    r = subprocess.run([binary, "optimize", "d0.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    check("D-1 대상 파트 1 이 SET_PART_ADD 20 안에 있다 — 접촉을 다룬다(예전엔 말없이 빠졌다)",
          re.search(r"\[optimize\] CONTACT #0: SBOPT", out) is not None, out[-500:])
    write("d1.k", "*SET_PART_LIST_GENERAL\n        20\n       ALL\n" + contact("GEN_side", 20, 3, 2, 3, card_a=True))
    open(os.path.join(d, "d1.yaml"), "w").write(
        "model: d1.k\noutput: d1_out.k\noptimize: rubber\npids: [1]\nanalysis_type: explicit\n")
    r = subprocess.run([binary, "optimize", "d1.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    check("D-2 풀지 못하는 세트는 건드리지 않고 그 사실을 말한다",
          "세트를 풀지 못해 대상 파트가 드는지 모른다" in out, out[-500:])

    print("[E optimize — `_ID` 접촉의 카드 세기]")
    # ★`_ID` 의 (CID+제목) 줄을 세지 않으면 Card 3 을 Card A 로 알고 SOFT 를 SFSA 칸(슬레이브 강성 배율)에 쓴다.
    write("e0.k", contact("Id_side", 1, 3, 3, 3, card_a=True, cid=7))
    open(os.path.join(d, "e0.yaml"), "w").write(
        "model: e0.k\noutput: e0_out.k\noptimize: rubber\npids: [1]\nanalysis_type: explicit\n")
    r = subprocess.run([binary, "optimize", "e0.yaml"], cwd=d, capture_output=True, text=True, timeout=300)
    blk, on = [], False
    for ln in open(os.path.join(d, "e0_out.k"), errors="replace").read().splitlines():
        if ln.startswith("*CONTACT"):
            on = True
            continue
        if on and ln.startswith("*"):
            break
        if on and ln.strip() and not ln.startswith("$"):
            blk.append(ln)
    card3, card_a = (blk[3] if len(blk) > 3 else ""), (blk[4] if len(blk) > 4 else "")
    check("E-1 Card 3 은 그대로(SFSA 1.0 — 0 이 들어가면 슬레이브 강성이 0 이다)",
          card3[:10].strip() == "1.0", repr(card3))
    check("E-2 SOFT 는 Card A 첫 칸에 0 으로", card_a[:10].strip() == "0", repr(card_a))

    shutil.rmtree(d, ignore_errors=True)
    print()
    if FAILS:
        print("--- 실패 %d건 ---" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
