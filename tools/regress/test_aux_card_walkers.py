#!/usr/bin/env python3
# 보 족(격자 밖) 요소 카드를 걷는 소비자들이 카드 경계 · 칸 자리를 맞게 세는지 보는 회귀 시험(cleanup-nodes · extract-parts)
"""보 족 카드 걷기 (2026-11-07 적대적 검토 뒤 고침).

왜 이 시험이 있나.

  보 · 이산 · 질량 · 안전띠 · 플롯 요소는 격자 리더가 메시에 담지 않는다 — cleanup-nodes 와 extract-parts 가 덱 줄을 직접 걸으며
  카드 경계(`auxElementCard` 의 줄 수)와 칸 자리를 센다. 검토가 그 걸음의 결함을 찾았다.

무엇을 보나.
  A 빈 옵션 카드 — `*ELEMENT_BEAM_ORIENTATION` 의 VX VY VZ 카드를 비워 두면 그 빈 줄이 카드다(LS-PrePost 도 그렇게 읽는다).
    두 걸음이 「카드 밖의 빈 줄」 을 격자 셈으로만 판정해 다음 요소의 Card 1 을 그 카드로 삼켰다 — cleanup-nodes 는 그 요소의
    절점을 지우고(rc 0), extract-parts 는 절점을 놓쳐 되읽기에서 rc 1 로 깨진 산출을 냈다.
  B 보 장치 — `*ELEMENT_BEAM_PULLEY`(PUID BID1 BID2 PNID …) · `*ELEMENT_BEAM_SOURCE`(BSID BSNID BSEID …)는 보 요소가 아니라 PID 칸이
    없는 별개 키워드다. 예전엔 보의 옵션으로 읽어 칸 1 을 PID 로 셌다 — 고른 보에 붙은 도르래를 조용히 버렸다(rc 0). extract-parts 는
    고른 보 요소(BID1 · BID2 · BSEID)를 가리키거나 번호가 0(이웃 보를 스스로 찾는다)인데 고른 파트에 보가 있으면 거절, 그 밖은 버리고 센다.
  C 질량 얹기 — `*ELEMENT_MASS_PART` 는 칸 0 이 PID 다(ID ADDMASS(F16) FINMASS(F16) LCID MWD). 예전엔 질량 카드의 칸 3 을 읽어 고른 파트의
    추가 질량을 버렸다. `_SET` 은 파트 세트를 풀어 다 고른 파트면 싣고 · 하나도 아니면 버리고 · 일부거나 못 풀면 거절한다.
    cleanup-nodes 는 그 줄의 정수(LCID)를 절점으로 세지 않는다.
  D 보 `_ELBOW` 의 가운데 절점 MN(Card 10 · 8칸 표) — 예전엔 Card 1 만 읽어 cleanup-nodes safe 가 MN 을 지우고(rc 0 · 되읽기 0)
    extract-parts 가 싣지 않았다. 이제 다 읽고 renumber 도 그 칸(1-10열)에 새 번호를 쓴다 · 콤마 ELBOW 줄 · MN 칸 안에서 시작하는
    `$` 주석은 renumber 를 거절한다(새 번호가 `$` 를 덮어 주석 글자가 칸 2 의 값이 됐다 — D4)

usage: test_aux_card_walkers.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:400]))
    print("  %-72s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def node(n, x):
    return "%8d%16.6f%16.6f%16.6f" % (n, x, 0.0, 0.0)


def node_ids(path):
    """*NODE 블록의 번호 → x 좌표(이 시험의 절점은 x = 옛 번호)."""
    out, sect = {}, ""
    for ln in open(path, encoding="utf-8").read().split("\n"):
        if ln.startswith("*"):
            sect = ln.split()[0].upper()
        elif sect == "*NODE" and ln.strip() and not ln.startswith("$"):
            out[int(ln[:8])] = int(round(float(ln[8:24])))
    return out


def section_lines(path, kw):
    out, sect = [], ""
    for ln in open(path, encoding="utf-8").read().split("\n"):
        if ln.startswith("*"):
            sect = ln.split()[0].upper().rstrip("%+-")
        elif sect == kw and not ln.startswith("$"):
            out.append(ln)
    return out


def beam_deck(block, nodes=(101, 102, 103, 104, 105)):
    """절점(x = 번호) · 보 블록 · 파트 9(보 단면 · 탄성 재질)."""
    L = ["*KEYWORD", "*NODE"] + [node(n, float(n)) for n in nodes] + block
    L += ["*PART", "cable", "%10d%10d%10d" % (9, 9, 9), "*SECTION_BEAM", "%10d%10d" % (9, 1),
          "*MAT_ELASTIC", "%10d%10s%10s%10s" % (9, "7.85E-9", "210000.", "0.3"), "*END"]
    return "\n".join(L) + "\n"


def dev_deck(extra=""):
    """절점 101-105 · 보 21(101 102) · 22(102 103) 는 파트 9, 보 9(104 105) · 31(105 104) 는 파트 8 · 그 뒤에 `extra`."""
    L = ["*KEYWORD", "*NODE"] + [node(n, float(n)) for n in (101, 102, 103, 104, 105)]
    L += ["*ELEMENT_BEAM", "%8d%8d%8d%8d" % (21, 9, 101, 102), "%8d%8d%8d%8d" % (22, 9, 102, 103),
          "%8d%8d%8d%8d" % (9, 8, 104, 105), "%8d%8d%8d%8d" % (31, 8, 105, 104)]
    L += ["*PART", "cable", "%10d%10d%10d" % (9, 9, 9), "*PART", "other", "%10d%10d%10d" % (8, 9, 9),
          "*SECTION_BEAM", "%10d%10d" % (9, 3), "*MAT_ELASTIC", "%10d%10s%10s%10s" % (9, "7.85E-9", "210000.", "0.3")]
    return "\n".join(L) + "\n" + extra + "*END\n"


def extract(binary, d, tag, deck, parts):
    write(os.path.join(d, tag + ".k"), deck)
    write(os.path.join(d, tag + ".yaml"), "model: %s.k\noutput: %s_out.k\nparts: [%s]\nreport: %s.json\n" %
          (tag, tag, ",".join(map(str, parts)), tag))
    rc, out = run(binary, d, "extract-parts", tag + ".yaml")
    rp = os.path.join(d, tag + ".json")
    rep = json.load(open(rp, encoding="utf-8")) if rc == 0 and os.path.exists(rp) else {}
    return rc, out, rep, os.path.join(d, tag + "_out.k")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="acw_")
    try:
        print("[A 빈 옵션 카드 — `*ELEMENT_BEAM_ORIENTATION` 의 VX VY VZ 를 비운 줄도 카드다]")
        # 보 21(101 · 102) + **빈** Card 2 · 보 22(103 · 104) + 방향 벡터 Card 2. 105 는 아무도 안 쓴다
        blk = ["*ELEMENT_BEAM_ORIENTATION",
               "%8d%8d%8d%8d" % (21, 9, 101, 102), "",
               "%8d%8d%8d%8d" % (22, 9, 103, 104), "%16s%16s%16s" % ("0.0", "1.0", "0.0")]
        write(os.path.join(d, "A.k"), beam_deck(blk))
        write(os.path.join(d, "a.yaml"), "model: A.k\noutput: a_out.k\nmode: safe\nreport: a.json\n")
        rc, out = run(binary, d, "cleanup-nodes", "a.yaml")
        rep = json.load(open(os.path.join(d, "a.json"), encoding="utf-8")) if os.path.exists(os.path.join(d, "a.json")) else {}
        kept = sorted(node_ids(os.path.join(d, "a_out.k")).values()) if rc == 0 else []
        check("A-1 cleanup-nodes safe — rc 0 · ★보 22 의 절점(103 · 104)을 남기고 105 만 지운다",
              rc == 0 and kept == [101, 102, 103, 104] and (rep.get("nodes") or {}).get("deletable") == 1,
              (rc, kept, rep.get("nodes"), out[-300:]))
        write(os.path.join(d, "ax.yaml"), "model: A.k\noutput: ax_out.k\nparts: [9]\nreport: ax.json\n")
        rc, out = run(binary, d, "extract-parts", "ax.yaml")
        rep = json.load(open(os.path.join(d, "ax.json"), encoding="utf-8")) if os.path.exists(os.path.join(d, "ax.json")) else {}
        carried = sorted(node_ids(os.path.join(d, "ax_out.k")).values()) if rc == 0 else []
        check("A-2 extract-parts — rc 0 · ★두 보의 절점 넷을 싣고 되읽기 미정의 0",
              rc == 0 and carried == [101, 102, 103, 104] and (rep.get("verify") or {}).get("undefined_nodes") == 0,
              (rc, carried, rep.get("verify"), out[-300:]))
        rows = section_lines(os.path.join(d, "ax_out.k"), "*ELEMENT_BEAM_ORIENTATION") if rc == 0 else []
        check("A-3 extract-parts — 보 두 장을 빈 카드까지 그대로 실었다(빈 줄을 버리지 않는다)", rows == blk[1:], rows)

        print("[B 보 장치 — *ELEMENT_BEAM_PULLEY · _SOURCE 는 PID 칸이 없다 · 고른 보를 가리키면 거절]")
        pul = lambda b1, b2: "*ELEMENT_BEAM_PULLEY\n" + "%10d%10d%10d%10d%10s" % (1, b1, b2, 103, "0.1") + "\n"
        src = lambda e: "*ELEMENT_BEAM_SOURCE\n" + "%10d%10d%10d%10d%10s" % (1, 101, e, 3, "1.0") + "\n"
        for tag, extra, parts, refuse, what in (
                ("B1", pul(21, 22), (9,), True, "★도르래가 고른 보 21 · 22 를 가리킨다 → rc 1 · 줄을 댄다 · 산출 없음"),
                ("B2", pul(9, 31), (9,), False, "도르래가 안 고른 보(9 · 31)만 가리킨다 — 칸 1(9)을 PID 로 짐작하지 않는다 → rc 0 · 버리고 센다"),
                ("B3", pul(0, 0), (9,), True, "★도르래 보 번호가 0(이웃 보를 스스로 찾는다)이고 고른 파트에 보가 있다 → rc 1"),
                ("B4", src(22), (9,), True, "★공급원(_SOURCE)의 BSEID 가 고른 보 22 다 → rc 1"),
                ("B5", pul(21, 22) + src(22), (8,), False, "보 파트 8 만 고르면 21 · 22 를 가리키는 장치는 버리고 센다 → rc 0")):
            rc, out, rep, outp = extract(binary, d, tag, dev_deck(extra), parts)
            if refuse:
                kwl = [i + 1 for i, l in enumerate(dev_deck(extra).split("\n")) if l.startswith("*ELEMENT_BEAM_")]
                check("%s %s" % (tag, what), rc == 1 and not os.path.exists(outp) and
                      any(("%s.k:%d *ELEMENT_BEAM_" % (tag, n + 1)) in out for n in kwl), (rc, out[-500:]))
            else:
                dk = rep.get("dropped_keywords") or {}
                check("%s %s" % (tag, what), rc == 0 and "*ELEMENT_BEAM_PULLEY" in dk and
                      not section_lines(outp, "*ELEMENT_BEAM_PULLEY"), (rc, dk, out[-400:]))

        print("[C 질량 얹기 — *ELEMENT_MASS_PART 는 칸 0 이 PID · _SET 은 세트를 풀어 견준다]")
        mp = "*ELEMENT_MASS_PART\n" + "%8d%16s%16s%8d%8d" % (9, "0.25", "0.0", 105, 0) + "\n"
        mps = lambda sid: "*ELEMENT_MASS_PART_SET\n" + "%8d%16s%16s%8d%8d" % (sid, "0.5", "0.0", 0, 0) + "\n"
        sets = ("*SET_PART_LIST\n" + "%10d" % 77 + "\n" + "%10d%10d" % (9, 8) + "\n" +
                "*SET_PART_LIST_TITLE\nonly8\n" + "%10d" % 76 + "\n" + "%10d" % 8 + "\n" +
                "*SET_PART_ADD\n" + "%10d" % 78 + "\n" + "%10d" % 77 + "\n")
        rc, out, rep, outp = extract(binary, d, "C1", dev_deck(mp), (9,))
        check("C-1 ★고른 파트 9 의 *ELEMENT_MASS_PART 를 싣는다(예전엔 칸 3 을 PID 로 읽어 버렸다) · 되읽기 0",
              rc == 0 and section_lines(outp, "*ELEMENT_MASS_PART") == [mp.split("\n")[1]] and
              (rep.get("verify") or {}).get("undefined_parts") == 0, (rc, rep.get("verify"), out[-400:]))
        rc, out, rep, outp = extract(binary, d, "C2", dev_deck(mp), (8,))
        check("C-2 안 고른 파트(9)의 질량 얹기는 싣지 않는다", rc == 0 and not section_lines(outp, "*ELEMENT_MASS_PART"),
              (rc, out[-300:]))
        for tag, sid, parts, want, what in (("C3", 77, (9,), "refuse", "★세트 77(9 · 8) 가운데 9 만 고른다 → rc 1 · 줄을 댄다"),
                                            ("C4", 77, (9, 8), "carry", "세트 77 을 다 고르면 질량 얹기와 세트를 싣는다"),
                                            ("C5", 78, (9,), "refuse", "★세트 78 은 *SET_PART_ADD — 풀 수 없다 → rc 1"),
                                            ("C6", 76, (9,), "drop", "세트 76(8 만)은 고른 파트에 닿지 않는다 → 버린다 · rc 0")):
            deck = dev_deck(sets + mps(sid))
            rc, out, rep, outp = extract(binary, d, tag, deck, parts)
            ml = mps(sid).split("\n")[1]
            if want == "refuse":
                n = deck.split("\n").index(ml) + 1
                check("C-%s %s" % (tag[1:], what), rc == 1 and not os.path.exists(outp) and
                      ("%s.k:%d *ELEMENT_MASS_PART_SET" % (tag, n)) in out, (rc, out[-500:]))
            elif want == "carry":
                check("C-%s %s" % (tag[1:], what), rc == 0 and section_lines(outp, "*ELEMENT_MASS_PART_SET") == [ml] and
                      "*SET_PART_LIST" in open(outp, encoding="utf-8").read(), (rc, out[-400:]))
            else:
                check("C-%s %s" % (tag[1:], what), rc == 0 and not section_lines(outp, "*ELEMENT_MASS_PART_SET"), (rc, out[-400:]))
        # cleanup-nodes — 질량 얹기 줄의 정수(LCID 105)는 절점이 아니다(예전엔 모르는 변형이라 줄의 정수를 다 절점으로 남겼다)
        cdeck = dev_deck(mp).replace("%8d%8d%8d%8d\n" % (9, 8, 104, 105), "").replace("%8d%8d%8d%8d\n" % (31, 8, 105, 104), "")
        write(os.path.join(d, "C7.k"), cdeck)
        write(os.path.join(d, "c7.yaml"), "model: C7.k\noutput: c7_out.k\nmode: safe\nreport: c7.json\n")
        rc, out = run(binary, d, "cleanup-nodes", "c7.yaml")
        kept = sorted(node_ids(os.path.join(d, "c7_out.k")).values()) if rc == 0 else []
        check("C-7 cleanup-nodes — 질량 얹기의 LCID(105)를 절점으로 세지 않는다 → 고아 104 · 105 를 지운다",
              rc == 0 and kept == [101, 102, 103], (rc, kept, out[-300:]))

        print("[D 보 _ELBOW 의 가운데 절점 MN(Card 10) — cleanup-nodes · extract-parts · renumber]")
        for tag, kwname, cards in (("D1", "*ELEMENT_BEAM_ELBOW", ["%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103), "%10d" % 104]),
                                   ("D2", "*ELEMENT_BEAM_ORIENTATION_ELBOW",
                                    ["%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103), "%16s%16s%16s" % ("0.0", "1.0", "0.0"), "%10d" % 104])):
            write(os.path.join(d, tag + ".k"), beam_deck([kwname] + cards))
            write(os.path.join(d, tag + "c.yaml"), "model: %s.k\noutput: %sc_out.k\nmode: safe\nreport: %sc.json\n" % (tag, tag, tag))
            rc, out = run(binary, d, "cleanup-nodes", tag + "c.yaml")
            kept = sorted(node_ids(os.path.join(d, tag + "c_out.k")).values()) if rc == 0 else []
            check("%s-1 ★cleanup-nodes safe — %s 의 MN(104)을 남기고 105 만 지운다" % (tag, kwname),
                  rc == 0 and kept == [101, 102, 103, 104], (rc, kept, out[-300:]))
            rc, out, rep, outp = extract(binary, d, tag + "x", beam_deck([kwname] + cards), (9,))
            carried = sorted(node_ids(outp).values()) if rc == 0 else []
            check("%s-2 ★extract-parts — MN(104)까지 싣는다 · 되읽기 0" % tag,
                  rc == 0 and carried == [101, 102, 103, 104] and (rep.get("verify") or {}).get("undefined_nodes") == 0,
                  (rc, carried, rep.get("verify"), out[-300:]))
            write(os.path.join(d, tag + "r.k"), beam_deck([kwname] + cards))
            write(os.path.join(d, tag + "r.yaml"), "model: %sr.k\noutput: %sr_out.k\nparts: [9]\nrenumber: true\nreport: %sr.json\n" % (tag, tag, tag))
            rc, out = run(binary, d, "extract-parts", tag + "r.yaml")
            ids = node_ids(os.path.join(d, tag + "r_out.k")) if rc == 0 else {}
            new = {old: nid for nid, old in ids.items()}
            rows = section_lines(os.path.join(d, tag + "r_out.k"), kwname) if rc == 0 else []
            check("%s-3 ★renumber — MN 칸(1-10열)에 새 번호(%s)를 쓴다 · 되읽기 0" % (tag, new.get(104)),
                  rc == 0 and len(rows) == len(cards) and rows[-1] == "%10d" % new.get(104, -1) and new.get(104) != 104,
                  (rc, rows, out[-300:]))
        write(os.path.join(d, "D3.k"), beam_deck(["*ELEMENT_BEAM_ELBOW", "%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103), "104,0"]))
        write(os.path.join(d, "D3r.yaml"), "model: D3.k\noutput: D3r_out.k\nparts: [9]\nrenumber: true\n")
        rc, out = run(binary, d, "extract-parts", "D3r.yaml")
        check("D3 콤마 ELBOW 줄 — renumber 는 제자리가 없어 거절한다 · 산출 없음",
              rc == 1 and "제자리에 바꿔 쓸 수 없다" in out and not os.path.exists(os.path.join(d, "D3r_out.k")), (rc, out[-300:]))
        # MN 칸(1-10열) 안에서 시작하는 `$` 주석 — 새 번호를 칸에 쓰면 `$` 를 덮어 주석 글자가 칸 2 의 값이 됐다(「         4m」) → 거절.
        # 칸 뒤에서 시작하는 주석은 그대로 두고 번호를 바꾼다
        write(os.path.join(d, "D4.k"), beam_deck(["*ELEMENT_BEAM_ELBOW", "%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103), "     104 $m"]))
        write(os.path.join(d, "D4r.yaml"), "model: D4.k\noutput: D4r_out.k\nparts: [9]\nrenumber: true\n")
        rc, out = run(binary, d, "extract-parts", "D4r.yaml")
        rc2, out2, rep2, outp2 = extract(binary, d, "D4x", beam_deck(["*ELEMENT_BEAM_ELBOW", "%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103),
                                                                       "     104 $m"]), (9,))
        carried = sorted(node_ids(outp2).values()) if rc2 == 0 else []
        check("D4 ★MN 칸 안에서 시작하는 $ 주석 — renumber 거절(주석을 덮지 않는다) · 싣기는 MN 까지",
              rc == 1 and "겹친 $ 주석" in out and not os.path.exists(os.path.join(d, "D4r_out.k")) and rc2 == 0 and
              carried == [101, 102, 103, 104], (rc, out[-300:], rc2, carried))
        write(os.path.join(d, "D5.k"), beam_deck(["*ELEMENT_BEAM_ELBOW", "%8d%8d%8d%8d%8d" % (21, 9, 101, 102, 103), "       104 $ mid node"]))
        write(os.path.join(d, "D5r.yaml"), "model: D5.k\noutput: D5r_out.k\nparts: [9]\nrenumber: true\n")
        rc, out = run(binary, d, "extract-parts", "D5r.yaml")
        rows = section_lines(os.path.join(d, "D5r_out.k"), "*ELEMENT_BEAM_ELBOW") if rc == 0 else []
        ids = node_ids(os.path.join(d, "D5r_out.k")) if rc == 0 else {}
        new = {old: nid for nid, old in ids.items()}
        check("D5 MN 칸 뒤의 주석은 그대로 두고 MN 을 바꾼다",
              rc == 0 and len(rows) == 2 and rows[1] == "%10d $ mid node" % new.get(104, -1), (rc, rows, out[-300:]))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
