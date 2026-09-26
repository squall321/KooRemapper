#!/usr/bin/env python3
"""요소→파트·파트→섹션·재질 참조와 **망가진 `*CONTACT_` 카드** 를 `info` 가 보는가 (P1-6).

왜 이 시험이 있나 (2026-09-26):

  `checkSetReferences` 는 **세트만** 봤다. 그래서 요소가 없는 파트를 가리키는 덱이,
  파트가 없는 섹션을 가리키는 덱이 `info` 에서 통째로 통과했다. LS-DYNA 는 그 덱에서
  키워드 단계에서 즉사한다. 특히 P1-2 이전의 `convert` 는 파트를 못 읽으면 PID 자리에
  **`-1` 을 써 냈고**, `info` 는 그 덱을 `[OK]` 로 통과시켰다 — 그 구멍이 이 시험의 A-5 다.

이 시험의 절반은 **오탐이 없는지**다. 오탐을 한 번 내면 사람은 보고를 통째로 무시한다.
그래서 리포의 실제 덱들을 지목해 못 박아 둔다:

  · `*PART` 카드2 의 칸이 어긋난 덱(`restack_result.k`) — 읽는 쪽(`KFileReader::parsePartSection`)
    처럼 **자유형식 토큰을 먼저** 보지 않으면 SECID 가 빈칸으로 읽혀 그 파트가 '정의된 적 없다'
    가 되고, 그 파트를 쓰는 요소 전부가 가짜 미정의 참조로 뜬다. 실제로 그렇게 떴다.
  · 파트 표가 아예 없는 메시 조각(`arc30_flat.k`) — 대조할 표가 없으니 조용해야 한다.
  · 반대로 진짜 결함인 덱은 **계속 보고해야** 한다(B 묶음). 이 덱들은 고치지 않는다 —
    픽스처를 고치면 이 시험이 무엇을 지키는지 알 수 없게 된다.

`info` 의 rc 는 이 검사와 무관하게 0 이어야 한다 — 상위 파이프라인이 그렇게 기대한다.

usage: test_element_part_references.py <KooRemapper 바이너리>
"""
import os
import re
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))

# 리포 실제 덱 — (경로, 이 검사가 조용해야 하나, 왜)
QUIET = [
    ("examples/replace_test/restack_result.k",
     "*PART 카드2 의 칸이 어긋났다(SECID 자리가 빈칸) — 토큰으로 읽어야 파트 1·2 가 보인다"),
    ("examples/replace_test/base_model_3part.k",
     "같은 어긋남의 원본. 파트 1·2·3 이 전부 정의돼 있다"),
    ("examples/arc30/arc30_flat.k",
     "*PART 가 하나도 없는 메시 조각 — 대조할 표가 없다"),
    ("examples/indent/small/block.k",
     "평범한 온전한 덱"),
]
# 진짜 결함이 있는 리포 덱 — 계속 보고해야 한다
LOUD = [
    ("examples/squeeze_interference/interference_model.k", r"\*PART: 섹션 1",
     "*SECTION 이 덱에 아예 없는데 파트 둘이 섹션 1 을 가리킨다"),
    ("examples/wrap/cylinder_2layer.k", r"\*PART: (섹션|재질) 2",
     "*SECTION/*MAT 는 1번만 있는데 파트 2 가 2번을 가리킨다"),
]

CLEAN = """*KEYWORD
*PART
cube
       7       1       1
*SECTION_SOLID
       1       1
*MAT_ELASTIC
       1 7.85E-9  210000     0.3
*NODE
       1     0.0     0.0     0.0
       2     1.0     0.0     0.0
       3     1.0     1.0     0.0
       4     0.0     1.0     0.0
       5     0.0     0.0     1.0
       6     1.0     0.0     1.0
       7     1.0     1.0     1.0
       8     0.0     1.0     1.0
*ELEMENT_SOLID
       1       7       1       2       3       4       5       6       7       8
*END
"""
ELEM_LINE = "       1       7       1       2       3       4       5       6       7       8"


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + detail.strip()[:400]) if detail else ""))


