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
  W   ★인클루드의 칸 폭이 주 덱과 갈리는 덱(2026-11-21) — 산출은 주 덱의 `*KEYWORD` 한 줄 아래에 모든 파일의 카드를 그대로 싣는다.
      예전엔 long 주 덱 + 표준 폭 인클루드(제 `*KEYWORD` · `*INCLUDE -`) · 표준과 I10 이 갈리는 꼴이 rc 0 으로 폭 섞인 산출을 냈다
      (LS-DYNA 는 그 카드를 주 덱 폭으로 읽는다). 이제 고쳐 쓰는 op 의 `flatten_includes` 와 같은 규칙으로 거절한다 — 어느 파일에든
      `*INCLUDE +` · `-` 가 있거나, 인클루드가 제 `*KEYWORD` 를 갖고 그 폭이 주 덱과 다르다. rc 1 · 까닭 글 · 산출 없음.
      폭이 같은 꼴(머리 없는 인클루드 · 같은 폭의 제 `*KEYWORD` · 키워드 접미사 `%`)은 그대로 rc 0 이다. 읽지 않는 줄(`*END` 뒤)은 안 본다
  B   ★파일 맨 앞의 UTF-8 BOM(2026-11-21) — 윈도우 편집기가 붙이는 세 바이트다. 인클루드 닫힘 · 주 덱 리더는 떼는데 extract-parts 의
      제 걸음(색인 · 요소 훑기 · 쓰기 · 되읽기)은 안 뗐다 — 첫 줄이 키워드 줄로 안 읽혀, BOM 으로 시작하는 인클루드의 첫 줄이
      `*ELEMENT_SOLID` 면 **rc 0 으로 고른 요소 하나가 빠진 덱**을 썼고, `*NODE` · `*PART` 면 rc 1, `LONG=Y` 주 덱이면 폭을 못 읽어
      rc 1 이었다. 이제 BOM 이 있는 덱의 보고 · 산출이 BOM 없는 쌍둥이와 **바이트까지 같다**(산출에 BOM 은 싣지 않는다)

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
BOM = b"\xef\xbb\xbf"
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


def split3(text):
    """model() 의 글을 (머리 — 절점 · 요소, 가운데 — 파트 · 섹션 · 재질 · 세트, 꼬리 — `*CONTROL_TERMINATION` 부터)로."""
    L = text.splitlines()
    a = next(i for i, l in enumerate(L) if l.startswith("*PART"))
    b = next(i for i, l in enumerate(L) if l.startswith("*CONTROL_TERMINATION"))
    return L[:a], L[a:b], L[b:]


def i10_pair(main_head, main_w, inc_head, inc_w, suffix=""):
    """(주 덱, 인클루드) — 인클루드가 절점과 요소 1(파트 1) · 2(파트 2)를 제 폭으로, 주 덱이 요소 3(파트 2)을 제 폭으로 갖는다."""
    def n(x, y, z):
        return 1 + x + 4 * y + 8 * z

    def elems(w, sfx, *pairs):
        L = ["*ELEMENT_SOLID" + sfx]
        for eid, pid, ix in pairs:
            L += [ints(w, eid, pid), ints(w, n(ix, 0, 0), n(ix + 1, 0, 0), n(ix + 1, 1, 0), n(ix, 1, 0),
                                           n(ix, 0, 1), n(ix + 1, 0, 1), n(ix + 1, 1, 1), n(ix, 1, 1))]
        return L

    inc = ([inc_head] if inc_head else []) + ["*NODE" + suffix]
    inc += ["%*d%16.7f%16.7f%16.7f" % (inc_w, n(ix, iy, iz), ix, iy, iz)
            for iz in range(2) for iy in range(2) for ix in range(4)]
    inc += elems(inc_w, suffix, (1, 1, 0), (2, 2, 1))
    main = [main_head, "*INCLUDE", "inc.k"] + elems(main_w, "", (3, 2, 2))
    main += ["*PART", "p1", ints(10, 1, 1, 1), "*PART", "p2", ints(10, 2, 1, 1), "*SECTION_SOLID", ints(10, 1, 1),
             "*MAT_ELASTIC", ints(10, 1) + reals(10, 7.85e-9, 2.1e5, 0.3), "*END"]
    return main, inc


