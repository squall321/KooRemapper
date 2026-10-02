#!/usr/bin/env python3
# applyfold 가 군별 변환을 빠짐없이 찍는지 — 희소 ID 덱에서 조용히 빠지는 절점을 잡는다
"""`applyfold` 의 적용 계약 (2026-10-02, 현장 보고 §2-5).

왜 이 시험이 있나.

  보고의 수용 기준은 "바이트 크기 동일 · 되읽기 오차 ~0 · 미이동 0 · bbox 가 기대 범위 안" 이고,
  ★안전장치를 하나 못 박았다 — "ID 인덱스 배열은 **덱의 최대 ID** 로 잡는다. 실측: 절점 15.81M
  인데 최대 ID 17.85M, **712,103개가 조용히 누락됐다.** 버린 개수가 0 이 아니면 실패."

  이 구현은 ID 로 색인한 배열이 아니라 **맵**을 쓰므로 그 함정 자체는 없다. 그래도 **기준은
  그대로 지킨다** — 번호가 듬성듬성한 덱(최대 ID 가 절점 수의 10배)에서도 하나도 빠지지 않는지
  본다. 함정이 없다는 말보다 안 빠진다는 측정이 낫다.

  그리고 "미이동 0" 은 그대로 쓰면 **틀린 기준이다.** 회전축 위의 절점은 제대로 변환해도 제자리에
  남는다. 그래서 '움직였나' 가 아니라 **'요구한 변환과 같은가'** 를 본다 — 더 센 검사다.

usage: test_applyfold.py <KooRemapper 바이너리>
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


def rot(axis, deg):
    n = math.sqrt(sum(a * a for a in axis))
    u = [a / n for a in axis]
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    ux, uy, uz = u
    return [[c+ux*ux*(1-c), ux*uy*(1-c)-uz*s, ux*uz*(1-c)+uy*s],
            [uy*ux*(1-c)+uz*s, c+uy*uy*(1-c), uy*uz*(1-c)-ux*s],
            [uz*ux*(1-c)-uy*s, uz*uy*(1-c)+ux*s, c+uz*uz*(1-c)]]


def tf(R, piv, p):
    d = [p[i] - piv[i] for i in range(3)]
    return [sum(R[i][j] * d[j] for j in range(3)) + piv[i] for i in range(3)]


def build(path, parts, id_stride=1, share_nodes=False):
    """parts = [pid, ...]; id_stride 로 절점 번호를 듬성듬성하게 만든다."""
    nid, eid, nodes, elems = 1, 1, [], []
    prev_top = None
    for k, pid in enumerate(parts):
        x0 = 10.0 * k
        idx = {}
        for kk in (0, 1):
            for jj in (0, 1):
                for ii in (0, 1):
                    if share_nodes and prev_top is not None and ii == 0:
                        idx[(ii, jj, kk)] = prev_top[(jj, kk)]
                        continue
                    nodes.append((nid, (x0 + ii * 8.0, jj * 4.0, kk * 2.0)))
                    idx[(ii, jj, kk)] = nid
                    nid += id_stride
        prev_top = {(jj, kk): idx[(1, jj, kk)] for jj in (0, 1) for kk in (0, 1)}
        c = [idx[(0,0,0)], idx[(1,0,0)], idx[(1,1,0)], idx[(0,1,0)],
             idx[(0,0,1)], idx[(1,0,1)], idx[(1,1,1)], idx[(0,1,1)]]
        elems.append((eid, pid, c))
        eid += 1
    L = ["*KEYWORD", "*NODE"]
    for n, p in nodes:
        L.append("%8d%16.9f%16.9f%16.9f" % (n, p[0], p[1], p[2]))
    L.append("*ELEMENT_SOLID")
    for e, pid, c in elems:
        L.append("%8d%8d" % (e, pid) + "".join("%8d" % v for v in c))
    for pid in parts:
        L += ["*PART", "p%d" % pid, "%10d%10d%10d" % (pid, pid, pid),
              "*SECTION_SOLID", "%10d%10d" % (pid, 1),
              "*MAT_ELASTIC", "%10d%10.4g%10.6g%10.4g" % (pid, 7.85e-9, 210000.0, 0.3)]
    L.append("*END")
    open(path, "w", newline="\n").write("\n".join(L) + "\n")
    return len(nodes), (nid - id_stride)


def groups_yaml(path, entries):
    """entries = [(parts, angle, axis, pivot, slide)]"""
    L = ["groups:"]
    for parts, ang, ax, piv, sl in entries:
        L.append("  - parts: [%s]" % ", ".join(str(p) for p in parts))
        L.append("    angle: %.12g" % ang)
        L.append("    axis: [%.12g, %.12g, %.12g]" % tuple(ax))
        L.append("    pivot: [%.12g, %.12g, %.12g]" % tuple(piv))
        L.append("    slide: %.12g" % sl)
    open(path, "w", newline="\n").write("\n".join(L) + "\n")


def main():
    if len(sys.argv) < 2:
        print("usage: test_applyfold.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="afold_")
    Z = [0.0, 0.0, 1.0]
    try:
        # ── A: linkage-fit → applyfold 왕복 ──
        n_nodes, _ = build(os.path.join(d, "flat.k"), [1, 2, 3])
        src = read_nodes(os.path.join(d, "flat.k"))
        spec = {2: (Z, 45.0, [10.0, 0.0, 0.0]), 3: (Z, 90.0, [20.0, 0.0, 0.0])}
        # 참 접힘 덱을 만든다
        lines = open(os.path.join(d, "flat.k"), encoding="utf-8").read().splitlines()
        # 파트별 절점을 알려면 요소를 봐야 하니, 간단히 x 로 구간을 나눈다(블록이 겹치지 않는다)
        def part_of(p):
            return 1 if p[0] < 9.5 else (2 if p[0] < 19.5 else 3)
        out = []
        kw = None
        for ln in lines:
            if ln.startswith("*"):
                kw = ln.strip().upper()
                out.append(ln)
                continue
            if kw == "*NODE" and len(ln) >= 56:
                n = int(ln[0:8])
                p = src[n]
                pid = part_of(p)
                q = p if pid not in spec else tf(rot(spec[pid][0], spec[pid][1]), spec[pid][2], list(p))
                out.append("%8d%16.9f%16.9f%16.9f" % (n, q[0], q[1], q[2]))
            else:
                out.append(ln)
        open(os.path.join(d, "folded.k"), "w", newline="\n").write("\n".join(out) + "\n")

        write_cfg(os.path.join(d, "lf.yaml"), reference="flat.k", folded="folded.k", output="g")
        rc, out_lf = run(binary, d, "linkage-fit", "lf.yaml")
        check("A-1 linkage-fit rc=0", rc == 0, out_lf[-300:])
        write_cfg(os.path.join(d, "af.yaml"), model="flat.k", groups="g.yaml", output="refold")
        rc, out = run(binary, d, "applyfold", "af.yaml")
        check("A-2 applyfold rc=0", rc == 0, out[-500:])
        check("A-3 요구한 변환과의 최대 편차가 관용 안", kv(out, "Off-transform nodes") == "0",
              kv(out, "Max transform deviation"))
        check("A-4 군에 없는 절점이 움직이지 않았다", kv(out, "Moved but should not") == "0",
              kv(out, "Moved but should not"))
        check("A-5 절점을 하나도 버리지 않았다 (%d개)" % n_nodes,
              kv(out, "Nodes moved") == str(n_nodes), kv(out, "Nodes moved"))
        sz = kv(out, "Byte size")
        check("A-6 바이트 크기 동일 (%s)" % sz, sz and sz.split("→")[0].strip() == sz.split("→")[1].strip(), sz)
        got = read_nodes(os.path.join(d, "refold.k"))
        want = read_nodes(os.path.join(d, "folded.k"))
        worst = max(math.dist(got[n], want[n]) for n in want)
        check("A-7 왕복 좌표가 참 접힘 덱과 맞는다 (최대 %.3g)" % worst, worst < 1e-6, worst)
        # 회전축 위 절점은 제자리에 남지만 **실패가 아니다** — 그 자리를 못 박는다
        onaxis = [n for n, p in src.items() if abs(p[0] - 10.0) < 1e-9 and abs(p[1]) < 1e-9]
        check("A-8 회전축 위 절점(%d개)이 제자리인데도 rc=0" % len(onaxis),
              bool(onaxis) and all(math.dist(got[n], src[n]) < 1e-9 for n in onaxis), onaxis[:3])

        # ── B: ★희소 ID — 최대 ID 가 절점 수의 10배여도 하나도 안 빠진다 ──
        n2, maxid = build(os.path.join(d, "sparse.k"), [1, 2, 3], id_stride=10)
        groups_yaml(os.path.join(d, "gs.yaml"),
                    [([1], 0.0, Z, [0, 0, 0], 0.0),
                     ([2], 45.0, Z, [10, 0, 0], 0.0),
                     ([3], 90.0, Z, [20, 0, 0], 0.0)])
        write_cfg(os.path.join(d, "afs.yaml"), model="sparse.k", groups="gs.yaml", output="sfold")
        rc, out = run(binary, d, "applyfold", "afs.yaml")
        check("B-1 rc=0", rc == 0, out[-400:])
        check("B-2 절점 %d개 · 최대 ID %d 인 덱에서 전부 옮겼다" % (n2, maxid),
              kv(out, "Nodes moved") == str(n2) and kv(out, "Nodes") == str(n2),
              (kv(out, "Nodes"), kv(out, "Nodes moved")))
        check("B-3 요구한 변환과 다른 절점 0개", kv(out, "Off-transform nodes") == "0",
              kv(out, "Max transform deviation"))

        # ── C: 안전장치 — 없는 파트 / 절점을 나눠 가진 군 / 망가진 yaml ──
        groups_yaml(os.path.join(d, "bad1.yaml"), [([1, 99], 45.0, Z, [10, 0, 0], 0.0)])
        write_cfg(os.path.join(d, "c1.yaml"), model="flat.k", groups="bad1.yaml", output="x1")
        rc, out = run(binary, d, "applyfold", "c1.yaml")
        check("C-1 덱에 없는 파트를 가리키면 rc=1", rc == 1, out[-200:])
        check("C-2 어느 파트가 없는지 말한다", "99" in out, out[-200:])

        build(os.path.join(d, "welded.k"), [1, 2], share_nodes=True)
        groups_yaml(os.path.join(d, "bad2.yaml"),
                    [([1], 0.0, Z, [0, 0, 0], 0.0), ([2], 90.0, Z, [10, 0, 0], 0.0)])
        write_cfg(os.path.join(d, "c3.yaml"), model="welded.k", groups="bad2.yaml", output="x3")
        rc, out = run(binary, d, "applyfold", "c3.yaml")
        check("C-3 두 군이 절점을 나눠 가지면 rc=1", rc == 1, out[-300:])
        check("C-4 disconnect 를 권한다", "disconnect" in out, out[-300:])

        for name, body in (("C-5 parts 가 비면 rc=1", "groups:\n  - parts: []\n    angle: 0\n"),
                           ("C-6 축이 망가지면 rc=1",
                            "groups:\n  - parts: [1]\n    angle: 0\n    axis: [0, 0]\n"),
                           ("C-7 groups 항목이 없으면 rc=1", "groups:\n")):
            open(os.path.join(d, "bad3.yaml"), "w", newline="\n").write(body)
            write_cfg(os.path.join(d, "c.yaml"), model="flat.k", groups="bad3.yaml", output="x")
            rc, out = run(binary, d, "applyfold", "c.yaml")
            check(name, rc == 1, out[-200:])

        for name, args in (("C-8 model 누락은 rc=1", dict(groups="g.yaml", output="x")),
                           ("C-9 groups 누락은 rc=1", dict(model="flat.k", output="x")),
                           ("C-10 output 누락은 rc=1", dict(model="flat.k", groups="g.yaml")),
                           ("C-11 없는 groups 파일은 rc=1",
                            dict(model="flat.k", groups="nope.yaml", output="x"))):
            write_cfg(os.path.join(d, "c.yaml"), **args)
            rc, out = run(binary, d, "applyfold", "c.yaml")
            check(name, rc == 1, out[-200:])

        # ── D: 군에 없는 파트는 바이트 그대로 남는다 ──
        groups_yaml(os.path.join(d, "only2.yaml"), [([2], 90.0, Z, [10, 0, 0], 0.0)])
        write_cfg(os.path.join(d, "d.yaml"), model="flat.k", groups="only2.yaml", output="dfold")
        rc, out = run(binary, d, "applyfold", "d.yaml")
        check("D-1 rc=0", rc == 0, out[-300:])
        dn = read_nodes(os.path.join(d, "dfold.k"))
        untouched = [n for n, p in src.items() if p[0] > 19.5]
        check("D-2 군에 없는 파트(PID 3)의 절점이 그대로다",
              all(math.dist(dn[n], src[n]) < 1e-12 for n in untouched), len(untouched))
        check("D-3 bbox 를 찍는다", kv(out, "bbox before") and kv(out, "bbox after"),
              (kv(out, "bbox before"), kv(out, "bbox after")))
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
