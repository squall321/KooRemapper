#!/usr/bin/env python3
# 적층 battery 의 탭이 셀 밖이면 짓기 전에 거절하고, 셀 끝에 걸친 탭도 덱에 있는 절점만 가리키는지 보는 회귀 시험
"""적층 battery 의 탭 자리 (2026-11-08).

왜 이 시험이 있나.

  탭 줄(createTabStrip)은 셀 위 가장자리(+Y) 격자 열에서 뻗는다. 기본 탭 중심(17.5 · 52.5)은 폭 70 셀 기준이라 폭 30 셀이면 음극
  탭이 셀 밖인데, 시작 열을 nx 까지 허락해 ixEnd = nx+1 — 격자 (ny+1)×(nx+1) 밖을 읽어 **덱에 없는 절점 번호**(실측 174421089 ·
  `info` 가 「정의되지 않은 것을 가리키는 카드」)를 쓰고 rc 0 이었다. 셀 끝에 조금 걸친 탭(xLo/dx 가 nx 로 반올림)도 같았다.
  이제 셀 밖 탭은 짓기 전에 rc 1 · 끝에 걸친 탭은 격자 안 마지막 열에서 뻗는다.

무엇을 보나.
  T-1 폭 30 셀 · 기본 탭(음극 47.5~57.5) → rc 1 · 음극 탭 · neg_x_center 를 말한다 · 덱 없음
  T-2 폭 30 셀 · neg_x_center 33(28~38 — 끝에 걸친다) → rc 0 · 요소 · 세트가 가리키는 절점이 다 덱에 있다
  대조 C-1 예제(폭 70) 그대로 · C-2 no_pcm: true 면 탭을 짓지 않아 폭 30 · 기본 탭도 rc 0

usage: test_battery_tab_in_cell.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def dangling_nodes(path):
    """덱에 정의되지 않은 절점을 가리키는 요소 줄(8칸 열) · 세트 멤버(10칸 열)의 수 — 칸이 붙어 못 읽으면 그 줄도 센다."""
    nodes, refs, bad = set(), [], 0
    kw = None
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("*"):
            kw = l.split()[0].upper()
            continue
        if kw is None or l.startswith("$"):
            continue
        try:
            if kw == "*NODE":
                nodes.add(int(l[0:8]))
            elif kw in ("*ELEMENT_SHELL", "*ELEMENT_SOLID", "*ELEMENT_TSHELL"):
                refs.extend(int(l[a:a + 8]) for a in range(16, len(l), 8) if l[a:a + 8].strip())
        except ValueError:
            bad += 1
    return bad + sum(1 for r in refs if r and r not in nodes)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    src = open(os.path.join(REPO, "examples", "battery", "swell", "stacked", "stacked_swell.yaml"), encoding="utf-8").read()
    src = re.sub(r"^output:.*$", "output: bt", src, count=1, flags=re.M)
    small = ("output: bt\nmodel_type: stacked\ntier: -1\nphase: 1\ngeometry:\n  cell_width: 30\n  cell_height: 30\n"
             "  n_unit_cells: 1\n")
    root = tempfile.mkdtemp(prefix="btab_")
    try:
        def case(k, text):
            d = os.path.join(root, "c%d" % k)
            os.makedirs(d)
            with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
                f.write(text)
            p = subprocess.run([binary, "battery", "b.yaml"], cwd=d, capture_output=True, text=True, timeout=900,
                               encoding="utf-8", errors="replace")
            ks = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".k")]
            return p.returncode, p.stdout + p.stderr, ks

        rc, out, ks = case(1, small)
        check("★T-1 폭 30 셀 · 기본 탭(음극 47.5~57.5) → rc 1 · 음극 탭 · neg_x_center 를 말한다 · 덱 없음(예전엔 rc 0 에 없는 절점)",
              rc == 1 and "음극 탭" in out and "neg_x_center" in out and not ks,
              (rc, [dangling_nodes(k) for k in ks], out[-300:]))
        rc, out, ks = case(2, small + "tabs:\n  neg_x_center: 33\n")
        check("★T-2 폭 30 셀 · neg_x_center 33(끝에 걸친다) → rc 0 · 요소가 가리키는 절점이 다 덱에 있다(예전엔 격자 밖을 읽었다)",
              rc == 0 and len(ks) == 1 and dangling_nodes(ks[0]) == 0, (rc, [dangling_nodes(k) for k in ks], out[-300:]))
        rc, out, ks = case(3, src)
        check("C-1 대조 — 예제(폭 70) 그대로 rc 0 · 끊긴 절점 없음", rc == 0 and len(ks) == 1 and dangling_nodes(ks[0]) == 0,
              (rc, out[-300:]))
        rc, out, ks = case(4, small + "no_pcm: true\n")
        check("C-2 대조 — no_pcm: true 면 탭을 짓지 않는다 — 폭 30 · 기본 탭도 rc 0 · 끊긴 절점 없음",
              rc == 0 and len(ks) == 1 and dangling_nodes(ks[0]) == 0, (rc, out[-300:]))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
