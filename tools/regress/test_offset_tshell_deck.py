#!/usr/bin/env python3
# offset 의 element_type: tshell 산출이 매뉴얼대로의 TSHELL 덱인지 보는 회귀 시험
"""`offset` 의 `element_type: tshell` 산출이 **매뉴얼대로의 TSHELL 덱**인가.

왜 이 시험이 있나 (2026-10-16).

  커밋된 예제 `examples/offset/03_tshell_result.k` 가 TSHELL 덱이 아니었다 —
    · 요소를 **4절점 `*ELEMENT_SHELL`** 로 썼다. 압출이 만든 8절점 중 윗면 넷이 빠지고, `*SECTION_TSHELL`
      파트를 셸 요소가 썼다
    · `*SECTION_TSHELL` 에 **ELFORM 16** 을 썼다 — TSHELL 의 정식은 1·2·3·5·6·7 뿐이다(Vol_I 229493-229500)
    · 셸 섹션처럼 **두께 줄(T1~T4)** 을 붙였다 — TSHELL 섹션에는 두께 카드가 없고 Card 2 는 ICOMP=1 일 때의
      각도 카드다. ICOMP=0 이면 그 줄은 **새 섹션 세트**로 읽힌다
    · 삼각 바닥은 `[b0,b1,b2,t0,t1,t2,0,0]` — 매뉴얼의 쐐기 꼴은 n1,n2,n3,n3,n4,n5,n6,n6 이다
      (`*ELEMENT_TSHELL` Remark 「Orientation」)
  (회귀 문서 `tests/offset/README_REGRESSION.md` 도 「TSHELL 요소」를 기대했지만 산출은 셸이었다.)

무엇을 보나.
  A 사각 바닥 1층(arc30_flat) — `*ELEMENT_TSHELL` 만(새 파트에 셸 0) · 줄마다 0 아닌 8절점 · 아랫면 4와 윗면 4가
    서로 다르고 그 거리가 층 두께 · `*SECTION_TSHELL` 데이터 줄 하나 · ELFORM ∈ {1,2,3,5,6,7}
  B 2층 — 요소 수 = 면 × 2 · 1층 윗면 = 2층 아랫면(절점 공유)
  C 삼각 바닥(사면체 하나 — 바깥면이 전부 삼각) — 쐐기 꼴 N4 = N3 · N8 = N7, 바닥 셋은 서로 다르다

usage: test_offset_tshell_deck.py <KooRemapper 바이너리>
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def blocks(path):
    """키워드(접미사 뗀 첫 토큰) → 데이터 줄 목록들."""
    out, kw = [], None
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("*"):
            kw = l.split()[0].upper().rstrip("%+-")
            out.append((kw, []))
        elif out and l.strip() and not l.lstrip().startswith("$"):
            out[-1][1].append(l)
    return out


def ints(line, w=8):
    return [int(line[i:i + w]) for i in range(0, len(line.rstrip()), w) if line[i:i + w].strip()]


def nodes_of(bl):
    xyz = {}
    for kw, data in bl:
        if kw == "*NODE":
            for l in data:
                xyz[int(l[:8])] = tuple(float(l[8 + 16 * k: 24 + 16 * k]) for k in range(3))
    return xyz


YAML = ("base_model: deck.k\noutput: out\noperations:\n  - type: offset\n    source_pid: 1\n"
        "    element_type: tshell\n    thickness: 1.5\n    shell_thickness: 1.5\n    num_layers: %d\n"
        "    offset_direction: +z\n    new_pid: 10\n    part_title: \"TShell\"\n    material_card: |\n"
        "      *MAT_ELASTIC\n      $#     mid        ro         e        pr\n"
        "           @MID@       2.0     12000      0.25\n")
TET = """*KEYWORD
*NODE
       1             0.0             0.0             0.0
       2             1.0             0.0             0.0
       3             0.0             1.0             0.0
       4             0.0             0.0             1.0
*PART
tet
         1         1         1
*SECTION_SOLID
         1        10
*MAT_ELASTIC
         1    7.8E-9  210000.0       0.3
*ELEMENT_SOLID
       1       1       1       2       3       4       4       4       4       4
