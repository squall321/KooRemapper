#!/usr/bin/env python3
# contact · boundary · rbe · battery 가 *END 가 둘인 덱에 카드를 한 벌만, 주 덱의 첫 *END 앞에 넣는지 보는 회귀 시험
"""덧붙인 카드는 주 덱의 첫 `*END` 앞에 한 벌만 (2026-11-07 · 셋째 묶음 #3 · #4).

왜 이 시험이 있나.

  LS-DYNA 는 첫 `*END` 에서 읽기를 멈춘다. 쓰기(`ModelAssembler::writeOutput`)의 덧붙임은 첫 `*END` 앞에만 넣게 고쳤지만(1dfa555 ·
  `endInsertsDone`), 쓰기 밖에서 `rawLines_` 를 고치는 넷은 그대로였다.
    · applyContact · applyBoundary · applyRbe — `*END` 를 만날 때마다 넣어 `*END` 가 둘인 덱에 같은 접촉 · SPC · 구속이 **두 벌**
      나갔고(둘째 벌은 해석에 안 든다), `*END` 가 없는 덱에서는 아무 데도 넣지 않아 카드가 **조용히 빠졌다**.
    · applyBattery — `*INCLUDE` 를 **마지막** `*END` 앞에 넣어 `*END` 가 둘인 덱에서는 LS-DYNA 가 그 인클루드를 읽지 않았다.
  이제 넷 다 주 덱의 첫 `*END` 앞에(없으면 끝에) 한 번 넣는다.

무엇을 보나.
  `*END` 가 둘인 덱 — 넣은 카드 수가 `*END` 하나인 덱과 같고, 넣은 카드가 다 첫 `*END` 앞에 있다(contact · boundary · rbe) ·
  배터리 `*INCLUDE` 가 첫 `*END` 앞에 있다 · `*END` 가 없는 덱에도 카드가 들어간다(contact · boundary · rbe).

usage: test_end_insert_once.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS, OKS = [], []

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 4\nny: 2\nnz: 1\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\n"
       "secid: 1\npid: 1\npart_title: PLATE\n")
TAIL = "*COMMENT\nLS-DYNA 는 첫 *END 에서 멈춘다 — 아래는 읽지 않는다\n*END\n"
BAT = ("output: bat\nmodel_type: stacked\ntier: -1\nphase: 1\ngeometry:\n  cell_width: 30\n  cell_height: 30\n"
       "  n_unit_cells: 1\n")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-84s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def write(path, text):
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def lines_of(path):
    return open(path, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(path) else []


def first_end(L):
    return next((i for i, l in enumerate(L) if l.upper().startswith("*END")), len(L))


def kw_rows(L, prefix):
    return [i for i, l in enumerate(L) if l.upper().startswith(prefix)]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="endins_")
    try:
        write(os.path.join(d, "box.yaml"), BOX)
        run(binary, d, "generate", "box", "box.yaml")
        box = open(os.path.join(d, "box.k"), encoding="utf-8").read()
        write(os.path.join(d, "one.k"), box)                                   # *END 하나
        write(os.path.join(d, "two.k"), box + TAIL)                            # *END 둘
        write(os.path.join(d, "none.k"), box.replace("*END\n", ""))            # *END 없음

        cases = (
            ("contact", "*CONTACT", lambda m, o: ("assemble", "base_model: %s\noutput: %s\noperations:\n  - type: contact\n"
                                                  "    contacts:\n      - action: create\n        type: tied\n"
                                                  "        slave:\n          pid: 1\n        master:\n          pid: 1\n" % (m, o[:-2]))),
            ("boundary", "*BOUNDARY_SPC", lambda m, o: ("boundary", "model: %s\noutput: %s\nboundaries:\n  - part: 1\n    dof: xyz\n"
                                                        "    direction: [0, 0, -1]\n    select: direction\n    angle: 45.0\n" % (m, o))),
            ("rbe", "*CONSTRAINED", lambda m, o: ("rbe", "model: %s\noutput: %s\nrbe:\n  - part: 1\n    select: direction\n"
                                                  "    direction: [0, 0, 1]\n    angle: 45.0\n    type: rbe3\n    mode: spider\n" % (m, o))),
        )
        for name, prefix, mk in cases:
            print("[%s]" % name)
            counts = {}
            for deck in ("one", "two", "none"):
                out = "%s_%s_out.k" % (name, deck)
                op, body = mk(deck + ".k", out)
                write(os.path.join(d, "%s_%s.yaml" % (name, deck)), body)
                rc, text = run(binary, d, op, "%s_%s.yaml" % (name, deck))
                L = lines_of(os.path.join(d, out))
                counts[deck] = (rc, len(kw_rows(L, prefix)), all(i < first_end(L) for i in kw_rows(L, prefix)), text)
            rc1, n1, _, t1 = counts["one"]
            rc2, n2, before2, t2 = counts["two"]
            rc0, n0, _, t0 = counts["none"]
            check("%s-1 기준 — *END 하나인 덱에 %s 카드가 들어간다" % (name, prefix), rc1 == 0 and n1 > 0, (rc1, n1, t1[-300:]))
            check("%s-2 ★*END 가 둘인 덱 — %s 카드가 한 벌(%d)이고 다 첫 *END 앞이다" % (name, prefix, n1),
                  rc2 == 0 and n2 == n1 and before2, (rc2, n2, before2, t2[-300:]))
            check("%s-3 ★*END 가 없는 덱에도 %s 카드가 들어간다(예전엔 넣을 자리가 없어 빠졌다)" % (name, prefix),
                  rc0 == 0 and n0 == n1, (rc0, n0, t0[-300:]))

        print("[battery]")
        write(os.path.join(d, "bat.yaml"), BAT)
        for deck in ("one", "two"):
            write(os.path.join(d, "b_%s.yaml" % deck), "base_model: %s.k\noutput: b_%s_out\noperations:\n  - type: battery\n"
                                                      "    config: bat.yaml\n" % (deck, deck))
            rc, text = run(binary, d, "assemble", "b_%s.yaml" % deck)
            L = lines_of(os.path.join(d, "b_%s_out.k" % deck))
            inc = kw_rows(L, "*INCLUDE")
            ok = rc == 0 and len(inc) == 1 and inc[0] < first_end(L)
            if deck == "one":
                check("battery-1 기준 — *END 하나인 덱에 배터리 *INCLUDE 가 첫 *END 앞에 들어간다", ok, (rc, inc, text[-300:]))
            else:
                check("battery-2 ★*END 가 둘인 덱 — 배터리 *INCLUDE 가 첫 *END 앞이다(예전엔 마지막 *END 앞이라 읽히지 않았다)",
                      ok, (rc, inc, first_end(L), text[-300:]))
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