def extract_tree(binary, d, tag, files, parts, bom=()):
    """폴더 하나에 파일들을 쓰고(`main.k` 가 주 덱) extract-parts 를 돌린다 — (rc, 콘솔, 보고, 산출 글 또는 None).
    `bom` 에 든 이름의 파일은 UTF-8 BOM 으로 시작한다."""
    sub = os.path.join(d, tag)
    os.makedirs(sub)
    for name, lines in files.items():
        with open(os.path.join(sub, name), "wb") as f:
            f.write((BOM if name in bom else b"") + ("\n".join(lines) + "\n").encode("ascii"))
    with open(os.path.join(sub, "x.yaml"), "w") as f:
        f.write("model: main.k\noutput: out.k\nparts: %s\nreport: rep.json\n" % parts)
    rc, out = run(binary, sub, "extract-parts", "x.yaml")
    rpath, opath = os.path.join(sub, "rep.json"), os.path.join(sub, "out.k")
    rep = json.load(open(rpath)) if os.path.exists(rpath) else {}
    return rc, out, rep, (open(opath).read() if os.path.exists(opath) else None)


def width_mix_cases():
    """(이름표, 무엇, 파일들, 고를 파트, 기대) — 기대는 "same"(표준 기준과 낱말 같음) · "two"(파트 2 의 요소 둘) · 거절 까닭의 한 토막."""
    sh, sm, st = split3(model(False))
    lh, lm, lt = split3(model(True))

    def tree(head, mid, tail, inc_head=None, sfx=""):
        return {"main.k": head + ["*INCLUDE" + sfx, "inc.k"] + tail, "inc.k": ([inc_head] if inc_head else []) + mid}

    def pair(*a):
        main, inc = i10_pair(*a)
        return {"main.k": main, "inc.k": inc}

    std_kw, long_kw, i10_kw = "*KEYWORD", "*KEYWORD LONG=Y", "*KEYWORD I10=Y"
    return (
        ("Wa", "표준 + 표준(머리 없음)", tree(sh, sm, st), "[1, 2, 7]", "same"),
        ("Wb", "long + long(머리 없음)", tree(lh, lm, lt), "[1, 2, 7]", "same"),
        ("Wc", "long + long(제 `*KEYWORD LONG=Y`)", tree(lh, lm, lt, long_kw), "[1, 2, 7]", "same"),
        ("Wd", "★long + 표준(제 `*KEYWORD`)", tree(lh, sm, lt, std_kw), "[1, 2, 7]", "inc.k 의 *KEYWORD 폭(8)이 주 덱(20)"),
        ("We", "표준 + long(제 `*KEYWORD LONG=Y`)", tree(sh, lm, st, long_kw), "[1, 2, 7]",
         "inc.k 의 *KEYWORD 폭(20)이 주 덱(8)"),
        ("Wf", "표준 + long(머리 없음 · `*INCLUDE +`)", tree(sh, lm, st, None, " +"), "[1, 2, 7]", "*INCLUDE + / *INCLUDE -"),
        ("Wg", "★long + 표준(머리 없음 · `*INCLUDE -`)", tree(lh, sm, lt, None, " -"), "[1, 2, 7]", "*INCLUDE + / *INCLUDE -"),
        ("Wh", "★표준 + I10(제 `*KEYWORD I10=Y`)", pair(std_kw, 8, i10_kw, 10), "[2]", "inc.k 의 *KEYWORD 폭(10)이 주 덱(8)"),
        ("Wi", "★I10 + 표준(제 `*KEYWORD`)", pair(i10_kw, 10, std_kw, 8), "[2]", "inc.k 의 *KEYWORD 폭(8)이 주 덱(10)"),
        ("Wj", "I10 + I10(머리 없음)", pair(i10_kw, 10, None, 10), "[2]", "two"),
        ("Wk", "표준 + I10(머리 없음 · 키워드 접미사 `%`)", pair(std_kw, 8, None, 10, " %"), "[2]", "two"),
        ("Wl", "I10 + I10(제 `*KEYWORD I10=Y`)", pair(i10_kw, 10, i10_kw, 10), "[2]", "two"),
        ("Wm", "표준 + 표준(제 `*KEYWORD`)", pair(std_kw, 8, std_kw, 8), "[2]", "two"),
        # 안쪽 인클루드의 부호 — long 주 덱 → 머리 없는 mid.k → `*INCLUDE -` 로 표준 폭 파일
        ("Wn", "★long → mid.k → `*INCLUDE -` 표준", {"main.k": lh + ["*INCLUDE", "mid.k"] + lt, "mid.k": ["*INCLUDE -", "inc.k"],
                                                  "inc.k": sm}, "[1, 2, 7]", "mid.k 에 *INCLUDE + / - 가 있다"),
        # 읽지 않는 줄은 안 본다 — 인클루드의 `*END` 뒤 · 주 덱의 `*END` 뒤(닫힘도 거기서 멈춘다)
        ("Wo", "long + long · 인클루드 `*END` 뒤 표준 `*KEYWORD` · `*INCLUDE -`",
         tree(lh, lm + ["*END", std_kw, "*INCLUDE -", "none.k"], lt), "[1, 2, 7]", "same"),
        ("Wp", "long + long · 주 덱 `*END` 뒤 `*INCLUDE -`", tree(lh, lm, lt + ["*INCLUDE -", "none.k"]), "[1, 2, 7]", "same"),
    )


