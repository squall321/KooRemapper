#!/usr/bin/env python3
"""같은 종류의 세트 ID 가 겹치면 말한다 — 그리고 **다른 종류의 공존은 건드리지 않는다** (P1-3).

왜 이 시험이 있나 (2026-09-28):

  `assemble` 의 `ld_findMaxSetSegmentId` 가 `*SET_SEGMENT_TITLE` 블록에서 **제목줄을 SID 줄로**
  읽었다(`_TITLE` 을 건너뛰지 않았다). `iss >> id` 가 실패해 최대값이 0 으로 남고, 새 세트가 1 부터
  시작해 **같은 타입 SID 가 중복**됐다. `_COLLECT` 가 없으면 LS-DYNA 는 error termination 한다.

  실측 — 커밋된 `examples/load/mesh_contact_load.k` 에 `*SET_SEGMENT_TITLE` SID **1 이 두 장**
  (26274줄 contact detect · 37535줄 load) 있었다. **우리 산출물이 불법 덱이었고** 아무도 몰랐다.

  그래서 두 가지를 한다 — 산출법을 고치고(`bc_findMaxSetNodeId` 의 규약을 그대로 따른다),
  `info` 가 그 부류를 **보이게** 한다.

⚠ **타입을 지우고 한 통으로 보면 안 된다.** SID 네임스페이스는 종류별로 갈리므로
`*SET_PART 6` 과 `*SET_NODE 6` 의 공존은 **합법**이고, 실사용 덱 1,303장 중 **312장(24%)** 이
그렇다(2026-09-27 실측). 한 통으로 보면 넷 중 하나가 오탐이 되고, 그러면 아무도 이 보고를 안 믿는다.

usage: test_set_id_uniqueness.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
BLOCK = os.path.join(REPO, "examples", "indent", "small", "block.k")


def check(name, cond, detail=""):
    print("  %-66s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:400]) if detail else ""))


def info(binary, path):
    d = os.path.dirname(path)
    p = subprocess.run([binary, "info", os.path.basename(path)], capture_output=True, text=True,
                       timeout=600, cwd=d)
    return p.returncode, p.stdout + p.stderr


def deck(d, name, cards):
    t = open(BLOCK, encoding="latin-1", newline="").read()
    p = os.path.join(d, name)
    open(p, "w", newline="\n").write(t.replace("*END", cards + "*END", 1))
    return p


def overlaps(out):
    return [l.strip() for l in out.splitlines() if "겹칩니다" in l]


def main():
    if len(sys.argv) < 2:
        print("usage: test_set_id_uniqueness.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary) or not os.path.exists(BLOCK):
        print("binary or fixture not found")
        return 2
    d = tempfile.mkdtemp(prefix="setid_")

    SEG = "*SET_SEGMENT\n         %d  0.0  0.0  0.0  0.0\n       1       2       3       4\n"
    SEG_T = ("*SET_SEGMENT_TITLE\nSome title here\n"
             "         %d  0.0  0.0  0.0  0.0\n       1       2       3       4\n")
    NODE = "*SET_NODE_LIST\n         %d\n       1       2       3       4\n"
    PART = "*SET_PART_LIST\n         %d\n       1\n"

    print("[A 같은 종류의 SID 가 겹치면 말한다]")
    rc, out = info(binary, deck(d, "a0.k", SEG % 5 + SEG % 5))
    check("A-1 같은 종류 SID 중복을 잡는다", len(overlaps(out)) == 1, overlaps(out))
    check("A-2 rc 는 0 그대로(info 계약)", rc == 0, rc)
    # ⚠ `_TITLE` 이 붙어도 잡아야 한다 — 이 결함의 원본 모양이 그것이다.
    rc, out = info(binary, deck(d, "a1.k", SEG_T % 7 + SEG_T % 7))
    check("A-3 `_TITLE` 변형에서도 잡는다(이 결함의 원본 모양)", len(overlaps(out)) == 1, overlaps(out))
    # 제목줄을 SID 로 오독하면 두 SID 를 못 보고 조용해진다 — 그 오독이 결함의 원인이었다.
    rc, out = info(binary, deck(d, "a2.k", SEG_T % 3 + SEG % 3))
    check("A-4 `_TITLE` 과 무제목이 섞여 겹쳐도 잡는다", len(overlaps(out)) == 1, overlaps(out))

    print("[B 다른 종류의 공존은 건드리지 않는다 — 실사용 24%가 이렇다]")
    rc, out = info(binary, deck(d, "b0.k", PART % 6 + NODE % 6 + SEG % 6))
    check("B-1 PART 6 · NODE 6 · SEGMENT 6 공존은 합법", overlaps(out) == [], overlaps(out))
    rc, out = info(binary, deck(d, "b1.k", NODE % 1 + NODE % 2 + NODE % 3))
    check("B-2 같은 종류라도 번호가 다르면 조용하다", overlaps(out) == [], overlaps(out))

    print("[C `_COLLECT` 는 겹쳐도 합법이다]")
    COLL = "*SET_SEGMENT_COLLECT\n         9  0.0  0.0  0.0  0.0\n       1       2       3       4\n"
    rc, out = info(binary, deck(d, "c0.k", COLL + COLL))
    check("C-1 `_COLLECT` 중복은 보고하지 않는다", overlaps(out) == [], overlaps(out))

    print("[F *SECTION·*MAT 도 같은 종류 안에서 유일해야 한다]")
    SEC = "*SECTION_SOLID\n       %d         1\n"
    MAT = "*MAT_ELASTIC\n       %d 7.85E-9  210000     0.3\n"
    rc, out = info(binary, deck(d, "f0.k", SEC % 7 + SEC % 7))
    check("F-1 SECID 중복을 잡는다", len(overlaps(out)) == 1, overlaps(out))
    rc, out = info(binary, deck(d, "f1.k", MAT % 9 + MAT % 9))
    check("F-2 MID 중복을 잡는다", len(overlaps(out)) == 1, overlaps(out))
    rc, out = info(binary, deck(d, "f2.k", SEC % 4 + MAT % 4 + NODE % 4))
    check("F-3 SECTION 4 · MAT 4 · SET_NODE 4 공존은 합법", overlaps(out) == [], overlaps(out))
    # ⚠ 첫 칸이 **구조 MID 가 아닌** `*MAT_` 변종. 이것을 세면 리포 덱 4장에서 오탐이 났다
    # (실측: `materials/test_matdb_result.k` 등). `*MAT_THERMAL_*` 의 첫 칸은 **TMID** 다.
    THERM = "*MAT_THERMAL_ISOTROPIC\n       %d       0.0       0.0       0.0\n       1.0       1.0\n"
    rc, out = info(binary, deck(d, "f3.k", MAT % 2 + THERM % 2))
    check("F-4 *MAT_THERMAL_ 의 TMID 는 구조 MID 와 다른 대역", overlaps(out) == [], overlaps(out))
    ADD = "*MAT_ADD_THERMAL_EXPANSION\n       %d     1.0E-5\n"
    rc, out = info(binary, deck(d, "f4.k", MAT % 3 + ADD % 3))
    check("F-5 *MAT_ADD_ 의 첫 칸은 PID — 재질로 세지 않는다", overlaps(out) == [], overlaps(out))

    print("[G restack 이 파트가 안 쓰는 *SECTION 을 재발행하지 않는다]")
    # ⚠ `maxSectionId_` 가 `Part::sectionId` 만 보면 아무 파트도 안 쓰는 섹션을 놓치고 그 번호를
    # **다시 발행**한다. 실측: `restack_base.k` 에 `*SECTION_SOLID 2` 를 넣으면 산출 SECID 가
    # `[1, 2, 2, 3, 4]` 가 됐다(rc=0).
    rt = os.path.join(REPO, "examples", "replace_test")
    yml = os.path.join(rt, "assemble_restack_test.yaml")
    if not os.path.isfile(yml):
        check("G 예제가 있다", False, "assemble_restack_test.yaml 이 없다")
    else:
        w = tempfile.mkdtemp(prefix="setid_rs_")
        for fn in os.listdir(rt):
            src = os.path.join(rt, fn)
            if os.path.isfile(src):
                shutil.copy(src, w)
        base = open(os.path.join(w, "restack_base.k"), encoding="latin-1", newline="").read()
        open(os.path.join(w, "trap.k"), "w", newline="\n").write(
            base.replace("*END", "*SECTION_SOLID\n         2         1\n*END", 1))
        cfg = open(yml, encoding="utf-8").read()
        cfg = cfg.replace("base_model: restack_base.k", "base_model: trap.k")
        cfg = cfg.replace("output: restack_result", "output: trap_result")
        open(os.path.join(w, "trap.yaml"), "w", newline="\n").write(cfg)
        p3 = subprocess.run([binary, "assemble", "trap.yaml"], capture_output=True, text=True,
                            timeout=900, cwd=w)
        check("G-1 assemble rc=0", p3.returncode == 0, (p3.stdout + p3.stderr)[-240:])
        made = os.path.join(w, "trap_result.k")
        if os.path.exists(made):
            rc, out = info(binary, made)
            check("G-2 산출 덱에 SECID 중복이 없다", overlaps(out) == [], overlaps(out))
        else:
            check("G-2 산출물이 생겼다", False, (p3.stdout + p3.stderr)[-240:])
        shutil.rmtree(w, ignore_errors=True)

    print("[E 산출법 자체를 지킨다 — assemble 이 겹치는 SID 를 만들지 않는다]")
    # ⚠ 위 A~D 는 **탐지**만 본다. 결함의 원본은 `assemble` 의 발행 스캐너가 `_TITLE` 을 건너뛰지
    # 않은 것이었고, 그것을 되돌리면 이 자리에서만 잡힌다 — 그래서 실제로 돌린다.
    ex = os.path.join(REPO, "examples", "load")
    if not os.path.isfile(os.path.join(ex, "assemble_contact_load.yaml")):
        check("E 예제가 있다", False, "examples/load/assemble_contact_load.yaml 이 없다")
    else:
        w = tempfile.mkdtemp(prefix="setid_asm_")
        for fn in os.listdir(ex):
            src = os.path.join(ex, fn)
            if os.path.isfile(src):
                shutil.copy(src, w)
        p2 = subprocess.run([binary, "assemble", "assemble_contact_load.yaml"],
                            capture_output=True, text=True, timeout=900, cwd=w)
        check("E-1 assemble rc=0", p2.returncode == 0, (p2.stdout + p2.stderr)[-240:])
        made = os.path.join(w, "mesh_contact_load.k")
        if os.path.exists(made):
            rc, out = info(binary, made)
            check("E-2 산출 덱에 같은 종류 SID 중복이 없다", overlaps(out) == [], overlaps(out))
        else:
            check("E-2 산출물이 생겼다", False, (p2.stdout + p2.stderr)[-240:])
        shutil.rmtree(w, ignore_errors=True)

    print("[D 리포 덱에 오탐이 없다]")
    for rel in ("examples/load/mesh_contact_load.k", "examples/contact/model.k",
                "examples/indent/small/block.k"):
        p = os.path.join(REPO, rel)
        if not os.path.exists(p):
            check("D " + rel, False, "덱이 없다")
            continue
        rc, out = info(binary, p)
        check("D " + rel, overlaps(out) == [], overlaps(out))

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
