#!/usr/bin/env python3
# 주 덱이 `*INCLUDE` 뿐이거나 비었을 때 strain · squeeze(명령줄 꼴)가 빈 산출 대신 rc 1 로 멈추는지 보는 회귀 시험
"""빈 메시를 읽은 strain · squeeze(명령줄 꼴) — rc 0 빈 산출 대신 거절 (2026-11-21 · 미룬 결함 3차 1판 L-03).

왜 이 시험이 있나.

  이 두 명령은 덱을 인자로 바로 받고 `*INCLUDE` 를 따라가지 않는다. 주 덱이 `*KEYWORD` + `*INCLUDE` + `*END` 뿐이면 읽은 메시가
  비는데, 실측(11-21 · 설치된 판)으로 둘 다 rc 0 이었다.
    · strain 은 머리 한 줄뿐인 CSV(72 바이트)를 썼다 — 통계는 전부 0
    · squeeze 는 `Part 1 not found in mesh, skipping` 경고 하나를 찍고 메시 없는 `.k`(180 바이트) · 요소 0 인 `.dynain` 을 썼다
  이웃 unfold · map 은 같은 덱을 `Mesh has no nodes` 로 거절한다. 이제 이 둘도 절점이나 요소(솔리드 · 셸)를 하나도 못 읽으면 rc 1 로 멈추고
  산출을 쓰지 않는다. 주 덱이 `*INCLUDE` 를 싣고 있으면 까닭 글이 그것을 말한다(인클루드를 읽게 넓히지는 않는다 — 펼친 한 파일을 준다).

무엇을 보나(도움말 사례를 판으로 쓴다).
  A. 안 쪼갠 덱 — rc 0 · 산출이 있다(기준)
  B. 주 덱을 `*INCLUDE` 로 쪼갠다 — rc 1 · 산출 없음 · `[ERROR]` 줄이 그 덱 이름과 `*INCLUDE` 를 말한다
  C. 인클루드도 메시도 없는 덱 — rc 1 · 산출 없음 · 까닭 글이 `*INCLUDE` 를 지어내지 않는다(`*INCLUDE_PATH` 만 있는 덱도)
  D. 절점만 있는 덱(요소 0) — rc 1 · 산출 없음 · 까닭 글이 「요소」 를 말한다(절점이 없으면 「절점」)
  E. 이미 있던 산출 파일은 거절 때 건드리지 않는다
  F. 셸뿐인 덱(솔리드 0)은 squeeze 가 예전처럼 rc 0 으로 돈다 — 리더는 셸도 요소로 센다. 거절을 솔리드에만 걸면 여기가 빨갛다

usage: test_include_only_main.py <KooRemapper 바이너리>
"""
import os
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
FAILS, OKS = [], []
SENTINEL = b"old output - must stay\n"
SHELL_DECK = b"""*KEYWORD
*NODE
       1             0.0             0.0             0.0
       2             1.0             0.0             0.0
       3             1.0             1.0             0.0
       4             0.0             1.0             0.0
*ELEMENT_SHELL
       1       1       1       2       3       4
*PART
shell
         1         1         1
*SECTION_SHELL
         1         2
       0.1       0.1       0.1       0.1
*MAT_ELASTIC
         1    7.8e-9  210000.0       0.3
*END
"""


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-104s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def call(binary, cwd, cmd):
    p = subprocess.run([binary] + cmd.split()[1:], cwd=cwd, capture_output=True, timeout=600)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def stage(binary, top, op):
    """도움말 사례를 차리고 제 명령 앞까지 돌린 폴더와 제 명령."""
    spec = SPEC[op]
    base = os.path.join(top, op + "_base")
    os.makedirs(base)
    for fname, content in spec["files"].items():
        with open(os.path.join(base, fname), "w", encoding="utf-8") as f:
            f.write(content)
    for c in spec["cmds"][:-1]:
        rc, text = call(binary, base, c)
        if rc != 0:
            raise RuntimeError("준비 명령 실패 %s: %s" % (c, text[-400:]))
    return base, spec["cmds"][-1]


def read(path):
    with open(path, "rb") as f:
        return f.read()


def write(path, data):
    with open(path, "wb") as f:
        f.write(data)


def split(d, deck):
    """덱을 `*KEYWORD` + `*INCLUDE` + `*END` 주 덱과 본문 인클루드로 쪼갠다."""
    child = "child_" + deck
    write(os.path.join(d, child), read(os.path.join(d, deck)))
    write(os.path.join(d, deck), ("*KEYWORD\n*INCLUDE\n%s\n*END\n" % child).encode())


def nodes_only(d, deck):
    """솔리드 요소 블록을 뺀다 — 절점은 남는다."""
    out, skip = [], False
    for line in read(os.path.join(d, deck)).split(b"\n"):
        if line.startswith(b"*"):
            skip = line.upper().startswith(b"*ELEMENT_SOLID")
        if not skip:
            out.append(line)
    write(os.path.join(d, deck), b"\n".join(out))


def errors(text):
    return [l for l in text.splitlines() if l.startswith("[ERROR]")]


