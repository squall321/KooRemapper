#!/usr/bin/env python3
"""2줄 혼재 훑기 — 1줄·2줄 `*ELEMENT_SOLID` 카드가 섞인 덱에서 42 op 이 요소를 잃거나 얻지 않는가.

왜 이 시험이 있나 (2026-10-16, plan2 P1-1 「2줄 혼재 픽스처를 42 op 전수 축으로」).

  LS-DYNA 의 `*ELEMENT_SOLID` 카드는 두 꼴이다 — 구 포맷 1줄(`EID PID N1..N8`)과 현대 포맷 2줄(머리 줄
  `EID PID` + 절점 줄). 실덱(WB-LSDYNA 산출)은 2줄이다. 이 꼴을 공백 토큰으로 다루면 2줄 카드의 머리 줄과
  절점 줄이 **따로 논다** — 장부 P0-1 의 원형이 그것이다(`meshfix` 가 절점 줄만 지워 머리 줄 5개가 남았는데
  rc=0). 이 시험은 그 부류를 op 전수에서 찾는다.

어떻게.
  · 각 op 의 예제를 두 판으로 돌린다 — 표준 그대로 · 입력 덱의 `*ELEMENT_SOLID` 묶음을 둘로 갈라 **뒤
    절반을 2줄 카드로**(한 덱에 두 꼴이 섞인다).
  · 산출 덱마다 ① 각 묶음이 **한 꼴로 일관**되는가(1줄만, 또는 머리 줄·절점 줄 교대) ② **PID 별 요소 EID
    집합**이 표준 판 산출과 같은가. 정답을 따로 만들지 않는다 — 꼴만 바꿨으니 결과는 같아야 한다.
  · 바꿀 1줄 솔리드 카드가 없는 op 은 **판정하지 않는다고 말한다** — 통과로 세지 않는다.

이 시험이 처음 잡은 것 — `merge` 가 2줄 카드를 **요소로 인식조차 못 했다**(공백 토큰 10개 이상인 줄만 봤다).
2줄 혼재 덱을 합치면 그 요소들이 합쳐지지 않고 원래 PID 에 그대로 남았다(rc=0). 고쳤다.

usage: test_twoline_mix_sweep.py <KooRemapper 바이너리>
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

# ── 변환기·오라클 ────────────────────────────────────────────────────────────
INTS = re.compile(r"\s*[+-]?\d+(\s+[+-]?\d+)*\s*$")


def _kw(line):
    s = line.lstrip()
    return s.split()[0].upper() if s.startswith("*") else None


def _ints8(line):
    """고정폭 8칸(또는 공백 토큰) 정수 줄 → 목록."""
    if "," in line or not INTS.match(line):
        return None
    toks = line.split()
    return [int(t) for t in toks]


def to_twoline(text):
    """(바꾼 글, 바꾼 카드 수, 모르는 꼴). 1줄 카드(EID PID N1..N8 = 정수 10개)만 다룬다."""
    out, kw, block = [], None, []
    changed, unknown = 0, set()
    nl = "\r\n" if text.count("\r\n") * 2 > text.count("\n") else "\n"
    lines = text.replace("\r\n", "\n").split("\n")

    def flush():
        nonlocal changed
        data = [i for i, l in enumerate(block) if l.strip() and not l.lstrip().startswith("$")]
        cards = [block[i] for i in data]
        if not cards or not all(_ints8(c) is not None and len(_ints8(c)) == 10 for c in cards) or len(cards) < 2:
            out.extend(block)
            if cards and not all(_ints8(c) is not None and len(_ints8(c)) == 10 for c in cards):
                unknown.add("*ELEMENT_SOLID(1줄 10칸이 아닌 카드)")
            return
        half = len(cards) // 2
        first_data = data[0]
        out.extend(block[:first_data])
        for c in cards[:half]:
            out.append(c)
        out.append("*ELEMENT_SOLID")
        for c in cards[half:]:
            v = _ints8(c)
            out.append("%8d%8d" % (v[0], v[1]))
            out.append("".join("%8d" % x for x in v[2:]))
            changed += 1
    for l in lines:
        k = _kw(l)
        if k is not None:
            if kw == "*ELEMENT_SOLID":
                flush(); block = []
            kw = k
            out.append(l)
            continue
        if kw == "*ELEMENT_SOLID":
            block.append(l)
        else:
            out.append(l)
    if kw == "*ELEMENT_SOLID":
        flush()
    return nl.join(out), changed, unknown


def solid_eids_by_pid(text):
    """*ELEMENT_SOLID 묶음마다 꼴을 판정해 {PID: set(EID)} 와 꼴이 깨진 줄 목록을 돌려준다."""
    by, broken, kw, mode, pend = {}, [], None, None, None
    for n, l in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        k = _kw(l)
        if k is not None:
            if pend is not None:
                broken.append((pend[0], "머리 줄 뒤에 절점 줄이 없다"))
            kw, mode, pend = k, None, None
            continue
        if kw is None or not kw.startswith("*ELEMENT_SOLID") or kw.rstrip("%+-") != "*ELEMENT_SOLID":
            continue
        s = l.strip()
        if not s or s.startswith("$"):
            continue
        v = _ints8(l)
        if v is None:
            continue
        if mode is None:
            mode = "two" if len(v) == 2 else "one"
        if mode == "one":
            if len(v) < 6:
                broken.append((n, "1줄 묶음에 짧은 줄 %r" % s[:40])); continue
            by.setdefault(v[1], set()).add(v[0])
        else:
            if pend is None:
                if len(v) != 2:
                    broken.append((n, "2줄 묶음의 머리 줄이 아니다 %r" % s[:40])); continue
                pend = (n, v)
            else:
                by.setdefault(pend[1][1], set()).add(pend[1][0])
                pend = None
    if pend is not None:
        broken.append((pend[0], "머리 줄 뒤에 절점 줄이 없다"))
    return by, broken


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
                if not rel.startswith("materials" + os.sep):
                    yield rel, p


def run_variant(binary, o, folder, args, env, build_command, convert):
    d = tempfile.mkdtemp(prefix="tlmx_")
    try:
        why = _nlm.stage(o["name"], folder, d)
        if why:
            return None, "stage: " + why
        if o["name"] in _nlm.PREP:                    # 사전 단계가 입력을 만들 수 있다 — 변환은 그 뒤에
            argv, _w = _nlm.PREP[o["name"]]
            if _nlm.run_op(binary, d, argv, env)[0] != 0:
                return None, "사전 단계 실패"
        changed = 0
        if convert:
            for rel, p in list(decks(d)):
                t = open(p, encoding="utf-8", errors="surrogateescape", newline="").read()
                t2, ch, _u = to_twoline(t)
                changed += ch
                if ch:
                    open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(t2)
        base = {}
        for rel, p in decks(d):
            base[rel] = hashlib.sha256(open(p, "rb").read()).hexdigest()
            os.utime(p, (_nlm.BASE_T, _nlm.BASE_T))
        built = build_command(o["name"], args, Path(d))
        if getattr(built, "error", None):
            return None, "인자 조립 실패"
        rc, out = _nlm.run_op(binary, d, built.argv, env)
        prod = {}
        for rel, p in decks(d):
            if rel in base and base[rel] == hashlib.sha256(open(p, "rb").read()).hexdigest() and \
                    int(os.stat(p).st_mtime) == _nlm.BASE_T:
                continue
            prod[rel] = solid_eids_by_pid(open(p, encoding="utf-8", errors="replace").read())
        return {"rc": rc, "prod": prod, "changed": changed, "out": out[-160:]}, None
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
    print("[2줄 혼재 훑기] %d op × (표준 · 2줄 혼재)" % len(todo))
    judged = 0
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
        a, why = run_variant(binary, o, folder, args, env, build_command, False)
        if a is None:
            check("%s[표준] 돈다" % name, False, why)
            continue
        b, why = run_variant(binary, o, folder, args, env, build_command, True)
        if b is None:
            check("%s[2줄] 돈다" % name, False, why)
            continue
        if b["changed"] == 0:
            SKIPS.append("%s — 바꿀 1줄 솔리드 카드가 없다" % name)
            continue
        judged += 1
        check("%s rc 가 같다" % name, a["rc"] == b["rc"], "rc %d → %d %s" % (a["rc"], b["rc"], b["out"].strip()[-100:]))
        for rel, (eids, broken) in b["prod"].items():
            check("%s %s 의 요소 카드 꼴이 일관된다" % (name, rel), not broken,
                  "%d 곳 — 첫 줄 %d: %s" % (len(broken), broken[0][0], broken[0][1]) if broken else "")
            if rel in a["prod"]:
                A = a["prod"][rel][0]
                diff = [(p, len(A.get(p, ())), len(eids.get(p, ()))) for p in sorted(set(A) | set(eids))
                        if A.get(p) != eids.get(p)]
                check("%s %s 의 PID 별 EID 가 표준 판과 같다" % (name, rel), not diff,
                      "(PID, 표준, 2줄) %s" % diff[:4])
    # 세는 관문이 0 을 세면 언제나 초록이다 — 실측(2026-10-16) 37 op 을 판정했다.
    check("판정한 op 이 30 개 이상이다", judged >= 30, judged)
    print()
    for s in SKIPS:
        print("  [판정 안 함] " + s)
    if FAILS:
        print("FAIL %d  (OK %d)" % (len(FAILS), len(OKS)))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL PASS — %d 항 · 판정한 op %d" % (len(OKS), judged))
    return 0


if __name__ == "__main__":
    sys.exit(main())
