#!/usr/bin/env python3
# refshell 이 만든 기준 셸의 기하·감김·법선을 닫힌식과 맞춘다 — 감김을 구전으로 두지 않기 위해
"""`refshell` 의 기하 계약 (2026-10-02, 현장 보고 §2-3).

왜 이 시험이 있나.

  보고의 수용 기준은 "현 합이 목표 길이와 0.01% 이내 · 종횡비 1:1 · 감김 `(a,d,c,b)` · Y 부호"
  였다. 그중 **감김과 Y 부호는 구전이 되기 쉽다** — "(a,d,c,b) 로 썼다" 는 말은 검사할 수 있지만
  그래서 법선이 어디를 향하는지는 따로 재지 않으면 아무도 모른다. 그래서 이 시험은 감김을
  **격자 공식으로** 확인하고, 그 감김이 내는 **법선 방향을 닫힌식과 대조한다.**

  폭을 +z 로 쓸고 곡선이 x-y 평면에 있으면 `(a,d,c,b)` 의 법선은 `ŵ x û` 다. 직선 곡선
  (û=+x)에서는 정확히 `+y` 여야 한다.

  그리고 만든 덱이 **우리 자신의 검증을 통과하는지** 본다 — `info` 가 셸 야코비안을 두고
  시비 걸지 않아야 하고(§1-7), 미정의 참조가 없어야 한다.

usage: test_refshell.py <KooRemapper 바이너리>
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []


def check(name, cond, detail=""):
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append("%s%s" % (name, ("   " + str(detail).strip()[:300]) if detail else ""))


def near(a, b, tol=1e-9):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return abs(a - b) <= tol * max(1.0, abs(b))


def kv(out, key):
    for line in out.splitlines():
        if line.startswith(key + ":"):
            return line[len(key) + 1:].strip()
    return None


def read_deck(path):
    nodes, elems, kw = {}, [], None
    for ln in open(path, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if ln.startswith("$"):
            continue
        if ln.startswith("*"):
            kw = ln.strip().upper()
            continue
        if kw == "*NODE" and len(ln) >= 56:
            try:
                nodes[int(ln[0:8])] = (float(ln[8:24]), float(ln[24:40]), float(ln[40:56]))
            except ValueError:
                pass
        elif kw == "*ELEMENT_SHELL" and len(ln) >= 48:
            try:
                elems.append([int(ln[i:i + 8]) for i in (0, 8, 16, 24, 32, 40)])
            except ValueError:
                pass
    return nodes, elems


def unit_normal(nodes, e):
    p = [nodes[i] for i in e[2:6]]
    u = [p[1][k] - p[0][k] for k in range(3)]
    v = [p[3][k] - p[0][k] for k in range(3)]
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    m = math.sqrt(sum(x * x for x in n))
    return tuple(x / m for x in n) if m > 0 else (0.0, 0.0, 0.0)


def write_cfg(path, **kw):
    with open(path, "w", newline="\n") as f:
        for k, v in kw.items():
            f.write("%s: %s\n" % (k, v))


def run(binary, cwd, *args):
    p = subprocess.run([binary] + list(args), capture_output=True, text=True, timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print("usage: test_refshell.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="refsh_")
    try:
        # ── A: 직선 곡선 — 기하가 전부 닫힌식이다 ──
        with open(os.path.join(d, "line.csv"), "w", newline="\n") as f:
            f.write("s,x,y\n")
            for i in range(11):
                f.write("%g,%g,%g\n" % (i, i, 0.0))
        write_cfg(os.path.join(d, "a.yaml"), curve="line.csv", output="a.k",
                  width=2.0, thickness=0.05)
        rc, out = run(binary, d, "refshell", "a.yaml")
        check("A-1 rc=0", rc == 0, out[-300:])
        check("A-2 현 합 = 입력 길이 10 (직선이니 정확히)",
              near(kv(out, "Chord sum"), 10.0, 1e-12), kv(out, "Chord sum"))
        check("A-3 종횡비 1:1", near(kv(out, "Aspect ratio"), 1.0, 1e-12),
              kv(out, "Aspect ratio"))
        check("A-4 분할 10 x 2", kv(out, "Divisions (curve x width)") == "10 x 2",
              kv(out, "Divisions (curve x width)"))
        nodes, elems = read_deck(os.path.join(d, "a.k"))
        check("A-5 절점 33 · 요소 20", len(nodes) == 33 and len(elems) == 20,
              (len(nodes), len(elems)))
        # 절점 좌표가 격자 공식 그대로인가
        nw = 2
        bad = []
        for i in range(11):
            for j in range(nw + 1):
                nid = i * (nw + 1) + j + 1
                want = (float(i), 0.0, j * 1.0)
                if nid not in nodes or any(abs(nodes[nid][k] - want[k]) > 1e-9 for k in range(3)):
                    bad.append(nid)
        check("A-6 절점이 격자 공식과 일치", not bad, bad[:5])
        # 감김이 (a, d, c, b) 인가 — 격자 공식으로 직접 확인
        wrong = []
        for idx, e in enumerate(elems):
            i, j = divmod(idx, nw)
            a = i * (nw + 1) + j + 1
            b = (i + 1) * (nw + 1) + j + 1
            cc = (i + 1) * (nw + 1) + j + 2
            dd = i * (nw + 1) + j + 2
            if e[2:6] != [a, dd, cc, b]:
                wrong.append((e[0], e[2:6], [a, dd, cc, b]))
        check("A-7 감김이 (a, d, c, b)", not wrong, wrong[:2])
        # 그 감김의 법선 — 직선(û=+x)·폭(+z)이면 ŵ x û = +y 다
        nz = [unit_normal(nodes, e) for e in elems]
        check("A-8 법선이 정확히 +y (= ŵ x û)",
              all(abs(n[0]) < 1e-12 and abs(n[1] - 1.0) < 1e-12 and abs(n[2]) < 1e-12 for n in nz),
              nz[:2])

        # ── B: 원호 곡선 — 현 합이 호 길이의 0.01% 안이고 모든 절점이 반지름 위에 있다 ──
        R, ANG = 3.0, 90.0
        Lc = R * math.radians(ANG)
        write_cfg(os.path.join(d, "f.yaml"), output="circ", arc_length=repr(Lc),
                  fold_angle=ANG, min_radius=R, points=401)
        rc, out = run(binary, d, "foldsurface", "f.yaml")
        check("B-1 foldsurface rc=0", rc == 0, out[-200:])
        write_cfg(os.path.join(d, "b.yaml"), curve="circ_curve.csv", output="b.k",
                  width=5.0, thickness=0.05, divisions=400)
        rc, out = run(binary, d, "refshell", "b.yaml")
        check("B-2 rc=0", rc == 0, out[-300:])
        dev = abs(float(kv(out, "Length deviation").split()[0]))
        check("B-3 길이 편차 0.01%% 이내 (%.5f%%)" % dev, dev <= 0.01, dev)
        check("B-4 종횡비 1:1", near(kv(out, "Aspect ratio"), 1.0, 1e-3),
              kv(out, "Aspect ratio"))
        check("B-5 길이 편차 경고가 없다", "현 합이" not in out,
              [l for l in out.splitlines() if "현 합" in l][:1])
        nodes, elems = read_deck(os.path.join(d, "b.k"))
        # 정점이 원점·수평인 반경 R 원호 → 중심은 (0, R)
        off = max(abs(math.hypot(p[0], p[1] - R) - R) for p in nodes.values())
        check("B-6 모든 절점이 반지름 %g 위에 있다 (최대 편차 %.3g)" % (R, off), off < 1e-6, off)
        check("B-7 z 가 0..폭 을 채운다",
              near(min(p[2] for p in nodes.values()), 0.0, 1e-12)
              and near(max(p[2] for p in nodes.values()), 5.0, 1e-9))

        # ── C: 만든 덱이 우리 자신의 검증을 통과한다 ──
        rc, out = run(binary, d, "info", "b.k")
        check("C-1 info rc=0", rc == 0, out[-300:])
        check("C-2 info 가 요소 수를 같게 본다", "Elements" in out
              and str(len(elems)) in out, [l for l in out.splitlines() if "Elements" in l][:1])
        check("C-3 셸이라 야코비안을 따지지 않는다 (§1-7)", "해당 없음" in out,
              [l for l in out.splitlines() if "Jacobian" in l or "야코비안" in l][:2])
        # 성공 문구 자체에 "미정의 참조 0건" 이 들어 있다 — 부분문자열로 보면 조용히 틀린다
        check("C-4 참조 무결성 OK 로 끝난다", "참조 무결성 OK" in out,
              [l for l in out.splitlines() if "참조" in l][:2])

        # ── D: 잘못된 입력은 덱을 내지 않는다 ──
        with open(os.path.join(d, "noxy.csv"), "w", newline="\n") as f:
            f.write("s,a,b\n0,1,2\n1,2,3\n")
        cases = [
            ("D-1 x/y 칸이 없으면 rc=1", dict(curve="noxy.csv", output="x1.k", width=2.0, thickness=0.05)),
            ("D-2 없는 CSV 는 rc=1", dict(curve="nope.csv", output="x2.k", width=2.0, thickness=0.05)),
            ("D-3 width<=0 은 rc=1", dict(curve="line.csv", output="x3.k", width=0.0, thickness=0.05)),
            ("D-4 thickness<=0 은 rc=1", dict(curve="line.csv", output="x4.k", width=2.0, thickness=0.0)),
            ("D-5 curve 누락은 rc=1", dict(output="x5.k", width=2.0, thickness=0.05)),
            ("D-6 output 누락은 rc=1", dict(curve="line.csv", width=2.0, thickness=0.05)),
        ]
        for name, args in cases:
            write_cfg(os.path.join(d, "dd.yaml"), **args)
            rc, out = run(binary, d, "refshell", "dd.yaml")
            check(name, rc == 1, out[-200:])
            if "output" in args:
                check(name.split()[0] + " 덱을 쓰지 않는다",
                      not os.path.exists(os.path.join(d, args["output"])))
        # 점이 하나뿐인 CSV
        with open(os.path.join(d, "one.csv"), "w", newline="\n") as f:
            f.write("s,x,y\n0,0,0\n")
        write_cfg(os.path.join(d, "dd.yaml"), curve="one.csv", output="x7.k",
                  width=2.0, thickness=0.05)
        rc, out = run(binary, d, "refshell", "dd.yaml")
        check("D-7 점이 2개 미만이면 rc=1", rc == 1, out[-200:])
    finally:
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
