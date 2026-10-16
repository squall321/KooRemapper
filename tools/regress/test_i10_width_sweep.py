#!/usr/bin/env python3
"""i10 폭 훑기 — 42 op 의 산출 덱이 **LS-DYNA 가 읽을 폭**과 맞는가(표준 판 · i10 판).

왜 이 시험이 있나 (2026-10-16, plan2 P1-1 「픽스처 `I10=Y` 를 42 op 전수 축으로」).

  i10 덱에 8칸 카드를 끼우는 결함이 여러 번 났다(`cnrb2solid`·`cnrb2spring` — `290b740`). 그런데 우리
  `info` 는 공백 토큰을 **먼저** 보는 관대한 리더라 8칸 줄도 값을 옳게 읽는다. LS-DYNA 는 선언된 폭의
  **고정 창**으로 읽는다 — `      19       2      57      61` 을 10칸으로 읽으면 넷째 칸이 `61      62` 다.
  그래서 아무 관문도 안 물었다. 이 시험은 LS-DYNA 처럼 읽는다.

어떻게.
  · 각 op 의 예제를 두 판으로 돌린다 — 표준 그대로 · 입력 덱을 i10 으로 넓혀서(아래 변환기).
  · 산출 덱마다 **실효 폭**을 정한다 — 주 덱 첫 `*KEYWORD` 의 I10/LONG(Vol_I 18086 — 그 카드만 효력),
    인클루드된 파일은 **포함하는 덱의 폭**(그 파일의 `*KEYWORD` 는 효력이 없다), `*INCLUDE -`/`+` 는 그 파일
    전체를 표준/long 으로(19350), 키워드 끝 `%`/`+`/`-` 는 그 키워드만(19342-19360).
  · I10 이 **넓히는** 카드만 본다 — 표준에서 8칸 정수 칸인 `*NODE` 와 `*ELEMENT_SOLID/SHELL/TSHELL/BEAM`
    (19353 "extending 8-character input fields where they exist"). `*INITIAL_STRESS_*` 첫 카드처럼 원래
    10칸(80열 표준 카드)인 것은 I10 과 무관하다.
  · 줄마다 — 실효 폭 창으로 읽어 숫자가 되고, **모든 글자 덩어리의 끝이 칸 경계**에 온다. 숫자가 되는지만
    보면 모자란다 — `%8d%16.6f` 노드 줄은 10칸으로 읽어도 좌표 앞 공백이 넉넉하면 **우연히** 읽힌다.
    꽉 찬 칸끼리 붙은 줄(`9000000190000002`)도 끝은 경계라 거짓 경보가 없다.
  · 입력에 **그대로 있던 줄**은 뺀다 — op 이 쓴 줄만 본다(예제에는 칸을 안 맞춘 손글씨 덱이 있다).

이 시험이 처음 잡은 것 — `merge`(새 `*ELEMENT_SOLID` 4줄)·`cclip`(새 노드·셸 88줄)이 i10 덱에 8칸으로 썼다.
처음 판의 검사기는 `*INITIAL_STRESS_SOLID` 첫 카드를 8칸으로 **가정**해 `.dynain` 5건을 거짓으로 물었다 —
매뉴얼로 확인하고 뺐다. 그 카드는 원래 10칸이다.

usage: test_i10_width_sweep.py <KooRemapper 바이너리>
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
CORE = os.path.join(REPO, "platform", "core")

# ⚠ 픽스처 표(FIXTURES/PREP/EXCLUDE)와 스테이징은 **매트릭스에서 빌려 쓴다**(베끼면 갈린다).
_spec = importlib.util.spec_from_file_location("nlm", os.path.join(HERE, "test_newline_matrix.py"))
_nlm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_nlm)

# ── 변환기 — 8칸 정수 칸을 10칸으로 ──────────────────────────────────────────
# 리더(`KFileReader`)와 같은 차례로 읽는다. 공백 토큰이 숫자 개수에 맞고 붙은 숫자가 없으면 토큰으로,
# 아니면 고정폭으로. 좌표 **글자는 그대로** 16칸에 맞춰 놓는다(값을 다시 찍으면 op 결과가 달라져 거짓
# 실패가 난다). `*KEYWORD` 가 없으면 맨 앞에 `*KEYWORD I10=Y` 를 넣는다 — 선언이 없으면 10칸 줄을 8칸으로 읽는다.
ELEM_OK = {"*ELEMENT_SOLID", "*ELEMENT_SHELL", "*ELEMENT_TSHELL"}
_GLUED = re.compile(r"\d[eE][+-]?\d+[+-]\d|\d[+-]\d")   # 1.0e+01-2.0 · 1.0-2.0 처럼 숫자가 붙은 것


def _kw(line):
    s = line.lstrip()
    return s.split()[0].upper() if s.startswith("*") else None


def _num(tok):
    try:
        float(tok); return True
    except ValueError:
        return False


def _node(line):
    toks = line.split()
    if "," not in line and 4 <= len(toks) <= 6 and all(_num(t) for t in toks) and \
            not any(_GLUED.search(t) for t in toks[1:4]) and all(len(t) <= 16 for t in toks[1:4]):
        nid = int(toks[0]); xyz = toks[1:4]
        tc = int(float(toks[4])) if len(toks) > 4 else None
        rc = int(float(toks[5])) if len(toks) > 5 else None
    else:
        if "," in line or len(line.rstrip()) < 56:
            return None
        try:
            nid = int(line[0:8]); xyz = [line[8:24].strip(), line[24:40].strip(), line[40:56].strip()]
            r = line[56:]
            tc = int(r[0:8]) if r[0:8].strip() else None
            rc = int(r[8:16]) if r[8:16].strip() else None
        except ValueError:
            return None
    s = "%10d%16s%16s%16s" % (nid, xyz[0], xyz[1], xyz[2])
    if tc is not None or rc is not None:
        s += "%10d%10d" % (tc or 0, rc or 0)
    return s


def _ints(line):
    toks = line.split()
    if "," not in line and toks and all(re.fullmatch(r"[+-]?\d+", t) for t in toks):
        return [int(t) for t in toks]
    body = line.rstrip()
    if "," in body or not body:
        return None
    out = []
    for k in range(0, len(body), 8):
        f = body[k:k + 8]
        try:
            out.append(int(f))
        except ValueError:
            return None
    return out


def declares_i10(text):
    for line in text.splitlines():
        if _kw(line) == "*KEYWORD":
            return "I10" in line.upper() and "I10=N" not in line.upper().replace(" ", "")
    return False


def to_i10(text):
    """(변환한 글, 모르는 꼴 집합). 각 줄의 개행(CRLF/LF)과 말미 개행은 원본 그대로다."""
    if declares_i10(text):
        return text, {"이미 i10"}
    lines = text.split("\n")
    out, unknown, kw = [], set(), None
    saw_kw = False
    for raw in lines:
        cr = raw.endswith("\r")
        line = raw[:-1] if cr else raw
        tail = "\r" if cr else ""
        k = _kw(line)
        if k is not None:
            kw = k
            if k == "*KEYWORD":
                saw_kw = True
                if "I10" not in line.upper():
                    line = line.rstrip() + " I10=Y"
            out.append(line + tail)
            continue
        s = line.lstrip()
        if not s or s.startswith("$") or kw is None:
            out.append(raw); continue
        if kw.rstrip("%+-") == "*NODE":
            n = _node(line)
            if n is None:
                unknown.add("*NODE"); out.append(raw)
            else:
                out.append(n + tail)
            continue
        if kw.startswith("*ELEMENT"):
            base = kw.rstrip("%+-")
            f = _ints(line) if base in ELEM_OK else None
            if f is None:
                unknown.add(base); out.append(raw)
            else:
                out.append("".join("%10d" % v for v in f) + tail)
            continue
        out.append(raw)
    if not saw_kw:
        nl = "\r\n" if text.count("\r\n") * 2 > text.count("\n") else "\n"
        return "*KEYWORD I10=Y" + nl + "\n".join(out), unknown
    return "\n".join(out), unknown


# ── 폭 검사기 ── LS-DYNA 가 읽는 그대로 ──────────────────────────────────────

# I10 이 **넓히는** 카드만 본다 — 표준에서 8칸 정수 칸을 가진 것(Vol_I 19353 "extending 8-character input
# fields where they exist"). `*INITIAL_STRESS_*` 첫 카드처럼 원래 10칸(80열 표준 카드)인 것은 I10 과 무관하다.
INT_KW = {"*ELEMENT_SOLID": None, "*ELEMENT_SHELL": None, "*ELEMENT_TSHELL": None, "*ELEMENT_BEAM": None}


def deck_width(lines):
    for l in lines:
        s = l.lstrip()
        if not s.startswith("*"):
            continue
        u = s.upper().replace(" ", "")
        if u.startswith("*KEYWORD"):
            if re.search(r"LONG=(Y|K)", u): return 20
            if "I10=Y" in u or re.search(r"I10(?!=N)", u): return 10
            return 8
    return 8


def kw_width(kwline, base):
    t = kwline.strip().upper()
    if t.endswith("%"): return 10
    if t.endswith("+"): return 20
    if t.endswith("-") or t.endswith(" -"): return 8
    return base


def _aligned(line, w, first=0, step=None):
    """오른쪽 맞춤 고정폭 줄인가 — 모든 글자 덩어리의 **끝**이 칸 경계에 온다.
    꽉 찬 칸끼리 붙은 덩어리(`9000000190000002`)도 끝은 경계다 — 공백 토큰으로 비교하면 거짓 경보가 난다."""
    step = step or w
    body = line.rstrip()
    i = 0
    while i < len(body):
        if body[i] == " ":
            i += 1; continue
        j = i
        while j < len(body) and body[j] != " ":
            j += 1
        if (j - first) % step != 0 or j < first:
            return False
        i = j
    return True


def _fixed_ints(line, w):
    body = line.rstrip()
    out = []
    for k in range(0, len(body), w):
        f = body[k:k + w]
        if not f.strip():
            out.append(None); continue
        try:
            out.append(int(f))
        except ValueError:
            return None
    return out


def _node_ok(l, w):
    """LS-DYNA 가 읽는 그대로 — 실효 폭 창의 nid 와 좌표 셋(16칸)이 숫자가 되고, **덩어리 끝이 칸 경계**에 온다.
    ⚠ 숫자가 되는지만 보면 모자란다. `%8d%16.6f` 줄을 10칸으로 읽어도 좌표 앞 공백이 넉넉하면 값이 창 안에
    들어가 **우연히** 읽힌다(16칸을 꽉 채우는 좌표면 깨진다). 끝 경계로 보면 우연에 기대지 않는다."""
    try:
        int(l[0:w])
        for k in range(3):
            f = l[w + 16 * k: w + 16 * (k + 1)]
            if f.strip(): float(f)
    except ValueError:
        return False
    ends = {w, w + 16, w + 32, w + 48, w + 48 + w, w + 48 + 2 * w}
    body = l.rstrip(); i = 0
    while i < len(body):
        if body[i] == " ":
            i += 1; continue
        j = i
        while j < len(body) and body[j] != " ":
            j += 1
        if j not in ends:
            return False
        i = j
    return True


def check_lines(lines, width, label, skip=frozenset()):
    """(검사한 줄 수, 틀린 줄 [(줄번호, 키워드, 줄)]). `skip` 은 입력에 그대로 있던 줄 — op 이 쓴 것이 아니다."""
    kw, base_kw, w, bad, n, card = None, None, width, [], 0, 0
    for i, l in enumerate(lines, 1):
        s = l.lstrip()
        if s.startswith("*"):
            kw = s.split()[0].upper()
            base_kw = kw.rstrip("%+-")
            w = kw_width(s, width)
            card = 0
            continue
        if not s.strip() or s.startswith("$") or base_kw is None:
            continue
        if "," in l:
            continue                          # 자유형식은 폭과 무관하다
        if l.rstrip() in skip:
            continue
        if base_kw in ("*NODE",):
            n += 1
            if not _node_ok(l, w):
                bad.append((i, kw, l.rstrip()[:90]))
            continue
        if base_kw in INT_KW:
            only_first = INT_KW[base_kw]
            card += 1
            if only_first and card != 1:
                # 응력 카드는 정수 첫 줄 + 실수 줄들 — 실수 줄이 끝나고 다음 요소의 첫 줄이 오면 card 를 되돌린다
                if re.fullmatch(r"\s*[+-]?\d+(\s+[+-]?\d+)*\s*", l):
                    card = 1
                else:
                    continue
            if not re.fullmatch(r"\s*[+-]?\d+(\s+[+-]?\d+)*\s*", l):
                continue                      # 정수만의 줄이 아니면(두께·각 카드) 이 검사의 대상이 아니다
            n += 1
            if _fixed_ints(l, w) is None or not _aligned(l, w):
                bad.append((i, kw, l.rstrip()[:90]))
    return n, bad


# ── 훑기 ─────────────────────────────────────────────────────────────────────

FAILS, OKS, SKIPS = [], [], []


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail)[:300]))
    return cond


def decks(d):
    for root, _, files in os.walk(d):
        for fn in files:
            if fn.endswith(_nlm.DECK_EXT):
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, d)
                if not rel.startswith("materials" + os.sep):    # 번들 재질 조각 — 노드·요소가 없다
                    yield rel, p


def include_map(d):
    """포함되는 파일 → (포함하는 파일, 접미사 폭 또는 None)."""
    m = {}
    for rel, p in decks(d):
        L = open(p, encoding="utf-8", errors="replace").read().splitlines()
        for i, l in enumerate(L):
            u = l.strip().upper()
            if not u.startswith("*INCLUDE") or u.startswith("*INCLUDE_"):
                continue
            suf = 8 if u.rstrip().endswith("-") else (20 if u.rstrip().endswith("+") else None)
            for j in range(i + 1, len(L)):
                t = L[j].strip()
                if t.startswith("*"):
                    break
                if not t or t.startswith("$"):
                    continue
                m[os.path.normpath(os.path.join(os.path.dirname(rel), t.split()[0]))] = (rel, suf)
    return m


def eff_width(rel, d, imap, seen=()):
    if rel in imap and rel not in seen:
        parent, suf = imap[rel]
        return suf if suf else eff_width(parent, d, imap, seen + (rel,))
    return deck_width(open(os.path.join(d, rel), encoding="utf-8", errors="replace").read().splitlines())


def run_variant(binary, o, folder, args, env, build_command, convert):
    d = tempfile.mkdtemp(prefix="i10w_")
    try:
        why = _nlm.stage(o["name"], folder, d)
        if why:
            return None, "stage: " + why
        # ⚠ 사전 단계가 입력 덱을 **만드는** op 이 있다(cclip — `generate box`). 변환은 그 **뒤에**.
        if o["name"] in _nlm.PREP:
            argv, _w = _nlm.PREP[o["name"]]
            if _nlm.run_op(binary, d, argv, env)[0] != 0:
                return None, "사전 단계 실패"
        unknown = set()
        if convert:
            for rel, p in list(decks(d)):
                t = open(p, encoding="utf-8", errors="surrogateescape", newline="").read()
                t2, u = to_i10(t)
                unknown |= (u - {"이미 i10"})
                open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(t2)
        base, inlines = {}, set()
        for rel, p in decks(d):
            base[rel] = hashlib.sha256(open(p, "rb").read()).hexdigest()
            os.utime(p, (_nlm.BASE_T, _nlm.BASE_T))
            inlines |= {x.rstrip() for x in open(p, encoding="utf-8", errors="replace").read().splitlines()}
        built = build_command(o["name"], args, Path(d))
        if getattr(built, "error", None):
            return None, "인자 조립 실패"
        rc, out = _nlm.run_op(binary, d, built.argv, env)
        imap = include_map(d)
        res = []
        for rel, p in decks(d):
            if rel in base and base[rel] == hashlib.sha256(open(p, "rb").read()).hexdigest() and \
                    int(os.stat(p).st_mtime) == _nlm.BASE_T:
                continue                                         # 안 건드린 입력
            w = eff_width(rel, d, imap)
            n, bad = check_lines(open(p, encoding="utf-8", errors="replace").read().splitlines(), w, rel,
                                 frozenset(inlines))
            res.append((rel, w, n, bad))
        return {"rc": rc, "res": res, "unknown": unknown}, None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    sys.path.insert(0, CORE)
    try:
        from kooremapper_core.argbuild import build_command
    except Exception as exc:                                     # noqa: BLE001
        print("argbuild 를 못 불러왔다(파이썬 계층 필요): %s" % exc)
        return 2
    env = dict(os.environ)
    g = _nlm.gmsh_path()
    if g:
        env["KOOREMAPPER_GMSH"] = g
    ops = json.load(open(_nlm.CATALOG, encoding="utf-8"))["operations"]
    todo = [o for o in ops if o["name"] not in _nlm.EXCLUDE]
    print("[i10 폭 훑기] %d op × (표준 · i10)" % len(todo))
    lines_checked = 0
    for o in todo:
        name = o["name"]
        folder = o.get("example_folder")
        folder = folder if (folder and os.path.isabs(folder)) else (os.path.join(REPO, folder) if folder else None)
        args = (o.get("example") or {}).get("args")
        if not folder or not os.path.isdir(folder) or not isinstance(args, dict):
            check("%s 예제가 있다" % name, False, "카탈로그를 고쳐야 한다")
            continue
        if o.get("requires_gmsh") and not g:
            check("%s gmsh 가 있다" % name, False, "requires_gmsh 인데 gmsh 가 없다")
            continue
        for label, conv in (("표준", False), ("i10", True)):
            r, why = run_variant(binary, o, folder, args, env, build_command, conv)
            if r is None:
                check("%s[%s] 돈다" % (name, label), False, why)
                continue
            if conv and r["unknown"]:
                # 변환기가 모르는 꼴이면 **판정하지 않는다고 말한다** — 통과로 세지 않는다.
                SKIPS.append("%s[i10] — 변환 못 한 꼴 %s" % (name, ", ".join(sorted(r["unknown"]))))
                continue
            for rel, w, n, bad in r["res"]:
                lines_checked += n
                if bad:
                    i, kw, line = bad[0]
                    check("%s[%s] %s 의 카드가 실효 %d칸과 맞다" % (name, label, rel, w), False,
                          "%d줄 틀림 — 첫 %s:%d %r" % (len(bad), kw, i, line[:70]))
                else:
                    OKS.append("%s[%s] %s" % (name, label, rel))
    # 세는 관문이 0 을 세면 언제나 초록이다 — 실측(2026-10-16) 14,366 줄이었다.
    check("검사한 정수 줄이 10,000 이상이다", lines_checked >= 10000, lines_checked)
    print()
    for s in SKIPS:
        print("  [판정 안 함] " + s)
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항 · 정수 줄 %d" % (len(OKS), lines_checked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
