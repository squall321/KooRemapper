#!/usr/bin/env python3
"""덱이 가리키는 세트가 **정의돼 있나** — 델타 검사가 못 보는 '애초에 없는' 참조를 잡는다.

왜 이 시험이 있나 (2026-09-24, 덱 편집 계약 요청서 DF-06):

  기존 스캐너(`scanDeadReferences`)는 **"이번 op 이 지웠나"** 만 보는 델타 검사다.
  "애초에 정의돼 있나" 는 아무도 안 봤다. 실측 — 없는 세트를 가리키는 카드 5종을 심은 덱이
  `info` 에서 `[OK] Mesh is valid` · rc=0 으로 통과했다. LS-DYNA 는 그 덱에서 **Error 10144 로
  키워드 단계에서 즉사**한다(요청서 사건표의 TN4 전멸). 해석 시간을 쓰기도 전에 죽는데
  도구는 멀쩡하다고 말했다.

이 시험의 절반은 **오탐이 없는지**다. 오탐을 한 번 내면 사람은 이 보고를 통째로 무시하고,
그러면 진짜를 놓친다. 그래서 까다로운 변형을 일부러 넣는다:

  · `_GENERATE_TITLE` 정의(제목줄 +1, 멤버가 범위쌍)      → 잡으면 안 된다
  · `*PARAMETER` 의 `&name` 참조(값이 기호다)             → 검사하지 않는다
  · CONTACT SSTYP=3(파트 ID — 세트가 아니다)             → 검사하지 않는다
  · `*INCLUDE` 가 있으면 **단정하지 않는다**(경고로 낮춘다)

usage: test_reference_integrity.py <KooRemapper 바이너리>
"""
import os
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK = os.path.normpath(os.path.join(HERE, "..", "..", "examples", "indent", "small", "block.k"))


def check(name, cond, detail=""):
    print("  %-64s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + detail.strip()[:300]) if detail else ""))


def deck(d, name, cards):
    t = open(BLOCK, encoding="utf-8", errors="replace").read()
    p = os.path.join(d, name)
    open(p, "w").write(t.replace("*END", cards + "*END", 1))
    return p


def info(binary, path):
    p = subprocess.run([binary, "info", path], capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print("usage: test_reference_integrity.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    d = tempfile.mkdtemp(prefix="refint_")

    print("[A 미정의 세트 참조를 잡는다 — TN4 재현]")
    p = deck(d, "dangling.k", """*DATABASE_HISTORY_SOLID_SET
      9999
*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE
      8888      7777         2         2
*CONSTRAINED_NODAL_RIGID_BODY
        99         0      6666
*BOUNDARY_SPC_SET
    999999         0         1         1         1
""")
    rc, out = info(binary, p)
    for sid in ("9999", "8888", "7777", "6666", "999999"):
        check("세트 %s 를 보고한다" % sid, sid in out and "정의되지 않았습니다" in out, out[-400:])
    check("INCLUDE 가 없으면 단정한다(키워드 단계에서 멈춥니다)",
          "키워드 단계에서 멈춥니다" in out, out[-300:])
    # rc 는 건드리지 않는다 — 상위 파이프라인이 info 의 rc=0 을 기대한다
    check("info 의 rc 계약은 그대로 0", rc == 0, "rc=%d" % rc)

    print("[B 오탐을 내지 않는다 — 이쪽이 절반이다]")
    p = deck(d, "gen.k", """*SET_NODE_LIST_GENERATE_TITLE
my generated set
       700
         1        10
*BOUNDARY_SPC_SET
       700         0         1         1         1
""")
    _, out = info(binary, p)
    check("_GENERATE_TITLE 정의를 알아본다", "무결성 OK" in out, out[-300:])

    p = deck(d, "param.k", """*PARAMETER
R  mysid    700
*BOUNDARY_SPC_SET
    &mysid         0         1         1         1
""")
    _, out = info(binary, p)
    check("&파라미터 참조는 검사하지 않는다", "무결성 OK" in out and "검사하지 않은" in out, out[-300:])

    p = deck(d, "ctype3.k", """*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE
         1         2         3         3
""")
    _, out = info(binary, p)
    check("CONTACT SSTYP=3(파트 ID)은 세트가 아니다", "무결성 OK" in out, out[-300:])

    print("[C *INCLUDE 가 있으면 단정하지 않는다]")
    p = deck(d, "inc.k", """*INCLUDE
sub/other.k
*BOUNDARY_SPC_SET
       700         0         1         1         1
""")
    _, out = info(binary, p)
    check("경고로 낮춘다(정의되지 않았다고 단정하지 않는다)",
          "단정하지 않습니다" in out and "정의되지 않았습니다" not in out, out[-400:])
    check("어느 INCLUDE 를 안 봤는지 말한다", "sub/other.k" in out, out[-300:])

    print("[D 저장소 예제 덱에서 오탐 0건]")
    ex = os.path.normpath(os.path.join(HERE, "..", "..", "examples"))
    checked = bad = 0
    for root, _dirs, files in os.walk(ex):
        for fn in files:
            if not fn.endswith(".k"):
                continue
            checked += 1
            if checked > 40:
                break
            _, o = info(binary, os.path.join(root, fn))
            if "정의되지 않았습니다" in o:
                bad += 1
                print("     오탐 의심: %s" % os.path.join(root, fn))
        if checked > 40:
            break
    check("예제 덱 %d개에서 단정 보고 0건" % min(checked, 40), bad == 0, "%d건" % bad)

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
