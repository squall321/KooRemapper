#!/usr/bin/env python3
"""`disconnect mefem` 이 새 `*SET_NODE_LIST` 번호를 **기존 SET_NODE 위로** 내는가.

왜 이 시험이 있나 (2026-10-15, 장부 P1-3 「disconnect mefem 이 SET 네임스페이스를 전혀 안 본다」).

  mefem 은 세트 번호를 `maxPartId + 1000` 부터 냈다 — **기존 `*SET_NODE` 를 보지도 않았다.**
  재현 — `examples/disconnect/two_hex_2part.k`(PID 최대 2)에 `*SET_NODE_LIST 1002` 를 넣고 돌리면
  새 세트를 **1002** 부터 냈고 `info` 가 「SID 1002 가 line 44 과 겹칩니다」. 같은 종류의 SID 가 둘이면
  LS-DYNA 가 키워드 단계에서 멈춘다.

  고친 규칙 — 이 op 의 관례(PID 최대 + 1000)는 **바닥**으로 남기고, 덱과 인클루드의 기존 SET_NODE
  위로 올린다. 그래서 안 겹치는 덱에서는 번호가 **한 글자도 안 바뀐다**(예제 4장 옛 대 새 바이트 동일).

무엇을 보나.
  A 예제 그대로 — 새 세트가 1002 부터(오늘과 같은 번호)
  B 덱에 SET_NODE 1002 가 있으면 그 위로(1003 부터) · 펼친 덱에 겹침 0
  C 인클루드에 SET_NODE 1500 이 있으면 그 위로(1501 부터)
  D ★**다른 종류**(`*SET_PART 5000`)의 큰 번호에는 끌려가지 않는다 — 1002 부터 그대로.
    매뉴얼상 SET 네임스페이스는 종류별이다. 한 통으로 세면 번호가 이유 없이 움직인다
  E 못 읽은 인클루드는 경고한다(rc 0)

usage: test_disconnect_mefem_set_ids.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples", "disconnect")
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def stage(extra_lines=None, include=None):
    d = tempfile.mkdtemp(prefix="dmsi_")
    shutil.copy2(os.path.join(EX, "disconnect_mefem.yaml"), d)
    L = open(os.path.join(EX, "two_hex_2part.k"), encoding="utf-8").read().splitlines()
    k = next(i for i, l in enumerate(L) if l.strip().upper() == "*END")
    add = list(extra_lines or [])
    if include:
        name, body = include
        add += ["*INCLUDE", name]
        if body is not None:
            open(os.path.join(d, name), "w", encoding="utf-8").write(body)
    L[k:k] = add
    open(os.path.join(d, "two_hex_2part.k"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    return d


def run(binary, d):
    r = subprocess.run([binary, "assemble", "disconnect_mefem.yaml"], cwd=d, capture_output=True,
                       text=True, timeout=120, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def new_node_sets(d, preexisting):
    """새로 낸 SET_NODE 번호들. ⚠ **등장 횟수로** 센다 — 원래 있던 번호를 또 내면 그것도 새 것이다.
    (처음 판은 원래 있던 번호를 그냥 걸러서, 옛 바이너리가 1002 를 또 낸 것이 사라져 「1003 부터」가
    통과했다. 겹침 갈래가 대신 잡았지만 이 갈래는 그 자체로 물어야 한다.)"""
    L = open(os.path.join(d, "disconnect_mefem_result.k"), encoding="utf-8").read().splitlines()
    seen = {}
    for i, l in enumerate(L):
        if l.strip().upper().startswith("*SET_NODE"):
            j = i + 1
            while L[j].lstrip().startswith("$"):
                j += 1
            sid = int(L[j].split()[0])
            seen[sid] = seen.get(sid, 0) + 1
    out = []
    for sid, n in seen.items():
        out += [sid] * (n - (1 if sid in preexisting else 0))
    return sorted(out)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])

    cases = [
        ("A 예제 그대로", None, None, set(), 1002),
        ("B 덱에 SET_NODE 1002", ["*SET_NODE_LIST", "      1002", "         1"], None, {1002}, 1003),
        ("C 인클루드에 SET_NODE 1500", None,
         ("inc.k", "*KEYWORD\n*SET_NODE_LIST\n      1500\n         1\n*END\n"), {1500}, 1501),
        ("D 다른 종류 SET_PART 5000", ["*SET_PART_LIST", "      5000", "         1"], None, set(), 1002),
    ]
    for label, extra, inc, pre, want_first in cases:
        print("[%s]" % label)
        d = stage(extra, inc)
        try:
            rc, out = run(binary, d)
            if not check("%s — rc 0" % label, rc == 0, out[-300:]):
                continue
            sets = new_node_sets(d, pre)
            check("%s — 새 세트가 %d 부터" % (label, want_first),
                  bool(sets) and sets[0] == want_first and sets == list(range(want_first, want_first + len(sets))),
                  sets)
            if label.startswith("B"):
                r2 = subprocess.run([binary, "info", os.path.join(d, "disconnect_mefem_result.k")],
                                    capture_output=True, text=True, timeout=120, encoding="utf-8",
                                    errors="replace")
                check("B 겹침 보고가 없다", "겹칩니다" not in (r2.stdout + r2.stderr),
                      [l for l in (r2.stdout + r2.stderr).splitlines() if "겹칩" in l][:2])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    print("[E 못 읽은 인클루드]")
    d = stage(None, ("gone.k", None))
    try:
        rc, out = run(binary, d)
        check("E rc 0", rc == 0, out[-300:])
        check("E 못 본 인클루드를 경고한다", "못 본 인클루드" in out and "gone.k" in out, out[-300:])
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
