#!/usr/bin/env python3
# linkage-fit 이 알려진 군별 강체변환을 되찾는지 — 피벗 산포 안전장치까지 확인한다
"""`linkage-fit` 의 역산 계약 (2026-10-02, 현장 보고 §2-1).

왜 이 시험이 있나.

  보고가 직접 가장 강한 시험을 지정했다 — "**알려진** 군별 강체변환을 걸어 접힘 덱을 합성하고
  op 이 그것을 되찾는지 본다". 그대로 한다. 참 값을 내가 정하므로 '그럴듯한가' 가 아니라
  '맞는가' 를 물을 수 있다.

  그리고 보고가 안전장치를 못 박았다 — "★군별 **피벗 산포**를 출력하라. 각도만으로 묶으면
  조용히 틀린다(실측 5.41mm)". 그래서 **같은 각·다른 피벗** 파트를 일부러 넣고 그 경고가
  숫자와 함께 뜨는지 본다.

  피벗은 축 위 어느 점이든 같은 변환이다. 그래서 비교는 '점이 같은가' 가 아니라 **'되찾은 점이
  참 축선 위에 있는가'** 로 한다.

usage: test_linkage_fit.py <KooRemapper 바이너리>
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


def rot(axis, deg):
    """축-각 회전행렬 (Rodrigues)."""
    n = math.sqrt(sum(a * a for a in axis))
    u = [a / n for a in axis]
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    ux, uy, uz = u
    return [
        [c + ux*ux*(1-c),    ux*uy*(1-c)-uz*s, ux*uz*(1-c)+uy*s],
        [uy*ux*(1-c)+uz*s,   c + uy*uy*(1-c),  uy*uz*(1-c)-ux*s],
        [uz*ux*(1-c)-uy*s,   uz*uy*(1-c)+ux*s, c + uz*uz*(1-c)],
    ]


def apply_tf(R, pivot, slide_axis, slide, p):
    d = [p[i] - pivot[i] for i in range(3)]
    q = [sum(R[i][j] * d[j] for j in range(3)) + pivot[i] for i in range(3)]
    if slide:
        n = math.sqrt(sum(a * a for a in slide_axis))
        q = [q[i] + slide_axis[i] / n * slide for i in range(3)]
    return q


def axis_dist(p, pivot, axis):
    """점 p 에서 (pivot, axis) 축선까지의 수직 거리."""
    n = math.sqrt(sum(a * a for a in axis))
    u = [a / n for a in axis]
    d = [p[i] - pivot[i] for i in range(3)]
    par = sum(d[i] * u[i] for i in range(3))
    perp = [d[i] - par * u[i] for i in range(3)]
    return math.sqrt(sum(a * a for a in perp))


def build_decks(d, specs, stretch_pid=None):
    """파트마다 hex8 블록 하나. specs[pid] = (axis, angle, pivot, slide)."""
    nid, eid = 1, 1
    rn, dn, elems, parts = [], [], [], []
    for k, (pid, spec) in enumerate(sorted(specs.items())):
        x0 = 10.0 * k
        corners = []
        for kk in (0, 1):
            for jj in (0, 1):
                for ii in (0, 1):
                    corners.append((x0 + ii * 8.0, jj * 4.0, kk * 2.0))
        base = nid
        for p in corners:
            rn.append((nid, p))
            if spec is None:
                q = p
            else:
                ax, ang, piv, sl = spec
                q = apply_tf(rot(ax, ang), piv, ax, sl, list(p))
            if stretch_pid == pid:
                q = [q[0] * 1.02, q[1], q[2]]   # 강체가 아닌 파트
            dn.append((nid, q))
            nid += 1
        c = [base + i for i in (0, 1, 3, 2, 4, 5, 7, 6)]
        elems.append((eid, pid, c))
        eid += 1
        parts.append(pid)

    def deck(path, nodes):
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
        open(os.path.join(d, path), "w", newline="\n").write("\n".join(L) + "\n")

    deck("ref.k", rn)
    deck("fold.k", dn)


def table_rows(out):
    """파트 표를 {pid: (angle, axis, pivot, slide, rms)} 로 읽는다."""
    rows = {}
    for ln in out.splitlines():
        s = ln.strip()
        if not s or s.startswith(("[", "=", "PID", "group")):
            continue
        if "(" not in s:
            continue
        try:
            pid = int(s.split()[0])
            ang = float(s.split()[1])
            a = s[s.index("(") + 1:s.index(")")].split()
            rest = s[s.index(")") + 1:]
            p = rest[rest.index("(") + 1:rest.index(")")].split()
            tail = rest[rest.index(")") + 1:].split()
            rows[pid] = (ang, [float(v) for v in a], [float(v) for v in p],
                         float(tail[0]), float(tail[1]))
        except (ValueError, IndexError):
            continue
    return rows


def main():
    if len(sys.argv) < 2:
        print("usage: test_linkage_fit.py <KooRemapper 바이너리>")
        return 2
    binary = os.path.abspath(sys.argv[1])
    if not os.path.exists(binary):
        print("binary not found")
        return 2

    d = tempfile.mkdtemp(prefix="lfit_")
    try:
        # 참 값 — PID 3,4 는 같은 힌지(한 군), PID 5 는 **같은 각 다른 피벗**(안전장치 표적)
        Z = [0.0, 0.0, 1.0]
        specs = {
            1: None,                                  # 고정
            2: (Z, 45.0, [10.0, 0.0, 0.0], 0.0),
            3: (Z, 90.0, [20.0, 0.0, 0.0], 0.0),
            4: (Z, 90.0, [20.0, 0.0, 0.0], 0.0),      # 3 과 같은 힌지
            5: (Z, 90.0, [60.0, 0.0, 0.0], 0.0),      # 같은 각, **다른 피벗**
            6: ([0.0, 1.0, 0.0], 30.0, [50.0, 0.0, 0.0], 7.0),   # 나사 운동
        }
        build_decks(d, specs)
        write_cfg(os.path.join(d, "lf.yaml"), reference="ref.k", folded="fold.k",
                  output="groups", angle_tol=0.5, pivot_tol=0.5)
        rc, out = run(binary, d, "linkage-fit", "lf.yaml")
        check("A-1 rc=0", rc == 0, out[-400:])
        check("A-2 파트 6개를 적합했다", kv(out, "Parts fitted") == "6", kv(out, "Parts fitted"))
        rows = table_rows(out)
        check("A-3 표에서 파트 6개를 읽었다", len(rows) == 6, sorted(rows))

        for pid, spec in specs.items():
            if pid not in rows:
                continue
            ang, axis, piv, slide, rms = rows[pid]
            if spec is None:
                check("B-%d 고정 파트는 각 0" % pid, abs(ang) < 1e-6, ang)
                continue
            ax, want_ang, want_piv, want_slide = spec
            check("B-%d 각 = %.6g (되찾음 %.6f)" % (pid, want_ang, ang),
                  abs(ang - want_ang) < 1e-6, ang)
            dot = abs(sum(axis[i] * ax[i] for i in range(3)))
            check("B-%d 축이 참 축과 평행 (|dot|=%.9f)" % (pid, dot),
                  abs(dot - 1.0) < 1e-9, (axis, ax))
            # 피벗은 축 위 어느 점이든 같다 — 참 축선까지의 거리로 본다
            dist = axis_dist(piv, want_piv, ax)
            check("B-%d 피벗이 참 축선 위에 있다 (거리 %.3g)" % (pid, dist), dist < 1e-6, (piv, want_piv))
            check("B-%d 축방향 이동 = %.6g (되찾음 %.6f)" % (pid, want_slide, slide),
                  abs(slide - want_slide) < 1e-6, slide)
            check("B-%d 강체 잔차 ~ 0 (%.3g)" % (pid, rms), rms < 1e-8, rms)

        # ── C: 군 묶기 — 3,4 는 한 군, 5 는 따로 ──
        check("C-1 군이 5개다 (3·4 만 묶인다)", kv(out, "Groups") == "5", kv(out, "Groups"))
        gline = [l for l in out.splitlines() if "3,4" in l]
        check("C-2 3 과 4 가 같은 군이다", bool(gline), [l.strip() for l in out.splitlines()
                                                   if l.strip().startswith(("1 ", "2 ", "3 "))][:3])
        if gline:
            parts = gline[0].split()
            check("C-3 그 군의 피벗 산포 ~ 0", float(parts[-2]) < 1e-6, parts[-2:])

        # ── D: ★안전장치 — 각도만으로 묶으면 피벗이 흩어진다고 말한다 ──
        warn = [l for l in out.splitlines() if "각도만으로" in l]
        check("D-1 각도만 묶기의 위험을 경고한다", bool(warn), out[-500:])
        if warn:
            # 90도 파트는 3,4(피벗 20) 와 5(피벗 60) → 산포 40
            check("D-2 경고가 **산포 40** 을 숫자로 말한다", " 40 " in warn[0] or "40 만큼" in warn[0],
                  warn[0])

        # ── E: 산출 yaml ──
        yml = os.path.join(d, "groups.yaml")
        check("E-1 yaml 을 썼다", os.path.exists(yml))
        if os.path.exists(yml):
            txt = open(yml, encoding="utf-8").read()
            check("E-2 groups: 와 parts: 가 있다", "groups:" in txt and "parts:" in txt, txt[:200])
            check("E-3 3·4 가 한 항목으로 묶였다", "[3, 4]" in txt,
                  [l for l in txt.splitlines() if "parts:" in l])
            check("E-4 축·피벗·각을 모두 적었다",
                  all(k in txt for k in ("angle:", "axis:", "pivot:", "slide:", "rms_residual:")))

        # ── F: 강체가 아닌 파트는 그렇게 말한다 ──
        build_decks(d, specs, stretch_pid=2)
        rc, out2 = run(binary, d, "linkage-fit", "lf.yaml")
        check("F-1 rc=0 (경고로 끝낸다)", rc == 0, out2[-300:])
        check("F-2 PID 2 가 강체가 아니라고 말한다",
              any("강체가 아니다" in l and "PID 2" in l for l in out2.splitlines()),
              [l for l in out2.splitlines() if "강체" in l][:2])

        # ── G: 위상이 다르면 끊는다 ──
        lines = open(os.path.join(d, "fold.k"), encoding="utf-8").read().splitlines()
        out_lines, dropped, kw = [], 0, None
        for ln in lines:
            if ln.startswith("*"):
                kw = ln.strip().upper()
                out_lines.append(ln)
                continue
            if kw == "*NODE" and dropped == 0 and len(ln) >= 56:
                dropped = 1
                continue
            out_lines.append(ln)
        open(os.path.join(d, "short.k"), "w", newline="\n").write("\n".join(out_lines) + "\n")
        write_cfg(os.path.join(d, "g.yaml"), reference="ref.k", folded="short.k", output="g")
        rc, out3 = run(binary, d, "linkage-fit", "g.yaml")
        check("G-1 절점이 모자라면 rc=1", rc == 1, out3[-200:])
        check("G-2 몇 개가 없는지 말한다", "1개" in out3 or "1 개" in out3, out3[-200:])

        for name, args in (("G-3 reference 누락은 rc=1", dict(folded="fold.k", output="x")),
                           ("G-4 folded 누락은 rc=1", dict(reference="ref.k", output="x")),
                           ("G-5 output 누락은 rc=1", dict(reference="ref.k", folded="fold.k"))):
            write_cfg(os.path.join(d, "h.yaml"), **args)
            rc, o = run(binary, d, "linkage-fit", "h.yaml")
            check(name, rc == 1, o[-200:])
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
