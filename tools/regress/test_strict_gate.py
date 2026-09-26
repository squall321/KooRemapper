#!/usr/bin/env python3
"""`info --strict` 가 **LS-DYNA 가 키워드 단계에서 죽을 덱만** 막는가 (P1-5).

왜 이 시험이 있나 (2026-09-26):

  P1-6 이 검사를 넓혀 보고는 정확해졌는데 **막는 자리가 없었다.** 실측 — 추적 덱 489장 중
  **40장에 실제 결함**이 들어 있고 그 40장이 전부 `rc=0` 으로 나갔다. 하류(pyKooCAE REMAP
  체인·플랫폼 워커)는 rc 로만 판정하므로 LS-DYNA 에 가서야 터진다.

무엇을 관문에 넣고 무엇을 뺐는지는 **489장 전수 실측으로** 정했다.

  넣은 것 — 미정의 참조(**단정 등급만**) 39장 · 망가진 카드 0장 · 없는 노드를 가리키는 요소 1장
  뺀 것   — `Mesh has no nodes` **86장**: 자재만 있는 덱·IGA 덱에서 정상이다
            음수 자코비안 **111장**: 품질 경고이고 키워드 단계에서 죽지 않는다

  오탐 한 번에 아무도 이 관문을 안 쓴다. 그래서 뺀 쪽의 숫자를 여기 적어 둔다 — 누가 다시
  넣으려 하면 정상 픽스처 86장·111장이 막힌다는 것을 먼저 알아야 한다.

**`info` 의 rc 는 0 그대로다.** 그것이 계약이고(`test_reference_integrity.py` 가 일부러 단언하고
플랫폼이 업로드마다 돈다) 이 시험의 A 묶음이 그것을 지킨다.

usage: test_strict_gate.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))

# 리포 실제 덱 — (경로, 관문이 막아야 하나, 왜)
REPO_CASES = [
    ("examples/squeeze_interference/interference_model.k", True,
     "*SECTION 이 덱에 아예 없는데 파트 둘이 섹션 1 을 가리킨다"),
    ("test_data/arc_unfold_fix.k", True,
     "요소 41 이 노드 57 을 가리키는데 그 노드가 파일에 없다(56-66 이 비어 있다)"),
    ("examples/offset/01_basic_result.k", True,
     "요소가 파트 1 을 가리키는데 이 덱에는 파트 10 만 있다"),
    ("examples/indent/small/block.k", False,
     "평범한 온전한 덱"),
    ("examples/assemble_display/mat_all.k", False,
     "자재만 있는 덱 — `Mesh has no nodes` 는 결함이 아니다"),
    ("examples/arc30/arc30_mapped.k", False,
     "음수 자코비안이 있다 — 품질 경고이고 키워드 단계에서 죽지 않는다"),
    ("examples/wrap/cylinder_2layer.k", False,
     "한 키워드 아래 섹션 1·2 가 정의돼 있다(P1-6 이 오탐을 냈던 덱)"),
]

CLEAN = """*KEYWORD
*PART
cube
       7       1       1
*SECTION_SOLID
       1       1
*MAT_ELASTIC
       1 7.85E-9  210000     0.3
*NODE
       1     0.0     0.0     0.0
       2     1.0     0.0     0.0
       3     1.0     1.0     0.0
       4     0.0     1.0     0.0
       5     0.0     0.0     1.0
       6     1.0     0.0     1.0
       7     1.0     1.0     1.0
       8     0.0     1.0     1.0
*ELEMENT_SOLID
       1       7       1       2       3       4       5       6       7       8
