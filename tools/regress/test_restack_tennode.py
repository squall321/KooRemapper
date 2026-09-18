#!/usr/bin/env python3
# 두 줄 포맷 *ELEMENT_SOLID 덱에서 restack 이 요소를 온전히 지우고 새 층을 제 포맷으로 쓰는지 지키는 회귀 시험
"""
배경(현장 KMM 낙하판, 새 층 요소 37,100 개 손실):
  - *ELEMENT_SOLID (ten nodes format) 은 한 요소가 두 줄이다(1줄 'eid pid', 2줄 노드).
    restack 이 대상 파트 요소를 지울 때 'eid pid' 줄만 지워 노드 줄이 고아로 남았다.
    두 줄로 읽는 쪽은 그 노드 줄을 다음 요소의 'eid pid' 로 읽어 덱 전체가 밀린다(#1).
  - 같은 이유로 노드 줄의 첫 칸(노드 ID)이 지워진 요소 번호와 우연히 같으면
    멀쩡한 요소의 노드 줄이 사라졌다.
  - 새 층 요소는 두 줄 포맷 섹션 안에 한 줄 포맷으로 적혔다 — 두 줄로 읽는 쪽이
    한 요소의 절반을 노드 줄로 읽어 요소가 통째로 사라진다(#2).
  - *ELEMENT_TSHELL 섹션은 출력 필터에서 어느 섹션도 아니어서 지운 요소가 그대로 남았다.
  - 새 층 PID 는 언제나 '모델 최대 PID + 1' 이라 사내 ID 관례(예약 대역)와 부딪혔다(#4).

사용: python3 tools/regress/test_restack_tennode.py <KooRemapper 바이너리>
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
    return open(path, encoding="utf-8", errors="replace").read().splitlines()


def element_sections(path, keyword="*ELEMENT_SOLID"):
    """(키워드 줄, 데이터 줄 목록) 목록 — 주석·빈 줄은 뺀다"""
    out = []
    cur = None
    for ln in read(path):
        s = ln.strip()
        if s.startswith("*"):
            if s.upper().startswith(keyword):
                cur = (s, [])
                out.append(cur)
            else:
                cur = None
            continue
        if cur is None or not s or s.startswith("$"):
            continue
        cur[1].append(ln)
    return out


def fixed_width_eid(line, fw=8):
    """리더처럼 고정폭 한 줄 포맷을 먼저 시도한다 — 8자리 노드 ID 는 칸이 붙어 2 토큰으로 보인다.
    한 줄 포맷 요소면 eid, 아니면 None."""
    if len(line) < fw * 10:
        return None
    try:
        eid = int(line[0:fw])
        n1 = int(line[fw * 2:fw * 3])
    except ValueError:
        return None
    return eid if eid > 0 and n1 > 0 else None


def parse_elements(data_lines):
    """리더와 같은 규칙으로 요소를 읽는다 — 고정폭 한 줄 / 자유 포맷 한 줄(10칸 이상) /
    두 줄 포맷(2~3칸 + 노드 줄). 구조가 깨졌으면 예외를 던진다."""
    eids = []
    i = 0
    while i < len(data_lines):
        packed = fixed_width_eid(data_lines[i])
        if packed is not None:
            eids.append(packed)
            i += 1
            continue
        toks = data_lines[i].split()
        if len(toks) >= 10:
            eids.append(int(toks[0]))
            i += 1
        elif 2 <= len(toks) <= 3:
            if i + 1 >= len(data_lines):
                raise ValueError("두 줄 포맷 헤더 뒤에 노드 줄이 없다: " + data_lines[i])
            nodes = data_lines[i + 1].split()
            if len(nodes) < 8:
                raise ValueError("노드 줄이 아니다: " + data_lines[i + 1])
            eids.append(int(toks[0]))
            i += 2
        else:
            raise ValueError("요소 줄로 읽을 수 없다: " + data_lines[i])
    return eids


def info_counts(binary, cwd, deck):
    rc, out = run(binary, cwd, "info", deck)
    n = re.search(r"^Nodes:\s+(\d+)", out, re.M)
    e = re.search(r"^Elements:\s+(\d+)", out, re.M)
    return rc, (int(n.group(1)) if n else -1), (int(e.group(1)) if e else -1), out


NODES = "\n".join(
    "%8d %15.6f %15.6f %15.6f       0       0" % (1000 + i, x, y, z)
    for i, (x, y, z) in enumerate(
        [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),
         (0, 0, 5), (10, 0, 5), (10, 10, 5), (0, 10, 5),
         (0, 0, 5), (10, 0, 5), (10, 10, 5), (0, 10, 5),
         (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10)], start=1)
)

TAIL = """*PART
LOWER
         1         1         1
