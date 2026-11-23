#!/usr/bin/env python3
# battery 덱의 솔리드가 뒤집히지 않았는지(가운데 야코비안 양수 · info 의 Negative Jacobian 줄 없음) 보는 회귀 시험
"""battery 덱 솔리드의 방향 (2026-11-23 · 3차 7판 L-25 · 사용자 결정 「절점 차례를 바로 고친다」).

왜 이 시험이 있나.

  권취 덱의 바닥판(PID 101 · 솔리드 16)과 PCM(2030 · 9)이 통째로 뒤집혀 있었다 — 바닥판은 아래 면(n1 ~ n4)을 판의 위쪽 z 에 두었고,
  PCM 은 x · z 로 놓은 아래 면의 법선이 −y 인데 위 면을 +y 에 두었다. `info` 가 「Negative Jacobian elements: 25」 를 냈다(dent · side 의 권취
  48 덱 전부 · 적층은 괜찮다). 둘 다 강체라 솔버가 받는지는 못 쟀다(라이선스 만료). 이제 두 고정구의 요소 줄에서 두 면의 차례를 바꿔
  적층처럼 바로 놓는다 — 절점 좌표와 번호는 그대로다.

무엇을 보나.
  적층 dent · side · 권취 평평 · 나선 × dent · side · 권취 dent no_impactor(PCM 만) — rc 0 · 덱 하나
  ★솔리드마다 가운데 야코비안(트라이리니어 육면체)이 양수 · `info` 에 「Negative Jacobian」 줄이 없다

usage: test_battery_jacobian.py <KooRemapper 바이너리>
"""
import collections
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def neg_jacobians(path):
    """PART 별 (음수 개수, 전체 개수) — 8 절점 솔리드의 가운데 야코비안."""
    nodes, els, kw = {}, [], None
    for l in open(path, encoding="utf-8", errors="replace"):
        if l.startswith("*"):
            kw = l.split()[0].upper()
            continue
        if l.startswith("$") or not l.strip():
            continue
        if kw == "*NODE":
            nodes[int(l[0:8])] = (float(l[8:24]), float(l[24:40]), float(l[40:56]))
        elif kw == "*ELEMENT_SOLID":
            f = [int(l[i:i + 8]) for i in range(0, 80, 8) if l[i:i + 8].strip()]
            if len(f) >= 10:
                els.append(f)
    out = collections.defaultdict(lambda: [0, 0])
    for f in els:
        n = [nodes[x] for x in f[2:10]]
        d = [[sum(s * n[k][i] for k, s in enumerate(sg)) for i in range(3)]
             for sg in ((-1, 1, 1, -1, -1, 1, 1, -1), (-1, -1, 1, 1, -1, -1, 1, 1), (-1, -1, -1, -1, 1, 1, 1, 1))]
        det = (d[0][0] * (d[1][1] * d[2][2] - d[1][2] * d[2][1]) - d[0][1] * (d[1][0] * d[2][2] - d[1][2] * d[2][0])
               + d[0][2] * (d[1][0] * d[2][1] - d[1][1] * d[2][0]))
        out[f[1]][1] += 1
        if det < 0:
            out[f[1]][0] += 1
    return dict(out), len(nodes)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="bjac_")
    try:
        for tag, text in (("stacked dent", "model_type: stacked\nmode: dent\n"),
                          ("stacked side", "model_type: stacked\nmode: side\n"),
                          ("wound dent", "model_type: wound\nmode: dent\n"),
                          ("wound side", "model_type: wound\nmode: side\n"),
                          ("wound 나선 dent", "model_type: wound\nmode: dent\nwound:\n  flat: false\n"),
                          ("wound 나선 side", "model_type: wound\nmode: side\nwound:\n  flat: false\n"),
                          ("wound dent no_impactor", "model_type: wound\nmode: dent\nno_impactor: true\n")):
            d = os.path.join(root, tag.replace(" ", "_"))
            os.makedirs(d)
            with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
                f.write("output: bt\ntier: -1\n" + text)
            p = subprocess.run([binary, "battery", "b.yaml"], cwd=d, capture_output=True, text=True, timeout=900,
                               encoding="utf-8", errors="replace")
            ks = [os.path.join(d, x) for x in os.listdir(d) if x.endswith(".k")]
            if not check("%s → rc 0 · 덱 하나" % tag, p.returncode == 0 and len(ks) == 1, (p.returncode, (p.stdout + p.stderr)[-300:])):
                continue
            per, nn = neg_jacobians(ks[0])
            bad = {pid: c for pid, c in per.items() if c[0]}
            q = subprocess.run([binary, "info", ks[0]], capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace")
            neg_line = [l.strip() for l in (q.stdout + q.stderr).splitlines() if "Negative Jacobian" in l]
            check("★%s — 솔리드 %d 개 모두 가운데 야코비안 양수 · info 에 Negative Jacobian 줄 없음(예전 권취는 바닥판 · PCM 이 뒤집혔다)"
                  % (tag, sum(c[1] for c in per.values())), not bad and not neg_line, (bad, neg_line))
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
