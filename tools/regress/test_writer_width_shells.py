#!/usr/bin/env python3
# 메시 쓰기가 덱의 칸 폭을 지키고 셸 블록 · 솔리드를 잃지 않는지 보는 회귀 시험(tetremesh · unfold · map · squeeze · id_floor)
"""메시 쓰기의 칸 폭 · 셸 블록 · 번호 바닥의 정수 범위 (2026-11-21 — 11-08 에 「다음 판」 으로 미뤘던 결함과 재다 나온 것).

왜 이 시험이 있나.

  쓰기 함수(`KFileWriter`)가 폭을 한 자리에서 정하지 않았고, 원본 글을 리더와 다른 두 번째 해석기로 다시 읽었다. rc 0 으로 나가던 것들.
  · tetremesh — 8절점 셸을 4절점으로 썼다 · `*ELEMENT_SHELL_THICKNESS` 의 두께 카드를 버렸다 · `I10=Y` 덱을 맨 `*KEYWORD` 아래
    8칸으로 썼다(번호가 9자리면 칸이 붙은 깨진 덱)
  · map · squeeze — `LONG=Y` 덱의 좌표 칸을 16 으로 썼다(절점 줄 68자 — 규격 80) · 셸 블록의 줄을 8칸으로 다시 읽어
    (`I10=Y` 셸 줄 · 두께 카드 · 리더가 안 읽는 `_BETA` · `_COMPOSITE` 블록의 줄) 거기서 나온 수와 번호가 같은 솔리드를 빼고 썼다 ·
    `*NODE%` 처럼 접미사를 붙여 쓴 블록은 그대로 베끼고 메시에서 한 번 더 썼다(절점 · 솔리드가 두 번)
  · unfold — `I10=Y` · `LONG=Y` 덱을 맨 `*KEYWORD` 아래 8칸으로 썼다
  · id_floor — 요소 번호 2147483647 인 덱에 `elem_start: 2147483648` 을 냈다(LS-DYNA 정수 상한 밖 — Vol_I 19325)

  이제 쓰기는 덱이 선언한 폭 하나로 `*KEYWORD` · 정수 칸 · 실수 칸을 쓰고, 번호가 그 칸에 안 들어가면 쓰지 않는다. 원본을 따라 쓰는
  길은 블록을 리더의 키워드 이름으로 가르고 메시의 사실(QUAD4 · 두께 셸 표지)만 본다. tetremesh 는 리더가 읽은 셸 · 두께 셸 블록을
  원본에서 그대로 옮긴다. id_floor 는 다음 번호가 정수 상한을 넘으면 거절한다.

무엇을 보나(번호는 계획 `deferred-defects-round2-1120.plan.md` §1 표).
  S   표준 덱 — tetremesh 산출은 맨 `*KEYWORD` · 절점 줄 56자 · 4절점 셸 줄 그대로
  T-2 tetremesh — 8절점 셸 줄 그대로            T-3 tetremesh — `*ELEMENT_SHELL_THICKNESS` 키워드 · 두 줄 카드 그대로
  T-4 tetremesh — `I10=Y` 덱(작은 번호 · 9자리 번호)은 `*KEYWORD I10=Y` · 10칸 · 번호 집합 그대로
  T-5 tetremesh — 인클루드 안의 셸도 `flatten_includes` 로 펼친 덱에서 그대로
  T-7 tetremesh — 첫 `*END` 뒤의(읽히지 않는) 셸 블록은 산출에 살아나지 않는다
  W-3 표준 덱의 `%` 블록에 9자리 번호 — tetremesh · squeeze 는 rc 1 · 산출 없음 · 까닭에 번호
  I-1 id_floor — 최대 2147483647 은 rc 1 · JSON 없음 / 최대 2147483646 은 rc 0 · `elem_start` 2147483647
  N-1 `I10=Y` · `LONG=Y` 메시 덱 × unfold · map · squeeze · tetremesh — 선언 · 줄 길이 · 번호 집합(map 은 좌표도)
  N-2 squeeze — `I10=Y` 덱의 10칸 셸 1001~1005 가 있어도 솔리드 100 개 전부
  N-3 squeeze — 두께 카드(1.0 · 2.5 · 37.0)가 있어도 솔리드 전부 · 카드 그대로
  N-4 squeeze — 리더가 안 읽는 `*ELEMENT_TSHELL_BETA` · `*ELEMENT_SHELL_COMPOSITE` 블록이 있어도 솔리드 전부 · 블록 그대로
  N-6 squeeze · map — `*NODE%` · `*ELEMENT_SOLID%`(공백 없는 접미사) 블록은 한 번만(198 · 100)
  N-7 `*NODE-` · `*ELEMENT_SOLID-` · `*ELEMENT_SHELL-`(공백 없는 표준 폭 접미사) × unfold · map · squeeze · tetremesh — 공백 있는 꼴과
      산출이 바이트까지 같다(표준 덱은 맨 키워드 덱과도 같다) · `LONG=Y` 덱 안에서도 그 블록은 표준 폭으로 읽는다
  M-1 map — 평판의 두께 셸은 `*ELEMENT_SOLID` 에 없고 `*ELEMENT_TSHELL` 블록 그대로

usage: test_writer_width_shells.py <KooRemapper 바이너리>
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []
INT_MAX = 2147483647

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")
SQ = "parts:\n  - pid: 1\n    eps_x: -0.01\n    eps_y: -0.01\n    eps_z: 0.0\nmaterial:\n  E: 210000.0\n  nu: 0.3\n"
TET = "model: box.k\noutput: tet_out.k\nbackend: localimprove\ntarget_pids: [1]\n"
SKIN = ("*SECTION_SHELL\n$#   secid    elform\n         2         2\n       0.1       0.1       0.1       0.1\n"
        "*PART\nSKIN\n$#     pid     secid       mid\n         2         2         1\n")
OPS = (("unfold", ("unfold", "box.k", "unf.k"), "unf.k"), ("map", ("map", "box.k", "box.k", "map.k"), "map.k"),
       ("squeeze", ("squeeze", "box.k", "sq.yaml", "sq"), "sq.k"), ("tetremesh", ("tetremesh", "tet.yaml"), "tet_out.k"))


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-500:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def lines_of(path):
    return open(path, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(path) else []


def blocks(path):
    """[(키워드 줄, [데이터 줄 …])] — 첫 `*END` 앞까지. `$` 줄 · 빈 줄은 뺀다."""
    out = []
    for l in lines_of(path):
        if l.startswith("*"):
            if l.split()[0].upper() == "*END":
                break
            out.append((l, []))
        elif out and l.strip() and not l.startswith("$"):
            out[-1][1].append(l)
    return out


def rows(path, name):
    """이름이 name 인 블록들의 데이터 줄 — 폭 접미사(`%` `+` `-`)는 붙었든 띄었든 같은 이름으로 본다."""
    return [r for kw, data in blocks(path) if kw.split()[0].upper().rstrip("%+-") == name for r in data]


def kwlines(path, prefix):
    return [kw for kw, _ in blocks(path) if kw.upper().startswith(prefix)]


def ids(data, w):
    return [int(r[:w]) for r in data]


def case_dir(root, name, binary):
    """새 폴더에 상자 덱(육면체 10×5×2 — 절점 198 · 솔리드 100)을 짓고 그 글을 돌려준다."""
    d = os.path.join(root, name)
    os.makedirs(d)
    write(os.path.join(d, "box.yaml"), BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    assert rc == 0, out[-300:]
    write(os.path.join(d, "sq.yaml"), SQ)
    write(os.path.join(d, "tet.yaml"), TET)
    return d, open(os.path.join(d, "box.k"), encoding="utf-8").read()


def quads():
    """상자 아래 · 윗면의 사각형 절점(생성기의 절점 번호 규칙 — i + 11 j + 66 k + 1)."""
    return [(n, n + 1, n + 12, n + 11) for k in (0, 2) for j in range(5) for i in range(10)
            for n in (1 + i + 11 * j + 66 * k,)]


def hexes(text):
    out, on = [], False
    for l in text.splitlines():
        if l.startswith("*"):
            on = l.split()[0].upper() == "*ELEMENT_SOLID"
        elif on and l.strip() and not l.startswith("$"):
            out.append([int(x) for x in l.split()])
    return out


def shell_block(kw, eids, tail=(), card2=""):
    return SKIN + kw + "\n" + "".join(
        "".join("%8d" % v for v in (e, 2) + q + tuple(tail)) + "\n" + card2 for e, q in zip(eids, quads()))


def put(d, text, block):
    write(os.path.join(d, "box.k"), text.replace("*END", block + "*END", 1))


def to_i10(text, shift, decl="*KEYWORD I10=Y", suffix=""):
    """절점 · 솔리드 · 셸 블록의 정수 칸을 10칸으로 다시 쓴다(번호에 shift 를 더한다). 다른 카드는 그대로다."""
    out, kw = [], ""
    for l in text.splitlines():
        if l.startswith("*"):
            kw = l.split()[0].upper()
            out.append(decl if kw == "*KEYWORD" else l + suffix if kw in ("*NODE", "*ELEMENT_SOLID", "*ELEMENT_SHELL") else l)
        elif l.startswith("$") or not l.strip():
            out.append(l)
        elif kw == "*NODE":
            out.append("%10d%s" % (int(l[:8]) + shift, l[8:56]))
        elif kw in ("*ELEMENT_SOLID", "*ELEMENT_SHELL"):
            f = [int(x) for x in l.split()]
            out.append("%10d%10d" % (f[0] + shift, f[1]) + "".join("%10d" % (x + shift) for x in f[2:]))
        else:
            out.append(l)
    return "\n".join(out) + "\n"


def mesh_only(text, w, decl):
    """절점 · 솔리드만 폭 w 로 쓴 덱(실수 칸은 w = 20 이면 20, 아니면 16). `LONG=Y` 는 모든 카드의 폭을 바꾸므로 메시만 남긴다."""
    out, kw, rw = ["*KEYWORD" + decl], "", 20 if w == 20 else 16
    for l in text.splitlines():
        if l.startswith("*"):
            kw = l.split()[0].upper()
            if kw in ("*NODE", "*ELEMENT_SOLID"):
                out.append(kw)
        elif l.startswith("$") or not l.strip():
            continue
        elif kw == "*NODE":
            f = l.split()
            out.append("%*d" % (w, int(f[0])) + "".join("%*.9e" % (rw, float(x)) for x in f[1:4]))
        elif kw == "*ELEMENT_SOLID":
            out.append("".join("%*d" % (w, int(x)) for x in l.split()))
    return "\n".join(out) + "\n*END\n"


def tet(binary, d):
    rc, out = run(binary, d, "tetremesh", "tet.yaml")
    return rc, out, os.path.join(d, "tet_out.k")


def squeeze(binary, d):
    rc, out = run(binary, d, "squeeze", "box.k", "sq.yaml", "sq")
    return rc, out, os.path.join(d, "sq.k")


def same_rows(tag, src, out, name, n):
    """블록 name 의 데이터 줄이 원본과 글자까지 같고 n 줄인가."""
    a, b = rows(src, name), rows(out, name)
    return check("%s — %s 블록 %d 줄이 원본 그대로" % (tag, name, n), len(a) == n and a == b, "원본 %d 줄 · 산출 %d 줄 %r" % (len(a), len(b), b[:2]))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="koorm_writer_width_")
    try:
        return body(binary, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def body(binary, root):
    print("[S · T] tetremesh — 셸 블록과 칸 폭")
    d, s = case_dir(root, "s", binary)
    put(d, s, shell_block("*ELEMENT_SHELL", range(1001, 1006)))
    rc, out, o = tet(binary, d)
    L = lines_of(o)
    check("S 표준 덱 — rc 0 · 첫 줄은 맨 *KEYWORD", rc == 0 and L[:1] == ["*KEYWORD"], "rc %d %r %s" % (rc, L[:1], out[-300:]))
    nd = rows(o, "*NODE")
    check("S 표준 덱 — 절점 198 줄 · 줄마다 56자", len(nd) == 198 and {len(r) for r in nd} == {56}, "%d %r" % (len(nd), nd[:1]))
    check("S 표준 덱 — 솔리드 100 줄", len(rows(o, "*ELEMENT_SOLID")) == 100, len(rows(o, "*ELEMENT_SOLID")))
    same_rows("S 표준 덱", os.path.join(d, "box.k"), o, "*ELEMENT_SHELL", 5)

    d, s = case_dir(root, "t2", binary)
    put(d, s, shell_block("*ELEMENT_SHELL", range(1001, 1006), tail=(190, 191, 192, 193)))
    rc, out, o = tet(binary, d)
    check("T-2 8절점 셸 — rc 0", rc == 0, out[-300:])
    same_rows("T-2 8절점 셸", os.path.join(d, "box.k"), o, "*ELEMENT_SHELL", 5)

    d, s = case_dir(root, "t3", binary)
    put(d, s, shell_block("*ELEMENT_SHELL_THICKNESS", range(1001, 1006), card2="%16.5f%16.5f%16.5f%16.5f\n" % ((0.7,) * 4)))
    rc, out, o = tet(binary, d)
    check("T-3 두께 셸 카드 — rc 0 · 키워드가 *ELEMENT_SHELL_THICKNESS", rc == 0 and kwlines(o, "*ELEMENT_SHELL") == ["*ELEMENT_SHELL_THICKNESS"],
          "rc %d %r" % (rc, kwlines(o, "*ELEMENT_SHELL")))
    same_rows("T-3 두께 셸 카드", os.path.join(d, "box.k"), o, "*ELEMENT_SHELL_THICKNESS", 10)

    for tag, shift in (("T-4a I10 작은 번호", 0), ("T-4b I10 9자리 번호", 200000000)):
        d, s = case_dir(root, "t4_%d" % shift, binary)
        write(os.path.join(d, "box.k"), to_i10(s.replace("*END", shell_block("*ELEMENT_SHELL", range(1001, 1006)) + "*END", 1), shift))
        src = os.path.join(d, "box.k")
        rc, out, o = tet(binary, d)
        L = lines_of(o)
        check(tag + " — rc 0 · 첫 줄 *KEYWORD I10=Y", rc == 0 and L[:1] == ["*KEYWORD I10=Y"], "rc %d %r %s" % (rc, L[:1], out[-300:]))
        nd, el = rows(o, "*NODE"), rows(o, "*ELEMENT_SOLID")
        check(tag + " — 절점 번호 집합이 원본과 같다(10칸 · 줄 58자)",
              bool(nd) and {len(r) for r in nd} == {58} and ids(nd, 10) == ids(rows(src, "*NODE"), 10), nd[:1])
        check(tag + " — 솔리드 줄이 원본과 같다(10칸 · 줄 100자)", bool(el) and el == rows(src, "*ELEMENT_SOLID"), el[:1])
        same_rows(tag, src, o, "*ELEMENT_SHELL", 5)

    d, s = case_dir(root, "t5", binary)
    put(d, s, "*INCLUDE\nskin.k\n")
    write(os.path.join(d, "skin.k"), "*KEYWORD\n" + shell_block("*ELEMENT_SHELL", range(1001, 1006), tail=(190, 191, 192, 193)) + "*END\n")
    write(os.path.join(d, "tet.yaml"), TET + "flatten_includes: true\n")
    rc, out, o = tet(binary, d)
    check("T-5 인클루드 안의 8절점 셸 — rc 0", rc == 0, out[-300:])
    same_rows("T-5 인클루드 안의 8절점 셸", os.path.join(d, "skin.k"), o, "*ELEMENT_SHELL", 5)

    d, s = case_dir(root, "t7", binary)
    write(os.path.join(d, "box.k"), s + shell_block("*ELEMENT_SHELL", range(3001, 3006)) + "*END\n")
    rc, out, o = tet(binary, d)
    L = lines_of(o)
    check("T-7 첫 *END 뒤의 셸 블록 — rc 0 · 산출에 살아나지 않는다(*END 하나 · 셸 블록 0)",
          rc == 0 and sum(1 for l in L if l.startswith("*END")) == 1 and not [l for l in L if l.upper().startswith("*ELEMENT_SHELL")],
          "rc %d *END %d %r" % (rc, sum(1 for l in L if l.startswith("*END")), [l for l in L if l.upper().startswith("*ELEMENT_SHELL")]))

    print("[W-3] 표준 덱의 % 블록에 9자리 번호 — 8칸에 안 들어간다")
    for op, fn in (("tetremesh", tet), ("squeeze", squeeze)):
        d, s = case_dir(root, "w3_" + op, binary)
        write(os.path.join(d, "box.k"), to_i10(s, 200000000, decl="*KEYWORD", suffix=" %"))
        rc, out, o = fn(binary, d)
        check("W-3 %s — rc 1 · 산출 없음" % op, rc == 1 and not os.path.exists(o), "rc %d made %s %s" % (rc, os.path.exists(o), out[-300:]))
        check("W-3 %s — 까닭에 번호와 칸 폭" % op, "2000000" in out and "8" in out and "칸" in out, out[-400:])

    print("[I-1] id_floor — 다음 번호가 정수 상한을 넘는가")
    for tag, top, want_rc in (("최대 2147483647", INT_MAX, 1), ("최대 2147483646", INT_MAX - 1, 0)):
        d, s = case_dir(root, "i1_%d" % want_rc, binary)
        blk = "*ELEMENT_SOLID %\n" + "".join("%10d" % v for v in (top, 1, 1, 2, 13, 12, 67, 68, 79, 78)) + "\n"
        write(os.path.join(d, "box.k"), to_i10(s, 0).replace("*END", blk + "*END", 1))
        write(os.path.join(d, "f.yaml"), "model: box.k\noutput: floor.json\n")
        rc, out = run(binary, d, "id_floor", "f.yaml")
        p = os.path.join(d, "floor.json")
        if want_rc:
            check("I-1 %s — rc 1 · JSON 없음 · 까닭에 상한" % tag, rc == 1 and not os.path.exists(p) and str(INT_MAX) in out,
                  "rc %d made %s %s" % (rc, os.path.exists(p), out[-300:]))
        else:
            got = json.load(open(p)).get("elem_start") if os.path.exists(p) else None
            check("I-1 %s — rc 0 · elem_start 2147483647" % tag, rc == 0 and got == INT_MAX, "rc %d %r %s" % (rc, got, out[-300:]))

    print("[N-1] I10=Y · LONG=Y 메시 덱 — 선언 · 줄 길이 · 번호")
    for tag, w, decl in (("I10=Y", 10, " I10=Y"), ("LONG=Y", 20, " LONG=Y")):
        d, s = case_dir(root, "n1_%d" % w, binary)
        write(os.path.join(d, "box.k"), mesh_only(s, w, decl))
        src = os.path.join(d, "box.k")
        rw = 20 if w == 20 else 16
        for op, args, outn in OPS:
            rc, out = run(binary, d, *args)
            o = os.path.join(d, outn)
            nd, el = rows(o, "*NODE"), rows(o, "*ELEMENT_SOLID")
            name = "N-1 %s %s" % (tag, op)
            check(name + " — rc 0 · 선언이 *KEYWORD%s 하나" % decl, rc == 0 and kwlines(o, "*KEYWORD") == ["*KEYWORD" + decl],
                  "rc %d %r %s" % (rc, kwlines(o, "*KEYWORD"), out[-300:]))
            check(name + " — 절점 줄 %d자 · 번호 1~198" % (w + 3 * rw), bool(nd) and {len(r) for r in nd} == {w + 3 * rw}
                  and sorted(ids(nd, w)) == list(range(1, 199)), "%d 줄 %r" % (len(nd), nd[:1]))
            check(name + " — 솔리드 줄 %d자 · 100 개" % (10 * w), len(el) == 100 and {len(r) for r in el} == {10 * w}, "%d 줄 %r" % (len(el), el[:1]))
            if op == "map":   # 굽은 기준 = 평판 — 좌표가 그대로여야 한다(칸을 잘못 자르면 여기서 어긋난다)
                xyz = lambda r: [float(r[w + i * rw:w + (i + 1) * rw]) for i in range(3)]
                a = {int(r[:w]): xyz(r) for r in rows(src, "*NODE")}
                try:
                    bad = [r[:w] for r in nd if max(abs(p - q) for p, q in zip(xyz(r), a[int(r[:w])])) > 1e-6]
                except (ValueError, KeyError) as e:
                    bad = ["칸을 못 읽는다 — %s" % e]
                check(name + " — 좌표가 원본과 같다", bool(nd) and not bad, bad[:3])

    print("[N-2 · N-3 · N-4] squeeze — 셸 블록의 줄이 솔리드를 지우지 않는다")
    d, s = case_dir(root, "n2", binary)
    write(os.path.join(d, "box.k"), to_i10(s.replace("*END", shell_block("*ELEMENT_SHELL", range(1001, 1006)) + "*END", 1), 0))
    rc, out, o = squeeze(binary, d)
    got = ids(rows(o, "*ELEMENT_SOLID"), 10)
    check("N-2 I10=Y 덱의 10칸 셸 — rc 0 · 솔리드 100 개 전부", rc == 0 and sorted(got) == list(range(1, 101)),
          "rc %d 빠진 것 %s" % (rc, sorted(set(range(1, 101)) - set(got))))
    same_rows("N-2 I10=Y 덱의 10칸 셸", os.path.join(d, "box.k"), o, "*ELEMENT_SHELL", 5)

    for thick, fmt in ((1.0, "%16.7f"), (2.5, "%16.7f"), (37.0, "%16.9e")):
        d, s = case_dir(root, "n3_%s" % str(thick).replace(".", "_"), binary)
        put(d, s, shell_block("*ELEMENT_SHELL_THICKNESS", range(1001, 1006), card2=fmt * 4 % ((thick,) * 4) + "\n"))
        rc, out, o = squeeze(binary, d)
        got = ids(rows(o, "*ELEMENT_SOLID"), 8)
        check("N-3 두께 %s — rc 0 · 솔리드 100 개 전부" % thick, rc == 0 and sorted(got) == list(range(1, 101)),
              "rc %d 빠진 것 %s" % (rc, sorted(set(range(1, 101)) - set(got))))
        same_rows("N-3 두께 %s" % thick, os.path.join(d, "box.k"), o, "*ELEMENT_SHELL_THICKNESS", 10)

    def tshell_beta(hx, eids, beta):
        return ("*SECTION_TSHELL\n         3         1\n*PART\nTS\n         3         3         1\n*ELEMENT_TSHELL_BETA\n" + "".join(
            "%8d%8d" % (e, 3) + "".join("%8d" % n for n in h[2:10]) + "\n" + " " * 30 + "%10.3f" % beta + "\n" for e, h in zip(eids, hx)))

    def shell_comp(hx, eids):
        return "*PART\nSK\n         2         2         1\n*ELEMENT_SHELL_COMPOSITE\n" + "".join(
            "%8d%8d" % (e, 2) + "".join("%8d" % n for n in h[2:6]) + "\n" + "%10d%10.3f%10.3f" % (1, 0.1, 0.0) * 2 + "\n"
            for e, h in zip(eids, hx))

    for tag, name, mk in (("N-4a _TSHELL_BETA 같은 번호", "*ELEMENT_TSHELL_BETA", lambda hx: tshell_beta(hx, range(1, 6), 0.0)),
                          ("N-4b _TSHELL_BETA 먼 번호 · 각 45", "*ELEMENT_TSHELL_BETA", lambda hx: tshell_beta(hx, range(2001, 2006), 45.0)),
                          ("N-4c _SHELL_COMPOSITE 같은 번호", "*ELEMENT_SHELL_COMPOSITE", lambda hx: shell_comp(hx, range(1, 6))),
                          ("N-4d _SHELL_COMPOSITE 먼 번호", "*ELEMENT_SHELL_COMPOSITE", lambda hx: shell_comp(hx, range(2001, 2006)))):
        d, s = case_dir(root, "n4_" + tag[3], binary)
        put(d, s, mk(hexes(s)))
        rc, out, o = squeeze(binary, d)
        got = ids(rows(o, "*ELEMENT_SOLID"), 8)
        check(tag + " — rc 0 · 솔리드 100 개 전부", rc == 0 and sorted(got) == list(range(1, 101)),
              "rc %d 빠진 것 %s" % (rc, sorted(set(range(1, 101)) - set(got))))
        same_rows(tag, os.path.join(d, "box.k"), o, name, 10)

    print("[T-8] tetremesh — 싣지 않은 셸 · 두께 셸 변형 블록을 경고로 찍는다(산출은 그대로)")

    def skipped(out):
        """경고 줄에서 {키워드: (블록 수, 데이터 줄 수)}."""
        return {m.group(1): (int(m.group(2)), int(m.group(3))) for m in
                re.finditer(r"WARN[^\n]*싣지 않았다[^\n]*?(\*ELEMENT_\w+) 블록 (\d+) 개 · 데이터 줄 (\d+)", out)}

    def undated(path):
        return [l for l in lines_of(path) if not l.startswith("$ Date")]

    d, s = case_dir(root, "t8_plain", binary)
    hx = hexes(s)
    base = shell_block("*ELEMENT_SHELL", range(1001, 1006))
    put(d, s, base)
    rc, out, o = tet(binary, d)
    plain = undated(o)
    check("T-8 변형 없는 덱 — rc 0 · 변형 경고 없음", rc == 0 and not skipped(out) and "싣지 않았다" not in out, "rc %d %r" % (rc, skipped(out)))

    d, s = case_dir(root, "t8a", binary)
    put(d, s, base + shell_comp(hx, range(2001, 2006)) + tshell_beta(hx, range(3001, 3006), 0.0))
    rc, out, o = tet(binary, d)
    check("T-8a 안 읽는 변형 둘 — rc 0 · 키워드마다 블록 1 · 데이터 줄 10 을 경고로",
          rc == 0 and skipped(out) == {"*ELEMENT_SHELL_COMPOSITE": (1, 10), "*ELEMENT_TSHELL_BETA": (1, 10)}, "rc %d %r" % (rc, skipped(out)))
    check("T-8a 안 읽는 변형 둘 — 산출은 변형 없는 덱의 산출과 같다(변형 블록은 없다)",
          rc == 0 and undated(o) == plain and not kwlines(o, "*ELEMENT_SHELL_COMPOSITE") and not kwlines(o, "*ELEMENT_TSHELL"),
          "%d 줄 · 변형 없는 덱 %d 줄 %r" % (len(undated(o)), len(plain), kwlines(o, "*ELEMENT_")))

    d, s = case_dir(root, "t8b", binary)
    put(d, s, base + shell_comp(hx[:3], range(2001, 2004)) + "$ 주석 줄\n\n" + shell_comp(hx[3:5], range(2004, 2006)))
    rc, out, o = tet(binary, d)
    check("T-8b 같은 변형이 두 블록 · 주석과 빈 줄 — 블록 2 · 데이터 줄 10(주석 · 빈 줄은 안 센다)",
          rc == 0 and skipped(out) == {"*ELEMENT_SHELL_COMPOSITE": (2, 10)}, "rc %d %r" % (rc, skipped(out)))
    check("T-8b 같은 변형이 두 블록 — 산출은 변형 없는 덱의 산출과 같다", rc == 0 and undated(o) == plain,
          "%d 줄 · 변형 없는 덱 %d 줄" % (len(undated(o)), len(plain)))

    print("[N-6] 공백 없이 붙인 폭 접미사 — 블록을 한 번만 쓴다")
    d, s = case_dir(root, "n6", binary)
    write(os.path.join(d, "box.k"), to_i10(s, 0, decl="*KEYWORD", suffix="%"))
    for op, args, outn in OPS[1:3]:
        rc, out = run(binary, d, *args)
        o = os.path.join(d, outn)
        nd, el = rows(o, "*NODE"), rows(o, "*ELEMENT_SOLID")
        check("N-6 %s — rc 0 · 절점 198 줄 · 솔리드 100 줄(한 번씩)" % op, rc == 0 and len(nd) == 198 and len(el) == 100,
              "rc %d 절점 %d 솔리드 %d %s" % (rc, len(nd), len(el), kwlines(o, "*NODE") + kwlines(o, "*ELEMENT_SOLID")))
        check("N-6 %s — 다시 쓴 블록은 맨 키워드 아래 8칸" % op, kwlines(o, "*NODE") == ["*NODE"] and {len(r) for r in nd} == {56}
              and kwlines(o, "*ELEMENT_SOLID") == ["*ELEMENT_SOLID"] and {len(r) for r in el} == {80},
              "%s %r" % (kwlines(o, "*NODE") + kwlines(o, "*ELEMENT_SOLID"), nd[:1]))

    print("[N-7] 공백 없이 붙인 `-`(표준 폭) 접미사 — 공백 있는 꼴과 같게 읽는다")

    def suffixed(text, suf, decl=None):
        """절점 · 솔리드 · 셸 키워드 줄에 suf 를 붙인다(블록의 글은 그대로 — 표준 폭). decl 을 주면 `*KEYWORD` 줄을 바꾼다."""
        out = []
        for l in text.splitlines():
            kw = l.split()[0].upper() if l.startswith("*") else ""
            out.append(decl if kw == "*KEYWORD" and decl else l + suf if kw in ("*NODE", "*ELEMENT_SOLID", "*ELEMENT_SHELL") else l)
        return "\n".join(out) + "\n"

    def outputs(tag, text):
        d, _ = case_dir(root, tag, binary)
        write(os.path.join(d, "box.k"), text)
        res = {}
        for op, args, outn in OPS:
            rc, out = run(binary, d, *args)
            o = os.path.join(d, outn)
            res[op] = (rc, open(o, "rb").read() if os.path.exists(o) else None, o, out)
        return res

    _, s = case_dir(root, "n7_src", binary)
    plain, blank, glued = outputs("n7_plain", s), outputs("n7_blank", suffixed(s, " -")), outputs("n7_glued", suffixed(s, "-"))
    for op, _, _ in OPS:
        rc, data, o, out = glued[op]
        nd, el = rows(o, "*NODE"), rows(o, "*ELEMENT_SOLID")
        check("N-7 표준 덱 %s — rc 0 · 절점 198 줄 · 솔리드 100 줄" % op, rc == 0 and len(nd) == 198 and len(el) == 100,
              "rc %d 절점 %d 솔리드 %d %s" % (rc, len(nd), len(el), out[-300:]))
        check("N-7 표준 덱 %s — 산출이 `*NODE -`(공백) 덱 · 맨 키워드 덱의 산출과 바이트 같다" % op,
              data is not None and data == blank[op][1] and data == plain[op][1],
              "rc %d · 공백 꼴 rc %d · 맨 키워드 rc %d" % (rc, blank[op][0], plain[op][0]))
    rc, data, o, out = glued["squeeze"]
    src_nodes = rows(os.path.join(root, "n7_glued", "box.k"), "*NODE")
    check("N-7 표준 덱 squeeze — 절점 좌표가 실제로 바뀌었다(아무것도 안 누르고 rc 0 이 아니다)", rc == 0 and rows(o, "*NODE") != src_nodes
          and len(src_nodes) == 198, "rc %d" % rc)

    # 메시 밖 카드(`*PART-` · `*SECTION_SOLID-` · `*MAT_ELASTIC-` …)도 같은 규칙이다 — 붙여 쓴 꼴과 띄어 쓴 꼴의 산출은 그 키워드 줄의
    # 철자만 다르다
    def all_suffixed(text, suf):
        return "\n".join(l + suf if l.startswith("*") and l.split()[0].upper() not in ("*KEYWORD", "*END") else l
                         for l in text.splitlines()) + "\n"

    blank, glued = outputs("n7_all_blank", all_suffixed(s, " -")), outputs("n7_all_glued", all_suffixed(s, "-"))
    for op, _, _ in OPS:
        rc, data, o, out = glued[op]
        nd, el = rows(o, "*NODE"), rows(o, "*ELEMENT_SOLID")
        check("N-7 모든 키워드에 `-` %s — rc 0 · 절점 198 줄 · 솔리드 100 줄" % op, rc == 0 and len(nd) == 198 and len(el) == 100,
              "rc %d 절점 %d 솔리드 %d %s" % (rc, len(nd), len(el), out[-300:]))
        check("N-7 모든 키워드에 `-` %s — 띄어 쓴 꼴의 산출과 키워드 줄 철자만 다르다" % op, data is not None and blank[op][1] is not None
              and data == blank[op][1].replace(b" -\n", b"-\n"), "rc %d · 공백 꼴 rc %d" % (rc, blank[op][0]))

    # 셸 블록 — squeeze · tetremesh 는 그 블록을 키워드 줄째 옮긴다. 산출은 그 한 줄만 빼고 맨 키워드 덱의 산출과 같아야 한다
    std = s.replace("*END", shell_block("*ELEMENT_SHELL", range(1001, 1006)) + "*END", 1)
    plain, glued = outputs("n7_sh_plain", std), outputs("n7_sh_glued", suffixed(std, "-"))
    for op in ("squeeze", "tetremesh"):
        rc, data, o, out = glued[op]
        check("N-7 셸 든 표준 덱 %s — rc 0 · 셸 블록이 `*ELEMENT_SHELL-` 줄째" % op, rc == 0 and kwlines(o, "*ELEMENT_SHELL") == ["*ELEMENT_SHELL-"],
              "rc %d %r %s" % (rc, kwlines(o, "*ELEMENT_SHELL"), out[-300:]))
        same_rows("N-7 셸 든 표준 덱 %s" % op, os.path.join(root, "n7_sh_glued", "box.k"), o, "*ELEMENT_SHELL", 5)
        check("N-7 셸 든 표준 덱 %s — 그 키워드 한 줄만 빼면 맨 키워드 덱의 산출과 같다" % op, data is not None and plain[op][1] is not None
              and data.replace(b"*ELEMENT_SHELL-\n", b"*ELEMENT_SHELL\n") == plain[op][1], "rc %d · 맨 키워드 rc %d" % (rc, plain[op][0]))

    # `LONG=Y` 덱 안의 표준 폭 블록 — 선언은 20칸인데 `-` 블록만 8 · 16 칸이다(Vol_I 19342-19348). 메시만 남긴다(다른 카드는 폭이 바뀐다).
    # 번호를 8자리로, 좌표를 음수로 밀어 **칸이 붙게** 한다 — 공백으로 끊어 읽으면 못 읽고, 20칸으로 잘라도 못 읽는다(표준 폭이어야 읽힌다)
    SH = 10000000

    def glued_mesh(text):
        out, kw = ["*KEYWORD LONG=Y"], ""
        for l in text.splitlines():
            if l.startswith("*"):
                kw = l.split()[0].upper()
                if kw in ("*NODE", "*ELEMENT_SOLID"):
                    out.append(kw)
            elif l.startswith("$") or not l.strip():
                continue
            elif kw == "*NODE":
                f = l.split()
                out.append("%8d" % (int(f[0]) + SH) + "".join("%16.9e" % (float(x) - 100.0) for x in f[1:4]))
            elif kw == "*ELEMENT_SOLID":
                f = [int(x) for x in l.split()]
                out.append("%8d%8d" % (f[0] + SH, f[1]) + "".join("%8d" % (x + SH) for x in f[2:]))
        return "\n".join(out) + "\n*END\n"

    mesh = glued_mesh(s)
    check("N-7 LONG=Y 준비 — 표준 폭 절점 줄 56자 · 솔리드 줄 80자가 칸째 붙어 있다", {len(r) for r in mesh.splitlines()[2:200]} == {56}
          and all(len(r.split()) < 4 for r in mesh.splitlines()[2:200]), mesh.splitlines()[2:3])
    lblank = outputs("n7_long_blank", suffixed(mesh, " -"))
    lglued = outputs("n7_long_glued", suffixed(mesh, "-"))
    src = os.path.join(root, "n7_long_glued", "box.k")
    for op, _, _ in OPS:
        rc, data, o, out = lglued[op]
        nd, el = rows(o, "*NODE"), rows(o, "*ELEMENT_SOLID")
        name = "N-7 LONG=Y 덱 %s" % op
        check(name + " — rc 0 · 선언이 *KEYWORD LONG=Y 하나", rc == 0 and kwlines(o, "*KEYWORD") == ["*KEYWORD LONG=Y"],
              "rc %d %r %s" % (rc, kwlines(o, "*KEYWORD"), out[-300:]))
        check(name + " — 절점 줄 80자 · 번호 %d~%d · 솔리드 100 줄 200자" % (SH + 1, SH + 198), bool(nd) and {len(r) for r in nd} == {80}
              and sorted(ids(nd, 20)) == list(range(SH + 1, SH + 199)) and len(el) == 100 and {len(r) for r in el} == {200},
              "절점 %d 줄 %r 솔리드 %d 줄" % (len(nd), nd[:1], len(el)))
        check(name + " — 산출이 `*NODE -`(공백) 덱의 산출과 바이트 같다", data is not None and data == lblank[op][1],
              "rc %d · 공백 꼴 rc %d" % (rc, lblank[op][0]))
        if op == "map":   # 굽은 기준 = 평판 — 좌표가 그대로여야 한다(표준 폭 블록을 20칸으로 자르면 여기서 어긋난다)
            a = {int(r[:8]): [float(r[8 + 16 * i:24 + 16 * i]) for i in range(3)] for r in rows(src, "*NODE")}
            try:
                bad = [r[:20] for r in nd if max(abs(float(r[20 + 20 * i:40 + 20 * i]) - a[int(r[:20])][i]) for i in range(3)) > 1e-6]
            except (ValueError, KeyError) as e:
                bad = ["칸을 못 읽는다 — %s" % e]
            check(name + " — 좌표가 원본과 같다", bool(nd) and not bad, bad[:3])

    print("[M-1] map — 평판의 두께 셸")
    d, s = case_dir(root, "m1", binary)
    hx = hexes(s)
    cut = s.index("\n", s.index("\n" + "".join("%8d" % v for v in hx[50])) + 1) + 1   # 솔리드 51 줄 끝
    tail = s[cut:s.index("*END")]                                                    # 솔리드 52~100 줄
    s2 = s[:cut].rsplit("\n", 2)[0] + "\n" + "*ELEMENT_TSHELL\n" + "".join("%8d" % v for v in hx[50]) + "\n" + tail + "*END\n"
    write(os.path.join(d, "box.k"), s2)
    src = os.path.join(d, "box.k")
    check("M-1 준비 — 원본은 솔리드 50 · 두께 셸 50", len(rows(src, "*ELEMENT_SOLID")) == 50 and len(rows(src, "*ELEMENT_TSHELL")) == 50,
          "%d · %d" % (len(rows(src, "*ELEMENT_SOLID")), len(rows(src, "*ELEMENT_TSHELL"))))
    rc, out = run(binary, d, "map", "box.k", "box.k", "map.k")
    o = os.path.join(d, "map.k")
    got = ids(rows(o, "*ELEMENT_SOLID"), 8)
    check("M-1 map — rc 0 · *ELEMENT_SOLID 에는 솔리드 1~50 만", rc == 0 and sorted(got) == list(range(1, 51)), "rc %d %d 개 %s" % (rc, len(got), out[-300:]))
    same_rows("M-1 map", src, o, "*ELEMENT_TSHELL", 50)

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
