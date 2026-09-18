# YAML 블록 스칼라 지시자·따옴표 스칼라·대시만 있는 목록 항목 회귀 시험 — 빌드 바이너리를 실제로 실행
"""
사용: python3 tools/regress/test_yaml_block_scalars.py <KooRemapper 바이너리>

배경(감사에서 재현된 결함)
  - R2 카드 키의 값을 val == "|" 로 정확 비교해, '|-' '|+' '|2' '>' 같은 정상 블록 표기와 따옴표
        스칼라가 else 로 빠졌다. 그 값(두 글자 '|-' 이나 "*MAT_...\\n..." 한 줄)이 그대로 *MAT 카드가
        되어 덱에 쓰레기 한 줄이 찍히고 *PART 의 mid 가 0 이 됐다(rc=0, 경고 0줄).
        플랫폼(argbuild)·pyKooCAE(yaml.safe_dump)는 조건에 따라 따옴표 스칼라를 내보내므로,
        웹·MCP·체인 경로로 들어온 정상 카드가 이 자리에서 조용히 깨졌다.
        PyYAML 은 80칸이 넘는 값을 '\\' + 줄바꿈으로 접으므로 여러 줄에 걸친 따옴표 값도 이어 읽어야 한다.
  - R2' '>' (접기) 블록은 카드를 한 줄로 만든다. LS-DYNA 카드는 줄 단위라 접힌 카드는 반드시 깨지므로
        받아들이지 않고 rc=1 로 거절한다(경고만 내면 '조용히 틀린 덱' 이 된다).
  - R2'' 카드로 볼 수 없는 값(빈 값, *MAT 줄 없음, 키워드 줄만 있고 데이터 줄 없음)은 MID 를 쓸 자리가
        없어 mid 0 덱이 된다 — rc=1 로 거절한다.
  - R7 '-' 만 있는 줄로 여는 목록 항목(다음 줄부터 키)이 정상 YAML 인데 'no layers defined for restack'
        (assemble 은 'No operations defined')으로 거부됐다.
  - R2a 카드 키워드 줄이 1열에서 시작하지 않으면(‘|1’·‘|2’ 지시자나 앞 공백이 든 따옴표 값) LS-DYNA 가
        키워드로 읽지 않아 앞 카드의 데이터 줄처럼 붙고 *PART 의 mid 가 정의되지 않은 MID 를 가리켰다.
  - R2b '*MAT_..._TITLE' 인데 내용 줄이 하나뿐이면 제목·데이터 중 하나가 빠진 것이라 MID 를 쓸 자리가
        없다 — rc=0 에 경고 0줄로 mid 0 덱이 나갔다.
  - R2c '|4' 처럼 지시자가 요구하는 열보다 내용이 얕은 블록(PyYAML 은 ParserError)을 단독은 rc=0 덱으로,
        assemble 은 rc=1 'has no material_card' 로 갈라 읽었다. 카드 '가운데' 빈 줄도 단독은 버리고
        assemble 은 남겨 덱이 한 줄 달랐다(LS-DYNA 는 빈 줄을 칸이 모두 0 인 데이터 카드로 읽는다).
"""
import os
import subprocess
import sys
import tempfile

FAILS = []

BOX = ("output: box.k\nlx: 20.0\nly: 10.0\nlz: 2.0\nnx: 4\nny: 2\nnz: 1\n"
       "rho: 7.85e-9\nE: 210000.0\nnu: 0.3\nmid: 1\nsecid: 1\npid: 1\npart_title: PLATE\n")

# 제목 줄이 있는 정상 카드 두 장 — MID 칸(1~10열)이 새 번호로 바뀌는지 본다
CARD1 = ("*MAT_ELASTIC_TITLE\n"
         "Substrate\n"
         "$#     mid        ro         e        pr\n"
         "        90  7.85E-09  2.10E+05       0.3")
CARD2 = CARD1.replace("Substrate", "Cover").replace("        90", "        91")


