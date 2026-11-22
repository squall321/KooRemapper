#!/usr/bin/env python3
# 덱의 번호가 정수 상한(2147483647)일 때 새 번호를 내는 op 이 넘친 번호(음수 · 상한 위)를 쓰지 않고 거절하는지 보는 회귀 시험(미룬 결함 3차 2판)
"""새 번호 커서의 정수 상한 (2026-11-22 · 미룬 결함 3차 2판 L-04 · 계획 deferred-defects-round3-1121.plan.md).

왜 이 시험이 있나.

  op 들은 「덱의 최대 번호 + 1」 부터 새 번호를 낸다. I10 덱에서 최대 번호가 2147483647 이면 `+ 1` 이 int 를 넘쳐, 11-22 설치된 판
  (d1e2ce96)에서 op 여덟이 넘친 번호를 rc 0 으로 썼다 — meshfix(새 절점 · 요소가 -2147483648 부터) · cnrb2solid(새 절점) · matswap(새
  SECID) · boundary(새 세트) · ale(MID 음수) · iga(MID · `*PARAMETER_LOCAL`) · cclip(보고의 new_mid · new_secid) · merge(rc 1 이었지만 덱은
  썼다). 앞서 고친 tetremesh · id_floor 처럼 이제 모두 rc 1 로 멈추고 까닭에 상한을 적는다.

무엇을 보나(도움말 사례 덱을 I10 으로 다시 쓰고, 번호가 2147483647 인 절점 넷 · 셸 · 파트 · 섹션 · 재질 · 세트를 더한다).
  A. 모든 사례 — rc 가 무엇이든 산출(덱 · 보고 · JSON)에 상한을 넘거나 넘쳐 음수가 된 번호가 없다
  B. 위 여덟 — rc 1 · 까닭에 「2147483647」 · 산출 덱이 없다(보고 · 곁파일도)
  C. 바닥 — 같은 덱의 상한 번호를 2000000000 으로 낮추면 위 여덟이 상한 까닭으로 멈추지 않고 산출에 넘친 번호가 없다

usage: test_id_cursor_limit.py <KooRemapper 바이너리>
"""
import json
import os
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_deck_bom as T  # noqa: E402 — 도움말 사례를 차리는 판(Case)을 같이 쓴다

FAILS, OKS = [], []
MUST = ("meshfix", "cnrb2solid", "matswap", "boundary", "ale", "iga", "cclip", "merge")
TOKEN_KW = ("*NODE", "*ELEMENT_", "*SET_", "*CONSTRAINED_NODAL_RIGID_BODY", "*PART", "*SECTION_", "*MAT_")
NEG = re.compile(r"-(\d{10,})")
TOK = re.compile(r"(?<![\w.+-])(-?\d{10,})(?![\w.])")


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-104s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def i10(text):
    """도움말 사례 덱을 I10 으로 — 절점 · 요소 줄의 번호 칸만 10 칸(제목 · 인클루드 이름 줄은 그대로)."""
    out, kw, nline = [], "", 0
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if line.startswith("*"):
            kw, nline = line.split()[0].upper(), 0
            out.append("*KEYWORD I10=Y" if kw == "*KEYWORD" else line)
            continue
        if line.startswith("$") or not line.strip() or not kw or kw.startswith("*INCLUDE"):
            out.append(line)
            continue
        nline += 1
        title = (kw == "*TITLE") or (kw.startswith("*PART") and nline % 2 == 1) or (kw.endswith("_TITLE") and nline == 1)
        if title:
            out.append(line.strip())
            continue
        if kw.startswith("*NODE") and len(line.rstrip()) >= 56:
            cells = [line[0:8], line[8:24], line[24:40], line[40:56]] + [line[i:i + 8] for i in range(56, len(line.rstrip()), 8)]
        elif kw.startswith(TOKEN_KW):
            cells = line.split()
        else:
            out.append(line)
            continue
        cells = [c.strip() for c in cells]
        if kw.startswith("*NODE"):
            out.append(cells[0].rjust(10) + "".join(c.rjust(16) for c in cells[1:4]) + "".join(c.rjust(10) for c in cells[4:]))
        elif kw.startswith("*ELEMENT_"):
            out.append("".join(c.rjust(10) for c in cells))
        else:
            out.append("".join(c.rjust(10) for c in cells).rstrip())
    return "\n".join(out)


def extra(m):
    return "\n".join([
        "*NODE",
        "%10d%16s%16s%16s" % (m, "1000.0", "1000.0", "1000.0"), "%10d%16s%16s%16s" % (m - 1, "1001.0", "1000.0", "1000.0"),
        "%10d%16s%16s%16s" % (m - 2, "1001.0", "1001.0", "1000.0"), "%10d%16s%16s%16s" % (m - 3, "1000.0", "1001.0", "1000.0"),
        "*PART", "maxid part", "%10d%10d%10d" % (m, m, m),
        "*SECTION_SHELL", "%10d%10d" % (m, 2), "%10s%10s%10s%10s" % ("1.0", "1.0", "1.0", "1.0"),
        "*MAT_ELASTIC", "%10d%10s%10s%10s" % (m, "7.85e-9", "210000.0", "0.3"),
        "*ELEMENT_SHELL", "%10d%10d%10d%10d%10d%10d" % (m, m, m, m - 1, m - 2, m - 3),
        "*SET_NODE_LIST", "%10d" % m, "%10d%10d%10d%10d" % (m, m - 1, m - 2, m - 3),
    ]) + "\n"


