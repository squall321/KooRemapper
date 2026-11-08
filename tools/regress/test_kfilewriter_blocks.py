#!/usr/bin/env python3
# 메시 쓰기(KFileWriter)가 첫 *END 앞만 보는지 보는 회귀 시험(map)
"""메시 쓰기의 블록 (2026-11-08 여섯째 검토 — 물성을 바꾸던 기존 결함).

왜 이 시험이 있나.

  P3 · 원본을 따라 쓰는 길(`writeFileWithSource` — map · shellmap · squeeze)이 `*KEYWORD` 찾기 · 칸 폭 · 셸 번호 미리 훑기를 덱 끝까지
       했다. 첫 `*END` 뒤의(LS-DYNA 가 읽지 않는) 셸 블록에 산 솔리드와 같은 번호가 있으면 그 솔리드를 쓰지 않았고(map rc 0), 첫 `*END`
       뒤의 `*KEYWORD I10=Y` 가 앞 덱의 칸 폭을 바꿨다. 이제 그 걸음들은 첫 `*END` 앞만 보고 뒤는 그대로 베낀다.

무엇을 보나.
  A-1 map — 첫 `*END` 뒤 죽은 셸(번호 = 산 솔리드)이 있어도 그 솔리드를 쓰고 · 죽은 셸 줄은 첫 `*END` 뒤에 그대로
  A-2 map — `*KEYWORD` 없는 덱의 첫 `*END` 뒤에 `*KEYWORD I10=Y` 가 있어도 산출은 표준 폭 · 맨 앞에 `*KEYWORD`

usage: test_kfilewriter_blocks.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-500:]))
    print("  %-90s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def lines_of(path):
    return open(path, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(path) else []


def blocks(L, stop_at_end=True):
    """키워드 → 데이터 줄들(첫 *END 에서 멈춘다)."""
    out, kw = {}, None
    for l in L:
        if l.startswith("*"):
            kw = l.split()[0].upper()
            if stop_at_end and kw == "*END":
                break
            out.setdefault(kw, [])
            continue
        if kw and l.strip() and not l.startswith("$"):
            out[kw].append(l)
    return out


def eid_of(l, w=8):
    return int(l[:w]) if l[:w].strip().lstrip("-").isdigit() else None


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="kfwblk_")
    try:
        run(binary, d, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo")
        flat = open(os.path.join(d, "demo_flat.k"), encoding="utf-8").read()
        print("[A map — 첫 *END 앞만 본다(P3)]")
        assert flat.rstrip().endswith("*END")
        dead = "*ELEMENT_SHELL\n%8d%8d%8d%8d%8d%8d\n*END\n" % (5, 9, 1, 2, 3, 4)
        write(os.path.join(d, "a1.k"), flat + dead)
        rc, out = run(binary, d, "map", "demo_bent.k", "a1.k", "a1_out.k")
        L = lines_of(os.path.join(d, "a1_out.k"))
        bl = blocks(L)
        solids = {eid_of(l) for l in bl.get("*ELEMENT_SOLID", [])}
        ends = [i for i, l in enumerate(L) if l.upper().startswith("*END")]
        tail = L[ends[0] + 1:] if ends else []
        check("A-1 ★첫 *END 뒤의 죽은 셸(EID 5)이 있어도 산 솔리드 5 를 쓴다 · 죽은 셸 줄은 첫 *END 뒤에 그대로",
              rc == 0 and 5 in solids and "%8d%8d%8d%8d%8d%8d" % (5, 9, 1, 2, 3, 4) in tail, (rc, 5 in solids, tail[:4], out[-300:]))
        body = flat.split("\n", 1)[1] if flat.startswith("*KEYWORD") else flat
        write(os.path.join(d, "a2.k"), body + "*KEYWORD I10=Y\n*END\n")
        rc, out = run(binary, d, "map", "demo_bent.k", "a2.k", "a2_out.k")
        L = lines_of(os.path.join(d, "a2_out.k"))
        bl = blocks(L)
        node1 = bl.get("*NODE", [""])[0]
        check("A-2 ★첫 *END 뒤의 *KEYWORD I10=Y 가 앞 덱의 칸 폭을 바꾸지 않는다(표준 8칸) · 맨 앞에 *KEYWORD",
              rc == 0 and L and L[0].startswith("*KEYWORD") and node1[:8].strip().isdigit(), (rc, L[:2], node1, out[-300:]))

    finally:
        shutil.rmtree(d, ignore_errors=True)

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
