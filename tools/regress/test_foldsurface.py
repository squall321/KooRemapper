#!/usr/bin/env python3
# foldsurface 의 elastica 해를 독립 적분·닫힌식과 맞춘다 — 틀린 분기를 집는 것을 막기 위해
"""`foldsurface` 의 수치 계약 (2026-10-02, 현장 보고 §2-2).

왜 이 시험이 있나.

  elastica 는 **다중해다.** 보고의 실측이 그것을 짚었다 — 찬 초기값으로 이분법하면 2.6배 틀린
  분기를 집는다. 그래서 이 시험이 보는 것은 "값이 그럴듯한가" 가 아니라 셋이다.

    ① 원호 한계(α = L/R)는 **닫힌식**과 맞나. 현 = 2R·sin(α/2), 높이 = R(1-cos(α/2)).
    ② 일반해는 **독립 적분**과 맞나. 파이썬이 보고된 B 로 같은 ODE 를 자기 RK4 로 다시 풀어
       곡선을 대조한다.
    ③ 집은 분기가 **첫 분기**인가. 파이썬이 [0, Bmax] 를 따로 훑어 첫 교차를 찾아 비교한다.
       Bmax = κ0²/(2(1-cos(α/2))) — θ 가 α/2 에 닿으려면 되돌이점이 그보다 멀어야 한다.

  상태: (x, y, θ, κ)' = (cosθ, sinθ, κ, -B sinθ), 정점에서 (0, 0, 0, 1/R).

usage: test_foldsurface.py <KooRemapper 바이너리>
"""
import csv
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


def rk4_half(B, k0, L2, n):
    """정점에서 반길이까지 적분한다 — 바이너리와 **독립된** 구현."""
    def f(st):
        x, y, th, k = st
        return (math.cos(th), math.sin(th), k, -B * math.sin(th))

    st = (0.0, 0.0, 0.0, k0)
    h = L2 / n
    for _ in range(n):
        a = f(st)
        s2 = tuple(st[i] + 0.5 * h * a[i] for i in range(4))
        b = f(s2)
        s3 = tuple(st[i] + 0.5 * h * b[i] for i in range(4))
        c = f(s3)
        s4 = tuple(st[i] + h * c[i] for i in range(4))
        e = f(s4)
        st = tuple(st[i] + h / 6.0 * (a[i] + 2 * b[i] + 2 * c[i] + e[i]) for i in range(4))
    return st


def first_branch_B(k0, L2, half, n=4000, steps=4000):
    """[0, Bmax] 를 훑어 **첫** 교차를 찾아 이분법한다 — 분기 선택을 독립으로 재현한다."""
    Bmax = k0 * k0 / (2.0 * (1.0 - math.cos(half)))

    def res(B):
        return rk4_half(B, k0, L2, steps)[2] - half

    r_lo, b_lo = res(0.0), 0.0
    if r_lo <= 0.0:
        return 0.0, Bmax
    b_hi = None
    for i in range(1, n + 1):
        b = Bmax * i / n
        r = res(b)
        if (r_lo > 0) != (r > 0):
            b_hi = b
            break
        b_lo, r_lo = b, r
    if b_hi is None:
        return None, Bmax
    for _ in range(100):
        bm = 0.5 * (b_lo + b_hi)
        if (r_lo > 0) != (res(bm) > 0):
            b_hi = bm
        else:
            b_lo, r_lo = bm, res(bm)
    return 0.5 * (b_lo + b_hi), Bmax


def write_cfg(path, **kw):
    with open(path, "w", newline="\n") as f:
        for k, v in kw.items():
            f.write("%s: %s\n" % (k, v))