def add_extra(text, m):
    i = text.rfind("\n*END")
    return text[:i + 1] + extra(m) + text[i + 1:] if i >= 0 else text + extra(m)


def _json_hits(o, path=""):
    """JSON 의 정수 가운데 상한을 넘거나 넘쳐 음수가 된 것 — `shift`(이월 적용의 옮김량)는 번호가 아니라 뺀다."""
    if isinstance(o, dict):
        return [h for k, v in o.items() if k != "shift" for h in _json_hits(v, path + "." + k)]
    if isinstance(o, list):
        return [h for i, v in enumerate(o) for h in _json_hits(v, path + "[%d]" % i)]
    if isinstance(o, int) and not isinstance(o, bool) and (o > 2147483647 or o < -999999999):
        return ["%s %d" % (path, o)]
    return []


def overflowed(data):
    """넘친 번호 — 덱은 10 칸씩(절점 줄은 번호 칸만) 큰 수 · 붙은 음수, JSON 은 구조로, 그 밖은 떨어진 토큰."""
    hits = []
    text = data.decode("utf-8", "replace")
    if text.lstrip().startswith(("{", "[")):
        try:
            return _json_hits(json.loads(text))
        except ValueError:
            pass
    deck = any(l.startswith("*") for l in text.split("\n")[:50])
    kw = ""
    for l in text.split("\n"):
        l = l.rstrip("\r")
        if deck and l.startswith("*"):
            kw = l.split()[0].upper() if l.split() else l
            continue
        if l.startswith("$") or not l.strip():
            continue
        if deck:
            if kw.startswith(("*KEYWORD", "*TITLE", "*INCLUDE")):
                continue
            cells = [l[:10]] if kw.rstrip("%+-").startswith("*NODE") else [l[c:c + 10] for c in range(0, len(l), 10)]
            hits += ["%s %s" % (kw, c.strip()) for c in cells if c.strip().lstrip("-").isdigit() and
                     (int(c.strip()) > 2147483647 or int(c.strip()) < -999999999)]
            hits += ["%s -%s" % (kw, m.group(1)) for m in NEG.finditer(l)]
        else:
            hits += [m.group(1) for m in TOK.finditer(l) if int(m.group(1)) > 2147483647 or int(m.group(1)) < -999999999]
    return hits


def run_case(spec, root, m):
    case = T.Case(T_BINARY, root, spec)
    if not case.cmd or not case.decks:
        return None
    for k, rel in enumerate(case.decks):
        if "frag" in os.path.basename(rel).lower():
            continue                                  # 조각은 계약상 표준 폭이다
        p = os.path.join(case.base, rel)
        with open(p, encoding="utf-8", errors="replace", newline="") as f:
            text = i10(f.read())
        if k == 0:
            text = add_extra(text, m)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    return case.go()


def main():
    global T_BINARY
    T_BINARY = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_idlimit_")
    try:
        print("[A · B — 번호가 2147483647 인 덱]")
        for spec in T.OPS:
            name = spec["name"]
            root = os.path.join(top, "max_" + re.sub(r"[^A-Za-z0-9]+", "_", name))
            try:
                got = run_case(spec, root, 2147483647)
            except Exception as e:  # noqa: BLE001
                check(f"A {name} — 사례 준비", False, e)
                continue
            if got is None:
                continue
            rc, text, outs = got
            hits = [rel + " " + h for rel, data in outs.items() for h in overflowed(data)]
            check(f"A {name} — 넘친 번호를 쓰지 않는다(rc {rc})", not hits, hits[:4])
            if name in MUST:
                decks = [r for r in outs if r.endswith((".k", ".key", ".dyn", ".json"))]
                check(f"B {name} — rc 1 · 까닭에 상한 · 덱 · 보고 없음", rc == 1 and "2147483647" in text and not decks,
                      (rc, decks, text[-300:]))
            shutil.rmtree(root, ignore_errors=True)
        print("[C — 바닥(2000000000)이면 된다]")
        for spec in T.OPS:
            if spec["name"] not in MUST:
                continue
            root = os.path.join(top, "low_" + spec["name"])
            got = run_case(spec, root, 2000000000)
            rc, text, outs = got
            hits = [rel + " " + h for rel, data in outs.items() for h in overflowed(data)]
            # 사례마다 rc 0 은 아니다(merge 사례는 PID 참조 보고로 rc 1) — 상한 까닭으로 멈추지 않고 넘친 번호가 없으면 된다
            check(f"C {spec['name']} — 상한 까닭 없음 · 넘친 번호 없음", "2147483647" not in text and not hits and bool(outs),
                  (rc, hits[:3], text[-300:]))
            shutil.rmtree(root, ignore_errors=True)
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
