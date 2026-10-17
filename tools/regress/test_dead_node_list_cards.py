#!/usr/bin/env python3
# restack 이 지운 절점을 치울 때 목록 카드를 정본 표로 가르는지 — 세트 ID 를 절점으로 읽거나 맨 *SET_NODE 를 빼지 않는다
"""**지운 절점 정리가 목록 카드를 정본 표로 가르나** (2026-10-17).

왜 이 시험이 있나.

  restack 은 중간면 절점을 지우고, 그 절점을 가리키던 카드를 세 장치가 다룬다 — 옮기기(`migrateDeadNodeSets`) ·
  치우기(`cleanupDeadNodeRefs`) · 남은 것 보고(`scanDeadReferences`). 셋 다 **세트 분류와 칸 범위를 따로** 들고 있었고,
  찾는 쪽 정본(`noderefs::find`)과 달랐다. 실측으로 두 결함이 났다.

    · `*SET_NODE_INTERSECT`·`*SET_SEGMENT_INTERSECT` 의 멤버는 **세트 ID** 다. 치우는 장치는 `_ADD` 만 건너뛰어
      세트 ID 70·71 을 지운 절점 70·71 로 읽고 교집합 세트를 **비웠다**(「구성원이 하나도 남지 않았습니다」).
    · 매뉴얼상 같은 목록 카드인 맨 `*SET_NODE`(<BLANK>)와 `*SET_NODE_LIST` 가 다르게 다뤄졌다 — 옮기기 장치가 이름이
      `*SET_NODE_LIST` 로 시작할 때만 봐서, 같은 세트가 `_LIST` 면 67·68 → 199·200 으로 **옮겨지고** 맨 이름이면 둘 다
      **빠졌다**(조용히 세트가 줄어든다).

  지금은 세 장치가 정본 표(`noderefs::listCardOf`·`listCardFields`)를 쓴다.

usage: test_dead_node_list_cards.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
FAILS = []

BOX = """output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 10
ny: 5
nz: 2
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
"""


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s   %s" % (name, str(detail).strip()[:300]))


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], capture_output=True, text=True, timeout=300, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def restack_yaml(model, out, nlayers):
    y = "model: %s\noutput: %s\ntarget_pid: 1\ndirection: z\npid_refs: warn\nlayers:\n" % (model, out)
    for i in range(nlayers):
        y += ("  - title: L%d\n    thickness: %.6f\n    num_elements: 1\n    material_card: |\n"
              "      *MAT_ELASTIC\n      $#     mid        ro         e        pr\n"
              "        MID%03d  7.85E-09    210000       0.3\n" % (i + 1, 2.0 / nlayers, i + 1))
    return y


def block(deck, kw):
    """키워드가 정확히 kw 인 첫 블록의 데이터 줄(주석 뺌)."""
    L = open(deck, encoding="utf-8", errors="replace").read().splitlines()
    for i, l in enumerate(L):
        if l.strip().upper() == kw:
            out = []
            for m in L[i + 1:]:
                if m.startswith("*"):
                    break
                if m.strip() and not m.startswith("$"):
                    out.append(m)
            return out
    return None


def ints(lines):
    return [int(t) for l in lines for t in re.findall(r"-?\d+", l)]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    d = tempfile.mkdtemp(prefix="dnl_")
    try:
        open(os.path.join(d, "box.yaml"), "w").write(BOX)
        run(binary, d, "generate", "box", "box.yaml")
        base = open(os.path.join(d, "box.k")).read()
        # 중간면(z=1) 절점은 67..132 다 — 셋으로 다시 쌓으면 옮길 곳이 없고, 둘로 쌓으면 같은 자리에 새 절점이 생긴다

        print("[A 세트 ID 를 절점으로 읽지 않는다 — 셋으로 쌓기(옮길 곳 없음)]")
        cards = ("*SET_NODE_LIST\n        70\n         1         2\n"
                 "*SET_NODE_LIST\n        71\n         2         3\n"
                 "*SET_NODE_INTERSECT\n       900\n        70        71\n"
                 "*SET_SEGMENT_INTERSECT\n       901\n        70        71\n"
                 "*SET_NODE_LIST\n        72\n         1        67\n"
                 "*DATABASE_HISTORY_NODE\n         1        67         2\n")
        open(os.path.join(d, "a.k"), "w").write(base.replace("*END", cards + "*END", 1))
        open(os.path.join(d, "a.yaml"), "w").write(restack_yaml("a.k", "a_out.k", 3))
        rc, out = run(binary, d, "restack", "a.yaml")
        ao = os.path.join(d, "a_out.k")
        check("A-0 restack 이 돈다(pid_refs: warn)", rc == 0 and os.path.exists(ao), out[-300:])
        if os.path.exists(ao):
            check("A-1 ★교집합 세트 900 의 멤버(세트 ID 70·71)가 그대로다",
                  ints(block(ao, "*SET_NODE_INTERSECT") or []) == [900, 70, 71], block(ao, "*SET_NODE_INTERSECT"))
            check("A-2 ★세그먼트 교집합 901 도 그대로다",
                  ints(block(ao, "*SET_SEGMENT_INTERSECT") or []) == [901, 70, 71], block(ao, "*SET_SEGMENT_INTERSECT"))
            check("A-3 교집합을 「지운 노드」로 보고하지 않는다", "INTERSECT" not in out, [l for l in out.splitlines() if "INTERSECT" in l][:2])
            # 목록 세트의 진짜 지운 절점은 예전처럼 뺀다(동작 불변)
            sets = [b for b in re.split(r"\n(?=\*)", open(ao).read()) if b.startswith("*SET_NODE_LIST")]
            s72 = [ints([l for l in b.splitlines()[1:] if l.strip() and not l.startswith("$")]) for b in sets]
            check("A-4 목록 세트 72 의 지운 절점 67 은 예전처럼 빠진다", [72, 1] in s72, s72)
            check("A-5 이력 목록의 지운 절점 67 도 예전처럼 빠진다",
                  ints(block(ao, "*DATABASE_HISTORY_NODE") or []) == [1, 2], block(ao, "*DATABASE_HISTORY_NODE"))

        print("[B 맨 *SET_NODE 도 목록이다 — 둘로 쌓기(같은 자리에 새 절점)]")
        cards = ("*SET_NODE\n        80\n         1        67        68\n"
                 "*SET_NODE_LIST\n        81\n         1        67        68\n")
        open(os.path.join(d, "b.k"), "w").write(base.replace("*END", cards + "*END", 1))
        open(os.path.join(d, "b.yaml"), "w").write(restack_yaml("b.k", "b_out.k", 2))
        rc, out = run(binary, d, "restack", "b.yaml")
        bo = os.path.join(d, "b_out.k")
        check("B-0 restack 이 돈다", rc == 0 and os.path.exists(bo), out[-300:])
        if os.path.exists(bo):
            s80 = ints(block(bo, "*SET_NODE") or [])
            s81 = ints(block(bo, "*SET_NODE_LIST") or [])
            check("B-1 `_LIST` 는 67·68 을 같은 자리 새 절점으로 옮긴다(기준)",
                  len(s81) == 4 and s81[:2] == [81, 1] and 67 not in s81 and 68 not in s81, s81)
            check("B-2 ★맨 `*SET_NODE` 도 **같은** 새 절점으로 옮긴다(빼지 않는다)", s80[1:] == s81[1:], (s80, s81))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
