#!/usr/bin/env python3
# 주 덱이 I10=Y · LONG=Y 일 때 assemble 의 battery 덱이 주 덱 폭으로 쓰이는지 보는 회귀 시험(미룬 결함 3차 2판 L-08)
"""battery 덱을 주 덱 폭으로 (2026-11-22 · 미룬 결함 3차 2판 L-08 · 사용자 결정 「battery 덱을 주 덱 폭으로 쓴다」).

왜 이 시험이 있나.

  11-22 설치된 판(d1e2ce96)은 주 덱이 `*KEYWORD I10=Y` · `LONG=Y` 여도 `use_include: true` 면 rc 0 으로 표준 폭 battery 덱(맨
  `*KEYWORD` · 절점 줄 56 자)을 `*INCLUDE` 로 붙였다. LS-DYNA 는 인클루드를 주 덱 폭으로 읽을 수 있고(Vol_I 「Long Format Input」 —
  `*INCLUDE -` · `+` 가 없으면) 우리 extract-parts 는 그 닫힘을 섞인 폭으로 거절했다. `use_include: false` 는 주 덱이 표준 폭이 아니면
  rc 1 로 거절했다. 이제 battery 덱 쓰기 전부가 주 덱의 칸 폭을 따른다 — 인클루드는 머리에 제 폭을 밝히고(`I10=Y` · `LONG=Y`),
  펼친 카드는 주 덱 폭이다. LS-DYNA 로 돌려 본 것은 없다(라이선스 만료).

무엇을 보나(변형 여섯 × 주 덱 폭 둘 — 기준은 같은 상자를 표준 폭으로 둔 실행).
  W-1 use_include: true — rc 0 · battery 덱이 주 덱 폭을 밝힌다 · 선언된 폭으로 읽은 battery 덱 값(블록 차례 · 줄 수 · 수는 상대
      1e-3)이 기준과 같다 · 주 덱 값도 같다
  W-2 use_include: false — rc 0(예전엔 거절) · 주 덱에 `*INCLUDE` 가 없다 · 주 덱 값이 기준(펼친 표준 덱)과 같다

usage: test_battery_deck_width.py <KooRemapper 바이너리>
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
sys.path.insert(0, os.path.join(REPO, "tools", "help"))
import test_long_readers as L  # noqa: E402 — 선언된 폭으로 읽기 · 표준 → LONG
from ops_help import OPS  # noqa: E402

FAILS, OKS = [], []
BOX = {o["name"]: o for o in OPS}["warpage"]["files"]["box.yaml"]
VARIANTS = (
    ("적층 기본", "stacked", {}),
    ("적층 dent", "stacked", {"mode": "dent"}),
    ("적층 pouch 예압", "stacked", {"pouch_expand_ratio": "0.01"}),
    ("적층 TSHELL", "stacked", {"solid_electrode": "false"}),
    ("적층 에어백", "stacked", {"airbag_fill": "true"}),
    ("권취 기본", "wound", {}),
)


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-600:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=1800,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def to_i10(text):
    """표준 덱을 I10=Y 로 — 절점 (I8,3F16,2I8) → (I10,3F16,2I10) · 격자 요소 줄 8 칸 → 10 칸. 10 칸 카드는 그대로."""
    out, kw = [], ""
    for line in text.split("\n"):
        if line.startswith("*"):
            kw = line.split()[0].upper()
            out.append("*KEYWORD I10=Y" if kw == "*KEYWORD" else line)
            continue
        if line.startswith("$") or not line.strip():
            out.append(line)
            continue
        if kw == "*NODE":
            cells = [line[0:8], line[8:24], line[24:40], line[40:56], line[56:64], line[64:72]]
            ws = [10, 16, 16, 16, 10, 10]
            out.append("".join(c.strip().rjust(w) for c, w in zip(cells, ws)).rstrip())
        elif kw in ("*ELEMENT_SHELL", "*ELEMENT_SOLID", "*ELEMENT_TSHELL"):
            out.append("".join(c.strip().rjust(10) for c in L.chunks(line, 8)).rstrip())
        else:
            out.append(line)
    return "\n".join(out)


def battery_yaml(model, extra):
    src = {"stacked": "stacked/stacked_swell.yaml", "wound": "wound/wound_swell.yaml"}[model]
    t = open(os.path.join(REPO, "examples", "battery", "swell", src), encoding="utf-8").read()
    t = re.sub(r"^output:.*$", "output: bt", t, count=1, flags=re.M)
    for k, v in extra.items():
        pat = re.compile(r"^%s:.*$" % re.escape(k), re.M)
        t = pat.sub("%s: %s" % (k, v), t, count=1) if pat.search(t) else t + "\n%s: %s\n" % (k, v)
    return t


def stage(binary, root, name, bat_text, conv, use_include):
    d = os.path.join(root, name)
    os.makedirs(d)
    with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
        f.write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    p = os.path.join(d, "box.k")
    with open(p, encoding="utf-8") as f:
        t = f.read()
    with open(p, "w", encoding="utf-8") as f:
        f.write(conv(t))
    with open(os.path.join(d, "bat.yaml"), "w", encoding="utf-8") as f:
        f.write(bat_text)
    with open(os.path.join(d, "a.yaml"), "w", encoding="utf-8") as f:
        f.write("base_model: box.k\noutput: ba\noperations:\n  - type: battery\n    config: bat.yaml\n"
                + ("" if use_include else "    use_include: false\n"))
    rc, out = run(binary, d, "assemble", "a.yaml")
    return d, rc, out


def battery_deck(d, main_text):
    """주 덱의 `*INCLUDE` 가 가리키는 battery 덱 경로(없으면 None)."""
    lines = main_text.split("\n")
    for i, l in enumerate(lines):
        if l.strip().upper() == "*INCLUDE" and i + 1 < len(lines):
            return os.path.join(d, lines[i + 1].strip())
    return None


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    binary = os.path.abspath(sys.argv[1])
    top = tempfile.mkdtemp(prefix="kr_batwidth_")
    try:
        for vi, (vname, model, extra) in enumerate(VARIANTS):
            text = battery_yaml(model, extra)
            for inc in (True, False):
                tag = "W-1 include" if inc else "W-2 펼침"
                base, brc, bout = stage(binary, top, "v%d_%d_std" % (vi, inc), text, lambda t: t, inc)
                if not check("%s %s — 표준 주 덱 기준 rc 0" % (tag, vname), brc == 0, bout[-300:]):
                    continue
                for wname, conv, fw in (("I10", to_i10, 10), ("LONG", L.to_long, 20)):
                    d, rc, out = stage(binary, top, "v%d_%d_%s" % (vi, inc, wname), text, conv, inc)
                    name = "%s %s · 주 덱 %s" % (tag, vname, wname)
                    if not check(name + " — rc 0", rc == 0, out[-400:]):
                        continue
                    main_a, main_b = read(os.path.join(base, "ba.k")), read(os.path.join(d, "ba.k"))
                    why = L.same_values(L.values(main_a), L.values(main_b, strict=(fw == 20)))
                    check(name + " — 주 덱 값이 기준과 같다", why is None, why)
                    if inc:
                        pa, pb = battery_deck(base, main_a), battery_deck(d, main_b)
                        if not check(name + " — 주 덱이 battery 덱을 *INCLUDE 로 문다", pa and pb and os.path.exists(pb), (pa, pb)):
                            continue
                        bat_a, bat_b = read(pa), read(pb)
                        check(name + " — battery 덱이 주 덱 폭을 밝힌다", L.deck_width(bat_b) == fw, bat_b[:300])
                        why = L.same_values(L.values(bat_a), L.values(bat_b, strict=(fw == 20), inherit=fw))
                        check(name + " — battery 덱 값이 기준과 같다", why is None, why)
                    else:
                        check(name + " — 주 덱에 *INCLUDE 없음(펼쳤다)", "*INCLUDE" not in main_b.upper(), "")
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
