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
  칸 자리는 이제 공용 판정기의 읽기들(`auxCardReadings` — 설명서 칸 · 정수 폭)이 정하고 모든 소비자가 그것을 쓴다.
  칸 자리가 없는 줄(콤마 자유형식 · 쓰는 칸 안에 빈칸이 낀 줄)은 제자리에 번호를 못 바꾸니 renumber 가 거절한다.
  줄을 정수 폭으로 써서 두 읽기가 갈리면(SLEN 8칸) 지키는 쪽은 **둘 다** 남기고 renumber 는 거절한다(사용자 결정 2026-11-07 —
  3ce0c4c 는 설명서 칸 자르기에 칸 안 공백이 없으면 그것만 믿어, 빈 SLEN 을 8칸에 쓴 줄의 진짜 N3 을 지웠다).

무엇을 보나.
  A cleanup-nodes safe — 8칸 · i10 덱에서 N3 · N4 를 남기고 아무도 안 쓰는 절점만 지운다 · 되읽기 미정의 0
  B extract-parts — i10 덱에서 N3 · N4 를 싣고 renumber 가 제자리(67-86열)에 새 번호를 쓴다 · SBRID · SLEN 글자 그대로 ·
    콤마 줄은 그대로 실어 나르되 renumber 는 rc 1 · 산출 없음
  C apply_carryover_plan — 다시 짓는(remesh) PID 의 절점을 N4 로만 쓰는 안전띠 → shared_nodes 로 거절
  D restack — 지운 절점을 N4 로 무는 안전띠 줄은 manual · SBRID 만 같은 번호인 줄은 아니다
  E extract-parts — 안전띠 **장치** 키워드(`*ELEMENT_SEATBELT_RETRACTOR` …)는 PID 칸이 없어 고른 띠에 붙었는지 증명할 수 없다.
    고른 파트에 `*ELEMENT_SEATBELT` 가 있으면 **거절**한다(rc 1 · 산출 없음 · 장치 키워드와 줄을 댄다). 안전띠를 고르지 않았으면
    싣지 않고 dropped_keywords 에 센다 — 칸 1 을 PID 로 짐작하지 않는다(그 조각이 고른 PID 와 같아도 거절하지 않는다).
    가속도계(`_ACCELEROMETER`)는 거절하지 않고 dropped_keywords 에 센다 · 데이터 줄 없는 장치 블록은 장치가 아니다(사용자 결정 11-07).
    따라가지 않는 파일 인클루드(`*INCLUDE_TRANSFORM` …)의 안은 못 보니 거절한다 — 띠를 고르지 않아도(재검토 N2) · `*INCLUDE_PATH` 는
    탐색 경로라 아니다
  F 두 가지로 읽히는 줄(정수 폭으로 쓴 안전띠 · 질량 줄) — cleanup-nodes · extract-parts 는 두 읽기의 절점을 다 지킨다 ·
    renumber 는 다른 읽기의 절점이 덱에 있으면 거절(줄을 댄다 · 산출 없음) · 설명서대로 쓴 줄(빈 SLEN · 빈 SBRID · 소수점 · E/D 지수 ·
    왼쪽 맞춤 · 꼬리 주석)은 renumber 가 그대로 된다 · restack 은 어느 읽기로든 지운 절점을 물면 올린다 · 질량 PID 가 읽기마다
    갈리고 그 하나를 고르면 extract-parts 가 거절 · 이월 적용의 aux_in_part 도 PID 후보 전부를 본다
  G 다른 읽기의 규칙(재검토 R1 · R2 · R6 뒤 사용자 결정) — 정수 폭 읽기는 칸이 다 깨끗하고 칸 꼴이 맞고 · 줄이 카드 폭 안에서 끝나고
    (꼬리 $ 주석 빼고) · 안전띠면 N3 ⟺ N4 · 질량이면 MASS 가 있을 때만 든다. 설명서 꼴 줄(두 절점 띠의 정수꼴 SLEN · 네 절점 띠의
    정수꼴 SLEN · i10 왼쪽 맞춤 · PID 없는 정수꼴 질량)은 유령 절점이 없고 renumber 가 되고 rebind · 이월 적용이 거절하지 않는다.
    첫 검토의 깨진 꼴((a)(b)(c) · 「0.5」 · N3 만)은 절점을 다 지키고 renumber 를 거절한다. 번호 칸에 겹친 $ 주석은 renumber 를 거절한다
  H 고정폭 줄은 늘 설명서 칸(2026-11-08 재검토) — 카드 폭 뒤 글자(「belt left 1」 · 「mass on lid」)나 SLEN · MASS 칸 안 빈칸이 있어도
    공백 토큰이 설명서 칸을 갈음하지 않는다: cleanup-nodes 가 N3 을 지우지 않고 · extract-parts 가 싣고 · renumber 가 되고 · 질량이
    버려지지 않는다. 같은 읽기를 쓰는 이월 적용(나눠 쓴 절점) · restack(지운 절점 보고) · rebind(질량 PID)도. 갈리는 줄의 한 읽기만
    말하는 번호가 덱에 없으면(정수 폭 i10 줄의 설명서 칸 조각) 되읽기가 미정의로 세지 않는다
  I 규칙 (e)(2026-11-08 재검토) — 칸마다 맞춤이 다른 설명서 꼴 i10 줄은 정수 폭 읽기가 다른 읽기가 아니다(고아 10 을 지우고 renumber 가
    된다) · 정수 폭으로 고르게 쓴 줄(오른쪽 맞춤 · `%7d `)은 그대로 두 읽기를 다 지키고 renumber 를 거절한다

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