*PART
UPPER
         2         1         1
*SECTION_SOLID
         1         1
*MAT_ELASTIC
         1  7.85e-09    210000       0.3
*END
"""


def deck(element_block):
    return "*KEYWORD\n*TITLE\nten node format test\n*NODE\n" + NODES + "\n" + element_block + TAIL


def packed_deck():
    """8자리 노드 ID(10000001~) 3x2x3 격자 — 한 줄 포맷이지만 pid 칸과 n1 칸이 붙는다.
    PID 1 과 PID 2 요소를 번갈아 놓아 오판이 어느 쪽으로 새든 드러나게 한다."""
    nid = {}
    nodes = []
    n = 10000001
    for k, z in enumerate([0.0, 2.0, 4.0]):
        for j, y in enumerate([0.0, 10.0]):
            for i, x in enumerate([0.0, 10.0, 20.0]):
                nid[(i, j, k)] = n
                nodes.append((n, x, y, z))
                n += 1

    def hexn(i, j, k):
        return [nid[(i, j, k)], nid[(i + 1, j, k)], nid[(i + 1, j + 1, k)], nid[(i, j + 1, k)],
                nid[(i, j, k + 1)], nid[(i + 1, j, k + 1)], nid[(i + 1, j + 1, k + 1)], nid[(i, j + 1, k + 1)]]

    lines = ["*ELEMENT_SOLID"]
    eid = 5001
    for k in range(2):
        for col, pid in ((0, 1), (1, 2)):
            lines.append("%8d%8d" % (eid, pid) + "".join("%8d" % v for v in hexn(col, 0, k)))
            eid += 1
    return ("*KEYWORD\n*NODE\n"
            + "\n".join("%8d%16.6f%16.6f%16.6f" % v for v in nodes) + "\n"
            + "\n".join(lines) + "\n" + TAIL)


LAYERS = """layers:
  - title: L1
    thickness: 2.5
    num_elements: 1
{pid1}    material_card: |
      *MAT_ELASTIC_TITLE
      L1
      $#     mid        ro         e        pr
              90  7.85e-09   2.1e+05      0.30
  - title: L2
    thickness: 2.5
    num_elements: 1
{pid2}    material_card: |
      *MAT_ELASTIC_TITLE
      L2
      $#     mid        ro         e        pr
              91  2.70e-09   7.0e+04      0.33
"""


def yaml(model, output, extra="", pid1="", pid2=""):
    return ("model: %s\noutput: %s\ntarget_pid: 1\ndirection: z\npid_refs: warn\n%s" % (model, output, extra)
            + LAYERS.format(pid1=("    pid: %d\n" % pid1) if pid1 else "",
                            pid2=("    pid: %d\n" % pid2) if pid2 else ""))


def main():
    if len(sys.argv) < 2:
        print("usage: test_restack_tennode.py <KooRemapper>")
        return 2
    binary = os.path.abspath(sys.argv[1])

    with tempfile.TemporaryDirectory() as d:
        two_line = """*ELEMENT_SOLID (ten nodes format)
    5001       1
    1001    1002    1003    1004    1005    1006    1007    1008       0       0
    5002       2
    1009    1010    1011    1012    1013    1014    1015    1016       0       0
