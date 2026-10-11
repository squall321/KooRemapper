#!/usr/bin/env python3
# extract-parts 가 뽑은 덱이 **그대로 돌아가는지** — 조용히 빠진 참조가 하나도 없는지
"""`extract-parts` 계약 (2026-10-11).

왜 이 시험이 있나.

  요청서(CAE그룹 v1.0) ①. 61파트 Q8 Close 덱(2.32GB)에서 몇 파트만 떼어 `unfold` →
  `prestress` → `relax` 로 보내는 일을 매번 손으로 했다. 어려운 부분은 '뽑기' 가 아니라
  **남은 것이 멀쩡한가** 다 — 뽑은 덱이 없는 절점·파트·섹션·재질을 가리키면 LS-DYNA 는
  엉뚱한 자리에서 죽고, 그 원인이 추출이라는 것은 한참 뒤에 안다.

  그래서 이 시험이 보는 것은 "뽑혔나" 가 아니라 **"뽑힌 덱의 미정의 참조가 0 인가"** 다.

  ★그리고 **조용한 손실**을 본다. 두 자리가 특히 위험했다.
    · `*INCLUDE` — 2.32GB 급 덱은 거의 늘 인클루드로 쪼개져 있다. 안 읽으면 고른 파트의
      요소가 **하나도 없는** 덱이 조용히 나온다(B 절).
    · 우리가 줄 수를 모르는 `*ELEMENT_*` 변형 — 고른 파트의 요소를 담고 있으면 **거절**해야
      한다. 빠뜨린 덱은 그럴듯하게 돌면서 틀린다(J 절).

usage: test_extract_parts.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], capture_output=True, text=True, timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def write(path, text, newline="\n"):
    with open(path, "w", newline=newline) as f:
        f.write(text)


def nl(n, x, y, z):
    return "%8d%16.7f%16.7f%16.7f" % (n, x, y, z)


def e8(*v):
    return "".join("%8d" % n for n in v)


def s10(*v):
    return "".join("%10d" % n for n in v)


def base_deck(include_name="inc_part2.k", extra=()):
    """세 파트: 1(솔리드, 주덱) · 2(솔리드, **인클루드**) · 3(셸, 주덱)."""
    L = ["*KEYWORD", "*NODE"]
    for i in range(1, 9):
        L.append(nl(i, i % 2, (i // 2) % 2, i // 4))
    for i in range(9, 17):
        L.append(nl(i, i % 2 + 2, (i // 2) % 2, i // 4))
    for i in range(17, 21):
        L.append(nl(i, i % 2 + 4, (i // 2) % 2, 0))
    L.append(nl(999, 99.0, 0.0, 0.0))
    L += ["*ELEMENT_SOLID", e8(1, 1), e8(*range(1, 9))]
    L += ["*ELEMENT_SHELL", e8(30, 3, 17, 18, 19, 20)]
    L += ["*PART", "part one solid", s10(1, 1, 1), "part three shell", s10(3, 3, 3)]
    L += ["*SECTION_SOLID", s10(1, 1)]
    L += ["*SECTION_SHELL", s10(3, 2), "         1.0       1.0       1.0       1.0"]
    L += ["*MAT_ELASTIC", "         1  7.85E-9  210000     0.3"]
    L += ["*MAT_ELASTIC", "         3  2.70E-9   70000    0.33"]
    L += ["*SECTION_SOLID", s10(2, 1)]
    L += ["*MAT_ELASTIC", "         2  1.00E-9   10000     0.4"]
    L += ["*SET_NODE_LIST", s10(500), s10(*range(1, 9)), s10(*range(9, 17))]
    L += ["*SET_PART_LIST", s10(600), s10(1, 2, 3)]
    L += ["*SET_NODE_LIST_GENERATE", s10(700), s10(1, 20)]
    L += ["*SET_SEGMENT", s10(800), s10(1, 2, 3, 4), s10(17, 18, 19, 20)]
    L += ["*CONTROL_TERMINATION", "      10.0"]
    L += ["*DATABASE_BINARY_D3PLOT", "       1.0"]
    L += ["*DATABASE_HISTORY_NODE", s10(999)]
    L += ["*DEFINE_CURVE", s10(10), "               0.0               0.0"]
    L += list(extra)
    L += ["*INCLUDE", include_name, "*END"]
    return "\n".join(L) + "\n"


INC = "\n".join(["*KEYWORD", "*PART", "part two solid in include", s10(2, 2, 2),
                 "*ELEMENT_SOLID", e8(2, 2), e8(*range(9, 17)), "*END"]) + "\n"


def cfg(d, name, body):
    write(os.path.join(d, name), body)
    return name


def rep(d, name="rep.json"):
    with open(os.path.join(d, name)) as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("usage: test_extract_parts.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="extract_parts_")
    try:
        write(os.path.join(d, "main.k"), base_deck())
        write(os.path.join(d, "inc_part2.k"), INC)

        # ── A: 기본 ───────────────────────────────────────────────────────────
        cfg(d, "a.yaml", "model: main.k\noutput: out.k\nparts: [1, 2]\nreport: rep.json\n")
        rc, out = run(binary, d, "extract-parts", "a.yaml")
        check("A-0 rc=0", rc == 0, out[-500:])
        r = rep(d)
        check("A-1 ★되읽기 검증 — 미정의 참조 0 (절점·파트·섹션·재질 전수)",
              r["verify"] == {"undefined_nodes": 0, "undefined_parts": 0,
                              "undefined_sections": 0, "undefined_materials": 0}, r["verify"])
        check("A-2 고른 파트의 요소 카드 2개", r["picked"]["element_cards"] == 2, r["picked"])
        check("A-3 그 요소가 쓰는 절점 16개만", r["picked"]["nodes"] == 16, r["picked"])
        check("A-4 쓴 *NODE 줄도 16개 (아무도 안 쓰는 999 는 안 간다)",
              r["picked"]["node_lines_written"] == 16, r["picked"])
        check("A-5 *PART 2개", r["picked"]["parts_emitted"] == 2, r["picked"])
        o = open(os.path.join(d, "out.k")).read()
        check("A-6 안 고른 파트의 요소는 없다", "      30       3" not in o)
        check("A-7 안 고른 재질은 없다 (MID 3)", "         3  2.70E-9" not in o)
        check("A-8 필요한 섹션·재질은 둘 다 있다",
              r["needed"]["sections"] == [1, 2] and r["needed"]["materials"] == [1, 2], r["needed"])
        check("A-9 ID 를 그대로 둔다 (renumber 기본 false)",
              r["renumber"]["on"] is False and "\n       1       2       3       4" in o)
        check("A-10 *CONTROL_* 은 그대로 싣는다 (안 싣으면 덱이 안 돈다)",
              "*CONTROL_TERMINATION" in o)
        check("A-11 ★*DATABASE_HISTORY_NODE 는 버린다 (없는 절점을 가리킨다)",
              "*DATABASE_HISTORY_NODE" not in o and
              "*DATABASE_HISTORY_NODE" in r["dropped_keywords"], r["dropped_keywords"])
        check("A-12 그 밖 *DATABASE_ 는 싣는다", "*DATABASE_BINARY_D3PLOT" in o)
        check("A-13 ★버린 것을 전부 수로 적는다 (안 보이는 손실을 만들지 않는다)",
              len(r["dropped_keywords"]) >= 4, r["dropped_keywords"])
        check("A-14 한 줄도 안 실린 블록은 키워드 줄도 내지 않는다",
              "*ELEMENT_SHELL" not in o)

        # ── B: ★*INCLUDE 를 펼친다 ────────────────────────────────────────────
        check("B-1 ★인클루드의 파트도 뽑힌다 (안 읽으면 요소가 하나도 없다)",
              "part two solid in include" in o and "       2       2\n" in o)
        check("B-2 펼친 인클루드 수를 적는다", r["deck"]["includes_inlined"] == 1, r["deck"])
        check("B-3 산출 덱에 *INCLUDE 가 남지 않는다 (홀로 선다)", "*INCLUDE" not in o)
        check("B-4 인클루드의 *KEYWORD·*END 가 두 번 나오지 않는다",
              o.count("*KEYWORD") == 1 and o.count("*END") == 1,
              (o.count("*KEYWORD"), o.count("*END")))
        # 인클루드만 고르면 — 안 읽으면 rc=1 로 죽는다(요소 0)
        cfg(d, "b.yaml", "model: main.k\noutput: b.k\nparts: [2]\nreport: repb.json\n")
        rc, out = run(binary, d, "extract-parts", "b.yaml")
        check("B-5 ★인클루드 안의 파트만 골라도 돈다", rc == 0, out[-400:])
        check("B-6 그 덱의 요소 카드 1개", rep(d, "repb.json")["picked"]["element_cards"] == 1)

        # ── C: part_titles 와일드카드 ────────────────────────────────────────
        cfg(d, "c.yaml", 'model: main.k\noutput: c.k\npart_titles: ["part*solid*"]\n'
                         "report: repc.json\n")
        rc, out = run(binary, d, "extract-parts", "c.yaml")
        rcj = rep(d, "repc.json")
        check("C-1 제목 와일드카드가 PID 로 풀린다", rc == 0 and rcj["parts_selected"] == [1, 2],
              rcj.get("parts_selected"))
        check("C-2 셸 파트는 안 걸린다('solid' 가 없다)", 3 not in rcj["parts_selected"])
        cfg(d, "c2.yaml", 'model: main.k\noutput: c2.k\npart_titles: ["nope*"]\n')
        rc, out = run(binary, d, "extract-parts", "c2.yaml")
        check("C-3 아무것도 안 맞으면 경고하고 거절한다", rc == 1 and "맞는 파트가 없다" in out,
              out[-300:])

        # ── D: renumber ──────────────────────────────────────────────────────
        cfg(d, "dd.yaml", "model: main.k\noutput: rn.k\nparts: [1, 2]\nrenumber: true\n"
                          "report: repd.json\n")
        rc, out = run(binary, d, "extract-parts", "dd.yaml")
        rd = rep(d, "repd.json")
        rn = open(os.path.join(d, "rn.k")).read()
        check("D-0 rc=0", rc == 0, out[-400:])
        check("D-1 ★번호를 매겼는데도 미정의 참조 0",
              rd["verify"]["undefined_nodes"] == 0, rd["verify"])
        check("D-2 절점이 1 부터다", "\n       1       1.0000000" in rn, rn[:200])
        mp_path = os.path.join(d, os.path.basename(rd["renumber"]["map"] or ""))
        check("D-3 매핑 표를 함께 낸다 (없으면 되돌릴 수 없다)",
              rd["renumber"]["map"] and os.path.exists(mp_path), rd["renumber"]["map"])
        with open(mp_path) as f:
            mp = json.load(f)
        check("D-4 매핑이 16 절점·2 요소", len(mp["nodes"]) == 16 and len(mp["elements"]) == 2,
              (len(mp["nodes"]), len(mp["elements"])))
        check("D-5 매핑이 옛→새 쌍이다", mp["nodes"][8] == [9, 9] and mp["elements"] == [[1, 1], [2, 2]],
              (mp["nodes"][8], mp["elements"]))
        # ★좌표 글자는 손대지 않는다 — 칸만 제자리에서 갈아 끼우므로 실수 왕복 오차가 0 이다
        src_coords = [l[8:] for l in open(os.path.join(d, "main.k")).read().split("\n")
                      if l.startswith("       9       ")]
        out_coords = [l[8:] for l in rn.split("\n") if l.startswith("       9       ")]
        check("D-6 ★좌표 글자가 바이트 그대로다 (다시 포맷하지 않는다)",
              src_coords and out_coords and src_coords[0] == out_coords[0],
              (src_coords[:1], out_coords[:1]))
        check("D-7 세트 멤버도 함께 번호가 바뀐다 (*SET_NODE_LIST 500)",
              "*SET_NODE_LIST" in rn and rd["verify"]["undefined_nodes"] == 0)

        # ── E: include.sets / materials 끄기 ─────────────────────────────────
        cfg(d, "e.yaml", "model: main.k\noutput: e.k\nparts: [1, 2]\ninclude:\n"
                         "  sets: none\n  materials: false\nreport: repe.json\n")
        rc, out = run(binary, d, "extract-parts", "e.yaml")
        e = open(os.path.join(d, "e.k")).read()
        re_ = rep(d, "repe.json")
        check("E-1 sets: none 이면 *SET_* 이 없다", "*SET_" not in e)
        check("E-2 materials: false 면 *MAT_* 이 없다", "*MAT_" not in e)
        check("E-3 ★그러면 검증이 재질 미정의를 잡는다 (조용히 통과하지 않는다)",
              re_["verify"]["undefined_materials"] > 0 and rc != 0, (re_["verify"], rc))

        # ── F: 세트 자르기 ───────────────────────────────────────────────────
        check("F-1 *SET_NODE_LIST 를 남은 절점으로 자른다",
              r["sets_trimmed"].get("*SET_NODE_LIST") == 1, r["sets_trimmed"])
        check("F-2 *SET_PART_LIST 를 고른 파트로 자른다",
              r["sets_trimmed"].get("*SET_PART_LIST") == 1, r["sets_trimmed"])
        check("F-3 자른 뒤 안 고른 PID 3 이 세트에서 빠졌다",
              "\n         1         2\n" in o, "")
        check("F-4 ★멤버를 ID 로 못 읽는 변형은 버리고 **SID 를 적는다**",
              r["sets_dropped_sids"] == [700], r["sets_dropped_sids"])
        check("F-5 ★*SET_SEGMENT 는 네 절점이 다 남은 면만 싣는다",
              "*SET_SEGMENT" in o and "        17        18        19        20" not in o)
        check("F-6 그 세트의 남은 면은 있다", "         1         2         3         4" in o)

        # ── G: CRLF 보존 ─────────────────────────────────────────────────────
        write(os.path.join(d, "crlf.k"), base_deck("inc_crlf.k"), newline="\r\n")
        write(os.path.join(d, "inc_crlf.k"), INC, newline="\r\n")
        cfg(d, "g.yaml", "model: crlf.k\noutput: g.k\nparts: [1, 2]\nreport: repg.json\n")
        rc, out = run(binary, d, "extract-parts", "g.yaml")
        raw = open(os.path.join(d, "g.k"), "rb").read()
        lone = raw.replace(b"\r\n", b"").count(b"\n")
        check("G-1 rc=0", rc == 0, out[-300:])
        check("G-2 ★산출에 홀로 선 LF 가 0", lone == 0, lone)
        check("G-3 CRLF 가 실제로 있다", raw.count(b"\r\n") > 10, raw.count(b"\r\n"))

        # ── H: 고차 솔리드 두 줄 카드 ────────────────────────────────────────
        L = ["*KEYWORD", "*NODE"]
        for n in range(1, 21):
            L.append(nl(n, float(n), 0.0, 0.0))
        L.append(nl(101, 99.0, 0.0, 0.0))
        L += ["*ELEMENT_SOLID", e8(1, 7), e8(*range(1, 11)), e8(*range(11, 21)),
              "*PART", "hex20", s10(7, 7, 7),
              "*SECTION_SOLID", s10(7, 23),
              "*MAT_ELASTIC", "         7  7.85E-9  210000     0.3", "*END"]
        write(os.path.join(d, "hex20.k"), "\n".join(L) + "\n")
        cfg(d, "h.yaml", "model: hex20.k\noutput: h.k\nparts: [7]\nreport: reph.json\n")
        rc, out = run(binary, d, "extract-parts", "h.yaml")
        rh = rep(d, "reph.json")
        check("H-1 ★절점 카드 두 줄을 다 싣는다 (ELFORM 23 = 20절점)",
              rh["picked"]["nodes"] == 20, rh["picked"])
        check("H-2 미정의 참조 0", rh["verify"]["undefined_nodes"] == 0, rh["verify"])
        check("H-3 한 줄만 실으면 덱이 깨진다 — 두 줄이 실렸다",
              open(os.path.join(d, "h.k")).read().count("      11      12") == 1)

        # ── I: 8자리 ID 가 칸을 꽉 채운다 ────────────────────────────────────
        ids = list(range(10000001, 10000009))
        L = ["*KEYWORD", "*NODE"] + [nl(n, float(i), 0.0, 0.0) for i, n in enumerate(ids)]
        L += [nl(10000009, 9.0, 0.0, 0.0)]
        L += ["*ELEMENT_SOLID", e8(1, 5), e8(*ids),
              "*PART", "packed", s10(5, 5, 5),
              "*SECTION_SOLID", s10(5, 1),
              "*MAT_ELASTIC", "         5  7.85E-9  210000     0.3", "*END"]
        write(os.path.join(d, "packed.k"), "\n".join(L) + "\n")
        cfg(d, "i.yaml", "model: packed.k\noutput: i.k\nparts: [5]\nreport: repi.json\n")
        rc, out = run(binary, d, "extract-parts", "i.yaml")
        ri = rep(d, "repi.json")
        check("I-1 ★8자리 ID 가 붙어도 8절점을 읽는다", ri["picked"]["nodes"] == 8, ri["picked"])
        check("I-2 미정의 참조 0", ri["verify"]["undefined_nodes"] == 0, ri["verify"])
        check("I-3 아무도 안 쓰는 10000009 는 안 간다",
              "10000009" not in open(os.path.join(d, "i.k")).read())

        # ── J: 거절 ──────────────────────────────────────────────────────────
        cfg(d, "j1.yaml", "model: main.k\noutput: j1.k\nparts: [1, 42]\n")
        rc, out = run(binary, d, "extract-parts", "j1.yaml")
        check("J-1 ★덱에 없는 PID 는 거절한다 (오타면 조용히 빈 덱이 나온다)",
              rc == 1 and "없는 PID" in out, out[-300:])
        # 모르는 *ELEMENT_* 변형이 고른 파트의 요소를 담고 있다
        write(os.path.join(d, "beam.k"),
              # ⚠ `*ELEMENT_*` 는 덱의 정수 칸 폭(여기서는 8)이다 — 10칸으로 쓰면 칸이 밀려
              # PID 가 90 으로 읽히고, 그건 덱이 틀린 것이지 op 이 틀린 것이 아니다.
              base_deck("inc_part2.k", extra=["*ELEMENT_BEAM", e8(90, 1, 1, 2, 0)]))
        cfg(d, "j2.yaml", "model: beam.k\noutput: j2.k\nparts: [1]\n")
        rc, out = run(binary, d, "extract-parts", "j2.yaml")
        check("J-2 ★못 읽는 *ELEMENT_* 변형이 고른 파트를 담으면 거절한다",
              rc == 1 and "*ELEMENT_BEAM" in out, out[-400:])
        cfg(d, "j3.yaml", "model: beam.k\noutput: j3.k\nparts: [3]\n")
        rc, out = run(binary, d, "extract-parts", "j3.yaml")
        check("J-3 안 고른 파트의 것이면 거절하지 않는다 (버리고 수로 적는다)", rc == 0, out[-300:])
        write(os.path.join(d, "miss.k"), base_deck("nope.k"))
        cfg(d, "j4.yaml", "model: miss.k\noutput: j4.k\nparts: [1]\n")
        rc, out = run(binary, d, "extract-parts", "j4.yaml")
        check("J-4 ★못 읽는 *INCLUDE 는 거절한다 (파트가 조용히 빠진다)",
              rc == 1 and "열 수 없다" in out, out[-300:])
        cfg(d, "j5.yaml", "model: main.k\noutput: j5.k\n")
        rc, out = run(binary, d, "extract-parts", "j5.yaml")
        check("J-5 무엇을 뽑을지 안 고르면 거절한다", rc == 1 and "하나는 필요하다" in out, out[-300:])
        write(os.path.join(d, "j6.yaml"), "model: main.k\n\tparts: [1]\n")
        rc, out = run(binary, d, "extract-parts", "j6.yaml")
        check("J-6 탭 들여쓰기를 거른다", rc == 1 and "extract-parts" in out, out[-200:])
        cfg(d, "j7.yaml", "model: nosuch.k\nparts: [1]\n")
        rc, out = run(binary, d, "extract-parts", "j7.yaml")
        check("J-7 없는 모델은 rc=1 로 말한다", rc == 1 and "Cannot open model" in out, out[-200:])
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


if __name__ == "__main__":
    sys.exit(main())