def bom_cases():
    """(이름표, 무엇, 파일들, BOM 을 붙일 파일[, 고를 파트]) — 고를 파트가 없으면 1 · 2 · 7 이고 산출을 표준 기준과도 견준다."""
    sh, sm, st = split3(model(False))
    lh, lm, lt = split3(model(True))
    e = sh.index("*ELEMENT_SOLID")
    nodes, elems = sh[1:e], sh[e:]            # `*NODE` 블록 · 요소 블록 둘
    inc = ["*INCLUDE", "inc.k"]
    return (
        ("Ba", "★인클루드 첫 줄이 `*ELEMENT_SOLID`", {"main.k": sh[:e] + inc + sm + st, "inc.k": elems}, ("inc.k",)),
        ("Bb", "★인클루드 첫 줄이 `*NODE`", {"main.k": sh[:1] + inc + elems + sm + st, "inc.k": nodes}, ("inc.k",)),
        ("Bc", "인클루드 첫 줄이 `$` 주석", {"main.k": sh[:1] + inc + elems + sm + st, "inc.k": ["$ nodes"] + nodes}, ("inc.k",)),
        ("Bd", "인클루드 첫 줄이 `*KEYWORD`", {"main.k": sh[:1] + inc + elems + sm + st, "inc.k": ["*KEYWORD"] + nodes},
         ("inc.k",)),
        ("Be", "★인클루드 첫 줄이 `*PART`", {"main.k": sh + inc + st, "inc.k": sm}, ("inc.k",)),
        ("Bf", "★주 덱(표준 · 인클루드 없음)", {"main.k": sh + sm + st}, ("main.k",)),
        ("Bg", "★주 덱(`LONG=Y` · 인클루드 없음)", {"main.k": lh + lm + lt}, ("main.k",)),
        ("Bh", "★주 덱과 인클루드 둘 다", {"main.k": sh + inc + st, "inc.k": sm}, ("main.k", "inc.k")),
        # 파트 1 의 요소가 두 파일에 나뉜다 — 주 덱에 요소 1, 맨 앞에서 부르는 인클루드에 요소 2(PID 를 1 로 · 첫 줄 `*ELEMENT_SOLID`)와
        # 절점. 예전엔 rc 0 · 되읽기 0 으로 인클루드 쪽 요소가 빠진 덱을 썼다(조용히 빠짐 — 2026-11-21 고치기 전 판으로 쟀다)
        ("Bi", "★★고른 파트의 요소가 주 덱과 인클루드에 나뉜다",
         {"main.k": sh[:1] + inc + elems[:3] + elems[5:] + sm + st, "inc.k": [elems[0], ints(8, 2, 1), elems[4]] + nodes},
         ("inc.k",), "[1]"),
    )


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

        # ── W: 인클루드의 칸 폭이 주 덱과 갈리는 덱 ──────────────────────────
        for tag, what, files, parts, want in width_mix_cases():
            rc, out, r, t = extract_tree(binary, d, tag, files, parts)
            if want == "same":
                check("%s %s — rc 0 · 되읽기 0 · 산출이 표준 기준과 낱말 단위로 같다" % (tag, what),
                      rc == 0 and r.get("verify") == ZERO and t is not None and cards(t) == cs,
                      (rc, r.get("verify"), r.get("refusals"), out[-300:]))
            elif want == "two":
                got = [rows[i][0] for k, rows in cards(t or "") if k == "*ELEMENT_SOLID" for i in range(0, len(rows), 2)]
                check("%s %s — rc 0 · 되읽기 0 · 파트 2 의 요소 2 · 3 · `*KEYWORD` 줄은 주 덱 것" % (tag, what),
                      rc == 0 and r.get("verify") == ZERO and sorted(got) == ["2", "3"] and
                      (t or "").splitlines()[:1] == files["main.k"][:1], (rc, r.get("verify"), got, r.get("refusals"), out[-300:]))
            else:
                ref = r.get("refusals") or [{}]
                check("%s %s — rc 1 · 까닭이 폭이다 · 산출 없음" % (tag, what),
                      rc == 1 and t is None and r.get("output_written") is False and ref[0].get("kind") == "include" and
                      "칸 폭이 주 덱과 섞인다" in ref[0].get("message", "") and want in ref[0].get("message", "") and
                      want in out, (rc, t is None, ref, out[-300:]))

        # ── B: 파일 맨 앞의 UTF-8 BOM ────────────────────────────────────────
        def out_bytes(tag):
            path = os.path.join(d, tag, "out.k")
            return open(path, "rb").read() if os.path.exists(path) else None

        def facts(r):
            return {k: r.get(k) for k in ("picked", "needed", "verify", "refusals")}

        for tag, what, files, bom, *rest in bom_cases():
            parts = rest[0] if rest else "[1, 2, 7]"
            rc0, out0, r0, t0 = extract_tree(binary, d, tag + "0", files, parts)
            rc, out, r, t = extract_tree(binary, d, tag, files, parts, bom=bom)
            b0, b = out_bytes(tag + "0"), out_bytes(tag)
            if rest:
                got = [rows[i][0] for k, rows in cards(t0 or "") if k == "*ELEMENT_SOLID" for i in range(0, len(rows), 2)]
                check("%s-0 %s — BOM 없는 쌍둥이는 rc 0 · 되읽기 0 · 파트 1 의 요소 1 · 2 를 다 싣는다" % (tag, what),
                      rc0 == 0 and r0.get("verify") == ZERO and sorted(got) == ["1", "2"] and
                      (r0.get("picked") or {}).get("element_cards") == 2, (rc0, r0.get("verify"), got, r0.get("picked")))
            else:
                check("%s-0 %s — BOM 없는 쌍둥이는 rc 0 · 되읽기 0 · 산출이 표준 기준과 낱말 단위로 같다" % (tag, what),
                      rc0 == 0 and r0.get("verify") == ZERO and t0 is not None and cards(t0) == cs and
                      r0.get("picked") == rs.get("picked"), (rc0, r0.get("verify"), r0.get("picked"), out0[-300:]))
            check("%s-1 %s — BOM 이 있어도 rc 0 · 되읽기 0" % (tag, what), rc == 0 and r.get("verify") == ZERO,
                  (rc, r.get("verify"), r.get("refusals"), out[-300:]))
            check("%s-2 %s — 보고의 고른 수 · 딸린 것 · 되읽기가 쌍둥이와 같다" % (tag, what), facts(r) == facts(r0),
                  diff(facts(r), facts(r0)))
            check("%s-3 %s — 산출이 쌍둥이와 바이트까지 같다(BOM 을 싣지 않는다)" % (tag, what),
                  b is not None and b == b0 and BOM not in b,
                  (None if b is None else (len(b), b[:12]), None if b0 is None else (len(b0), b0[:12])))
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
