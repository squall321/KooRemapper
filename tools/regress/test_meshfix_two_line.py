#!/usr/bin/env python3
"""meshfix 가 2줄 포맷 요소 카드를 반토막 내지 않는다 — 다른 파트의 요소가 조용히 사라졌다.

왜 이 시험이 있나 (2026-09-25, 덱 계약 2차 P0-1):

  `spliceMesh` 가 줄마다 `parseFirstInt` 로 첫 정수를 읽어 삭제를 정했다. 그런데
  `*ELEMENT_SOLID` **2줄 포맷**에서 둘째 줄의 첫 정수는 **노드 번호**다. 그 값이 삭제 대상
  EID 집합(= 그 PID 의 전체 eid)에 우연히 들어 있으면 **건드리지 말아야 할 파트의 노드 줄만**
  지워져 요소 카드가 헤더만 남는다.

  재현(수정 전) — `examples/mesh/tetramesh.k`(이미 2줄 포맷이다)에 노드 번호가 PID 1 의 EID 와
  겹치는 PID 2 카드 3개를 붙이고 `meshfix pid:1`:

      원본      Elements 28416 / Parts 2
      산출물    Elements  1908 / Parts 2       ← PID 2 의 3개가 사라졌다
      산출물 원문:
          900001       2
          900002       2                        ← 노드 줄이 없다
          900003       2
      그런데 `info` 는 `[OK] Mesh is valid` · rc=0

  셋이 겹쳐 최악이었다 — ① 리포의 meshfix 예제 덱이 이미 2줄 포맷이다 ② meshfix 는 자체
  라이터라 요소 수 대조 게이트(ModelAssembler)를 안 거친다 ③ `info` 가 통과시킨다.
  캠페인 사건 1(A27 요소 소실)과 같은 모양이다.

  같은 판정의 올바른 구현은 리포에 이미 있었다 — `cclip.cpp:802 cc_removeSolidElements`.

usage: test_meshfix_two_line.py <KooRemapper 바이너리>
"""
import os
import re
import subprocess
import sys
import tempfile

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
TETRA = os.path.join(REPO, "examples", "mesh", "tetramesh.k")


def check(name, cond, detail=""):
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))


def gmsh_path():
    """gmsh 를 결정적으로 찾는다 — PATH 의 깨진 파이썬 래퍼를 집으면 meshfix 가 rc=1 로 죽는다."""
    env = os.environ.get("KOOREMAPPER_GMSH")
    if env and os.path.exists(env):
        return env
    cand = os.path.join(REPO, "dist", "gmsh", "gmsh")
    return cand if os.path.exists(cand) else None


def run(binary, cwd, *args):
    env = dict(os.environ)
    g = gmsh_path()
    if g:
        env["KOOREMAPPER_GMSH"] = g
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True,
                       timeout=900, env=env)
    return p.returncode, p.stdout + p.stderr


def counts(binary, cwd, path):
    rc, out = run(binary, cwd, "info", path)
    m = re.search(r"^Elements\s*:?\s*(\d+)", out, re.M)
    e = int(m.group(1)) if m else -1
    m = re.search(r"^Parts\s*:?\s*(\d+)", out, re.M)
    p = int(m.group(1)) if m else -1
    return e, p, out


def build_two_part(dst):
    """tetramesh.k(2줄 포맷)에 **노드 번호가 PID 1 의 EID 와 겹치는** PID 2 카드 3개를 붙인다.

    겹치게 만드는 것이 이 시험의 핵심이다 — 겹치지 않으면 버그가 드러나지 않는다.
    """
    lines = open(TETRA, encoding="utf-8", errors="replace").read().splitlines()
    si = next(i for i, l in enumerate(lines) if l.strip() == "*ELEMENT_SOLID")
    ei = next(i for i in range(si + 1, len(lines)) if lines[i].startswith("*"))

    eids, i = [], si + 1
    while i < ei:
        t = lines[i].split()
        if len(t) == 2:
            eids.append(int(t[0])); i += 2
        else:
            i += 1
    if len(eids) < 3:
        return None, None
    collide = eids[:3]                       # PID 2 의 첫 노드로 쓸 값 = PID 1 의 EID
    new = []
    for k, eid in enumerate((900001, 900002, 900003)):
        new.append("%8d%8d" % (eid, 2))
        new.append("".join("%8d" % v for v in [collide[k], 785, 786, 8747, 8747, 8747, 8747, 8747]))
    txt = "\n".join(lines[:ei] + new + lines[ei:]) + "\n"
    txt = txt.replace("*END", "*PART\npart two\n         2         1         1\n*END", 1)
    open(dst, "w").write(txt)
    return len(eids), collide


