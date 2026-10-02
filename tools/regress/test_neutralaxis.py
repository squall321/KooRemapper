#!/usr/bin/env python3
# neutralaxis 의 EI 가중 중립축을 닫힌식 손계산과 맞춘다 — 적층 가중을 조용히 틀리지 않기 위해
"""`neutralaxis` 의 수치 계약 (2026-10-02, 현장 보고 §2-7).

왜 이 시험이 있나.

  중립축은 **조용히 틀린다.** 두께를 셸 절점 범위(=0)에서 읽거나, 가중을 두께만으로 하거나,
  E 를 못 읽은 파트를 0 으로 쓰면 숫자는 그럴듯하게 나오고 아무도 못 알아챈다. 그래서 이 시험은
  메시를 한 번도 거치지 않는 **닫힌식**을 기준으로 쓴다.

      z_n = Σ Eᵢ tᵢ zᵢ / Σ Eᵢ tᵢ        D = Σ Eᵢ(tᵢ³/12 + tᵢ(zᵢ - z_n)²)

  파이썬 쪽은 층 목록에서 바로 저 식을 계산한다. C++ 쪽은 덱을 읽고 파트를 모아 두께를 재서
  계산한다. 두 경로가 1e-9 이내로 같아야 한다.

  §1-6(shellmap 의 z=0 전제)과 맞물린다 — 이 op 의 오프셋이 그 전제를 재는 자다.

usage: test_neutralaxis.py <KooRemapper 바이너리>
"""
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


def near(a, b, rel=1e-9):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if b == 0:
        return abs(a) < rel
    return abs(a - b) / abs(b) < rel


def closed_form(layers):
    """층 목록 [(t, z, E)] 에서 중립축과 굽힘강성을 닫힌식으로 구한다."""
    sum_et = sum(E * t for t, z, E in layers)
    sum_etz = sum(E * t * z for t, z, E in layers)
    sum_t = sum(t for t, z, E in layers)
    sum_tz = sum(t * z for t, z, E in layers)
    zn = sum_etz / sum_et
    D = sum(E * (t ** 3 / 12.0 + t * (z - zn) ** 2) for t, z, E in layers)
    return {"zn": zn, "zgeom": sum_tz / sum_t, "sum_et": sum_et, "sum_t": sum_t, "D": D}


def kv(out, key):
    """`Key:        value` 에서 value 를 꺼낸다."""
    for line in out.splitlines():
        if line.startswith(key + ":"):
            return line[len(key) + 1:].strip()
    return None


