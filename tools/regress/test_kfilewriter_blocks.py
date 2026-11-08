#!/usr/bin/env python3
# 메시 쓰기(KFileWriter)가 첫 *END 앞만 보고 셸 · 두께 셸을 제 키워드로 쓰는지 보는 회귀 시험(map · tetremesh · unfold)
"""메시 쓰기의 블록 (2026-11-08 여섯째 검토 — 물성을 바꾸던 기존 결함 둘).

왜 이 시험이 있나.

  P3 · 원본을 따라 쓰는 길(`writeFileWithSource` — map · shellmap · squeeze)이 `*KEYWORD` 찾기 · 칸 폭 · 셸 번호 미리 훑기를 덱 끝까지
       했다. 첫 `*END` 뒤의(LS-DYNA 가 읽지 않는) 셸 블록에 산 솔리드와 같은 번호가 있으면 그 솔리드를 쓰지 않았고(map rc 0), 첫 `*END`
       뒤의 `*KEYWORD I10=Y` 가 앞 덱의 칸 폭을 바꿨다. 이제 그 걸음들은 첫 `*END` 앞만 보고 뒤는 그대로 베낀다.
  P4 · 원본 없이 덱을 지어내는 길(`writeFile` — tetremesh · unfold)이 메시의 요소를 다 `*ELEMENT_SOLID` 로 썼다. 리더는 셸을 n5-n8 =
       n1-n4 인 QUAD4 로, 두께 셸을 육면체 칸으로 담으므로 셸은 부피 0 인 육면체로, 두께 셸은 솔리드로 나갔다(rc 0). 이제 셸은
       `*ELEMENT_SHELL`(EID PID N1-N4), 두께 셸(리더가 적은 `Mesh::thickShellIds`)은 `*ELEMENT_TSHELL` 로 쓴다.

무엇을 보나.
  A-1 map — 첫 `*END` 뒤 죽은 셸(번호 = 산 솔리드)이 있어도 그 솔리드를 쓰고 · 죽은 셸 줄은 첫 `*END` 뒤에 그대로
  A-2 map — `*KEYWORD` 없는 덱의 첫 `*END` 뒤에 `*KEYWORD I10=Y` 가 있어도 산출은 표준 폭 · 맨 앞에 `*KEYWORD`
  B-1 · B-2 tetremesh — 셸은 `*ELEMENT_SHELL` 의 네 절점, 두께 셸은 `*ELEMENT_TSHELL` 의 여덟 절점 · 둘 다 `*ELEMENT_SOLID` 에 없다
  B-3 unfold — 굽힌 덱의 두께 셸 칸은 펼친 덱에서도 `*ELEMENT_TSHELL`

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

        print("[B 원본 없는 쓰기 — 셸 · 두께 셸은 제 키워드로(P4)]")
        tet = open(os.path.join(d, "demo_flat_tet.k"), encoding="utf-8").read().split("\n")
        nodes = []
        on = False
        for l in tet:
            if l.startswith("*"):
                on = l.startswith("*NODE")
                continue
            if on and l.strip() and not l.startswith("$"):
                nodes.append(int(l[:8]))
            if len(nodes) >= 8:
                break
        extra = ["*ELEMENT_SHELL", "%8d%8d" % (900001, 2) + "".join("%8d" % n for n in nodes[:4]),
                 "*ELEMENT_TSHELL", "%8d%8d" % (900002, 3) + "".join("%8d" % n for n in nodes[:8]),
                 "*PART", "shell", "%10d%10d%10d" % (2, 2, 1), "*PART", "tshell", "%10d%10d%10d" % (3, 3, 1),
                 "*SECTION_SHELL", "%10d%10d" % (2, 2), "%10s" % "1.0", "*SECTION_TSHELL", "%10d%10d" % (3, 1)]
        i = tet.index("*END")
        tet[i:i] = extra
        write(os.path.join(d, "t.k"), "\n".join(tet))
        write(os.path.join(d, "t.yaml"), "model: t.k\noutput: t_out.k\nbackend: localimprove\ntarget_pids: [1]\n"
                                         "quality:\n  min_jacobian: 0.2\n  max_aspect_ratio: 8.0\n")
        rc, out = run(binary, d, "tetremesh", "t.yaml")
        bl = blocks(lines_of(os.path.join(d, "t_out.k")))
        solid_ids = {eid_of(l) for l in bl.get("*ELEMENT_SOLID", [])}
        sh = [l for l in bl.get("*ELEMENT_SHELL", []) if eid_of(l) == 900001]
        ts = [l for l in bl.get("*ELEMENT_TSHELL", []) if eid_of(l) == 900002]
        check("B-1 ★tetremesh — 셸 900001 은 *ELEMENT_SHELL(EID PID N1-N4) · *ELEMENT_SOLID 에 없다",
              rc == 0 and len(sh) == 1 and sh[0] == "%8d%8d" % (900001, 2) + "".join("%8d" % n for n in nodes[:4]) and 900001 not in solid_ids,
              (rc, sh, 900001 in solid_ids, out[-300:]))
        check("B-2 ★tetremesh — 두께 셸 900002 는 *ELEMENT_TSHELL(EID PID N1-N8) · *ELEMENT_SOLID 에 없다",
              rc == 0 and len(ts) == 1 and ts[0] == "%8d%8d" % (900002, 3) + "".join("%8d" % n for n in nodes[:8]) and 900002 not in solid_ids,
              (rc, ts, 900002 in solid_ids, out[-300:]))
        bent = open(os.path.join(d, "demo_bent.k"), encoding="utf-8").read().split("\n")
        ie = bent.index("*END")
        last = bent[ie - 1]
        bent = bent[:ie - 1] + ["*ELEMENT_TSHELL", last] + bent[ie:]
        write(os.path.join(d, "bt.k"), "\n".join(bent))
        rc, out = run(binary, d, "unfold", "bt.k", "bt_out.k")
        bl = blocks(lines_of(os.path.join(d, "bt_out.k")))
        e = eid_of(last)
        check("B-3 ★unfold — 굽힌 덱의 두께 셸 칸(EID %d)은 펼친 덱에서도 *ELEMENT_TSHELL" % e,
              rc == 0 and any(eid_of(l) == e for l in bl.get("*ELEMENT_TSHELL", [])) and
              not any(eid_of(l) == e for l in bl.get("*ELEMENT_SOLID", [])), (rc, list(bl), out[-300:]))
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
