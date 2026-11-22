#!/usr/bin/env python3
# 열 재질 번호 이름의 이상한 철자 · `info --strict` 의 TMID 참조 · extract-parts 의 PID 꼴 덧붙임을 보는 회귀 시험(3차 3판 L-15)
"""열 재질 철자 · TMID 참조 · PID 꼴 덧붙임 (2026-11-22 · 미룬 결함 3차 3판 L-15).

왜 이 시험이 있나.

  열 재질 판정(`cards::isThermalMaterialKeyword`)이 번호 이름을 `*MAT_T01` ~ `*MAT_T18` 두 자리로만 받았다 — `*MAT_T1` · `*MAT_T19` ·
  `*MAT_T001` 은 구조 재질로 세어 그 첫 칸(TMID)을 MID 로 읽었다(겹침 오탐 · 없는 구조 재질을 「정의됨」 · 커서가 TMID 위로 뛴다).
  구조 재질의 번호 이름은 `*MAT_0xx`, 이름 꼴은 `*MAT_T` + 글자라 `*MAT_T` + 숫자는 열 재질 꼴로만 읽힌다.
  `info --strict` 는 `*PART` 의 TMID(여덟째 칸)를 보지 않았다 — 이제 없는 열 재질을 「의심」 줄로 짚는다(rc 와 무관). Vol I *PART TMID 는
  열 · 열-구조 연성 해석에만 열 물성을 요구하고, `/data` 의 battery 덱이 TMID 107 을 정의하지 않고 정상 종료했다(실측 11-22).
  extract-parts 는 `*MAT_ADD_THERMAL_EXPANSION`(첫 칸 PID)을 고른 재질 번호와 견주어 고른 파트의 열팽창 카드를 버리고, 번호가 우연히
  고른 MID 와 같은 남의 파트 카드는 실었다.

무엇을 보나.
  A 철자 — `*MAT_ELASTIC 2` + `*MAT_T1 2` · `*MAT_T001 2` 는 겹침이 아니다(--strict rc 0)
  B 철자 — `*PART` MID 2 를 `*MAT_T19 2` 가 정의하지 않는다(--strict rc 1)
  C 철자 — assemble offset(재질 카드)의 새 MID 가 `*MAT_T001 5` 의 TMID 위로 뛰지 않는다(2)
  D TMID — 없는 열 재질은 의심 줄(rc 0) · 이름 꼴 · 번호 이름으로 정의하면 줄이 없다 · 구조 재질 번호는 TMID 를 정의하지 않는다 ·
    `*PART +`(20 칸) · 콤마 자유형식도 칸대로
  E extract-parts — 고른 파트의 `*MAT_ADD_THERMAL_EXPANSION` 을 싣고, 고른 MID 와 번호만 같은 남의 파트 것은 버린다
  F `*PART +`(키워드 줄의 칸폭 표지) — 맨 파트로 읽는다. 예전엔 변형으로 보아 `--strict` 가 섹션 · 재질을 안 봤고, 요소 색인이 파트의
    ELFORM(23 — 20 절점)을 몰라 셋째 줄(절점 11 ~ 20)을 새 요소로 읽었다(「파트 12 미정의」)

usage: test_thermal_spelling.py <KooRemapper 바이너리>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

FAILS, OKS = [], []

BOX = """output: box.k
lx: 20.0
ly: 10.0
lz: 2.0
nx: 4
ny: 2
nz: 1
rho: 7.85e-9
E: 210000.0
nu: 0.3
mid: 1
secid: 1
pid: 1
part_title: PLATE
"""
OFFSET = """base_model: box.k
output: out
operations:
  - type: offset
    source_pid: 1
    element_type: solid
    thickness: 1.0
    num_layers: 1
    offset_direction: +z
    connection_mode: tied
    new_pid: 10
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
           @MID@  7.85E-09  2.10E+05       0.3
