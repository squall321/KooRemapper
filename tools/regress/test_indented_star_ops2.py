#!/usr/bin/env python3
# 6판 여섯 op 밖의 덱 훑기 · 리더 · 공용 재질 훑기가 들여 쓴 `*` 줄(제목 · *COMMENT 글)을 키워드로 읽지 않는지 보는 회귀 시험
"""들여 쓴 `*` 줄 — 여섯 op 밖 나머지(2026-11-23 · 3차 7판 L-24 · 사용자 결정 「다음 판에서 다 쓸기」).

왜 이 시험이 있나.

  6판에서 contact · cclip · matswap · merge · optimize · modelmeta(+ ale)를 공용 1열 규칙(deckscan::isKeywordLine)으로 맞췄다. 그 밖에도
  앞 공백을 지운 줄(또는 첫 비공백 글자)이 `*` 면 키워드로 보는 훑기가 남아 있었다 — 리더의 미리 훑기(파트 · 섹션 ELFORM)와 인클루드 폭
  바꿈 찾기 · 인클루드 닫힘의 폭 표지 · 공용 재질 번호 훑기(matids) · 재질 카드 검사기(줄 어디든 「*MAT」 면 키워드) · 요소 카드 걸음
  (ecWalk) · assemble 의 matdb · elform · update · merge · 점탄성 카드 읽기 · stabilize · iga 산출 목록 · apply_carryover_plan · 조각 ·
  cad_solid_merge_to_deck · rebind. 들여 쓴 「  *SECTION_SOLID / 1 23」 글 하나에 리더가 파트를 2차 솔리드로 보고, 「  *MAT_ELASTIC / 99」
  에 새 재질 번호가 100 으로 뛰는 꼴이다. 이제 다 공용 규칙을 쓴다.

무엇을 보나(op 마다 같은 입력을 여러 판으로 돌린다).
  ★독 — 입력 덱의 맨 앞 `*KEYWORD` 뒤(없으면 맨 앞)에 들여 쓴 키워드 줄과 숫자 줄을 담은 `*COMMENT` 를 끼워도 rc 0 이고 산출에서 그
    블록을 빼면 그대로 판의 산출과 바이트까지 같다(쓴 시각 머리줄만 뺀다)
  ★제목 — `_TITLE` · `*PART` 의 제목 줄을 「  *제목」 으로 바꿔도 rc 0 이고 산출의 그 줄을 되돌리면 그대로 판과 같다
  ★재질 카드 — assemble restack 의 material_card 글에 「$ … *MAT_024 …」 주석 줄을 더해도 rc 0 · 산출이 같다

usage: test_indented_star_ops2.py <KooRemapper 바이너리>
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples")
FAILS, OKS = [], []

# 독 — 들여 쓴 키워드 줄과 그것의 데이터처럼 보이는 숫자 줄(1열이 아니라 *COMMENT 의 글이다)
BLOCK = ["*COMMENT",
         "  *KEYWORD LONG=Y",
         "  *INCLUDE +",
         "  *MAT_ELASTIC",
         "        99 7.850E-09  210000.0       0.3",
         "  *SECTION_SOLID",
         "         1        23",
         "  *SECTION_SHELL",
         "        77         2",
         "  *PART",
         "  ghost",
         "        88        77        99",
         "  *SET_NODE_LIST",
         "        66",
         "         1         2",
         "  *CONTROL_CONTACT",
         "  *CONTROL_ENERGY",
         "  *CONTROL_TIMESTEP",
         "  *ELEMENT_SOLID",
         "       999         1         1         2         3         4         5         6         7         8",
         "  *NODE",
         "         2             9.9             9.9             9.9",
         "  *HOURGLASS",
         "        33",
         "  *DEFINE_CURVE",
         "        22"]
BOX = "output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 10\nny: 5\nnz: 2\nrho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n"


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-500:]))
    print("  %-96s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args, env=None):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, p.stdout + p.stderr


def read(path):
    with open(path, "rb") as f:
        return f.read()


def poison(path):
    """맨 앞 1열 `*KEYWORD` 줄 뒤(없으면 맨 앞)에 BLOCK 을 끼운다."""
    raw = read(path).decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    L = raw.split(nl)
    at = next((i + 1 for i, l in enumerate(L) if l.upper().startswith("*KEYWORD")), 0)
    L[at:at] = BLOCK
    with open(path, "wb") as f:
        f.write(nl.join(L).encode("utf-8"))


def title_star(path):
    """`_TITLE` · `*PART` 의 제목 줄(주석 뺀 첫 줄)을 「  *제목」 으로 — 바꾼 제목들을 돌려준다."""
    raw = read(path).decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    L = raw.split(nl)
    titles, want = set(), False
    for i, l in enumerate(L):
        if l.startswith("*"):
            k = l.split()[0].upper() if l.split() else ""
            want = k.endswith("_TITLE") or k == "*PART"
            continue
        if want and not l.startswith("$"):
            want = False
            t = l.rstrip()
            if t and not t[0].isspace() and not t[0].isdigit() and "&" not in t:
                L[i] = "  *" + t
                titles.add(t)
    with open(path, "wb") as f:
        f.write(nl.join(L).encode("utf-8"))
    return titles


def undated(data):
    """쓴 시각 머리줄을 빼고, `$` 진단 주석의 입력 줄 번호(「line 36」 — 끼운 줄만큼 밀린다)를 맞춘다."""
    out = []
    for l in data.split(b"\n"):
        if l.startswith(b"$ Date:") or l.startswith(b"$ Generated"):
            continue
        out.append(re.sub(rb"line \d+", b"line N", l) if l.startswith(b"$") else l)
    return b"\n".join(out)


def strip_block(data):
    text = data.decode("utf-8", errors="replace")
    nl = "\r\n" if "\r\n" in text else "\n"
    L = text.split(nl)
    i = 0
    while i <= len(L) - len(BLOCK):   # 덱마다 끼운 블록이 펼친 산출에 여럿 있을 수 있다 — 다 뺀다
        if L[i:i + len(BLOCK)] == BLOCK:
            del L[i:i + len(BLOCK)]
        else:
            i += 1
    return nl.join(L).encode("utf-8")


def unstar(data, titles):
    text = data.decode("utf-8", errors="replace")
    for t in titles:
        text = text.replace("  *" + t, t)
    return text.encode("utf-8")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="istar2_")
    try:
        base = os.path.join(top, "base")
        os.makedirs(base)
        with open(os.path.join(base, "box.yaml"), "w") as f:
            f.write(BOX)
        run(binary, base, "generate", "box", "box.yaml")
        box = os.path.join(base, "box.k")
        cubes = os.path.join(EX, "matswap", "two_cubes.k")
        rubber = os.path.join(EX, "matswap", "rubber.k")
        dyn = os.path.join(base, "u.dynain")
        with open(dyn, "w") as f:
            f.write("*KEYWORD\n*NODE\n       1             0.1             0.0             0.0\n*END\n")
        ctl = os.path.join(base, "cubes_ctl.k")
        with open(ctl, "w") as f:
            f.write(open(cubes, encoding="utf-8").read().replace(
                "*END", "*CONTROL_CONTACT\n$#  slsfac    rwpnal    islchk    shlthk    penopt    thkchg     orien    enmass\n"
                        "       0.1       0.0         2         0         1         0         1         0\n*END"))
        noinc = os.path.join(base, "part2_noinc.k")
        with open(noinc, "w") as f:
            f.write("".join(l for l in open(os.path.join(EX, "extract-parts", "part2_include.k"), encoding="utf-8")
                            if not l.upper().startswith("*KEYWORD")))
        dirs = lambda name: {n: os.path.join(EX, name, n) for n in os.listdir(os.path.join(EX, name))
                             if os.path.isfile(os.path.join(EX, name, n)) and not n.endswith(("_result.k", ".docx", ".md", ".py"))}
        # (이름, 깔 파일, 독 · 제목을 넣을 파일, 명령, 산출, 설정)
        cases = [
            ("extract-parts(리더 미리 훑기)", {"two_cubes.k": cubes}, ["two_cubes.k"], ["extract-parts", "c.yaml"], ["out.k"],
             {"c.yaml": "model: two_cubes.k\noutput: out.k\nparts: [1, 2]\n"}),
            ("matswap(공용 재질 번호)", {"two_cubes.k": cubes, "rubber.k": rubber}, ["two_cubes.k"], ["matswap", "c.yaml"], ["s.k"],
             {"c.yaml": "model: two_cubes.k\noutput: s.k\nswaps:\n  - bundle: rubber.k\n    pid: 1\n"}),
            ("matdb", {"two_cubes.k": cubes, "materials/material_db.json": os.path.join(REPO, "materials", "material_db.json")},
             ["two_cubes.k"], ["matdb", "c.yaml"], ["m.k"],
             {"c.yaml": "model: two_cubes.k\noutput: m.k\nmat_type: MAT_ELASTIC\nmaterials:\n  - mid: 1\n    match: \"SUS304\"\n"}),
            ("stabilize", {"cubes_ctl.k": ctl}, ["cubes_ctl.k"], ["stabilize", "c.yaml"], ["st.k"],
             {"c.yaml": "model: cubes_ctl.k\noutput: st.k\nstabilize: explicit\nlevel: 3\n"}),
            ("assemble elform", dirs("elform"), ["simple_hex.k"], ["assemble", "elform_case_a.yaml"], ["elform_case_a_result.k"], {}),
            ("assemble update", {"two_cubes.k": cubes, "u.dynain": dyn}, ["u.dynain", "two_cubes.k"], ["assemble", "c.yaml"], ["au.k"],
             {"c.yaml": "base_model: two_cubes.k\noutput: au\noperations:\n  - type: update\n    dynain: u.dynain\n"}),
            ("assemble merge", {"three_layer.k": os.path.join(EX, "merge", "three_layer.k")}, ["three_layer.k"], ["assemble", "c.yaml"],
             ["am.k"], {"c.yaml": "base_model: three_layer.k\noutput: am\noperations:\n  - type: merge\n    pids: [1, 2, 3]\n"
                                  "    direction: z\n    method: vrh\n"}),
            ("assemble split", {"box.k": box}, ["box.k"], ["assemble", "c.yaml"], ["sp.k"],
             {"c.yaml": "base_model: box.k\noutput: sp\noperations:\n  - type: split\n    pid: 1\n    direction: x\n    divisions: 2\n"}),
            ("rebind", dirs("rebind_entities_after_remesh"), ["v1.k", "v2.k", "ours.k"], ["rebind_entities_after_remesh", "rebind.yaml"],
             ["ours_rebound.k"], {}),
            ("apply_carryover_plan", dirs("apply_carryover_plan"), ["deck.k"], ["apply_carryover_plan", "c.yaml"], ["out.k"],
             {"c.yaml": "model: deck.k\nplan: plan.json\noutput: out.k\n"}),
            ("cad_solid_merge_to_deck", dirs("cad_solid_merge_to_deck"), ["deck.k"], ["cad_solid_merge_to_deck", "merge.yaml"],
             ["merged.k"], {}),
            ("assemble iga", {"block_2x2x1.k": os.path.join(EX, "iga", "block_2x2x1.k"), "iga_single.yaml": os.path.join(EX, "iga", "iga_single.yaml")},
             ["block_2x2x1.k"], ["assemble", "iga_single.yaml"], ["iga_single_result.k", "iga_single_result_iga_p1.k"], {}),
            ("extract-parts(폭 표지 없는 인클루드)", {"assembly.k": os.path.join(EX, "extract-parts", "assembly.k"), "part2_include.k": noinc},
             ["assembly.k", "part2_include.k"], ["extract-parts", "c.yaml"], ["extracted.k"],
             {"c.yaml": "model: assembly.k\noutput: extracted.k\nparts: [1, 2]\n"}),
        ]

        def materialize(d, files, cfg):
            for dst, src in files.items():
                os.makedirs(os.path.dirname(os.path.join(d, dst)) or d, exist_ok=True)
                shutil.copy(src, os.path.join(d, dst))
            for dst, text in cfg.items():
                with open(os.path.join(d, dst), "w") as f:
                    f.write(text)

        def fix_plan(d):
            pp = os.path.join(d, "plan.json")
            if os.path.exists(pp) and os.path.exists(os.path.join(d, "deck.k")):
                plan = json.load(open(pp, encoding="utf-8"))
                if isinstance(plan.get("deck"), dict) and "sha256" in plan["deck"]:
                    plan["deck"]["sha256"] = hashlib.sha256(read(os.path.join(d, "deck.k"))).hexdigest()
                    with open(pp, "w", encoding="utf-8") as f:
                        f.write(json.dumps(plan, ensure_ascii=False, indent=1))

        print("[op 마다 — 독 *COMMENT · 제목 「  *…」 판의 산출이 그대로 판과 같다]")
        for name, files, targets, argv, outs, cfg in cases:
            res, titles = {}, set()
            for variant in ("plain", "poison", "title"):
                d = os.path.join(top, re.sub(r"\W+", "_", name), variant)
                os.makedirs(d)
                materialize(d, files, cfg)
                if variant == "poison":
                    for t in targets:
                        poison(os.path.join(d, t))
                elif variant == "title":
                    for t in targets:
                        if t.endswith(".k"):
                            titles |= title_star(os.path.join(d, t))
                    for j in os.listdir(d):   # 제목으로 파트를 가리키는 표(rebind 구간 표)도 리더가 읽을 제목 「*…」 로
                        if j.endswith(".json") and j != "plan.json":
                            txt = open(os.path.join(d, j), encoding="utf-8").read()
                            for t in titles:
                                txt = txt.replace('"%s"' % t, '"*%s"' % t)
                            open(os.path.join(d, j), "w", encoding="utf-8").write(txt)
                fix_plan(d)
                rc, out = run(binary, d, *argv)
                res[variant] = (rc, out, [read(os.path.join(d, o)) if os.path.exists(os.path.join(d, o)) else None for o in outs])
            rc0, out0, o0 = res["plain"]
            for variant in ("poison", "title"):
                rc1, out1, o1 = res[variant]
                norm = (lambda b: undated(strip_block(b))) if variant == "poison" else (lambda b: undated(unstar(b, titles)))
                same = all(a is not None and b is not None and norm(b) == undated(a) for a, b in zip(o0, o1))
                if variant == "title" and not titles:
                    continue
                check("★%s · %s — rc 0 · 산출이 그대로 판과 같다%s" % (name, "독 *COMMENT" if variant == "poison" else "제목 %d 개 「  *…」" % len(titles),
                                                                  "" if variant == "poison" else ""),
                      rc0 == 0 and rc1 == 0 and same, (rc0, rc1, [x is None for x in o0], [x is None for x in o1], out1[-400:]))

        # 재질 카드 — YAML material_card 글의 `$` 주석에 「*MAT」 이 있어도 키워드가 아니다(재질 카드 검사기)
        rs = os.path.join(EX, "replace_test")
        res = {}
        for variant in ("plain", "card"):
            d = os.path.join(top, "restack", variant)
            os.makedirs(d)
            shutil.copy(os.path.join(rs, "restack_base.k"), d)
            y = open(os.path.join(rs, "assemble_restack_test.yaml"), encoding="utf-8").read()
            if variant == "card":
                y = y.replace("          *MAT_ELASTIC\n", "          *MAT_ELASTIC\n          $ note — a *MAT_024 card also works here\n")
            open(os.path.join(d, "r.yaml"), "w", encoding="utf-8").write(y)
            rc, out = run(binary, d, "assemble", "r.yaml")
            res[variant] = (rc, out, read(os.path.join(d, "restack_result.k")) if os.path.exists(os.path.join(d, "restack_result.k")) else None)
        (rc0, out0, a), (rc1, out1, b) = res["plain"], res["card"]
        b2 = b.replace(b"$ note \xe2\x80\x94 a *MAT_024 card also works here\n", b"") if b else b
        check("★assemble restack · material_card 의 `$ … *MAT_024 …` 주석 — rc 0 · 산출(주석 줄 뺀)이 그대로 판과 같다",
              rc0 == 0 and rc1 == 0 and a is not None and b2 is not None and undated(b2) == undated(a), (rc0, rc1, out1[-400:]))
    finally:
        shutil.rmtree(top, ignore_errors=True)
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
