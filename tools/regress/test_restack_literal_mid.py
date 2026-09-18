#!/usr/bin/env python3
# restack 의 재질 카드에 숫자 MID 를 직접 적었을 때 그 번호가 그대로 쓰이는지 지키는 회귀 시험
"""
배경:
  - 사용자가 material_card 의 mid 칸에 90 을 적으면 층 PART 의 mid 도 90 이어야 한다.
    예전에는 항상 maxMID+1 로 다시 번호를 매겨 사용자가 적은 번호가 사라졌다
    (그보다 더 옛 빌드에서는 PART mid 가 0 이 되고 둘째 층 카드가 통째로 빠졌다).
  - 다만 그 번호가 이미 모델에서 쓰이는 중이면 조용히 덮어쓰면 안 되므로
    새 번호를 주고 무엇을 왜 바꿨는지 알려야 한다.
  - *MAT_..._TITLE 인데 제목 줄이 빠진 카드는 유일한 데이터 줄이 제목으로 먹혀
    MID 칸이 사라지고 mid 0 인 *PART 와 '이미 씀' 으로 버려진 2층 카드가 나왔다(R1).
    데이터 줄이 2줄 이상이면 둘째 줄 첫 칸이 덮여 물성이 망가졌다(R1b).
  - 고정폭 카드에서 MID 토큰이 다음 값과 붙어 있으면 치환이 뒤 필드(RO)를 지웠다(R3).
  - 층 카드는 MaterialCardValidator 를 한 번도 거치지 않았다(R4).
  - 리더가 모르는 *MAT 종류가 쓰는 MID 와 새 MID 가 겹쳤다(R5).
  - 기존 MID 가 INT_MAX 면 ++ 가 부호 오버플로로 음수 MID 를 찍었다(R6).

사용: python3 tools/regress/test_restack_literal_mid.py <KooRemapper 바이너리>
"""
import os
import re
import subprocess
import sys
import tempfile

FAIL = 0