"""
PART10 = "         1         1         1\n"
SUSPECT = "의심 line 14 *PART: 열 재질(TMID) %d 이 정의되지 않았습니다"


def thermal(kw, tmid):
    """열 재질 Card 1 TMID TRO TGRLC TGMULT · Card 2 HC TC(`*MAT_THERMAL_ISOTROPIC` 꼴)."""
    return "%s\n%10d       0.0       0.0       0.0\n       1.0       1.0\n" % (kw, tmid)


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[:500]))
    print("  %-70s %s" % (name[:70], "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def box(binary, d, before_end="", part=None):
    """상자 덱 — part 를 주면 `*PART` 데이터 줄(10 칸 PID SECID MID)을 그 줄로 바꾼다."""
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    rc, out = run(binary, d, "generate", "box", "box.yaml")
    assert rc == 0, out[-400:]
    p = os.path.join(d, "box.k")
    body = open(p, encoding="utf-8").read()
    if part is not None:
        assert body.count(PART10) == 1
        body = body.replace(PART10, part)
    open(p, "w", encoding="utf-8").write(body.replace("*END", before_end + "*END"))


def fresh(tmp, name):
    d = os.path.join(tmp, name)
    os.makedirs(d)
    return d


def strict(binary, d, before_end="", part=None):
    box(binary, d, before_end, part)
    return run(binary, d, "info", "--strict", "box.k")


def nodes8(base, x0):
    return ["%8d%16.7f%16.7f%16.7f" % (base + i, x0 + (i % 2), (i // 2) % 2, i // 4) for i in range(8)]


def two_part_deck(addon):
    """파트 10 · 20 (둘 다 SECID 1 · MID 1) + 파트 1(MID 1 · 요소 없음은 아님 — 요소 하나) — 덧붙임 블록을 끝에 붙인다."""
    L = ["*KEYWORD", "*NODE"] + nodes8(1, 0.0) + nodes8(11, 3.0) + nodes8(21, 6.0)
    L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 10), "".join("%8d" % n for n in range(1, 9))]
    L += ["%8d%8d" % (2, 20), "".join("%8d" % n for n in range(11, 19))]
    L += ["%8d%8d" % (3, 1), "".join("%8d" % n for n in range(21, 29))]
    L += ["*PART", "ten", "%10d%10d%10d" % (10, 1, 1), "twenty", "%10d%10d%10d" % (20, 1, 1), "one", "%10d%10d%10d" % (1, 1, 1)]
    L += ["*SECTION_SOLID", "%10d%10d" % (1, 1)]
    L += ["*MAT_ELASTIC", "         1  7.85E-9  210000     0.3"]
    L += addon
    L += ["*END"]
    return "\n".join(L) + "\n"


def addon_blocks(text):
    """`*MAT_ADD_THERMAL_EXPANSION` 블록마다 첫 데이터 줄의 PID."""
    out, lines = [], text.split("\n")
    for i, l in enumerate(lines):
        if l.strip().upper().startswith("*MAT_ADD_THERMAL_EXPANSION"):
            j = i + 1
            while j < len(lines) and lines[j].startswith("$"):
                j += 1
            out.append(int(lines[j][:10]))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="thermal_spelling_")
    try:
        print("[A 철자 — `*MAT_T` + 숫자는 열 재질이다(겹침이 아니다)]")
        for kw in ("*MAT_T1", "*MAT_T001"):
            d = fresh(tmp, "a" + kw[5:])
            rc, out = strict(binary, d, "*MAT_ELASTIC\n         2   7.85E-9    210000       0.3\n" + thermal(kw, 2))
            check("A %s 2 + *MAT_ELASTIC 2 — 겹침(망가진 카드)이 아니다(--strict rc 0)" % kw,
                  rc == 0 and "망가진 카드" not in out, out[-300:])

        print("[B 철자 — 열 재질은 구조 MID 를 정의하지 않는다]")
        d = fresh(tmp, "b")
        rc, out = strict(binary, d, thermal("*MAT_T19", 2), part="         1         1         2\n")
        check("B *PART MID 2 · *MAT_T19 2 뿐 — 재질 2 미정의(--strict rc 1)", rc == 1 and "재질 2" in out, out[-300:])

        print("[C 철자 — 커서가 TMID 위로 뛰지 않는다]")
        d = fresh(tmp, "c")
        box(binary, d, thermal("*MAT_T001", 5))
        open(os.path.join(d, "off.yaml"), "w").write(OFFSET)
        rc, out = run(binary, d, "assemble", "off.yaml")
        o = open(os.path.join(d, "out.k"), encoding="utf-8").read() if rc == 0 else ""
        lines = o.split("\n")
        new_mid = None
        for i, l in enumerate(lines):
            if l.strip().upper() == "*MAT_ELASTIC":
                j = i + 1
                while lines[j].startswith("$"):
                    j += 1
                v = int(lines[j][:10])
                if v != 1:
                    new_mid = v
        rc2, out2 = run(binary, d, "info", "--strict", "out.k") if rc == 0 else (None, out)
        check("C 새 MID 는 2(`*MAT_T001 5` 의 TMID 는 구조 번호 공간이 아니다) · --strict rc 0",
              rc == 0 and new_mid == 2 and rc2 == 0, (rc, new_mid, rc2, out2[-300:]))

        print("[D info --strict — *PART 의 TMID(여덟째 칸)]")
        tm10 = "         1         1         1         0         0         0         0         7\n"
        d = fresh(tmp, "d1")
        rc, out = strict(binary, d, part=tm10)
        check("D-1 TMID 7 · 열 재질 없음 — 의심 줄 「열 재질(TMID) 7」 · rc 0", rc == 0 and SUSPECT % 7 in out, out[-300:])
        d = fresh(tmp, "d2")
        rc, out = strict(binary, d, thermal("*MAT_THERMAL_ISOTROPIC", 7), part=tm10)
        check("D-2 TMID 7 · *MAT_THERMAL_ISOTROPIC 7 — rc 0", rc == 0 and "열 재질" not in out, out[-300:])
        d = fresh(tmp, "d3")
        rc, out = strict(binary, d, thermal("*MAT_T01", 7), part=tm10)
        check("D-3 TMID 7 · *MAT_T01 7 — rc 0", rc == 0 and "열 재질" not in out, out[-300:])
        d = fresh(tmp, "d4")
        rc, out = strict(binary, d, "*MAT_ELASTIC\n         7   7.85E-9    210000       0.3\n", part=tm10)
        check("D-4 TMID 7 · 구조 *MAT_ELASTIC 7 뿐 — 의심 줄(구조 번호는 TMID 를 정의하지 않는다)", rc == 0 and SUSPECT % 7 in out, out[-300:])
        d = fresh(tmp, "d5")
        open(os.path.join(d, "box.yaml"), "w").write(BOX)
        run(binary, d, "generate", "box", "box.yaml")
        p = os.path.join(d, "box.k")
        body = open(p, encoding="utf-8").read()
        body = body.replace("*PART\n", "*PART +\n", 1).replace(PART10, "%20d%20d%20d%20d%20d%20d%20d%20d\n" % (1, 1, 1, 0, 0, 0, 0, 7))
        open(p, "w", encoding="utf-8").write(body)
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("D-5 `*PART +`(20 칸) TMID 7 · 열 재질 없음 — 의심 줄(20 칸으로 읽는다)", rc == 0 and SUSPECT % 7 in out, out[-300:])
        open(p, "w", encoding="utf-8").write(body.replace("*END", thermal("*MAT_THERMAL_ISOTROPIC", 7) + "*END"))
        rc, out = run(binary, d, "info", "--strict", "box.k")
        check("D-6 `*PART +` TMID 7 · 열 재질 7 — rc 0", rc == 0 and "열 재질" not in out, out[-300:])
        d = fresh(tmp, "d7")
        rc, out = strict(binary, d, part="1,1,1,0,0,0,0,7\n")
        check("D-7 콤마 자유형식 TMID 7 · 열 재질 없음 — 의심 줄", rc == 0 and SUSPECT % 7 in out, out[-300:])
        d = fresh(tmp, "d8")
        rc, out = strict(binary, d, part="         1         1         1         0         0         0         0         0\n")
        check("D-8 TMID 0 — 보지 않는다(rc 0)", rc == 0 and "열 재질" not in out, out[-300:])

        print("[E extract-parts — PID 꼴 덧붙임은 고른 파트와 견준다]")
        d = fresh(tmp, "e")
        add = []
        for pid in (10, 20, 1):
            add += ["*MAT_ADD_THERMAL_EXPANSION", "%10d%10d%10.1f" % (pid, 0, 1.0)]
        open(os.path.join(d, "m.k"), "w").write(two_part_deck(add))
        open(os.path.join(d, "x.yaml"), "w").write("model: m.k\noutput: out.k\nparts: [10]\nreport: rep.json\n")
        rc, out = run(binary, d, "extract-parts", "x.yaml")
        o = open(os.path.join(d, "out.k")).read() if rc == 0 else ""
        got = addon_blocks(o)
        check("E-1 rc 0", rc == 0, out[-300:])
        check("E-2 고른 파트 10 의 *MAT_ADD_THERMAL_EXPANSION 을 싣는다", 10 in got, got)
        check("E-3 안 고른 파트 20 · 1 의 것은 버린다(1 은 고른 MID 와 번호만 같다)", 20 not in got and 1 not in got, got)
        r = json.load(open(os.path.join(d, "rep.json"))) if rc == 0 else {}
        check("E-4 되읽기 — 미정의 참조 0", r.get("verify", {}).get("undefined_parts") == 0, r.get("verify"))

        print("[F `*PART +` — 맨 파트다]")
        d = fresh(tmp, "f")
        pts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
               (.5, 0, 0), (1, .5, 0), (.5, 1, 0), (0, .5, 0), (0, 0, .5), (1, 0, .5), (1, 1, .5), (0, 1, .5),
               (.5, 0, 1), (1, .5, 1), (.5, 1, 1), (0, .5, 1)]
        L = ["*KEYWORD", "*NODE"] + ["%8d%16.4f%16.4f%16.4f" % (i + 1, *q) for i, q in enumerate(pts)]
        L += ["*ELEMENT_SOLID", "%8d%8d" % (1, 1), "".join("%8d" % n for n in range(1, 11)), "".join("%8d" % n for n in range(11, 21))]
        L += ["*PART +", "p", "%20d%20d%20d" % (1, 1, 1), "*SECTION_SOLID", "%10d%10d" % (1, 23)]
        L += ["*MAT_ELASTIC", "         1   7.85E-9    210000       0.3", "*END"]
        open(os.path.join(d, "h20.k"), "w").write("\n".join(L) + "\n")
        rc, out = run(binary, d, "info", "--strict", "h20.k")
        check("F-1 20 절점 솔리드(ELFORM 23) · `*PART +` — 요소 하나 · --strict rc 0", rc == 0 and "Elements:                1" in out,
              out[-300:])
        open(os.path.join(d, "h20.k"), "w").write("\n".join(L).replace("%20d%20d%20d" % (1, 1, 1), "%20d%20d%20d" % (1, 1, 5)) + "\n")
        rc, out = run(binary, d, "info", "--strict", "h20.k")
        check("F-2 `*PART +` MID 5 미정의 — 재질 5 를 본다(--strict rc 1)", rc == 1 and "재질 5" in out, out[-300:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print("결과: %d 통과 · %d 실패" % (len(OKS), len(FAILS)))
    for f in FAILS:
        print("  FAIL " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