def solid_stack_deck(path, stack, axis="z"):
    """stack = [(두께, E, PID)] 를 축 방향으로 쌓은 hex8 덱. 1 요소/층."""
    nid = 1
    nodes, planes = [], []
    pos = 0.0
    bounds = [0.0]
    for t, E, pid in stack:
        pos += t
        bounds.append(pos)

    def coord(i, j, a):
        """축이 axis 인 좌표 3개를 만든다."""
        if axis == "x":
            return (a, i * 1.0, j * 1.0)
        if axis == "y":
            return (i * 1.0, a, j * 1.0)
        return (i * 1.0, j * 1.0, a)

    for a in bounds:
        plane = {}
        for j in (0, 1):
            for i in (0, 1):
                x, y, z = coord(i, j, a)
                nodes.append((nid, x, y, z))
                plane[(i, j)] = nid
                nid += 1
        planes.append(plane)

    L = ["*KEYWORD", "*NODE"]
    for i, x, y, z in nodes:
        L.append("%8d%16.9f%16.9f%16.9f" % (i, x, y, z))
    L.append("*ELEMENT_SOLID")
    for k, (t, E, pid) in enumerate(stack):
        lo, hi = planes[k], planes[k + 1]
        c = [lo[(0, 0)], lo[(1, 0)], lo[(1, 1)], lo[(0, 1)],
             hi[(0, 0)], hi[(1, 0)], hi[(1, 1)], hi[(0, 1)]]
        L.append("%8d%8d" % (k + 1, pid) + "".join("%8d" % v for v in c))
    for t, E, pid in stack:
        L += ["*PART", "layer%d" % pid, "%10d%10d%10d" % (pid, pid, pid),
              "*SECTION_SOLID", "%10d%10d" % (pid, 1)]
        if E > 0:
            L += ["*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (pid, 7.85e-9, E, 0.3)]
    L.append("*END")
    open(path, "w", newline="\n").write("\n".join(L) + "\n")


def run(binary, cwd, *args):
    p = subprocess.run([binary, "neutralaxis"] + list(args),
                       capture_output=True, text=True, timeout=300, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def main():
    if len(sys.argv) < 2:
        print("usage: test_neutralaxis.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="nax_")
    try:
        # ── A: 솔리드 3층. 비대칭 적층이라 기하 중심과 중립축이 분명히 다르다 ──
        stack = [(0.2, 1000.0, 1), (0.3, 70000.0, 2), (0.1, 3000.0, 3)]
        solid_stack_deck(os.path.join(d, "a.k"), stack)
        zc, exp = 0.0, None
        layers = []
        for t, E, pid in stack:
            layers.append((t, zc + t / 2.0, E))
            zc += t
        exp = closed_form(layers)

        rc, out = run(binary, d, "a.k")
        check("A-1 rc=0", rc == 0, out[-300:])
        check("A-2 층 3개를 썼다", kv(out, "Layers used") == "3", kv(out, "Layers used"))
        check("A-3 중립축 = 닫힌식 %.12g" % exp["zn"],
              near(kv(out, "Neutral axis"), exp["zn"]), kv(out, "Neutral axis"))
        check("A-4 기하 중심면 = 닫힌식 %.12g" % exp["zgeom"],
              near(kv(out, "Geometric mid-plane"), exp["zgeom"]), kv(out, "Geometric mid-plane"))
        check("A-5 ΣE*t = 닫힌식 %.12g" % exp["sum_et"],
              near(kv(out, "Sum E*t"), exp["sum_et"]), kv(out, "Sum E*t"))
        check("A-6 총두께 = %.12g" % exp["sum_t"],
              near(kv(out, "Total thickness"), exp["sum_t"]), kv(out, "Total thickness"))
        dv = (kv(out, "Bending stiffness D") or "").split()[0]
        check("A-7 굽힘강성 D = 닫힌식 %.12g" % exp["D"], near(dv, exp["D"]), dv)
        # 중립축이 기하 중심과 **달라야** 한다 — 같으면 가중이 두께만으로 된 것이다
        check("A-8 중립축 ≠ 기하 중심면 (EI 가중이 실제로 걸렸다)",
              abs(exp["zn"] - exp["zgeom"]) > 1e-6
              and not near(kv(out, "Neutral axis"), exp["zgeom"], 1e-6),
              "%s vs %s" % (kv(out, "Neutral axis"), kv(out, "Geometric mid-plane")))

        # ── B: 셸 층은 두께를 *SECTION_SHELL 에서 읽는다(절점 범위는 0 이다) ──
        T = 0.05
        ZS = 1.0
        L = ["*KEYWORD", "*NODE"]
        for n, (x, y) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)], start=1):
            L.append("%8d%16.9f%16.9f%16.9f" % (n, x, y, ZS))
        L += ["*ELEMENT_SHELL", "%8d%8d%8d%8d%8d%8d" % (1, 7, 1, 2, 3, 4),
              "*PART", "skin", "%10d%10d%10d" % (7, 7, 7),
              "*SECTION_SHELL", "%10d%10d" % (7, 2), "%10.6g%10.6g%10.6g%10.6g" % (T, T, T, T),
              "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (7, 7.85e-9, 70000.0, 0.3), "*END"]
        open(os.path.join(d, "b.k"), "w", newline="\n").write("\n".join(L) + "\n")
        rc, out = run(binary, d, "b.k")
        check("B-1 rc=0", rc == 0, out[-300:])
        check("B-2 셸 두께를 *SECTION_SHELL 에서 읽었다 (%g)" % T,
              near(kv(out, "Total thickness"), T), kv(out, "Total thickness"))
        check("B-3 셸 한 층이면 중립축 = 중면 z (%g)" % ZS,
              near(kv(out, "Neutral axis"), ZS), kv(out, "Neutral axis"))
        check("B-4 층을 shell 로 분류했다", " shell " in out, [l for l in out.splitlines() if "shell" in l][:2])

        # ── C: E 를 못 읽은 파트는 0 으로 쓰지 않고 제외하고 말한다 ──
        bad = [(0.2, 1000.0, 1), (0.3, 0.0, 2), (0.1, 3000.0, 3)]   # PID 2 에 *MAT 가 없다
        solid_stack_deck(os.path.join(d, "c.k"), bad)
        rc, out = run(binary, d, "c.k")
        check("C-1 rc=0", rc == 0, out[-300:])
        check("C-2 층 2개만 썼다", kv(out, "Layers used") == "2", kv(out, "Layers used"))
        check("C-3 제외했다고 말한다", "제외" in out and "MID" in out,
              [l for l in out.splitlines() if "제외" in l][:2])
        exp_c = closed_form([(0.2, 0.1, 1000.0), (0.1, 0.55, 3000.0)])
        check("C-4 남은 두 층의 중립축 = 닫힌식 %.12g" % exp_c["zn"],
              near(kv(out, "Neutral axis"), exp_c["zn"]), kv(out, "Neutral axis"))

        # ── D: 쓸 층이 하나도 없으면 숫자를 내지 않고 rc=1 ──
        solid_stack_deck(os.path.join(d, "e.k"), [(0.2, 0.0, 1)])
        rc, out = run(binary, d, "e.k")
        check("D-1 쓸 층이 없으면 rc=1", rc == 1, "rc=%d" % rc)
        check("D-2 중립축 값을 내지 않는다", kv(out, "Neutral axis") is None, kv(out, "Neutral axis"))

        # ── E: --axis 가 실제로 축을 바꾼다 ──
        solid_stack_deck(os.path.join(d, "f.k"), stack, axis="x")
        rc, out = run(binary, d, "f.k", "--axis", "x")
        check("E-1 rc=0", rc == 0, out[-300:])
        check("E-2 x 로 쌓은 적층의 중립축 = 닫힌식 %.12g" % exp["zn"],
              near(kv(out, "Neutral axis"), exp["zn"]), kv(out, "Neutral axis"))
        # 같은 덱을 기본 z 로 보면 세 층이 모두 z 0~1 을 채우므로 중립축이 0.5 로 나와야 한다.
        # x 답과 달라야 --axis 가 실제로 축을 바꾼 것이다.
        rc2, out2 = run(binary, d, "f.k")
        check("E-3 같은 덱을 기본 z 로 보면 다른 답(0.5)이 나온다 (축을 정말 쓴다)",
              rc2 == 0 and near(kv(out2, "Neutral axis"), 0.5)
              and not near(kv(out2, "Neutral axis"), exp["zn"], 1e-6),
              "rc=%d / %s" % (rc2, kv(out2, "Neutral axis")))
        rc3, out3 = run(binary, d, "f.k", "--axis", "q")
        check("E-4 모르는 축은 rc=1", rc3 == 1, out3[-200:])

        # ── F: shellmap 의 축=0 전제와 맞물린 경고 ──
        far = [(0.1, 1000.0, 1)]
        # 적층을 z=5 로 띄운다 → 중립축이 적층 밖(|z_n| > 0.5*Σt)
        L = open(os.path.join(d, "a.k")).read()
        solid_stack_deck(os.path.join(d, "g.k"), far)
        lines = open(os.path.join(d, "g.k")).read().splitlines()
        outl = []
        in_node = False
        for ln in lines:
            if ln.startswith("*"):
                in_node = (ln.strip() == "*NODE")
                outl.append(ln)
                continue
            if in_node and len(ln) >= 56:
                z = float(ln[40:56]) + 5.0
                outl.append(ln[:40] + "%16.9f" % z)
            else:
                outl.append(ln)
        open(os.path.join(d, "g.k"), "w", newline="\n").write("\n".join(outl) + "\n")
        rc, out = run(binary, d, "g.k")
        check("F-1 rc=0", rc == 0, out[-300:])
        check("F-2 중립축 = 5.05 (z 를 5 띄웠다)", near(kv(out, "Neutral axis"), 5.05, 1e-7),
              kv(out, "Neutral axis"))
        check("F-3 z=0 이 적층 밖이면 그렇게 경고한다", "shellmap" in out and "z=0 이 적층 밖" in out,
              [l for l in out.splitlines() if "shellmap" in l][:2])
        check("F-4 적층 범위를 찍는다 (5 .. 5.1)",
              (kv(out, "Stack extent") or "").replace(" ", "") == "5..5.1", kv(out, "Stack extent"))

        # z=0 이 적층 **안**이지만 중립축에서 멀 때 — a.k 는 z 0~0.6, z_n=0.3505
        rc, out = run(binary, d, "a.k")
        check("F-5 z=0 이 적층 안이면 '적층 밖' 이라 말하지 않는다", "z=0 이 적층 밖" not in out,
              [l for l in out.splitlines() if "적층 밖" in l][:2])
        check("F-6 중립축에서 두께 절반 넘게 떨어졌으면 경고한다", "두께의 절반 넘게" in out,
              [l for l in out.splitlines() if "shellmap" in l][:2])

        # 중립축이 정확히 z=0 인 대칭 적층 — 경고가 없어야 한다(오탐 방지)
        sym = [(0.1, 1000.0, 1), (0.3, 70000.0, 2), (0.1, 1000.0, 3)]
        solid_stack_deck(os.path.join(d, "h.k"), sym)
        lines = open(os.path.join(d, "h.k")).read().splitlines()
        outl, in_node = [], False
        for ln in lines:
            if ln.startswith("*"):
                in_node = (ln.strip() == "*NODE")
                outl.append(ln)
                continue
            if in_node and len(ln) >= 56:
                outl.append(ln[:40] + "%16.9f" % (float(ln[40:56]) - 0.25))
            else:
                outl.append(ln)
        open(os.path.join(d, "h.k"), "w", newline="\n").write("\n".join(outl) + "\n")
        rc, out = run(binary, d, "h.k")
        check("F-7 대칭 적층의 중립축 = 0", near(kv(out, "Neutral axis"), 0.0, 1e-12),
              kv(out, "Neutral axis"))
        check("F-8 중립축이 z=0 이면 경고하지 않는다 (오탐 방지)", "shellmap" not in out,
              [l for l in out.splitlines() if "shellmap" in l][:2])
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
