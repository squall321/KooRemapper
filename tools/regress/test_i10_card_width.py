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
REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

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


def write_shell_deck(path, fw):
    """QUAD8 셸 하나(SECTION_SHELL elform 23). `elform` 강등이 이 카드를 다시 쓴다."""
    ifmt = "%%%dd" % fw
    head = "*KEYWORD I10=Y" if fw == 10 else "*KEYWORD"
    pts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
           (0.5, 0, 0), (1, 0.5, 0), (0.5, 1, 0), (0, 0.5, 0)]
    L = [head, "*PART", "plate", (ifmt * 3) % (10, 1, 1),
         "*SECTION_SHELL", (ifmt * 2) % (1, 23),
         "*MAT_ELASTIC", (ifmt % 1) + "%10.3g%10.3g%10.3g" % (7.85e-9, 210000.0, 0.3), "*NODE"]
    for i, (x, y, z) in enumerate(pts, 1):
        L.append((ifmt % i) + "%16.7f%16.7f%16.7f" % (x, y, z))
    L.append("*ELEMENT_SHELL")
    L.append((ifmt * 2) % (1, 10) + "".join(ifmt % n for n in range(1, 9)))
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


def rewrite_deck_width(src, dst, fw):
    """8칸 덱을 fw 칸으로 다시 서식한다(정수 칸만). fw=10 이면 `*KEYWORD I10=Y` 를 단다."""
    lines = open(src, encoding="utf-8", errors="replace").read().splitlines()
    out, sec = [], None
    for l in lines:
        if l.startswith("*"):
            sec = l.strip().upper()
            out.append("*KEYWORD I10=Y" if (sec == "*KEYWORD" and fw == 10) else l)
            continue
        if not l or l.startswith("$"):
            out.append(l)
            continue
        if sec == "*NODE" and len(l) >= 8:
            out.append(("%*s" % (fw, l[0:8].strip())) + l[8:])
            continue
        if sec and sec.startswith("*ELEMENT"):
            toks = [l[i:i + 8].strip() for i in range(0, len(l), 8)]
            if toks and all(t == "" or t.lstrip("-").isdigit() for t in toks):
                out.append("".join("%*s" % (fw, t) for t in toks))
                continue
        out.append(l)
    open(dst, "w").write("\n".join(out) + "\n")


def section_line_lengths(path):
    """{섹션: {줄 길이 집합}} — 한 섹션 안에서 폭이 갈리면 집합이 둘 이상이 된다."""
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return {}
    out, sec = {}, None
    for l in lines:
        if l.startswith("*"):
            sec = l.strip().upper()
            continue
        if sec and l and not l.startswith("$"):
            out.setdefault(sec, set()).add(len(l))
    return out


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

    print("[elform 강등(QUAD8→QUAD4)도 덱 폭을 따라간다]")
    # ⚠ 이 갈래는 201e0c8 이 이웃(convert·disconnect)을 고칠 때 **빠졌다.** 같은 함수 안인데
    # `setw(8)` 이 남아, I10 덱이 `*KEYWORD I10=Y` 를 단 채 8칸 요소 줄을 냈다.
    for name, want_fw in (("s8", 8), ("s10", 10)):
        write_shell_deck(os.path.join(d, name + ".k"), want_fw)
        open(os.path.join(d, "e_%s.yaml" % name), "w").write(
            "base_model: %s.k\noutput: e_%s\noperations:\n  - type: elform\n"
            "    target_elform: 2\n" % (name, name))
        rc, out = run(binary, d, "assemble", "e_%s.yaml" % name)
        check("%s elform rc=0" % name, rc == 0, out[-250:])
        ep = os.path.join(d, "e_%s.k" % name)
        c = cards(ep, "*ELEMENT_SHELL", 1) if os.path.exists(ep) else []
        check("%s 강등된 셸 카드가 %d칸이다" % (name, want_fw),
              bool(c) and field_width(c[0], 6) == want_fw,
              "len=%d %r" % (len(c[0]), c[0]) if c else "카드 없음")

    print("[meshfix 도 덱 폭을 따라간다]")
    # ⚠ `meshfix` 는 덱의 칸 폭을 **아예 읽지 않고** 언제나 8칸으로 썼다. `*KEYWORD I10=Y` 를
    # 그대로 보존한 채 8칸 카드를 내보내므로 LS-DYNA 가 10칸으로 읽어 노드 번호가 뭉개진다.
    # ⚠ gmsh 가 없으면 **skip 이 아니라 FAIL** 이다 — 그 skip 안에 실제 결함이 숨어 있었다.
    g = os.environ.get("KOOREMAPPER_GMSH") or os.path.join(REPO, "dist", "gmsh", "gmsh")
    if not os.path.exists(g):
        check("gmsh 를 찾았다(KOOREMAPPER_GMSH 나 dist/gmsh/gmsh)", False,
              "meshfix 갈래를 검사할 수 없다 — 건너뛰지 않는다")
    else:
        src = os.path.join(REPO, "examples", "mesh", "tetramesh.k")
        if not os.path.exists(src):
            check("meshfix 예제 덱이 있다", False, src)
        else:
            for name, fw in (("t8", 8), ("t10", 10)):
                rewrite_deck_width(src, os.path.join(d, name + ".k"), fw)
                open(os.path.join(d, "mf_%s.yaml" % name), "w").write(
                    "model: %s.k\noutput: mf_%s.k\npid: 1\n" % (name, name))
                e = dict(os.environ); e["KOOREMAPPER_GMSH"] = g
                p = subprocess.run([binary, "meshfix", "mf_%s.yaml" % name], cwd=d,
                                   capture_output=True, text=True, timeout=900, env=e)
                check("%s meshfix rc=0" % name, p.returncode == 0,
                      (p.stdout + p.stderr)[-250:])
                op = os.path.join(d, "mf_%s.k" % name)
                lens = section_line_lengths(op)
                check("%s meshfix *NODE 가 %d칸이다" % (name, fw),
                      lens.get("*NODE") == {fw + 16 * 3}, lens.get("*NODE"))
                check("%s meshfix *ELEMENT_SOLID 가 %d칸이다" % (name, fw),
                      lens.get("*ELEMENT_SOLID") == {fw * 10}, lens.get("*ELEMENT_SOLID"))

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