def run(binary, cwd, cfg):
    p = subprocess.run([binary, "foldsurface", cfg], capture_output=True, text=True,
                       timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print("usage: test_foldsurface.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="fold_")
    try:
        R, ANG = 3.0, 90.0
        half = math.radians(ANG) / 2.0

        # ── A: 원호 한계(α = L/R) — 닫힌식과 대조 ──
        Lc = R * math.radians(ANG)
        write_cfg(os.path.join(d, "a.yaml"), output="a", arc_length=repr(Lc),
                  fold_angle=ANG, min_radius=R, points=9)
        rc, out = run(binary, d, "a.yaml")
        check("A-1 rc=0", rc == 0, out[-300:])
        check("A-2 원호 한계에서 B=0", near(kv(out, "B (force parameter)"), 0.0, 1e-12),
              kv(out, "B (force parameter)"))
        check("A-3 최소반경 = 목표", near(kv(out, "Achieved min radius"), R, 1e-9),
              kv(out, "Achieved min radius"))
        check("A-4 뒤집힘 0", kv(out, "Curvature sign flips") == "0",
              kv(out, "Curvature sign flips"))
        # 현 = 2R sin(α/2), 높이 = R(1-cos(α/2))
        check("A-5 현 = 2R·sin(α/2) = %.12g" % (2 * R * math.sin(half)),
              near(kv(out, "End separation"), 2 * R * math.sin(half), 1e-9),
              kv(out, "End separation"))
        check("A-6 높이 = R(1-cos(α/2)) = %.12g" % (R * (1 - math.cos(half))),
              near(kv(out, "Apex-to-end height"), R * (1 - math.cos(half)), 1e-9),
              kv(out, "Apex-to-end height"))
        # 굽힘 에너지 = ∫κ²/2 ds = L/(2R²)
        check("A-7 에너지 = L/(2R²) = %.12g" % (Lc / (2 * R * R)),
              near(kv(out, "Bending energy / EI"), Lc / (2 * R * R), 1e-9),
              kv(out, "Bending energy / EI"))

        rows = list(csv.DictReader(open(os.path.join(d, "a_curve.csv"), encoding="utf-8")))
        check("A-8 CSV 9점", len(rows) == 9, len(rows))
        bad = []
        for r in rows:
            s, x, y = float(r["s"]), float(r["x"]), float(r["y"])
            th = math.radians(float(r["theta_deg"]))
            # 정점을 원점·수평으로 둔 반경 R 원호의 닫힌식
            t = (s - Lc / 2.0) / R
            if (abs(x - R * math.sin(t)) > 1e-9 or abs(y - R * (1 - math.cos(t))) > 1e-9
                    or abs(th - t) > 1e-9 or abs(float(r["curvature"]) - 1.0 / R) > 1e-9):
                bad.append(r["s"])
        check("A-9 곡선 전체가 원호 닫힌식과 1e-9 이내", not bad, bad[:3])

        # ── B: 일반해 — 독립 적분과 대조 ──
        Lw = 10.0
        write_cfg(os.path.join(d, "b.yaml"), output="b", arc_length=Lw,
                  fold_angle=ANG, min_radius=R, points=201)
        rc, out = run(binary, d, "b.yaml")
        check("B-1 rc=0", rc == 0, out[-300:])
        Bgot = float(kv(out, "B (force parameter)"))
        Bexp, Bmax = first_branch_B(1.0 / R, Lw / 2.0, half)
        check("B-2 B 가 독립 계산과 일치 (%.12g)" % Bexp, near(Bgot, Bexp, 1e-7),
              "got=%.12g exp=%.12g" % (Bgot, Bexp))
        check("B-3 B 상한 = κ0²/(2(1-cos(α/2))) = %.12g" % Bmax,
              near(kv(out, "B upper bound"), Bmax, 1e-12), kv(out, "B upper bound"))
        check("B-4 끝점 잔차 ≈ 0", abs(float(kv(out, "Turn residual").split()[0])) < 1e-8,
              kv(out, "Turn residual"))
        check("B-5 최소반경 = 목표", near(kv(out, "Achieved min radius"), R, 1e-9),
              kv(out, "Achieved min radius"))
        st = rk4_half(Bgot, 1.0 / R, Lw / 2.0, 40000)
        check("B-6 끝점 x 가 독립 적분과 일치",
              near(float(kv(out, "End separation")) / 2.0, abs(st[0]), 1e-7),
              "%s vs %.12g" % (kv(out, "End separation"), 2 * abs(st[0])))
        check("B-7 끝점 y 가 독립 적분과 일치",
              near(kv(out, "Apex-to-end height"), abs(st[1]), 1e-7),
              "%s vs %.12g" % (kv(out, "Apex-to-end height"), abs(st[1])))

        rows = list(csv.DictReader(open(os.path.join(d, "b_curve.csv"), encoding="utf-8")))
        check("B-8 CSV 201점", len(rows) == 201, len(rows))
        check("B-9 s 가 0 에서 L 까지", near(rows[0]["s"], 0.0, 1e-12)
              and near(rows[-1]["s"], Lw, 1e-9), (rows[0]["s"], rows[-1]["s"]))
        # 폴리라인 길이가 호 길이와 맞나 — s 가 정말 호길이 매개변수인지 본다
        plen = sum(math.hypot(float(rows[i]["x"]) - float(rows[i - 1]["x"]),
                              float(rows[i]["y"]) - float(rows[i - 1]["y"]))
                   for i in range(1, len(rows)))
        check("B-10 폴리라인 길이 ≈ L (%.6g)" % plen, abs(plen - Lw) < 1e-3 * Lw, plen)
        # 대칭성 — 거울 반쪽이 정확히 맞아야 한다
        n = len(rows)
        sym = all(abs(float(rows[i]["x"]) + float(rows[n - 1 - i]["x"])) < 1e-12
                  and abs(float(rows[i]["y"]) - float(rows[n - 1 - i]["y"])) < 1e-12
                  for i in range(n))
        check("B-11 곡선이 정점 기준 대칭", sym)
        # κ 부호 변화 수가 보고된 값과 같나
        flips = sum(1 for i in range(1, n)
                    if (float(rows[i - 1]["curvature"]) > 0) != (float(rows[i]["curvature"]) > 0))
        check("B-12 보고된 뒤집힘 수가 CSV 와 맞는다",
              str(flips) == kv(out, "Curvature sign flips"),
              "csv=%d 보고=%s" % (flips, kv(out, "Curvature sign flips")))
        check("B-13 물결이면 그렇게 경고한다", flips == 0 or "물결" in out,
              [l for l in out.splitlines() if "물결" in l][:1])

        # ── C: 분기 — 더 작은 B 에 해가 없어야 한다(첫 분기를 집었나) ──
        def res(B):
            return rk4_half(B, 1.0 / R, Lw / 2.0, 20000)[2] - half
        grid = [Bgot * i / 400.0 for i in range(1, 400)]
        signs = [res(b) > 0 for b in grid]
        check("C-1 보고된 B 보다 작은 쪽에는 교차가 없다 (첫 분기)",
              all(s == signs[0] for s in signs), "부호가 %d번 바뀐다" % sum(
                  1 for i in range(1, len(signs)) if signs[i] != signs[i - 1]))

        # ── D: 불가능한 입력은 숫자를 내지 않는다 ──
        write_cfg(os.path.join(d, "d.yaml"), output="dd", arc_length=2.0,
                  fold_angle=ANG, min_radius=R)
        rc, out = run(binary, d, "d.yaml")
        check("D-1 길이가 부족하면 rc=1", rc == 1, "rc=%d" % rc)
        check("D-2 필요한 R 과 L 을 알려 준다",
              ("%.12g" % (2.0 / math.radians(ANG))) in out
              and ("%.12g" % (R * math.radians(ANG))) in out, out[-300:])
        check("D-3 CSV 를 쓰지 않는다", not os.path.exists(os.path.join(d, "dd_curve.csv")))

        for key, val in (("fold_angle", 0.0), ("fold_angle", 360.0),
                         ("min_radius", 0.0), ("arc_length", -1.0), ("points", 2)):
            args = dict(output="ee", arc_length=10.0, fold_angle=ANG, min_radius=R)
            args[key] = val
            write_cfg(os.path.join(d, "e.yaml"), **args)
            rc, out = run(binary, d, "e.yaml")
            check("D-4 %s=%s 는 rc=1" % (key, val), rc == 1, out[-200:])
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
