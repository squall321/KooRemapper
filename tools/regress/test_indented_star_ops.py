#!/usr/bin/env python3
# 여섯 op(+ ale)이 들여 쓴 `*` 줄(제목 · *COMMENT 글)을 키워드로 읽지 않는지 — 리더의 1열 규칙과 같은지 보는 회귀 시험
"""들여 쓴 `*` 줄 — contact · cclip · matswap · merge · optimize · modelmeta · ale (2026-11-22 · 3차 6판 · 사용자 결정).

왜 이 시험이 있나.

  리더(LS-DYNA 도)는 1열의 `*` 만 키워드로 읽는다 — 들여 쓴 `*` 줄은 앞 블록의 데이터(제목 · *COMMENT 글)다. 위 op 들의 덱 훑기는
  앞 공백을 지운 줄이 `*` 로 시작하면 키워드로 보아, 제목이 `  *…` 이면 블록을 거기서 닫고 *COMMENT 글 속의 `  *CONTACT_…` 를 접촉으로
  읽었다(rc 0 틀린 산출 · rc 1 엉뚱한 거절). 이제 공용 1열 규칙(deckscan::isKeywordLine)을 쓴다. 사용자 결정 「다음 판에서 여섯 다
  쓸기」 — op 마다 들여 쓴 `*` 제목 사례.

무엇을 보나(각 사례는 같은 덱의 들여 쓰지 않은 판과 견준다).
  ★contact — 세트 제목 `  *AllParts` 의 멤버 셋을 읽는다 · *COMMENT 의 `  *CONTACT_…` · `  *SET_…` 를 접촉 · 세트로 세지 않는다 ·
    create 의 새 CID 를 그 글로 밀어 올리지 않는다
  ★cclip — PART 제목 `  *…` 인 클립 파트를 찾는다(예전엔 「*PART line … not found」 rc 1) · 산출이 대조와 같다 ·
    섹션 · 재질을 나눠 쓰는 파트 제목이 `  *…` 여도 그 섹션 · 재질을 지우지 않는다 · *COMMENT 속 요소 블록 글은 그대로
  ★matswap — 모델 PART 제목 · 번들 PART 제목 · 모래시계를 나눠 쓰는 파트 제목 · 곡선 제목이 `  *…` 여도 산출이 대조와 같다
    (YAML 꼴 · 옛 위치 인자 꼴)
  ★merge — PART · MAT 제목이 `  *…` 여도 산출이 대조와 같다
  ★optimize — *COMMENT 의 `  *CONTROL_IMPLICIT_GENERAL` 로 implicit 이라 보지 않는다 · `  *CONTROL_TIMESTEP` 다음 글 줄을 고치지도
    읽지도 않는다 · `  *CONTROL_ENERGY` 글을 카드로 보지 않고 카드를 넣는다
  ★modelmeta — MAT 제목 `  *Steel_Top` 을 제목으로 읽는다 · *COMMENT 의 `  *MAT_RIGID` 로 재질 1 을 덮지 않는다
  ★ale — 사용자 재질 파일 *COMMENT 의 `  *EOS_GRUNEISEN` 을 EOS 로 싣지 않고 진짜 *EOS_ 를 싣는다

usage: test_indented_star_ops.py <KooRemapper 바이너리>
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
EX = os.path.join(REPO, "examples")
FAILS, OKS = [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-400:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def read(p):
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None


def body(text):
    """견줄 덱 글 — 머리의 생성 주석(시각 · 경로)을 뺀 `*KEYWORD` 부터."""
    if text is None:
        return None
    i = text.find("*KEYWORD")
    return text[i:] if i >= 0 else text


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="istar_")

    def run(tag, files, args):
        d = os.path.join(root, tag)
        os.makedirs(d)
        for name, text in files.items():
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                f.write(text)
        p = subprocess.run([binary] + args, cwd=d, capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace")
        return d, p.returncode, p.stdout + p.stderr

    def ex(*parts):
        return open(os.path.join(EX, *parts), encoding="utf-8").read()

    def sub1(text, old, new):
        assert text.count(old) == 1, (old, text.count(old))
        return text.replace(old, new)

    try:
        # ── contact ──
        model, ana = ex("contact", "model.k"), ex("contact", "01_analyze.yaml")
        star = sub1(model, "\nAllParts\n", "\n  *AllParts\n")
        star = sub1(star, "*KEYWORD\n", "*KEYWORD\n*COMMENT\n  *CONTACT_AUTOMATIC_SINGLE_SURFACE_ID\n         7\n"
                                        "         1         0         2\n  *SET_PART_LIST\n        77\n         1\n")
        _, rc0, o0 = run("ct_plain", {"model.k": model, "a.yaml": ana}, ["contact", "a.yaml"])
        _, rc1, o1 = run("ct_star", {"model.k": star, "a.yaml": ana}, ["contact", "a.yaml"])
        check("★contact — 세트 제목 `  *AllParts` 의 멤버 셋 · *COMMENT 의 `  *CONTACT_…` 는 접촉이 아니다(대조와 같은 2 접촉 · 1 세트)",
              rc0 == 0 and rc1 == 0 and "Found 2 contacts, 1 sets" in o1 and "3 entries [1, 2, 3]" in o1,
              (rc1, re.findall(r"Found [^\n]*|SET_PART[^\n]*", o1)))
        cre = ex("contact", "02_create_part.yaml")
        d1, rc1, o1 = run("ct_create", {"model.k": star, "c.yaml": cre}, ["contact", "c.yaml"])
        res = read(os.path.join(d1, "02_create_part_result.k")) or ""
        check("★contact create — 새 접촉 CID 는 진짜 접촉의 최대(2) 다음 3(*COMMENT 의 `  *CONTACT_…_ID` 의 7 을 세면 8)",
              rc1 == 0 and "\n         3Left_to_Right\n" in res, (rc1, re.findall(r"\n( *\d+Left_to_Right)\n", res), o1[-200:]))

        # ── cclip ──
        d, rc, out = run("cc_gen", {"g.yaml": ex("cclip", "gen_board.yaml")}, ["generate", "box", "g.yaml"])
        board = read(os.path.join(d, "clip_board.k"))
        m = re.search(r"^\*PART[^\n]*\n([^\n]*)\n", board or "", re.M)
        if check("cclip — 대조 판(generate box) rc 0 · *PART 제목", rc == 0 and bool(m), out[-300:]):
            title = m.group(1)
            cfg = ex("cclip", "cclip.yaml")
            d0, rc0, o0 = run("cc_plain", {"clip_board.k": board, "c.yaml": cfg}, ["cclip", "c.yaml"])
            sboard = board.replace("*PART" + m.group(0)[5:], m.group(0).replace("\n" + title + "\n", "\n  *" + title.strip() + "\n"), 1)
            d1, rc1, o1 = run("cc_star", {"clip_board.k": sboard, "c.yaml": cfg}, ["cclip", "c.yaml"])
            a = body(read(os.path.join(d0, "clip_board_cclip.k")))
            b = body(read(os.path.join(d1, "clip_board_cclip.k")))
            b = b.replace("  *" + title.strip() + "\n", title + "\n") if b else b
            check("★cclip — PART 제목 `  *…` 인 클립 파트를 찾고 산출이 대조와 같다(예전엔 「*PART line … not found」 rc 1)",
                  rc0 == 0 and rc1 == 0 and a is not None and a == b, (rc1, o1[-300:]))

            # 섹션 · 재질을 나눠 쓰는 다른 파트(제목 `  *Holder`)와 *COMMENT 속 들여 쓴 요소 블록 — 클립의 옛 섹션 · 재질을 지우지 않고
            # (나눠 쓴다) 글은 그대로 둔다. 대조는 같은 덱의 들여 쓰지 않은 제목 판
            extra = ("*PART\n%s\n         9         2         2\n*COMMENT\n  *ELEMENT_SOLID\n       999         2         1         2"
                     "         3         4         5         6         7         8\n*END")
            pb = board.replace("*END", extra % "Holder", 1)
            sb = board.replace("*END", extra % "  *Holder", 1)
            d0, rc0, o0 = run("cc_hold_plain", {"clip_board.k": pb, "c.yaml": cfg}, ["cclip", "c.yaml"])
            d1, rc1, o1 = run("cc_hold_star", {"clip_board.k": sb, "c.yaml": cfg}, ["cclip", "c.yaml"])
            a = body(read(os.path.join(d0, "clip_board_cclip.k")))
            b = body(read(os.path.join(d1, "clip_board_cclip.k")))
            b = b.replace("  *Holder\n", "Holder\n") if b else b
            check("★cclip — 섹션 · 재질을 나눠 쓰는 파트의 제목이 `  *Holder` 여도 그 섹션 2 · 재질 2 를 지우지 않는다 · *COMMENT 속 "
                  "`  *ELEMENT_SOLID` 글은 그대로", rc0 == 0 and rc1 == 0 and a is not None and a == b and "       999         2" in (b or "")
                  and re.search(r"^\*SECTION_SOLID[^\n]*\n(?:\$[^\n]*\n)*\s+2\s", b or "", re.M) is not None,
                  (rc0, rc1, o1[-300:]))

        # ── matswap ──
        cubes, rubber, cfg = ex("matswap", "two_cubes.k"), ex("matswap", "rubber.k"), ex("matswap", "01_single_pid.yaml")
        d0, rc0, o0 = run("ms_plain", {"two_cubes.k": cubes, "rubber.k": rubber, "s.yaml": cfg}, ["matswap", "s.yaml"])
        a = body(read(os.path.join(d0, "01_single_result.k")))
        for tag, files, fix, what in (
                ("ms_model", {"two_cubes.k": sub1(cubes, "\nCube_1\n", "\n  *Cube_1\n"), "rubber.k": rubber}, ("  *Cube_1\n", "Cube_1\n"),
                 "모델 PART 제목"),
                ("ms_bundle", {"two_cubes.k": cubes, "rubber.k": sub1(rubber, "\nRubber_Part\n", "\n  *Rubber_Part\n")}, None,
                 "번들 PART 제목")):
            files["s.yaml"] = cfg
            d1, rc1, o1 = run(tag, files, ["matswap", "s.yaml"])
            b = body(read(os.path.join(d1, "01_single_result.k")))
            if fix and b:
                b = b.replace(*fix)
            check("★matswap — %s `  *…` 여도 rc 0 · 산출이 대조와 같다" % what, rc0 == 0 and rc1 == 0 and a is not None and a == b,
                  (rc1, o1[-300:]))

        # 옛 위치 인자 꼴(matswap <model> <bundle> <pid> <output>) — 같은 op 의 다른 훑기(msw_*)
        args = ["matswap", "two_cubes.k", "rubber.k", "1", "o.k"]
        d0, rc0, o0 = run("msl_plain", {"two_cubes.k": cubes, "rubber.k": rubber}, args)
        a = body(read(os.path.join(d0, "o.k")))
        for tag, files, fix, what in (
                ("msl_model", {"two_cubes.k": sub1(cubes, "\nCube_1\n", "\n  *Cube_1\n"), "rubber.k": rubber}, ("  *Cube_1\n", "Cube_1\n"),
                 "모델 PART 제목"),
                ("msl_bundle", {"two_cubes.k": cubes, "rubber.k": sub1(rubber, "\nRubber_Part\n", "\n  *Rubber_Part\n")}, None,
                 "번들 PART 제목")):
            d1, rc1, o1 = run(tag, files, args)
            b = body(read(os.path.join(d1, "o.k")))
            if fix and b:
                b = b.replace(*fix)
            check("★matswap(위치 인자 꼴) — %s `  *…` 여도 rc 0 · 산출이 대조와 같다" % what,
                  rc0 == 0 and rc1 == 0 and a is not None and a == b, (rc1, o1[-300:]))

        # 둘째 파트가 HGID 1 을 나눠 쓰고(제목 `  *Cube_2`) 모델에 곡선 5(제목 `  *Load`)가 있다 — 모래시계 1 을 지우지 않고(나눠 쓴다)
        # 번들 곡선은 6 을 받는다. 두 꼴(YAML · 옛 위치 인자) 다
        row2 = "         2         2         2         0         2         0         0         0"
        curve = "*DEFINE_CURVE_TITLE\n%s\n         5\n       0.0       0.0\n       1.0       1.0\n*END"
        shared = sub1(cubes, row2, row2[:40] + "         1" + row2[50:])
        pm = shared.replace("*END", curve % "Load", 1)
        sm = sub1(shared, "\nCube_2\n", "\n  *Cube_2\n").replace("*END", curve % "  *Load", 1)
        for form, args, outname in (("YAML", ["matswap", "s.yaml"], "01_single_result.k"),
                                    ("위치 인자", ["matswap", "two_cubes.k", "rubber.k", "1", "o.k"], "o.k")):
            d0, rc0, o0 = run("ms_sh_plain_%d" % len(form), {"two_cubes.k": pm, "rubber.k": rubber, "s.yaml": cfg}, args)
            d1, rc1, o1 = run("ms_sh_star_%d" % len(form), {"two_cubes.k": sm, "rubber.k": rubber, "s.yaml": cfg}, args)
            a, b = body(read(os.path.join(d0, outname))), body(read(os.path.join(d1, outname)))
            if b:
                b = b.replace("  *Cube_2\n", "Cube_2\n").replace("  *Load\n", "Load\n")
            check("★matswap(%s) — HGID 를 나눠 쓰는 파트 · 곡선의 제목이 `  *…` 여도 모래시계 1 을 지우지 않고 번들 곡선은 6(산출이 대조와 같다)"
                  % form, rc0 == 0 and rc1 == 0 and a is not None and a == b and "LCID) 1 -> 6" in o1, (rc1, o1[-300:]))

        # swap_all · mids 는 YAML 길의 다른 훑기(파트 전부 · MID 로 고르기)를 쓴다 — 제목 `  *Cube_2` 인 파트도 고른다
        for tag, extra in (("all", "    swap_all: true\n"), ("mids", "    mids: [2]\n")):
            yml = "model: two_cubes.k\noutput: r.k\nswaps:\n  - bundle: rubber.k\n" + extra
            d0, rc0, o0 = run("ms_%s_plain" % tag, {"two_cubes.k": cubes, "rubber.k": rubber, "s.yaml": yml}, ["matswap", "s.yaml"])
            d1, rc1, o1 = run("ms_%s_star" % tag, {"two_cubes.k": sub1(cubes, "\nCube_2\n", "\n  *Cube_2\n"), "rubber.k": rubber,
                                                   "s.yaml": yml}, ["matswap", "s.yaml"])
            a, b = body(read(os.path.join(d0, "r.k"))), body(read(os.path.join(d1, "r.k")))
            b = b.replace("  *Cube_2\n", "Cube_2\n") if b else b
            check("★matswap(%s) — 제목 `  *Cube_2` 인 파트도 고른다(산출이 대조와 같다)" % ("swap_all" if tag == "all" else "mids: [2]"),
                  rc0 == 0 and rc1 == 0 and a is not None and a == b, (rc0, rc1, o1[-300:]))

        # mids 꼴은 번들의 *SECTION 블록을 걸러 낸다(ELFORM 은 모델 그대로) — 번들 섹션 제목이 `  *Rubber_Section` 이어도 그 블록을 통째로
        yml = "model: two_cubes.k\noutput: r.k\nswaps:\n  - bundle: rubber.k\n    mids: [2]\n"
        d0, rc0, o0 = run("ms_midsec_plain", {"two_cubes.k": cubes, "rubber.k": rubber, "s.yaml": yml}, ["matswap", "s.yaml"])
        d1, rc1, o1 = run("ms_midsec_star", {"two_cubes.k": cubes, "rubber.k": sub1(rubber, "\nRubber_Section\n", "\n  *Rubber_Section\n"),
                                             "s.yaml": yml}, ["matswap", "s.yaml"])
        a, b = body(read(os.path.join(d0, "r.k"))), body(read(os.path.join(d1, "r.k")))
        check("★matswap(mids) — 번들 섹션 제목이 `  *Rubber_Section` 이어도 그 *SECTION 블록을 통째로 걸러 낸다(산출이 대조와 같다)",
              rc0 == 0 and rc1 == 0 and a is not None and a == b, (rc1, [l for l in (b or "").splitlines() if "Rubber_Section" in l or "        13" in l][:3]))

        # ── merge ──
        layers, cfg = ex("merge", "three_layer.k"), ex("merge", "merge_test.yaml")
        d0, rc0, o0 = run("mg_plain", {"three_layer.k": layers, "m.yaml": cfg}, ["merge", "m.yaml"])
        sl = sub1(sub1(layers, "\nPolymer_Layer\n", "\n  *Polymer_Layer\n"), "\nSteel_E210\n", "\n  *Steel_E210\n")
        d1, rc1, o1 = run("mg_star", {"three_layer.k": sl, "m.yaml": cfg}, ["merge", "m.yaml"])
        a, b = body(read(os.path.join(d0, "merged_output.k"))), body(read(os.path.join(d1, "merged_output.k")))
        if b:
            b = b.replace("  *Polymer_Layer\n", "Polymer_Layer\n").replace("  *Steel_E210\n", "Steel_E210\n")
        check("★merge — PART · MAT 제목 `  *…` 여도 rc 0 · 산출이 대조와 같다", rc0 == 0 and rc1 == 0 and a is not None and a == b,
              (rc1, o1[-300:]))

        # ── optimize ──
        ctl = ("*CONTROL_TIMESTEP\n$#  dtinit    tssfac      isdo    tslimt     dt2ms      lctm     erode     ms1st\n"
               "       0.0       0.9         0       0.0       0.0         0         0         0\n")
        note = "*COMMENT\n  *CONTROL_IMPLICIT_GENERAL\n  *CONTROL_ENERGY\n  *CONTROL_TIMESTEP\n  memo — 0.9 above is a note, not a card\n"
        ocfg = "model: m.k\noutput: o.k\noptimize: rubber\npids: [1]\ntssfac: 0.67\n"
        d0, rc0, o0 = run("op_plain", {"m.k": sub1(cubes, "*END", ctl + "*END"), "o.yaml": ocfg}, ["optimize", "o.yaml"])
        d1, rc1, o1 = run("op_star", {"m.k": sub1(cubes, "*END", note + ctl + "*END"), "o.yaml": ocfg}, ["optimize", "o.yaml"])
        a, b = body(read(os.path.join(d0, "o.k"))), body(read(os.path.join(d1, "o.k")))
        b2 = b.replace(note, "") if b else b
        check("★optimize — *COMMENT 의 `  *CONTROL_IMPLICIT_GENERAL` 로 implicit 이라 보지 않는다(대조처럼 explicit)",
              rc0 == 0 and rc1 == 0 and "implicit" not in [l for l in o1.splitlines() if "Analysis type" in l][0], o1[-300:])
        check("★optimize — *COMMENT 글은 그대로 · *CONTROL_TIMESTEP 의 TSSFAC 을 고친다(산출이 대조 + 그 글)",
              b is not None and note in b and a == b2, (b or "")[-400:])
        ts0 = [l for l in o0.splitlines() if "TSSFAC" in l]
        ts1 = [l for l in o1.splitlines() if "TSSFAC" in l]
        check("★optimize — TSSFAC 보고(옛 값)를 진짜 *CONTROL_TIMESTEP 에서 읽는다 · *CONTROL_ENERGY 는 글이 아니라 없으니 넣는다(대조와 같다)",
              bool(ts0) and ts0 == ts1 and o1.count("*CONTROL_ENERGY:") == 1 and "(inserted)" in [l for l in o1.splitlines()
                                                                                            if "*CONTROL_ENERGY:" in l][0], (ts0, ts1))

        # ── modelmeta ──
        mcube = sub1(sub1(cubes, "\nSteel_Top\n", "\n  *Steel_Top\n"), "*END",
                     "*COMMENT\n  *MAT_RIGID\n         1  7.8500E-09  210000.0       0.3\n*END")
        d1, rc1, o1 = run("mm_star", {"m.k": mcube, "mm.yaml": "model: m.k\noutput: m\n"}, ["modelmeta", "mm.yaml"])
        try:
            parts = json.loads(read(os.path.join(d1, "m_modelmeta.json")) or "{}").get("parts", [])
        except ValueError:
            parts = []
        k1 = next((((x.get("material") or {}).get("kfile") or {}) for x in parts if x.get("pid") == 1), {})
        check("★modelmeta — MAT 제목 `  *Steel_Top` 을 제목으로 읽고 *COMMENT 의 `  *MAT_RIGID` 로 재질 1 을 덮지 않는다",
              rc1 == 0 and k1.get("keyword") == "*MAT_ELASTIC_TITLE" and k1.get("name") == "*Steel_Top", (rc1, k1, o1[-200:]))

        # ── ale ──
        mat = ("*KEYWORD\n*COMMENT\n  *EOS_GRUNEISEN\n         9       1.0       2.0\n*MAT_NULL\n$      MID        RO\n"
               "         1  1.000E-9\n*EOS_LINEAR_POLYNOMIAL\n$    EOSID        C0        C1        C2        C3        C4"
               "        C5        C6\n         1       0.0       0.0       0.0       0.0       0.4       0.4       0.0\n"
               "$       E0        V0\n    2.5E-4       1.0\n*END\n")
        acfg = "model: explicit.k\noutput: a.k\nale_parts:\n  - pid: 3\n    material: mymat.k\n"
        d1, rc1, o1 = run("ale_star", {"explicit.k": ex("ale", "explicit.k"), "mymat.k": mat, "a.yaml": acfg}, ["ale", "a.yaml"])
        out = read(os.path.join(d1, "a.k")) or ""
        eos = re.search(r"EOSID=(\d+)", o1)
        poly = re.search(r"^\*EOS_LINEAR_POLYNOMIAL\n(?:\$[^\n]*\n)*([^\n]*)\n", out, re.M)
        check("★ale — *COMMENT 의 `  *EOS_GRUNEISEN` 을 싣지 않고 진짜 *EOS_LINEAR_POLYNOMIAL 을 새 EOSID 로 싣는다",
              rc1 == 0 and "*EOS_GRUNEISEN" not in out and bool(eos) and bool(poly)
              and poly.group(1)[0:10].strip() == eos.group(1), (rc1, eos and eos.group(1), poly and poly.group(1), o1[-200:]))
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
