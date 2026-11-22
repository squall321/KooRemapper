#!/usr/bin/env python3
# rbe 의 CNRB PID · matdb 의 감쇠 세트 SID 가 공용 번호 커서로 나와 덱의 파트 · 세트와 겹치지 않는지 보는 회귀 시험(3차 3판 L-16)
"""공용 번호 커서 (2026-11-22 · 미룬 결함 3차 3판 L-16).

왜 이 시험이 있나 — 11-22 설치된 판(1106bef1)에서
  · rbe(rbe2 · spider)의 `*CONSTRAINED_NODAL_RIGID_BODY` PID 를 덱의 CNRB 최대값 위로만 내 상자의 `*PART` 1 과 같은 1 을 냈다 — CNRB 의 PID 는
    파트 번호와 한 이름공간이다(강체 파트 · LS-DYNA 가 멈춘다)
  · matdb 의 감쇠 세트(`*SET_PART_LIST` · `*DAMPING_PART_*_SET` 의 PSID)를 「MID · PID + 800000」 으로 박아, 덱에 이미 있는 SET 800001 과 겹쳤고
    두 번 돌리면 앞 실행이 남긴 세트와 겹쳤다(rc 0)
  이제 CNRB 는 공용 파트 커서, 감쇠 세트는 공용 세트 커서(덱 · 인클루드의 세트 위)로 낸다. 같은 규칙의 세트 훑기 사본 둘도 하나로 모았다.

무엇을 보나
  A rbe2 spider — rc 0 · CNRB PID 가 `*PART` 번호와 겹치지 않는다
  B matdb(SUS304 · DB 감쇠 카드 + smartphone_drop · 모든 파트) · 덱에 SET 800001 — rc 0 · 세트 번호 겹침 없음 · `*DAMPING_PART_*_SET` 의 PSID 가
    정의된 세트다
  C 같은 설정을 B 의 산출에 한 번 더 — 세트 번호 겹침 없음
  A2 덱에 CNRB PID 2 가 이미 있다 — 새 CNRB PID 가 그것과 겹치지 않는다(파트 커서를 CNRB 최대값까지 올린다)
  D 세트의 들여 쓴 `*` · `$` 제목 — 세트 커서가 그 세트의 SID 를 센다(3차 3판 L-09 — 1열 규칙)

usage: test_shared_cursors.py <KooRemapper 바이너리>
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
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
from ops_help import OPS  # noqa: E402

FAILS, OKS = [], []
SP = {o["name"]: o for o in OPS}


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, d, *args):
    p = subprocess.run([binary, *args], cwd=d, capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def first_ids(text, prefix):
    """prefix 로 시작하는 블록마다 첫 데이터 줄(`_TITLE` 이면 제목 다음)의 첫 칸."""
    out, kw, need, first = [], None, False, False
    for l in text.split("\n"):
        if l.startswith("*"):
            k = l.split()[0].upper()
            kw = k if k.startswith(prefix) else None
            need = kw is not None and "_TITLE" in kw
            first = kw is not None
            continue
        if kw is None or l.startswith("$"):
            continue
        if need:
            need = False
            continue
        if first and l.strip():
            out.append(int(l[:10]))
            first = False
    return out


def part_ids(text):
    return [int(m.group(1)) for m in re.finditer(r"\*PART(?:_TITLE)?\n[^\n]*\n(?:\$[^\n]*\n)*\s*(\d+)", text)]


def main():
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_cursors_")
    try:
        d = os.path.join(top, "a")
        os.makedirs(d)
        for fn, c in SP["rbe"]["files"].items():
            with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
                f.write(c.replace("type: rbe3", "type: rbe2"))
        run(binary, d, "generate", "box", "box.yaml")
        rc, out = run(binary, d, "rbe", "rbe.yaml")
        o = os.path.join(d, "box_rbe.k")
        if check("A rbe2 spider — rc 0", rc == 0 and os.path.exists(o), out[-300:]):
            t = open(o, encoding="utf-8").read()
            cnrb, parts = first_ids(t, "*CONSTRAINED_NODAL_RIGID_BODY"), part_ids(t)
            check("A — CNRB PID %s 가 *PART %s 와 겹치지 않는다" % (cnrb, parts), cnrb and not set(cnrb) & set(parts), (cnrb, parts))

        # A2 — 덱에 CNRB PID 2(파트 표 위)가 이미 있다 — 새 CNRB 는 파트 · CNRB 최대값 위로
        p = os.path.join(d, "box.k")
        t = open(p, encoding="utf-8").read()
        with open(p, "w", encoding="utf-8") as f:
            f.write(t.replace("*END", "*CONSTRAINED_NODAL_RIGID_BODY\n%10d%10d%10d\n*SET_NODE_LIST\n%10d\n%10d%10d\n*END" % (2, 0, 900, 900, 1, 2), 1))
        rc, out = run(binary, d, "rbe", "rbe.yaml")
        if check("A2 rbe2 · 덱에 CNRB PID 2 — rc 0", rc == 0 and os.path.exists(o), out[-300:]):
            t = open(o, encoding="utf-8").read()
            cnrb, parts = first_ids(t, "*CONSTRAINED_NODAL_RIGID_BODY"), part_ids(t)
            check("A2 — CNRB PID %s 가 서로 · *PART %s 와 겹치지 않는다" % (cnrb, parts),
                  len(cnrb) >= 2 and len(set(cnrb)) == len(cnrb) and not set(cnrb) & set(parts), (cnrb, parts))

        d = os.path.join(top, "b")
        os.makedirs(d)
        for fn, c in SP["matdb"]["files"].items():
            with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
                f.write(c + ("damping_preset: smartphone_drop\n" if fn == "matdb.yaml" else ""))
        run(binary, d, "generate", "box", "box.yaml")
        p = os.path.join(d, "box.k")
        t = open(p, encoding="utf-8").read()
        t = t.replace("*END", "*SET_PART_LIST\n%10d\n%10d\n*END" % (800001, 1), 1)
        t = t.replace("*END", "*PART\nsecond\n%10d%10d%10d\n*END" % (2, 1, 1), 1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(t)
        for tag, src in (("B", "box.k"), ("C", "box_matdb.k")):
            if tag == "C":
                shutil.copy(os.path.join(d, "box_matdb.k"), os.path.join(d, "again.k"))
                with open(os.path.join(d, "matdb.yaml"), encoding="utf-8") as f:
                    y = f.read()
                with open(os.path.join(d, "matdb.yaml"), "w", encoding="utf-8") as f:
                    f.write(y.replace("model: box.k", "model: again.k").replace("output: box_matdb.k", "output: again_matdb.k"))
            rc, out = run(binary, d, "matdb", "matdb.yaml")
            o = os.path.join(d, "box_matdb.k" if tag == "B" else "again_matdb.k")
            if not check("%s matdb 감쇠(DB 카드 · 모든 파트) — rc 0" % tag, rc == 0 and os.path.exists(o), out[-300:]):
                continue
            t = open(o, encoding="utf-8").read()
            sets = first_ids(t, "*SET_")
            psid = first_ids(t, "*DAMPING_PART_")
            dup = sorted({x for x in sets if sets.count(x) > 1})
            check("%s — 세트 번호 겹침 없음 %s · 감쇠 카드의 PSID %s 가 정의된 세트다" % (tag, sets, psid),
                  not dup and psid and set(psid) <= set(sets), (sets, psid, dup))
        # D — 세트의 들여 쓴 제목(「  *rim」 · 「  $rim」)은 제목이다 — 세트 커서가 그 SID 2 를 센다(3차 3판 L-09)
        for tag, title in (("D-1", "  *rim parts"), ("D-2", "  $rim parts")):
            d = os.path.join(top, tag)
            os.makedirs(d)
            for fn, c in SP["matdb"]["files"].items():
                with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
                    f.write(c + ("damping_preset: smartphone_drop\n" if fn == "matdb.yaml" else ""))
            run(binary, d, "generate", "box", "box.yaml")
            p = os.path.join(d, "box.k")
            t = open(p, encoding="utf-8").read()
            t = t.replace("*END", "*SET_PART_LIST\n%10d\n%10d\n*SET_PART_LIST_TITLE\n%s\n%10d\n%10d\n*END" % (1, 1, title, 2, 1), 1)
            with open(p, "w", encoding="utf-8") as f:
                f.write(t)
            rc, out = run(binary, d, "matdb", "matdb.yaml")
            o = os.path.join(d, "box_matdb.k")
            if check("%s matdb 감쇠 · 세트 1 · 제목 「%s」 인 세트 2 — rc 0" % (tag, title), rc == 0 and os.path.exists(o), out[-300:]):
                t = open(o, encoding="utf-8").read()
                sets = first_ids(t, "*SET_")
                dup = sorted({x for x in sets if sets.count(x) > 1})
                check("%s — 세트 번호 겹침 없음 %s" % (tag, sets), not dup and 2 in sets, (sets, dup))
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