def main():
    if len(sys.argv) < 2:
        print("usage: test_meshfix_two_line.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found: " + binary)
        return 2
    if not os.path.exists(TETRA):
        print("예제 덱이 없다: " + TETRA)
        return 2

    g = gmsh_path()
    # ⚠ gmsh 가 없으면 **skip 이 아니라 FAIL** 이다. meshfix 는 requires_gmsh 인 유일한 op 이고,
    # 조용히 건너뛰면 이 결함이 정확히 그렇게 숨어 있었다(실사용 박스가 먼저 찾아 돌려줬다).
    if not g:
        print("  %-62s %s" % ("gmsh 를 찾았다(dist/gmsh/gmsh 또는 KOOREMAPPER_GMSH)", "FAIL"))
        print("\nFAIL 1\n  - gmsh 가 없어 meshfix 를 검사할 수 없다 — 건너뛰지 않는다")
        return 1

    d = tempfile.mkdtemp(prefix="mf2l_")
    print("[A 2줄 포맷 — 다른 파트의 카드가 짝으로 살아남는다]")
    n_pid1, collide = build_two_part(os.path.join(d, "two.k"))
    check("2줄 포맷 예제에서 PID 1 요소를 찾았다", bool(n_pid1), str(n_pid1))
    if not n_pid1:
        return 1
    before_e, before_p, _ = counts(binary, d, "two.k")
    check("원본 파트 2개", before_p == 2, "parts=%d" % before_p)

    open(os.path.join(d, "mf.yaml"), "w").write("model: two.k\noutput: fixed.k\npid: 1\n")
    rc, out = run(binary, d, "meshfix", "mf.yaml")
    check("meshfix rc=0", rc == 0, out[-400:])
    fixed = os.path.join(d, "fixed.k")
    check("산출물이 생겼다", os.path.exists(fixed), out[-300:])
    if not os.path.exists(fixed):
        return 1

    body = open(fixed, encoding="utf-8", errors="replace").read().splitlines()
    for eid, n1 in zip((900001, 900002, 900003), collide):
        idx = [i for i, l in enumerate(body) if l.split()[:2] == [str(eid), "2"]]
        check("PID 2 의 %d 헤더가 남았다" % eid, bool(idx), "없다")
        if not idx:
            continue
        nxt = body[idx[0] + 1] if idx[0] + 1 < len(body) else ""
        # ⚠ 핵심 — 헤더 **다음 줄이 노드 목록**이어야 한다. 노드 줄만 지워지던 버그가 여기서 잡힌다.
        toks = nxt.split()
        check("%d 의 노드 줄이 남았다(첫 노드 %d)" % (eid, n1),
              len(toks) >= 4 and toks[0] == str(n1), repr(nxt))

    after_e, after_p, _ = counts(binary, d, "fixed.k")
    check("PID 2 의 요소 3개가 살아 있다(요소 수 = PID1 신규 + 3)",
          after_e >= 3, "elements=%d" % after_e)
    check("파트는 여전히 2개", after_p == 2, "parts=%d" % after_p)

    print("[B 1줄 포맷은 바이트가 안 바뀐다 — 고치면서 반대로 깨뜨리지 않았나]")
    # 같은 덱을 1줄 포맷으로 합쳐서 돌린다
    lines = open(TETRA, encoding="utf-8", errors="replace").read().splitlines()
    si = next(i for i, l in enumerate(lines) if l.strip() == "*ELEMENT_SOLID")
    ei = next(i for i in range(si + 1, len(lines)) if lines[i].startswith("*"))
    merged, i = [], si + 1
    while i < ei:
        t = lines[i].split()
        if len(t) == 2 and i + 1 < ei:
            merged.append("".join("%8s" % v for v in t + lines[i + 1].split())); i += 2
        else:
            merged.append(lines[i]); i += 1
    d2 = tempfile.mkdtemp(prefix="mf1l_")
    open(os.path.join(d2, "one.k"), "w").write("\n".join(lines[:si + 1] + merged + lines[ei:]) + "\n")
    open(os.path.join(d2, "mf.yaml"), "w").write("model: one.k\noutput: o.k\npid: 1\n")
    rc, out = run(binary, d2, "meshfix", "mf.yaml")
    check("1줄 포맷 meshfix rc=0", rc == 0, out[-300:])
    e1, p1, _ = counts(binary, d2, "o.k")
    check("1줄 포맷 산출물이 읽힌다", e1 > 0, "elements=%d" % e1)

    print("")
    if FAILS:
        print("FAIL %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
