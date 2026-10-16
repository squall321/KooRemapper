#!/usr/bin/env python3
# 새 MID 가 리더가 모르는 재질 종류의 MID 위로 나는지 보는 회귀 시험
"""새 재질 번호(MID)가 **리더가 모르는 재질 종류**의 MID 위로 나는가 — 그리고 TMID·`*MAT_ADD_*` 에 끌려가지 않는가.

왜 이 시험이 있나 (2026-10-16).

  `ModelAssembler` 의 MID 커서는 `KFileReader` 가 담은 재질에서만 셌다. 그 리더는 재질 **다섯 종류**
  (ELASTIC·024·RIGID·VISCOELASTIC·MOONEY-RIVLIN)만 읽는다. 재현 — `*MAT_PLASTIC_KINEMATIC 2` 가 있는 덱에
  czm 이 `*MAT_COHESIVE_MIXED_MODE 2` 를 냈다(rc 0). MID 는 재질 종류를 가리지 않는 한 번호 공간이다
  (`*PART` 가 종류 없이 MID 만 적는다) — 같은 MID 가 둘이면 LS-DYNA 는 키워드 단계에서 멈춘다.
  지금은 덱의 `*MAT_*` 전부를 칸으로 읽어 그 위로 낸다.

  빼는 것도 본다 — 매뉴얼대로.
    · `*MAT_THERMAL_*` 의 TMID 는 MID 와 **독립된** 번호다(Vol II 159546-159548 「identical TMID and MID
      numbers may exist」). 그것에 끌려가면 번호가 이유 없이 움직인다
    · `*MAT_ADD_*` 는 새 MID 를 정의하지 않는다 — 있는 재질에 덧붙이고, 몇몇은 첫 칸이 PID 다

무엇을 보나(`two_hex_2part.k` — MAT_ELASTIC 1 하나 · czm 이 새 MID 하나를 낸다).
  A 리더가 모르는 `*MAT_PLASTIC_KINEMATIC 2` → 새 MID 3
  B `*MAT_THERMAL_ISOTROPIC` TMID 50 → 새 MID 2 (끌려가지 않는다)
  C `*MAT_ADD_THERMAL_EXPANSION` PID 77 → 새 MID 2 (PID 를 MID 로 세지 않는다)
  D 칸이 붙은 카드 `         27.8500E-09` → MID 2 로 읽고 새 MID 3 (공백 토큰이면 27 로 읽는다)
  E `_TITLE` (제목 `steel 9`) MID 4 → 새 MID 5
  F 인클루드 안의 `*MAT_PLASTIC_KINEMATIC 6` → 새 MID 7
  G long 칸(`*MAT_PLASTIC_KINEMATIC +`, 20칸) MID 8 → 새 MID 9

usage: test_mid_unknown_types.py <KooRemapper 바이너리>
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


PK = "*MAT_PLASTIC_KINEMATIC"
PK_REST = "       0.0       0.0       0.0"
CASES = [
    ("A 리더가 모르는 재질", [PK, "         2  7.85E-09    210000       0.3     250.0", PK_REST], {}, 3),
    ("B 열 재질 TMID 50", ["*MAT_THERMAL_ISOTROPIC", "        50  7.85E-09       0.0       0.0",
                          "     460.0      50.0"], {}, 2),
    ("C *MAT_ADD_THERMAL_EXPANSION PID 77", ["*MAT_ADD_THERMAL_EXPANSION", "        77         0       1.0"], {}, 2),
    ("D 칸이 붙은 카드", [PK, "         27.8500E-09    210000       0.3     250.0", PK_REST], {}, 3),
    ("E _TITLE", [PK + "_TITLE", "steel 9", "         4  7.85E-09    210000       0.3     250.0", PK_REST], {}, 5),
    ("F 인클루드 안", ["*INCLUDE", "mats.k"],
     {"mats.k": "\n".join(["*KEYWORD", PK, "         6  7.85E-09    210000       0.3     250.0", PK_REST,
                           "*END"]) + "\n"}, 7),
    ("G long 칸(+)", [PK + " +", "%20d%20s%20s%20s" % (8, "7.85E-09", "210000.", "0.3"), "%20s" % "0.0"], {}, 9),
]
YAML = "base_model: deck.k\noutput: out\noperations:\n  - type: disconnect\n    mode: czm\n    target_pid: 0\n"


def new_mid(path):
    """czm 이 낸 `*MAT_COHESIVE_MIXED_MODE` 의 MID."""
    L = open(path, encoding="utf-8", errors="replace").read().splitlines()
    for i, l in enumerate(L):
        if l.strip().upper().startswith("*MAT_COHESIVE"):
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
        d = tempfile.mkdtemp(prefix="mut_")
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
            got = new_mid(out)
            check("%s — 새 MID %d" % (label, want), got == want, "새 MID=%s" % got)
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
