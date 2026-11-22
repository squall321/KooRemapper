#!/usr/bin/env python3
# battery contact.depth 가 자동 접촉 Card A 의 DEPTH 에 쓰이고 contact.soft 는 [WARN] 인지 재는 회귀 시험
"""battery contact.depth · contact.soft (2026-11-22 · 3차 6판 · 사용자 결정 「depth 만 덱에 쓰이게」).

왜 이 시험이 있나.

  설정의 contact.depth · contact.soft 를 읽기만 하고 덱에는 늘 DEPTH 5 · SOFT 1(면 대 면) · 2(셀 자기 접촉)를 썼다 — 키를 바꿔도
  덱이 그대로였다(rc 0 · 말없이). 이제 depth 는 모든 자동 접촉 Card A 의 DEPTH 칸(51~60열)에 쓴다(기본 5 라 안 준 덱은 같다).
  DEPTH 는 Vol_I 형 I — 음수는 하중 곡선 번호(덱에 없다)라, 정수가 아닌 값은 예전에 0 으로 읽혀 거절한다(rc 1 · 덱 없음).
  soft 는 접촉마다 달라 키 하나로 정하지 않는다 — 읽기만 두고 적으면 [WARN].

무엇을 보나(적층 · 권취 dent — 자동 접촉 둘씩).
  depth 를 안 주면 DEPTH 5 · soft 경고 없음
  ★depth: 3 → 모든 자동 접촉 DEPTH 3 · `info --strict` rc 0 · depth: 0 → DEPTH 0(LS-DYNA 기본)
  ★depth: -2 · 2.5 · abc · 1234567890 → rc 1 · 덱 없음 · 정수 0 이상을 말한다
  ★soft: 2 → rc 0 · [WARN] contact.soft · SOFT 칸은 그대로(면 대 면 1 · 자기 접촉 2)

usage: test_battery_contact_depth.py <KooRemapper 바이너리>
"""
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


def card_a(path):
    """덱의 `*CONTACT_AUTOMATIC_*` 마다 (키워드, SOFT 칸, DEPTH 칸) — 주석 뺀 다섯째 자료 줄(ID · Card 1 · 2 · 3 · A)."""
    out, cur = [], None
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("*"):
            cur = None
            if l.upper().startswith("*CONTACT_AUTOMATIC"):
                cur = [l.split()[0].upper(), []]
                out.append(cur)
            continue
        if cur is not None and not l.startswith("$"):
            cur[1].append(l)
    return [(kw, ls[4][0:10].strip(), ls[4][50:60].strip()) for kw, ls in out if len(ls) > 4]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="bcdp_")
    n = [0]

    def gen(mt, extra):
        n[0] += 1
        d = os.path.join(root, "c%d" % n[0])
        os.makedirs(d)
        with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
            f.write("output: bt\nmodel_type: %s\ntier: -1\nmode: dent\n%s" % (mt, extra))
        p = subprocess.run([binary, "battery", "b.yaml"], cwd=d, capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
        ks = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".k")]
        return p.returncode, p.stdout + p.stderr, ks

    try:
        for mt in ("stacked", "wound"):
            rc, out, ks = gen(mt, "")
            if check("%s · depth 안 줌 → rc 0 · 덱 하나" % mt, rc == 0 and len(ks) == 1, (rc, out[-300:])):
                ca = card_a(ks[0])
                check("%s · depth 안 줌 → 자동 접촉 %d 의 DEPTH 5 · contact.soft 경고 없음" % (mt, len(ca)),
                      len(ca) == 2 and all(c[2] == "5" for c in ca) and "contact.soft" not in out, (ca, out[-200:]))
            for v, want in (("3", "3"), ("0", "0")):
                rc, out, ks = gen(mt, "contact:\n  depth: %s\n" % v)
                if check("%s · depth: %s → rc 0 · 덱 하나" % (mt, v), rc == 0 and len(ks) == 1, (rc, out[-300:])):
                    ca = card_a(ks[0])
                    check("★%s · depth: %s → 자동 접촉 %d 의 DEPTH %s(예전엔 늘 5)" % (mt, v, len(ca), want),
                          len(ca) == 2 and all(c[2] == want for c in ca), ca)
                    if v == "3":
                        q = subprocess.run([binary, "info", ks[0], "--strict"], capture_output=True, text=True, timeout=900,
                                           encoding="utf-8", errors="replace")
                        check("%s · depth: 3 → info --strict rc 0" % mt, q.returncode == 0, (q.stdout + q.stderr)[-300:])
            for v in ("-2", "2.5", "abc", "1234567890"):   # 열 자리는 int 를 넘을 수 있다 — 예전 읽기는 0
                rc, out, ks = gen(mt, "contact:\n  depth: %s\n" % v)
                check("★%s · depth: %s → rc 1 · 덱 없음 · 정수 0 이상을 말한다(예전엔 rc 0 · 늘 5)" % (mt, v),
                      rc == 1 and not ks and "contact.depth" in out and "0 이상" in out, (rc, ks, out[-300:]))
            rc, out, ks = gen(mt, "contact:\n  soft: 2\n")
            if check("%s · soft: 2 → rc 0 · 덱 하나" % mt, rc == 0 and len(ks) == 1, (rc, out[-300:])):
                ca = card_a(ks[0])
                check("★%s · soft: 2 → [WARN] contact.soft · SOFT 칸 그대로(면 대 면 1 · 자기 접촉 2)" % mt,
                      "[WARN]" in out and "contact.soft" in out
                      and sorted(c[1] for c in ca) == ["1", "2"], (ca, [l for l in out.splitlines() if "soft" in l][:3]))
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
