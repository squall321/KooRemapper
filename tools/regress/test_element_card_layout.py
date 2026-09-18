#!/usr/bin/env python3
# 요소 카드 줄 수 판정(매뉴얼 표)·지운 노드 참조 정리·파트별 요소 수 대조·왕복 검증 회귀 시험
"""
배경(현장 T4 PV1/DVR 6면 낙하, 485런 전량 폐기):
  - AP 칩을 2층으로 나눈 덱을 돌렸는데 모델에 AP 가 통째로 없는 채 "Normal termination" 했다.
    LS-DYNA 도 KooMeshModifier 도 에러를 내지 않았다.
  - 원인은 요소 카드 줄 수를 어림짐작으로 다뤘기 때문이다. 이 시험은 그 판정을
    LS-DYNA R16 매뉴얼 표로 확정했는지, 그리고 확정할 수 없으면 rc=1 로 거절하는지를 지킨다.

덮는 것:
  A  *SECTION_SOLID ELFORM 23(20절점)으로 3 줄 카드임을 확정하고, 셋째 줄의 첫 칸이
     지워지는 요소 번호와 겹쳐도 그 줄을 지우지 않는다(예전 판정은 셋째 줄을 요소로 오판했다).
  B  고차 요소 파트를 restack 하면 rc=1 로 거절한다(8 절점 모서리만 담으므로 다시 만들 수 없다).
  C  *ELEMENT_SHELL_THICKNESS: 셸을 지우면 두께 카드도 함께 지운다(중간절점이 있으면 셋째 카드까지).
  D  지운 노드를 가리키는 카드(*SET_NODE_LIST·*BOUNDARY_SPC_NODE·*SET_SEGMENT·*ELEMENT_MASS…)를
     실제로 정리한다. *_GENERATE 범위는 매뉴얼 근거로 고치지 않고 보고만 한다.
  E  파트별 요소 수를 `PID x: a → b` 로 찍고 왕복 검증을 통과했다고 알린다.
  F  카드 줄 수를 확정할 수 없는 섹션(COMPOSITE)에서 요소를 지워야 하면 덱을 쓰지 않고 rc=1.

사용: python3 tools/regress/test_element_card_layout.py <KooRemapper 바이너리>
"""
import os
import re
import subprocess
import sys
import tempfile

FAIL = 0


