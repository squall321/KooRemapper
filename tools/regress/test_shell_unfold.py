#!/usr/bin/env python3
# 평면 셸은 전개가 항등이어야 한다 — 전개 시트가 자기 위로 접히는 것을 막는 관문
"""`shellmap` 전개(ShellUnfolder)의 기하 계약 (2026-10-02).

왜 이 시험이 있나.

  전개가 **조용히 접힌다.** 변 길이는 접혀도 보존되므로 왜곡 지표(max/avg distortion)가 0% 로
  나오고, 그런데도 전개 치수가 실제보다 작아진다. 그러면 `shellmap` 의 bbox 정합이 그 작은
  치수에 디테일을 맞춰 **가짜 변형률**을 남긴다(§1-4 경고가 바로 그 증상이다).

  그래서 이 시험은 이론이 필요 없는 기준을 쓴다.

    ① **평면 셸의 전개는 항등이다.** 굽어 있지 않은 셸을 전개하면 치수가 자기 치수와 같아야
       한다. 격자 크기를 바꿔 가며 전수로 본다 — 실측에서 1/2·1/4·5/8 로 들쭉날쭉했다.
    ② **원통(전개 가능) 셸의 전개는 정확한 직사각형이다.** (호 길이 x 폭).

  둘 다 `shellmap` 이 찍는 `Flat extent X/Y` 로 잰다.

usage: test_shell_unfold.py <KooRemapper 바이너리>
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


def kv(out, key):
    for line in out.splitlines():
        if line.startswith(key + ":"):
            return line[len(key) + 1:].strip()
    return None


def write_cfg(path, **kw):
    with open(path, "w", newline="\n") as f:
        for k, v in kw.items():
            f.write("%s: %s\n" % (k, v))


def run(binary, cwd, *args):
    p = subprocess.run([binary] + list(args), capture_output=True, text=True, timeout=600, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def extents(binary, d, shell, detail):
    """셸을 전개했을 때의 치수 (X, Y) 를 shellmap 출력에서 읽는다."""
    rc, out = run(binary, d, "shellmap", shell, detail, "out.k")
    if rc != 0:
        return None, None, out
    try:
        return float(kv(out, "Flat extent X")), float(kv(out, "Flat extent Y")), out
    except (TypeError, ValueError):
        return None, None, out


def main():
    if len(sys.argv) < 2:
        print("usage: test_shell_unfold.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="unfold_")
    try:
        # 매핑 대상(디테일)은 결과에 영향이 없다 — 전개는 셸만 본다. 가장 단순한 평판을 쓴다.
        write_cfg(os.path.join(d, "box.yaml"), output="flat.k", lx=1.0, ly=1.0, lz=0.1,
                  nx=2, ny=2, nz=1, rho=7.85e-9, E=210000.0, nu=0.3,
                  mid=1, secid=1, pid=1, part_title="DETAIL")
        rc, out = run(binary, d, "generate", "box", "box.yaml")
        check("준비: 디테일 평판 생성", rc == 0, out[-200:])

        # ── A: 평면 셸 — 전개는 항등이어야 한다 ──
        LEN, WID = 4.8, 1.0
        with open(os.path.join(d, "line.csv"), "w", newline="\n") as f:
            f.write("s,x,y\n")
            for i in range(97):
                f.write("%g,%g,0\n" % (i * LEN / 96.0, i * LEN / 96.0))
        for ns, nw in ((96, 1), (96, 2), (96, 4), (96, 8), (96, 16),
                       (2, 2), (4, 4), (8, 3), (16, 5), (3, 7)):
            write_cfg(os.path.join(d, "s.yaml"), curve="line.csv", output="s.k",
                      width=WID, thickness=0.05, divisions=ns, width_divisions=nw)
            rc, out = run(binary, d, "refshell", "s.yaml")
            if rc != 0:
                check("A %dx%d refshell rc=0" % (ns, nw), False, out[-200:])
                continue
            ex, ey, out = extents(binary, d, "s.k", "flat.k")
            # 전개 좌표계는 임의라 두 치수가 (폭, 길이) 또는 (길이, 폭) 로 나온다
            got = sorted([ex, ey]) if ex is not None else None
            want = sorted([WID, LEN])
            ok = got is not None and all(abs(got[i] - want[i]) < 1e-9 * max(1.0, want[i])
                                         for i in range(2))
            check("A %2dx%-2d 평면 셸의 전개 = 자기 치수 (%g x %g)" % (ns, nw, LEN, WID), ok,
                  "got=%s want=%s" % (got, want))

        # ── B: 원통 셸 — 전개는 정확한 직사각형이다 ──
        R, ANG = 3.0, 90.0
        arc = R * math.radians(ANG)
        write_cfg(os.path.join(d, "f.yaml"), output="c", arc_length=repr(arc),
                  fold_angle=ANG, min_radius=R, points=193)
        rc, out = run(binary, d, "foldsurface", "f.yaml")
        check("B-1 foldsurface rc=0", rc == 0, out[-200:])
        for ns, nw in ((192, 4), (96, 8), (48, 16)):
            write_cfg(os.path.join(d, "b.yaml"), curve="c_curve.csv", output="b.k",
                      width=WID, thickness=0.05, divisions=ns, width_divisions=nw)
            rc, out = run(binary, d, "refshell", "b.yaml")
            chord = float(kv(out, "Chord sum"))
            ex, ey, out = extents(binary, d, "b.k", "flat.k")
            got = sorted([ex, ey]) if ex is not None else None
            want = sorted([WID, chord])
            ok = got is not None and all(abs(got[i] - want[i]) < 1e-6 * max(1.0, want[i])
                                         for i in range(2))
            check("B %3dx%-2d 원통 셸의 전개 = 직사각형 (현합 x 폭)" % (ns, nw), ok,
                  "got=%s want=%s" % (got, want))

        # ── C: 치수가 맞으면 §1-4 의 가짜 변형률 경고가 뜨지 않는다 ──
        # 셸의 전개 치수와 **같은 크기**의 평면 디테일을 만들어 넣는다.
        write_cfg(os.path.join(d, "s.yaml"), curve="line.csv", output="s.k",
                  width=WID, thickness=0.05, divisions=96, width_divisions=4)
        run(binary, d, "refshell", "s.yaml")
        write_cfg(os.path.join(d, "det.yaml"), output="det.k", lx=LEN, ly=WID, lz=0.1,
                  nx=24, ny=5, nz=1, rho=7.85e-9, E=210000.0, nu=0.3,
                  mid=1, secid=1, pid=1, part_title="DETAIL")
        rc, out = run(binary, d, "generate", "box", "det.yaml")
        check("C-1 디테일 생성 rc=0", rc == 0, out[-200:])
        rc, out = run(binary, d, "shellmap", "s.k", "det.k", "c_out.k")
        check("C-2 shellmap rc=0", rc == 0, out[-300:])
        warn = [l for l in out.splitlines() if "정합이 디테일을" in l]
        check("C-3 치수가 맞으면 정합 경고가 없다", not warn, warn[:1])
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