"""
        open(os.path.join(d, "two.k"), "w").write(deck(two_line))
        open(os.path.join(d, "two.yaml"), "w").write(yaml("two.k", "two_out.k"))

        print("[A 두 줄 포맷 — 지운 요소의 노드 줄이 남지 않는다]")
        rc, out = run(binary, d, "restack", "two.yaml")
        check("rc=0", rc == 0, out[-400:])
        secs = element_sections(os.path.join(d, "two_out.k"))
        orig = [s for s in secs if "TEN NODE" in s[0].upper()]
        check("원래 두 줄 포맷 섹션이 그대로 있다", len(orig) == 1, str([s[0] for s in secs]))
        if orig:
            check("남은 요소는 5002 하나이고 그 두 줄이 온전하다",
                  orig[0][1] == ["    5002       2",
                                 "    1009    1010    1011    1012    1013    1014    1015    1016       0       0"],
                  str(orig[0][1]))

        print("[B 새 층 요소는 그 섹션 포맷과 섞이지 않는다]")
        newsecs = [s for s in secs if "TEN NODE" not in s[0].upper()]
        check("새 층 요소는 표준 *ELEMENT_SOLID 섹션을 따로 연다", len(newsecs) == 1, str([s[0] for s in secs]))
        if newsecs:
            check("그 섹션 줄은 한 줄 포맷(10칸 이상)이다",
                  all(len(ln.split()) >= 10 for ln in newsecs[0][1]), str(newsecs[0][1]))
            check("새 요소 2 개", len(newsecs[0][1]) == 2, str(newsecs[0][1]))
        for kw, data in secs:
            try:
                parse_elements(data)
            except ValueError as e:
                check("섹션 '%s' 이 두 줄 리더로 읽힌다" % kw, False, str(e))

        print("[C 출력 덱을 다시 읽으면 요소 수가 맞는다(왕복)]")
        rc, n, e, out = info_counts(binary, d, "two_out.k")
        check("rc=0", rc == 0, out[-300:])
        check("요소 3 개(남은 1 + 새 층 2)", e == 3, "elements=%d" % e)
        check("노드 20 개(원 16 + 중간면 4)", n == 20, "nodes=%d" % n)

        print("[D 노드 ID 가 지워진 요소 번호와 같아도 멀쩡한 요소가 살아남는다]")
        collide = """*ELEMENT_SOLID (ten nodes format)
    1009       1
    1001    1002    1003    1004    1005    1006    1007    1008       0       0
    5002       2
    1009    1010    1011    1012    1013    1014    1015    1016       0       0
"""
        open(os.path.join(d, "col.k"), "w").write(deck(collide))
        open(os.path.join(d, "col.yaml"), "w").write(yaml("col.k", "col_out.k"))
        rc, out = run(binary, d, "restack", "col.yaml")
        check("rc=0", rc == 0, out[-400:])
        csecs = element_sections(os.path.join(d, "col_out.k"))
        ckept = [s for s in csecs if "TEN NODE" in s[0].upper()]
        check("5002 의 노드 줄이 지워지지 않았다",
              bool(ckept) and ckept[0][1] == [
                  "    5002       2",
                  "    1009    1010    1011    1012    1013    1014    1015    1016       0       0"],
              str(ckept[0][1]) if ckept else str(csecs))
        rc2, n2, e2, out2 = info_counts(binary, d, "col_out.k")
        check("요소 3 개", e2 == 3, "elements=%d" % e2)

        print("[E 한 줄 포맷 덱은 예전과 같은 결과다]")
        one_line = """*ELEMENT_SOLID
    5001       1    1001    1002    1003    1004    1005    1006    1007    1008
    5002       2    1009    1010    1011    1012    1013    1014    1015    1016
"""
        open(os.path.join(d, "one.k"), "w").write(deck(one_line))
        open(os.path.join(d, "one.yaml"), "w").write(yaml("one.k", "one_out.k"))
        rc, out = run(binary, d, "restack", "one.yaml")
        check("rc=0", rc == 0, out[-400:])
        osecs = element_sections(os.path.join(d, "one_out.k"))
        check("섹션을 새로 열지 않는다(*ELEMENT_SOLID 하나)", len(osecs) == 1, str([s[0] for s in osecs]))
        if osecs:
            check("남은 요소 뒤에 새 층 요소가 한 줄씩 붙는다",
                  parse_elements(osecs[0][1])[0] == 5002 and len(osecs[0][1]) == 3, str(osecs[0][1]))
        rc3, n3, e3, out3 = info_counts(binary, d, "one_out.k")
        check("요소 3 개", e3 == 3, "elements=%d" % e3)

        print("[F 섞인 섹션 — 두 줄 요소와 한 줄 요소가 같은 섹션에 있어도 안전하다]")
        mixed = """*ELEMENT_SOLID (ten nodes format)
    5001       1
    1001    1002    1003    1004    1005    1006    1007    1008       0       0
    5002       2    1009    1010    1011    1012    1013    1014    1015    1016
