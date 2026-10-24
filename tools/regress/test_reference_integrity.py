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

    # `_MPP` 는 Card 1 앞에 MPP 1(첫 칸이 `&` 면 MPP 2 도)을 둔다(Vol_I 카드 순서). 예전 검사는 `_TITLE` · `_ID` 만 세어
    # MPP 1(IGNORE BCKT LCBCKT NS2TRK …)을 Card 1 로 읽었다(10-23 재현) — IGNORE 2 · LCBCKT 0 을 「세그먼트 세트 2 가 없다」로
    # 단정하고(`--strict` 면 rc 1), 진짜 Card 1 의 없는 세트는 못 봤고, MPP 2 까지 있으면 Card 1 을 Card 3 자리로 보아
    # 「Card A 가 밀려 올라왔다」고 의심했다. 이제 카드 자리는 정본(`ct_parseContacts`)이 센다.
    print("[E `_MPP` — MPP 1 · MPP 2 는 Card 1 이 아니다]")
    C3 = "       0.2       0.2\n       1.0       1.0\n"
    p = deck(d, "mpp_fp.k", "*CONTACT_AUTOMATIC_SINGLE_SURFACE_MPP\n         2       200         0         3\n"
                            "         0         0         5         0\n" + C3)
    rc, out = info(binary, p)
    check("MPP 1 의 IGNORE 2 를 세트로 읽지 않는다", "세트 2 이" not in out and "정의되지 않았습니다" not in out, out[-300:])
    p = deck(d, "mpp_fn.k", "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MPP\n         0       200\n"
                            "      8888      7777         2         2\n" + C3)
    rc, out = info(binary, p)
    check("`_MPP` 접촉의 진짜 Card 1 이 가리키는 없는 세트를 잡는다", "8888" in out and "7777" in out, out[-300:])
    p = deck(d, "mpp2.k", "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID_MPP\n        10contact ten\n"
                          "         2       200         0         3\n&        0\n      8888      7777         2         2\n" + C3)
    rc, out = info(binary, p)
    check("`_ID_MPP` + `&` MPP 2 — Card 1 의 8888 · 7777 을 잡는다", "8888" in out and "7777" in out, out[-300:])
    check("`_ID_MPP` + `&` MPP 2 — MPP 1 의 IGNORE 2 를 세트로 읽지 않는다", "세트 2 이" not in out, out[-300:])
    check("`_ID_MPP` + `&` MPP 2 — Card 1 을 Card 3 자리로 보지 않는다(거짓 손상 의심 없음)",
          "밀려 올라온" not in out, out[-400:])
    p = deck(d, "mpp_blank.k", "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_MPP\n\n      8888      7777         2         2\n" + C3)
    rc, out = info(binary, p)
    check("빈 줄로 둔 MPP 1(전부 기본값)도 카드로 센다 — Card 1 의 8888 · 7777", "8888" in out and "7777" in out,
          out[-300:])

    # 10-23(fe82dd3) 전의 optimize 는 `_ID` 의 ID 카드를 못 건너뛰어 Card 3 을 Card A 로 알고 SOFT=0 을 SFSA 칸에, SBOPT=2 를
    # SFSAT 칸에 썼다(그 판 코드 — kw_setField(…, 0, 10, "0") · kw_setField(…, 40, 10, "2")). 그 꼴을 의심으로 짚는다(결정 9B).
    print("[F 옛 optimize 의 흔적 — Card 3 의 SFSA 정수 0 · SFSAT 정수 2]")
    dmg = ("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID\n        11rubber\n         1         2         3         3\n       0.2       0.1\n"
           "         0       1.0       0.0       0.0         2       1.0\n")
    p = deck(d, "optdmg.k", dmg)
    rc, out = info(binary, p)
    check("옛 optimize 가 쓴 Card 3(SFSA 0 · SFSAT 2)을 의심으로 짚는다", "10-23 전 optimize" in out, out[-400:])
    rc2 = subprocess.run([binary, "info", "--strict", p], capture_output=True, text=True, timeout=300).returncode
    check("의심이라 단정하지 않는다 — rc 0 · --strict 도 0", "의심" in out and rc == 0 and rc2 == 0,
          "rc=%d strict=%d" % (rc, rc2))
    clean = ("*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID\n        12clean\n         1         2         3         3\n       0.2       0.1\n"
             "       1.0       1.0       0.0       0.0       1.0       1.0\n")
    p = deck(d, "optclean.k", clean)
    rc, out = info(binary, p)
    check("멀쩡한 Card 3 은 짚지 않는다", "10-23 전 optimize" not in out, out[-300:])

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
