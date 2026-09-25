#!/usr/bin/env python3
"""8칸 덱에 9자리 ID 가 생기면 **자르지도 넘기지도 않고 거절**하나.

왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P1-2):

  새 노드·요소 카드는 `std::setw(fw)` 로 쓴다. 그런데 `std::setw` 은 값이 폭보다 길면
  **자르지 않고 칸을 늘린다.** 그래서 8칸 덱에서 노드 ID 가 100000000 으로 올라가면 그 줄만
  한 칸 길어지고, 뒤따르는 좌표가 통째로 밀린다 — **rc=0 이고 경고가 없다.**

  실측(수정 전, `offset` 으로 노드를 더한 8칸 덱):

      *NODE           len=56 8줄 · len=57 8줄      ← 8줄이 칸을 넘겼다
      *ELEMENT_SOLID  len=80 1줄 · len=84 6줄
      엄격 8칸으로 다시 읽으면 *NODE 16줄이 **고유 9개**로 뭉친다(중복 7)

  구조 카운트는 전부 정상이라 아무도 못 알아본다. LS-DYNA 는 8칸으로 읽으므로 노드가 겹치고
  요소는 없는 노드를 가리킨다. `e2281b3`(control 칸)·`d194c49`(ORTHO 거절)와 같은 규약을 쓴다 —
  **반쯤 맞는 덱을 내느니 멈춘다.**

  ⚠ 8칸 덱의 정상 범위는 건드리지 않는다. 예제 42 op 의 산출 덱 sha256 이 전부 그대로임을
  별도로 확인했다.

usage: test_id_width_overflow.py <KooRemapper 바이너리>
"""
import os
import subprocess
import sys
import tempfile

FAILS = []


def check(name, cond, detail=""):
    print("  %-62s %s" % (name[:62], "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:250]) if detail else ""))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def cube_deck(path, first_nid, fw=8):
    """8 노드 육면체 하나. `first_nid` 로 ID 대역을 정한다."""
    ifmt = "%%%dd" % fw
    pts = [(i, j, k) for k in range(2) for j in range(2) for i in range(2)]
    ids = [first_nid + n for n in range(8)]
    head = "*KEYWORD I10=Y" if fw == 10 else "*KEYWORD"
    L = [head, "*PART", "cube", (ifmt * 3) % (1, 1, 1),
         "*SECTION_SOLID", (ifmt * 2) % (1, 1),
         "*MAT_ELASTIC", (ifmt % 1) + "%10.3g%10.3g%10.3g" % (7.85e-9, 210000.0, 0.3), "*NODE"]
    for n, (x, y, z) in zip(ids, pts):
        L.append((ifmt % n) + "%16.7f%16.7f%16.7f" % (x, y, z))
    L.append("*ELEMENT_SOLID")
    L.append((ifmt * 2) % (1, 1) + "".join(ifmt % n for n in ids))
    L.append("*END")
    open(path, "w").write("\n".join(L) + "\n")


_OFFSET_YAML = ("base_model: base.k\noutput: out\noperations:\n  - type: offset\n"
                "    source_pid: 1\n    element_type: solid\n    thickness: 1.0\n"
                "    num_layers: 1\n    offset_direction: \"+z\"\n"
                "    connection_mode: tied\n    new_pid: 10\n")


def line_lengths(path, keyword):
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return {}
    out, sec = {}, None
    for l in lines:
        if l.startswith("*"):
            sec = l.strip().upper()
            continue
        if sec == keyword and l and not l.startswith("$"):
            out[len(l)] = out.get(len(l), 0) + 1
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: test_id_width_overflow.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2

    print("[A 8칸 덱에서 새 ID 가 9자리가 되면 거절한다]")
    d = tempfile.mkdtemp(prefix="idw_bad_")
    cube_deck(os.path.join(d, "base.k"), 99999992)     # 최대 99999999 — 다음이 9자리다
    open(os.path.join(d, "o.yaml"), "w").write(_OFFSET_YAML)
    rc, out = run(binary, d, "assemble", "o.yaml")
    check("rc≠0 이다", rc != 0, out[-300:])
    check("무엇이 왜 안 되는지 말한다", "고정폭 초과" in out and "노드 ID" in out, out[-300:])
    check("출력 파일을 쓰지 않았다", not os.path.exists(os.path.join(d, "out.k")),
          "out.k 가 생겼다")

    print("[B 같은 op 이 평범한 8칸 덱에서는 그대로 돈다]")
    d2 = tempfile.mkdtemp(prefix="idw_ok_")
    cube_deck(os.path.join(d2, "base.k"), 1)
    open(os.path.join(d2, "o.yaml"), "w").write(_OFFSET_YAML)
    rc, out = run(binary, d2, "assemble", "o.yaml")
    check("rc=0", rc == 0, out[-300:])
    op = os.path.join(d2, "out.k")
    check("출력이 생겼다", os.path.exists(op), out[-200:])
    if os.path.exists(op):
        nl = line_lengths(op, "*NODE")
        check("*NODE 줄이 전부 56자다(칸을 안 넘긴다)", set(nl) == {56}, nl)

    print("[C I10 덱에서는 9자리가 정상이다 — 폭 판정이 덱을 따라간다]")
    d3 = tempfile.mkdtemp(prefix="idw_i10_")
    cube_deck(os.path.join(d3, "base.k"), 99999992, fw=10)
    open(os.path.join(d3, "o.yaml"), "w").write(_OFFSET_YAML)
    rc, out = run(binary, d3, "assemble", "o.yaml")
    check("I10 덱에서는 rc=0", rc == 0, out[-300:])
    op3 = os.path.join(d3, "out.k")
    check("I10 출력이 생겼다", os.path.exists(op3), out[-200:])
    if os.path.exists(op3):
        nl = line_lengths(op3, "*NODE")
        check("I10 *NODE 줄이 전부 58자다(10+16*3)", set(nl) == {58}, nl)

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