*END
"""
ELEM = "       1       7       1       2       3       4       5       6       7       8"
ID_HEAD = "*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET_ID\n        11Contact_1\n"
C1 = "         1         2         3         3         0         0         0         0\n"
C2 = "       0.2       0.1       0.0       0.0       0.0         0       0.0  1.00E+20\n"
C3 = "       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0\n"


def check(name, cond, detail=""):
    print("  %-68s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:400]) if detail else ""))


def run(binary, path, strict, cwd):
    argv = [binary, "info", path] + (["--strict"] if strict else [])
    p = subprocess.run(argv, capture_output=True, text=True, timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print("usage: test_strict_gate.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    # ⚠ op 을 리포 루트에서 돌리면 추적 픽스처를 덮어쓴다. 임시 폴더에서 돈다.
    d = tempfile.mkdtemp(prefix="strict_")

    def deck(name, text):
        p = os.path.join(d, name)
        open(p, "w", newline="\n").write(text)
        return p

    planted = [
        ("요소가 없는 파트를 가리킨다", CLEAN.replace(ELEM, ELEM.replace("       7", "      99", 1)), True),
        ("파트가 없는 섹션을 가리킨다", CLEAN.replace("       7       1       1", "       7      55       1"), True),
        ("요소 PID 가 -1 이다", CLEAN.replace(ELEM, ELEM.replace("       7", "      -1", 1)), True),
        ("SSID 칸에 실수가 들어 있다",
         CLEAN.replace("*END", ID_HEAD + "      0.33       0.1       3         3         0         0         0         0\n" + C2 + C3 + "*END", 1), True),
        ("필수 Card 3 가 사라졌다", CLEAN.replace("*END", ID_HEAD + C1 + C2 + "*END", 1), True),
        ("없는 노드를 가리키는 요소", CLEAN.replace(ELEM, ELEM.replace("       8", "      99", 1)), True),
        ("온전한 덱", CLEAN, False),
    ]

    print("[A `info` 의 rc 는 0 그대로다 — 이것이 계약이다]")
    for i, (name, text, _should_block) in enumerate(planted):
        p = deck("a%d.k" % i, text)
        rc, out = run(binary, p, False, d)
        check("A " + name, rc == 0, "rc=%d / %s" % (rc, out[-200:]))

    print("[B `--strict` 는 키워드 단계에서 죽을 것만 막는다 — 심은 결함]")
    for i, (name, text, should_block) in enumerate(planted):
        p = deck("b%d.k" % i, text)
        rc, out = run(binary, p, True, d)
        check("B %s → %s" % (name, "막는다" if should_block else "통과"),
              (rc != 0) == should_block, "rc=%d / %s" % (rc, out[-240:]))
        if should_block:
            check("   B 이유를 한 줄로 말한다", "--strict:" in out and "키워드 단계" in out, out[-240:])

    print("[C 단정할 수 없으면 막지 않는다 — `*INCLUDE` 를 못 읽었을 때]")
    # 인클루드가 있으면 그 안에 정의됐을 수 있다. 등급이 '불확실' 이므로 rc 를 올리면 오탐이다.
    inc = CLEAN.replace(ELEM, ELEM.replace("       7", "      99", 1)) \
               .replace("*END", "*INCLUDE\nparts_elsewhere.k\n*END", 1)
    p = deck("c0.k", inc)
    rc, out = run(binary, p, True, d)
    check("C-1 인클루드를 못 읽었으면 rc=0", rc == 0, "rc=%d / %s" % (rc, out[-260:]))
    check("   C-1 그래도 못 찾았다고 말한다", "못 찾았습니다" in out or "단정" in out, out[-300:])

    # 노드 축에도 같은 빗장이 있어야 한다 — 노드가 `*INCLUDE` 안에 있을 수 있다.
    # (이 경우가 없으면 "인클루드를 못 읽어도 단정한다" 는 돌연변이가 살아남는다 — 실제로 살아남았다.)
    inc_node = CLEAN.replace(ELEM, ELEM.replace("       8", "      99", 1)) \
                    .replace("*END", "*INCLUDE\nnodes_elsewhere.k\n*END", 1)
    p = deck("c1.k", inc_node)
    rc, out = run(binary, p, True, d)
    check("C-2 없는 노드 + 인클루드 → rc=0", rc == 0, "rc=%d / %s" % (rc, out[-260:]))

    print("[D 리포의 실제 덱 — 막을 것과 막지 말 것]")
    for rel, should_block, why in REPO_CASES:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            check("D " + rel, False, "덱이 없다 — 시험을 고쳐라")
            continue
        rc0, _ = run(binary, path, False, d)
        rc1, out = run(binary, path, True, d)
        check("D %s → %s" % (rel, "막는다" if should_block else "통과"),
              (rc1 != 0) == should_block, why + " / rc=%d %s" % (rc1, out[-200:]))
        check("   D %s 는 플래그 없이는 rc=0" % os.path.basename(rel), rc0 == 0, "rc=%d" % rc0)

    shutil.rmtree(d, ignore_errors=True)
    print()
    if FAILS:
        print("--- 실패 %d건 ---" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
