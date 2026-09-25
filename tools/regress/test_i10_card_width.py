#!/usr/bin/env python3
"""`I10=Y` 덱에 새로 쓰는 요소 카드가 **10칸**으로 나가나 — 그리고 PID 를 제대로 읽나.

왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P1-2):

  LS-DYNA 덱의 정수 칸은 `*KEYWORD` 가 정한다 — 표준 8칸, `I10=Y` 면 10칸, `LONG=Y` 면 20칸.
  그런데 요소를 **바꿔 쓰는** 경로(convert tet10/hex20/quad8/tria6 · disconnect)가 폭을
  8 로 못 박고 있었다. 결과가 둘이었다(실측).

    ① PID 오독 — `parsePartIdFromLine` 이 `substr(8, 8)` 이라 I10 카드에서는 그 자리가
       **EID 칸의 꼬리**다. PID 77 인 요소가 **1** 로 나갔고, 1번 파트는 덱에 없다.
    ② 폭 불일치 — 산출 덱이 `*KEYWORD I10=Y` 를 달고 `*PART`·`*NODE` 는 10칸인데
       새 요소 카드만 8칸이었다. LS-DYNA 는 그 줄을 10칸으로 읽으므로 값이 통째로 어긋난다.

  둘 다 **조용했다** — rc=0 이고 `info` 도 통과시킨다. 이 리포가 반복해 당한 모양이다.

  ⚠ 8칸 덱에서는 한 글자도 바뀌면 안 된다. 그것도 여기서 함께 못 박는다(예제 42 op 의
  sha256 불변은 별도로 확인했다).

usage: test_i10_card_width.py <KooRemapper 바이너리>
"""
import os
import re
import subprocess
import sys
import tempfile

FAILS = []

_PTS = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
        (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
PID = 77


def check(name, cond, detail=""):
    print("  %-62s %s" % (name[:62], "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:250]) if detail else ""))


def write_deck(path, fw):
    """같은 모형을 fw 칸(8 또는 10)으로 쓴다. fw=10 이면 `*KEYWORD I10=Y`."""
    ifmt = "%%%dd" % fw
    head = "*KEYWORD I10=Y" if fw == 10 else "*KEYWORD"
    L = [head, "*PART", "cube", (ifmt * 3) % (PID, 1, 1),
         "*SECTION_SOLID", (ifmt * 2) % (1, 1),
         "*MAT_ELASTIC", (ifmt % 1) + "%10.3g%10.3g%10.3g" % (7.85e-9, 210000.0, 0.3),
         "*NODE"]
    for i, (x, y, z) in enumerate(_PTS, 1):
        L.append((ifmt % i) + "%16.7f%16.7f%16.7f" % (x, y, z))
    L.append("*ELEMENT_SOLID")
    L.append((ifmt * 2) % (1, PID) + "".join(ifmt % n for n in range(1, 9)))
    L.append("*END")
    open(path, "w").write("\n".join(L) + "\n")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def cards(path, keyword, n=1):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    i = next((k for k, l in enumerate(lines) if l.strip().upper() == keyword), None)
    return lines[i + 1:i + 1 + n] if i is not None else []


def field_width(card, expect_fields):
    """카드 한 줄의 칸 폭을 되돌린다 — 길이가 칸 수로 나누어떨어져야 한다."""
    return len(card) // expect_fields if expect_fields and len(card) % expect_fields == 0 else -1


def main():
    if len(sys.argv) < 2:
        print("usage: test_i10_card_width.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2

    d = tempfile.mkdtemp(prefix="i10w_")
    for fw, name in ((8, "std8"), (10, "i10")):
        write_deck(os.path.join(d, name + ".k"), fw)

    print("[두 덱이 먼저 제대로 읽힌다 — 덱이 틀린 것을 도구 탓하지 않기 위해]")
    for name in ("std8", "i10"):
        rc, out = run(binary, d, "info", name + ".k")
        m = re.search(r"^Nodes\s*:?\s*(\d+)", out, re.M)
        e = re.search(r"^Elements\s*:?\s*(\d+)", out, re.M)
        check("%s 가 노드 8 · 요소 1 로 읽힌다" % name,
              bool(m) and int(m.group(1)) == 8 and bool(e) and int(e.group(1)) == 1,
              out[-200:])

    print("[convert hex20 — 새 요소 카드의 칸 폭과 PID]")
    for name, want_fw in (("std8", 8), ("i10", 10)):
        open(os.path.join(d, "c_%s.yaml" % name), "w").write(
            "base_model: %s.k\noutput: %s_out\ntype: hex20\n" % (name, name))
        rc, out = run(binary, d, "convert", "c_%s.yaml" % name)
        check("%s convert rc=0" % name, rc == 0, out[-250:])
        op = os.path.join(d, "%s_out.k" % name)
        if not os.path.exists(op):
            check("%s 산출물이 생겼다" % name, False, out[-250:])
            continue
        c1 = cards(op, "*ELEMENT_SOLID", 3)
        if len(c1) < 3:
            check("%s 요소 카드 3줄이 나왔다" % name, False, repr(c1))
            continue
        # Card 1 = EID PID (2칸), Card 2·3 = 노드 10개씩
        check("%s 요소 Card1 이 %d칸이다" % (name, want_fw),
              field_width(c1[0], 2) == want_fw, "len=%d %r" % (len(c1[0]), c1[0]))
        check("%s 요소 Card2 가 %d칸이다" % (name, want_fw),
              field_width(c1[1], 10) == want_fw, "len=%d" % len(c1[1]))
        # ⚠ 이 단언이 오독을 잡는다 — 예전에는 I10 에서 1 이 나왔다(EID 의 끝자리).
        check("%s 요소의 PID 가 %d 다(EID 꼬리를 읽지 않는다)" % (name, PID),
              c1[0].split() == ["1", str(PID)], repr(c1[0]))
        # 같은 파일 안에서 폭이 갈리지 않는다.
        # ⚠ `*PART` 다음 줄은 **제목**이다(LS-DYNA 관례) — 데이터 카드는 그 다음이다.
        pc = cards(op, "*PART", 2)
        if len(pc) >= 2:
            check("%s *PART 와 요소 카드의 칸 폭이 같다" % name,
                  field_width(pc[1], 3) == field_width(c1[0], 2),
                  "part=%d(%r) elem=%d" % (field_width(pc[1], 3), pc[1], field_width(c1[0], 2)))

    print("[8칸 덱 산출물은 예전과 한 글자도 다르면 안 된다 — 모양으로 못 박는다]")
    op8 = os.path.join(d, "std8_out.k")
    if os.path.exists(op8):
        c = cards(op8, "*ELEMENT_SOLID", 1)
        check("8칸 산출물의 Card1 이 정확히 '       1      77'",
              c and c[0] == "%8d%8d" % (1, PID), repr(c[0] if c else None))

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