def run_case(binary, top, base, cmd, tag, mutate, outputs, sentinel=False):
    """base 를 새 폴더로 복사하고 mutate 로 덱을 바꾼 뒤 제 명령을 돌린다 → (rc, 화면, 생긴 · 바뀐 산출 이름)."""
    d = os.path.join(top, tag)
    shutil.copytree(base, d)
    mutate(d)
    if sentinel:
        for o in outputs:
            write(os.path.join(d, o), SENTINEL)
    rc, text = call(binary, d, cmd)
    if sentinel:
        touched = [o for o in outputs if read(os.path.join(d, o)) != SENTINEL]
    else:
        touched = [o for o in outputs if os.path.exists(os.path.join(d, o))]
    return rc, text, touched


def refused(op, label, res, deck, include, word="절점을"):
    """거절 한 건 — rc 1 · 산출 없음 · 까닭 글이 덱 이름과 못 읽은 것(word)을 말하고 `*INCLUDE` 는 있을 때만 말한다."""
    rc, text, touched = res
    errs = errors(text)
    line = next((l for l in errs if deck in l), "")
    says = "*INCLUDE" in line
    check("★%s · %s → rc 1 · 산출 없음 · 까닭 글이 %s · 「%s」 을 말하고 `*INCLUDE` 는 %s"
          % (op, label, deck, word, "말한다" if include else "말하지 않는다"),
          rc == 1 and not touched and bool(line) and word in line and says == include, (rc, touched, errs or text[-300:]))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_incl_only_")
    try:
        # ---- strain <기준 메시> <변형 메시> <산출 CSV> ----
        print("[strain]")
        base, cmd = stage(binary, top, "strain")
        ref, deform, outs = "demo_flat.k", "demo_bent.k", ["strain.csv"]
        rc, text, touched = run_case(binary, top, base, cmd, "s_a", lambda d: None, outs)
        rows = read(os.path.join(top, "s_a", "strain.csv")).count(b"\n") if touched else 0
        check("strain · A 안 쪼갠 덱 → rc 0 · CSV 에 요소 줄이 있다", rc == 0 and rows > 1, (rc, rows, text[-300:]))
        empty = b"*KEYWORD\n*END\n"
        path_only = b"*KEYWORD\n*INCLUDE_PATH\nsub\n*END\n"
        for label, mutate, deck, include, word in (
                ("B 두 덱 다 쪼갬", lambda d: (split(d, ref), split(d, deform)), ref, True, "절점을"),
                ("B 기준 메시만 쪼갬", lambda d: split(d, ref), ref, True, "절점을"),
                ("B 변형 메시만 쪼갬", lambda d: split(d, deform), deform, True, "절점을"),
                ("C 기준 메시가 빈 덱", lambda d: write(os.path.join(d, ref), empty), ref, False, "절점을"),
                ("C 변형 메시가 `*INCLUDE_PATH` 뿐", lambda d: write(os.path.join(d, deform), path_only), deform, False, "절점을"),
                ("D 기준 메시가 절점뿐", lambda d: nodes_only(d, ref), ref, False, "요소(솔리드 · 셸)를")):
            tag = "s_%d" % len(OKS + FAILS)
            refused("strain", label, run_case(binary, top, base, cmd, tag, mutate, outs), deck, include, word)
        refused("strain", "E 쪼갠 덱 · 이미 있던 CSV",
                run_case(binary, top, base, cmd, "s_e", lambda d: split(d, ref), outs, sentinel=True), ref, True)

        # ---- squeeze <메시> <설정> <산출 접두어> ----
        print("[squeeze]")
        base, cmd = stage(binary, top, "squeeze")
        deck, outs = "box.k", ["box_sq.k", "box_sq.dynain"]
        rc, text, touched = run_case(binary, top, base, cmd, "q_a", lambda d: None, outs)
        check("squeeze · A 안 쪼갠 덱 → rc 0 · `.k` · `.dynain` 을 쓴다", rc == 0 and touched == outs, (rc, touched, text[-300:]))
        for label, mutate, include, word in (
                ("B 주 덱을 쪼갬", lambda d: split(d, deck), True, "절점을"),
                ("C 빈 덱", lambda d: write(os.path.join(d, deck), empty), False, "절점을"),
                ("C `*INCLUDE_PATH` 뿐", lambda d: write(os.path.join(d, deck), path_only), False, "절점을"),
                ("D 절점뿐", lambda d: nodes_only(d, deck), False, "요소(솔리드 · 셸)를")):
            tag = "q_%d" % len(OKS + FAILS)
            refused("squeeze", label, run_case(binary, top, base, cmd, tag, mutate, outs), deck, include, word)
        refused("squeeze", "E 쪼갠 덱 · 이미 있던 산출",
                run_case(binary, top, base, cmd, "q_e", lambda d: split(d, deck), outs, sentinel=True), deck, True)
        rc, text, touched = run_case(binary, top, base, cmd, "q_f", lambda d: write(os.path.join(d, deck), SHELL_DECK), outs)
        check("squeeze · F 셸뿐인 덱(솔리드 0) → 예전처럼 rc 0 · `.k` · `.dynain` 을 쓴다", rc == 0 and touched == outs,
              (rc, touched, text[-300:]))
    finally:
        shutil.rmtree(top, ignore_errors=True)

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