def belt_deck(fw, belt_line, tail="", nodes=(101, 102, 103, 104, 105)):
    """절점 101-105(x = 번호) · 안전띠 한 장(PID 9) · 파트 9. 절점 105 는 아무도 안 쓴다."""
    head = "*KEYWORD I10=Y" if fw == 10 else "*KEYWORD"
    L = [head, "*NODE"] + [node(fw, n, float(n)) for n in nodes]
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

        print("[E extract-parts — 안전띠 장치 키워드: 띠를 고르면 거절 · 안 고르면 dropped_keywords · 칸 1 을 PID 로 짐작하지 않는다]")
        # *ELEMENT_SEATBELT_RETRACTOR Card 1 = SBRID SBRNID SBID SID1-4 DSID (I10 · Vol_I 160931). SBRID 10008 을 8칸으로 자르면
        # 칸 1 이 「08」 — 예전엔 그것을 PID 8 로 읽어, 보 파트 8 을 뽑으면 「고른 파트를 담았다」 고 거절했다(띠와 상관없이).
        retr = ("*ELEMENT_SEATBELT_RETRACTOR\n" + "%10d%10d%10d" % (10008, 101, 13) + "\n" +
                "%10s%10s%10d%10d%10s" % ("0.0", "0.0", 0, 0, "0.0") + "\n")
        beam = ("*ELEMENT_BEAM\n" + "%8d%8d%8d%8d" % (20, 8, 101, 102) + "\n*PART\nbeam\n" + "%10d%10d%10d" % (8, 8, 8) +
                "\n*SECTION_BEAM\n" + "%10d%10d" % (8, 1) + "\n*MAT_ELASTIC\n" + "%10d%10s%10s%10s" % (8, "7.85E-9", "210000.", "0.3") + "\n")
        edeck = belt_deck(8, belt(8, 13, 9, 101, 102, 10008, "0.0", 103, 104), tail=beam + retr)
        write(os.path.join(d, "E.k"), edeck)
        rline = edeck.split("\n").index("*ELEMENT_SEATBELT_RETRACTOR") + 1
        # (1) 안전띠(PID 9)를 고른다 — 장치가 그 띠에 붙었는지 증명할 수 없다 → 거절
        write(os.path.join(d, "e1.yaml"), "model: E.k\noutput: e1_out.k\nparts: [9]\nreport: e1.json\n")
        rc, out = run(binary, d, "extract-parts", "e1.yaml")
        check("E-1 ★띠를 고르면 거절 — rc 1 · 산출 없음 · 장치 키워드와 그 줄(%d)을 댄다" % rline,
              rc == 1 and not os.path.exists(os.path.join(d, "e1_out.k")) and
              re.search(r"E\.k:%d \*ELEMENT_SEATBELT_RETRACTOR" % rline, out) is not None, (rc, out[-500:]))
        # (2) 보 파트 8 만 고른다 — 띠가 없으니 장치는 싣지 않고 센다 · 칸 1 의 「08」 을 PID 8 로 짐작하지 않는다
        write(os.path.join(d, "e2.yaml"), "model: E.k\noutput: e2_out.k\nparts: [8]\nreport: e2.json\n")
        rc, out = run(binary, d, "extract-parts", "e2.yaml")
        rep = json.load(open(os.path.join(d, "e2.json"), encoding="utf-8")) if rc == 0 else {}
        body = open(os.path.join(d, "e2_out.k"), encoding="utf-8").read() if rc == 0 else ""
        check("E-2 ★띠를 안 고르면 rc 0 — 장치는 dropped_keywords 에 센다(칸 1 을 PID 8 로 짐작해 거절하지 않는다)",
              rc == 0 and "*ELEMENT_SEATBELT_RETRACTOR" in (rep.get("dropped_keywords") or {}), (rc, rep.get("dropped_keywords"), out[-400:]))
        check("E-3 보(PID 8)는 실었고 안전띠 요소 · 장치는 싣지 않았다",
              rc == 0 and len(section_lines(os.path.join(d, "e2_out.k"), "*ELEMENT_BEAM")) == 1 and "*ELEMENT_SEATBELT" not in body,
              body[-400:])

        # 가속도계는 띠와 무관할 수 있다 — 거절 목록에서 뺀다(버리고 dropped_keywords). 데이터 줄 없는 장치 블록은 장치가 아니다
        acc = "*ELEMENT_SEATBELT_ACCELEROMETER\n" + "%10d%10d%10d%10d" % (1, 105, 105, 105) + "\n"
        empty_sensor = "*ELEMENT_SEATBELT_SENSOR\n$ 아직 안 채웠다\n\n"
        sensor = "*ELEMENT_SEATBELT_SENSOR\n" + "%10d%10d%10d%10d" % (1, 1, 13, 0) + "\n"
        ecases = (("E-4", acc, False, "*ELEMENT_SEATBELT_ACCELEROMETER", "★가속도계만 있으면 띠를 골라도 rc 0 — 가속도계는 dropped_keywords"),
                  ("E-5", empty_sensor, False, "*ELEMENT_SEATBELT_SENSOR", "★데이터 줄 없는 장치 블록(빈 _SENSOR)은 세지 않는다 — rc 0"),
                  ("E-6", acc + empty_sensor + sensor, True, "*ELEMENT_SEATBELT_SENSOR", "데이터 줄 있는 _SENSOR 는 그대로 거절 — 그 블록만 댄다(가속도계 · 빈 블록은 아니다)"),
                  ("E-7", "*ELEMENT_SEATBELT_PRETENSIONER\n" + "%10d%10d%10d%10d" % (1, 1, 1, 0) + "\n", True, "*ELEMENT_SEATBELT_PRETENSIONER", "_PRETENSIONER 는 그대로 거절"),
                  ("E-8", "*ELEMENT_SEATBELT_WHATEVER\n" + "%10d" % 1 + "\n", True, "*ELEMENT_SEATBELT_WHATEVER", "모르는 *ELEMENT_SEATBELT_* 도 그대로 거절"))
        for tag, extra, refuse, kwname, what in ecases:
            xdeck = belt_deck(8, belt(8, 13, 9, 101, 102, 0, "0.0", 103, 104), tail=extra)
            y = tag.replace("-", "") + ".yaml"
            write(os.path.join(d, y + ".k"), xdeck)
            write(os.path.join(d, y), "model: %s.k\noutput: %s_out.k\nparts: [9]\nreport: %s.json\n" % (y, y, y))
            rc, out = run(binary, d, "extract-parts", y)
            if refuse:
                kl = [i + 1 for i, l in enumerate(xdeck.split("\n")) if l == kwname]
                listed = re.findall(r"^\s+\S+\.k:(\d+) (\*ELEMENT_SEATBELT_\w+)", out, re.M)
                ok = rc == 1 and not os.path.exists(os.path.join(d, y + "_out.k")) and listed == [(str(n), kwname) for n in kl[-1:]]
                check("%s %s — rc 1 · 줄 %s" % (tag, what, kl[-1:]), ok, (rc, listed, out[-500:]))
            else:
                rep = json.load(open(os.path.join(d, y + ".json"), encoding="utf-8")) if rc == 0 else {}
                ok = rc == 0 and len(section_lines(os.path.join(d, y + "_out.k"), "*ELEMENT_SEATBELT")) == 1 and \
                    kwname in (rep.get("dropped_keywords") or {})
                check("%s %s" % (tag, what), ok, (rc, rep.get("dropped_keywords"), out[-400:]))
        # 따라가지 않는 파일 인클루드 — 그 안의 장치를 못 본다. 띠를 고르면 거절(인클루드 키워드 · 줄을 댄다) · 탐색 경로(_PATH)는 세지 않는다
        retr_file = "*KEYWORD\n*ELEMENT_SEATBELT_RETRACTOR\n" + "%10d%10d%10d" % (10008, 101, 13) + "\n" + \
            "%10s%10s%10d%10d%10s" % ("0.0", "0.0", 0, 0, "0.0") + "\n*END\n"
        write(os.path.join(d, "inc_dev.k"), retr_file)
        os.makedirs(os.path.join(d, "incdir"), exist_ok=True)
        tr = "*INCLUDE_TRANSFORM\ninc_dev.k\n0,0,0,0,0,0,0\n0,0,0,0,0,0,0\n1.0,1.0,1.0,1.0\n0\n"
        icases = (("E-9", belt_deck(8, belt(8, 13, 9, 101, 102, 0, "0.0", 103, 104), tail=tr), "9", True,
                   "★띠를 고르고 *INCLUDE_TRANSFORM(안에 리트랙터)이 있으면 거절 — rc 1 · 인클루드 줄을 댄다"),
                  ("E-10", belt_deck(8, belt(8, 13, 9, 101, 102, 0, "0.0", 103, 104), tail="*INCLUDE_PATH\nincdir\n"), "9", False,
                   "*INCLUDE_PATH(탐색 경로)만 있으면 띠를 골라도 rc 0"),
                  ("E-11", edeck.replace("*END\n", tr + "*END\n"), "8", True,
                   "★띠를 안 골라도 *INCLUDE_TRANSFORM 이 있으면 거절 — 안의 고른 파트를 못 본다(재검토 N2)"))
        for tag, ideck, pick, refuse, what in icases:
            y = tag.replace("-", "") + ".yaml"
            write(os.path.join(d, y + ".k"), ideck)
            write(os.path.join(d, y), "model: %s.k\noutput: %s_out.k\nparts: [%s]\nreport: %s.json\n" % (y, y, pick, y))
            rc, out = run(binary, d, "extract-parts", y)
            if refuse:
                il = ideck.split("\n").index("*INCLUDE_TRANSFORM") + 1
                check("%s %s(%d)" % (tag, what, il),
                      rc == 1 and ("%s.k:%d *INCLUDE_TRANSFORM" % (y, il)) in out and not os.path.exists(os.path.join(d, y + "_out.k")),
                      (rc, out[-500:]))
            else:
                rep = json.load(open(os.path.join(d, y + ".json"), encoding="utf-8")) if rc == 0 else {}
                check("%s %s" % (tag, what), rc == 0 and os.path.exists(os.path.join(d, y + "_out.k")),
                      (rc, rep.get("dropped_keywords"), out[-400:]))

        print("[F 두 가지로 읽히는 줄 — 지키는 쪽은 둘 다 · renumber 는 거절 · 설명서 꼴은 그대로 · 질량 PID]")
        # SLEN 을 8칸에 쓴(빈 SLEN) 줄 — 설명서 칸(SLEN 16)으로 읽으면 SLEN = 「103」 · N3 = 104 · N4 없음, 정수 폭이면 N3 103 · N4 104
        w8 = "%8d%8d%8d%8d%8d%8s%8d%8d" % (13, 9, 101, 102, 0, "", 103, 104)
        write(os.path.join(d, "F1.k"), belt_deck(8, w8))
        write(os.path.join(d, "F1.yaml"), "model: F1.k\noutput: F1_out.k\nmode: safe\nreport: F1.json\n")
        rc, out = run(binary, d, "cleanup-nodes", "F1.yaml")
        kept = sorted(node_ids(os.path.join(d, "F1_out.k"), 8).values()) if rc == 0 else []
        check("F-1 ★cleanup-nodes — 빈 SLEN 을 8칸에 쓴 줄의 두 읽기 절점을 다 남긴다(103 · 104) · 105 만 지운다",
              rc == 0 and kept == [101, 102, 103, 104], (rc, kept, out[-300:]))
        # i10 덱에 SLEN 을 10칸(빈)으로 쓴 줄 — 설명서 칸은 N3(1000003)을 둘로 잘라 「100」 · 「0003」(= 절점 3)을 읽는다
        g2 = "%10d%10d%10d%10d%10d%10s%10d%10d" % (13, 9, 1000001, 1000002, 0, "", 1000003, 42)
        f2nodes = (1000001, 1000002, 1000003, 42, 3, 1000005)
        write(os.path.join(d, "F2.k"), belt_deck(10, g2, nodes=f2nodes))
        write(os.path.join(d, "F2.yaml"), "model: F2.k\noutput: F2_out.k\nmode: safe\nreport: F2.json\n")
        rc, out = run(binary, d, "cleanup-nodes", "F2.yaml")
        kept = sorted(node_ids(os.path.join(d, "F2_out.k"), 10).values()) if rc == 0 else []
        check("F-2 ★cleanup-nodes — i10 줄의 두 읽기(3 · 1000003)를 다 남긴다 · 1000005 만 지운다",
              rc == 0 and kept == [3, 42, 1000001, 1000002, 1000003], (rc, kept, out[-300:]))
        # extract-parts — renumber 없이는 두 읽기의 절점을 다 싣고 줄은 그대로 · renumber 는 줄을 대고 거절(산출 없음)
        write(os.path.join(d, "f3.yaml"), "model: F1.k\noutput: f3_out.k\nparts: [9]\nreport: f3.json\n")
        rc, out = run(binary, d, "extract-parts", "f3.yaml")
        rep = json.load(open(os.path.join(d, "f3.json"), encoding="utf-8")) if rc == 0 else {}
        kept = sorted(node_ids(os.path.join(d, "f3_out.k"), 8).values()) if rc == 0 else []
        check("F-3 ★extract-parts — 두 읽기의 절점(103 · 104)을 다 싣는다 · 줄 그대로 · 되읽기 미정의 0",
              rc == 0 and kept == [101, 102, 103, 104] and section_lines(os.path.join(d, "f3_out.k"), "*ELEMENT_SEATBELT") == [w8] and
              (rep.get("verify") or {}).get("undefined_nodes") == 0, (rc, kept, rep.get("verify"), out[-300:]))
        for tag, deckname, bline in (("F-4", "F1.k", belt_deck(8, w8).split("\n").index(w8) + 1),
                                     ("F-5", "F2.k", belt_deck(10, g2, nodes=f2nodes).split("\n").index(g2) + 1)):
            y = tag.replace("-", "") + "r.yaml"
            write(os.path.join(d, y), "model: %s\noutput: %s_out.k\nparts: [9]\nrenumber: true\nreport: %s.json\n" % (deckname, y, y))
            rc, out = run(binary, d, "extract-parts", y)
            check("%s ★renumber — %s 의 줄이 두 가지로 읽혀 갈린다 → rc 1 · 줄(%s:%d)을 댄다 · 산출 · 보고 없음" % (tag, deckname, deckname, bline),
                  rc == 1 and "갈린다" in out and ("%s:%d *ELEMENT_SEATBELT" % (deckname, bline)) in out and
                  not os.path.exists(os.path.join(d, y + "_out.k")), (rc, out[-500:]))
        # 설명서대로 쓴 줄은 갈리지 않는다 — renumber 가 그대로 된다(절점 넷이 설명서 칸 17-32 · 57-72열에서 새 번호 · 나머지 글자 그대로)
        manual = {
            "빈 SLEN": "%8d%8d%8d%8d%8d%16s%8d%8d" % (13, 9, 101, 102, 0, "", 103, 104),
            "빈 SBRID": "%8d%8d%8d%8d%8s%16s%8d%8d" % (13, 9, 101, 102, "", "0.0", 103, 104),
            "빈 SBRID · SLEN": "%8d%8d%8d%8d%8s%16s%8d%8d" % (13, 9, 101, 102, "", "", 103, 104),
            "소수점": "%8d%8d%8d%8d%8d%16s%8d%8d" % (13, 9, 101, 102, 0, "100.0", 103, 104),
            "E 지수": "%8d%8d%8d%8d%8d%16s%8d%8d" % (13, 9, 101, 102, 0, "-1.234567890E-01", 103, 104),
            "D 지수": "%8d%8d%8d%8d%8d%16s%8d%8d" % (13, 9, 101, 102, 0, "-5.0D+00", 103, 104),
            "왼쪽 맞춤": "%-8d%-8d%-8d%-8d%-8d%-16s%-8d%-8d" % (13, 9, 101, 102, 0, "1.5", 103, 104),
            "꼬리 주석": "%8d%8d%8d%8d%8s%16s%8d%8d" % (13, 9, 101, 102, "", "0.0", 103, 104) + "  $ belt A",
        }
        for k, (name, ml) in enumerate(manual.items()):
            tag = "F6%d" % k
            write(os.path.join(d, tag + ".k"), belt_deck(8, ml))
            write(os.path.join(d, tag + ".yaml"), "model: %s.k\noutput: %s_out.k\nparts: [9]\nrenumber: true\nreport: %s.json\n" % (tag, tag, tag))
            rc, out = run(binary, d, "extract-parts", tag + ".yaml")
            rep = json.load(open(os.path.join(d, tag + ".json"), encoding="utf-8")) if rc == 0 else {}
            ok = rc == 0 and (rep.get("verify") or {}).get("undefined_nodes") == 0
            got = None
            if ok:
                ids = node_ids(os.path.join(d, tag + "_out.k"), 8)
                new = {old: nid for nid, old in ids.items()}
                rows = section_lines(os.path.join(d, tag + "_out.k"), "*ELEMENT_SEATBELT")
                want = (ml[:16] + "%8d%8d" % (new.get(101, -1), new.get(102, -1)) + ml[32:56] +
                        "%8d%8d" % (new.get(103, -1), new.get(104, -1)) + ml[72:])
                got = rows
                ok = sorted(ids.values()) == [101, 102, 103, 104] and rows == [want] and new.get(104) != 104
            check("F-6.%d 설명서 꼴(%s) — renumber rc 0 · 절점 넷이 설명서 칸에서 새 번호 · 나머지 글자 그대로" % (k + 1, name), ok,
                  (rc, got, out[-300:]))
        # 정수꼴 SLEN(「10」 · 절점 10 이 덱에 있다) — 정수 폭 읽기는 SLEN 의 뒤 절반을 N3 = 10 으로 읽지만 N4 가 65-72열에 있어 설명서
        # 꼴이다(정수 폭으로 쓴 줄은 64열에서 끝난다). 다른 읽기가 아니다 — renumber 가 되고 10 은 싣지 않는다(재검토 R1 — 예전엔 넘치게 실었다)
        ml = "%8d%8d%8d%8d%8d%16s%8d%8d" % (13, 9, 101, 102, 0, "10", 103, 104)
        write(os.path.join(d, "F69.k"), belt_deck(8, ml, nodes=(10, 101, 102, 103, 104, 105)))
        write(os.path.join(d, "F69.yaml"), "model: F69.k\noutput: F69_out.k\nparts: [9]\nrenumber: true\nreport: F69.json\n")
        rc, out = run(binary, d, "extract-parts", "F69.yaml")
        rep = json.load(open(os.path.join(d, "F69.json"), encoding="utf-8")) if rc == 0 else {}
        ok, got = rc == 0 and (rep.get("verify") or {}).get("undefined_nodes") == 0, None
        if ok:
            ids = node_ids(os.path.join(d, "F69_out.k"), 8)
            new = {old: nid for nid, old in ids.items()}
            got = section_lines(os.path.join(d, "F69_out.k"), "*ELEMENT_SEATBELT")
            want = (ml[:16] + "%8d%8d" % (new.get(101, -1), new.get(102, -1)) + ml[32:56] + "%8d%8d" % (new.get(103, -1), new.get(104, -1)))
            ok = sorted(ids.values()) == [101, 102, 103, 104] and got == [want]
        check("F-6.9 ★정수꼴 SLEN(「10」 · 절점 10 이 있다) — N4 가 65-72열이라 다른 읽기가 아니다 · renumber rc 0 · 10 은 안 싣는다", ok,
              (rc, got, out[-400:]))
        # restack — 정수 폭 읽기의 N3(500006)이 지운 절점이고 설명서 칸 읽기(SLEN 자리)는 그것을 못 본다 → 어느 읽기로든 물면 manual
        fbelts = ["*ELEMENT_SEATBELT", "%8d%8d%8d%8d%8d%8s%8d%8d" % (9103, 3, 500001, 500002, 0, "", 500006, 500003)]
        fdeck = deck.replace("\n".join(belts), "\n".join(fbelts))
        assert fdeck != deck
        write(os.path.join(d, "F7.k"), fdeck)
        write(os.path.join(d, "f7.yaml"), open(os.path.join(d, "d.yaml"), encoding="utf-8").read()
              .replace("model: D.k", "model: F7.k").replace("output: d_out.k", "output: f7_out.k"))
        rc, out = run(binary, d, "restack", "f7.yaml")
        l9103 = next(i for i, l in enumerate(fdeck.split("\n")) if l.startswith("    9103")) + 1
        check("F-7 ★restack — 정수 폭 읽기만 지운 절점(500006)을 무는 줄(%d)도 manual 로 올린다" % l9103,
              rc == 0 and re.search(r"line %d \*ELEMENT_SEATBELT \(manual\)" % l9103, out) is not None, (rc, out[-500:]))
        # 질량 — 줄이 32열(PID 칸 앞)에서 끝나면 정수 폭으로 쓴 줄일 수 있다: 설명서 칸은 MASS 「1000」 · PID 없음, 정수 폭은 PID 1000.
        # 8칸 MASS 에 8자리 PID 가 붙은 줄도 같다(설명서 칸 MASS 「1.00E-0310000005」 · PID 없음). 그 PID 를 고르면 실을지 버릴지
        # 정할 수 없다 → 거절 · 줄을 댄다. PID 칸(33-40열)까지 쓴 줄은 설명서 꼴이다 — 정수꼴 질량 「1000」 이어도 갈리지 않는다
        mbeam = ("*ELEMENT_BEAM\n" + "%8d%8d%8d%8d" % (20, 7, 101, 102) + "\n" + "%8d%8d%8d%8d" % (21, 1000, 103, 104) + "\n" +
                 "%8d%8d%8d%8d" % (22, 10000005, 103, 104) + "\n"
                 "*PART\nb7\n" + "%10d%10d%10d" % (7, 8, 8) + "\n*PART\nb1000\n" + "%10d%10d%10d" % (1000, 8, 8) +
                 "\n*PART\nb10000005\n" + "%10d%10d%10d" % (10000005, 8, 8) +
                 "\n*SECTION_BEAM\n" + "%10d%10d" % (8, 1) + "\n*MAT_ELASTIC\n" + "%10d%10s%10s%10s" % (8, "7.85E-9", "210000.", "0.3") + "\n")
        mcases = (("F-8", "%8d%8d%16s" % (95001, 105, "1000"), (1000,), None),
                  ("F-9", "%8d%8d%8s%8d" % (95001, 105, "1.00E-03", 10000005), (10000005,), "PID 0(없음) / 10000005"),
                  ("F-10", "%8d%8d%16s%8d" % (95001, 105, "1000", 7), (7,), None),
                  ("F-10b", "%8d%8d%16s%8d" % (95001, 105, "1000", 7), (1000,), None),
                  ("F-10c", "%8d%8d%16s%8d" % (95001, 105, "1.0", 7), (7,), None))
        for tag, ml, picks, said in mcases:
            mdeck = belt_deck(8, belt(8, 13, 9, 101, 102, 0, "0.0", 103, 104), tail=mbeam + "*ELEMENT_MASS\n" + ml + "\n")
            y = tag.replace("-", "") + ".yaml"
            write(os.path.join(d, y + ".k"), mdeck)
            write(os.path.join(d, y), "model: %s.k\noutput: %s_out.k\nparts: [%s]\nreport: %s.json\n" % (y, y, ",".join(map(str, picks)), y))
            rc, out = run(binary, d, "extract-parts", y)
            mline = mdeck.split("\n").index(ml) + 1
            if said:
                check("%s ★질량 PID 가 읽기마다 갈린다(%s) · 그 PID 를 고르면 거절 — rc 1 · 줄(%d)을 댄다 · 산출 없음" % (tag, said, mline),
                      rc == 1 and re.search(r"%s\.k:%d \*ELEMENT_MASS — %s" % (re.escape(y), mline, re.escape(said)), out) is not None and
                      not os.path.exists(os.path.join(d, y + "_out.k")), (rc, out[-500:]))
            else:
                mine = 7 in picks and ml.endswith("%8d" % 7)
                rows = section_lines(os.path.join(d, y + "_out.k"), "*ELEMENT_MASS") if rc == 0 else None
                check("%s 설명서 꼴 질량(%s · PID %s) · %s 를 고른다 — rc 0 · 질량을 %s" %
                      (tag, ml[16:32].strip(), "7" if ml.endswith("%8d" % 7) else "없음", picks[0], "싣는다" if mine else "싣지 않는다"),
                      rc == 0 and rows == ([ml] if mine else []), (rc, rows, out[-400:]))
        # 이월 적용 — 질량 줄의 PID 가 설명서 칸으로 비고(0) 정수 폭으로 4(다시 짓는 PID)면 aux_in_part 로 PID 4 를 거절한다. 정수 폭 읽기가
        # 그렇게 쓴 꼴이어야 한다 — 8칸 MASS(「1.00E-03」)에 8칸 PID(「00000004」)가 붙어 설명서 칸으로도 깨끗한 줄(MASS 가 빈 꼴은 아니다)
        dm = os.path.join(d, "carry_mass")
        shutil.copytree(CARRY, dm)
        text = open(os.path.join(dm, "deck.k"), encoding="utf-8").read()
        text = text.rstrip()[:-4] + "*ELEMENT_MASS\n%8d%8d%8s%8s\n*END\n" % (95601, keep[0], "1.00E-03", "00000004")
        write(os.path.join(dm, "deck.k"), text)
        plan = json.load(open(os.path.join(dm, "plan.json"), encoding="utf-8"))
        plan["deck"]["sha256"] = hashlib.sha256(open(os.path.join(dm, "deck.k"), "rb").read()).hexdigest()
        write(os.path.join(dm, "plan.json"), json.dumps(plan, ensure_ascii=False, indent=1))
        write(os.path.join(dm, "run.yaml"), "model: deck.k\nplan: plan.json\noutput: out.k\n")
        rc, out = run(binary, dm, "apply_carryover_plan", "run.yaml")
        rp = os.path.join(dm, "out_carryover.json")
        rep = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
        hits = [p for p in (rep.get("problems") or []) if p.get("pid") == 4 and p.get("kind") == "aux_in_part"]
        check("F-11 ★apply_carryover_plan — 정수 폭 읽기의 질량 PID(4)도 aux_in_part 로 본다 → rc 1",
              rc == 1 and hits and "*ELEMENT_MASS" in hits[0].get("detail", ""), (rc, rep.get("problems"), out[-300:]))

        print("[G 다른 읽기의 규칙 — 설명서 꼴 줄은 유령 절점 · 거짓 거절이 없다 · 깨진 꼴은 다 지키고 renumber 를 거절한다]")
        # 설명서 꼴 줄 — 정수 폭 읽기가 다른 읽기가 아니다. cleanup-nodes 는 덱의 고아(절점 5 · 10 · 1000)를 지우고, extract-parts 는 띠의
        # 절점만 싣고, renumber 가 된다
        gcases = (("G-1", 8, "%8d%8d%8d%8d%8d%16s" % (13, 9, 101, 102, 0, "10"), (10, 101, 102, 103), [101, 102],
                   "두 절점 띠(N3 · N4 없음)의 정수꼴 SLEN 「10」"),
                  ("G-2", 8, "%8d%8d%8d%8d%8d%16s%8d%8d" % (13, 9, 101, 102, 0, "5", 103, 104), (5, 101, 102, 103, 104), [101, 102, 103, 104],
                   "네 절점 띠의 정수꼴 SLEN 「5」"),
                  ("G-3", 10, ("%-10d%-10d%-10d%-10d%-10d%-16s%-10d%-10d" % (13, 9, 101, 102, 0, "0.0", 1000003, 42)).rstrip(),
                   (42, 101, 102, 1000, 1000003), [42, 101, 102, 1000003], "i10 왼쪽 맞춤(N3 7자리 · N4 2자리)"))
        for tag, fw, gl, gnodes, want, what in gcases:
            gdeck = belt_deck(fw, gl, nodes=gnodes)
            write(os.path.join(d, tag + ".k"), gdeck)
            write(os.path.join(d, tag + "c.yaml"), "model: %s.k\noutput: %sc_out.k\nmode: safe\n" % (tag, tag))
            rc, out = run(binary, d, "cleanup-nodes", tag + "c.yaml")
            kept = sorted(node_ids(os.path.join(d, tag + "c_out.k"), fw).values()) if rc == 0 else None
            check("%s ★cleanup-nodes — %s: 고아(%s)를 지운다 · 띠의 절점만 남긴다" % (tag, what, sorted(set(gnodes) - set(want))),
                  rc == 0 and kept == want, (rc, kept, out[-300:]))
            write(os.path.join(d, tag + "x.yaml"), "model: %s.k\noutput: %sx_out.k\nparts: [9]\nreport: %sx.json\n" % (tag, tag, tag))
            rc, out = run(binary, d, "extract-parts", tag + "x.yaml")
            carried = sorted(node_ids(os.path.join(d, tag + "x_out.k"), fw).values()) if rc == 0 else None
            check("%s ★extract-parts — %s: 띠의 절점만 싣는다(유령 절점이 없다)" % (tag, what), rc == 0 and carried == want, (rc, carried, out[-300:]))
            write(os.path.join(d, tag + "r.yaml"), "model: %s.k\noutput: %sr_out.k\nparts: [9]\nrenumber: true\nreport: %sr.json\n" % (tag, tag, tag))
            rc, out = run(binary, d, "extract-parts", tag + "r.yaml")
            rr = json.load(open(os.path.join(d, tag + "r.json"), encoding="utf-8")) if rc == 0 else {}
            ids = node_ids(os.path.join(d, tag + "r_out.k"), fw) if rc == 0 else {}
            check("%s ★renumber — %s: 거절하지 않는다 · 띠의 절점만 1 부터 · 되읽기 0" % (tag, what),
                  rc == 0 and sorted(ids.values()) == want and sorted(ids) == list(range(1, len(want) + 1)) and
                  (rr.get("verify") or {}).get("undefined_nodes") == 0, (rc, sorted(ids.items()), out[-400:]))
        # 첫 검토의 깨진 꼴 — 절점을 다 지키고(cleanup · 싣기) renumber 는 거절한다
        bcases = (("G-4", 8, "%8d%8d%8d%8d%8d%8s%8d%8d" % (13, 9, 10000001, 10000002, 0, "0.0", 10000003, 10000004),
                   (10000001, 10000002, 10000003, 10000004, 10000005), "(a) 8자리 절점 + 8칸 SLEN 「0.0」"),
                  ("G-5", 8, "%8d%8d%8d%8d%8d%8s%8d%8d" % (13, 9, 101, 102, 7, "0.5", 103, 104), (101, 102, 103, 104, 105),
                   "8칸 SLEN 「0.5」"),
                  ("G-6", 8, "%8d%8d%8d%8d%8d%8s%8d" % (13, 9, 101, 102, 7, "0.5", 103), (101, 102, 103, 105), "8칸 SLEN 「0.5」 · N3 만"),
                  ("G-7", 8, "%8d%8d%8d%8d%8d%8s%8d%8d        " % (13, 9, 101, 102, 0, "", 103, 104), (101, 102, 103, 104, 105),
                   "8칸 빈 SLEN · 꼬리 공백"))
        for tag, fw, gl, gnodes, what in bcases:
            want = sorted(n for n in gnodes if str(n) in gl)
            gdeck = belt_deck(fw, gl, nodes=gnodes)
            write(os.path.join(d, tag + ".k"), gdeck)
            write(os.path.join(d, tag + "c.yaml"), "model: %s.k\noutput: %sc_out.k\nmode: safe\n" % (tag, tag))
            rc, out = run(binary, d, "cleanup-nodes", tag + "c.yaml")
            kept = sorted(node_ids(os.path.join(d, tag + "c_out.k"), fw).values()) if rc == 0 else None
            write(os.path.join(d, tag + "x.yaml"), "model: %s.k\noutput: %sx_out.k\nparts: [9]\n" % (tag, tag))
            rcx, outx = run(binary, d, "extract-parts", tag + "x.yaml")
            carried = sorted(node_ids(os.path.join(d, tag + "x_out.k"), fw).values()) if rcx == 0 else None
            write(os.path.join(d, tag + "r.yaml"), "model: %s.k\noutput: %sr_out.k\nparts: [9]\nrenumber: true\n" % (tag, tag))
            rcr, outr = run(binary, d, "extract-parts", tag + "r.yaml")
            check("%s ★%s — cleanup 이 띠의 절점 %s 를 다 남기고 · 다 싣고 · renumber 는 거절" % (tag, what, want),
                  rc == 0 and kept == want and rcx == 0 and carried == want and rcr == 1 and "제자리에 바꿔 쓸 수 없다" in outr,
                  (rc, kept, rcx, carried, rcr, outr[-300:]))
        # 번호 칸에 겹친 $ 주석(N4 칸 안에서 시작) — 제자리에 쓰면 주석을 덮는다 → renumber 거절(싣기 · cleanup 은 절점을 다 지킨다)
        gl = "%-8d%-8d%-8d%-8d%-8d%-16s%-8d" % (13, 9, 128, 147, 0, "", 118) + "101 $ 2 7"
        write(os.path.join(d, "G8.k"), belt_deck(8, gl, nodes=(101, 118, 128, 147)))
        write(os.path.join(d, "G8r.yaml"), "model: G8.k\noutput: G8r_out.k\nparts: [9]\nrenumber: true\n")
        rc, out = run(binary, d, "extract-parts", "G8r.yaml")
        write(os.path.join(d, "G8x.yaml"), "model: G8.k\noutput: G8x_out.k\nparts: [9]\n")
        rcx, outx = run(binary, d, "extract-parts", "G8x.yaml")
        carried = sorted(node_ids(os.path.join(d, "G8x_out.k"), 8).values()) if rcx == 0 else None
        check("G-8 ★번호 칸에 겹친 $ 주석 — renumber 거절(주석을 덮지 않는다) · 싣기는 절점 넷을 다 싣는다",
              rc == 1 and "겹친 $ 주석" in out and not os.path.exists(os.path.join(d, "G8r_out.k")) and rcx == 0 and
              carried == [101, 118, 128, 147], (rc, out[-300:], rcx, carried))
        # 주석이 겹친 칸이 0(N3 · N4 = 0 인 1D 띠)이면 바꿔 쓸 번호가 없다 — renumber 는 되고 주석이 그대로다(검토자 퍼즈의 거짓 거절)
        gz = ("%-8d%-8d%-8d%-8d%-8d%-16s%-8d%-8d" % (13, 9, 128, 147, 0, "0.0", 0, 0)).rstrip() + "  $ belt"
        write(os.path.join(d, "G8z.k"), belt_deck(8, gz, nodes=(128, 147)))
        write(os.path.join(d, "G8z.yaml"), "model: G8z.k\noutput: G8z_out.k\nparts: [9]\nrenumber: true\n")
        rc, out = run(binary, d, "extract-parts", "G8z.yaml")
        rows = section_lines(os.path.join(d, "G8z_out.k"), "*ELEMENT_SEATBELT") if rc == 0 else []
        check("G-8z ★주석이 겹친 칸이 0 이면 renumber 를 거절하지 않는다 · N1 · N2 만 바꾸고 주석은 그대로",
              rc == 0 and len(rows) == 1 and rows[0].endswith("0  $ belt") and rows[0][16:32] == "%8d%8d" % (1, 2),
              (rc, rows, out[-300:]))
        # 재결속 — 엔티티의 질량 줄 「    9003       1               1」(PID 없음 · 정수꼴 MASS)은 정수 폭 읽기의 MASS 가 비어 다른 읽기가
        # 아니다 → 옛 덱의 PID 1 이 있어도 「단정하지 못한 자리」가 아니다(재검토 R6 — 예전엔 rc 1)
        rb = os.path.join(d, "rebind")
        os.makedirs(rb)
        def hexdeck(path, n0, e0, pid):
            L, nid, idx = ["*KEYWORD", "*NODE"], n0, {}
            for k in (0, 1):
                for j in (0, 1):
                    for i in (0, 1):
                        idx[(i, j, k)] = nid
                        L.append("%8d%16.6f%16.6f%16.6f" % (nid, float(i), float(j), float(k)))
                        nid += 1
            c = [idx[(0, 0, 0)], idx[(1, 0, 0)], idx[(1, 1, 0)], idx[(0, 1, 0)], idx[(0, 0, 1)], idx[(1, 0, 1)], idx[(1, 1, 1)], idx[(0, 1, 1)]]
            L += ["*ELEMENT_SOLID", "%8d%8d" % (e0, pid) + "".join("%8d" % v for v in c), "*PART", "A#1", "%10d%10d%10d" % (pid, 1, 1),
                  "*SECTION_SOLID", "%10d%10d" % (1, 1), "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (1, 7.85e-9, 210000, 0.3), "*END"]
            write(path, "\n".join(L) + "\n")
        hexdeck(os.path.join(rb, "v1.k"), 1, 1, 1)
        hexdeck(os.path.join(rb, "v2.k"), 101, 11, 5)
        write(os.path.join(rb, "ours.k"), "*KEYWORD\n*ELEMENT_MASS\n%8d%8d%16s\n*END\n" % (9003, 1, "1"))
        write(os.path.join(rb, "rb.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: ours.k\noutput: o.k\n")
        rc, out = run(binary, rb, "rebind_entities_after_remesh", "rb.yaml")
        check("G-9 ★rebind — PID 없는 정수꼴 질량 줄은 다른 읽기의 PID 가 아니다(MASS 가 빈 꼴) → 거절하지 않는다",
              rc == 0 and "단정하지 못한" not in out, (rc, out[-400:]))
        # 이월 적용 — PID 20 띠의 정수꼴 SLEN 이 다시 짓는 PID 4 만 쓰는 절점 번호와 같다 — 네 절점 띠라 다른 읽기가 아니다 → shared_nodes 아님
        dg = os.path.join(d, "carry_slen")
        shutil.copytree(CARRY, dg)
        text = open(os.path.join(dg, "deck.k"), encoding="utf-8").read()
        line = belt(8, 95501, 20, keep[0], keep[1], 0, str(rem[0]), keep[2], keep[3])
        text = text.rstrip()[:-4] + "*PART\nbelt\n%10d%10d%10d\n*ELEMENT_SEATBELT\n%s\n*END\n" % (20, 1, 1, line)
        write(os.path.join(dg, "deck.k"), text)
        plan = json.load(open(os.path.join(dg, "plan.json"), encoding="utf-8"))
        plan["deck"]["sha256"] = hashlib.sha256(open(os.path.join(dg, "deck.k"), "rb").read()).hexdigest()
        write(os.path.join(dg, "plan.json"), json.dumps(plan, ensure_ascii=False, indent=1))
        write(os.path.join(dg, "run.yaml"), "model: deck.k\nplan: plan.json\noutput: out.k\n")
        rc, out = run(binary, dg, "apply_carryover_plan", "run.yaml")
        rp = os.path.join(dg, "out_carryover.json")
        rep = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
        check("G-10 ★apply_carryover_plan — 네 절점 띠의 정수꼴 SLEN(%d — PID 4 만 쓰는 절점)은 나눠 쓴 절점이 아니다 → rc 0" % rem[0],
              rc == 0 and not [p for p in (rep.get("problems") or []) if p.get("kind") == "shared_nodes"], (rc, rep.get("problems"), out[-300:]))

        print("[H 고정폭 줄은 늘 설명서 칸 — 꼬리 글 · SLEN · MASS 칸 안 빈칸에도 토큰이 갈음하지 않는다]")
        def three(tag, fw, gl, gnodes, want, what, renum=True):
            """cleanup-nodes safe · extract-parts · renumber — 띠의 절점(want)만 남기고 싣고, renumber 는 거절하지 않는다(renum)."""
            write(os.path.join(d, tag + ".k"), belt_deck(fw, gl, nodes=gnodes))
            write(os.path.join(d, tag + "c.yaml"), "model: %s.k\noutput: %sc_out.k\nmode: safe\n" % (tag, tag))
            rc, out = run(binary, d, "cleanup-nodes", tag + "c.yaml")
            kept = sorted(node_ids(os.path.join(d, tag + "c_out.k"), fw).values()) if rc == 0 else None
            check("%s ★cleanup-nodes — %s: %s 를 남기고 나머지를 지운다" % (tag, what, want), rc == 0 and kept == want, (rc, kept, out[-300:]))
            write(os.path.join(d, tag + "x.yaml"), "model: %s.k\noutput: %sx_out.k\nparts: [9]\n" % (tag, tag))
            rc, out = run(binary, d, "extract-parts", tag + "x.yaml")
            carried = sorted(node_ids(os.path.join(d, tag + "x_out.k"), fw).values()) if rc == 0 else None
            check("%s ★extract-parts — %s: %s 를 싣는다" % (tag, what, want), rc == 0 and carried == want, (rc, carried, out[-300:]))
            write(os.path.join(d, tag + "r.yaml"), "model: %s.k\noutput: %sr_out.k\nparts: [9]\nrenumber: true\nreport: %sr.json\n" % (tag, tag, tag))
            rc, out = run(binary, d, "extract-parts", tag + "r.yaml")
            if not renum:
                check("%s renumber — %s: 두 읽기가 갈려 거절한다(산출 없음)" % (tag, what),
                      rc == 1 and not os.path.exists(os.path.join(d, tag + "r_out.k")), (rc, out[-300:]))
                return
            rr = json.load(open(os.path.join(d, tag + "r.json"), encoding="utf-8")) if rc == 0 else {}
            ids = node_ids(os.path.join(d, tag + "r_out.k"), fw) if rc == 0 else {}
            rows = section_lines(os.path.join(d, tag + "r_out.k"), "*ELEMENT_SEATBELT") if rc == 0 else []
            check("%s ★renumber — %s: 거절하지 않는다 · 1 부터 · 되읽기 0" % (tag, what),
                  rc == 0 and sorted(ids.values()) == want and sorted(ids) == list(range(1, len(want) + 1)) and
                  (rr.get("verify") or {}).get("undefined_nodes") == 0 and len(rows) == 1, (rc, sorted(ids.items()), rows, out[-400:]))
            return rows
        # 꼬리 글(카드 폭 뒤) — 예전엔 줄 전체의 칸을 보아 공백 토큰이 설명서 칸을 갈음했다: N3 103 을 지웠고(rc 0) 싣지 않았다
        tl = "%8d%8d%8d%8d%8s%16s%8d%8d" % (13, 9, 101, 102, "", "0.0", 103, 104) + "        belt left 1"
        rows = three("H-1", 8, tl, (101, 102, 103, 104, 105), [101, 102, 103, 104], "8칸 줄 뒤 꼬리 글 「belt left 1」")
        check("H-1r renumber 는 N3 · N4 를 57-72열에 쓰고 꼬리 글은 그대로다",
              bool(rows) and rows[0][56:72] == "%8d%8d" % (3, 4) and rows[0].endswith("        belt left 1"), rows)
        tl = "%10d%10d%10d%10d%10s%16s%10d%10d" % (13, 9, 101, 102, "", "0.0", 1000003, 1000004) + " LH belt"
        three("H-2", 10, tl, (101, 102, 1000003, 1000004, 105), [101, 102, 1000003, 1000004], "i10 줄 뒤 꼬리 글 「LH belt」")
        for k, slen in enumerate(("- 1.5", "1 000.0")):
            tl = "%8d%8d%8d%8d%8s%16s%8d%8d" % (13, 9, 101, 102, "", slen, 103, 104)
            three("H-3%s" % "ab"[k], 8, tl, (101, 102, 103, 104, 105), [101, 102, 103, 104], "SLEN 칸 안 빈칸 「%s」" % slen)

        def mass_deck(fw, mline, nodes):
            f = "%" + str(fw) + "d"
            L = ["*KEYWORD" + (" I10=Y" if fw == 10 else ""), "*NODE"] + [node(fw, n, float(n)) for n in nodes]
            L += ["*ELEMENT_SHELL", (f * 6) % (1, 7, 1, 2, 3, 4), "*ELEMENT_MASS", mline, "*PART", "p7", "%10d%10d%10d" % (7, 1, 1),
                  "*SECTION_SHELL", "%10d%10d" % (1, 2), "%10s" % "1.0", "*MAT_ELASTIC", "%10d%10s%10s%10s" % (1, "7.85E-9", "210000.", "0.3"), "*END"]
            return "\n".join(L) + "\n"
        mcases = (("H-4", "%8d%8d%16s%8d" % (95001, 105, "1.0 E-03", 7), 105, "MASS 칸 안 빈칸 「1.0 E-03」"),
                  ("H-5", "%8d%8d%16s%8d" % (95001, 10000005, "0.001", 7) + "  mass on lid", 10000005, "EID · NID 가 붙은 줄 뒤 꼬리 글 「mass on lid」"))
        for tag, ml, mn, what in mcases:
            write(os.path.join(d, tag + ".k"), mass_deck(8, ml, (1, 2, 3, 4, mn, 99)))
            write(os.path.join(d, tag + "c.yaml"), "model: %s.k\noutput: %sc_out.k\nmode: safe\n" % (tag, tag))
            rc, out = run(binary, d, "cleanup-nodes", tag + "c.yaml")
            kept = sorted(node_ids(os.path.join(d, tag + "c_out.k"), 8).values()) if rc == 0 else None
            check("%s ★cleanup-nodes — %s: 질량 절점 %d 를 남기고 99 를 지운다" % (tag, what, mn), rc == 0 and kept == [1, 2, 3, 4, mn], (rc, kept, out[-300:]))
            for ren in (False, True):
                y = "%s%s.yaml" % (tag, "r" if ren else "x")
                write(os.path.join(d, y), "model: %s.k\noutput: %s_out.k\nparts: [7]\nrenumber: %s\n" % (tag, y, "true" if ren else "false"))
                rc, out = run(binary, d, "extract-parts", y)
                ms = section_lines(os.path.join(d, y + "_out.k"), "*ELEMENT_MASS") if rc == 0 else []
                car = sorted(node_ids(os.path.join(d, y + "_out.k"), 8).values()) if rc == 0 else None
                check("%s ★extract-parts%s parts [7] — %s: 질량 줄(PID 7 · 33-40열)을 싣는다" % (tag, " renumber" if ren else "", what),
                      rc == 0 and len(ms) == 1 and car == [1, 2, 3, 4, mn] and ms[0][32:40] == "%8d" % 7, (rc, ms, car, out[-300:]))

        # 같은 읽기를 쓰는 소비자 — 이월 적용의 나눠 쓴 절점 · restack 의 지운 절점 보고 · rebind 의 질량 PID
        dh = os.path.join(d, "carry_tail")
        shutil.copytree(CARRY, dh)
        text = open(os.path.join(dh, "deck.k"), encoding="utf-8").read()
        tl = "%8d%8d%8d%8d%8s%16s%8d%8d" % (95501, 20, keep[0], keep[1], "", "0.0", rem[0], keep[2]) + "        belt left 1"
        text = text.rstrip()[:-4] + "*PART\nbelt\n%10d%10d%10d\n*ELEMENT_SEATBELT\n%s\n*END\n" % (20, 1, 1, tl)
        write(os.path.join(dh, "deck.k"), text)
        plan = json.load(open(os.path.join(dh, "plan.json"), encoding="utf-8"))
        plan["deck"]["sha256"] = hashlib.sha256(open(os.path.join(dh, "deck.k"), "rb").read()).hexdigest()
        write(os.path.join(dh, "plan.json"), json.dumps(plan, ensure_ascii=False, indent=1))
        write(os.path.join(dh, "run.yaml"), "model: deck.k\nplan: plan.json\noutput: out.k\n")
        rc, out = run(binary, dh, "apply_carryover_plan", "run.yaml")
        rp = os.path.join(dh, "out_carryover.json")
        rep = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
        hits = [p for p in (rep.get("problems") or []) if p.get("pid") == 4 and p.get("kind") == "shared_nodes"]
        check("H-6 ★apply_carryover_plan — 꼬리 글이 붙은 띠의 N3(%d — PID 4 만 쓰는 절점)도 나눠 쓴 절점 → rc 1" % rem[0],
              rc == 1 and hits and str(rem[0]) in hits[0].get("detail", ""), (rc, rep.get("problems"), out[-300:]))
        db = open(os.path.join(d, "D.k"), encoding="utf-8").read()
        tl = "%8d%8d%8d%8d%8s%16s%8d%8d" % (9103, 3, 500001, 500002, "", "0.0", 500006, 500004) + "        belt left 1"
        db = db.replace("\n*END\n", "\n" + tl + "\n*END\n")
        write(os.path.join(d, "H7.k"), db)
        write(os.path.join(d, "h7.yaml"), open(os.path.join(d, "d.yaml"), encoding="utf-8").read().replace("model: D.k", "model: H7.k").replace("d_out.k", "h7_out.k"))
        rc, out = run(binary, d, "restack", "h7.yaml")
        l9103 = db.split("\n").index(tl) + 1
        check("H-7 ★restack — 꼬리 글이 붙은 띠의 N3 이 지운 절점(500006)이면 그 줄(%d)을 manual 로 올린다" % l9103,
              rc == 0 and any(re.search(r"line %d \*ELEMENT_SEATBELT \(manual\)" % l9103, l) for l in out.splitlines()), (rc, out[-400:]))
        write(os.path.join(rb, "ours2.k"), "*KEYWORD\n*ELEMENT_MASS\n%8d%8d%16s%8d\n*END\n" % (9003, 1, "1.0 E-03", 1))
        write(os.path.join(rb, "rb2.yaml"), "old_deck: v1.k\nnew_deck: v2.k\nentities: ours2.k\noutput: o2.k\n")
        rc, out = run(binary, rb, "rebind_entities_after_remesh", "rb2.yaml")
        check("H-8 ★rebind — MASS 칸에 빈칸이 낀 질량 줄의 PID(33-40열 · 1)를 읽는다 → 「단정하지 못한 자리」 로 거절",
              rc == 1 and "단정하지 못한" in out, (rc, out[-400:]))

        # 정수 폭으로 쓴 i10 줄의 설명서 칸은 덱에 없는 번호를 말할 수 있다(N4 칸에 N4 의 끝 네 자리 · 붙은 두 번호를 가른 조각) — 한 읽기만
        # 말하는 절점은 덱에 있을 때만 쓰는 절점으로 친다. 예전엔 설명서 칸이 깨끗하면 그 조각을 쓰는 절점으로 세어 되읽기가 「미정의」 로
        # cleanup-nodes · extract-parts 를 rc 1 로 끝냈다(2차 퍼즈 i10 200 줄 가운데 18)
        tl = "%10d%10d%10d%10d%10d%10s%10d%10d" % (13, 9, 2038153015, 216154185, 0, "", 2064627083, 569778307)
        three("H-9", 10, tl, (2038153015, 216154185, 2064627083, 569778307, 105), [216154185, 569778307, 2038153015, 2064627083],
              "정수 폭 i10 · 설명서 칸 N3 에 빈칸 · N4 = 8307(덱에 없다)", renum=False)
        tl = ("%-10d%-10d%-10d%-10d%-10s%-10s%-10d%-10d" % (13, 9, 997202346, 1379264357, "0", "", 1242401273, 1756551707)).rstrip()
        three("H-10", 10, tl, (997202346, 1379264357, 1242401273, 1756551707, 105), [997202346, 1242401273, 1379264357, 1756551707],
              "정수 폭 i10 왼쪽 맞춤 · 붙은 번호(설명서 칸 N3 = 1273175655 · N4 = 1707 — 덱에 없다)", renum=False)

        print("[I 규칙 (e) — 정수 폭 읽기는 칸마다 같은 꼴(같은 왼쪽 · 오른쪽 여백)로 쓴 줄만]")
        # 칸마다 맞춤이 다른 설명서 꼴 i10 줄(N3 오른쪽 · N4 왼쪽 맞춤)은 정수 폭 읽기가 다른 읽기가 아니다 — 예전엔 「10」(SLEN 의 끝)을
        # N3 으로 읽어 고아 절점 10 을 남기고 · 싣고 · renumber 를 거절했다(재검토 퍼즈 i10 1200 줄 가운데 34)
        tl = "%10d%10d%10d%10d%10s%16s%10d%-10s" % (1, 9, 101, 102, "", "10", 103, "104")
        three("I-1", 10, tl, (10, 101, 102, 103, 104, 105), [101, 102, 103, 104], "i10 설명서 꼴 · N3 오른쪽 N4 왼쪽 맞춤(고아 10)")
        # 정수 폭으로 고르게 쓴 줄은 그대로 두 읽기를 다 지키고 renumber 를 거절한다 — 오른쪽 맞춤(긴 N3 · 짧은 N4) · 칸마다 뒤 한 칸(`%7d `)
        tl = "%10d%10d%10d%10d%10s%10s%10d%10d" % (13, 9, 101, 102, "", "", 123456789, 1234)
        three("I-2", 10, tl, (101, 102, 1234, 6789, 123456789, 105), [101, 102, 1234, 6789, 123456789],
              "정수 폭 오른쪽 맞춤 i10(N3 123456789 · N4 1234)", renum=False)
        tl = ("%7d %7d %7d %7d %7s %7s %7d %7d " % (13, 9, 101, 102, "", "0.5", 1031, 1041)).rstrip()
        three("I-3", 8, tl, (101, 102, 1031, 1041, 105), [101, 102, 1031, 1041], "정수 폭 `%7d ` 줄", renum=False)
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