def check(name, cond, detail=""):
    print("  %-70s %s" % (name, "OK" if cond else "FAIL"))
    if not cond:
        FAILS.append(f"{name} {detail}")


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def workdir(binary, tag):
    d = tempfile.mkdtemp(prefix=f"blockscalar_{tag}_")
    open(os.path.join(d, "box.yaml"), "w").write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    return d


def parts_and_mats(path):
    """({pid: mid}, {mid: (keyword, title, data_line)}) — *PART·*MAT 을 덱에서 그대로 읽는다"""
    L = open(path).read().splitlines()
    parts, mats = {}, {}
    i = 0
    while i < len(L):
        if L[i].startswith("*PART"):
            d = []
            j = i + 1
            while j < len(L) and not L[j].startswith("*"):
                if L[j].strip() and not L[j].startswith("$"):
                    d.append(L[j])
                j += 1
            if len(d) >= 2:
                try:
                    parts[int(d[1][0:10])] = int(d[1][20:30])
                except ValueError:
                    pass
        elif L[i].startswith("*MAT"):
            kw = L[i].strip()
            d = []
            j = i + 1
            while j < len(L) and not L[j].startswith("*"):
                if L[j].strip():
                    d.append(L[j])
                j += 1
            title = ""
            body = list(d)
            if kw.endswith("_TITLE") and body:
                title = body.pop(0).strip()
            body = [b for b in body if not b.startswith("$")]
            if body:
                try:
                    mats[int(body[0][0:10])] = (kw, title, body[0])
                except ValueError:
                    pass
        i += 1
    return parts, mats


def indent_block(text, n):
    return "".join(" " * n + ln + "\n" for ln in text.split("\n"))


def standalone_yaml(layers_body):
    return ("model: box.k\noutput: out\ntarget_pid: 1\ndirection: z\nelement_type: solid\n"
            "layers:\n" + layers_body)


def assemble_yaml(layers_body):
    body = "".join(("    " + ln if ln.strip() else "") + "\n" for ln in layers_body.split("\n"))
    return ("base_model: box.k\noutput: out\noperations:\n  - type: restack\n"
            "    target_pid: 1\n    direction: z\n    element_type: solid\n    layers:\n" + body)


def layers_with(indicator, card1=CARD1, card2=CARD2):
    """'material_card: <지시자>' 두 층 — 내용 줄은 키보다 2칸 깊게"""
    out = ""
    for card in (card1, card2):
        out += "  - thickness: 1.0\n    material_card: " + indicator + "\n" + indent_block(card, 6)
    return out