"""
        open(os.path.join(d, "mix.k"), "w").write(deck(mixed))
        open(os.path.join(d, "mix.yaml"), "w").write(yaml("mix.k", "mix_out.k"))
        rc, out = run(binary, d, "restack", "mix.yaml")
        check("rc=0", rc == 0, out[-400:])
        msecs = element_sections(os.path.join(d, "mix_out.k"))
        kept = [s for s in msecs if "TEN NODE" in s[0].upper()]
        check("한 줄 요소 5002 만 남는다",
              bool(kept) and parse_elements(kept[0][1]) == [5002], str(kept[0][1]) if kept else str(msecs))
        rc4, n4, e4, out4 = info_counts(binary, d, "mix_out.k")
        check("요소 3 개", e4 == 3, "elements=%d" % e4)

        print("[G *ELEMENT_TSHELL 섹션의 대상 요소도 지운다]")
        tshell = """*ELEMENT_TSHELL
    5001       1    1001    1002    1003    1004    1005    1006    1007    1008
    5002       2    1009    1010    1011    1012    1013    1014    1015    1016
"""
        open(os.path.join(d, "ts.k"), "w").write(deck(tshell))
        open(os.path.join(d, "ts.yaml"), "w").write(yaml("ts.k", "ts_out.k"))
        rc, out = run(binary, d, "restack", "ts.yaml")
        check("rc=0", rc == 0, out[-400:])
        tsec = element_sections(os.path.join(d, "ts_out.k"), "*ELEMENT_TSHELL")
        check("대상 파트 요소 5001 이 남지 않는다",
              bool(tsec) and parse_elements(tsec[0][1]) == [5002], str(tsec))
        rc5, n5, e5, out5 = info_counts(binary, d, "ts_out.k")
        check("요소 3 개", e5 == 3, "elements=%d" % e5)

        print("[H 층 PID 지정 — 반영되고, 이미 쓰는 번호면 rc=1]")
        open(os.path.join(d, "pid.yaml"), "w").write(yaml("two.k", "pid_out.k", pid1=701, pid2=702))
        rc, out = run(binary, d, "restack", "pid.yaml")
        check("rc=0", rc == 0, out[-400:])
        pids = [int(ln.split()[1]) for ln in
                (element_sections(os.path.join(d, "pid_out.k"))[-1][1] if
                 element_sections(os.path.join(d, "pid_out.k")) else [])]
        check("새 요소가 지정 PID 를 쓴다", pids == [701, 702], str(pids))
        parts = [ln for ln in read(os.path.join(d, "pid_out.k"))]
        check("*PART 카드에 701·702 가 있다",
              any(ln.split()[:1] == ["701"] for ln in parts if ln.split()) and
              any(ln.split()[:1] == ["702"] for ln in parts if ln.split()))

        open(os.path.join(d, "conf.yaml"), "w").write(yaml("two.k", "conf_out.k", pid1=2))
        rc, out = run(binary, d, "restack", "conf.yaml")
        check("이미 쓰는 PID 는 rc=1", rc == 1, out[-400:])
        check("무엇이 겹쳤는지 알린다", "already used by this model" in out, out[-400:])
        check("덱을 쓰지 않는다", not os.path.exists(os.path.join(d, "conf_out.k")))

        open(os.path.join(d, "start.yaml"), "w").write(yaml("two.k", "start_out.k", extra="pid_start: 900\n"))
        rc, out = run(binary, d, "restack", "start.yaml")
        check("pid_start rc=0", rc == 0, out[-400:])
        spids = [int(ln.split()[1]) for ln in element_sections(os.path.join(d, "start_out.k"))[-1][1]]
        check("자동 PID 가 pid_start 부터다", spids == [900, 901], str(spids))

        print("[I assemble 도 같은 결과를 낸다]")
        asm = ("base_model: two.k\noutput: asm_out.k\noperations:\n  - type: restack\n"
               "    target_pid: 1\n    direction: z\n    pid_refs: warn\n    pid_start: 900\n    "
               + LAYERS.format(pid1="", pid2="").replace("\n", "\n    ").rstrip() + "\n")
        open(os.path.join(d, "asm.yaml"), "w").write(asm)
        rc, out = run(binary, d, "assemble", "asm.yaml")
        check("rc=0", rc == 0, out[-600:])
        if rc == 0:
            a = [ln for ln in read(os.path.join(d, "asm_out.k")) if not ln.startswith("$ KOOREMAPPER")]
            b = [ln for ln in read(os.path.join(d, "start_out.k")) if not ln.startswith("$ KOOREMAPPER")]
            check("단독 restack 과 같은 덱", a == b,
                  "\n".join(x for x in a if x not in b)[:300])

        print("[J 8자리 노드 ID — 칸이 붙어 2 토큰으로 보여도 한 줄 포맷으로 읽는다]")
        # pid 칸과 n1 칸 사이에 공백이 없어 토큰 수만 보면 '두 줄 헤더' 로 오판된다.
        # 대상 파트는 남겨야 할 다음 요소를 노드 줄로 버리고, 비대상 파트는 지워야 할
        # 다음 요소를 그대로 내보낸다 — 양쪽 다 조용히 틀린 덱이 나간다.
        open(os.path.join(d, "pk.k"), "w").write(packed_deck())
        for tag, target, kept in (("a", 1, [5002, 5004]), ("b", 2, [5001, 5003])):
            open(os.path.join(d, "pk%s.yaml" % tag), "w").write(
                yaml("pk.k", "pk%s_out.k" % tag).replace("target_pid: 1", "target_pid: %d" % target))
            rc, out = run(binary, d, "restack", "pk%s.yaml" % tag)
            check("대상 %d rc=0" % target, rc == 0, out[-400:])
            psecs = element_sections(os.path.join(d, "pk%s_out.k" % tag))
            check("대상 %d 섹션을 새로 열지 않는다" % target, len(psecs) == 1, str([s[0] for s in psecs]))
            if psecs:
                check("대상 %d 비대상 파트 요소가 남고 대상 요소만 새 층으로 바뀐다" % target,
                      parse_elements(psecs[0][1]) == kept + [5005, 5006], str(psecs[0][1]))
            rc, n, e, out = info_counts(binary, d, "pk%s_out.k" % tag)
            check("대상 %d 요소 4 개(남은 2 + 새 층 2)" % target, e == 4, "elements=%d" % e)

        print("[K element_type: tshell 층 — 베이스 *ELEMENT_SOLID 섹션이 있어도 나간다]")
        # *ELEMENT_SOLID 섹션 끝에서 솔리드만 쓰고 '다 썼다' 고 표시해 *END 앞의
        # *ELEMENT_TSHELL 폴백이 영영 실행되지 않았다 — rc=0 인데 요소 0 개짜리 덱.
        open(os.path.join(d, "tl.yaml"), "w").write(
            yaml("one.k", "tl_out.k").replace("    num_elements: 1\n",
                                              "    num_elements: 1\n    element_type: tshell\n"))
        rc, out = run(binary, d, "restack", "tl.yaml")
        check("rc=0", rc == 0, out[-400:])
        tlsec = element_sections(os.path.join(d, "tl_out.k"), "*ELEMENT_TSHELL")
        check("새 층이 *ELEMENT_TSHELL 섹션으로 나간다", len(tlsec) == 1, str(tlsec))
        if tlsec:
            check("새 tshell 요소 2 개", len(parse_elements(tlsec[0][1])) == 2, str(tlsec[0][1]))
        ksol = element_sections(os.path.join(d, "tl_out.k"))
        check("솔리드 섹션에는 비대상 요소 5002 만 남는다",
              bool(ksol) and parse_elements(ksol[0][1]) == [5002], str(ksol))
        rc, n, e, out = info_counts(binary, d, "tl_out.k")
        check("요소 3 개(남은 1 + 새 층 2)", e == 3, "elements=%d" % e)

    print("FAIL %d" % FAIL if FAIL else "ALL PASS")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
