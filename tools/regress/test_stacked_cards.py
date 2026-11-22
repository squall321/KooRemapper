#!/usr/bin/env python3
# 한 키워드 아래 쌓인 *SECTION · *HOURGLASS 묶음을 matswap · cclip · ale 가 잃거나 그 번호를 다시 내지 않는지 보는 회귀 시험(3차 3판 L-10)
"""쌓인 섹션 · 모래시계 묶음 (2026-11-22 · 미룬 결함 3차 3판 L-10).

왜 이 시험이 있나.

  LS-DYNA 는 한 키워드 아래 정의를 여러 벌 쌓는다(「The next card set or the next keyword」). 11-22 설치된 판(1106bef1)에서
  · matswap(YAML · 옛 자리 인자 두 꼴)이 바꿀 파트의 옛 `*SECTION` · `*HOURGLASS` 를 지울 때 **첫 묶음의 번호만** 보고 블록을 통째로 지워,
    같은 블록에 쌓인 다른 파트의 섹션 · 모래시계를 잃었다. 새 번호 셈도 첫 묶음만 세어, 번들 카드가 그 번호를 다시 받았다 — 옛 자리
    인자 꼴은 다른 파트(PID 2)가 번들의 고무 섹션(ELFORM 13)을, YAML 꼴은 번들의 모래시계를 조용히 가리켰다(rc 0)
  · cclip · ale 의 새 SECID(· ale 의 HGID) 셈이 첫 묶음만 세어 쌓인 묶음의 번호를 다시 낼 수 있었다
  이제 그 번호의 **묶음만** 지우고(블록이 비면 블록째), 새 번호는 쌓인 묶음까지 센 최대값 위로 낸다(조립기의 가르기 하나).

무엇을 보나 — 산출 덱을 묶음째 읽어
  A matswap 두 꼴 · 쌓인 섹션 · 모래시계 — rc 0 · PID 2 의 SECID 2 · HGID 2 가 정의돼 있고 원래 값(ELFORM 1 · IHQ 그대로)이다 · 번호 겹침 없음
  B matswap 두 꼴 · 쌓인 묶음의 뒤 번호(섹션 블록 [1, 3] + [2]) — 새 SECID 가 3 이 아니다 · 번호 겹침 없음 · SECID 3 이 남는다
  C cclip — 상자 섹션(SECID 2) 뒤에 SECID 3 을 쌓고 그것을 쓰는 파트 9 — SECID 3 이 원래 솔리드 섹션 그대로 남고 상자의 새 섹션은 3 이
    아니다(설치된 판은 블록째 지우고 새 셸 섹션에 3 을 줘 파트 9 가 그것을 조용히 가리켰다)
  D ale — 섹션 블록에 SECID 2 · 모래시계 블록에 HGID 2 를 쌓은 덱 — 새 SECID · HGID 가 겹치지 않는다(D2 — 섹션을 다른 파트와 나눠 써서
    ale 가 새 SECID 를 내는 덱)
  A · B · C 는 바꾼 파트의 옛 묶음이 지워졌는지도 본다(변이 — 지우기를 끈 판이 살아남았다)

usage: test_stacked_cards.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
from ops_help import OPS  # noqa: E402

FAILS, OKS = [], []
SPEC = {o["name"]: o for o in OPS}
ROWS = {"*SECTION_SOLID": 1, "*SECTION_SHELL": 2, "*HOURGLASS": 1, "*MAT_ELASTIC": 1, "*MAT_NULL": 1}


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def facts(text):
    """{'SEC': {id: [첫 줄 칸들…]}, 'HG': …, 'MID': …} 묶음마다(겹치면 리스트가 둘 이상) · 파트 (PID, SECID, MID, HGID)."""
    defs = {"SEC": {}, "HG": {}, "MID": {}}
    parts = []
    kw, rows = None, []

    def flush():
        if kw is None:
            return
        r = list(rows)
        while r and not r[-1].strip():
            r.pop()
        title = kw.endswith("_TITLE")
        base = kw[:-6] if title else kw
        if base == "*PART":
            for a in range(1, len(r), 2):
                f = [r[a][i:i + 10].strip() for i in range(0, 80, 10)]
                parts.append(tuple(int(x or 0) for x in (f[0], f[1], f[2], f[4])))
            return
        fam = "SEC" if base.startswith("*SECTION_") else "HG" if base == "*HOURGLASS" else \
            "MID" if base.startswith("*MAT_") and not base.startswith("*MAT_ADD") else None
        if fam is None:
            return
        n = ROWS.get(base)
        t = 1 if title else 0
        if n is None:            # 모르는 꼴 — 첫 묶음만
            if len(r) > t:
                defs[fam].setdefault(int(float(r[t][0:10])), []).append([r[t][i:i + 10].strip() for i in range(0, 80, 10)])
            return
        for a in range(0, len(r), t + n):
            if a + t < len(r) and r[a + t][0:10].strip():
                defs[fam].setdefault(int(float(r[a + t][0:10])), []).append([r[a + t][i:i + 10].strip() for i in range(0, 80, 10)])

    for l in text.split("\n"):
        l = l.rstrip("\r")
        if l.startswith("*"):
            flush()
            kw, rows = l.split()[0].upper(), []
            continue
        if l.startswith("$"):
            continue
        rows.append(l)
    flush()
    return defs, parts


def dups(defs):
    return {k: sorted(i for i, v in d.items() if len(v) > 1) for k, d in defs.items() if any(len(v) > 1 for v in d.values())}


def dangling(defs, parts):
    out = []
    for pid, sec, mid, hg in parts:
        if sec and sec not in defs["SEC"]:
            out.append("PID %d → SECID %d" % (pid, sec))
        if mid and mid not in defs["MID"]:
            out.append("PID %d → MID %d" % (pid, mid))
        if hg and hg not in defs["HG"]:
            out.append("PID %d → HGID %d" % (pid, hg))
    return out


def unstack(t, first, nth_title):
    """두 번째 키워드 줄(제목 nth_title 앞)을 지워 앞 블록에 쌓는다."""
    a = t.index(first + "\n" + nth_title)
    return t[:a] + t[a + len(first) + 1:]


def main():
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_stacked_")
    try:
        base = open(os.path.join(REPO, "examples", "matswap", "two_cubes.k"), encoding="utf-8").read()
        stacked = unstack(unstack(base, "*SECTION_SOLID_TITLE", "Section_2"), "*HOURGLASS_TITLE", "HG_2")
        line1 = "         1         1         0\n"
        a = base.index(line1) + len(line1)
        later = base[:a] + "Section_3\n         3         1         0\n" + base[a:]
        orig, _ = facts(base)
        for case, deck in (("A 쌓인 섹션 · 모래시계", stacked), ("B 쌓인 묶음의 뒤 번호", later)):
            for form in ("YAML", "옛 자리 인자"):
                d = os.path.join(top, "%s_%s" % (case[0], "y" if form == "YAML" else "o"))
                os.makedirs(d)
                with open(os.path.join(d, "m.k"), "w", encoding="utf-8") as f:
                    f.write(deck)
                shutil.copy(os.path.join(REPO, "examples", "matswap", "rubber.k"), d)
                if form == "YAML":
                    with open(os.path.join(d, "s.yaml"), "w", encoding="utf-8") as f:
                        f.write("model: m.k\noutput: out.k\nswaps:\n  - bundle: rubber.k\n    pid: 1\n")
                    rc, out = run(binary, d, "matswap", "s.yaml")
                else:
                    rc, out = run(binary, d, "matswap", "m.k", "rubber.k", "1", "out.k")
                name = "%s · matswap %s" % (case, form)
                if not check(name + " — rc 0", rc == 0 and os.path.exists(os.path.join(d, "out.k")), out[-300:]):
                    continue
                defs, parts = facts(open(os.path.join(d, "out.k"), encoding="utf-8").read())
                check(name + " — 번호 겹침 없음 · 파트의 참조가 다 정의돼 있다", not dups(defs) and not dangling(defs, parts),
                      (dups(defs), dangling(defs, parts)))
                p2 = [p for p in parts if p[0] == 2]
                if case.startswith("A"):
                    ok = p2 and p2[0][1] == 2 and p2[0][3] == 2 and defs["SEC"].get(2) == orig["SEC"][2] and \
                        defs["HG"].get(2) == orig["HG"][2]
                    check(name + " — PID 2 의 SECID 2 · HGID 2 가 원래 값 그대로다", ok,
                          (p2, defs["SEC"].get(2), defs["HG"].get(2)))
                    check(name + " — 바꾼 파트의 옛 SECID 1 · HGID 1 묶음은 지웠다(쌓인 블록에서 그 묶음만)",
                          1 not in defs["SEC"] and 1 not in defs["HG"], (sorted(defs["SEC"]), sorted(defs["HG"])))
                else:
                    p1 = [p for p in parts if p[0] == 1]
                    check(name + " — SECID 3 이 남고 새 SECID 는 3 이 아니다", 3 in defs["SEC"] and p1 and p1[0][1] not in (1, 2, 3),
                          (sorted(defs["SEC"]), p1))
                    check(name + " — 바꾼 파트의 옛 SECID 1 묶음은 지웠다(같은 블록의 3 은 남는다)", 1 not in defs["SEC"], sorted(defs["SEC"]))

        print("[C — cclip]")
        cc = SPEC["cclip"]["files"]
        d = os.path.join(top, "cclip")
        os.makedirs(d)
        for fn, content in cc.items():
            with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
                f.write(content)
        run(binary, d, "generate", "box", "board.yaml")
        p = os.path.join(d, "clip_board.k")
        t = open(p, encoding="utf-8").read()
        L = t.split("\n")
        k = next(i for i, l in enumerate(L) if l.upper().startswith("*SECTION_SOLID"))
        k += 1 + (1 if L[k].upper().startswith("*SECTION_SOLID_TITLE") else 0)
        while L[k].startswith("$"):
            k += 1
        L.insert(k + 1, "%10d%10d" % (3, 1))        # 상자 섹션(Card 1 한 줄) 바로 뒤에 SECID 3 을 쌓는다
        t = "\n".join(L)
        t = t.replace("*END", "*PART\nextra\n%10d%10d%10d\n*END" % (9, 3, 2), 1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(t)
        before, _ = facts(t)
        rc, out = run(binary, d, "cclip", "cclip.yaml")
        o = os.path.join(d, "clip_board_cclip.k")
        if check("C cclip · 쌓인 섹션(SECID 2 · 3) — rc 0 · 입력에 SECID 3 이 쌓여 있다", rc == 0 and os.path.exists(o) and 3 in before["SEC"],
                 (rc, sorted(before["SEC"]), out[-300:])):
            defs, parts = facts(open(o, encoding="utf-8").read())
            box = [q for q in parts if q[0] == 2]
            check("C cclip — 쌓인 SECID 3 이 원래 솔리드 섹션(ELFORM 1) 그대로 하나 · 상자의 새 섹션은 3 이 아니다 · 겹침 없음",
                  defs["SEC"].get(3, [[]])[0][:2] == ["3", "1"] and len(defs["SEC"].get(3, [])) == 1 and box and box[0][1] != 3
                  and not dups(defs), (defs["SEC"].get(3), box, dups(defs)))
            check("C cclip — 상자의 옛 SECID 2 묶음은 지웠다(같은 블록에 쌓인 3 은 남는다)", 2 not in defs["SEC"], sorted(defs["SEC"]))

        print("[D — ale]")
        al = SPEC["ale"]["files"]
        d = os.path.join(top, "ale")
        os.makedirs(d)
        for fn, content in al.items():
            with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
                f.write(content)
        run(binary, d, "generate", "box", "box.yaml")
        p = os.path.join(d, "box.k")
        t = open(p, encoding="utf-8").read()
        sec = t.index("*SECTION_SOLID")
        nxt = t.index("\n*", sec + 1) + 1
        t = t[:nxt] + "%10d%10d\n" % (2, 1) + t[nxt:]              # 첫 카드(SECID 1)만 세면 새 SECID 가 2 로 겹친다
        t = t.replace("*END", "*HOURGLASS\n%10d%10d\n%10d%10d\n*END" % (1, 6, 2, 6), 1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(t)
        rc, out = run(binary, d, "ale", "ale.yaml")
        o = os.path.join(d, "box_ale.k")
        if check("D ale · 쌓인 SECID 2 · HGID 2 — rc 0", rc == 0 and os.path.exists(o), out[-300:]):
            defs, parts = facts(open(o, encoding="utf-8").read())
            check("D ale — SECID · HGID 겹침 없음(쌓인 2 위로 냈다)", not dups(defs).get("SEC") and not dups(defs).get("HG")
                  and 2 in defs["SEC"] and 2 in defs["HG"], (sorted(defs["SEC"]), sorted(defs["HG"]), dups(defs)))
        # D2 — 다른 파트(9)가 ALE 파트의 섹션 1 을 나눠 쓰면 ale 는 새 SECID 를 낸다 — 쌓인 2 위로
        with open(p, "w", encoding="utf-8") as f:
            f.write(t.replace("*END", "*PART\nshared\n%10d%10d%10d\n*END" % (9, 1, 1), 1))
        rc, out = run(binary, d, "ale", "ale.yaml")
        if check("D2 ale · 섹션 1 을 파트 9 와 나눠 씀 · 쌓인 SECID 2 — rc 0", rc == 0 and os.path.exists(o), out[-300:]):
            defs, parts = facts(open(o, encoding="utf-8").read())
            p1 = [q for q in parts if q[0] == 1]
            check("D2 ale — 새 SECID 가 1 · 2 가 아니고 겹침 없음", p1 and p1[0][1] not in (1, 2) and not dups(defs).get("SEC"),
                  (p1, sorted(defs["SEC"]), dups(defs)))
    finally:
        shutil.rmtree(top, ignore_errors=True)
    print()
    if FAILS:
        print("FAIL — %d 항 실패 / %d" % (len(FAILS), len(FAILS) + len(OKS)))
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL PASS — %d 항" % len(OKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
