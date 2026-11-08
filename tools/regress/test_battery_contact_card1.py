#!/usr/bin/env python3
# battery 덱의 접촉 Card 1(SSID MSID SSTYP MSTYP …)이 LS-DYNA 의 10칸 여덟으로 읽혀 뜻한 값이 되는지 보는 회귀 시험
"""battery 접촉 Card 1 의 칸 폭 (2026-11-08).

왜 이 시험이 있나.

  `*CONTACT_*` Card 1 은 10칸 여덟(SURFA SURFB SURFATYP SURFBTYP SABOXID SBBOXID SAPR SBPR)이다. 권취(wound) 덱만 `%8d` 여덟으로
  써서, 10칸으로 읽으면 넷째 칸(MSTYP)이 `" 2       0"`(MSTYP 2 의 끝과 SBOXID 0 이 한 칸)이었다 — dent 의 impactor 접촉
  (108 102 2 2)에서 뜻이 갈린다(빈칸을 무시하면 20). 적층(stacked) 덱은 처음부터 10칸이다. assemble 의 battery 가 번호를
  옮길 때도 이 칸을 고쳐 쓴다 — 표준 칸이어야 옮긴 번호를 제자리에 쓴다.

무엇을 보나 — 덱의 접촉마다 Card 1 을 10칸 여덟으로 잘라 칸마다 수 하나(가운데 빈칸 없음)이고, 값이 뜻한 것과 같다.
  wound dent(impactor 108/102/2/2 · 자기 접촉 102/0/2/0) · wound 기본(자기 접촉) · stacked dent(대조 — 처음부터 10칸)

usage: test_battery_contact_card1.py <KooRemapper 바이너리>
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


def card1s(path):
    """덱의 `*CONTACT_*_ID` 마다 (키워드, Card 1 줄) — ID 카드 다음의 첫 데이터 줄."""
    out, kw, k = [], None, 0
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("*"):
            kw = l.split()[0].upper() if l.upper().startswith("*CONTACT_") else None
            k = 0
            continue
        if kw is None or l.startswith("$"):
            continue
        k += 1
        if k == 2:
            out.append((kw, l))
    return out


def fields10(line):
    """10칸 여덟 — 칸마다 공백을 뺀 토큰 목록(둘 이상이면 칸이 어긋났다)."""
    return [line[i:i + 10].split() for i in range(0, 80, 10)]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="bcc1_")
    try:
        for name, src, mode, want in (
                ("wound dent", "wound/wound_swell.yaml", "dent",
                 {"*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID": [108, 102, 2, 2],
                  "*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID": [102, 0, 2, 0]}),
                ("wound 기본", "wound/wound_swell.yaml", None, {"*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID": [102, 0, 2, 0]}),
                ("stacked dent(대조)", "stacked/stacked_swell.yaml", "dent",
                 {"*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID": [100, 102, 3, 2],
                  "*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID": [102, 0, 2, 0]})):
            d = tempfile.mkdtemp(dir=root)
            t = open(os.path.join(REPO, "examples", "battery", "swell", src), encoding="utf-8").read()
            t = re.sub(r"^output:.*$", "output: b", t, count=1, flags=re.M)
            if mode:
                t = re.sub(r"^mode:.*$", "mode: " + mode, t, count=1, flags=re.M) if re.search(r"^mode:", t, re.M) \
                    else t + "\nmode: %s\n" % mode
            with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
                f.write(t)
            p = subprocess.run([binary, "battery", "b.yaml"], cwd=d, capture_output=True, text=True, timeout=900)
            decks = [f for f in os.listdir(d) if f.endswith(".k")]
            if not check("%s 덱을 짓는다" % name, p.returncode == 0 and len(decks) == 1, (p.returncode, p.stdout[-200:])):
                continue
            got = {}
            clean = True
            for kw, l in card1s(os.path.join(d, decks[0])):
                fs = fields10(l)
                clean = clean and all(len(x) <= 1 for x in fs)
                got[kw] = [int(x[0]) if x else 0 for x in fs[:4]] if all(len(x) <= 1 for x in fs) else l
            check("★%s — Card 1 을 10칸 여덟으로 자르면 칸마다 수 하나 · SSID MSID SSTYP MSTYP 가 뜻한 값(예전 wound 는 8칸)" % name,
                  clean and all(got.get(k) == v for k, v in want.items()), got)
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
