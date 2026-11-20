#!/usr/bin/env python3
# extract-parts 가 long 형식(칸 20) 덱에서도 표준 형식과 같은 것을 뽑는지 보는 회귀 시험
"""extract-parts 의 long 형식 (2026-11-20 · 11-08 에 「다음 판」 으로 미뤘던 결함).

왜 이 시험이 있나.

  `*KEYWORD LONG=Y` 덱에서 extract-parts 가 「No *PART definitions found」 로 끝났다(rc 1 · 산출 없음). 요소 · 절점 카드는 키워드 폭을
  따라 읽었는데 `*PART` 카드 2 · `*SECTION_*` · `*MAT` · `*EOS` · `*HOURGLASS` 의 ID 칸은 늘 10 칸으로 읽었다. long 형식에서는
  표준에서 20 칸 이하인 칸이 다 20 칸이다(Vol_I 19315-19316) — 20 칸의 앞 10 칸은 빈칸이라 PID 가 0 으로 읽혔다. 키워드 하나만
  long 으로 바꾸는 `+` 접미사(Vol_I 19342-19345)도 같았다.

  이제 그 카드들도 키워드 폭으로 읽는다(색인 · 쓰기 · 되읽기). 되읽기의 재질 셈(공용 재질 훑기)은 `*MAT` 블록 줄만 받아 덱 폭을
  몰랐다 — `*KEYWORD` 줄을 같이 넘긴다.

무엇을 보나.
  같은 모델(육면체 둘 · 20절점 육면체 하나 · 셸 하나 · 파트 넷)을 네 꼴로 쓴다 — 표준 · `LONG=Y` · 표준 덱에 `+` 접미사(그 키워드만
  long) · `LONG=Y` 덱에 `-` 접미사(그 키워드만 표준). 기준은 표준 꼴이다.
  S   표준 — rc 0 · 뽑힌 것을 수로 못박는다(파트 1 · 2 · 7 · 섹션 1 · 7 · 재질 1 · 2 · 7 · 아워글라스 4 · 절점 32 · 되읽기 0)
  L · P · M  나머지 세 꼴 — rc 0 · 보고가 표준 꼴과 같다(경로 · 덱 폭 칸만 뺀 전부) · 산출의 카드가 표준 꼴과 낱말 단위로 같다 ·
      `*KEYWORD` 줄과 접미사 · 카드 줄은 입력 그대로다(폭을 바꿔 쓰지 않는다)
  N   되읽기가 long 에서도 잡는다 — 없는 재질 · 없는 섹션을 가리키는 파트를 고르면 표준 꼴과 같이 rc 1 · 수 1 · 산출 없음
  V   `*PART_INERTIA` 블록의 칸 0 이 고른 PID 면 통째로 싣는다 — 표준 꼴과 같다
  R   `renumber: true` — 표준 꼴과 같다(보고 · 산출 낱말)

usage: test_extract_parts_long.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []
ZERO = {"undefined_nodes": 0, "undefined_parts": 0, "undefined_sections": 0, "undefined_materials": 0,
        "malformed_comma_lines": 0}


def check(name, cond, detail=""):
    print("  %-78s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:400]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], capture_output=True, text=True, timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def ints(w, *v):
    return "".join("%*d" % (w, n) for n in v)


def reals(w, *v):
    return "".join("%*.4g" % (w, x) for x in v)


def model(long_deck, suffix="", mid2=2, sec2=1, variant=False):
    """네 파트 — 1 · 2(육면체) · 7(20절점 육면체 · ELFORM 23) · 3(셸). `suffix` 는 일반 카드 키워드에만 붙인다."""
    wi = 20 if long_deck else 8                      # 절점 · 요소 정수 칸
    wr = 20 if long_deck else 16                     # 절점 좌표 칸
    wd = 20 if long_deck else 10                     # 덱 폭을 따르는 일반 카드 칸
    wg = 20 if (suffix == " +" or (long_deck and suffix != " -")) else 10   # 접미사를 붙인 키워드의 카드 칸

    def n(ix, iy, iz):
        return 1 + ix + 3 * iy + 6 * iz

    L = ["*KEYWORD" + (" LONG=Y" if long_deck else ""), "*NODE"]
    for iz in range(2):
        for iy in range(2):
            for ix in range(3):
                L.append("%*d%*.7f%*.7f%*.7f" % (wi, n(ix, iy, iz), wr, ix, wr, iy, wr, iz))
    for i in range(101, 121):
        L.append("%*d%*.7f%*.7f%*.7f" % (wi, i, wr, i - 100, wr, 5.0, wr, 0.0))
    L.append("%*d%*.7f%*.7f%*.7f" % (wi, 999, wr, 99.0, wr, 0.0, wr, 0.0))
    hex1 = [n(0, 0, 0), n(1, 0, 0), n(1, 1, 0), n(0, 1, 0), n(0, 0, 1), n(1, 0, 1), n(1, 1, 1), n(0, 1, 1)]
    hex2 = [n(1, 0, 0), n(2, 0, 0), n(2, 1, 0), n(1, 1, 0), n(1, 0, 1), n(2, 0, 1), n(2, 1, 1), n(1, 1, 1)]
    L += ["*ELEMENT_SOLID", ints(wi, 1, 1), ints(wi, *hex1), ints(wi, 2, 2), ints(wi, *hex2),
          ints(wi, 7, 7), ints(wi, *range(101, 111)), ints(wi, *range(111, 121))]
    L += ["*ELEMENT_SHELL", ints(wi, 30, 3, n(0, 0, 1), n(1, 0, 1), n(1, 1, 1), n(0, 1, 1))]
    L.append("*PART" + suffix)
    #                 제목                PID SECID MID EOSID HGID GRAV ADPOPT TMID
    for title, card in (("part one solid", (1, 1, 1, 0, 4, 0, 0, 0)), ("part two solid", (2, sec2, mid2, 0, 0, 0, 0, 0)),
                        ("part three shell", (3, 3, 3, 0, 0, 0, 0, 0)), ("part seven hex20", (7, 7, 7, 0, 0, 0, 0, 0))):
        L += [title, ints(wg, *card)]
    if variant:   # 칸 0 이 고른 PID 2 인 변형 블록 — 통째로 실려야 한다
        L += ["*PART_INERTIA" + suffix, "inertia of two", ints(wg, 2, 1, 2, 0, 0, 0, 0, 0),
              reals(wg, 0.5, 0.5, 0.5, 1.5) + ints(wg, 0, 0), reals(wg, 1.5, 0.0, 0.0, 1.5, 0.0, 1.5),
              reals(wg, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
    L += ["*SECTION_SOLID" + suffix, ints(wg, 1, 1)]
    L += ["*SECTION_SHELL" + suffix, ints(wg, 3, 2), reals(wg, 0.5, 0.5, 0.5, 0.5)]
    L += ["*SECTION_SOLID" + suffix, ints(wg, 7, 23)]
    for mid, e in ((1, 210000.0), (2, 70000.0), (3, 3000.0), (7, 1000.0)):
        L += ["*MAT_ELASTIC" + suffix, ints(wg, mid) + reals(wg, 7.85e-9, e, 0.3)]
    L += ["*HOURGLASS" + suffix, ints(wg, 4, 5) + reals(wg, 0.05)]
    L += ["*HOURGLASS" + suffix, ints(wg, 5, 5) + reals(wg, 0.05)]
    L += ["*SET_PART_LIST" + suffix, ints(wg, 600), ints(wg, 1, 2, 3, 7)]
    L += ["*SET_NODE_LIST" + suffix, ints(wg, 500), ints(wg, 1, 2, 4, 5, 999)]
    L += ["*CONTROL_TERMINATION", reals(wd, 1.0), "*END"]
    return "\n".join(L) + "\n"


def bare(line):
    return line.split()[0].rstrip("+-%").upper()


def cards(text):
    """산출의 카드를 폭과 무관하게 — (키워드, 데이터 줄마다 낱말). 주석은 뺀다."""
    out = []
    for l in text.splitlines():
        if l.startswith("*"):
            out.append((bare(l), []))
        elif out and not l.startswith("$") and l.strip():
            out[-1][1].append(tuple(l.split()))
    return out


def first_ids(cs, kw, every=1, skip=0):
    return sorted(int(rows[i][0]) for k, rows in cs if k == kw for i in range(skip, len(rows), every))


def extract(binary, d, tag, deck, body="parts: [1, 2, 7]\n"):
    """덱을 쓰고 extract-parts 를 돌린다 — (rc, 콘솔, 보고, 산출 글 또는 None, 입력 글)."""
    with open(os.path.join(d, tag + ".k"), "w") as f:
        f.write(deck)
    with open(os.path.join(d, tag + ".yaml"), "w") as f:
        f.write("model: %s.k\noutput: %s_out.k\n%sreport: %s.json\n" % (tag, tag, body, tag))
    rc, out = run(binary, d, "extract-parts", tag + ".yaml")
    rpath, opath = os.path.join(d, tag + ".json"), os.path.join(d, tag + "_out.k")
    rep = json.load(open(rpath)) if os.path.exists(rpath) else {}
    text = open(opath).read() if os.path.exists(opath) else None
    return rc, out, rep, text, deck


def comparable(rep):
    """보고에서 꼴마다 달라도 되는 칸(경로 · 덱 폭)을 뺀 것."""
    r = {k: v for k, v in rep.items() if k not in ("model", "output", "deck", "renumber")}
    r["parts_in_deck"] = (rep.get("deck") or {}).get("parts_in_deck")
    r["renumber_on"] = (rep.get("renumber") or {}).get("on")
    return r


def diff(a, b):
    return {k: (a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)}


SHAPES = (("L", "LONG=Y", True, "", 20), ("P", "표준 덱 + 접미사 `+`", False, " +", 8),
          ("M", "LONG=Y 덱 + 접미사 `-`", True, " -", 20))


def main():
    if len(sys.argv) < 2:
        print("usage: test_extract_parts_long.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="extract_parts_long_")
    try:
        # ── S: 표준 꼴(기준) ─────────────────────────────────────────────────
        rc, out, rs, ts, _ = extract(binary, d, "S", model(False))
        cs = cards(ts or "")
        check("S-1 표준 — rc 0 · 덱 폭 8 · 파트 넷", rc == 0 and rs.get("deck", {}).get("field_width") == 8 and
              rs.get("deck", {}).get("parts_in_deck") == 4, (rc, rs.get("deck"), out[-300:]))
        check("S-2 표준 — 요소 카드 3 · 절점 32 · 파트 3 · 섹션 1 · 7 · 재질 1 · 2 · 7 · 아워글라스 4",
              rs.get("picked") == {"element_cards": 3, "aux_element_cards": 0, "nodes": 32, "node_lines_written": 32,
                                   "parts_emitted": 3} and
              rs.get("needed") == {"sections": [1, 7], "materials": [1, 2, 7], "eos": [], "hourglass": [4]},
              (rs.get("picked"), rs.get("needed")))
        check("S-3 표준 — 되읽기 미정의 0", rs.get("verify") == ZERO, rs.get("verify"))
        check("S-4 표준 — 산출의 파트 1 · 2 · 7 · 섹션 1 · 7 · 재질 1 · 2 · 7 · 아워글라스 4 · 세트 멤버 1 · 2 · 7 · 절점 32",
              first_ids(cs, "*PART", every=2, skip=1) == [1, 2, 7] and
              first_ids(cs, "*SECTION_SOLID") == [1, 7] and first_ids(cs, "*SECTION_SHELL", every=9) == [] and
              first_ids(cs, "*MAT_ELASTIC") == [1, 2, 7] and first_ids(cs, "*HOURGLASS") == [4] and
              [r for k, rows in cs if k == "*SET_PART_LIST" for r in rows[1:]] == [("1", "2", "7")] and
              len(first_ids(cs, "*NODE")) == 32 and 999 not in first_ids(cs, "*NODE"),
              [(k, rows[:3]) for k, rows in cs if k != "*NODE"])

        # ── L · P · M: 같은 모델의 다른 꼴 ───────────────────────────────────
        for tag, what, long_deck, suffix, fw in SHAPES:
            rc, out, r, t, src = extract(binary, d, tag, model(long_deck, suffix))
            check("%s-1 %s — rc 0 · 덱 폭 %d" % (tag, what, fw),
                  rc == 0 and r.get("deck", {}).get("field_width") == fw, (rc, r.get("deck"), out[-300:]))
            check("%s-2 %s — 보고가 표준 꼴과 같다" % (tag, what), comparable(r) == comparable(rs),
                  diff(comparable(r), comparable(rs)))
            check("%s-3 %s — 산출의 카드가 표준 꼴과 낱말 단위로 같다" % (tag, what), t is not None and cards(t) == cs,
                  [x for x in zip(cards(t or ""), cs) if x[0] != x[1]][:2])
            lines, src_lines = (t or "").splitlines(), set(src.splitlines())
            check("%s-4 %s — `*KEYWORD` 줄 · 접미사 · 절점 · 요소 · 파트 카드는 입력 줄 그대로다" % (tag, what),
                  bool(lines) and lines[0] == src.splitlines()[0] and
                  all(l in src_lines for l in lines if l.startswith("*")) and
                  all(l in src_lines for k, l in ((k, l) for k, l in keyed(lines)
                                                  if k in ("*NODE", "*ELEMENT_SOLID", "*PART", "*SECTION_SOLID",
                                                           "*MAT_ELASTIC", "*HOURGLASS"))),
                  [l for l in lines if l.startswith("*") and l not in src_lines][:3])

        # ── N: 되읽기가 long 에서도 잡는다 ───────────────────────────────────
        for tag, what, kw, key in (("N1", "없는 재질(MID 9)", {"mid2": 9}, "undefined_materials"),
                                   ("N2", "없는 섹션(SECID 8)", {"sec2": 8}, "undefined_sections")):
            got = {}
            for shape, long_deck in (("s", False), ("l", True)):
                rc, out, r, t, _ = extract(binary, d, tag + shape, model(long_deck, **kw))
                got[shape] = (rc, (r.get("verify") or {}).get(key), r.get("output_written"), t is None)
            check("%s ★%s 을 가리키는 파트 — 표준 · LONG=Y 다 rc 1 · %s 1 · 산출 없음" % (tag, what, key),
                  got["s"] == (1, 1, False, True) and got["l"] == got["s"], got)

        # ── V: 파트 변형 블록 ────────────────────────────────────────────────
        got = {}
        for shape, long_deck in (("s", False), ("l", True)):
            rc, out, r, t, _ = extract(binary, d, "V" + shape, model(long_deck, variant=True))
            got[shape] = (rc, r.get("part_variant_blocks_carried_whole"), r.get("verify") == ZERO,
                          [rows for k, rows in cards(t or "") if k == "*PART_INERTIA"])
        check("V-1 `*PART_INERTIA` 의 칸 0 이 고른 PID — 표준 · LONG=Y 다 rc 0 · 블록 하나를 통째로(다섯 줄)",
              got["s"][:3] == (0, 1, True) and len(got["s"][3]) == 1 and len(got["s"][3][0]) == 5 and got["l"] == got["s"],
              got)

        # ── R: renumber ──────────────────────────────────────────────────────
        got = {}
        for shape, long_deck in (("s", False), ("l", True)):
            rc, out, r, t, _ = extract(binary, d, "R" + shape, model(long_deck), "parts: [2, 7]\nrenumber: true\n")
            got[shape] = (rc, comparable(r), cards(t or ""))
        ids = first_ids(got["s"][2], "*NODE")
        check("R-1 renumber — 표준은 rc 0 · 되읽기 0 · 절점 1..28", got["s"][0] == 0 and got["s"][1].get("verify") == ZERO and
              ids == list(range(1, 29)), (got["s"][0], got["s"][1].get("verify"), ids[:5], len(ids)))
        check("R-2 renumber — LONG=Y 가 표준과 같다(보고 · 산출 낱말)", got["l"] == got["s"],
              (got["l"][0], diff(got["l"][1], got["s"][1])))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    if FAILS:
        print("FAIL %d 항" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


def keyed(lines):
    """(지금 블록의 키워드, 데이터 줄) — 주석 · 빈 줄 · 키워드 줄은 뺀다."""
    kw = ""
    for l in lines:
        if l.startswith("*"):
            kw = bare(l)
        elif l.strip() and not l.startswith("$"):
            yield kw, l


if __name__ == "__main__":
    sys.exit(main())
