#!/usr/bin/env python3
# 쌓인 재질 묶음 · 모르는 꼴 재질 · 사용자 재료 파일 · LONG 2차 솔리드를 리더 · iga · ale 가 제대로 읽는지 보는 회귀 시험(3차 3판 L-12)
"""재질 묶음 읽기 (2026-11-22 · 미룬 결함 3차 3판 L-12).

왜 이 시험이 있나 — 11-22 설치된 판(1106bef1)에서
  · 리더가 `*MAT_ELASTIC` · `*MAT_PIECEWISE_LINEAR_PLASTICITY` · `*MAT_RIGID` 블록의 첫 묶음만 읽었다 — 쌓인 둘째 재질을 쓰는 파트는
    prestress 가 「Material 2: NOT FOUND — stress will be 0」(rc 0). 빈 카드(`*MAT_RIGID` Card 2 · 3)와 빈 `_TITLE` 제목 줄을 건너뛰어
    다음 줄을 이 묶음의 카드로 셌다
  · iga 가 카드 수를 모르는 꼴의 재질(`*MAT_JOHNSON_COOK`)을 블록 끝까지 베껴, 같은 블록에 쌓인 다른 재질(MID 2)까지 IGA 인클루드에
    실었다(그 MID 가 둘 · rc 0)
  · ale 의 사용자 재료 파일은 첫 `*MAT_` 블록을 통째로 베꼈다 — `*MAT_ADD_EROSION` 이 앞이면 그것을 재질로 싣고, `_TITLE` 재질은
    제목 줄에 새 MID 를 써 Card 1 의 옛 MID 가 남았다
  · LONG=Y 덱의 2차 솔리드(HEX20)를 리더 · 참조 검사가 10 칸으로 훑어 2차 파트를 못 알아봐 두 줄 꼴 요소를 한 줄 꼴로 읽었다(100 → 200
    요소 · 정의 안 된 파트 100 · 음의 야코비안)

무엇을 보나
  A 리더 — 쌓인 `*MAT_ELASTIC` [1, 2] · 쌓인 `*MAT_RIGID_TITLE`(빈 제목 · 빈 Card 2 · 3) [3, 4] — prestress 의 파트-재질 표에 넷 다 있다
  B iga — 쌓인 `*MAT_JOHNSON_COOK` [1, 2](파트 2 가 MID 2) rc 1 · 까닭에 「쌓여 있다」 · 산출 없음 / 하나뿐이면 rc 0 · IGA 파일에 재질 묶음
    하나
  C ale 재료 파일 — `*MAT_ADD_EROSION` 다음 `*MAT_NULL_TITLE`(제목 · MID 7) · `*EOS_LINEAR_POLYNOMIAL` — 산출의 새 재질은 `*MAT_NULL` 이고 Card 1
    첫 칸이 새 MID · 제목 줄은 그대로 · `*MAT_ADD_EROSION` 은 싣지 않는다
  D LONG=Y HEX20 상자 — info 의 요소 100 · 미정의 참조 0 · 음의 야코비안 없음(표준 덱과 같다)

usage: test_material_sets.py <KooRemapper 바이너리>
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
import test_long_readers as L  # noqa: E402 — 표준 → LONG
from ops_help import OPS  # noqa: E402

FAILS, OKS = [], []
SP = {o["name"]: o for o in OPS}
BOX = SP["warpage"]["files"]["box.yaml"]


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def row(*v):
    return "".join(("%10d" % x) if isinstance(x, int) else ("%10.4g" % x) for x in v) + "\n"


def box(binary, top, name):
    d = os.path.join(top, name)
    os.makedirs(d)
    with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
        f.write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    return d, open(os.path.join(d, "box.k"), encoding="utf-8").read()


def four_parts(t):
    """상자 100 요소를 PID 1 ~ 4 로 나눈다(25 개씩)."""
    out, kw = [], ""
    for l in t.split("\n"):
        if l.startswith("*"):
            kw = l.split()[0]
        elif kw == "*ELEMENT_SOLID" and l.strip() and not l.startswith("$"):
            l = l[:8] + "%8d" % ((int(l[:8]) - 1) // 25 + 1) + l[16:]
        out.append(l)
    return "\n".join(out)


def main():
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_matsets_")
    try:
        print("[A — 리더의 쌓인 재질]")
        d, t = box(binary, top, "a")
        j = t.index("*SECTION_SOLID")
        t = t[:j] + row(2, 2.7e-9, 70000.0, 0.33) + "*MAT_RIGID_TITLE\n\n" + row(3, 7.8e-9, 200000.0, 0.3) + "\n\n" + \
            "rigid four\n" + row(4, 7.8e-9, 190000.0, 0.29) + "\n\n" + t[j:]
        t = four_parts(t).replace("*END", "*PART\np2\n%s*PART\np3\n%s*PART\np4\n%s*END" % (row(2, 1, 2), row(3, 1, 3), row(4, 1, 4)), 1)
        with open(os.path.join(d, "box.k"), "w", encoding="utf-8") as f:
            f.write(t)
        rc, out = run(binary, d, "prestress", "box.k", "box.k", "pre")
        rows = [l.strip() for l in out.splitlines() if "-> Material" in l]
        want = {1: "2.1000e+05", 2: "7.0000e+04", 3: "2.0000e+05", 4: "1.9000e+05"}
        got = {k: any(("Part %d -> Material %d: E=%s" % (k, k, e)) in r for r in rows) for k, e in want.items()}
        check("A prestress 의 파트-재질 표 — 넷 다 있고 E 가 맞다(쌓인 ELASTIC 둘째 · 빈 제목 · 빈 카드의 RIGID 둘)", rc == 0 and all(got.values()),
              (rc, rows))

        print("[B — iga 의 모르는 꼴 재질]")
        for stacked in (True, False):
            d, t = box(binary, top, "b%d" % stacked)
            i, j = t.index("*MAT_ELASTIC"), t.index("*SECTION_SOLID")
            jc = "*MAT_JOHNSON_COOK\n"
            for mid in ((1, 2) if stacked else (1,)):
                jc += row(mid, 7.85e-9, 80000.0, 210000.0, 0.3) + row(250.0, 400.0, 0.3, 0.01, 1.0) + row(4.5e8, 0.0, 2.0, 0) + row(0.0, 0.0, 0.0)
            t = t[:i] + jc + t[j:]
            if stacked:
                t = t.replace("*END", "*PART\nsecond\n%s*END" % row(2, 1, 2), 1)
            with open(os.path.join(d, "box.k"), "w", encoding="utf-8") as f:
                f.write(t)
            with open(os.path.join(d, "iga.yaml"), "w", encoding="utf-8") as f:
                f.write(SP["iga"]["files"]["iga.yaml"])
            rc, out = run(binary, d, "iga", "iga.yaml")
            igaf = [f for f in os.listdir(d) if "_iga_p" in f]
            if stacked:
                check("B 쌓인 *MAT_JOHNSON_COOK [1, 2] — rc 1 · 까닭에 「쌓여 있다」 · IGA 파일 없음",
                      rc == 1 and "쌓여 있다" in out and not igaf, (rc, out[-300:], igaf))
            else:
                ok = rc == 0 and igaf
                if ok:
                    txt = open(os.path.join(d, igaf[0]), encoding="utf-8").read()
                    blk = txt[txt.index("*MAT_JOHNSON_COOK"):]
                    blk = blk[:blk.index("\n*", 1)]
                    data = [l for l in blk.split("\n")[1:] if l.strip() and not l.startswith("$")]
                    ok = len(data) == 4
                check("B 하나뿐인 *MAT_JOHNSON_COOK — rc 0 · IGA 파일에 재질 묶음 하나(4 줄)", ok, (rc, out[-200:]))

        print("[C — ale 사용자 재료 파일]")
        d = os.path.join(top, "c")
        os.makedirs(d)
        with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
            f.write(SP["ale"]["files"]["box.yaml"])
        run(binary, d, "generate", "box", "box.yaml")
        with open(os.path.join(d, "fluid.k"), "w", encoding="utf-8") as f:
            f.write("*KEYWORD\n*MAT_ADD_EROSION\n" + row(7, 0.0) + row(0.0, 0.0, 0.5) + "*MAT_NULL_TITLE\nmy fluid\n" +
                    row(7, 1.0e-9, 0.0, 0.0) + "*EOS_LINEAR_POLYNOMIAL\n" + row(3, 0.0, 2200.0) + row(0.0, 0.0, 1.0) + "*END\n")
        with open(os.path.join(d, "ale.yaml"), "w", encoding="utf-8") as f:
            f.write("model: box.k\noutput: box_ale.k\nale_parts:\n  - pid: 1\n    material: fluid.k\n")
        rc, out = run(binary, d, "ale", "ale.yaml")
        o = os.path.join(d, "box_ale.k")
        if check("C ale 재료 파일(덧붙임이 앞 · _TITLE 재질) — rc 0", rc == 0 and os.path.exists(o), out[-300:]):
            txt = open(o, encoding="utf-8").read()
            ls = txt.split("\n")
            k = next((i for i, l in enumerate(ls) if l.upper().startswith("*MAT_NULL_TITLE")), None)
            part = ""
            for i, l in enumerate(ls):
                if not l.startswith("*PART"):
                    continue
                rows = [x for x in ls[i + 1:i + 6] if not x.startswith("$")]
                if len(rows) > 1 and rows[1][:10].strip() == "1":
                    part = rows[1]
                    break
            newmid = part[20:30].strip()
            ok = k is not None and ls[k + 1].strip() == "my fluid" and ls[k + 2][:10].strip() == newmid and newmid not in ("", "7")
            check("C — 새 재질은 *MAT_NULL_TITLE · 제목 그대로 · Card 1 첫 칸이 파트의 새 MID", ok,
                  (ls[k:k + 3] if k is not None else None, part))
            check("C — *MAT_ADD_EROSION 은 싣지 않는다", "*MAT_ADD_EROSION" not in txt.upper(), "")
        # C2 — 재료 파일에 구조 재질이 둘이면 첫 것(*MAT_NULL_TITLE 7)만 싣고 다른 하나를 알린다
        with open(os.path.join(d, "fluid.k"), "w", encoding="utf-8") as f:
            f.write("*KEYWORD\n*MAT_NULL_TITLE\nmy fluid\n" + row(7, 1.0e-9, 0.0, 0.0) + "*MAT_ELASTIC\n" + row(8, 7.85e-9, 2.1e5, 0.3) +
                    "*EOS_LINEAR_POLYNOMIAL\n" + row(3, 0.0, 2200.0) + row(0.0, 0.0, 1.0) + "*END\n")
        rc, out = run(binary, d, "ale", "ale.yaml")
        if check("C2 ale 재료 파일에 구조 재질 둘 — rc 0", rc == 0 and os.path.exists(o), out[-300:]):
            txt = open(o, encoding="utf-8").read().upper()
            check("C2 — 첫 구조 재질(*MAT_NULL_TITLE)만 싣고 *MAT_ELASTIC 은 새로 싣지 않는다 · 다른 재질 1 개를 알린다",
                  "*MAT_NULL_TITLE" in txt and txt.count("*MAT_ELASTIC") == 1 and "다른 재질 1 개" in out, (txt.count("*MAT_ELASTIC"), out[-300:]))

        print("[D — LONG=Y 2차 솔리드]")
        d = os.path.join(top, "d")
        os.makedirs(d)
        for fn, content in SP["convert"]["files"].items():
            with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
                f.write(content)
        run(binary, d, "generate", "box", "box.yaml")
        run(binary, d, "convert", "convert.yaml")
        src = os.path.join(d, "box_hex20.k")
        if check("D HEX20 상자를 지었다", os.path.exists(src), ""):
            with open(os.path.join(d, "ho_long.k"), "w", encoding="utf-8") as f:
                f.write(L.to_long(open(src, encoding="utf-8").read()))
            for fn in ("box_hex20.k", "ho_long.k"):
                rc, out = run(binary, d, "info", fn)
                check("D info %s — 요소 100 · 미정의 참조 0 · 음의 야코비안 없음" % fn,
                      rc == 0 and "Elements:                100" in out and "정의되지 않은" not in out and "Negative Jacobian" not in out,
                      [l for l in out.splitlines() if "Elements" in l or "ERROR" in l or "Negative" in l])
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