def check(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  OK   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")
        if detail:
            print(f"       {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def part_mids(path):
    """*PART 블록마다 (제목, mid)"""
    out = []
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().upper().startswith("*PART"):
            title = lines[i + 1].strip() if i + 1 < len(lines) else ""
            j = i + 2
            while j < len(lines) and lines[j].startswith("$"):
                j += 1
            if j < len(lines):
                f = lines[j].split()
                if len(f) >= 3 and f[2].lstrip("-").isdigit():
                    out.append((title, int(f[2])))
            i = j
        i += 1
    return out


CARD = """      *MAT_ELASTIC_TITLE
      {title}
      $#     mid        ro         e        pr
      {mid:>10}  2.33e-09   1.7e+05      0.28
"""


# 제목 줄이 빠진 *MAT_..._TITLE 카드 — 내용 줄이 데이터 줄 하나뿐이다
NO_TITLE_CARD = """      *MAT_ELASTIC_TITLE
      $#     mid        ro         e        pr
      {mid:>10}  2.33e-09   1.7e+05      0.28
"""


def no_title_yaml(output):
    return (
        "model: base.k\n"
        f"output: {output}\n"
        "target_pid: 1\n"
        "direction: z\n"
        "layers:\n"
        "  - title: Substrate\n"
        "    thickness: 0.7\n"
        "    num_elements: 2\n"
        "    material_card: |\n"
        + NO_TITLE_CARD.format(mid=90)
        + "  - title: DieLayer\n"
        "    thickness: 0.3\n"
        "    num_elements: 1\n"
        "    material_card: |\n"
        + NO_TITLE_CARD.format(mid=91)
    )


def restack_yaml(l1_mid, l2_mid, output):
    return (
        "model: base.k\n"
        f"output: {output}\n"
        "target_pid: 1\n"
        "direction: z\n"
        "layers:\n"
        "  - title: Substrate\n"
        "    thickness: 0.7\n"
        "    num_elements: 2\n"
        "    material_card: |\n"
        + CARD.format(title="Substrate_Si", mid=l1_mid)
        + "  - title: DieLayer\n"
        "    thickness: 0.3\n"
        "    num_elements: 1\n"
        "    material_card: |\n"
        + CARD.format(title="Die_Epoxy", mid=l2_mid)
    )


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "gen.yaml"), "w").write(
            "output: base.k\ndimensions: [20.0, 10.0, 2.0]\ndivisions: [4, 2, 1]\n")
        rc, out = run(binary, d, "generate", "box", "gen.yaml")
        check("입력 박스 생성", rc == 0 and os.path.exists(os.path.join(d, "base.k")), out[-200:])

        print("[숫자 MID 를 그대로 쓴다]")
        open(os.path.join(d, "a.yaml"), "w").write(restack_yaml(90, 91, "a.k"))
        rc, out = run(binary, d, "restack", "a.yaml")
        mids = dict(part_mids(os.path.join(d, "a.k"))) if rc == 0 else {}
        check("rc=0", rc == 0, out[-300:])
        check("Substrate PART 의 mid 가 90", mids.get("Substrate") == 90, str(mids))
        check("DieLayer PART 의 mid 가 91", mids.get("DieLayer") == 91, str(mids))
        deck = open(os.path.join(d, "a.k"), encoding="utf-8", errors="replace").read()
        check("재질 카드 두 장이 다 들어간다", deck.count("*MAT_ELASTIC_TITLE") == 2,
              f"count={deck.count('*MAT_ELASTIC_TITLE')}")
        check("카드 안의 MID 칸도 90/91", re.search(r"^\s+90\s+2\.33e-09", deck, re.M) is not None
              and re.search(r"^\s+91\s+2\.33e-09", deck, re.M) is not None)
        check("층 제목이 PART 제목이 된다", "Substrate" in mids and "DieLayer" in mids, str(mids))

        print("[모델이 이미 쓰는 번호면 새 번호를 주고 알린다]")
        open(os.path.join(d, "b.yaml"), "w").write(restack_yaml(1, 91, "b.k"))
        rc, out = run(binary, d, "restack", "b.yaml")
        mids = dict(part_mids(os.path.join(d, "b.k"))) if rc == 0 else {}
        check("rc=0", rc == 0, out[-300:])
        check("기존 MID 1 은 다시 쓰지 않는다", mids.get("Substrate") not in (None, 1), str(mids))
        check("무엇을 왜 바꿨는지 알린다", "already in use" in out and "assigned MID" in out, out[-300:])
        check("다른 층의 숫자 MID 는 그대로", mids.get("DieLayer") == 91, str(mids))

        print("[같은 숫자 MID 를 두 층이 서로 다른 카드로 쓰면 나눠 준다]")
        open(os.path.join(d, "c.yaml"), "w").write(
            restack_yaml(90, 90, "c.k").replace("Die_Epoxy", "Die_Other").replace("1.7e+05", "4.0e+03", 2))
        rc, out = run(binary, d, "restack", "c.yaml")
        mids = dict(part_mids(os.path.join(d, "c.k"))) if rc == 0 else {}
        check("rc=0", rc == 0, out[-300:])
        check("두 층의 MID 가 다르다", mids.get("Substrate") != mids.get("DieLayer"), str(mids))
        deck = open(os.path.join(d, "c.k"), encoding="utf-8", errors="replace").read()
        check("재질 카드 두 장이 다 들어간다", deck.count("*MAT_ELASTIC_TITLE") == 2,
              f"count={deck.count('*MAT_ELASTIC_TITLE')}")

        print("[자리표시(MIDnnn) 카드는 예전처럼 새 번호를 받되 숫자 MID 를 피한다]")
        y = restack_yaml(2, 91, "d.k")
        y = y.replace("        91  2.33e-09", "    MID002  2.33e-09")
        open(os.path.join(d, "d.yaml"), "w").write(y)
        rc, out = run(binary, d, "restack", "d.yaml")
        mids = dict(part_mids(os.path.join(d, "d.k"))) if rc == 0 else {}
        check("rc=0", rc == 0, out[-300:])
        check("숫자 MID 2 는 그 층이 가져간다", mids.get("Substrate") == 2, str(mids))
        check("자리표시 층은 2 를 피해 다른 번호를 받는다",
              mids.get("DieLayer") not in (None, 2) and mids.get("DieLayer") != mids.get("Substrate"), str(mids))


        print("[R1 제목 줄 없는 _TITLE 카드 — 데이터 줄이 하나면 그것이 데이터 줄이다]")
        open(os.path.join(d, "e.yaml"), "w").write(no_title_yaml("e.k"))
        rc, out = run(binary, d, "restack", "e.yaml")
        mids = dict(part_mids(os.path.join(d, "e.k"))) if rc == 0 else {}
        check("rc=0", rc == 0, out[-400:])
        check("1층 PART 의 mid 가 90 (0 이 아니다)", mids.get("Substrate") == 90, str(mids))
        check("2층 PART 의 mid 가 91", mids.get("DieLayer") == 91, str(mids))
        deck = open(os.path.join(d, "e.k"), encoding="utf-8", errors="replace").read() if rc == 0 else ""
        check("2층 재질 카드가 버려지지 않는다", deck.count("*MAT_ELASTIC_TITLE") == 2,
              f"count={deck.count('*MAT_ELASTIC_TITLE')}")
        check("제목 줄이 없었다는 사실을 알린다", "no title line" in out, out[-400:])
        check("mid 0 인 *PART 가 없다", all(m != 0 for m in mids.values()), str(mids))

        print("[R1b 제목 줄 없는 카드에 데이터 줄이 2줄 이상이면 물성을 망가뜨리지 않고 멈춘다]")
        two_line = (
            "model: base.k\noutput: f.k\ntarget_pid: 1\ndirection: z\nlayers:\n"
            "  - title: Substrate\n    thickness: 1.0\n    num_elements: 1\n"
            "    material_card: |\n"
            "      *MAT_PLASTIC_KINEMATIC_TITLE\n"
            "      $#     mid        ro         e        pr      sigy\n"
            "              90  7.85E-09  2.10E+05       0.3     250.0\n"
            "      $#       c         p      fail      tdel\n"
            "             40.0       5.0       0.0       0.0\n"
        )
        open(os.path.join(d, "f.yaml"), "w").write(two_line)
        rc, out = run(binary, d, "restack", "f.yaml")
        check("rc=1", rc == 1, out[-400:])
        check("둘째 데이터 줄을 덮어쓴 덱을 내지 않는다", not os.path.exists(os.path.join(d, "f.k")))
        check("무엇이 잘못됐는지 알린다(제목 줄)", "title line" in out, out[-400:])

        print("[R3 MID 토큰이 다음 값과 붙어 있어도 뒤 필드를 지우지 않는다]")
        glued = (
            "model: base.k\noutput: g.k\ntarget_pid: 1\ndirection: z\nlayers:\n"
            "  - title: Substrate\n    thickness: 1.0\n    num_elements: 1\n"
            "    material_card: |\n"
            "      *MAT_ELASTIC_TITLE\n"
            "      Substrate_Si\n"
            "      $#     mid        ro         e        pr\n"
            "              902.3300E-09  1.69E+05      0.28\n"
        )
        open(os.path.join(d, "g.yaml"), "w").write(glued)
        rc, out = run(binary, d, "restack", "g.yaml")
        deck = open(os.path.join(d, "g.k"), encoding="utf-8", errors="replace").read() if rc == 0 else ""
        check("rc=0", rc == 0, out[-400:])
        check("MID 칸(1~10열)만 바뀌고 RO 가 남는다",
              re.search(r"^ {8}90 ?2\.3300E-09  1\.69E\+05", deck, re.M) is not None,
              repr([l for l in deck.splitlines() if "2.3300E-09" in l]))
        check("PART mid 가 90", dict(part_mids(os.path.join(d, "g.k"))).get("Substrate") == 90 if rc == 0 else False)

        print("[R3 10열 안에 다음 값이 있는 줄(help 예제식)은 예전처럼 토큰 끝까지만 바꾼다]")
        narrow = (
            "model: base.k\noutput: h.k\ntarget_pid: 1\ndirection: z\nlayers:\n"
            "  - title: Substrate\n    thickness: 1.0\n    num_elements: 1\n"
            "    material_card: |\n"
            "      *MAT_ELASTIC\n"
            "           1  2.0     12000      0.25\n"
        )
        open(os.path.join(d, "h.yaml"), "w").write(narrow)
        rc, out = run(binary, d, "restack", "h.yaml")
        deck = open(os.path.join(d, "h.k"), encoding="utf-8", errors="replace").read() if rc == 0 else ""
        check("rc=0", rc == 0, out[-400:])
        check("MID 1 은 모델이 쓰는 중이라 새 번호를 받는다",
              dict(part_mids(os.path.join(d, "h.k"))).get("Substrate") not in (None, 0, 1) if rc == 0 else False)
        check("뒤 필드 '2.0' 이 지워지지 않는다",
              re.search(r"^ {5}\d  2\.0     12000      0\.25$", deck, re.M) is not None,
              repr([l for l in deck.splitlines() if "12000" in l]))

        print("[R4 층 카드도 MaterialCardValidator 를 거친다]")
        bad = (
            "model: base.k\noutput: i.k\ntarget_pid: 1\ndirection: z\nlayers:\n"
            "  - title: Substrate\n    thickness: 1.0\n    num_elements: 1\n"
            "    material_card: |\n"
            "      *MAT_ELASTIC_TITLE\n"
            "      Substrate_Si\n"
            "      $#     mid        ro         e        pr\n"
            "              90  7.85E-09  2.10E+05       0.9\n"
        )
        open(os.path.join(d, "i.yaml"), "w").write(bad)
        rc, out = run(binary, d, "restack", "i.yaml")
        check("rc=1", rc == 1, out[-400:])
        check("무엇이 잘못됐는지 알린다(PR)", "Poisson" in out, out[-400:])
        check("반쪽 덱이 남지 않는다", not os.path.exists(os.path.join(d, "i.k")))

        print("[R5 리더가 모르는 *MAT 이 쓰는 MID 와 새 MID 가 겹치지 않는다]")
        base = open(os.path.join(d, "base.k"), encoding="utf-8", errors="replace").read()
        unknown = ("*MAT_MODIFIED_JOHNSON_COOK_TITLE\nJC_Steel\n"
                   "$#     mid        ro         e        pr\n"
                   "         5  7.85e-09   2.1e+05       0.3\n")
        open(os.path.join(d, "unk.k"), "w").write(base.replace("*SECTION_SOLID", unknown + "*SECTION_SOLID", 1))
        ph = ("  - title: L{n}\n    thickness: 0.2\n    num_elements: 1\n    material_card: |\n"
              "      *MAT_ELASTIC\n"
              "      $#     mid        ro         e        pr\n"
              "          MID00{n}  {ro}E-09  2.10E+05       0.3\n")
        open(os.path.join(d, "j.yaml"), "w").write(
            "model: unk.k\noutput: j.k\ntarget_pid: 1\ndirection: z\nlayers:\n" +
            "".join(ph.format(n=n, ro=n) for n in range(1, 6)))
        rc, out = run(binary, d, "restack", "j.yaml")
        mids = [m for t, m in part_mids(os.path.join(d, "j.k"))] if rc == 0 else []
        check("rc=0", rc == 0, out[-400:])
        check("리더가 모르는 *MAT 의 MID 5 를 다시 쓰지 않는다", 5 not in mids[1:], str(mids))
        check("새 MID 가 서로 겹치지 않는다", len(set(mids)) == len(mids), str(mids))

        print("[R6 기존 MID 가 INT_MAX 면 오버플로 대신 분명한 오류]")
        maxed = ("*MAT_ELASTIC\n$#     mid        ro         e        pr\n"
                 "2147483647  7.85e-09   2.1e+05       0.3\n")
        open(os.path.join(d, "max.k"), "w").write(base.replace("*SECTION_SOLID", maxed + "*SECTION_SOLID", 1))
        open(os.path.join(d, "k.yaml"), "w").write(
            "model: max.k\noutput: k.k\ntarget_pid: 1\ndirection: z\nlayers:\n" + ph.format(n=1, ro=1))
        rc, out = run(binary, d, "restack", "k.yaml")
        check("rc=1", rc == 1, out[-400:])
        check("번호가 바닥났다고 알린다", "no free material ID" in out, out[-400:])
        check("음수 MID 인 덱을 내지 않는다", not os.path.exists(os.path.join(d, "k.k")))

    print("FAIL %d" % FAIL if FAIL else "ALL PASS")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
