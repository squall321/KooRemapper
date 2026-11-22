#!/usr/bin/env python3
# 덱 폭 선언(*KEYWORD 줄) 읽기 · 좌표 칸 넘침 · 정수 상한을 넘는 번호 · applyfold 경고 숫자를 보는 회귀 시험(미룬 결함 3차 2판)
"""덱 폭 선언 · 칸 넘침 · 정수 상한 (2026-11-22 · 미룬 결함 3차 2판 L-05 · 계획 deferred-defects-round3-1121.plan.md).

왜 이 시험이 있나.

  11-21 검토가 찾은 기존 결함 가운데 네 op(unfold · map · squeeze · tetremesh)이 같이 닿는 것들이다(11-22 설치된 판에서 다시 잼).
    · `*KEYWORD MEMORY=20M JOBID=LONGRUN` 의 `LONGRUN` · `memory=belong` 의 `belong` 을 `LONG=Y` 로 읽었다 — 표준 덱이 20 칸으로 나갔다
    · `*KEYWORD` 가 둘이거나 들여쓴 덱 — 리더(마지막 선언 · 들여쓴 줄은 키워드가 아님)와 쓰기(첫 줄 · 들여써도 셈)가 갈려 op 마다
      산출 폭이 달랐다. 매뉴얼은 `*` 가 1 칸에 있어야 키워드고(Vol_I 17940) `*KEYWORD` 는 첫 카드다(18086)
    · `*KEYWORD_ID I10=Y` — `*KEYWORD` 의 선택지 꼴(Vol_I 201990 `*KEYWORD_{OPTION}`)인데 리더가 폭 선언으로 읽지 않아 I10 줄을 8 칸으로
      읽고 엉뚱한 까닭(「Element 1 has 0 neighbors」 · 「요소 번호가 겹쳐」)으로 멈췄다
    · 좌표 `-1.5e-120` 를 17 자로 써 16 칸을 넘었다(map · tetremesh — 절점 줄 57 자)
    · 정수 상한(2147483647)을 넘는 절점 번호 — 리더가 0 으로 읽어 그 절점을 조용히 버렸다(squeeze · tetremesh 는 rc 0 으로 하나 빠진
      덱 · map · unfold 는 「non-existent node 0」)
    · applyfold 의 「바이트 크기가 달라졌다」 경고가 `%+lld` 에 실수를 넘겨 엉뚱한 숫자를 찍었다

무엇을 보나(`generate box` 상자 — 절점 198 · 솔리드 100).
  A. 부분 문자열 — 두 덱 모두 네 op 이 rc 0 · 산출 절점 줄 56 자(표준) · 산출에 `LONG=Y` 가 없다
  B. 들여쓴 `*KEYWORD I10=Y` · 둘째 `*KEYWORD I10=Y`(첫째는 맨 꼴) — 표준 줄 덱이라 네 op 모두 절점 줄 56 자
  C. `*KEYWORD_ID I10=Y` + ID 카드 + I10 줄 — 네 op 모두 rc 0 · 절점 줄 58 자 · 절점 198
  D. 좌표 `-1.5e-120` — map · tetremesh 의 절점 줄이 모두 56 자 이하 · 되읽은 값이 같다
  E. 절점 번호 2147483648(I10 덱) — 네 op 모두 rc 1 · 까닭에 그 번호와 상한 · 산출 없음. 2147483647 은 네 op 모두 rc 0
  F. applyfold — 자유형식 절점 줄 덱이면 크기가 달라지고, 경고의 숫자가 「Byte size a → b」 의 b − a 와 같다

usage: test_width_decl.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
from ops_help import OPS  # noqa: E402

SPEC = {o["name"]: o for o in OPS}
BOX = SPEC["warpage"]["files"]["box.yaml"]
FAILS, OKS = [], []
SQ = "parts:\n  - pid: 1\n    eps_x: -0.01\n    eps_y: -0.01\n    eps_z: 0.0\nmaterial:\n  E: 210000.0\n  nu: 0.3\n"
TET = "model: box.k\noutput: tet_out.k\nbackend: localimprove\ntarget_pids: [1]\n"
OPS4 = {"unfold": (["unfold", "box.k", "unf.k"], "unf.k"), "map": (["map", "box.k", "box.k", "map.k"], "map.k"),
        "squeeze": (["squeeze", "box.k", "sq.yaml", "sq"], "sq.k"), "tetremesh": (["tetremesh", "tet.yaml"], "tet_out.k")}


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-104s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, args):
    p = subprocess.run([binary] + list(args), cwd=cwd, capture_output=True, timeout=600)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def blocks(text):
    res, cur = [], None
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("*"):
            cur = (line.strip(), [])
            res.append(cur)
        elif cur is not None and line.strip() and not line.startswith("$"):
            cur[1].append(line)
    return res


def node_rows(text):
    return [r for k, rows in blocks(text) if k.split()[0].upper().rstrip("%+-") == "*NODE" for r in rows]


def base_box(binary, top):
    d = os.path.join(top, "gen")
    if not os.path.isdir(d):
        os.makedirs(d)
        open(os.path.join(d, "box.yaml"), "w").write(BOX)
        rc, out = run(binary, d, ["generate", "box", "box.yaml"])
        assert rc == 0, out[-400:]
    return open(os.path.join(d, "box.k"), encoding="utf-8").read()


def i10(text):
    """표준 줄 상자를 I10 줄로 — 절점 번호 10 칸 · 솔리드 줄은 모두 10 칸(머리 줄은 따로 단다)."""
    out, kw = [], ""
    for line in text.split("\n"):
        if line.startswith("*"):
            kw = line.split()[0].upper()
            out.append(line)
            continue
        if line.startswith("$") or not line.strip():
            out.append(line)
            continue
        if kw == "*NODE":
            out.append(line[:8].strip().rjust(10) + line[8:56])
        elif kw.startswith("*ELEMENT_SOLID"):
            out.append("".join(line[c:c + 8].strip().rjust(10) for c in range(0, len(line.rstrip()), 8)))
        else:
            out.append(line)
    return "\n".join(out)


def with_header(text, header_lines):
    """첫 `*KEYWORD` 줄을 갈아 끼운다(여러 줄이면 차례로)."""
    lines = text.split("\n")
    i = next(k for k, l in enumerate(lines) if l.upper().startswith("*KEYWORD"))
    return "\n".join(lines[:i] + header_lines + lines[i + 1:])


def case(top, name, deck):
    d = os.path.join(top, name)
    os.makedirs(d)
    open(os.path.join(d, "box.k"), "w", encoding="utf-8").write(deck)
    open(os.path.join(d, "sq.yaml"), "w").write(SQ)
    open(os.path.join(d, "tet.yaml"), "w").write(TET)
    return d


def four(binary, top, name, deck, ops=OPS4):
    """네 op 을 같은 덱의 사본으로 돌려 {op: (rc, 화면, 산출 글 또는 None)}."""
    got = {}
    for op, (args, outn) in ops.items():
        d = case(top, f"{name}_{op}", deck)
        rc, out = run(sys.argv[1], d, args)
        p = os.path.join(d, outn)
        got[op] = (rc, out, open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None)
    return got


def main():
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_widthdecl_")
    try:
        box = base_box(binary, top)
        print("[A — 폭 선언의 부분 문자열]")
        for tag, head in (("jobid", "*KEYWORD MEMORY=20M JOBID=LONGRUN"), ("memory", "*KEYWORD memory=belong")):
            for op, (rc, out, txt) in four(binary, top, "A_" + tag, with_header(box, [head])).items():
                lens = sorted({len(r) for r in node_rows(txt or "")})
                check(f"A {tag} · {op} — rc 0 · 절점 줄 56 자 · LONG 선언 없음", rc == 0 and lens == [56] and "LONG=Y" not in (txt or ""),
                      (rc, lens, out[-300:]))
        print("[B — 들여쓴 · 둘째 *KEYWORD 는 폭을 정하지 않는다(1 칸 · 첫 카드)]")
        for tag, head in (("indent", [" *KEYWORD I10=Y"]), ("second", ["*KEYWORD", "*KEYWORD I10=Y"])):
            for op, (rc, out, txt) in four(binary, top, "B_" + tag, with_header(box, head)).items():
                lens = sorted({len(r) for r in node_rows(txt or "")})
                check(f"B {tag} · {op} — rc 0 · 절점 줄 56 자", rc == 0 and lens == [56], (rc, lens, out[-300:]))
        print("[C — *KEYWORD_ID I10=Y 는 *KEYWORD 의 선택지 꼴이다]")
        deck = with_header(i10(box), ["*KEYWORD_ID I10=Y", "proj num stage"])
        for op, (rc, out, txt) in four(binary, top, "C", deck).items():
            rows = node_rows(txt or "")
            lens = sorted({len(r) for r in rows})
            check(f"C {op} — rc 0 · 절점 198 · 줄 58 자", rc == 0 and len(rows) == 198 and lens == [58], (rc, len(rows), lens, out[-300:]))
        print("[D — 음수 세 자리 지수 좌표가 16 칸에 든다]")
        lines = box.split("\n")
        k = next(i for i, l in enumerate(lines) if l.startswith("*NODE")) + 1
        while lines[k].startswith("$"):
            k += 1
        lines[k] = lines[k][:8] + "-1.50000000e-120" + lines[k][24:]
        deck = "\n".join(lines)
        sub = {o: OPS4[o] for o in ("map", "tetremesh")}
        for op, (rc, out, txt) in four(binary, top, "D", deck, sub).items():
            rows = node_rows(txt or "")
            first = next((r for r in rows if r[:8].strip() == lines[k][:8].strip()), "")
            try:
                x = float(first[8:24])
            except ValueError:
                x = None
            check(f"D {op} — rc 0 · 절점 줄 모두 56 자 이하 · 되읽은 x 가 같다",
                  rc == 0 and rows and max(len(r) for r in rows) <= 56 and x is not None and abs(x / -1.5e-120 - 1) < 1e-6,
                  (rc, max((len(r) for r in rows), default=0), first[:60], out[-200:]))
        print("[E — 정수 상한을 넘는 절점 번호]")
        ten = with_header(i10(box), ["*KEYWORD I10=Y"])
        nid_old = None
        for want_rc, newid in ((1, 2147483648), (0, 2147483647)):
            ls = ten.split("\n")
            kk = next(i for i, l in enumerate(ls) if l.startswith("*NODE")) + 1
            while ls[kk].startswith("$"):
                kk += 1
            nid_old = ls[kk][:10].strip()
            ls[kk] = str(newid).rjust(10) + ls[kk][10:]
            deck = []
            kw = ""
            for l in ls:
                if l.startswith("*"):
                    kw = l.split()[0].upper()
                if kw.startswith("*ELEMENT_SOLID") and not l.startswith(("*", "$")):
                    cells = [l[c:c + 10] for c in range(0, len(l), 10)]
                    l = "".join((str(newid).rjust(10) if c.strip() == nid_old and i >= 2 else c) for i, c in enumerate(cells))
                deck.append(l)
            for op, (rc, out, txt) in four(binary, top, f"E{newid}", "\n".join(deck)).items():
                if want_rc:
                    check(f"E {newid} · {op} — rc 1 · 까닭에 번호와 상한 · 산출 없음",
                          rc == 1 and str(newid) in out and "2147483647" in out and txt is None, (rc, out[-300:]))
                else:
                    check(f"E {newid} · {op} — rc 0(상한과 같은 번호는 된다)", rc == 0, (rc, out[-300:]))
        print("[F — applyfold 크기 경고의 숫자]")
        spec = SPEC["applyfold"]
        d = os.path.join(top, "F")
        os.makedirs(d)
        for need in spec["needs"]:
            shutil.copytree(os.path.dirname(os.path.join(REPO, need)), os.path.join(d, os.path.dirname(need)), dirs_exist_ok=True)
        for fname, content in spec["files"].items():
            open(os.path.join(d, fname), "w", encoding="utf-8").write(content)
        flat = os.path.join(d, spec["needs"][0])
        t = open(flat, encoding="utf-8").read()
        out_lines, kw = [], ""
        for l in t.split("\n"):
            if l.startswith("*"):
                kw = l.split()[0].upper()
            elif kw == "*NODE" and l.strip() and not l.startswith("$"):
                l = " ".join(l.split()[:4])          # 자유형식 — 고정폭 산출과 크기가 달라진다
            out_lines.append(l)
        open(flat, "w", encoding="utf-8").write("\n".join(out_lines))
        rc, out = run(binary, d, spec["cmds"][-1].split()[1:])
        m = re.search(r"Byte size\D*?(\d+)\s*→\s*(\d+)", out)
        w = re.search(r"바이트 크기가 달라졌다\(([+-]?\d+)\)", out)
        check("F applyfold — 경고 숫자가 b − a 와 같다",
              rc == 0 and m and w and int(w.group(1)) == int(m.group(2)) - int(m.group(1)), (rc, m and m.groups(), w and w.group(1),
                                                                                             out[-400:]))
    finally:
        shutil.rmtree(top, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL — %d 항 실패 / %d" % (len(FAILS), len(FAILS) + len(OKS)))
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