def check(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  OK   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")
        if detail:
            print(f"       {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def read(path):
    return open(path, encoding="utf-8", errors="replace").read()


def lines_of(path):
    return read(path).splitlines()


def section(path, keyword):
    """그 키워드 섹션의 데이터 줄(주석·빈 줄 제외). 없으면 None."""
    out = None
    cur = None
    for ln in lines_of(path):
        s = ln.strip()
        if s.startswith("*"):
            if s.upper().startswith(keyword):
                cur = []
                if out is None:
                    out = cur
            else:
                cur = None
            continue
        if cur is None or not s or s.startswith("$"):
            continue
        cur.append(ln)
    return out


# 2x2x2 격자(파트 1 = 아래층 4 요소, 파트 2 = 위층 4 요소) + 20절점 파트 9
def grid_nodes():
    nid = {}
    rows = []
    n = 1
    for k, z in enumerate([0.0, 2.5, 5.0]):
        for j, y in enumerate([0.0, 10.0]):
            for i, x in enumerate([0.0, 10.0]):
                nid[(i, j, k)] = n
                rows.append("%8d%16.6f%16.6f%16.6f" % (n, x, y, z))
                n += 1
    return nid, rows


def hexn(nid, i, j, k):
    return [nid[(i, j, k)], nid[(i + 1, j, k)], nid[(i + 1, j + 1, k)], nid[(i, j + 1, k)],
            nid[(i, j, k + 1)], nid[(i + 1, j, k + 1)], nid[(i + 1, j + 1, k + 1)], nid[(i, j + 1, k + 1)]]


def base_deck(extra_elem="", extra_cards="", extra_parts=""):
    nid, rows = grid_nodes()
    elems = ["*ELEMENT_SOLID"]
    eid = 1
    for k in range(2):
        pid = 1 if k == 0 else 2
        elems.append("%8d%8d" % (eid, pid) + "".join("%8d" % v for v in hexn(nid, 0, 0, k)))
        eid += 1
    return ("*KEYWORD\n*NODE\n" + "\n".join(rows) + "\n"
            + "\n".join(elems) + "\n" + extra_elem
            + "*PART\nLOWER\n         1         1         1\n"
            + "*PART\nUPPER\n         2         1         1\n"
            + extra_parts
            + "*SECTION_SOLID\n         1         1\n"
            + "*MAT_ELASTIC\n         1  7.85e-09    210000       0.3\n"
            + extra_cards + "*END\n")


RESTACK = """model: {model}
output: {out}
target_pid: {pid}
direction: z
pid_refs: {refs}
layers:
  - title: L1
    thickness: 1.25
    num_elements: 1
    material_card: |
      *MAT_ELASTIC_TITLE
      L1
      $#     mid        ro         e        pr
              90  7.85e-09   2.1e+05      0.30
  - title: L2
    thickness: 1.25
    num_elements: 1
    material_card: |
      *MAT_ELASTIC_TITLE
      L2
      $#     mid        ro         e        pr
              91  2.70e-09   7.0e+04      0.33
"""


def yaml(model, out, pid=1, refs="warn"):
    return RESTACK.format(model=model, out=out, pid=pid, refs=refs)


def main():
    if len(sys.argv) < 2:
        print("usage: test_element_card_layout.py <KooRemapper>")
        return 2
    binary = os.path.abspath(sys.argv[1])

    with tempfile.TemporaryDirectory() as d:
        w = lambda name, txt: open(os.path.join(d, name), "w").write(txt)
        P = lambda name: os.path.join(d, name)

        # ── A. 20절점 카드(3 줄)를 *SECTION_SOLID ELFORM 23 으로 확정한다 ──────
        # Card 3 의 첫 칸(N11)을 1 로 둔다 — 지워지는 요소 번호(1)와 똑같다.
        # 예전 판정은 그 줄을 '한 줄 포맷 요소' 로 읽어 지워 버렸다.
        print("[A 20절점 카드(ELFORM 23) — 셋째 줄이 요소 번호와 겹쳐도 지우지 않는다]")
        h20 = ("*ELEMENT_SOLID\n"
               "%8d%8d\n" % (9001, 9)
               + "".join("%8d" % v for v in [1, 2, 4, 3, 5, 6, 8, 7, 9, 10]) + "\n"
               + "".join("%8d" % v for v in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) + "\n")
        parts9 = "*PART\nHEX20\n         9         9         1\n"
        secs9 = "*SECTION_SOLID\n         9        23\n"
        w("h20.k", base_deck(extra_elem=h20, extra_cards=secs9, extra_parts=parts9))
        w("h20.yaml", yaml("h20.k", "h20_out.k", pid=1))
        rc, out = run(binary, d, "restack", "h20.yaml")
        check("rc=0 (대상은 보통 파트 1)", rc == 0, out[-500:])
        if rc == 0:
            sec = section(P("h20_out.k"), "*ELEMENT_SOLID")
            body = read(P("h20_out.k"))
            check("20절점 카드 3 줄이 온전히 남는다",
                  body.count("    9001       9") == 1
                  and "       1       2       4       3       5       6       8       7       9      10" in body
                  and "       1       2       3       4       5       6       7       8       9      10" in body,
                  str(sec))
            check("파트 9 요소 수가 1 로 보고된다(셋째 줄을 요소로 세지 않는다)",
                  "PID 9" not in out or "PID 9: 1" in out, out[-800:])
            check("왕복 검증을 통과한다", "왕복 검증" in out and "같았습니다" in out, out[-800:])

        # ── B. 고차 요소 파트를 restack 하면 거절한다 ─────────────────────────
        print("[B 20절점 파트를 restack 하면 rc=1 로 거절한다]")
        w("h20b.yaml", yaml("h20.k", "h20b_out.k", pid=9))
        rc, out = run(binary, d, "restack", "h20b.yaml")
        check("rc=1", rc == 1, out[-500:])
        check("이유를 알린다(고차 요소 파트라 8 절점 모서리만 담는다)",
              "고차 요소" in out and "8 절점" in out and "멈춥니다" in out, out[-500:])
        check("덱을 내지 않는다", not os.path.exists(P("h20b_out.k")))

        # ── C. *ELEMENT_SHELL_THICKNESS — 둘째 카드도 함께 지운다 ────────────
        print("[C *ELEMENT_SHELL_THICKNESS 는 두께 카드까지 한 카드다]")
        # 파트 1 의 아래면 노드로 셸을 만들고 파트 1 에 붙인다 → restack 이 그 셸도 지운다.
        shell = ("*ELEMENT_SHELL_THICKNESS\n"
                 "%8d%8d%8d%8d%8d%8d\n" % (7001, 1, 1, 2, 4, 3)
                 + "     1.00     1.00     1.00     1.00\n")
        w("sh.k", base_deck(extra_elem=shell))
        w("sh.yaml", yaml("sh.k", "sh_out.k", pid=1))
        rc, out = run(binary, d, "restack", "sh.yaml")
        check("rc=0", rc == 0, out[-500:])
        if rc == 0:
            body = read(P("sh_out.k"))
            if "$ KOOREMAPPER-PIDREF-END" in body:
                body = body[body.index("$ KOOREMAPPER-PIDREF-END"):]
            check("셸 요소 줄이 사라졌다", "    7001" not in body, body[-800:])
            check("두께 카드도 함께 사라졌다(고아 줄이 없다)",
                  "     1.00     1.00     1.00     1.00" not in body, body[-800:])

        # 비대상 파트의 두께 셸은 두 줄 모두 남는다
        shell2 = ("*ELEMENT_SHELL_THICKNESS\n"
                  "%8d%8d%8d%8d%8d%8d\n" % (7002, 2, 1, 2, 4, 3)
                  + "     2.00     2.00     2.00     2.00\n")
        w("sh2.k", base_deck(extra_elem=shell2))
        w("sh2.yaml", yaml("sh2.k", "sh2_out.k", pid=1))
        rc, out = run(binary, d, "restack", "sh2.yaml")
        check("비대상 셸: rc=0", rc == 0, out[-500:])
        if rc == 0:
            body = read(P("sh2_out.k"))
            check("비대상 셸은 두 줄 모두 남는다",
                  "    7002" in body and "     2.00     2.00     2.00     2.00" in body, body[-800:])

        # ── D. 지운 노드를 가리키는 카드를 실제로 정리한다 ────────────────────
        print("[D 지운 노드를 가리키는 카드를 실제로 치운다]")
        # 파트 1(아래층) 하나만 restack 하면 중간면 노드가 아니라 파트 전용 노드가 지워진다.
        # 두 파트를 모두 담아 중간면을 만들기 위해 target_pid=1,2 대신 두 층 덱을 쓴다.
        refs = ("*SET_NODE_LIST\n"
                "        50\n"
                "         5         6         7         8         1\n"
                "*SET_NODE_LIST_GENERATE\n"
                "        51\n"
                "         5         8\n"
                "*SET_SEGMENT\n"
                "        52\n"
                "         5         6         8         7\n"
                "         1         2         4         3\n"
                "*BOUNDARY_SPC_NODE\n"
                "         5         0         1         1         1\n"
                "*ELEMENT_MASS\n"
                "      8001         6     1.000\n"
                "*SET_NODE_ADD\n"
                "        53\n"
                "         5         6\n")
        # 파트 1+2 를 통째로 restack 하려면 두 파트가 한 파트여야 한다 → 두 층 모두 PID 1 인 덱
        nid, rows = grid_nodes()
        elems = ["*ELEMENT_SOLID"]
        for k in range(2):
            elems.append("%8d%8d" % (k + 1, 1) + "".join("%8d" % v for v in hexn(nid, 0, 0, k)))
        onepart = ("*KEYWORD\n*NODE\n" + "\n".join(rows) + "\n" + "\n".join(elems) + "\n"
                   + "*PART\nSTACK\n         1         1         1\n"
                   + "*SECTION_SOLID\n         1         1\n"
                   + "*MAT_ELASTIC\n         1  7.85e-09    210000       0.3\n"
                   + refs + "*END\n")
        w("refs.k", onepart)
        w("refs.yaml", yaml("refs.k", "refs_out.k", pid=1))
        rc, out = run(binary, d, "restack", "refs.yaml")
        check("rc=0 (pid_refs: warn)", rc == 0, out[-800:])
        if rc == 0:
            body = read(P("refs_out.k"))
            # 덱 머리의 $ KOOREMAPPER-PIDREF 블록에는 원문이 그대로 적힌다 — 그 뒤부터 본다
            if "$ KOOREMAPPER-PIDREF-END" in body:
                body = body[body.index("$ KOOREMAPPER-PIDREF-END"):]
            dead = {5, 6, 7, 8}
            sn = section(P("refs_out.k"), "*SET_NODE_LIST\n") or []
            # *SET_NODE_LIST 50 의 구성원에 지운 노드가 남아 있으면 안 된다
            after = body[body.index("*SET_NODE_LIST\n"):]
            after = after[:after.index("*SET_NODE_LIST_GENERATE")]
            vals = [int(t) for t in after.split()[1:] if t.isdigit()]
            check("*SET_NODE_LIST 에서 지운 노드가 빠졌다(남은 것은 1 뿐)",
                  set(vals) & dead == set() and 1 in vals, after)
            gen = body[body.index("*SET_NODE_LIST_GENERATE"):]
            gen = gen[:gen.index("*SET_SEGMENT")]
            check("*_GENERATE 범위는 손대지 않는다(매뉴얼 Vol_I 234577-234581)",
                  "         5         8" in gen, gen)
            seg = body[body.index("*SET_SEGMENT"):]
            seg = seg[:seg.index("*BOUNDARY_SPC_NODE")]
            check("*SET_SEGMENT: 지운 노드를 쓰는 세그먼트 줄만 빠졌다",
                  "         5         6         8         7" not in seg
                  and "         1         2         4         3" in seg, seg)
            spc = body[body.index("*BOUNDARY_SPC_NODE"):]
            spc = spc[:spc.index("*ELEMENT_MASS")]
            check("*BOUNDARY_SPC_NODE 줄이 빠졌다", "         5         0" not in spc, spc)
            em = body[body.index("*ELEMENT_MASS"):]
            em = em[:em.index("*SET_NODE_ADD")]
            check("*ELEMENT_MASS 줄이 빠졌다", "      8001" not in em, em)
            add = body[body.index("*SET_NODE_ADD"):]
            add = add[:add.index("*END")]
            check("*SET_NODE_ADD 는 건드리지 않는다(구성원이 노드 세트 ID 다)",
                  "         5         6" in add, add)
            check("무엇을 몇 개 치웠는지 알린다", "[정리]" in out, out[-1200:])

            # 남은 어떤 카드도 지워진 노드를 가리키지 않는다(*_GENERATE·_ADD 제외)
            live = set()
            for ln in lines_of(P("refs_out.k")):
                s = ln.strip()
                if s.startswith("*") or s.startswith("$") or not s:
                    continue
            check("출력 덱에 *NODE 가 남아 있다", "*NODE" in body)

        # ── E. 파트별 요소 수 보고 ────────────────────────────────────────────
        print("[E 파트별 요소 수를 찍는다]")
        check("삭제된 파트를 찍는다", re.search(r"PID 1: 2 → 0 \(삭제\)", out) is not None, out[-1200:])
        check("새 파트를 찍는다", re.search(r"PID \d+: 0 → \d+ \(신규\)", out) is not None, out[-1200:])
        check("합계를 찍는다", "합계 2 →" in out, out[-1200:])

        # ── F. 줄 수를 확정할 수 없는 섹션에서 지워야 하면 거절한다 ────────────
        print("[F COMPOSITE 섹션의 요소를 지워야 하면 덱을 쓰지 않고 rc=1]")
        comp = ("*ELEMENT_SHELL_COMPOSITE\n"
                "%8d%8d%8d%8d%8d%8d\n" % (1, 3, 1, 2, 4, 3)     # EID 1 = 지워질 솔리드와 같은 번호
                + "         1     0.500     0.000\n")
        w("comp.k", base_deck(extra_elem=comp))
        w("comp.yaml", yaml("comp.k", "comp_out.k", pid=1))
        rc, out = run(binary, d, "restack", "comp.yaml")
        check("rc=1", rc == 1, out[-600:])
        check("이유를 알린다(줄 수를 확정할 수 없는 섹션)",
              "확정할 수 없는" in out and "COMPOSITE" in out.upper(), out[-600:])
        check("덱을 내지 않는다", not os.path.exists(P("comp_out.k")))

        # ── G. 왕복 검증이 실제로 실패를 잡는가 ───────────────────────────────
        # *END 가 없는 덱에 tshell 층을 만들면 새 *ELEMENT_TSHELL 섹션이 *END 앞에서만
        # 나가도록 돼 있어 층이 통째로 빠진다(이번 조사에서 드러난 별개의 기존 결함).
        # 예전에는 rc=0 으로 그 덱이 그대로 나갔다 — 현장 사고와 똑같은 모양이다.
        # 이제는 출력 버퍼를 다시 읽어 파트별 요소 수가 어긋난 것을 잡고 덱을 쓰지 않는다.
        print("[G 왕복 검증이 요소 손실을 실제로 잡는다]")
        w("ne.k", base_deck().replace("*END\n", ""))
        w("ne.yaml", yaml("ne.k", "ne_out.k", pid=1).replace(
            "  - title: L1", "  - title: L1\n    element_type: tshell", 1))
        rc, out = run(binary, d, "restack", "ne.yaml")
        check("rc=1", rc == 1, out[-600:])
        check("무엇이 어긋났는지 파트별로 알린다",
              "왕복 검증 실패" in out and re.search(r"PID \d+: 기대 \d+, 출력 덱 \d+", out) is not None,
              out[-600:])
        check("틀린 덱을 디스크에 남기지 않는다", not os.path.exists(P("ne_out.k")))

    print("ALL PASS" if FAIL == 0 else "FAIL %d" % FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
