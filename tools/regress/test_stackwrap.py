#!/usr/bin/env python3
# stackwrap 이 적층을 중립축으로 옮겨 감는지 — 닫힌식 원호와 대조한다
"""`stackwrap` 의 기하 계약 (2026-10-02, 현장 보고 §2-4).

왜 이 시험이 있나.

  보고의 수용 기준은 "두 방법의 좌표 차이가 메시 크기의 1/10 이내" 였다. 두 번째 감기 구현을
  두고 서로 맞는지 보라는 뜻인데, **그러지 않았다.** `shellmap` 이 이미 적층을 감고 있고, 두
  구현이 서로 맞는 것은 둘 다 틀렸을 때도 성립한다. 대신 **닫힌식**과 맞춘다 — 기준면이 원호면
  감긴 절점의 반경은 `R - z` 로 정확히 안다.

  `stackwrap` 이 더하는 것은 감기가 아니라 **중립면 정렬**이다. `shellmap` 은 평면 덱의 z=0 을
  중립면으로 보고 z 를 법선 오프셋으로 쓴다(§1-6). 적층의 EI 중립축이 z=0 이 아니면 그만큼
  전부 어긋난다. 그래서 이 시험이 보는 것은 셋이다.

    ① 평행이동이 **정확히 -z_n** 이고 모든 절점에 같게 걸렸나.
    ② 감긴 절점의 반경이 `R - z_shifted` 와 **메시 크기의 1/10 안**에서 맞나.
    ③ 옮기지 않으면(`shift: false`) 그 사실을 **말하나.**

  부호 규약: `refshell` 의 감김 (a,d,c,b) 법선이 오목한 쪽을 향하므로, 평면 덱의 **양수 z 가
  오목한(곡률 중심) 쪽**으로 간다 — 반경이 R 보다 작아진다. 이 시험이 그 규약을 못 박는다.

usage: test_stackwrap.py <KooRemapper 바이너리>
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

FAILS = []
R = 3.0
ANG = 90.0
LAYERS = [(0.20, 1000.0, 1), (0.30, 70000.0, 2), (0.10, 3000.0, 3)]


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


def read_nodes(path):
    nodes, kw = {}, None
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
    return nodes


def make_stack(path, L, W, nx, ny, with_mat=True):
    zs = [0.0]
    for t, E, p in LAYERS:
        zs.append(zs[-1] + t)
    nid, nodes, idx = 1, [], {}
    for k, z in enumerate(zs):
        for j in range(ny + 1):
            for i in range(nx + 1):
                idx[(i, j, k)] = nid
                nodes.append((nid, L * i / nx, W * j / ny, z))
                nid += 1
    out = ["*KEYWORD", "*NODE"]
    for n, x, y, z in nodes:
        out.append("%8d%16.9f%16.9f%16.9f" % (n, x, y, z))
    out.append("*ELEMENT_SOLID")
    e = 0
    for k in range(len(LAYERS)):
        pid = LAYERS[k][2]
        for j in range(ny):
            for i in range(nx):
                e += 1
                c = [idx[(i, j, k)], idx[(i + 1, j, k)], idx[(i + 1, j + 1, k)], idx[(i, j + 1, k)],
                     idx[(i, j, k + 1)], idx[(i + 1, j, k + 1)], idx[(i + 1, j + 1, k + 1)],
                     idx[(i, j + 1, k + 1)]]
                out.append("%8d%8d" % (e, pid) + "".join("%8d" % v for v in c))
    for t, E, pid in LAYERS:
        out += ["*PART", "layer%d" % pid, "%10d%10d%10d" % (pid, pid, pid),
                "*SECTION_SOLID", "%10d%10d" % (pid, 1)]
        if with_mat:
            out += ["*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (pid, 7.85e-9, E, 0.3)]
    out.append("*END")
    open(path, "w", newline="\n").write("\n".join(out) + "\n")


def expected_neutral():
    zc, num, den = 0.0, 0.0, 0.0
    for t, E, p in LAYERS:
        c = zc + t / 2.0
        num += E * t * c
        den += E * t
        zc += t
    return num / den


def main():
    if len(sys.argv) < 2:
        print("usage: test_stackwrap.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="swrap_")
    try:
        # 기준면: 반경 3, 90도 원호. 정점이 원점이므로 곡률 중심은 (0, R).
        arc = R * math.radians(ANG)
        write_cfg(os.path.join(d, "f.yaml"), output="f", arc_length=repr(arc),
                  fold_angle=ANG, min_radius=R, points=97)
        rc, out = run(binary, d, "foldsurface", "f.yaml")
        check("준비-1 foldsurface rc=0", rc == 0, out[-200:])
        write_cfg(os.path.join(d, "r.yaml"), curve="f_curve.csv", output="ref.k",
                  width=1.0, thickness=0.05, divisions=48)
        rc, out = run(binary, d, "refshell", "r.yaml")
        check("준비-2 refshell rc=0", rc == 0, out[-200:])
        chord = float(kv(out, "Chord sum"))
        mesh_size = float(kv(out, "Element size (curve)"))
        nw = int(kv(out, "Divisions (curve x width)").split("x")[1])
        make_stack(os.path.join(d, "stack.k"), chord, 1.0, 48, nw)

        write_cfg(os.path.join(d, "sw.yaml"), bent_shell="ref.k", flat_stack="stack.k",
                  output="wrapped")
        rc, out = run(binary, d, "stackwrap", "sw.yaml")
        check("A-1 rc=0", rc == 0, out[-400:])
        zn = expected_neutral()
        check("A-2 중립축 = 닫힌식 %.12g" % zn,
              abs(float(kv(out, "Neutral axis")) - zn) < 1e-9, kv(out, "Neutral axis"))
        check("A-3 층 3개", kv(out, "Layers") == "3", kv(out, "Layers"))

        flat = read_nodes(os.path.join(d, "stack.k"))
        shifted = read_nodes(os.path.join(d, "wrapped_neutral.k"))
        wrapped = read_nodes(os.path.join(d, "wrapped.k"))
        check("A-4 절점 수가 세 덱에서 같다",
              len(flat) == len(shifted) == len(wrapped), (len(flat), len(shifted), len(wrapped)))
        dz = [shifted[n][2] - flat[n][2] for n in flat]
        check("A-5 모든 절점이 **정확히 같은 양** 만큼 이동했다",
              max(dz) - min(dz) < 1e-9, (min(dz), max(dz)))
        check("A-6 이동량 = -z_n (%.9g)" % -zn, abs(min(dz) + zn) < 1e-9, min(dz))
        dxy = max(max(abs(shifted[n][0] - flat[n][0]), abs(shifted[n][1] - flat[n][1]))
                  for n in flat)
        check("A-7 x·y 는 건드리지 않았다", dxy < 1e-12, dxy)

        # ── B: 감긴 좌표를 닫힌식과 대조한다. 반경 = R - z_shifted ──
        tol = mesh_size / 10.0
        worst, worst_at = 0.0, None
        for n, p in wrapped.items():
            zs_ = shifted[n][2]
            r = math.hypot(p[0], p[1] - R)
            err = abs(r - (R - zs_))
            if err > worst:
                worst, worst_at = err, (n, r, R - zs_)
        check("B-1 모든 절점의 반경 = R - z (오차 %.3g < 메시/10 = %.3g)" % (worst, tol),
              worst < tol, worst_at)
        # 부호 규약 — 양수 z 는 오목한 쪽(반경이 작아진다)
        top = [n for n in shifted if abs(shifted[n][2] - (0.6 - zn)) < 1e-9]
        bot = [n for n in shifted if abs(shifted[n][2] + zn) < 1e-9]
        check("B-2 평면 덱의 양수 z 가 오목한 쪽(반경 < R)으로 간다",
              top and all(math.hypot(wrapped[n][0], wrapped[n][1] - R) < R for n in top),
              [math.hypot(wrapped[n][0], wrapped[n][1] - R) for n in top[:2]])
        check("B-3 음수 z 가 볼록한 쪽(반경 > R)으로 간다",
              bot and all(math.hypot(wrapped[n][0], wrapped[n][1] - R) > R for n in bot),
              [math.hypot(wrapped[n][0], wrapped[n][1] - R) for n in bot[:2]])
        # 두께가 보존되나 — 바닥과 천장 반경 차이가 적층 두께다
        if top and bot:
            rt = sum(math.hypot(wrapped[n][0], wrapped[n][1] - R) for n in top) / len(top)
            rb = sum(math.hypot(wrapped[n][0], wrapped[n][1] - R) for n in bot) / len(bot)
            check("B-4 감긴 뒤에도 두께가 0.6 이다 (%.9f)" % (rb - rt),
                  abs((rb - rt) - 0.6) < tol, rb - rt)

        # ── C: 옮기지 않으면 그 사실을 말한다 ──
        write_cfg(os.path.join(d, "ns.yaml"), bent_shell="ref.k", flat_stack="stack.k",
                  output="noshift", shift="false")
        rc, out = run(binary, d, "stackwrap", "ns.yaml")
        check("C-1 rc=0", rc == 0, out[-300:])
        check("C-2 옮기지 않았다고 경고한다", "shift: false" in out and "어긋난" in out,
              [l for l in out.splitlines() if "shift" in l][:1])
        check("C-3 중간 덱을 쓰지 않는다", not os.path.exists(os.path.join(d, "noshift_neutral.k")))
        ns_w = read_nodes(os.path.join(d, "noshift.k"))
        moved = max(abs(math.hypot(ns_w[n][0], ns_w[n][1] - R)
                        - math.hypot(wrapped[n][0], wrapped[n][1] - R)) for n in ns_w)
        check("C-4 옮긴 결과와 **다르다** (중립면 정렬이 실제로 일을 한다, 차이 %.6g)" % moved,
              moved > 0.5 * zn, moved)

        # ── D: 입력 덱을 건드리지 않는다 ──
        before = open(os.path.join(d, "stack.k"), "rb").read()
        run(binary, d, "stackwrap", "sw.yaml")
        check("D-1 입력 덱이 바이트 그대로다",
              open(os.path.join(d, "stack.k"), "rb").read() == before)

        # ── E: 잘못된 입력은 숫자를 내지 않는다 ──
        make_stack(os.path.join(d, "nomat.k"), chord, 1.0, 4, 2, with_mat=False)
        cases = [
            ("E-1 bent_shell 누락은 rc=1", dict(flat_stack="stack.k", output="x1")),
            ("E-2 flat_stack 누락은 rc=1", dict(bent_shell="ref.k", output="x2")),
            ("E-3 output 누락은 rc=1", dict(bent_shell="ref.k", flat_stack="stack.k")),
            ("E-4 모르는 axis 는 rc=1", dict(bent_shell="ref.k", flat_stack="stack.k",
                                           output="x4", axis="q")),
            ("E-5 E 를 못 읽는 적층은 rc=1", dict(bent_shell="ref.k", flat_stack="nomat.k",
                                              output="x5")),
            ("E-6 없는 기준 셸은 rc=1", dict(bent_shell="nope.k", flat_stack="stack.k",
                                          output="x6")),
        ]
        for name, args in cases:
            write_cfg(os.path.join(d, "e.yaml"), **args)
            rc, out = run(binary, d, "stackwrap", "e.yaml")
            check(name, rc == 1, out[-200:])
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
