#!/usr/bin/env python3
"""`KFileWriter` 로 나가는 op 이 `*NODE` 의 TC/RC 와 칸 폭을 지키는가 (P1-2 확장).

왜 이 시험이 있나 (2026-09-26 실측 감사가 찾았다):

  `src/parser/KFileWriter.cpp` 가 `*NODE` 를 **id + x + y + z 로만** 썼다. 한 자리에서 두 가지가
  틀렸다.

    ① **TC/RC 칸을 버렸다.** 전 자유도 구속(`TC=7 RC=7`)을 준 노드가 **구속 없는 노드로** 나갔고
       rc=0 으로 성공을 보고했다. 데이터가 세 군데서 떨어지고 있었다 —
       리더가 그 칸을 읽지 않았고(주석에 `ignored` 라고 적혀 있었다) · `Node` 가 그 칸을 아예
       안 들고 있었고 · `MeshRemapper` 가 새 `Node` 를 만들며 또 떨어뜨렸다.
    ② **ID 칸 폭이 `setw(8)` 로 못 박혀 있었다.** 원본의 `*KEYWORD I10=Y` 는 그대로 베껴
       나가므로 **선언은 10칸인데 본문은 8칸인 덱**이 나갔다.

  ⚠ **왕복 회귀는 이것을 구조적으로 못 잡는다.** LF 판과 CRLF 판을 **서로** 비교하므로 양쪽에서
  똑같이 잃으면 초록이다. 그래서 별도로 못 박는다.

  TC/RC 는 **둘 중 하나라도 0 이 아닐 때만** 쓴다. 그래야 구속이 없는 덱의 출력 바이트가
  그대로다(옛 바이너리와 42 op 전수 대조로 확인했다 — 모든 파일 바이트 동일).

usage: test_node_constraints.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:400]) if detail else ""))


def node_lines(path):
    out, inn = [], False
    for l in open(path, encoding="latin-1", newline="").read().split("\n"):
        if l.startswith("*NODE"):
            inn = True
            continue
        if l.startswith("*"):
            if inn:
                break
            continue
        if inn and l.strip() and not l.startswith("$"):
            out.append(l.rstrip("\r"))
    return out


def elem_lines(path, kw="*ELEMENT_SOLID"):
    out, inn = [], False
    for l in open(path, encoding="latin-1", newline="").read().split("\n"):
        if l.startswith(kw):
            inn = True
            continue
        if l.startswith("*"):
            if inn:
                break
            continue
        if inn and l.strip() and not l.startswith("$"):
            out.append(l.rstrip("\r"))
    return out


def stage(d, pairs, *, constrain=0, keyword=None):
    """예제 덱을 임시 폴더로 옮기고, 앞 `constrain` 개 노드에 TC=RC=7 을 붙인다."""
    for src, dst in pairs:
        rows, inn, n = [], False, 0
        seen_keyword = False
        for l in open(os.path.join(REPO, src), encoding="latin-1", newline="").read().split("\n"):
            if keyword and l.upper().startswith("*KEYWORD"):
                rows.append(keyword)
                seen_keyword = True
                continue
            # ⚠ `examples/arc30/*.k` 에는 `*KEYWORD` 줄이 **아예 없다**(리포 실측). 그래서
            # 바꿔 치기만 하면 선언이 안 들어가고 덱이 표준 8칸으로 남는다 — 처음에 이 픽스처로
            # 시험이 실패했고 코드가 아니라 픽스처가 틀린 것이었다. 없으면 첫 키워드 앞에 넣는다.
            if keyword and not seen_keyword and l.startswith("*"):
                rows.append(keyword)
                seen_keyword = True
            if l.startswith("*NODE"):
                inn = True
                rows.append(l)
                continue
            if l.startswith("*"):
                inn = False
                rows.append(l)
                continue
            if inn and l.strip() and not l.startswith("$"):
                n += 1
                if n <= constrain:
                    l = l.rstrip() + "%8d%8d" % (7, 7)
            rows.append(l)
        text = "\n".join(rows)
        # ⚠ **선언만 바꾸면 안 된다.** 데이터가 8칸인 채로 `i10=y` 를 달면 리더가 (옳게) 칸을
        # 10 으로 읽어 노드 ID 가 어긋나고 "없는 노드를 가리킨다" 로 거절한다 — 처음에 그렇게
        # 실패했고 그것은 **리더가 맞은 것**이었다. 진짜 i10 덱을 만들려면 본문도 넓혀야 한다.
        if keyword and "I10" in keyword.upper():
            text = _widen_to_i10(text)
        open(os.path.join(d, dst), "w", newline="\n").write(text)


def _widen_to_i10(text):
    """8칸 덱을 **진짜** i10 덱으로 다시 쓴다 — ID 칸 10, 좌표 칸 16 그대로."""
    out, sect = [], None
    for l in text.split("\n"):
        if l.startswith("*"):
            u = l.upper()
            sect = "NODE" if u.startswith("*NODE") else ("ELEM" if u.startswith("*ELEMENT") else None)
            out.append(l)
            continue
        if not l.strip() or l.startswith("$") or sect is None:
            out.append(l)
            continue
        if sect == "NODE":
            nid = l[:8].strip()
            rest = [l[8 + i * 16:8 + (i + 1) * 16] for i in range(3)]
            tail = l[56:]          # TC/RC 가 붙어 있으면 10칸으로 다시 쓴다
            row = "%10s%s" % (nid, "".join(rest))
            if tail.strip():
                vals = [tail[i * 8:(i + 1) * 8].strip() for i in range(2)]
                row += "".join("%10s" % (v or "0") for v in vals)
            out.append(row)
        else:
            f = [l[i * 8:(i + 1) * 8].strip() for i in range(len(l) // 8)]
            out.append("".join("%10s" % x for x in f if x != ""))
    return "\n".join(out)


def run(binary, d, argv):
    p = subprocess.run([binary] + argv, capture_output=True, text=True, timeout=900, cwd=d)
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print("usage: test_node_constraints.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2

    ARC = [("examples/arc30/arc30_bent.k", "bent.k"), ("examples/arc30/arc30_flat.k", "flat.k")]
    SHELL = [("examples/shellmap_arc/arc_shell.k", "s.k"), ("examples/shellmap_arc/arc_flat.k", "f.k")]

    print("[A 구속(TC/RC)을 들고 간다]")
    for label, pairs, argv in (
        ("map", ARC, ["map", "bent.k", "flat.k", "out.k"]),
        ("shellmap", SHELL, ["shellmap", "s.k", "f.k", "out.k"]),
    ):
        d = tempfile.mkdtemp(prefix="nc_%s_" % label)
        stage(d, pairs, constrain=3)
        rc, out = run(binary, d, argv)
        check("A %s rc=0" % label, rc == 0, out[-240:])
        op = os.path.join(d, "out.k")
        if os.path.exists(op):
            nl = node_lines(op)
            got = [l for l in nl if l.split()[-2:] == ["7", "7"]]
            check("A %s 구속 3개가 출력에 남는다" % label, len(got) == 3,
                  "남은 줄 %d개 / 첫 줄=%r" % (len(got), nl[0] if nl else None))
            # 구속이 없는 노드에는 칸을 붙이지 않는다 — 0 을 써 넣으면 바이트가 달라진다.
            plain = [l for l in nl if len(l) == 56]
            check("A %s 구속 없는 노드는 56자 그대로" % label, len(plain) == len(nl) - 3,
                  "56자 %d / 전체 %d" % (len(plain), len(nl)))
        else:
            check("A %s 산출물이 생겼다" % label, False, out[-240:])
        shutil.rmtree(d, ignore_errors=True)

    print("[B 덱이 선언한 칸 폭을 따른다]")
    d = tempfile.mkdtemp(prefix="nc_i10_")
    stage(d, ARC, keyword="*KEYWORD i10=y")
    rc, out = run(binary, d, ["map", "bent.k", "flat.k", "out.k"])
    check("B-1 i10 덱 map rc=0", rc == 0, out[-240:])
    op = os.path.join(d, "out.k")
    if os.path.exists(op):
        nl, el = node_lines(op), elem_lines(op)
        # i10: ID 10칸 + 좌표 3×16 = 58자
        check("B-2 *NODE 가 58자다(ID 10칸)", nl and len(nl[0]) == 58,
              "길이=%s 첫 줄=%r" % (len(nl[0]) if nl else None, nl[0] if nl else None))
        # i10: 10칸 × 10필드 = 100자
        check("B-3 *ELEMENT 가 100자다(10칸 × 10)", el and len(el[0]) == 100,
              "길이=%s 첫 줄=%r" % (len(el[0]) if el else None, el[0] if el else None))
    else:
        check("B 산출물이 생겼다", False, out[-240:])
    shutil.rmtree(d, ignore_errors=True)

    print("[C 구속이 없는 8칸 덱은 예전과 같은 모양이다]")
    d = tempfile.mkdtemp(prefix="nc_plain_")
    stage(d, ARC)
    rc, out = run(binary, d, ["map", "bent.k", "flat.k", "out.k"])
    op = os.path.join(d, "out.k")
    if rc == 0 and os.path.exists(op):
        nl, el = node_lines(op), elem_lines(op)
        check("C-1 *NODE 는 56자(8+16×3) — 칸이 늘지 않았다", all(len(l) == 56 for l in nl),
              "다른 길이: %r" % sorted({len(l) for l in nl}))
        check("C-2 *ELEMENT 는 80자(8칸 × 10)", all(len(l) == 80 for l in el),
              "다른 길이: %r" % sorted({len(l) for l in el}))
    else:
        check("C map rc=0", False, out[-240:])
    shutil.rmtree(d, ignore_errors=True)

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
