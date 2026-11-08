#!/usr/bin/env python3
# battery 덱의 접촉 선택 카드가 매뉴얼 차례 · 꼴(Card A · B · C)로 쓰여 IGNORE 가 Card C 에서 먹고 PENMAX 는 기본값인지 보는 회귀 시험
"""battery 접촉의 선택 카드 (2026-11-08 · 6차 검토 P2 — 물성이 바뀌는 기존 결함).

왜 이 시험이 있나.

  `*CONTACT` 의 카드 차례는 ID · (MPP 1 · 2 — _MPP 옵션일 때 Card 1 앞) · Card 1 · 2 · 3 · 선택 Card A · B · C … 다(Vol_I *CONTACT
  「Cards must appear in the exact order listed below」). battery 쓰개는 Card A 다음에 MPP Card 1 꼴(IGNORE BCKT LCBCKT NS2TRK
  INITITR …)의 줄을 「Card C」 라며 썼는데, 그 자리는 Card B(PENMAX THKOPT SHLTHK SNLOG ISYM I2D3D SLDTHK SLDSTF)다 — LS-DYNA 는
  PENMAX = 1 로 읽고 IGNORE 는 어디에도 없었다(LS-PrePost 4.12 로 다시 써 보면 그 줄이 penmax 1.0 으로 나온다). 이제 Card B 는
  기본값(PENMAX 0.0)이고 IGNORE = 1 은 Card C(IGAP IGNORE DPRFAC DTSTIF EDGEK · 빈 칸 · FLANGL CID_RCF)의 둘째 칸이다.
  번호 옮기기(assemble battery)도 그 줄의 21~30열을 LCBCKT 로 보아 곡선처럼 옮기던 것을 그만둔다(매뉴얼의 Card B 에서는 SHLTHK).

무엇을 보나(덱마다 `*CONTACT_AUTOMATIC_*` 접촉 — 적층 dent · 기본, 권취 dent · 기본).
  · 칸 읽기(이 파일 — C++ 와 따로): Card A 뒤에 카드가 있으면 Card B 의 PENMAX(1~10열)는 0, Card C 의 IGNORE(11~20열)는 1
  · 우리 리더(`contact analyze`)도 같은 뜻으로 읽는다 — 「Card B:」 에 PENMAX 가 없고 「Card C: IGNORE=1」
  · 권취 dent 의 압입자 접촉(Card A 만)은 그대로

usage: test_battery_contact_optional_cards.py <KooRemapper 바이너리>
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
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def contacts(path):
    """덱의 `*CONTACT_AUTOMATIC_*` 마다 (키워드, 데이터 줄들[주석 뺌]) — ID · Card 1 · 2 · 3 · A · B · C 차례."""
    out, cur = [], None
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("*"):
            cur = None
            if l.upper().startswith("*CONTACT_AUTOMATIC"):
                cur = (l.split()[0].upper(), [])
                out.append(cur)
            continue
        if cur is not None and not l.startswith("$"):
            cur[1].append(l)
    return out


def real(s):
    s = s.strip()
    return 0.0 if not s else float(s)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="bcoc_")
    try:
        for name, src, mode, want in (
                ("적층 dent", "stacked/stacked_swell.yaml", "dent",
                 {"*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID": True, "*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID": True}),
                ("적층 기본", "stacked/stacked_swell.yaml", None, {"*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID": True}),
                ("권취 dent", "wound/wound_swell.yaml", "dent",
                 {"*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID": False, "*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID": True}),
                ("권취 기본", "wound/wound_swell.yaml", None, {"*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID": True})):
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
            deck = os.path.join(d, decks[0])
            got = {}
            for kw, ls in contacts(deck):
                if len(ls) <= 5:
                    got[kw] = "A 만"
                    continue
                try:
                    got[kw] = (len(ls), real(ls[5][0:10]), int(ls[6][10:20]) if len(ls) > 6 else None)
                except ValueError as e:
                    got[kw] = "못 읽음: %s" % e
            ok = all((got.get(kw) == (7, 0.0, 1)) if bc else got.get(kw) == "A 만" for kw, bc in want.items())
            check("★%s — Card B 의 PENMAX(1~10열) 0 · Card C 의 IGNORE(11~20열) 1(예전엔 Card B 자리에 IGNORE 1 → PENMAX 1)" % name,
                  ok, got)
            with open(os.path.join(d, "c.yaml"), "w", encoding="utf-8") as f:
                f.write("model: %s\noutput: c_out.k\ncontacts:\n  - action: analyze\n" % decks[0])
            p = subprocess.run([binary, "contact", "c.yaml"], cwd=d, capture_output=True, text=True, timeout=900)
            text = p.stdout + p.stderr
            n_bc = sum(1 for bc in want.values() if bc)
            check("★%s — 우리 리더(contact analyze)도 Card B 에 PENMAX 가 없고 Card C: IGNORE=1 로 읽는다" % name,
                  p.returncode == 0 and "PENMAX=" not in text and text.count("Card C: IGNORE=1") == n_bc,
                  (p.returncode, re.findall(r"Card [BC]:[^\n]*", text)))
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
