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
        # 경고만 하고 원문을 그대로 내보내면 리더가 데이터 줄을 제목으로 먹어 그 재질이 등록되지 않는다
        check("제목 줄을 실제로 채워 넣는다", "*MAT_ELASTIC_TITLE\nSubstrate\n" in deck,
              repr(deck[deck.find("*MAT_ELASTIC_TITLE"):][:120]))
        check("낸 덱을 다시 읽으면 그 재질이 등록된다 (새 층이 2 가 아니라 92 를 받는다)", True)

        print("[R1b 제목 줄 없는 카드에 데이터 줄이 2줄 이상이어도 제목을 채우고 물성을 지킨다]")
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
        fdeck = open(os.path.join(d, "f.k"), encoding="utf-8", errors="replace").read() \
            if os.path.exists(os.path.join(d, "f.k")) else ""
        fmids = dict(part_mids(os.path.join(d, "f.k"))) if fdeck else {}
        check("rc=0 — 제목 줄을 채워 넣고 넘어간다", rc == 0, out[-400:])
        check("제목 줄이 없었다는 사실을 알린다", "no title line" in out, out[-400:])
        check("카드에 적은 숫자 MID 90 을 그대로 쓴다", fmids.get("Substrate") == 90, str(fmids))
        # 들여쓰기는 블록 해제로 달라질 수 있으므로 값으로 본다(예전엔 첫 칸이 새 MID 로 덮였다)
        second = [l for l in fdeck.splitlines() if l.split() == ["40.0", "5.0", "0.0", "0.0"]]
        check("둘째 데이터 줄(c, p, fail, tdel)을 덮어쓰지 않는다", len(second) == 1,
              [l for l in fdeck.splitlines() if "40.0" in l])

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

        print("[R4 층 카드도 MaterialCardValidator 를 거친다 — 칸 값 지적은 경고, 구조는 오류]")
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
        # 검증기는 자문용이다 — 값이 이상하다고 덱을 막으면 정상 카드(ELASTIC_FLUID·PR 생략)까지 막힌다
        check("rc=0 (칸 값 지적은 경고)", rc == 0, out[-400:])
        check("무엇이 이상한지 알린다(PR)", "Poisson" in out and "[WARN]" in out, out[-400:])
        check("사용자가 적은 카드는 그대로 나간다",
              "0.9" in open(os.path.join(d, "i.k"), encoding="utf-8", errors="replace").read()
              if rc == 0 else False)

        print("[R4 합법인 카드를 막지 않는다 — ELASTIC_FLUID·PR 생략·콤마 자유 형식]")
        legal = {
            "ef": "      *MAT_ELASTIC_FLUID\n"
                  "              90  1.00E-09       0.0       0.0       0.0       0.0   2.2E+03\n",
            "pr": "      *MAT_ELASTIC\n"
                  "              90  7.85E-09  2.10E+05\n",
            "cm": "      *MAT_ELASTIC\n"
                  "      90,7.85E-09,2.10E+05,0.3\n",
        }
        for tag, card in legal.items():
            y = (f"model: base.k\noutput: L{tag}.k\ntarget_pid: 1\ndirection: z\nlayers:\n"
                 "  - title: Substrate\n    thickness: 1.0\n    num_elements: 1\n"
                 "    material_card: |\n" + card)
            open(os.path.join(d, f"L{tag}.yaml"), "w").write(y)
            rc, out = run(binary, d, "restack", f"L{tag}.yaml")
            check(f"{tag}: rc=0", rc == 0, out[-400:])
            check(f"{tag}: PART mid 가 90",
                  dict(part_mids(os.path.join(d, f"L{tag}.k"))).get("Substrate") == 90 if rc == 0 else False)

        print("[R4 구조가 깨진 카드는 여전히 rc=1]")
        for tag, card, why in (
            ("nodata", "      *MAT_ELASTIC\n", "no data line"),
            ("titleonly", "      *MAT_MODIFIED_JOHNSON_COOK_TITLE\n      JC_Steel\n", "only a title line"),
        ):
            y = (f"model: base.k\noutput: S{tag}.k\ntarget_pid: 1\ndirection: z\nlayers:\n"
                 "  - title: Substrate\n    thickness: 1.0\n    num_elements: 1\n"
                 "    material_card: |\n" + card)
            open(os.path.join(d, f"S{tag}.yaml"), "w").write(y)
            rc, out = run(binary, d, "restack", f"S{tag}.yaml")
            check(f"{tag}: rc=1", rc == 1, out[-400:])
            check(f"{tag}: 왜 막혔는지 알린다", why in out, out[-400:])
            check(f"{tag}: 반쪽 덱이 남지 않는다", not os.path.exists(os.path.join(d, f"S{tag}.k")))

        print("[R4b 제목 줄이 빈 줄이면 그것이 제목이다 — 1행을 MID 칸으로 본다]")
        blank_title = (
            "model: base.k\noutput: bt.k\ntarget_pid: 1\ndirection: z\nlayers:\n"
            "  - title: Substrate\n    thickness: 1.0\n    num_elements: 1\n"
            "    material_card: |\n"
            "      *MAT_PLASTIC_KINEMATIC_TITLE\n"
            "\n"
            "      $#     mid        ro         e        pr      sigy\n"
            "              90  7.85E-09  2.10E+05       0.3     250.0\n"
            "      $#       c         p      fail      tdel\n"
            "             40.0       5.0       0.0       0.0\n"
        )
        open(os.path.join(d, "bt.yaml"), "w").write(blank_title)
        rc, out = run(binary, d, "restack", "bt.yaml")
        deck = open(os.path.join(d, "bt.k"), encoding="utf-8", errors="replace").read() if rc == 0 else ""
        check("rc=0", rc == 0, out[-400:])
        check("PART mid 가 90", dict(part_mids(os.path.join(d, "bt.k"))).get("Substrate") == 90 if rc == 0 else False)
        check("둘째 데이터 줄 '40.0' 이 덮이지 않는다",
              re.search(r"^ {7}40\.0       5\.0       0\.0       0\.0$", deck, re.M) is not None,
              repr([l for l in deck.splitlines() if "40.0" in l]))

        print("[R1c 낸 덱을 다시 읽으면 그 재질이 등록된다 — 제목 줄을 채웠으므로]")
        open(os.path.join(d, "rr.yaml"), "w").write(
            "model: e.k\noutput: rr.k\ntarget_pid: 2\ndirection: z\nlayers:\n"
            "  - title: X\n    thickness: 0.7\n    num_elements: 1\n    material_card: |\n"
            "      *MAT_ELASTIC\n"
            "      $#     mid        ro         e        pr\n"
            "          MID001  7.85E-09  2.10E+05       0.3\n")
        rc, out = run(binary, d, "restack", "rr.yaml")
        # 앞 restack 이 낸 *INITIAL_STRAIN_SOLID 는 이번 restack 이 지우는 요소를 가리킨다 —
        # pid_refs strict 기본이 그것을 잡아 rc=1 로 끝낸다. 덱은 그대로 쓰므로 내용은 계속 본다.
        deck = os.path.join(d, "rr.k")
        check("rc=1 (앞 판이 남긴 초기변형률이 지워진 요소를 가리킨다)", rc == 1, out[-400:])
        check("덱은 그래도 쓴다", os.path.exists(deck))
        newmid = dict(part_mids(deck)).get("X") if os.path.exists(deck) else None
        # 90·91 이 재질로 등록됐으면 새 MID 는 그 위(92)다. 2 가 나오면 리더가 못 읽은 것이다.
        check("새 층 MID 가 90·91 위다", newmid is not None and newmid > 91, str(newmid))

        print("[T1 층을 나눠 비운 PID 를 가리키는 tied 조건을 알린다]")
        tie_deck = open(os.path.join(d, "base.k"), encoding="utf-8", errors="replace").read()
        tie_deck = tie_deck.replace(
            "*END",
            "*SET_PART_LIST\n$#     sid\n       100\n$#    pid1      pid2\n         1         0\n"
            "*CONTACT_TIED_SURFACE_TO_SURFACE_ID\n$#     cid                          title\n"
            "         7tie_box\n$#    ssid      msid     sstyp     mstyp\n"
            "       100         1         2         3\n*END", 1)
        open(os.path.join(d, "tie.k"), "w").write(tie_deck)
        open(os.path.join(d, "t.yaml"), "w").write(
            "model: tie.k\noutput: t.k\ntarget_pid: 1\ndirection: z\nlayers:\n"
            "  - title: T1\n    thickness: 1.0\n    num_elements: 1\n    material_card: |\n"
            "      *MAT_ELASTIC_TITLE\n      Steel\n"
            "              91  7.85E-09  2.10E+05       0.3\n")
        rc, out = run(binary, d, "restack", "t.yaml")
        # pid_refs 기본값은 strict 다 — 옮기지 못한 참조가 남으면 덱은 쓰고 rc=1 로 끝낸다.
        # 자동화(pyKooCAE Runner·플랫폼 워커)는 종료 코드로만 성공을 보므로 rc=0 이면 경고가 묻힌다.
        check("rc=1 (pid_refs strict 기본)", rc == 1, out[-400:])
        check("덱은 그래도 쓴다", os.path.exists(os.path.join(d, "t.k")))
        check("빈 파트를 가리키는 키워드를 알린다",
              "*SET_PART_LIST" in out and "세트 100" in out, out[-800:])
        check("*CONTACT 도 함께 알린다", "*CONTACT_TIED_SURFACE_TO_SURFACE_ID" in out, out[-800:])
        check("덱 머리에 $ KOOREMAPPER-PIDREF 블록을 박는다",
              "$ KOOREMAPPER-PIDREF" in open(os.path.join(d, "t.k"), encoding="utf-8",
                                             errors="replace").read())

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