*END
"""


def run(binary, deck_body, layers):
    d = tempfile.mkdtemp(prefix="otd_")
    try:
        open(os.path.join(d, "deck.k"), "w", encoding="utf-8").write(deck_body)
        open(os.path.join(d, "c.yaml"), "w", encoding="utf-8").write(YAML % layers)
        r = subprocess.run([binary, "assemble", "c.yaml"], cwd=d, capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        out = os.path.join(d, "out.k")
        if r.returncode != 0 or not os.path.exists(out):
            return None, (r.stdout + r.stderr)[-300:]
        return blocks(out), ""
    finally:
        shutil.rmtree(d, ignore_errors=True)


def tshell_lines(bl, pid=10):
    ts = [ints(l) for kw, data in bl if kw == "*ELEMENT_TSHELL" for l in data]
    shells = [ints(l) for kw, data in bl if kw == "*ELEMENT_SHELL" for l in data]
    return [t for t in ts if len(t) >= 2 and t[1] == pid], [s for s in shells if len(s) >= 2 and s[1] == pid]


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    arc = open(os.path.join(REPO, "examples", "arc30", "arc30_flat.k"), encoding="utf-8").read()

    print("[A 사각 바닥 1층]")
    bl, log = run(binary, arc, 1)
    if check("A rc 0", bl is not None, log):
        ts, sh = tshell_lines(bl)
        check("A 새 파트는 *ELEMENT_TSHELL 로만(셸 0)", ts and not sh, "tshell=%d shell=%d" % (len(ts), len(sh)))
        check("A 줄마다 0 아닌 8절점", all(len(t) == 10 and all(t[2:]) for t in ts),
              [t for t in ts if len(t) != 10 or not all(t[2:])][:2])
        check("A 아랫면 4 와 윗면 4 가 서로 다르다",
              all(not (set(t[2:6]) & set(t[6:10])) for t in ts), ts[:1])
        xyz = nodes_of(bl)
        dist = [math.dist(xyz[t[2 + k]], xyz[t[6 + k]]) for t in ts[:50] for k in range(4)]
        check("A 위아래 거리 = 층 두께 1.5", dist and all(abs(x - 1.5) < 1e-6 for x in dist),
              "dist %s" % sorted(set(round(x, 6) for x in dist))[:4])
        sec = [data for kw, data in bl if kw == "*SECTION_TSHELL"]
        check("A *SECTION_TSHELL 데이터 줄 하나(두께 줄 없음)", len(sec) == 1 and len(sec[0]) == 1, sec)
        elform = ints(sec[0][0], 10)[1] if sec and sec[0] else None
        check("A ELFORM 이 TSHELL 정식(1·2·3·5·6·7)", elform in (1, 2, 3, 5, 6, 7), elform)
        n_faces = len(ts)

    print("[B 2층]")
    bl2, log = run(binary, arc, 2)
    if check("B rc 0", bl2 is not None, log):
        ts2, _ = tshell_lines(bl2)
        check("B 요소 수 = 면 × 2", bl is not None and len(ts2) == 2 * n_faces, "%d vs %d" % (len(ts2), 2 * n_faces))
        tops = {tuple(t[6:10]) for t in ts2}
        bots = {tuple(t[2:6]) for t in ts2}
        check("B 1층 윗면 = 2층 아랫면(절점 공유)", len(tops & bots) == n_faces, len(tops & bots))

    print("[C 삼각 바닥 — 쐐기]")
    bl3, log = run(binary, TET, 1)
    if check("C rc 0", bl3 is not None, log):
        ts3, sh3 = tshell_lines(bl3)
        check("C 삼각 면 → TSHELL(셸 0)", len(ts3) >= 1 and not sh3, "tshell=%d shell=%d" % (len(ts3), len(sh3)))
        check("C 쐐기 꼴 N4 = N3 · N8 = N7 · 바닥 셋이 서로 다르다",
              ts3 and all(t[5] == t[4] and t[9] == t[8] and len({t[2], t[3], t[4]}) == 3 and all(t[2:]) for t in ts3),
              ts3[:2])

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
