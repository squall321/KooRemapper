#!/usr/bin/env python3
# 새 PID 가 `*PART` 변형이 정의한 PID 위로 나는지 보는 회귀 시험
"""새 파트 번호(PID)가 **`*PART` 변형**이 정의한 PID 위로 나는가 — 가리키기만 하는 키워드에는 끌려가지 않는가.

왜 이 시험이 있나 (2026-10-16).

  PID 커서는 `KFileReader` 가 담은 파트에서만 셌는데 그 리더는 맨 `*PART`(·`_TITLE`)만 읽는다. 재현 —
  `*PART_CONTACT 3` 이 있는 덱에 czm 이 응집 파트를 **PID 3** 으로 냈다(rc 0). PID 는 한 번호 공간이다.
  지금은 변형의 정의 꼴을 매뉴얼대로 읽는다(Vol_I 215905-216095 · 217025 · 218569).

무엇을 보나(`two_hex_2part.k` — PID 1·2 · czm 이 새 PID 하나를 낸다).
  A `*PART_CONTACT` PID 3 → 새 PID 4
  B `*PART_INERTIA` PID 5(관성 카드 셋) → 새 PID 6
  C1 `*PART_COMPOSITE` + 선택 카드(`OPTCARD`) PID 7 → 새 PID 8
  C2 `*PART_COMPOSITE` 선택 카드 없이 PID 7 → 새 PID 8
  D `*PART_STACKED_ELEMENTS` 층 파트 10·11 → 새 PID 12
  E `*PART_MOVE` 둘째 줄이 PID 50 을 **가리킨다** → 새 PID 3 (정의가 아니다 — 끌려가지 않는다).
    ⚠ 처음엔 한 줄짜리 `*PART_MODES` 로 썼다가 무력화(「모든 `*PART_` 를 정의로」)를 **못 잡았다** — 정의 꼴은
    첫 줄을 제목으로 넘기므로 한 줄짜리는 우연히 통과한다. 둘째 줄이 있어야 문다
  F 인클루드 안의 `*PART_CONTACT` PID 13 → 새 PID 14

usage: test_pid_part_variants.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def card(*v):
    return "".join("%10s" % x for x in v)


CONTACT_CARD = card("0.0", "0.0", "0.0", "0.0", "0.0", 0, "0.0", "0.0")
CASES = [
    ("A *PART_CONTACT", ["*PART_CONTACT", "contact part", card(3, 1, 1), CONTACT_CARD], {}, 4),
    ("B *PART_INERTIA", ["*PART_INERTIA", "rigid lump", card(5, 1, 1),
                         card("0.0", "0.0", "0.0", "1.0", 0, 0), card("1.0", "0.0", "0.0", "1.0", "0.0", "1.0"),
                         card("0.0", "0.0", "0.0", "0.0", "0.0", "0.0")], {}, 6),
    ("C1 *PART_COMPOSITE + OPTCARD", ["*PART_COMPOSITE", "laminate", "OPTCARD" + " " * 3 + card(0),
                                      card(7, 2, "0.833", 0, "0.0", 0, 0, 0),
                                      card(1, "0.5", "0.0", 0, 1, "0.5", "0.0", 0)], {}, 8),
    ("C2 *PART_COMPOSITE", ["*PART_COMPOSITE", "laminate", card(7, 2, "0.833", 0, "0.0", 0, 0, 0),
                            card(1, "0.5", "0.0", 0, 1, "0.5", "0.0", 0)], {}, 8),
    ("D *PART_STACKED_ELEMENTS", ["*PART_STACKED_ELEMENTS", "stack", card(1, 0, 0),
                                  card(10, 1, 1, "0.5"), card(11, 1, 1, "0.5")], {}, 12),
    ("E *PART_MOVE 는 가리킬 뿐", ["*PART_MOVE", card(1, "0.0", "0.0", "1.0"), card(50, "0.0", "0.0", "1.0")],
     {}, 3),
    ("F 인클루드 안", ["*INCLUDE", "parts.k"],
     {"parts.k": "\n".join(["*KEYWORD", "*PART_CONTACT", "contact part", card(13, 1, 1), CONTACT_CARD,
                            "*END"]) + "\n"}, 14),
]
YAML = "base_model: deck.k\noutput: out\noperations:\n  - type: disconnect\n    mode: czm\n    target_pid: 0\n"


def new_pid(path):
    """czm 이 낸 응집 파트(제목 `Cohesive interface`)의 PID."""
    L = open(path, encoding="utf-8", errors="replace").read().splitlines()
    for i, l in enumerate(L):
        if l.strip() == "Cohesive interface":
            for d in L[i + 1:]:
                if d.strip() and not d.lstrip().startswith("$"):
                    return int(re.match(r"\s*(-?\d+)", d).group(1))
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    base = open(os.path.join(REPO, "examples", "disconnect", "two_hex_2part.k"),
                encoding="utf-8").read().splitlines()
    end = next(i for i, l in enumerate(base) if l.strip().upper() == "*END")
    for label, extra, files, want in CASES:
        print("[%s]" % label)
        d = tempfile.mkdtemp(prefix="ppv_")
        try:
            open(os.path.join(d, "deck.k"), "w", encoding="utf-8").write(
                "\n".join(base[:end] + extra + base[end:]) + "\n")
            for name, body in files.items():
                open(os.path.join(d, name), "w", encoding="utf-8").write(body)
            open(os.path.join(d, "c.yaml"), "w", encoding="utf-8").write(YAML)
            r = subprocess.run([binary, "assemble", "c.yaml"], cwd=d, capture_output=True, text=True,
                               timeout=300, encoding="utf-8", errors="replace")
            out = os.path.join(d, "out.k")
            if not check("%s — rc 0" % label, r.returncode == 0 and os.path.exists(out),
                         (r.stdout + r.stderr)[-300:]):
                continue
            got = new_pid(out)
            check("%s — 새 PID %d" % (label, want), got == want, "새 PID=%s" % got)
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
