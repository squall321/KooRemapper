#!/usr/bin/env python3
# *ELEMENT_SEATBELT 의 N3 · N4(SLEN 이 E16 이라 57-72열)를 모든 소비자가 제자리에서 읽고 쓰는지 보는 회귀 시험
"""`*ELEMENT_SEATBELT` 칸 자리 (2026-11-07).

왜 이 시험이 있나.

  카드는 EID PID N1 N2 SBRID(I8) SLEN(F16) N3 N4(I8)다(Vol_I 160311-160353 — 10칸 표에 아홉 자리, SLEN 이 두 칸).
  공용 판정기(`auxElementCard`)가 그 줄을 정수 폭으로 잘라 칸 6·7(49-64열 — SLEN 의 뒤 절반과 N3)을 절점으로 읽었다.
    · cleanup-nodes `mode: safe` 가 안전띠가 쓰는 N4 를 고아로 **지웠다** — rc 0, 되읽기 검증도 같은 칸을 읽어 0
    · extract-parts 가 N4 를 싣지 않았고, renumber 는 N3 을 49열(SLEN 위)에 썼다
    · 이월 적용의 나눠 쓴 절점 검사가 N4 를 몰랐다
    · restack 의 「지운 절점을 무는 줄」 보고는 10칸으로 잘라 SBRID 를 절점으로 셌다
  칸 자리는 이제 `auxCardFields` · `auxCardCut`(넓은 칸 SLEN 을 따른 자르기)이 정하고 모든 소비자가 그것을 쓴다.
  칸 자리가 없는 줄(콤마 자유형식 · 칸이 어긋난 줄)은 제자리에 번호를 못 바꾸니 renumber 가 거절한다.

무엇을 보나.
  A cleanup-nodes safe — 8칸 · i10 덱에서 N3 · N4 를 남기고 아무도 안 쓰는 절점만 지운다 · 되읽기 미정의 0
  B extract-parts — i10 덱에서 N3 · N4 를 싣고 renumber 가 제자리(67-86열)에 새 번호를 쓴다 · SBRID · SLEN 글자 그대로 ·
    콤마 줄은 그대로 실어 나르되 renumber 는 rc 1 · 산출 없음
  C apply_carryover_plan — 다시 짓는(remesh) PID 의 절점을 N4 로만 쓰는 안전띠 → shared_nodes 로 거절
  D restack — 지운 절점을 N4 로 무는 안전띠 줄은 manual · SBRID 만 같은 번호인 줄은 아니다
  E extract-parts — 안전띠 **장치** 키워드(`*ELEMENT_SEATBELT_RETRACTOR` …)는 PID 칸이 없다 — 칸 1 을 PID 로 짐작해
    「고른 파트를 담았다」 고 거절하지 않는다(싣지 않고 dropped_keywords 에 센다)

usage: test_seatbelt_card_layout.py <KooRemapper 바이너리>
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
CARRY = os.path.join(REPO, "examples", "apply_carryover_plan")
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


def belt(fw, eid, pid, n1, n2, sbrid, slen, n3, n4):
    """매뉴얼 꼴 안전띠 Card 1 — 정수 칸은 fw(8 · i10 이면 10), SLEN 은 16칸."""
    i = "%" + str(fw) + "d"
    return (i * 5) % (eid, pid, n1, n2, sbrid) + "%16s" % slen + (i * 2) % (n3, n4)


def node(fw, n, x):
    return ("%" + str(fw) + "d") % n + "%16.6f%16.6f%16.6f" % (x, 0.0, 0.0)


def belt_deck(fw, belt_line, tail=""):
    """절점 101-105(x = 번호) · 안전띠 한 장(PID 9) · 파트 9. 절점 105 는 아무도 안 쓴다."""
    head = "*KEYWORD I10=Y" if fw == 10 else "*KEYWORD"
    L = [head, "*NODE"] + [node(fw, n, float(n)) for n in (101, 102, 103, 104, 105)]
    L += ["*ELEMENT_SEATBELT", belt_line]
    L += ["*PART", "belt", "%10d%10d%10d" % (9, 9, 9), "*SECTION_SEATBELT", "%10d" % 9,
          "*MAT_SEATBELT", "%10d%10s" % (9, "1.0E-9")]
    return "\n".join(L) + "\n" + tail + "*END\n"


def node_ids(path, fw):
    """*NODE 블록의 번호 → x 좌표(이 시험의 절점은 x = 옛 번호)."""
    out, sect = {}, ""
    for ln in open(path, encoding="utf-8").read().split("\n"):
        if ln.startswith("*"):
            sect = ln.split()[0].upper()
        elif sect == "*NODE" and ln.strip() and not ln.startswith("$"):
            out[int(ln[:fw])] = int(round(float(ln[fw:fw + 16])))
    return out


def section_lines(path, kw):
    out, sect = [], ""
    for ln in open(path, encoding="utf-8").read().split("\n"):
        if ln.startswith("*"):
            sect = ln.split()[0].upper().rstrip("%+-")
        elif sect == kw and ln.strip() and not ln.startswith("$"):
            out.append(ln)
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="sbl_")
    try:
        print("[A cleanup-nodes safe — 안전띠의 N3 · N4 를 남긴다(8칸 · i10)]")
        for fw in (8, 10):
            tag = "A%d" % fw
            line = belt(fw, 13, 9, 101, 102, 0, "0.0", 103, 104)
            write(os.path.join(d, tag + ".k"), belt_deck(fw, line))
            write(os.path.join(d, tag + ".yaml"), "model: %s.k\noutput: %s_out.k\nmode: safe\nreport: %s.json\n" % (tag, tag, tag))
            rc, out = run(binary, d, "cleanup-nodes", tag + ".yaml")
            rep = json.load(open(os.path.join(d, tag + ".json"), encoding="utf-8")) if rc == 0 else {}
            kept = sorted(node_ids(os.path.join(d, tag + "_out.k"), fw).values()) if rc == 0 else []
            check("%s-1 rc 0 · 요소가 쓰는 절점 4(N1 N2 N3 N4) · 지운 것은 105 하나" % tag,
                  rc == 0 and rep["nodes"]["used_by_elements"] == 4 and rep["nodes"]["deletable"] == 1, (rc, rep.get("nodes"), out[-300:]))
            check("%s-2 ★N4(104) · N3(103) 이 산출 덱에 남는다(예전엔 N4 를 지웠다)" % tag, kept == [101, 102, 103, 104], kept)
            check("%s-3 되읽기 검증 — 요소가 가리키는데 없는 절점 0" % tag,
                  rc == 0 and rep["verify"]["undefined_by_elements"] == 0, rep.get("verify"))
        # 되읽기 검증도 N4 를 본다 — N4 가 정의되지 않은 절점(106)이면 세고 rc 1(예전엔 같은 칸을 잘못 읽어 0 · rc 0)
        write(os.path.join(d, "A4.k"), belt_deck(8, belt(8, 13, 9, 101, 102, 0, "0.0", 103, 106)))
        write(os.path.join(d, "A4.yaml"), "model: A4.k\noutput: A4_out.k\nmode: safe\nreport: A4.json\n")
        rc, out = run(binary, d, "cleanup-nodes", "A4.yaml")
        rep = json.load(open(os.path.join(d, "A4.json"), encoding="utf-8")) if os.path.exists(os.path.join(d, "A4.json")) else {}
        check("A-4 ★되읽기 검증이 N4 를 본다 — 정의되지 않은 N4(106)를 세고 rc 1",
              rc == 1 and (rep.get("verify") or {}).get("undefined_by_elements") == 1, (rc, rep.get("verify"), out[-300:]))

        print("[B extract-parts — i10 덱에서 N3 · N4 를 싣고 renumber 가 제자리(67-86열)에 쓴다 · 콤마 줄 renumber 거절]")
        line10 = belt(10, 13, 9, 101, 102, 888, "0.0", 103, 104)
        write(os.path.join(d, "B.k"), belt_deck(10, line10))
        write(os.path.join(d, "b.yaml"), "model: B.k\noutput: b_out.k\nparts: [9]\nrenumber: true\nreport: b.json\n")
        rc, out = run(binary, d, "extract-parts", "b.yaml")
        rep = json.load(open(os.path.join(d, "b.json"), encoding="utf-8")) if os.path.exists(os.path.join(d, "b.json")) else {}
        ok = check("B-1 rc 0 · 되읽기 미정의 0", rc == 0 and (rep.get("verify") or {}).get("undefined_nodes") == 0,
                   (rc, rep.get("verify"), out[-300:]))
        if ok:
            ids = node_ids(os.path.join(d, "b_out.k"), 10)        # 새 번호 → 옛 번호
            new = {old: nid for nid, old in ids.items()}
            check("B-2 ★N3 · N4(103 · 104)를 실었다 — 아무도 안 쓰는 105 는 안 실린다",
                  sorted(ids.values()) == [101, 102, 103, 104], sorted(ids.values()))
            rows = section_lines(os.path.join(d, "b_out.k"), "*ELEMENT_SEATBELT")
            want = (line10[:20] + "%10d%10d" % (new.get(101, -1), new.get(102, -1)) + line10[40:66] +
                    "%10d%10d" % (new.get(103, -1), new.get(104, -1)))
            check("B-3 ★절점 넷이 제자리(21-40 · 67-86열)에서 새 번호 · SBRID(888) · SLEN 글자 그대로",
                  rows == [want] and new.get(104) != 104, (rows, want))
        comma = "13,9,101,102,0,0.0,103,104"
        write(os.path.join(d, "Bc.k"), belt_deck(8, comma))
        write(os.path.join(d, "bc.yaml"), "model: Bc.k\noutput: bc_out.k\nparts: [9]\n")
        rc, out = run(binary, d, "extract-parts", "bc.yaml")
        kept = sorted(node_ids(os.path.join(d, "bc_out.k"), 8).values()) if rc == 0 else []
        check("B-4 콤마 줄도 칸 차례로 읽어 N1-N4 를 싣는다(번호를 안 바꾸면 줄은 그대로)",
              rc == 0 and kept == [101, 102, 103, 104] and section_lines(os.path.join(d, "bc_out.k"), "*ELEMENT_SEATBELT") == [comma],
              (rc, kept, out[-300:]))
        write(os.path.join(d, "bcr.yaml"), "model: Bc.k\noutput: bcr_out.k\nparts: [9]\nrenumber: true\n")
        rc, out = run(binary, d, "extract-parts", "bcr.yaml")
        check("B-5 ★콤마 줄 renumber — 칸 자리가 없어 제자리에 못 쓴다 → rc 1 · 산출 없음",
              rc == 1 and "칸 자리가 없다" in out and not os.path.exists(os.path.join(d, "bcr_out.k")), (rc, out[-400:]))

        print("[C apply_carryover_plan — 다시 짓는 PID 의 절점을 N4 로만 쓰는 안전띠 → shared_nodes]")
        dc = os.path.join(d, "carry")
        shutil.copytree(CARRY, dc)
        text = open(os.path.join(dc, "deck.k"), encoding="utf-8").read()
        users, kw = {}, ""
        for ln in text.split("\n"):
            if ln.startswith("*"):
                kw = ln.split()[0].upper()
            elif kw in ("*ELEMENT_SOLID", "*ELEMENT_SHELL") and ln.strip() and not ln.startswith("$"):
                f = [int(ln[i:i + 8]) for i in range(0, len(ln), 8) if ln[i:i + 8].strip()]
                for n in f[2:]:
                    if n:
                        users.setdefault(n, set()).add(f[1])
        keep = sorted(n for n, ps in users.items() if ps == {1})      # 그대로 두는 PID 1 만 쓰는 절점
        rem = sorted(n for n, ps in users.items() if ps == {4})       # 다시 짓는 PID 4 만 쓰는 절점
        assert len(keep) >= 3 and rem, (len(keep), len(rem))
        line = belt(8, 95501, 20, keep[0], keep[1], 0, "0.0", keep[2], rem[0])
        assert text.rstrip().endswith("*END")
        text = text.rstrip()[:-4] + "*PART\nbelt\n%10d%10d%10d\n*ELEMENT_SEATBELT\n%s\n*END\n" % (20, 1, 1, line)
        write(os.path.join(dc, "deck.k"), text)
        plan = json.load(open(os.path.join(dc, "plan.json"), encoding="utf-8"))
        plan["deck"]["sha256"] = hashlib.sha256(open(os.path.join(dc, "deck.k"), "rb").read()).hexdigest()
        write(os.path.join(dc, "plan.json"), json.dumps(plan, ensure_ascii=False, indent=1))
        write(os.path.join(dc, "run.yaml"), "model: deck.k\nplan: plan.json\noutput: out.k\n")
        rc, out = run(binary, dc, "apply_carryover_plan", "run.yaml")
        rp = os.path.join(dc, "out_carryover.json")
        rep = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
        hits = [p for p in (rep.get("problems") or []) if p.get("pid") == 4 and p.get("kind") == "shared_nodes"]
        check("C-1 ★rc 1 · PID 4 shared_nodes — 상대가 *ELEMENT_SEATBELT 이고 그 절점이 N4(%d)다" % rem[0],
              rc == 1 and hits and "*ELEMENT_SEATBELT" in hits[0].get("detail", "") and str(rem[0]) in hits[0].get("detail", ""),
              (rc, rep.get("problems"), out[-300:]))
        check("C-2 거절하면 덱을 쓰지 않는다", not os.path.exists(os.path.join(dc, "out.k")), "out.k 가 있다")

        print("[D restack — 지운 절점을 N4 로 무는 안전띠 줄은 manual · SBRID 만 같은 번호인 줄은 아니다]")
        rows, n = [], 500001
        for z in (0.0, 2.5, 5.0):
            for y in (0.0, 10.0):
                for x in (0.0, 10.0):
                    rows.append("%8d%16.6f%16.6f%16.6f" % (n, x, y, z))
                    n += 1
        el = ["*ELEMENT_SOLID"]
        for k in range(2):
            b0 = 500001 + 4 * k
            nn = [b0, b0 + 1, b0 + 3, b0 + 2, b0 + 4, b0 + 5, b0 + 7, b0 + 6]
            el.append("%8d%8d" % (k + 1, 1) + "".join("%8d" % v for v in nn))
        # 가운데 면(z = 2.5 · 500005-500008)은 층을 다시 쌓으면 지워진다
        belts = ["*ELEMENT_SEATBELT", belt(8, 9101, 3, 500001, 500002, 0, "0.0", 500003, 500006),
                 belt(8, 9102, 3, 500001, 500002, 500007, "0.0", 500003, 500004)]
        deck = ("*KEYWORD\n*NODE\n" + "\n".join(rows) + "\n" + "\n".join(el) + "\n"
                "*PART\nSTACK\n         1         1         1\n*PART\nbelt\n         3         3         1\n"
                "*SECTION_SOLID\n         1         1\n*SECTION_SEATBELT\n         3\n"
                "*MAT_ELASTIC\n         1  7.85e-09    210000       0.3\n" + "\n".join(belts) + "\n*END\n")
        write(os.path.join(d, "D.k"), deck)
        mat = "      *MAT_ELASTIC_TITLE\n      %s\n      $#     mid        ro         e        pr\n              %d  7.85e-09   2.1e+05      0.30\n"
        write(os.path.join(d, "d.yaml"),
              "model: D.k\noutput: d_out.k\ntarget_pid: 1\ndirection: z\npid_refs: warn\nlayers:\n"
              "  - title: L1\n    thickness: 1.6\n    num_elements: 1\n    material_card: |\n" + mat % ("L1", 90) +
              "  - title: L2\n    thickness: 1.7\n    num_elements: 1\n    material_card: |\n" + mat % ("L2", 91))
        rc, out = run(binary, d, "restack", "d.yaml")
        found = [l for l in out.splitlines() if "*ELEMENT_SEATBELT (manual)" in l]
        lines = deck.split("\n")
        l9101 = next(i for i, l in enumerate(lines) if l.startswith("    9101")) + 1
        l9102 = next(i for i, l in enumerate(lines) if l.startswith("    9102")) + 1
        check("D-1 rc 0 · ★N4 가 지운 절점(500006)인 줄(%d)을 manual 로 올린다" % l9101,
              rc == 0 and any(re.search(r"line %d \*ELEMENT_SEATBELT \(manual\)" % l9101, l) for l in found), (rc, found, out[-400:]))
        check("D-2 ★SBRID 만 지운 절점과 같은 번호(500007)인 줄(%d)은 올리지 않는다 — 절점 칸이 아니다" % l9102,
              not any("line %d " % l9102 in l for l in found), found)

        print("[E extract-parts — 안전띠 장치 키워드는 PID 칸이 없다 · 칸 1 을 PID 로 짐작해 거절하지 않는다]")
        # *ELEMENT_SEATBELT_RETRACTOR Card 1 = SBRID SBRNID SBID SID1-4 DSID (I10 · Vol_I 160931). SBRID 10009 를 8칸으로 자르면
        # 칸 1 이 「09」 — 예전엔 그것을 PID 9 로 읽어 PID 9 를 뽑으면 「고른 파트를 담았다」 고 거절했다.
        retr = ("*ELEMENT_SEATBELT_RETRACTOR\n" + "%10d%10d%10d" % (10009, 101, 13) + "\n" +
                "%10s%10s%10d%10d%10s" % ("0.0", "0.0", 0, 0, "0.0") + "\n")
        write(os.path.join(d, "E.k"), belt_deck(8, belt(8, 13, 9, 101, 102, 10009, "0.0", 103, 104), tail=retr))
        write(os.path.join(d, "e.yaml"), "model: E.k\noutput: e_out.k\nparts: [9]\nreport: e.json\n")
        rc, out = run(binary, d, "extract-parts", "e.yaml")
        rep = json.load(open(os.path.join(d, "e.json"), encoding="utf-8")) if rc == 0 else {}
        check("E-1 ★rc 0 — 장치 키워드를 「PID 9 를 담았다」 고 거절하지 않는다",
              rc == 0 and "*ELEMENT_SEATBELT_RETRACTOR" in (rep.get("dropped_keywords") or {}), (rc, rep.get("dropped_keywords"), out[-400:]))
        check("E-2 안전띠 요소(PID 9)는 실었다 — 장치 키워드는 싣지 않는다(칸 자리를 모른다)",
              rc == 0 and len(section_lines(os.path.join(d, "e_out.k"), "*ELEMENT_SEATBELT")) == 1 and
              "*ELEMENT_SEATBELT_RETRACTOR" not in open(os.path.join(d, "e_out.k"), encoding="utf-8").read(), out[-300:])
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
