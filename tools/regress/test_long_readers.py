#!/usr/bin/env python3
# LONG=Y 덱(모든 칸 20)을 읽고 쓰는 op 들이 표준 덱과 같은 값을 내는지 보는 회귀 시험(미룬 결함 3차 2판)
"""LONG=Y 덱을 읽는 op 여덟 (2026-11-22 · 미룬 결함 3차 2판 L-04 · 사용자 결정 「여덟 다 읽게 고친다」).

왜 이 시험이 있나.

  덱 머리의 `*KEYWORD LONG=Y` 는 20 칸 이하의 모든 칸을 20 칸으로 넓힌다(Vol_I 19315-19316). 11-22 설치된 판(d1e2ce96)에서 제 카드
  리더를 가진 op 여덟이 그 덱을 못 읽었다 — cnrb2solid 는 rc 0 으로 아무것도 바꾸지 않은 덱(솔리드 0)을 썼고, info 는 rc 0 에 거짓
  「정의되지 않은 카드」 오류(--strict 면 rc 1), cnrb2spring · cclip · matswap · ale · stackwrap · neutralaxis 는 엉뚱한 까닭으로 rc 1
  이었다(「CNRB 가 없다」 · 「PID 1 이 없다」 · 「E 를 못 읽었다」). 이제 선언된 폭으로 읽고, 새로 쓰는 카드도 덱의 폭으로 쓴다.

무엇을 보나(도움말 사례 — `*KEYWORD` 를 가진 덱만 LONG 으로 다시 쓴다. 번들 · 조각처럼 머리가 없는 파일은 그대로).
  A. 산출이 있는 여섯 — LONG 사례 rc 0 · 산출 파일 이름이 같다 · 덱마다 선언된 폭으로 읽은 값(블록 차례 · 줄 수 · 수는 상대 1e-3)이 표준
     사례와 같다 · 산출 덱이 `*KEYWORD LONG=Y` 를 싣는다
  B. 화면만 내는 둘(neutralaxis · info) — LONG 사례 rc 0 · 「키: 값」 줄이 표준 사례와 같다(시각 · 걸린 시간은 뺀다) · `[ERROR]` 가 없다
  C. info --strict — LONG 사례 rc 0
  D. 나머지 사례 전부 — 설계된 거절 아홉(REFUSE)은 LONG 사례 rc 가 0 이 아니다. 그 밖은 A 와 같다 — 새로 쓰는 카드 · 곁 파일(dynain ·
     IGA 인클루드)도 덱 폭으로 쓴다(11-22 · 2판 탐침이 찾은 표준 폭 카드 열다섯 op). 산출 가운데 덱 꼴(`.k` · `.dynain` · `*KEYWORD` 로
     시작하는 파일)을 다 견준다. 머리 없는 산출은 LS-DYNA 처럼 주 덱 폭을 물려받는 것으로 읽는다. IGA 인클루드는 낱말(`&이름`)로 견주므로
     LONG 쪽 칸이 20 칸 자리에 섰는지(왼쪽 · 오른쪽 맞춤)를 따로 본다.
  E. 사례에 없는 꼴(변이가 살아남은 자리) — assemble 의 덱 내장 초기응력(`dynain_embed`) + DR 카드 · cclip 의 `stress_output: include`
     dynain · 재질이 표준 폭 인클루드에 있는 IGA(베낀 블록의 키워드에 `-`) · merge 의 세트(목록 · 열 꼴) 옮기기 · matswap 옛 자리 인자 꼴

usage: test_long_readers.py <KooRemapper 바이너리>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import test_deck_bom as T  # noqa: E402 — 도움말 사례를 차리는 판(Case)

FAILS, OKS = [], []
OPS8 = ("cnrb2solid", "cnrb2spring", "cclip", "matswap", "ale", "stackwrap", "neutralaxis", "info")
SCREEN_ONLY = ("neutralaxis", "info")
TOKEN_KW = ("*ELEMENT_", "*SET_")
# LONG=Y 덱을 「20 칸 서식을 확정하지 못했다」 로 거절하는 op 일곱 · 계약상 표준 폭 조각을 받는 둘(조각 폭 · 계획 sha)
REFUSE = ("convert", "refine", "disconnect", "offset", "restack", "meshfix", "rbe", "cad_solid_merge_to_deck", "apply_carryover_plan")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-700:]))
    print("  %-104s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def is_title_row(kw, nline):
    return (kw == "*TITLE") or (kw.startswith("*PART") and nline % 2 == 1) or (kw.endswith("_TITLE") and nline == 1)


def chunks(line, w):
    return [line[i:i + w] for i in range(0, len(line.rstrip()), w)]


def to_long(text):
    """표준 덱을 LONG=Y 로 — 칸마다 20 칸 오른쪽 맞춤. 절점 (I8,3F16,2I8) → (I20,3F20,2I20) · 요소 · 세트 줄은 낱말 · 곡선 점 줄(20 칸
    두 개)은 그대로 · 제목 · 인클루드 이름 · 주석은 그대로."""
    out, kw, nline = [], "", 0
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if line.startswith("*"):
            kw, nline = line.split()[0].upper(), 0
            out.append("*KEYWORD LONG=Y" if kw == "*KEYWORD" else line)
            continue
        if line.startswith("$") or not line.strip() or kw.startswith("*INCLUDE"):
            out.append(line)
            continue
        nline += 1
        if is_title_row(kw, nline):
            out.append(line.strip())
            continue
        if kw.startswith("*NODE"):
            cells = [line[0:8], line[8:24], line[24:40], line[40:56]] + chunks(line[56:], 8)
            if len(line.rstrip()) < 56 or any(c.strip() and num(c.strip()) is None for c in cells) or not cells[0].strip():
                cells = line.split()                  # 칸이 어긋난 줄(예제 덱) — 낱말로
        elif kw.startswith(TOKEN_KW):
            cells = line.split()
        elif kw.startswith("*DEFINE_CURVE") and nline > (2 if kw.endswith("_TITLE") else 1):
            out.append(line)                          # 점 줄은 표준에서도 20 칸이다
            continue
        else:
            cells = chunks(line, 10)
            if any(c.strip() and " " in c.strip() for c in cells):
                cells = line.split()                  # 칸이 어긋난 자유형식 줄
        out.append("".join(c.strip().rjust(20) for c in cells).rstrip())
    return "\n".join(out)


def deck_width(text):
    for l in text.split("\n"):
        if l[:1] == "*" and l.split()[0].upper() in ("*KEYWORD", "*KEYWORD_ID", "*KEYWORD_JOBID"):
            up = l.upper().replace(" =", "=").replace("= ", "=")
            toks = up.split()[1:]
            if any(t in ("LONG", "LONG=Y", "LONG=K") for t in toks):
                return 20
            if any(t.startswith("I10") and t not in ("I10=N",) for t in toks):
                return 10
            return 8
    return 8


def num(s):
    try:
        return float(s.replace("D", "E").replace("d", "e"))
    except ValueError:
        return None


def values(text, strict=False, inherit=8):
    """덱을 선언된 폭으로 읽은 값 — [(키워드, [줄 값들])]. 줄 값은 수(float) 또는 글. strict 면 칸이 수가 아닐 때 낱말로
    되돌리지 않고 글 줄로 둔다(LONG 덱에 섞인 10 칸 카드를 드러낸다). `*KEYWORD` 가 없는 파일은 inherit 폭(물려받는 주 덱 폭)으로 읽는다.
    `*IGA_` · `*PARAMETER` 카드는 칸 폭이 섞이고(20 칸 칸 · `&이름`) 낱말로 견준다."""
    fw = deck_width(text) if any(l[:8].upper() == "*KEYWORD" for l in text.split("\n")) else inherit
    res, kw, nline = [], None, 0
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if line.startswith("*"):
            tok = line.split()[0].upper()
            suf = tok[-1] if tok[-1] in "%+-" else ""
            name = tok.rstrip("%+-")
            if name in ("*KEYWORD", "*KEYWORD_ID", "*KEYWORD_JOBID", "*END"):
                kw = None
                continue
            w = {"+": 20, "-": 8, "%": 10}.get(suf, fw)
            kw, nline = (name, w), 0
            res.append((name, []))
            continue
        if kw is None or line.startswith("$") or not line.strip():
            continue
        name, w = kw
        nline += 1
        if is_title_row(name, nline):
            res[-1][1].append(("T", " ".join(line.split())))
            continue
        if name.startswith(("*IGA_", "*PARAMETER")):
            res[-1][1].append(("T", " ".join(line.split())))
            continue
        rw = 20 if w == 20 else 16
        cw = 20 if w == 20 else 10
        if name.startswith("*NODE"):
            cells = [line[0:w], line[w:w + rw], line[w + rw:w + 2 * rw], line[w + 2 * rw:w + 3 * rw]] + chunks(line[w + 3 * rw:], w)
        elif name.startswith("*ELEMENT_"):
            cells = chunks(line, w)
        elif name.startswith("*DEFINE_CURVE") and nline > (2 if name.endswith("_TITLE") else 1):
            cells = chunks(line, 20)
        else:
            cells = chunks(line, cw)
        toks = line.split()
        filled = [c.strip() for c in cells if c.strip()]
        glued = len(toks) < len(filled) and all(" " not in c and num(c) is not None for c in filled)   # 붙어 쓴 고정 칸
        if not strict and not glued and len(toks) >= 2 and all(num(x) is not None for x in toks) and (name.startswith(("*ELEMENT_", "*SET_"))):
            vals = [num(x) for x in toks]          # 표준 쪽(참값) 요소 · 세트 줄은 낱말로 — 예제 덱은 칸이 8 이 아닐 수 있다
            while vals and vals[-1] == 0.0:
                vals.pop()
            res[-1][1].append(tuple(vals))
            continue
        vals = [num(c.strip()) if c.strip() else 0.0 for c in cells]
        if any(v is None for v in vals) and strict:
            res[-1][1].append(("T", " ".join(line.split())))
            continue
        if any(v is None for v in vals):
            toks = line.split()
            vals = [num(t) for t in toks]
            if any(v is None for v in vals):
                res[-1][1].append(("T", " ".join(line.split())))
                continue
        while vals and vals[-1] == 0.0:
            vals.pop()                                 # 끝의 빈 칸 · 0 은 같다(기본값)
        res[-1][1].append(tuple(vals))
    return res


def same_values(a, b):
    if [k for k, _ in a] != [k for k, _ in b]:
        return "블록 차례가 다르다 %s / %s" % ([k for k, _ in a][:12], [k for k, _ in b][:12])
    for (k, ra), (_, rb) in zip(a, b):
        if len(ra) != len(rb):
            return "%s 줄 수 %d / %d" % (k, len(ra), len(rb))
        for x, y in zip(ra, rb):
            if x == y:
                continue
            if isinstance(x, tuple) and x and x[0] == "T" or isinstance(y, tuple) and y and y[0] == "T":
                if x != y:
                    return "%s 글 줄 %r / %r" % (k, x, y)
                continue
            if len(x) != len(y) or any(not (abs(p - q) <= 1e-9 or abs(p - q) <= 1e-3 * max(abs(p), abs(q))) for p, q in zip(x, y)):
                return "%s 줄 %r / %r" % (k, x[:8], y[:8])
    return None


CLOCK = re.compile(r"\d+(\.\d+)?\s*(ms|s|초)\b|\d{4}[-/]\d{2}[-/]\d{2}|\d{2}:\d{2}:\d{2}")


def kv_lines(text):
    out = []
    for l in text.splitlines():
        if ":" not in l or "time" in l.lower() or "시간" in l:
            continue
        k, _, v = l.partition(":")
        if not k.strip() or len(k) > 60:
            continue
        out.append((k.strip(), CLOCK.sub("<T>", v.strip())))
    return out


def deck_like(rel, data):
    return rel.endswith((".k", ".dynain")) or data.lstrip()[:8].upper() == b"*KEYWORD"


def misaligned20(text):
    """LONG 산출의 `*IGA_*` · `*PARAMETER*` · `*PART` · `*SECTION_IGA*` 데이터 줄에서 20 칸 자리에 서지 않은 낱말이 있는 줄 — 낱말은 20 의
    배수 자리에서 시작하거나(왼쪽 맞춤) 20 의 배수 자리에서 끝난다(오른쪽 맞춤)."""
    bad, kw, nline = [], "", 0
    for line in text.split("\n"):
        if line.startswith("*"):
            kw, nline = line.split()[0].upper(), 0
            continue
        if not line.strip() or line.startswith("$"):
            continue
        nline += 1
        if not kw.startswith(("*IGA_", "*PARAMETER", "*PART", "*SECTION_IGA")) or is_title_row(kw, nline):
            continue
        for m in re.finditer(r"\S+", line.rstrip()):
            if m.start() % 20 and m.end() % 20:
                bad.append(line)
                break
    return bad


def compare(sec, name, rs, os_, rl, tl, ol):
    check(f"{sec} {name} — LONG rc 0 · 산출 이름이 같다", rs == 0 and rl == 0 and sorted(ol) == sorted(os_),
          (rs, rl, sorted(ol), sorted(os_), tl[-400:]))
    for rel in sorted(os_):
        if rel not in ol or not deck_like(rel, os_[rel]):
            continue
        a, b = os_[rel].decode("utf-8", "replace"), ol[rel].decode("utf-8", "replace")
        why = same_values(values(a), values(b, strict=True, inherit=20))
        check(f"{sec} {name} — {rel} 값이 표준과 같다", why is None, why)
        if any(l[:8].upper() == "*KEYWORD" for l in b.split("\n")):
            check(f"{sec} {name} — {rel} 가 LONG=Y 를 싣는다", deck_width(b) == 20, b[:200])
        if "*IGA_" in b.upper():
            bad = misaligned20(b)
            check(f"{sec} {name} — {rel} 의 IGA 칸이 20 칸 자리에 선다", not bad, bad[:2])


def stage(binary, top, name, mode):
    spec = {o["name"]: o for o in T.OPS}[name]
    case = T.Case(binary, os.path.join(top, f"{name}_{mode}"), spec)
    if mode == "long":
        for rel in case.decks:
            p = os.path.join(case.base, rel)
            with open(p, encoding="utf-8", errors="replace", newline="") as f:
                text = f.read()
            if not any(l[:8].upper() == "*KEYWORD" for l in text.split("\n")):
                continue                              # 머리 없는 번들 · 조각은 그대로
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(to_long(text))
    return case


def pair(binary, top, name, prepare, cmd, longify):
    """표준 · LONG 두 폴더를 같은 준비로 차려(prepare(d)) longify 의 덱만 LONG 으로 다시 쓰고 cmd 를 돌린다 → 둘의 (rc, 화면, 새 파일)."""
    res = []
    for mode in ("std", "long"):
        d = os.path.join(top, "E_%s_%s" % (name, mode))
        os.makedirs(d)
        prepare(d)
        if mode == "long":
            for rel in longify:
                p = os.path.join(d, rel)
                with open(p, encoding="utf-8") as f:
                    t = f.read()
                with open(p, "w", encoding="utf-8") as f:
                    f.write(to_long(t))
        before = set(os.listdir(d))
        p = subprocess.run([binary] + cmd, cwd=d, capture_output=True, timeout=900)
        outs = {}
        for fn in sorted(set(os.listdir(d)) - before):
            with open(os.path.join(d, fn), "rb") as f:
                outs[fn] = f.read()
        res.append((p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace"), outs))
    return res


def extra_cases(binary, top):
    spec = {o["name"]: o for o in T.OPS}

    def gen(d, yaml_name, yaml_text):
        with open(os.path.join(d, yaml_name), "w", encoding="utf-8") as f:
            f.write(yaml_text)
        subprocess.run([binary, "generate", "box", yaml_name], cwd=d, capture_output=True, timeout=300)

    # E-1 assemble 의 덱 내장 초기응력 + DR 카드(formstrain — 셸 결과)
    def p1(d):
        shutil.copy2(os.path.join(REPO, "examples", "formstrain", "bent_shell.k"), d)
        with open(os.path.join(d, "a.yaml"), "w", encoding="utf-8") as f:
            f.write("base_model: bent_shell.k\noutput: fse\ndynain_embed: true\ndynamic_relaxation: true\noperations:\n"
                    "  - type: formstrain\n")
    (rs, ts, os_), (rl, tl, ol) = pair(binary, top, "embed_dr", p1, ["assemble", "a.yaml"], ["bent_shell.k"])
    compare("E", "assemble dynain_embed · DR", rs, os_, rl, tl, ol)
    check("E assemble dynain_embed · DR — 산출에 *INITIAL_STRESS_SHELL · *CONTROL_DYNAMIC_RELAXATION 이 있다",
          b"*INITIAL_STRESS_SHELL" in ol.get("fse.k", b"") and b"*CONTROL_DYNAMIC_RELAXATION" in ol.get("fse.k", b""), sorted(ol))

    # E-2 cclip 의 stress_output: include — 곁 dynain
    cc = spec["cclip"]["files"]
    def p2(d):
        gen(d, "board.yaml", cc["board.yaml"])
        with open(os.path.join(d, "cclip.yaml"), "w", encoding="utf-8") as f:
            f.write(cc["cclip.yaml"].replace("stress_output: embed", "stress_output: include"))
    (rs, ts, os_), (rl, tl, ol) = pair(binary, top, "cclip_inc", p2, ["cclip", "cclip.yaml"], ["clip_board.k"])
    compare("E", "cclip stress_output: include", rs, os_, rl, tl, ol)
    check("E cclip stress_output: include — 곁 dynain 이 있다", any(k.endswith(".dynain") for k in ol), sorted(ol))

    # E-3 재질이 표준 폭 인클루드에 있는 IGA — 베낀 재질 블록이 그 폭으로 읽힌다(키워드에 `-`)
    ig = spec["iga"]["files"]
    def p3(d):
        gen(d, "box.yaml", ig["box.yaml"])
        p = os.path.join(d, "box.k")
        with open(p, encoding="utf-8") as f:
            t = f.read()
        a, b = t.index("*MAT_ELASTIC"), t.index("*SECTION_SOLID")
        with open(os.path.join(d, "mat.k"), "w", encoding="utf-8") as f:
            f.write("*KEYWORD\n" + t[a:b] + "*END\n")
        with open(p, "w", encoding="utf-8") as f:
            f.write(t[:a] + t[b:].replace("*END", "*INCLUDE\nmat.k\n*END"))
        with open(os.path.join(d, "iga.yaml"), "w", encoding="utf-8") as f:
            f.write(ig["iga.yaml"])
    (rs, ts, os_), (rl, tl, ol) = pair(binary, top, "iga_inc", p3, ["iga", "iga.yaml"], ["box.k"])
    compare("E", "iga 재질이 표준 인클루드에", rs, os_, rl, tl, ol)
    igaf = [k for k in ol if "_iga_p" in k]
    check("E iga 재질이 표준 인클루드에 — IGA 파일의 베낀 재질 키워드가 `-` 로 끝난다",
          igaf and any(l.strip().upper().startswith("*MAT_") and l.strip().endswith("-")
                       for l in ol[igaf[0]].decode("utf-8", "replace").split("\n")), igaf)

    # E-4b merge 의 죽은 PID 옮기기 — 세트(목록 · 열 꼴)가 합친 파트를 가리킨다
    def p4b(d):
        shutil.copytree(os.path.join(REPO, "examples", "merge"), os.path.join(d, "examples", "merge"))
        with open(os.path.join(d, "merge.yaml"), "w", encoding="utf-8") as f:
            f.write(spec["merge"]["files"]["merge.yaml"])
        p = os.path.join(d, "examples", "merge", "three_layer.k")
        with open(p, encoding="utf-8") as f:
            t = f.read()
        sets = ("*SET_PART_LIST\n%10d\n%10d%10d%10d\n" % (701, 1, 2, 3) +
                "*SET_PART_LIST_COLUMN\n%10d\n%10d%10.1f\n%10d%10.1f\n" % (702, 1, 1.0, 3, 2.0))
        with open(p, "w", encoding="utf-8") as f:
            f.write(t.replace("*END", sets + "*END", 1))
    (rs, ts, os_), (rl, tl, ol) = pair(binary, top, "merge_sets", p4b, ["merge", "merge.yaml"],
                                       [os.path.join("examples", "merge", "three_layer.k")])
    compare("E", "merge 세트 옮기기", rs, os_, rl, tl, ol)
    check("E merge 세트 옮기기 — 표준 쪽이 세트를 옮겼다(시험이 그 길을 탄다)", "SET_PART_LIST_COLUMN" in ts and "moved" in ts,
          ts[-400:])

    # E-4 matswap 옛 자리 인자 꼴
    def p4(d):
        shutil.copytree(os.path.join(REPO, "examples", "matswap"), os.path.join(d, "examples", "matswap"))
    (rs, ts, os_), (rl, tl, ol) = pair(binary, top, "matswap_old", p4,
                                       ["matswap", "examples/matswap/two_cubes.k", "examples/matswap/rubber.k", "1", "out.k"],
                                       [os.path.join("examples", "matswap", "two_cubes.k")])
    compare("E", "matswap 옛 자리 인자 꼴", rs, os_, rl, tl, ol)


def main():
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_longread_")
    try:
        for name in OPS8:
            std, lng = stage(binary, top, name, "std"), stage(binary, top, name, "long")
            rs, ts, os_ = std.go()
            rl, tl, ol = lng.go()
            if name in SCREEN_ONLY:
                print(f"[B — {name}]")
                check(f"B {name} — LONG rc 0 · [ERROR] 없음", rl == 0 and "[ERROR]" not in tl, (rl, tl[-400:]))
                diff = [x for x in kv_lines(ts) if x not in kv_lines(tl)]
                check(f"B {name} — 「키: 값」 줄이 표준과 같다", rs == 0 and not diff, (diff[:5], tl[-300:]))
                continue
            print(f"[A — {name}]")
            compare("A", name, rs, os_, rl, tl, ol)
        print("[C — info --strict]")
        lng = stage(binary, top, "info", "long2")
        p = subprocess.run([binary, "info", "--strict", lng.decks[0]], cwd=lng.base, capture_output=True, timeout=300)
        if os.path.exists(os.path.join(lng.base, lng.decks[0])):
            with open(os.path.join(lng.base, lng.decks[0]), encoding="utf-8") as f:
                t = f.read()
            with open(os.path.join(lng.base, lng.decks[0]), "w", encoding="utf-8") as f:
                f.write(to_long(t))
            p = subprocess.run([binary, "info", "--strict", lng.decks[0]], cwd=lng.base, capture_output=True, timeout=300)
        check("C info --strict — LONG rc 0", p.returncode == 0, (p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")[-400:]))
        print("[D — 나머지 사례]")
        for spec in T.OPS:
            name = spec["name"]
            if name in OPS8:
                continue
            std, lng = stage(binary, top, name, "std"), stage(binary, top, name, "long")
            if not std.cmd or not std.decks:
                continue
            rs, ts, os_ = std.go()
            rl, tl, ol = lng.go()
            if name in REFUSE:
                check(f"D {name} — LONG 은 설계된 거절(rc ≠ 0)", rs == 0 and rl != 0, (rs, rl, tl[-300:]))
            else:
                compare("D", name, rs, os_, rl, tl, ol)
            shutil.rmtree(std.base, ignore_errors=True)
            shutil.rmtree(lng.base, ignore_errors=True)
        print("[E — 사례에 없는 꼴]")
        extra_cases(binary, top)
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