def info(binary, path):
    p = subprocess.run([binary, "info", path], capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def reports(out):
    """이 검사가 낸 줄만 — `*PART:` / `*ELEMENT:` 로 시작하는 것."""
    return [l.strip() for l in out.splitlines() if re.search(r"^\s+line \d+ \*(PART|ELEMENT):", l)]


def widen_to_i10(text, pid_override=None):
    """8칸 덱을 I10 덱으로 다시 쓴다. 제목줄은 건드리지 않는다."""
    out, in_elem = [], False
    for ln in text.split("\n"):
        if ln.startswith("*KEYWORD"):
            out.append("*KEYWORD I10=Y")
            continue
        if ln.startswith("*ELEMENT_SOLID"):
            in_elem = True
            out.append(ln)
            continue
        if ln.startswith("*"):
            in_elem = False
            out.append(ln)
            continue
        if not ln.strip() or not ln[:8].strip().lstrip("-").isdigit():
            out.append(ln)
            continue
        f = [x for x in (ln[i:i + 8].strip() for i in range(0, len(ln), 8)) if x]
        if in_elem and pid_override is not None:
            f[1] = str(pid_override)
        out.append("".join(x.rjust(10) for x in f))
    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        print("usage: test_element_part_references.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    d = tempfile.mkdtemp(prefix="elempart_")

    def write(name, text):
        p = os.path.join(d, name)
        open(p, "w", newline="\n").write(text)
        return p

    print("[A 심은 결함을 잡는다]")
    cases = [
        ("A-1 요소가 없는 파트를 가리킨다",
         CLEAN.replace(ELEM_LINE, ELEM_LINE.replace("       7", "      99", 1)),
         r"\*ELEMENT: 파트 99"),
        ("A-2 파트가 없는 섹션을 가리킨다",
         CLEAN.replace("       7       1       1", "       7      55       1"),
         r"\*PART: 섹션 55"),
        ("A-3 파트가 없는 재질을 가리킨다",
         CLEAN.replace("       7       1       1", "       7       1      66"),
         r"\*PART: 재질 66"),
        ("A-4 I10 덱에서도 칸을 따라 읽는다",
         widen_to_i10(CLEAN, pid_override=99),
         r"\*ELEMENT: 파트 99"),
        ("A-5 요소 PID 가 -1 이다 (P1-2 의 convert 가 실제로 써 낸 값)",
         CLEAN.replace(ELEM_LINE, ELEM_LINE.replace("       7", "      -1", 1)),
         r"\*ELEMENT: 파트 -1"),
    ]
    for i, (name, text, pat) in enumerate(cases):
        p = write("a%d.k" % i, text)
        rc, out = info(binary, p)
        hits = reports(out)
        check(name, any(re.search(pat, h) for h in hits), "보고=%r" % hits)
        check("   " + name.split()[0] + " rc 는 0 이다", rc == 0, out[-300:])

    print("[B 온전한 덱에는 조용하다 — 합성]")
    p = write("clean.k", CLEAN)
    rc, out = info(binary, p)
    check("B-1 온전한 8칸 덱", reports(out) == [], out)
    p = write("clean_i10.k", widen_to_i10(CLEAN))
    rc, out = info(binary, p)
    check("B-2 온전한 I10 덱", reports(out) == [], out)
    # PID 칸이 비었다 — 못 읽은 것이므로 단정하지 않는다(0 과 구별할 수 없다)
    p = write("pid_blank.k", CLEAN.replace(ELEM_LINE, "       1               1       2       3       4       5       6       7       8"))
    rc, out = info(binary, p)
    check("B-3 PID 칸이 비면 단정하지 않는다", reports(out) == [], out)
    check("   B-3 그래도 '검사하지 않았다' 고 말한다", "검사하지 않은 자리" in out, out[-400:])

    # `*MAT_ADD_*` 는 **재질을 새로 만들지 않는다** — 기존 MID 를 꾸민다. 정의 집합에 넣으면
    # 없는 재질을 있다고 말한다.
    p = write("mat_add.k", CLEAN.replace("       7       1       1", "       7       1      66")
                                .replace("*NODE", "*MAT_ADD_THERMAL_EXPANSION\n      66     1.0E-5\n*NODE", 1))
    rc, out = info(binary, p)
    check("B-4 *MAT_ADD_ 는 재질 정의가 아니다", any(re.search(r"\*PART: 재질 66", h) for h in reports(out)),
          "보고=%r" % reports(out))

    # 칸을 **꽉 채운** 덱 — 공백이 없어 자유형식 분해가 실패하고 고정폭 폴백으로 온다.
    # 그 폴백이 칸을 다듬지 않으면 PID 를 못 읽어 파트가 통째로 사라진다(M1 이 드러낸 길).
    # SECID 가 8자리여서 PID 칸에 **붙는다** → 공백 토큰이 2개뿐이라 고정폭 폴백으로 간다.
    # 그 폴백이 칸을 다듬지 않으면 PID 를 -1 로 읽어 파트 7 이 통째로 사라지고, 그 파트를 쓰는
    # 요소가 가짜 미정의 참조로 뜬다. 파트 8 을 같이 둬야 '파트 표가 아예 없다' 는 빠져나갈
    # 구멍이 막힌다 — 표가 비면 요소 검사를 아예 안 하기 때문이다.
    packed = (CLEAN.replace("*PART\ncube\n       7       1       1",
                            "*PART\ncube\n       712345678       1\n*PART\nspare\n       8       1       1")
                   .replace("*SECTION_SOLID\n       1       1",
                            "*SECTION_SOLID\n12345678       1\n*SECTION_SOLID\n       1       1"))
    p = write("packed.k", packed)
    rc, out = info(binary, p)
    check("B-5 칸을 꽉 채운 덱도 파트를 찾는다", reports(out) == [], "보고=%r" % reports(out))

    print("[C 리포의 실제 덱에 오탐이 없다]")
    for rel, why in QUIET:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            check("C " + rel, False, "덱이 없다 — 시험을 고쳐라")
            continue
        rc, out = info(binary, path)
        check("C " + rel, reports(out) == [], why + " / 보고=%r" % reports(out))
        if "칸이 어긋났다" in why:
            # 조용한 것과 **못 본 것을 감추는 것**은 다르다 — 어긋난 카드는 세어서 말해야 한다.
            check("   C 어긋난 카드를 세어 말한다", "검사하지 않은 자리" in out, out[-400:])

    print("[E 망가진 *CONTACT_ 카드 — 참조가 아니라 카드 자체가 깨진 축]")
    # `_ID` 덱에서 줄이 한 칸 밀리면 마찰계수가 SSID 칸에 덮어써진다(P1-4 가 그 쓰기를 고쳤다).
    # 이미 그렇게 망가진 덱을 알아보는 쪽이 이 검사다.
    ID_HEAD = "*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET_ID\n        11Contact_1\n"
    C1 = "         1         2         3         3         0         0         0         0\n"
    C2 = "       0.2       0.1       0.0       0.0       0.0         0       0.0  1.00E+20\n"
    C3 = "       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0\n"
    dmg = [
        ("E-1 SSID 칸에 마찰계수가 덮어써졌다",
         ID_HEAD + "      0.33       0.1       3         3         0         0         0         0\n" + C2 + C3,
         r"SSID 칸에 실수 0\.33"),
        ("E-2 필수 Card 3 가 사라졌다",
         ID_HEAD + C1 + C2,
         r"필수 카드가 2장뿐입니다"),
    ]
    for i, (name, cards, pat) in enumerate(dmg):
        p = write("e%d.k" % i, CLEAN.replace("*END", cards + "*END", 1))
        rc, out = info(binary, p)
        hits = [l.strip() for l in out.splitlines() if re.search(r"^\s+line \d+ \*CONTACT", l)]
        check(name, any(re.search(pat, h) for h in hits), "보고=%r" % hits)
        check("   " + name.split()[0] + " rc 는 0 이다", rc == 0, out[-300:])
    # 온전한 `_ID` 덱은 조용해야 한다 — 여기서 오탐이 나면 `_ID` 줄을 Card 1 로 센 것이다.
    p = write("e_ok.k", CLEAN.replace("*END", ID_HEAD + C1 + C2 + C3 + "*END", 1))
    rc, out = info(binary, p)
    check("E-3 온전한 _ID 덱에는 조용하다",
          not [l for l in out.splitlines() if re.search(r"^\s+line \d+ \*CONTACT", l)], out)
    # 카드 구성이 **다른 변종**에 3장 규칙을 들이대면 안 된다. `*CONTACT_1D` 는 카드가 한 장이고
    # 3·4번째 칸이 SSTYP/MSTYP 가 아니라 ID 다 — 그 칸이 0-6 을 벗어나면 서명이 아니라고 보고
    # 검사를 접는다. 이 빗장을 빼면 이 덱이 "필수 카드가 1장뿐" 이라는 오탐으로 뜬다.
    p = write("e_1d.k", CLEAN.replace(
        "*END", "*CONTACT_1D\n         1         2        11        12\n*END", 1))
    rc, out = info(binary, p)
    check("E-4 카드 구성이 다른 변종에는 3장 규칙을 안 쓴다",
          not [l for l in out.splitlines() if re.search(r"^\s+line \d+ \*CONTACT", l)], out)

    # 리포의 접촉 덱 21장 전부에 손상 보고가 없어야 한다(전수는 느리니 대표 2장을 못 박는다)
    for rel in ("examples/contact/model.k", "examples/replace_test/assembled_replace_result.k"):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            check("E " + rel, False, "덱이 없다 — 시험을 고쳐라")
            continue
        rc, out = info(binary, path)
        check("E " + rel + " 에 손상 보고가 없다",
              not [l for l in out.splitlines() if re.search(r"^\s+line \d+ \*CONTACT", l)], out)

    print("[D 리포의 진짜 결함 덱은 계속 보고한다]")
    for rel, pat, why in LOUD:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            check("D " + rel, False, "덱이 없다 — 시험을 고쳐라")
            continue
        rc, out = info(binary, path)
        hits = reports(out)
        check("D " + rel, any(re.search(pat, h) for h in hits), why + " / 보고=%r" % hits)

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
