#!/usr/bin/env python3
# *INITIAL_STRESS_SOLID 카드 1 이 네 쓰기 자리 모두에서 매뉴얼 꼴(I10×8)인지 보는 회귀 시험
"""`*INITIAL_STRESS_SOLID` 카드 1 이 매뉴얼 그대로 **I10×8** 인가 — 쓰는 자리 넷 모두.

왜 이 시험이 있나 (2026-10-16).

  이 카드를 쓰는 자리가 넷(`prestress` 의 DynainWriter · assemble 의 `.dynain` · assemble 의 덱 내장
  `dynain_embed` · `cclip` 의 `stress_output: embed`)이었고 넷 다 `I10 + I8×5` 로 썼다. 매뉴얼은 카드 1 을
  EID NINT NHISV LARGE IVEFLG IALEGP NTHINT NTHHSV 의 **I10×8** 로 둔다(Vol_I `*INITIAL_STRESS_SOLID`).
  지금 값(NINT=1 · 나머지 0)은 10칸 창에 우연히 들어가 맞게 읽혔지만, 다섯째·여섯째 칸(머리 주석은 옛 이름
  `ics`·`ncomp` 였다)이 0 이 아니게 되는 날 IVEFLG 가 틀리게 읽힌다. 지금은 한 곳(`InitialStressCard.h`)에서 쓴다.

무엇을 보나 — 자리마다 산출의 카드 1 줄이 전부
  · 80칸 · 10칸 고정폭으로 읽어 [EID, 1, 0, 0, 0, 0, 0, 0] · 칸마다 숫자가 10칸 경계에서 끝난다
  · 머리 주석이 매뉴얼 이름(`iveflg`·`ialegp`·`nthint`·`nthhsv`)이다
  · 카드 2(응력 6 + eps)는 그대로 10칸 일곱이다

usage: test_initial_stress_card.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\n"
       "mid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")
SQUEEZE = ("base_model: box.k\noutput: box_assembled\n%soperations:\n  - type: squeeze\n    target_pid: 1\n"
           "    eps_x: 0.0\n    eps_y: -0.01\n    eps_z: 0.0\nmaterial:\n  E: 210000.0\n  nu: 0.3\n")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def cards(path):
    """*INITIAL_STRESS_SOLID 블록마다 (머리 주석들, 카드 1 줄들, 카드 2 줄들)."""
    L = open(path, encoding="utf-8", errors="replace").read().splitlines()
    out, cur = [], None
    for l in L:
        if l.startswith("*"):
            cur = {"comments": [], "c1": [], "c2": []} if l.strip().upper() == "*INITIAL_STRESS_SOLID" else None
            if cur is not None:
                out.append(cur)
            continue
        if cur is None or not l.strip():
            continue
        if l.lstrip().startswith("$"):
            cur["comments"].append(l)
            continue
        (cur["c1"] if (len(cur["c1"]) == len(cur["c2"])) else cur["c2"]).append(l)
    return out


def judge(label, path):
    blocks = cards(path)
    if not check("%s — *INITIAL_STRESS_SOLID 가 있다" % label, bool(blocks) and any(b["c1"] for b in blocks), path):
        return
    c1 = [l for b in blocks for l in b["c1"]]
    c2 = [l for b in blocks for l in b["c2"]]
    bad = []
    for l in c1:
        f = [l[i:i + 10] for i in range(0, 80, 10)]
        ok = len(l) == 80 and all(re.fullmatch(r" *-?\d+", x) for x in f)
        vals = [int(x) for x in f] if ok else []
        if not ok or vals[1:] != [1, 0, 0, 0, 0, 0, 0] or vals[0] <= 0:
            bad.append(l)
    check("%s — 카드 1 이 I10×8 [EID 1 0 0 0 0 0 0](%d줄)" % (label, len(c1)), not bad, bad[:2])
    heads = [c for b in blocks for c in b["comments"]]
    check("%s — 머리 주석이 매뉴얼 이름이다" % label,
          any("iveflg" in h and "ialegp" in h and "nthint" in h and "nthhsv" in h for h in heads) and
          not any(" ics " in h + " " or "ncomp" in h for h in heads), heads[:2])
    bad2 = [l for l in c2 if len(l.rstrip()) != 70]
    check("%s — 카드 2 는 10칸 일곱 그대로" % label, c2 and not bad2, bad2[:2])


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="isc_")
    try:
        print("[prestress — DynainWriter]")
        run(binary, d, "generate", "--dim-i", "20", "--dim-j", "5", "arc", "demo")
        rc, out = run(binary, d, "prestress", "--E", "210000", "--nu", "0.3", "demo_flat.k", "demo_bent.k", "demo_pre")
        # prestress 는 dynain 을 접두어 그대로(확장자 없이) 쓴다 — 로그 「Writing dynain file: demo_pre」
        if check("prestress rc 0", rc == 0 and os.path.exists(os.path.join(d, "demo_pre")), out[-300:]):
            judge("prestress", os.path.join(d, "demo_pre"))

        print("[assemble — .dynain]")
        open(os.path.join(d, "box.yaml"), "w").write(BOX)
        run(binary, d, "generate", "box", "box.yaml")
        open(os.path.join(d, "asm.yaml"), "w").write(SQUEEZE % "")
        rc, out = run(binary, d, "assemble", "asm.yaml")
        if check("assemble rc 0", rc == 0 and os.path.exists(os.path.join(d, "box_assembled.dynain")), out[-300:]):
            judge("assemble .dynain", os.path.join(d, "box_assembled.dynain"))

        print("[assemble — 덱 내장(dynain_embed)]")
        open(os.path.join(d, "emb.yaml"), "w").write((SQUEEZE % "dynain_embed: true\n").replace(
            "output: box_assembled", "output: box_embedded"))
        rc, out = run(binary, d, "assemble", "emb.yaml")
        if check("embed rc 0", rc == 0 and os.path.exists(os.path.join(d, "box_embedded.k")), out[-300:]):
            judge("assemble 내장", os.path.join(d, "box_embedded.k"))

        print("[cclip — stress_output: embed]")
        shutil.copy2(os.path.join(REPO, "examples", "cclip", "gen_board.yaml"), d)
        run(binary, d, "generate", "box", "gen_board.yaml")
        y = open(os.path.join(REPO, "examples", "cclip", "cclip.yaml"), encoding="utf-8").read()
        # 예제는 셸 클립이라 *INITIAL_STRESS_SHELL 을 낸다 — 솔리드 초기응력 자리는 `element: solid` 가 탄다
        open(os.path.join(d, "cc.yaml"), "w").write(y.replace("mode: analytic", "mode: analytic\nelement: solid", 1))
        rc, out = run(binary, d, "cclip", "cc.yaml")
        outs = [os.path.join(d, f) for f in os.listdir(d) if f.startswith("clip_board_cclip") and f.endswith((".k", ".dynain"))]
        hit = [p for p in outs if cards(p)]
        if check("cclip rc 0 · 초기응력을 쓴 산출이 있다", rc == 0 and hit, (out[-300:], outs)):
            for p in hit:
                judge("cclip " + os.path.basename(p), p)
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
