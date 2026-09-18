# 단독 merge 명령도 assemble 과 같은 코드로 죽은 PID 참조를 옮기는지 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_merge_pidref_standalone.py <KooRemapper 바이너리>

배경
  - `KooRemapper merge cfg.yaml` 은 ModelAssembler 를 지나지 않고 자기 구현으로 덱을 쓴다.
    그래서 합쳐진 원 파트를 가리키던 세트·감쇠·이력·열팽창 카드가 빈 파트를 가리킨 채 남았다
    (assemble 안의 merge 는 이미 처리하고 있었다 — 같은 입력이 경로에 따라 다른 덱을 냈다).
  - 이제 두 경로가 ModelAssembler::processDeadReferences 한 곳을 같이 쓴다.
  - merge 는 새 PID 가 하나뿐이라 스칼라 PID 칸(*DAMPING_PART_MASS, *DATABASE_HISTORY_PART,
    *MAT_ADD_THERMAL_EXPANSION …)도 옮길 수 있다. restack 이 이 칸들을 '직접 고치세요' 로
    남기는 이유(칸 하나에 층 N 개를 못 담는다)가 merge 에는 없다.

임시 산출물은 /tmp 가 아니라 저장소 build/scratch/regress 아래에 만든다.
"""
import os
import re
import subprocess
import sys

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print("  OK   " + name)
    else:
        FAILS.append(name)
        print("  FAIL " + name)
        if detail:
            print("       " + str(detail)[:400])


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def field(line, idx):
    """고정폭 10칸에서 idx 번째 칸의 정수"""
    seg = line[idx * 10:(idx + 1) * 10].strip()
    try:
        return int(seg)
    except ValueError:
        return None


def card_after(deck, keyword, nth=0):
    """키워드 다음 nth 번째 데이터 줄('$'·'*'·빈 줄 아님).
    *SET_PART_LIST 는 0=SID, 1=구성원 줄이고, _TITLE 카드는 0=제목, 1=카드 1 이다."""
    lines = deck.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().upper().startswith(keyword):
            seen = 0
            for j in range(i + 1, len(lines)):
                t = lines[j]
                if not t.strip() or t.lstrip().startswith("$"):
                    continue
                if t.lstrip().startswith("*"):
                    break
                if seen == nth:
                    return t
                seen += 1
    return None


REFS = """*SET_PART_LIST
$#     sid
        50
$#   pid1      pid2
         1         2
*DAMPING_PART_MASS
$#     pid      lcid
         1         0
*DATABASE_HISTORY_PART
$#     pid
         2
