#!/usr/bin/env python3
"""`*CONTACT_*_ID` 는 카드 앞에 줄이 **1줄 더** 있다 — 그걸 안 세면 편집이 SSID 칸을 덮어쓴다.

왜 이 시험이 있나 (2026-09-24, 덱 편집 계약 요청서 DF-05):

  `_ID` 옵션은 `cid + 제목` 줄을 Card 1 앞에 둔다. 읽기는 그것을 세고 있었지만 그 판정이
  **지역 변수**라 `ContactDef` 에 안 남았고, 편집 5곳은 `hasTitle` 만 봤다. 그래서
  `_ID` 인데 `_TITLE` 이 아닌 카드에서 편집이 Card 1 자리를 한 줄 앞으로 잡았다.

  재현(수정 전) — `modify friction: 0.33`:

      원본    '         1         2         3         3'   ssid=1  msid=2
      수정 후 '      0.33         2         3         3'   ssid 칸에 마찰계수

  슬레이브 파트 참조가 파괴되고, 정작 FS 는 그대로고, 도구는 `Modified: FS=0.330000` 이라고
  **성공을 보고한다**. 접촉 **개수는 멀쩡하다** — 그래서 개수를 세는 시험은 이 버그를 전부 통과시킨다.

  ⚠ 그러므로 이 파일은 **개수를 단언하지 않는다.** 칸의 내용만 본다.

  판정도 좁았다. `rfind("_ID") == size-3` 이라 끝에 오는 `_ID` 만 잡고, 매뉴얼 정규 철자인
  `_ID_MPP` 처럼 뒤에 옵션이 더 붙는 형태를 놓쳤다.

usage: test_contact_id_option.py <KooRemapper 바이너리>
"""
import os
import subprocess
import sys
import tempfile

FAILS = []

# 끝에 오는 `_ID`, 중간에 오는 `_ID_`, 다른 옵션 뒤에 오는 `_ID` 셋 다 본다.
VARIANTS = [
    "AUTOMATIC_SURFACE_TO_SURFACE_ID",
    "AUTOMATIC_SURFACE_TO_SURFACE_ID_MPP",
    "TIED_SURFACE_TO_SURFACE_OFFSET_ID",
]

CARD = ("*CONTACT_{kw}\n"
        "      1000contact one\n"
        "         1         2         3         3\n"
        "       0.2       0.2\n")


def check(name, cond, detail=""):
    print("  %-68s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + detail.strip()[:300]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def build_deck(d, kw):
    src = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "examples", "indent", "small", "block.k"))
    txt = open(src, encoding="utf-8", errors="replace").read()
    open(os.path.join(d, "m.k"), "w").write(txt.replace("*END", CARD.format(kw=kw) + "*END", 1))


def cards_after(path, kw):
    """`*CONTACT_<kw>` 다음의 (ID줄, Card1, Card2) 를 돌려준다."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    key = "*CONTACT_" + kw
    for i, ln in enumerate(lines):
        if ln.strip().upper() == key:
            body = [s for s in lines[i + 1:i + 6] if s and s[0] not in "$*"]
            return body[:3]
    return []


def modify_keeps_card1(binary, kw):
    d = tempfile.mkdtemp(prefix="cid_")
    build_deck(d, kw)
    open(os.path.join(d, "mod.yaml"), "w").write(
        "model: m.k\noutput: o.k\ncontacts:\n"
        "  - action: modify\n    contact_index: 0\n    friction: 0.33\n")
    rc, out = run(binary, d, "contact", "mod.yaml")
    check("%s: rc=0" % kw, rc == 0, out[-300:])

    body = cards_after(os.path.join(d, "o.k"), kw)
    if len(body) < 3:
        check("%s: ID줄+Card1+Card2 를 찾았다" % kw, False, str(body))
        return
    idline, card1, card2 = body

    # ⚠ 핵심 — Card 1 의 ssid/msid 는 **한 글자도** 바뀌면 안 된다.
    f1 = [card1[k:k + 10] for k in range(0, len(card1), 10)]
    check("%s: ssid 칸 불변(1)" % kw, f1 and f1[0].strip() == "1", repr(card1))
    check("%s: msid 칸 불변(2)" % kw, len(f1) > 1 and f1[1].strip() == "2", repr(card1))

    # 그리고 마찰계수는 Card 2 의 첫 칸(fs)에 들어가야 한다.
    f2 = [card2[k:k + 10] for k in range(0, len(card2), 10)]
    try:
        ok = f2 and abs(float(f2[0]) - 0.33) < 1e-9
    except ValueError:
        ok = False
    check("%s: fs 칸이 0.33 이 됐다" % kw, ok, repr(card2))

    # ID 줄 자체는 편집 대상이 아니다.
    check("%s: ID 줄 보존" % kw, idline.strip().startswith("1000"), repr(idline))


def main():
    if len(sys.argv) < 2:
        print("usage: test_contact_id_option.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    print("[A `_ID` 카드를 편집해도 Card 1 을 덮어쓰지 않는다 — 개수는 보지 않는다]")
    for kw in VARIANTS:
        modify_keeps_card1(binary, kw)
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
