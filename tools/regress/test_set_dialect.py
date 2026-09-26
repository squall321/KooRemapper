#!/usr/bin/env python3
"""`*SET_*` 방언을 뜻대로 읽는가 — `_GENERATE` 는 **범위쌍**이고 `_ADD` 는 **세트 ID** 다 (P1-12).

왜 이 시험이 있나 (2026-09-26):

  `ct_parseSets` 는 데이터 줄의 모든 토큰을 멤버 ID 로 읽었다. 그래서
  `*SET_PART_LIST_GENERATE 7 / 1 5` 가 **파트 1 과 5** 로 읽혔다(뜻은 파트 1~5 다).
  더 나쁜 것은 type 판정이었다 — 예전 코드는 `_LIST` 를 찾아 **그 앞만** 남겼으므로
  매뉴얼 정규 철자에서 방언이 통째로 사라지고 `type` 이 "PART" 가 됐다. 그러면 소비자
  (`resolvePids`·`mm_resolveSide`·`opt_contactInvolvesPid`)가 그 틀린 멤버를 **그대로 쓴다**.
  실측: 그 세트를 가리키는 접촉의 `modelmeta` 연결 변이 2개가 아니라 **1개**로 나왔다.

매뉴얼 근거 (Vol_I `*SET` 페이지) —
  · Card 2b(GENERATE): `B1BEG B1END B2BEG B2END …` 한 줄에 **범위 4쌍**
  · Card 2c(GENERATE_INCREMENT): `BBEG BEND INCR` 한 줄에 범위 하나
  · Card 2d(GENERAL): 첫 칸이 **옵션 코드**(ALL·BOX·DELETE…)라 개체 ID 가 아니다
  · `*SET_PART_ADD`·`*SET_SHELL_INTERSECT`: 멤버가 **세트 ID** 다

뜻을 확정하지 못하는 방언은 `ids` 를 **비워 둔다**. 채워 두면 소비자가 파트 ID 로 쓴다 —
닫히는 쪽으로 실패하는 것이 규율이다.

usage: test_set_dialect.py <KooRemapper 바이너리>
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODEL = os.path.join(ROOT, "examples", "contact", "model.k")


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:400]) if detail else ""))


def main():
    if len(sys.argv) < 2:
        print("usage: test_set_dialect.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    if not os.path.exists(MODEL):
        print("fixture not found: " + MODEL)
        return 2
    d = tempfile.mkdtemp(prefix="setdial_")
    base = open(MODEL, encoding="utf-8", errors="replace").read()

    def deck(name, cards):
        p = os.path.join(d, name)
        open(p, "w", newline="\n").write(base.replace("*END", cards + "*END", 1))
        return p

    def analyze(path):
        y = path[:-2] + ".yaml"
        open(y, "w").write("model: %s\n\ncontacts:\n  - action: analyze\n" % os.path.basename(path))
        p = subprocess.run([binary, "contact", os.path.basename(y)], cwd=d,
                           capture_output=True, text=True, timeout=300)
        return p.returncode, p.stdout + p.stderr

    def setline(out, sid):
        for l in out.splitlines():
            m = re.search(r"^\s+SET_(\S+)\s+%d:\s*(.*)$" % sid, l)
            if m:
                return m.group(1), m.group(2).strip()
        return None, None

    print("[A `_GENERATE` 계열을 범위로 펼친다]")
    cases = [
        # ⚠ 기대값이 "1~5 전부" 가 아니다. 매뉴얼: "All **defined** ID's between and including
        # B[N]BEG to B[N]END are added to the set. B[N]BEG and B[N]END may simply be **limits on
        # the ID's**." 예제 덱의 파트는 1·2·3 뿐이므로 4·5 는 멤버가 아니다. 그대로 펼치면
        # `1 999999` 짜리 덱에서 없는 파트 백만 개를 만들어 낸다.
        ("A-1 _LIST_GENERATE 1 5 → 정의된 파트만(1·2·3)",
         "*SET_PART_LIST_GENERATE\n         7\n         1         5\n", 7,
         "PART_GENERATE", "3 entries (범위 1-5"),
        ("A-2 한 줄에 범위 두 쌍",
         "*SET_PART_LIST_GENERATE\n        13\n         1         2         3         9\n", 13,
         "PART_GENERATE", "3 entries (범위 1-2, 3-9"),
        ("A-3 _GENERATE_INCREMENT 1 9 2 → 1·3 만 정의돼 있다",
         "*SET_PART_LIST_GENERATE_INCREMENT\n        11\n         1         9         2\n", 11,
         "PART_GENERATE_INCREMENT", "2 entries (범위 1-9/2"),
        ("A-4 END 가 비면 홑개다",
         "*SET_PART_LIST_GENERATE\n        14\n         2\n", 14,
         "PART_GENERATE", "1 entries (범위 2-2"),
        ("A-5 _GENERATE_TITLE — 제목줄을 세지 않는다",
         "*SET_PART_LIST_GENERATE_TITLE\nTwo ranges\n        15\n         2         3\n", 15,
         "PART_GENERATE", "2 entries (범위 2-3"),
    ]
    for i, (name, cards, sid, want_t, want_m) in enumerate(cases):
        rc, out = analyze(deck("a%d.k" % i, cards))
        t, m = setline(out, sid)
        check(name, t == want_t and m.startswith(want_m) if m else False,
              "type=%r 멤버=%r (기대 %r / %r)" % (t, m, want_t, want_m))
        check("   " + name.split()[0] + " rc=0", rc == 0, out[-300:])

    print("[B 뜻을 확정하지 못하는 방언은 **비워 둔다**]")
    unknown = [
        ("B-1 _ADD — 멤버가 세트 ID 다", "*SET_PART_ADD\n         9\n         7         8\n", 9, "PART_ADD"),
        ("B-2 _GENERAL — 멤버가 옵션 코드다",
         "*SET_PART_LIST_GENERAL\n        12\n       ALL\n", 12, "PART_GENERAL"),
        ("B-3 _INTERSECT", "*SET_SHELL_INTERSECT\n        16\n         1         2\n", 16, "SHELL_INTERSECT"),
    ]
    for i, (name, cards, sid, want_t) in enumerate(unknown):
        rc, out = analyze(deck("b%d.k" % i, cards))
        t, m = setline(out, sid)
        check(name, t == want_t and m is not None and "미확정" in m,
              "type=%r 멤버=%r" % (t, m))

    print("[C 평범한 세트는 그대로다]")
    rc, out = analyze(deck("c0.k", "*SET_PART_LIST\n         8\n         1         2         3\n"))
    t, m = setline(out, 8)
    check("C-1 *SET_PART_LIST 불변", t == "PART" and m.startswith("3 entries [1, 2, 3]"),
          "type=%r 멤버=%r" % (t, m))
    rc, out = analyze(MODEL if False else deck("c1.k", ""))
    t, m = setline(out, 10)
    check("C-2 예제 덱의 *SET_PART_LIST_TITLE 불변",
          t == "PART" and m.startswith("3 entries [1, 2, 3]"), "type=%r 멤버=%r" % (t, m))

    print("[D 하류가 실제로 달라진다 — 연결 변]")
    # SSTYP=2 로 GENERATE 세트(1~3)를 가리키는 접촉. 마스터는 파트 3 이므로 변은 1-3, 2-3 둘이다.
    # 수정 전에는 세트가 {1,3} 으로 읽혀 변이 1-3 **하나**였다.
    cards = ("*SET_PART_LIST_GENERATE\n         7\n         1         3\n"
             "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TITLE\nGen_to_part\n"
             "         7         3         2         3         0         0         0         0\n"
             "       0.2       0.1       0.0       0.0       0.0         0       0.0  1.00E+20\n"
             "       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0\n")
    p = deck("d0.k", cards)
    open(os.path.join(d, "mm.yaml"), "w").write("model: d0.k\ndetect: false\n")
    r = subprocess.run([binary, "modelmeta", "mm.yaml"], cwd=d,
                       capture_output=True, text=True, timeout=300)
    jp = os.path.join(d, "d0_modelmeta.json")
    if not os.path.exists(jp):
        check("D-1 modelmeta 가 돌았다", False, r.stdout + r.stderr)
    else:
        e = json.load(open(jp))["connectivity"]["contact_edges"]
        pairs = sorted((x["a"], x["b"]) for x in e if x.get("title") == "Gen_to_part")
        check("D-1 GENERATE 세트가 변 2개로 풀린다", pairs == [(1, 3), (2, 3)], "변=%r" % pairs)
        check("   D-1 unresolved_sides 0",
              json.load(open(jp))["connectivity"]["unresolved_sides"] == 0, r.stdout[-200:])

    print("[E 한계값이 터무니없이 커도 없는 개체를 만들지 않는다]")
    # 이것이 범위를 펼치지 않는 이유다 — 그대로 펼치면 없는 파트 백만 개가 멤버가 된다.
    rc, out = analyze(deck("e0.k", "*SET_PART_LIST_GENERATE\n        17\n         1   9999999\n"))
    t, m = setline(out, 17)
    check("E-1 1-9999999 이라도 정의된 파트 3개만", m is not None and m.startswith("3 entries"),
          "멤버=%r" % m)
    check("   E-1 rc=0 (죽지 않는다)", rc == 0, out[-200:])
    check("   E-1 한계값임을 말한다", m is not None and "한계값" in m, "멤버=%r" % m)

    print("[F 요소 종류는 아직 좁히지 못한다 — 넘겨짚지 않고 말한다]")
    rc, out = analyze(deck("f0.k", "*SET_SOLID_LIST_GENERATE\n        18\n         1         5\n"))
    t, m = setline(out, 18)
    check("F-1 *SET_SOLID_..._GENERATE 는 미확정",
          t == "SOLID_GENERATE" and m is not None and "미확정" in m, "type=%r 멤버=%r" % (t, m))

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
