#!/usr/bin/env python3
# matdb 가 한 키워드 아래 쌓인 둘째 재질을 고르고, 지우기만 하는 고아 재질의 *MAT_ADD_* 를 남기지 않는지 보는 회귀 시험(3차 3판 L-11)
"""matdb 의 쌓인 재질 · 고아 재질의 덧붙임 (2026-11-22 · 미룬 결함 3차 3판 L-11).

왜 이 시험이 있나.

  11-22 설치된 판(1106bef1)에서
  · matdb 의 재질 훑기가 `*MAT_` 키워드마다 첫 묶음 하나만 봐서, 한 키워드 아래 쌓인 둘째 재질은 제목 맞추기 · `mid:` 규칙으로 고를 수 없었다
    (「No materials matched」 · rc 0 · 그대로 남았다)
  · 모든 파트가 새 MID 로 옮겨 지우기만 하는 고아 재질은 지웠지만 그 MID 의 `*MAT_ADD_EROSION` 같은 덧붙임을 남겨, 덱이 없는 재질을
    가리켰다(rc 0). matswap 은 같은 경우 덧붙임도 지운다
  이제 재질 묶음마다 맞춰 보고(공용 재질 훑기 `matids::scan`), 고아 재질의 MID 꼴 덧붙임을 지운다. 바꿔 넣는 MID 의 덧붙임은 예전처럼 남아
  새 DB 재질에 붙는다.

무엇을 보나(상자 덱 — MID 1 「Unknownium」 뒤에 MID 2 「SUS304 plate」 를 쌓고 파트 2 가 MID 2)
  A `match: "SUS304"` — rc 0 · 「No materials matched」 가 없다 · MID 2 가 DB 카드로 바뀌었다(제목이 「SUS304 plate」 가 아니다) · MID 1 은
    원래 값 그대로 하나 · 파트 1 · 2 의 MID 가 정의돼 있다
  B `match_part: "PLATE"` + `*MAT_ADD_EROSION` MID 1 — rc 0 · MID 1 정의가 없고 그 MID 를 가리키는 `*MAT_ADD_EROSION` 도 없다 · 파트의 새 MID 가
    정의돼 있다
  C `match: "*"` 대조 — 덧붙임이 있는 MID 를 바꿔 넣으면 덧붙임은 남는다(예전 그대로)

usage: test_matdb_stacked.py <KooRemapper 바이너리>
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
BOX = {o["name"]: o for o in OPS}["warpage"]["files"]["box.yaml"]


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def facts(text):
    """MID → [(제목, 첫 카드 칸들)] · 파트 [(PID, MID)] · *MAT_ADD_EROSION 의 MID 들."""
    mats, parts, ero = {}, [], []
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
                parts.append((int(r[a][0:10]), int(r[a][20:30] or 0)))
        elif base == "*MAT_ADD_EROSION":
            ero.append(int(r[0][0:10]))
        elif base == "*MAT_ELASTIC":
            t = 1 if title else 0
            for a in range(0, len(r), t + 1):
                mats.setdefault(int(r[a + t][0:10]), []).append((r[a].strip() if title else "", r[a + t][10:40].split()))
        elif base.startswith("*MAT_") and not base.startswith("*MAT_ADD") and r:
            t = 1 if title else 0
            mats.setdefault(int(float(r[t][0:10])), []).append((r[0].strip() if title else "", r[t][10:40].split()))

    for l in text.split("\n"):
        l = l.rstrip("\r")
        if l.startswith("*"):
            flush()
            kw, rows = l.split()[0].upper(), []
        elif not l.startswith("$"):
            rows.append(l)
    flush()
    return mats, parts, ero


def setup(binary, top, name, edit, yaml_text):
    d = os.path.join(top, name)
    os.makedirs(d)
    with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
        f.write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    p = os.path.join(d, "box.k")
    t = edit(open(p, encoding="utf-8").read())
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)
    with open(os.path.join(d, "m.yaml"), "w", encoding="utf-8") as f:
        f.write(yaml_text)
    rc, out = run(binary, d, "matdb", "m.yaml")
    o = os.path.join(d, "out.k")
    return rc, out, (open(o, encoding="utf-8").read() if os.path.exists(o) else None), t


def stacked(t):
    t = t.replace("*MAT_ELASTIC\n", "*MAT_ELASTIC_TITLE\nUnknownium\n", 1)
    j = t.index("*SECTION_SOLID")
    t = t[:j] + "SUS304 plate\n%10d%10.3e%10.1f%10.3f\n" % (2, 7.9e-9, 193000.0, 0.29) + t[j:]
    return t.replace("*END", "*PART\nsecond\n%10d%10d%10d\n*END" % (2, 1, 2), 1)


def erosion(t):
    return t.replace("*END", "*MAT_ADD_EROSION\n%10d%10.1f\n%10.1f%10.1f%10.3f\n*END" % (1, 0.0, 0.0, 0.0, 0.5), 1)


def main():
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_matdbst_")
    try:
        head = "model: box.k\noutput: out.k\nmat_type: MAT_ELASTIC\nmaterials:\n"
        rc, out, txt, inp = setup(binary, top, "a", stacked, head + "  - match: \"SUS304\"\n")
        if check("A 쌓인 둘째 재질 · match SUS304 — rc 0 · 산출", rc == 0 and txt is not None, out[-300:]):
            mats, parts, _ = facts(txt)
            orig, _, _ = facts(inp)
            check("A — 「No materials matched」 가 없다", "No materials matched" not in out, out[-300:])
            check("A — MID 2 가 하나 · DB 카드로 바뀌었다(제목이 「SUS304 plate」 가 아니다)",
                  len(mats.get(2, [])) == 1 and mats[2][0][0] != "SUS304 plate", mats.get(2))
            check("A — MID 1 은 원래 값 그대로 하나", mats.get(1) == orig.get(1) and len(mats.get(1, [])) == 1, (mats.get(1), orig.get(1)))
            check("A — 파트 1 · 2 의 MID 가 정의돼 있다", all(m in mats for _, m in parts), (parts, sorted(mats)))
        rc, out, txt, _ = setup(binary, top, "b", erosion, head + "  - match_part: \"PLATE\"\n    match: \"SUS304\"\n")
        if check("B 고아 MID 1 + *MAT_ADD_EROSION — rc 0 · 산출", rc == 0 and txt is not None, out[-300:]):
            mats, parts, ero = facts(txt)
            check("B — MID 1 정의가 없고 그 MID 를 가리키는 *MAT_ADD_EROSION 도 없다", 1 not in mats and 1 not in ero, (sorted(mats), ero))
            check("B — 파트의 새 MID 가 정의돼 있다", parts and all(m in mats for _, m in parts), (parts, sorted(mats)))
        rc, out, txt, _ = setup(binary, top, "c", erosion, head + "  - match: \"*\"\n")
        if check("C 바꿔 넣는 MID 1 + *MAT_ADD_EROSION — rc 0 · 산출", rc == 0 and txt is not None, out[-300:]):
            mats, parts, ero = facts(txt)
            if 1 in mats:
                check("C — 바꿔 넣은 MID 1 의 덧붙임은 남는다(새 재질에 붙는다 · 예전 그대로)", 1 in ero, (sorted(mats), ero))
            else:
                check("C — (대조) DB 에 맞는 재질이 없어 바꿔 넣지 않았다 — 덧붙임은 그대로", 1 in ero, (sorted(mats), ero, out[-200:]))
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
