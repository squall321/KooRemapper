#!/usr/bin/env python3
# 두께 셸(*ELEMENT_TSHELL)뿐인 덱을 unfold 해도 요소마다 두께 방향(n1-4 → n5-8)이 그대로인지 보는 회귀 시험(미룬 결함 3차 2판 L-05)
"""unfold 의 두께 셸 두께 방향 (2026-11-22 · 미룬 결함 3차 2판 L-05 — 11-21 검토의 여섯 가운데 남은 하나).

왜 이 시험이 있나.

  unfold 는 굽은 메시를 (i, j, k) 격자로 읽어 평판을 다시 짓는다 — 요소의 절점 차례도 격자 차례(k 가 두께 축)로 새로 매긴다. 솔리드는
  그래도 같은 요소지만 두께 셸은 n1-4(아랫면) → n5-8(윗면)이 두께 방향이다. 11-22 설치된 판(d1e2ce96)은 두께 방향이 x · y 인 두께 셸
  상자(두께 1.0 · 2.0)를 펼치면 모든 요소의 두께가 0.25(격자 k 축)가 됐고, 48 요소 가운데 입력과 결합이 같은 것이 0 이었다(rc 0).
  이제 입력이 두께 셸이던 요소는 제 절점 차례를 격자로 옮겨 쓴다 — 아랫면 · 윗면 절점이 입력과 같고, 평판에서 뒤집히면 면 안의 감김만
  되돌린다(두께 축은 그대로).

무엇을 보나(상자 · 원호 × 두께 축 z · x · y).
  · rc 0 · 산출이 *ELEMENT_TSHELL · 요소 수가 같다
  · 요소마다 아랫면 절점 네 개 · 윗면 절점 네 개가 입력과 같다(집합)
  · 평판에서 아랫면 법선이 윗면 쪽을 본다(양의 부피)
  · 상자는 요소마다 두께(아랫면 → 윗면 중심 거리)가 입력과 같다
  · 솔리드 덱은 예전 그대로다(같은 상자를 솔리드로 — 산출 바이트가 설치된 판과 같은지는 회귀 묶음이 본다)

usage: test_unfold_tshell_axis.py <KooRemapper 바이너리>
"""
import math
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

FAILS, OKS = [], []
BOX = {o["name"]: o for o in OPS}["warpage"]["files"]["box.yaml"]
# 표준 꼴 육면체(0→1 = 국소 x · 0→3 = y · 0→4 = z)에서 두께 축을 고른 두께 셸 차례 — 아랫면을 그 축의 0 쪽, 윗면을 1 쪽으로
AXIS = {"z": (0, 1, 2, 3, 4, 5, 6, 7), "x": (0, 3, 7, 4, 1, 2, 6, 5), "y": (0, 4, 5, 1, 3, 7, 6, 2)}


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def read(path):
    nodes, elems, kw = {}, {}, ""
    kws = set()
    for line in open(path, encoding="utf-8", errors="replace").read().split("\n"):
        if line.startswith("*"):
            kw = line.split()[0].upper()
            continue
        if not line.strip() or line.startswith("$"):
            continue
        if kw == "*NODE":
            nodes[int(line[0:8])] = (float(line[8:24]), float(line[24:40]), float(line[40:56]))
        elif kw in ("*ELEMENT_SOLID", "*ELEMENT_TSHELL"):
            kws.add(kw)
            v = [int(line[c:c + 8]) for c in range(0, 80, 8)]
            elems[v[0]] = v[2:]
    return nodes, elems, kws


def to_tshell(src, dst, axis):
    out, kw = [], ""
    for line in open(src, encoding="utf-8").read().split("\n"):
        if line.startswith("*"):
            kw = line.split()[0].upper()
            out.append("*ELEMENT_TSHELL" if kw == "*ELEMENT_SOLID" else line)
            continue
        if kw == "*ELEMENT_SOLID" and line.strip() and not line.startswith("$"):
            v = [int(line[c:c + 8]) for c in range(0, 80, 8)]
            n = [v[2 + q] for q in AXIS[axis]]
            line = "".join("%8d" % x for x in v[:2] + n)
        out.append(line)
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def centroid(nodes, ids):
    return [sum(nodes[q][d] for q in ids) / len(ids) for d in range(3)]


def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def orient(nodes, c):
    """아랫면 법선(대각선 곱)과 아랫면 → 윗면 벡터의 안곱 — 양이면 바른 차례."""
    p = [nodes[q] for q in c]
    nrm = cross(sub(p[2], p[0]), sub(p[3], p[1]))
    t = sub(centroid(nodes, c[4:]), centroid(nodes, c[:4]))
    return sum(nrm[d] * t[d] for d in range(3))


def thick(nodes, c):
    return math.dist(centroid(nodes, c[:4]), centroid(nodes, c[4:]))


def main():
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_unftsh_")
    try:
        base = os.path.join(top, "base")
        os.makedirs(base)
        with open(os.path.join(base, "box.yaml"), "w", encoding="utf-8") as f:
            f.write(BOX)
        run(binary, base, "generate", "box", "box.yaml")
        run(binary, base, "generate", "--dim-i", "12", "--dim-j", "3", "arc", "demo")
        for shape, src in (("상자", "box.k"), ("원호", "demo_bent.k")):
            for axis in ("z", "x", "y"):
                d = os.path.join(top, "%s_%s" % (src[:3], axis))
                os.makedirs(d)
                to_tshell(os.path.join(base, src), os.path.join(d, "ts.k"), axis)
                name = "%s · 두께 축 %s" % (shape, axis)
                rc, out = run(binary, d, "unfold", "ts.k", "unf.k")
                if not check(name + " — rc 0", rc == 0 and os.path.exists(os.path.join(d, "unf.k")), out[-300:]):
                    continue
                ni, ei, _ = read(os.path.join(d, "ts.k"))
                no, eo, ko = read(os.path.join(d, "unf.k"))
                check(name + " — 산출이 *ELEMENT_TSHELL · 요소 %d 개" % len(ei), ko == {"*ELEMENT_TSHELL"} and sorted(eo) == sorted(ei),
                      (ko, len(eo)))
                faces = [e for e in ei if e in eo and (set(eo[e][:4]) != set(ei[e][:4]) or set(eo[e][4:]) != set(ei[e][4:]))]
                check(name + " — 요소마다 아랫면 · 윗면 절점이 입력과 같다", not faces, faces[:3])
                bad = [e for e in eo if orient(no, eo[e]) <= 0]
                check(name + " — 평판에서 아랫면 법선이 윗면 쪽(양의 부피)", not bad, bad[:3])
                if shape == "상자":
                    ti = sorted({round(thick(ni, ei[e]), 6) for e in ei})
                    to = sorted({round(thick(no, eo[e]), 6) for e in eo})
                    check(name + " — 요소 두께가 입력과 같다 %s" % ti, ti == to, (ti, to))
    finally:
        shutil.rmtree(top, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL — %d 항 실패 / %d" % (len(FAILS), len(FAILS) + len(OKS)))
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