"""


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = os.path.join(repo, "examples", "merge", "three_layer.k")
    if not os.path.exists(src):
        print("SKIP: examples/merge/three_layer.k 없음")
        return 0
    d = os.path.join(repo, "build", "scratch", "regress", "merge_pidref")
    os.makedirs(d, exist_ok=True)

    base = open(src, encoding="utf-8", errors="replace").read()
    open(os.path.join(d, "base.k"), "w").write(base.replace("*END", REFS + "*END"))

    open(os.path.join(d, "sa.yaml"), "w").write(
        'model: base.k\noutput: out_sa.k\ndirection: z\nmethod: vrh\n'
        'merge:\n  - pids: [1, 2]\n    name: "Homog"\n')
    rc, out = run(binary, d, "merge", "sa.yaml")
    deck = open(os.path.join(d, "out_sa.k"), encoding="utf-8", errors="replace").read() \
        if os.path.exists(os.path.join(d, "out_sa.k")) else ""

    print("[단독 merge 도 죽은 PID 참조를 옮긴다]")
    check("rc=0 (옮길 수 있는 것을 다 옮겼다)", rc == 0, out[-400:])
    check("콘솔에 보고가 나온다", "빈 파트가 됐습니다" in out, out[-300:])
    check("덱 머리에 $ KOOREMAPPER-PIDREF 블록이 있다", "$ KOOREMAPPER-PIDREF" in deck)

    merged = None
    m = re.search(r"\(새 층 PID: (\d+)\)", out)
    if m:
        merged = int(m.group(1))
    check("합친 PID 를 보고에서 읽을 수 있다", merged is not None, out[-300:])

    if merged:
        setline = card_after(deck, "*SET_PART_LIST", nth=1)   # 0 은 SID 줄
        check("*SET_PART_LIST 구성원이 합친 PID 로 바뀐다",
              setline is not None and field(setline, 0) == merged, repr(setline))
        damp = card_after(deck, "*DAMPING_PART_MASS")
        check("*DAMPING_PART_MASS 의 PID 칸이 합친 PID 로 바뀐다",
              damp is not None and field(damp, 0) == merged, repr(damp))
        hist = card_after(deck, "*DATABASE_HISTORY_PART")
        check("*DATABASE_HISTORY_PART 의 PID 칸이 합친 PID 로 바뀐다",
              hist is not None and field(hist, 0) == merged, repr(hist))
        thex = card_after(deck, "*MAT_ADD_THERMAL_EXPANSION", nth=1)   # 0 은 제목 줄
        if thex is not None:
            check("*MAT_ADD_THERMAL_EXPANSION 의 PID 칸도 옮긴다",
                  field(thex, 0) == merged, repr(thex))

    print("[assemble 과 같은 결과를 낸다]")
    open(os.path.join(d, "asm.yaml"), "w").write(
        "base_model: base.k\noutput: out_asm\noperations:\n  - type: merge\n"
        "    pids: [1, 2]\n    name: Homog\n    direction: 2\n")
    rc2, out2 = run(binary, d, "assemble", "asm.yaml")
    deck2 = open(os.path.join(d, "out_asm.k"), encoding="utf-8", errors="replace").read() \
        if os.path.exists(os.path.join(d, "out_asm.k")) else ""
    check("assemble 도 rc=0", rc2 == 0, out2[-300:])
    for kw in ("*SET_PART_LIST", "*DAMPING_PART_MASS", "*DATABASE_HISTORY_PART"):
        nth = 1 if kw == "*SET_PART_LIST" else 0
        a, b = card_after(deck, kw, nth), card_after(deck2, kw, nth)
        check("두 경로의 %s 데이터 줄이 같다" % kw, a is not None and a == b, "%r vs %r" % (a, b))

    print("[pid_refs 는 두 경로에서 같은 규칙이다]")
    open(os.path.join(d, "bad.yaml"), "w").write(
        'model: base.k\noutput: out_bad.k\ndirection: z\nmethod: vrh\npid_refs: nonsense\n'
        'merge:\n  - pids: [1, 2]\n    name: "Homog"\n')
    rc3, out3 = run(binary, d, "merge", "bad.yaml")
    check("모르는 pid_refs 값은 rc=1 로 거절한다", rc3 == 1 and "pid_refs" in out3, out3[-300:])

    print("[옮기지 못한 자리가 남으면 rc=1, warn 이면 rc=0]")
    # 두 칸이 모두 이번 merge 로 사라지는 *CONSTRAINED_RIGID_BODIES — 합치면 자기 자신을 가리킨다
    crb = "*CONSTRAINED_RIGID_BODIES\n$#    pidl      pidc\n         1         2\n"
    open(os.path.join(d, "base2.k"), "w").write(base.replace("*END", crb + "*END"))
    open(os.path.join(d, "s2.yaml"), "w").write(
        'model: base2.k\noutput: out_s2.k\ndirection: z\nmethod: vrh\n'
        'merge:\n  - pids: [1, 2]\n    name: "Homog"\n')
    rc4, out4 = run(binary, d, "merge", "s2.yaml")
    check("못 옮긴 자리가 남으면 rc=1", rc4 == 1, out4[-400:])
    check("덱은 그래도 쓴다", os.path.exists(os.path.join(d, "out_s2.k")))
    check("왜 못 옮겼는지 적는다", "자기 자신" in out4 or "left" in out4, out4[-400:])
    open(os.path.join(d, "s3.yaml"), "w").write(
        'model: base2.k\noutput: out_s3.k\ndirection: z\nmethod: vrh\npid_refs: warn\n'
        'merge:\n  - pids: [1, 2]\n    name: "Homog"\n')
    rc5, out5 = run(binary, d, "merge", "s3.yaml")
    check("pid_refs: warn 이면 같은 보고를 하고 rc=0", rc5 == 0, out5[-300:])

    print("FAIL %d" % len(FAILS) if FAILS else "ALL PASS")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
