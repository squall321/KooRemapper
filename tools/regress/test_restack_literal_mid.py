#!/usr/bin/env python3
# restack 의 재질 카드에 숫자 MID 를 직접 적었을 때 그 번호가 그대로 쓰이는지 지키는 회귀 시험
"""
배경:
  - 사용자가 material_card 의 mid 칸에 90 을 적으면 층 PART 의 mid 도 90 이어야 한다.
    예전에는 항상 maxMID+1 로 다시 번호를 매겨 사용자가 적은 번호가 사라졌다
    (그보다 더 옛 빌드에서는 PART mid 가 0 이 되고 둘째 층 카드가 통째로 빠졌다).
  - 다만 그 번호가 이미 모델에서 쓰이는 중이면 조용히 덮어쓰면 안 되므로
    새 번호를 주고 무엇을 왜 바꿨는지 알려야 한다.

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

    print("FAIL %d" % FAIL if FAIL else "ALL PASS")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
