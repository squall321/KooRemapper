#!/usr/bin/env python3
"""contact 예제를 돌린 산출이 커밋된 골든과 **바이트로** 같은가 — 전수.

왜 이 시험이 있나 (2026-10-15).

  장부(`deck-contract-checklist.md` P1-3)가 「contact 골든 10장이 관문」이라고 적고 그것을
  `IdAllocator` 첫 채택의 증명 표면으로 삼았다. 실제로 맞대 보니 **그 골든을 보는 시험이 없었다.**
  그리고 커밋된 `examples/contact/*_result.k` 13장 중 **10장이 이미 지금 산출과 달랐다.** 차이는
  전부 세그먼트 절점의 순회 방향이다(`1 2 3 4` → `1 4 3 2` · 줄마다 같은 절점 집합 · 같은 첫
  절점) — 2026-10-05 `f1b3709` 가 면 0·3·4 의 순회를 뒤집었을 때 예제를 다시 만들지 않은 것이다.
  같은 변경이 ctest 를 10일 동안 빨갛게 했다. 이쪽은 **아무것도 빨개지지 않았다** — 보는 시험이
  없었기 때문이다.

  관문이라고 적힌 것이 관문이 아니면, 그 위에 세운 증명은 아무것도 증명하지 않는다.

무엇을 보나.
  A 예제 yaml 마다 산출이 골든과 **바이트 동일**하다(골든에는 날짜 줄이 없다 — 가리지 않는다)
  B 산출을 내는 예제마다 골든이 **있다** — 골든 없는 새 예제가 들어오면 여기서 빨개진다
  C 골든마다 그것을 내는 예제가 있다 — 주인 없는 골든이 남으면 빨개진다
  D 맞댄 장 수가 0 이 아니다 — 세는 관문이 0 을 세면 언제나 초록이다

골든을 고쳐야 할 때(의도된 출력 변경) — 산출을 그대로 복사해 넣고, 커밋에 **무엇이 왜** 바뀌었는지
적는다. 이 시험은 그 판단을 대신하지 않는다. 다만 **말없이 어긋나는 것**을 막는다.

usage: test_contact_goldens.py <KooRemapper 바이너리>
"""
import filecmp
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples", "contact")
RESULT = re.compile(r"_result.*\.k$")

FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    return cond


def first_diff(a, b):
    A = open(a, encoding="utf-8", errors="replace").read().splitlines()
    B = open(b, encoding="utf-8", errors="replace").read().splitlines()
    for i, (x, y) in enumerate(zip(A, B)):
        if x != y:
            return "line %d: 골든 %r / 산출 %r" % (i + 1, x.strip()[:50], y.strip()[:50])
    return "줄 수 %d / %d" % (len(A), len(B))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])

    goldens = sorted(f for f in os.listdir(EX) if RESULT.search(f))
    yamls = sorted(f for f in os.listdir(EX) if f.endswith(".yaml"))
    d = tempfile.mkdtemp(prefix="ctg_")
    try:
        for f in os.listdir(EX):                       # 입력만 — 골든은 들이지 않는다
            p = os.path.join(EX, f)
            if os.path.isfile(p) and not RESULT.search(f):
                shutil.copy2(p, d)
        for y in yamls:
            r = subprocess.run([binary, "contact", y], cwd=d, capture_output=True, text=True,
                               timeout=300, encoding="utf-8", errors="replace")
            check("%s rc=0" % y, r.returncode == 0, (r.stdout + r.stderr)[-200:])
        produced = sorted(f for f in os.listdir(d) if RESULT.search(f))

        print("[A 산출 = 골든]")
        seen = 0
        for f in produced:
            g = os.path.join(EX, f)
            if not os.path.exists(g):
                continue
            seen += 1
            same = filecmp.cmp(g, os.path.join(d, f), shallow=False)
            check("A %s 가 골든과 바이트 동일" % f, same, "" if same else first_diff(g, os.path.join(d, f)))
        print("[B·C 짝]")
        for f in produced:
            check("B %s 에 골든이 있다" % f, f in goldens, "산출은 있는데 골든이 없다 — 넣어라")
        for g in goldens:
            check("C %s 를 내는 예제가 있다" % g, g in produced, "주인 없는 골든이다")
        check("D 맞댄 골든이 0 장이 아니다", seen >= 10, "%d 장" % seen)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항 (골든 %d 장)" % (len(OKS), len(goldens)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
