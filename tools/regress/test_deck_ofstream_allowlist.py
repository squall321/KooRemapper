#!/usr/bin/env python3
"""덱을 쓰는 `std::ofstream` 이 새로 들어오면 잡는다 — 개행 계약이 다시 새지 않게.

왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P0-2 잔여):

  개행 소실을 12곳 고쳤지만, **다음 op 이 또 `std::ofstream` 을 직접 열면** 같은 결함이
  돌아온다. 실제로 그렇게 됐던 것이다 — 25곳 넘는 자체 라이터가 각자 개행을 정했고,
  누가 어디서 덱을 쓰는지 아무도 셀 수 없었다.

  그래서 `src/`·`include/` 의 `std::ofstream` 을 **파일별로 선언**해 둔다. 수가 달라지거나
  선언에 없는 파일에서 나오면 FAIL 이다. 새로 쓰는 사람은 둘 중 하나를 해야 한다 —
  덱이면 `KooRemapper::DeckWriter` 를 쓰고, 덱이 아니면 여기에 **이유를 적어** 수를 늘린다.

  왜 수만 세나 — 줄 번호는 흔들리고 변수 이름은 파일 안에서 겹친다(meshfix 의 `o` 가 둘이다).
  "파일별 수 + 이유" 는 흔들리지 않으면서도 **분류를 강제**한다. 이 시험이 막는 것은
  "아무도 모르게 늘어나는 것" 이다.

usage: test_deck_ofstream_allowlist.py [<KooRemapper 바이너리, 무시>]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
PAT = re.compile(r"std::ofstream")

# 파일 → (개수, 분류와 이유)
#
# 분류는 셋뿐이다.
#   덱(보존)   — 입력 덱을 읽어 쓴다. **DeckWriter 를 써야 한다.**
#   덱(신규)   — 입력 없이 새로 만든다. 보존할 원본 개행이 없다.
#   덱 아님    — STL·JSON·CSV·로그·VTK 등.
DECLARED = {
    # ── 덱 아님 ─────────────────────────────────────────────────────────────
    "src/analysis/StrainCalculator.cpp": (1, "덱 아님 — 변형률 CSV"),
    "src/assembly/WarpageGrid.cpp": (3, "덱 아님 — 휨 진단용 _raw.dat / _curvature.dat / _warpage.vtk"),
    "src/commands/modelmeta.cpp": (1, "덱 아님 — 메타 JSON"),
    "src/util/Validator.cpp": (1, "덱 아님 — 검증 로그(append)"),
    "src/util/Logger.cpp": (1, "덱 아님 — 로그 파일"),
    "include/util/Logger.h": (1, "덱 아님 — 로그 스트림 멤버 선언"),
    "src/commands/meshfix.cpp": (7, "덱 아님 — gmsh 왕복용 ASCII STL 4곳 · .geo 2곳 · .bat 1곳. "
                                    "덱 산출물은 DeckWriter 로 쓴다(2e47878)"),
    # ── 덱(신규) ────────────────────────────────────────────────────────────
    "src/commands/core_ops.cpp": (1, "덱(신규) — `generate box` 가 덱을 새로 만든다. 입력 덱이 없다"),
    "src/commands/battery.cpp": (2, "덱(신규) — 배터리 덱을 새로 만든다. 입력 덱을 읽지 않는다"),
    "src/commands/cclip.cpp": (2, "덱(신규) — F-δ 검증용 독립 압축 덱 1곳 + 리포트 1곳. "
                                  "본 덱·dynain·_free.k 는 DeckWriter 로 쓴다"),
    # ── 덱(보존) — 개행을 스스로 되붙이는 자리 ───────────────────────────────
    "src/assembly/ModelAssembler.cpp": (4, "덱(보존) — deckNewline_ 을 붙여 쓴다(본 덱·dynain·IGA) + CSV 1곳"),
    "src/parser/DynainWriter.cpp": (2, "덱(보존) — refFile 에서 deck_newline::detect 한 값을 쓴다"),
    # ── 계층 자신 ───────────────────────────────────────────────────────────
    "include/parser/DeckWriter.h": (1, "계층 자신 — 모든 덱 쓰기의 단일 진입점"),
}

FAILS = []


def check(name, cond, detail=""):
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:250]) if detail else ""))


def scan():
    found = {}
    for root in ("src", "include"):
        for dirpath, _dirs, files in os.walk(os.path.join(REPO, root)):
            for fn in files:
                if not fn.endswith((".cpp", ".h", ".hpp")):
                    continue
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, REPO)
                n = len(PAT.findall(open(p, encoding="utf-8", errors="replace").read()))
                if n:
                    found[rel] = n
    return found


def main():
    found = scan()
    print("[std::ofstream 전수 선언 관문] 찾은 파일 %d개 · 선언 %d개" % (len(found), len(DECLARED)))

    for rel in sorted(set(found) - set(DECLARED)):
        check("선언에 없는 파일: %s (%d곳)" % (rel, found[rel]), False,
              "덱이면 KooRemapper::DeckWriter 를 쓰고, 아니면 DECLARED 에 이유를 적어라")
    for rel in sorted(set(DECLARED) - set(found)):
        check("선언은 있는데 파일에 없다: %s" % rel, False, "DECLARED 에서 지워라")
    for rel in sorted(set(found) & set(DECLARED)):
        want, why = DECLARED[rel]
        check("%s  %d곳 — %s" % (rel, want, why.split(" — ")[0]), found[rel] == want,
              "선언 %d · 실제 %d — %s" % (want, found[rel], why))

    print("")
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