def both_paths(binary, tag, layers_body, expect_rc=0, want_msg=None, want_mids=(90, 91),
               want_titles=("Substrate", "Cover")):
    """같은 층 목록을 단독 restack 과 assemble 로 돌려 rc·덱이 같은지 본다"""
    d = workdir(binary, tag)
    open(os.path.join(d, "sa.yaml"), "w").write(standalone_yaml(layers_body))
    open(os.path.join(d, "as.yaml"), "w").write(assemble_yaml(layers_body))
    rc1, o1 = run(binary, d, "restack", "sa.yaml")
    sa_k = os.path.join(d, "out.k")
    sa_txt = open(sa_k).read() if rc1 == 0 and os.path.exists(sa_k) else None
    if os.path.exists(sa_k):
        os.remove(sa_k)
    rc2, o2 = run(binary, d, "assemble", "as.yaml")
    as_txt = open(sa_k).read() if rc2 == 0 and os.path.exists(sa_k) else None

    check(f"[{tag}] 단독 restack rc={expect_rc}", rc1 == expect_rc, f"rc={rc1} {o1[-220:]}")
    check(f"[{tag}] assemble rc={expect_rc}", rc2 == expect_rc, f"rc={rc2} {o2[-220:]}")
    if want_msg:
        check(f"[{tag}] 단독 오류 메시지에 '{want_msg}'", want_msg in o1, o1[-220:])
        check(f"[{tag}] assemble 오류 메시지에 '{want_msg}'", want_msg in o2, o2[-220:])
    if expect_rc != 0 or rc1 != 0 or rc2 != 0:
        return
    check(f"[{tag}] 두 경로 덱이 완전히 같다", sa_txt == as_txt, "덱이 다르다")
    parts, mats = parts_and_mats(sa_k)
    layer_mids = [parts.get(2), parts.get(3)]
    check(f"[{tag}] 층 PART 의 mid 가 0 이 아니다", all(m for m in layer_mids), str(parts))
    check(f"[{tag}] 층마다 다른 *MAT 카드가 실렸다",
          len(set(layer_mids)) == 2 and all(m in mats for m in layer_mids if m),
          f"{layer_mids} {list(mats)}")
    if all(m in mats for m in layer_mids if m):
        if want_titles:   # 제목 줄이 없는 '_TITLE' 아닌 카드는 견줄 제목이 없다
            titles = [mats[m][1] for m in layer_mids]
            check(f"[{tag}] 카드 제목이 그대로다 ({'/'.join(want_titles)})",
                  titles == list(want_titles), str(titles))
        ros = [mats[m][2][10:20].strip() for m in layer_mids]
        check(f"[{tag}] 둘째 칸(RO)이 살아 있다", ros == ["7.85E-09", "7.85E-09"], str(ros))
    return sa_txt


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    binary = os.path.abspath(sys.argv[1])

    # ── 블록 지시자 전 종류 × (단독/assemble) ────────────────────────────────
    print("[R2] 블록 스칼라 지시자 — '|' 뿐 아니라 잘라내기(-,+)·명시 들여쓰기(숫자)도 블록이다")
    base = None
    for indicator in ("|", "|-", "|+", "|2", "|2-", "|-2"):
        txt = both_paths(binary, "ind" + indicator.replace("|", "P"), layers_with(indicator))
        if indicator == "|":
            base = txt
        elif txt and base:
            # 카드 블록은 chomping 지시자를 알아보되 끝 빈 줄은 어느 쪽이든 버린다(clip) —
            # *MAT 카드 뒤 빈 줄은 LS-DYNA 에 뜻이 없고, 같은 카드를 '다른 카드' 로 만들어 MID 를 쪼갠다
            check(f"[ind{indicator}] '{indicator}' 덱이 '|' 덱과 같다", txt == base, "덱이 다르다")

    print("[R2] '>' (접기) 블록은 카드를 한 줄로 만든다 — 받지 않고 rc=1 로 거절한다")
    for indicator in (">", ">-", ">+", ">2"):
        both_paths(binary, "fold" + indicator.replace(">", "F"), layers_with(indicator),
                   expect_rc=1, want_msg="'>' 블록은")

    # ── 따옴표 스칼라 ────────────────────────────────────────────────────────
    print("[R2] 따옴표 스칼라 — 플랫폼(argbuild)·pyKooCAE 가 내보내는 표기")
    def dq(card):
        return '"' + card.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    def sq(card):
        return "'" + card.replace("'", "''").replace("\n", "\n    ") + "'"   # 작은따옴표는 \n 이스케이프가 없다

    body = ""
    for card in (CARD1, CARD2):
        body += "  - thickness: 1.0\n    material_card: " + dq(card) + "\n"
    both_paths(binary, "dquote", body)

    # 큰따옴표 안의 \t·\\·\" 도 규격대로 풀린다 — 카드 내용은 그대로 남아야 한다
    esc = CARD1.replace("Substrate", 'Sub\\"strate\\\\x')
    body = ("  - thickness: 1.0\n    material_card: " +
            '"' + esc.replace("\n", "\\n") + '"' + "\n" +
            "  - thickness: 1.0\n    material_card: " + dq(CARD2) + "\n")
    d = workdir(binary, "esc")
    open(os.path.join(d, "sa.yaml"), "w").write(standalone_yaml(body))
    rc, out = run(binary, d, "restack", "sa.yaml")
    check("[esc] 이스케이프가 든 따옴표 카드 rc=0", rc == 0, f"rc={rc} {out[-220:]}")
    if rc == 0:
        txt = open(os.path.join(d, "out.k")).read()
        check('[esc] \\" 와 \\\\ 가 글자로 풀린다', 'Sub"strate\\x' in txt, "제목이 다르다")

    print("[R2] PyYAML(yaml.safe_dump)이 '\\' + 줄바꿈으로 접은 따옴표 값도 이어 읽는다")
    try:
        import yaml
    except ImportError:
        print("  (PyYAML 없음 — 이 절은 건너뛴다)")
    else:
        d = workdir(binary, "pyyaml")
        doc = {"model": "box.k", "output": "out", "target_pid": 1, "direction": "z",
               "element_type": "solid",
               "layers": [{"thickness": 1.0, "material_card": CARD1 + "\n"},
                          {"thickness": 1.0, "material_card": CARD2 + "\n"}]}
        dumped = yaml.safe_dump(doc, default_flow_style=False, allow_unicode=False)
        check("[pyyaml] safe_dump 가 값을 여러 줄로 접었다(회귀 전제)",
              '\\\n' in dumped or "\\\n" in dumped, dumped[:200])
        open(os.path.join(d, "sa.yaml"), "w").write(dumped)
        rc, out = run(binary, d, "restack", "sa.yaml")
        check("[pyyaml] 단독 restack rc=0", rc == 0, f"rc={rc} {out[-220:]}")
        if rc == 0:
            parts, mats = parts_and_mats(os.path.join(d, "out.k"))
            lm = [parts.get(2), parts.get(3)]
            check("[pyyaml] 층 PART 의 mid 가 0 이 아니다", all(lm), str(parts))
            check("[pyyaml] 접힌 카드가 줄 단위로 복원됐다",
                  all(m in mats for m in lm if m) and
                  [mats[m][1] for m in lm if m] == ["Substrate", "Cover"],
                  str(mats))

    # ── 카드로 볼 수 없는 값은 rc=1 ─────────────────────────────────────────
    inline_base = base   # '|' 블록 기준 덱 — 빈 줄이 든 카드와 견준다

    print("[R2] 카드로 볼 수 없는 값은 조용히 넘기지 않는다")
    both_paths(binary, "empty", "  - thickness: 1.0\n    material_card:\n",
               expect_rc=1, want_msg="비어 있습니다")
    both_paths(binary, "nokw", "  - thickness: 1.0\n    material_card: Substrate\n",
               expect_rc=1, want_msg="*MAT 키워드 줄이 없습니다")
    both_paths(binary, "nodata", '  - thickness: 1.0\n    material_card: "*MAT_ELASTIC"\n',
               expect_rc=1, want_msg="데이터 줄이 없습니다")
    both_paths(binary, "unterm", '  - thickness: 1.0\n    material_card: "*MAT_ELASTIC\n',
               expect_rc=1, want_msg="따옴표가 닫히지 않았습니다")

    # ── 다른 카드 키(offset)도 같은 규칙 ────────────────────────────────────
    print("[R2] material_card 말고 다른 카드 키(offset)도 같은 규칙으로 읽는다")
    CZM = ("*MAT_COHESIVE_MIXED_MODE\n"
           "$#     mid        ro    roflg    intfail       et       en       gic      giic\n"
           "        80  1.00E-09        0          0    1000.0   1000.0       1.0       1.0")
    for tag, keybody in (
        ("off_card", "material_card: |-\n" + indent_block(CARD1, 2)),
        ("off_cards", "material_cards:\n  - |-\n" + indent_block(CARD1, 6)),
        ("off_quote", "material_card: " + dq(CARD1) + "\n"),
    ):
        d = workdir(binary, tag)
        o = ("model: box.k\noutput: of\nsource_pid: 1\nelement_type: solid\nthickness: 1.0\n"
             "num_layers: 1\noffset_direction: +z\nconnection_mode: tied\nnew_pid: 10\n" + keybody)
        a = ("base_model: box.k\noutput: of\noperations:\n  - type: offset\n    source_pid: 1\n"
             "    element_type: solid\n    thickness: 1.0\n    num_layers: 1\n"
             "    offset_direction: +z\n    connection_mode: tied\n    new_pid: 10\n" +
             "".join(("    " + ln if ln.strip() else "") + "\n" for ln in keybody.rstrip("\n").split("\n")))
        open(os.path.join(d, "sa.yaml"), "w").write(o)
        open(os.path.join(d, "as.yaml"), "w").write(a)
        rc1, out1 = run(binary, d, "offset", "sa.yaml")
        sa_txt = open(os.path.join(d, "of.k")).read() if rc1 == 0 else None
        if os.path.exists(os.path.join(d, "of.k")):
            os.remove(os.path.join(d, "of.k"))
        rc2, out2 = run(binary, d, "assemble", "as.yaml")
        as_txt = open(os.path.join(d, "of.k")).read() if rc2 == 0 else None
        check(f"[{tag}] 단독 offset rc=0", rc1 == 0, f"rc={rc1} {out1[-220:]}")
        check(f"[{tag}] assemble rc=0", rc2 == 0, f"rc={rc2} {out2[-220:]}")
        if rc1 == 0 and rc2 == 0:
            check(f"[{tag}] 두 경로 덱이 완전히 같다", sa_txt == as_txt, "덱이 다르다")
            parts, mats = parts_and_mats(os.path.join(d, "of.k"))
            mid = parts.get(10)
            check(f"[{tag}] 새 PART 의 mid 가 0 이 아니고 *MAT 이 실렸다",
                  bool(mid) and mid in mats and mats[mid][1] == "Substrate", f"{parts} {mats}")

    # offset 의 '>' 와 데이터 줄 없는 카드도 거절
    for tag, keybody, msg in (
        ("off_fold", "material_card: >\n" + indent_block(CARD1, 2), "'>' 블록은"),
        ("off_nodata", 'material_card: "*MAT_ELASTIC"\n', "데이터 줄이 없습니다"),
    ):
        d = workdir(binary, tag)
        o = ("model: box.k\noutput: of\nsource_pid: 1\nelement_type: solid\nthickness: 1.0\n"
             "num_layers: 1\noffset_direction: +z\nconnection_mode: tied\nnew_pid: 10\n" + keybody)
        open(os.path.join(d, "sa.yaml"), "w").write(o)
        rc, out = run(binary, d, "offset", "sa.yaml")
        check(f"[{tag}] 단독 offset rc=1", rc == 1, f"rc={rc} {out[-220:]}")
        check(f"[{tag}] 메시지에 '{msg}'", msg in out, out[-220:])

    # ── R2a: 키워드 줄은 1열에서 시작해야 한다 ──────────────────────────────
    print("[R2a] 카드 키워드 줄에 앞 공백이 있으면 거절한다 ('|N' 지시자·따옴표 값의 앞 공백)")
    # '|1'/'|2' 는 내용을 지시자보다 깊게 써 카드 첫 줄에 앞 공백이 남는 표기다(PyYAML 도 같다)
    for tag, indicator, extra in (("lead1", "|1", 1), ("lead2", "|2", 2)):
        body = ""
        for card in (CARD1, CARD2):
            body += ("  - thickness: 1.0\n    material_card: " + indicator + "\n" +
                     indent_block(card, 4 + extra + 1))
        both_paths(binary, tag, body, expect_rc=1, want_msg="1열에서 시작하지 않습니다")
    both_paths(binary, "lead_quote",
               '  - thickness: 1.0\n    material_card: ' + dq(" " + CARD1) + "\n",
               expect_rc=1, want_msg="1열에서 시작하지 않습니다")

    # ── R2b: '_TITLE' 은 제목 줄과 데이터 줄이 모두 있어야 한다 ──────────────
    print("[R2b] '*MAT_..._TITLE' 에 제목 줄이나 데이터 줄이 빠지면 거절한다")
    TITLE_ONLY = "*MAT_ELASTIC_TITLE\nTitle\n$#     mid        ro         e        pr"
    NO_TITLE = ("*MAT_ELASTIC_TITLE\n"
                "$#     mid        ro         e        pr\n"
                "        90  7.85E-09  2.10E+05       0.3")
    for tag, card in (("title_only", TITLE_ONLY), ("no_title", NO_TITLE)):
        body = "  - thickness: 1.0\n    material_card: |\n" + indent_block(card, 6)
        both_paths(binary, tag, body, expect_rc=1, want_msg="제목 줄 다음에 데이터 줄이")
    # 제목 줄이 없는 '_TITLE' 아닌 카드는 그대로 통과한다(데이터 줄만 있으면 된다)
    PLAIN = ("*MAT_ELASTIC\n"
             "$#     mid        ro         e        pr\n"
             "        90  7.85E-09  2.10E+05       0.3")
    both_paths(binary, "plain_mat",
               "  - thickness: 1.0\n    material_card: |\n" + indent_block(PLAIN, 6) +
               "  - thickness: 1.0\n    material_card: |\n" +
               indent_block(PLAIN.replace("        90", "        91"), 6),
               want_titles=None)

    # ── R2c: 얕은 블록 내용·카드 가운데 빈 줄을 두 경로가 같게 다룬다 ────────
    print("[R2c] 지시자보다 얕은 블록 내용은 두 경로 모두 rc=1 이고 원인을 그대로 말한다")
    for tag, indicator in (("shallow3", "|3"), ("shallow4", "|4")):
        body = ""
        for card in (CARD1, CARD2):
            body += ("  - thickness: 1.0\n    material_card: " + indicator + "\n" +
                     indent_block(card, 6))
        both_paths(binary, tag, body, expect_rc=1, want_msg="블록 내용이")
    # 들쭉날쭉한 들여쓰기(첫 줄이 깊고 다음 줄이 얕다)도 같은 자리에서 걸린다
    jag = ("  - thickness: 1.0\n    material_card: |\n" +
           "        *MAT_ELASTIC_TITLE\n      Substrate\n" +
           "      $#     mid        ro         e        pr\n" +
           "              90  7.85E-09  2.10E+05       0.3\n")
    both_paths(binary, "jagged", jag, expect_rc=1, want_msg="블록 내용이")

    print("[R2c] 카드 '가운데' 빈 줄은 두 경로 모두 버린다 — 남기면 LS-DYNA 가 0 카드로 읽는다")
    gap = ""
    for card in (CARD1, CARD2):
        lines = card.split("\n")
        gapped = "\n".join(lines[:2] + [""] + lines[2:])
        gap += "  - thickness: 1.0\n    material_card: |\n" + indent_block(gapped, 6)
    gap_txt = both_paths(binary, "gapline", gap)
    check("[R2c] 빈 줄이 든 카드 덱이 빈 줄 없는 덱과 같다",
          gap_txt is not None and gap_txt == inline_base, "덱이 다르다")

    # ── R7: '-' 만 있는 줄 ──────────────────────────────────────────────────
    print("[R7] '-' 만 있는 줄로 여는 목록 항목도 정상 YAML 이다")
    dash_layers = ""
    for card in (CARD1, CARD2):
        dash_layers += "  -\n    thickness: 1.0\n    material_card: |\n" + indent_block(card, 6)
    flat = both_paths(binary, "dash_layers", dash_layers)
    inline = both_paths(binary, "dash_inline", layers_with("|"))
    check("[R7] 대시만 있는 층 목록 덱이 '- key:' 형과 같다", flat is not None and flat == inline,
          "덱이 다르다")

    # operations 목록도 같은 문제가 없어야 한다
    d = workdir(binary, "dash_ops")
    ops = ("base_model: box.k\noutput: out\noperations:\n  -\n    type: restack\n"
           "    target_pid: 1\n    direction: z\n    element_type: solid\n    layers:\n" +
           "".join(("    " + ln if ln.strip() else "") + "\n"
                   for ln in layers_with("|").rstrip("\n").split("\n")))
    open(os.path.join(d, "as.yaml"), "w").write(ops)
    rc, out = run(binary, d, "assemble", "as.yaml")
    check("[R7] operations 항목도 '-' 만 있는 줄로 열린다 (rc=0)", rc == 0, f"rc={rc} {out[-220:]}")
    if rc == 0:
        parts, mats = parts_and_mats(os.path.join(d, "out.k"))
        check("[R7] 그 op 이 실제로 실행됐다(층 PART 두 장)",
              parts.get(2) and parts.get(3) and parts[2] != parts[3], str(parts))

    print()
    if FAILS:
        print(f"FAIL {len(FAILS)}")
        for f in FAILS:
            print("  -", f[:300])
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
