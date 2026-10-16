#!/usr/bin/env python3
# load 가 `*DEFINE_CURVE_TITLE` 의 LCID 위로 새 곡선을 내는지 보는 회귀 시험
"""`load` 가 새 곡선 LCID 를 `*DEFINE_CURVE_TITLE` 의 LCID **위로** 내는가.

왜 이 시험이 있나 (2026-10-16).

  `ld_findMaxCurveId` 가 `*DEFINE_CURVE_TITLE` 의 **제목줄을 LCID 줄로** 읽었다. 제목이 글자면 읽기가
  실패해 그 곡선의 LCID 를 못 셌고, 새 곡선이 그 번호를 **다시** 냈다 — 재현: 덱의
  `*DEFINE_CURVE_TITLE` LCID 1 옆에 load 가 `*DEFINE_CURVE` LCID 1 을 또 냈다(rc 0). 같은 LCID 가 둘이면
  LS-DYNA 는 키워드 단계에서 멈춘다. `ld_findMaxSetSegmentId` 가 2026-09-28 에 고친 것과 **같은 맹점**이고,
  같은 파일의 `mw_scanMaxId`(matswap)는 이미 건넌다 — 그 규약을 옮겼다.

무엇을 보나(덱 `two_hex_2part.k` 의 PID 2 윗면에 압력 하나).
  A 주 덱의 `*DEFINE_CURVE_TITLE` LCID 1(제목은 글자) → 새 LCID 2
  B 숫자로 시작하는 제목(`999 ramp`) LCID 1 → 새 LCID 2 (옛 판은 제목을 999 로 읽었다)
  C 제목 없는 `*DEFINE_CURVE` LCID 5 → 새 LCID 6 (바뀌지 않는 갈래)
  D 인클루드 안의 `*DEFINE_CURVE_TITLE` LCID 7 → 새 LCID 8 (인클루드 커서도 같은 스캐너다)

usage: test_curve_title_ids.py <KooRemapper 바이너리>
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


def curve(lcid, title=None):
    kw = "*DEFINE_CURVE_TITLE" if title is not None else "*DEFINE_CURVE"
    return ([kw] + ([title] if title is not None else []) +
            ["%10d" % lcid, "%20.6f%20.6f" % (0.0, 0.0), "%20.6f%20.6f" % (1.0, 1.0)])


def lcids(path):
    """산출 덱의 곡선 LCID 목록(제목줄을 건너뛴 첫 데이터 줄)."""
    L = open(path, encoding="utf-8", errors="replace").read().splitlines()
    out = []
    for i, l in enumerate(L):
        u = l.strip().upper()
        if not u.startswith("*DEFINE_CURVE"):
            continue
        skip = 1 if "_TITLE" in u else 0
        for d in L[i + 1:]:
            if d.startswith("*"):
                break
            if not d.strip() or d.lstrip().startswith("$"):
                continue
            if skip:
                skip -= 1
                continue
            out.append(int(re.match(r"\s*(-?\d+)", d).group(1)))
            break
    return out


YAML = ("base_model: deck.k\noutput: out\noperations:\n"
        "  - type: load\n    loads:\n      - part: 2\n        mode: pressure\n        value: 1.0\n"
        "        direction: [0, 0, 1]\n        select: direction\n        angle: 45.0\n"
        "        curve:\n          - [0.0, 0.0]\n          - [0.001, 1.0]\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    base = open(os.path.join(REPO, "examples", "disconnect", "two_hex_2part.k"),
                encoding="utf-8").read().splitlines()
    k = next(i for i, l in enumerate(base) if l.upper().startswith("*KEYWORD"))
    cases = [
        ("A 제목 있는 곡선(글자 제목)", curve(1, "existing ramp"), {}, 2),
        ("B 숫자로 시작하는 제목", curve(1, "999 ramp"), {}, 2),
        ("C 제목 없는 곡선", curve(5), {}, 6),
        ("D 인클루드 안의 제목 있는 곡선", ["*INCLUDE", "curves.k"],
         {"curves.k": "\n".join(["*KEYWORD"] + curve(7, "include ramp") + ["*END"]) + "\n"}, 8),
    ]
    for label, extra, files, want in cases:
        print("[%s]" % label)
        d = tempfile.mkdtemp(prefix="cti_")
        try:
            open(os.path.join(d, "deck.k"), "w", encoding="utf-8").write(
                "\n".join(base[:k + 1] + extra + base[k + 1:]) + "\n")
            for name, body in files.items():
                open(os.path.join(d, name), "w", encoding="utf-8").write(body)
            open(os.path.join(d, "c.yaml"), "w", encoding="utf-8").write(YAML)
            r = subprocess.run([binary, "assemble", "c.yaml"], cwd=d, capture_output=True, text=True,
                               timeout=300, encoding="utf-8", errors="replace")
            out = os.path.join(d, "out.k")
            if not check("%s — rc 0" % label, r.returncode == 0 and os.path.exists(out),
                         (r.stdout + r.stderr)[-300:]):
                continue
            got = lcids(out)
            before = set(lcids(os.path.join(d, "deck.k")))
            new = [x for x in got if x not in before] if not label.startswith("D") else got
            check("%s — 새 LCID %d" % (label, want), new == [want], "산출 LCID=%s" % got)
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
