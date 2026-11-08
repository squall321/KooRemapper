#!/usr/bin/env python3
# assemble 의 battery 덱 번호가 기존 모델 번호와 겹치지 않는지(족마다 최대값 위로 · 오프셋 · use_include · 거절) 보는 회귀 시험
"""assemble 의 battery 번호 (2026-11-08 · 사용자 결정 「고친다」).

왜 이 시험이 있나.

  `- type: battery` 는 battery 덱을 지어 `*INCLUDE` 로 붙인다. battery 덱의 번호는 늘 1(절점 · 요소)과 고정 상수(PID · SECID ·
  MID · 세트 · 곡선 · 접촉)라 기존 모델과 겹쳤고(실측: 상자 198 절점이 모두 겹쳐 rc 0), 카탈로그가 적은 node_id_offset ·
  elem_id_offset(0 = 있는 최대값 위) · use_include(false = 주 덱에 펼친다)는 읽기만 하고 쓰지 않았다. 이제 족마다 기존 모델의
  최대값 위로 옮기고(공용 바닥 + 열 재질 · 모래시계 · 접촉 · 곡선), 준 오프셋을 쓰고, use_include 를 지킨다.

판정은 이 파일의 덱 읽기(파이썬 — C++ 와 따로 쓴 칸 표)로 한다.
  · 족마다 정의가 주 덱 + battery 덱을 통틀어 하나뿐(세트는 종류마다 — LS-DYNA 의 이름공간)
  · 모든 참조(요소 → 절점 · 파트, 파트 → 섹션 · 재질 · 모래시계 · 열 재질, 세트 멤버, 접촉 SSID · MSID(STYP 로 족), 경계 · 하중 ·
    에어백 · 열팽창 · 초기 응력 · 변형률, 재질의 곡선)가 정의된 번호를 가리킨다
  · 얹은 battery 덱 = 단독 battery 덱 + 족마다 오프셋(정의 · 참조 모두 같은 차례) · 줄 수가 같고 바뀐 글자는 숫자 · 공백뿐
  · 오프셋 = 기존 모델(상자 + 모든 족을 겹치게 덧붙인 정의)의 그 족 최대값 — battery 가 쓰지 않는 족은 0

무엇을 보나.
  A 적층 기본 · dent · bare · phase 2 · pouch 예압(INITIAL_STRESS_SHELL) · TSHELL, 권취 기본 · dent · phase 2 — 위 넷
  E-1 node_id_offset 1000000 · elem_id_offset 2000000 → 그 값   E-2 node_id_offset 5(최대값 아래) → rc 1 · 아무것도 쓰지 않는다
  I   use_include: false → battery 덱 파일 없음 · 주 덱에 *INCLUDE 없음 · 한 덱에서 위 판정
  D   phase 2 · use_dynain · dynain_file → rc 1(옮기면 그 dynain 의 번호와 어긋난다) · 아무것도 쓰지 않는다
  L   battery 뒤의 contact 가 낸 접촉 · 세트 번호도 battery 와 겹치지 않는다(뒤 op 의 번호 발급이 battery 덱을 센다)

usage: test_assemble_battery_ids.py <KooRemapper 바이너리>
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
BOX = {o["name"]: o for o in OPS}["warpage"]["files"]["box.yaml"]

# 기존 모델(상자)에 덧붙여 battery 의 모든 족과 겹치게 하는 정의 — 세트 1 · 2 · 3 · 102 · 504, 곡선 9001~9904, 모래시계 1 · 2,
# 열 재질 101, 접촉 1. (섹션 · 재질 1 · 절점 1~ · 요소 1~ 은 상자에 이미 있다)
EXTRA = """*SET_NODE_LIST
         1
         1         2
*SET_NODE_LIST
         2
         3
*SET_NODE_LIST
         3
         4
*SET_PART_LIST
       102
         1
*SET_SEGMENT
       504
         1         2        13        12
*DEFINE_CURVE
      9001
                 0.0                 0.0
                 1.0                 1.0
*DEFINE_CURVE
      9002
                 0.0                 0.0
                 1.0                 1.0
*DEFINE_CURVE
      9901
                 0.0                 0.0
                 1.0                 1.0
*DEFINE_CURVE
      9903
                 0.0                 0.0
                 1.0                 1.0
*DEFINE_CURVE
      9904
                 0.0                 0.0
                 1.0                 1.0
*HOURGLASS
         1         4       0.1
         2         4       0.1
*MAT_THERMAL_ISOTROPIC
       101  7.85e-09       0.0       1.0
     460.0      50.0
*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID
         1
         1         0         3         0
         0         0
         0         0
*CONTROL_TERMINATION
     0.010
"""


def check(name, cond, detail=""):
    (OKS if cond else FAILS).append(name if cond else "%s   %s" % (name, str(detail).strip()[-500:]))
    print("  %-100s %s" % (name, "OK" if cond else "FAIL"))
    return cond


def run(binary, cwd, *args):
    p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=1800,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


# ── 덱 읽기(판정용 · C++ 와 따로 쓴 칸 표) ─────────────────────────────────────────────────────────────────────────

def blocks_of(path):
    """(키워드, 데이터 줄들[주석 뺌], *INCLUDE 이름들) — 첫 *END 에서 멈춘다."""
    out, incs = [], []
    kw, cur = None, None
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("*"):
            k = l.split()[0].upper()
            if k == "*END":
                break
            kw, cur = k, []
            out.append((kw, cur))
            continue
        if kw is None or l.startswith("$"):
            continue
        cur.append(l)
    for kw, ls in out:
        if kw == "*INCLUDE":
            incs.extend(x.strip() for x in ls if x.strip())
    return out, incs


def num(l, a, b):
    t = l[a:b].strip()
    if not t:
        return 0
    try:
        return int(t)
    except ValueError:
        raise DeckUnreadable("%d~%d열 「%s」 을 정수로 읽지 못했다 — 줄 %r" % (a + 1, b, t, l))


SET_KIND = {"*SET_NODE": "set_node", "*SET_PART": "set_part", "*SET_SEGMENT": "set_segment", "*SET_SHELL": "set_shell"}
STYP = {0: "set_segment", 1: "set_shell", 2: "set_part", 3: "part", 4: "set_node", 6: "set_part"}


def facts(blocks):
    """(정의 {족: [번호…]}, 참조 [(족, 번호)]) — 0 은 참조가 아니다."""
    defs, refs = {}, []

    def d(f, v):
        if v:
            defs.setdefault(f, []).append(v)

    def r(f, v):
        if v:
            refs.append((f, v))

    for kw, ls in blocks:
        title = kw.endswith("_TITLE")
        t0 = 1 if title else 0
        if kw == "*NODE":
            for l in ls:
                d("node", num(l, 0, 8))
        elif kw in ("*ELEMENT_SHELL", "*ELEMENT_SOLID", "*ELEMENT_TSHELL"):
            for l in ls:
                d("elem", num(l, 0, 8))
                r("part", num(l, 8, 16))
                for q in range(8):
                    r("node", num(l, 16 + 8 * q, 24 + 8 * q))
        elif kw == "*PART":
            for q in range(1, len(ls), 2):
                l = ls[q]
                d("part", num(l, 0, 10))
                r("section", num(l, 10, 20))
                r("mat", num(l, 20, 30))
                r("hourglass", num(l, 40, 50))
                r("tmat", num(l, 70, 80))
        elif kw == "*SECTION_SHELL":
            for q in range(0, len(ls), 2):
                d("section", num(ls[q], 0, 10))
        elif kw.startswith("*SECTION_"):
            for l in ls:
                d("section", num(l, 0, 10))
        elif kw == "*HOURGLASS":
            for l in ls:
                d("hourglass", num(l, 0, 10))
        elif kw.startswith("*MAT_THERMAL_"):
            d("tmat", num(ls[t0], 0, 10))
        elif kw == "*MAT_ADD_THERMAL_EXPANSION":
            for l in ls:
                r("part", num(l, 0, 10))
                r("curve", num(l, 10, 20))
                r("curve", num(l, 30, 40))
                r("curve", num(l, 50, 60))
        elif kw.startswith("*MAT_"):
            d("mat", num(ls[t0], 0, 10))
            if kw.startswith("*MAT_PIECEWISE_LINEAR_PLASTICITY") and len(ls) > t0 + 1:
                r("curve", num(ls[t0 + 1], 20, 30))
                r("curve", num(ls[t0 + 1], 30, 40))
        elif kw.startswith("*SET_"):
            kind = next(v for k, v in SET_KIND.items() if kw.startswith(k))
            d(kind, num(ls[t0], 0, 10))
            for l in ls[t0 + 1:]:
                if kind == "set_segment":
                    for q in range(4):
                        r("node", num(l, 10 * q, 10 * q + 10))
                else:
                    for q in range(8):
                        r("node" if kind == "set_node" else "part", num(l, 10 * q, 10 * q + 10))
        elif kw.startswith("*DEFINE_CURVE"):
            d("curve", num(ls[t0], 0, 10))
        elif kw.startswith("*CONTACT_"):
            d("contact", num(ls[0], 0, 10))
            c1 = ls[1]
            for idc, tc in ((0, 20), (10, 30)):
                t = num(c1, tc, tc + 10)
                if t != 5:
                    r(STYP[t], num(c1, idc, idc + 10))
            if len(ls) > 4:
                r("curve", num(ls[4], 20, 30))
            if len(ls) > 5:
                r("curve", num(ls[5], 20, 30))
        elif kw == "*BOUNDARY_SPC_NODE":
            for l in ls:
                r("node", num(l, 0, 10))
        elif kw == "*BOUNDARY_SPC_SET":
            for l in ls:
                r("set_node", num(l, 0, 10))
        elif kw == "*BOUNDARY_PRESCRIBED_MOTION_SET":
            for l in ls:
                r("set_node", num(l, 0, 10))
                r("curve", num(l, 30, 40))
        elif kw == "*LOAD_SEGMENT_SET":
            for l in ls:
                r("set_segment", num(l, 0, 10))
                r("curve", num(l, 10, 20))
        elif kw == "*LOAD_THERMAL_VARIABLE":
            for q in range(0, len(ls), 2):
                r("set_node", num(ls[q], 0, 10))
                r("set_node", num(ls[q], 10, 20))
                for a in (20, 50, 60, 70):
                    r("curve", num(ls[q + 1], a, a + 10))
        elif kw == "*AIRBAG_LINEAR_FLUID":
            r("set_segment" if num(ls[0], 10, 20) == 0 else "set_part", num(ls[0], 0, 10))
            for a in range(20, 80, 10):
                r("curve", num(ls[1], a, a + 10))
        elif kw == "*INITIAL_STRESS_SHELL":
            q = 0
            while q < len(ls):
                r("elem", num(ls[q], 0, 10))
                q += 1 + num(ls[q], 10, 20) * num(ls[q], 20, 30)
        elif kw == "*INITIAL_STRAIN_SOLID":
            q = 0
            while q < len(ls):
                r("elem", num(ls[q], 0, 10))
                q += 1 + max(1, num(ls[q], 10, 20))
        elif kw == "*CONTROL_TIMESTEP":
            r("curve", num(ls[0], 50, 60))
        elif kw == "*DATABASE_BINARY_D3PLOT":
            r("curve", num(ls[0], 10, 20))
            r("set_part", num(ls[0], 40, 50))
        elif kw in ("*DATABASE_GLSTAT", "*DATABASE_MATSUM", "*DATABASE_RCFORC"):
            r("curve", num(ls[0], 20, 30))
    return defs, refs


POOL = {"set_node": "set", "set_part": "set", "set_segment": "set", "set_shell": "set"}   # C++ 는 세트를 한 통으로 옮긴다


class DeckUnreadable(Exception):
    """칸이 어긋나 번호를 읽지 못한 카드 — 판정은 FAIL 로 적는다(시험이 멈추지 않게)."""


def deck_facts(main):
    """주 덱과 그 *INCLUDE(주 덱 폴더 기준)의 (정의, 참조, battery 쪽만의 (정의, 참조), 인클루드 이름)."""
    bl, incs = blocks_of(main)
    defs, refs = facts(bl)
    bdefs, brefs = {}, []
    for n in incs:
        ib, _ = blocks_of(os.path.join(os.path.dirname(main), n))
        dd, rr = facts(ib)
        for f, v in dd.items():
            defs.setdefault(f, []).extend(v)
            bdefs.setdefault(f, []).extend(v)
        refs.extend(rr)
        brefs.extend(rr)
    return defs, refs, bdefs, brefs, incs


def integrity(defs, refs):
    """겹친 정의(족마다)와 정의되지 않은 참조."""
    dup = {f: sorted({x for x in v if v.count(x) > 1})[:5] for f, v in defs.items() if len(v) != len(set(v))}
    have = {f: set(v) for f, v in defs.items()}
    dangling = sorted({(f, v) for f, v in refs if v not in have.get(f, ())})[:8]
    return dup, dangling


def shifted_ok(std_defs, std_refs, got_defs, got_refs, off):
    """얹은 battery = 단독 battery + 족 오프셋(정의 · 참조 모두 같은 차례)."""
    for f, v in std_defs.items():
        o = off.get(POOL.get(f, f), 0)
        if got_defs.get(f) != [x + o for x in v]:
            return "정의 %s 가 +%d 가 아니다" % (f, o)
    if set(got_defs) != set(std_defs):
        return "정의 족이 다르다 %s / %s" % (sorted(got_defs), sorted(std_defs))
    want = [(f, v + off.get(POOL.get(f, f), 0)) for f, v in std_refs]
    if want != got_refs:
        bad = next(((a, b) for a, b in zip(want, got_refs) if a != b), None)
        return "참조가 오프셋만큼 옮겨지지 않았다(첫 차이 %s)" % (bad,)
    return ""


def bytes_ok(std_path, got_path):
    a = open(std_path, encoding="utf-8").read().splitlines()
    b = open(got_path, encoding="utf-8").read().splitlines()
    if len(a) != len(b):
        return "줄 수 %d / %d" % (len(a), len(b))
    for i, (x, y) in enumerate(zip(a, b)):
        if x == y:
            continue
        if len(x) != len(y) or any(p != q and not (p in "0123456789 " and q in "0123456789 ") for p, q in zip(x, y)):
            return "%d째 줄이 번호 칸 밖에서 바뀌었다: %r → %r" % (i + 1, x, y)
    return ""


def base_offsets(defs):
    off = {}
    for f, v in defs.items():
        k = POOL.get(f, f)
        off[k] = max(off.get(k, 0), max(v))
    return off


VARIANTS = (
    ("적층 기본", "stacked", {}),
    ("적층 dent", "stacked", {"mode": "dent"}),
    ("적층 bare", "stacked", {"mode": "bare"}),
    ("적층 phase 2", "stacked", {"phase": "2"}),
    ("적층 pouch 예압", "stacked", {"pouch_expand_ratio": "0.01"}),
    ("적층 TSHELL", "stacked", {"solid_electrode": "false"}),
    ("권취 기본", "wound", {}),
    ("권취 dent", "wound", {"mode": "dent"}),
    ("권취 phase 2", "wound", {"phase": "2"}),
)


def battery_yaml(model, extra):
    src = {"stacked": "stacked/stacked_swell.yaml", "wound": "wound/wound_swell.yaml"}[model]
    t = open(os.path.join(REPO, "examples", "battery", "swell", src), encoding="utf-8").read()
    t = re.sub(r"^output:.*$", "output: bt", t, count=1, flags=re.M)
    for k, v in extra.items():
        pat = re.compile(r"^%s:.*$" % re.escape(k), re.M)
        t = pat.sub("%s: %s" % (k, v), t, count=1) if pat.search(t) else t + "\n%s: %s\n" % (k, v)
    return t


def setup(root, name, binary, bat_text, asm_ops, extra_base=True):
    d = os.path.join(root, name)
    os.makedirs(d)
    with open(os.path.join(d, "box.yaml"), "w", encoding="utf-8") as f:
        f.write(BOX)
    run(binary, d, "generate", "box", "box.yaml")
    if extra_base:
        p = os.path.join(d, "box.k")
        s = open(p, encoding="utf-8").read()
        assert s.count("*END") == 1
        with open(p, "w", encoding="utf-8") as f:
            f.write(s.replace("*END", EXTRA + "*END"))
    with open(os.path.join(d, "bat.yaml"), "w", encoding="utf-8") as f:
        f.write(bat_text)
    with open(os.path.join(d, "a.yaml"), "w", encoding="utf-8") as f:
        f.write("base_model: box.k\noutput: ba\noperations:\n  - type: battery\n    config: bat.yaml\n" + asm_ops)
    return d


def standalone(root, name, binary, bat_text):
    d = os.path.join(root, name + "_std")
    os.makedirs(d)
    with open(os.path.join(d, "b.yaml"), "w", encoding="utf-8") as f:
        f.write(bat_text)
    rc, out = run(binary, d, "battery", "b.yaml")
    ks = [f for f in os.listdir(d) if f.endswith(".k")]
    return (os.path.join(d, ks[0]) if rc == 0 and len(ks) == 1 else None), out


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = os.path.abspath(sys.argv[1])
    root = tempfile.mkdtemp(prefix="abid_")
    try:
        base_defs = None
        print("[A — 족마다 기존 모델의 최대값 위로]")
        for k, (name, model, extra) in enumerate(VARIANTS):
            text = battery_yaml(model, extra)
            std, sout = standalone(root, "v%d" % k, binary, text)
            if not check("%s — 단독 battery 덱을 짓는다" % name, std is not None, sout[-200:]):
                continue
            d = setup(root, "v%d" % k, binary, text, "")
            if base_defs is None:
                bl, _ = blocks_of(os.path.join(d, "box.k"))
                base_defs, _ = facts(bl)
            rc, out = run(binary, d, "assemble", "a.yaml")
            main_k = os.path.join(d, "ba.k")
            if not check("★%s — assemble rc 0" % name, rc == 0 and os.path.exists(main_k), out[-300:]):
                continue
            try:
                defs, refs, bdefs, brefs, incs = deck_facts(main_k)
            except DeckUnreadable as e:
                check("★%s — 얹은 덱의 카드를 칸대로 읽는다" % name, False, e)
                continue
            dup, dangling = integrity(defs, refs)
            check("★%s — 주 덱 + battery 덱에 겹친 번호가 없다(예전엔 절점 · 요소 · 섹션 · 재질 · 세트 · 곡선 …)" % name,
                  not dup, dup)
            check("★%s — 참조가 모두 정의된 번호를 가리킨다" % name, not dangling, dangling)
            try:
                sdefs, srefs = facts(blocks_of(std)[0])
            except DeckUnreadable as e:
                check("%s — 단독 battery 덱의 카드를 칸대로 읽는다" % name, False, e)
                continue
            off = base_offsets(base_defs)
            off = {f: (o if any(POOL.get(g, g) == f for g in sdefs) else 0) for f, o in off.items()}
            why = shifted_ok(sdefs, srefs, bdefs, brefs, off)
            check("%s — 얹은 battery = 단독 battery + 족마다 기존 최대값(정의 · 참조)" % name, not why, why)
            if len(incs) == 1:
                why = bytes_ok(std, os.path.join(d, incs[0]))
                check("%s — 줄 수가 같고 바뀐 글자는 번호 칸의 숫자 · 공백뿐" % name, not why, why)
                if k == 0:   # 문서(§43.1 · 2026-11-08 「지금은 그대로」) — battery 의 제어 카드도 주 덱의 것 옆에 실린다
                    terms = sum(1 for p in (main_k, os.path.join(d, incs[0])) for l in open(p, encoding="utf-8")
                                if l.upper().startswith("*CONTROL_TERMINATION"))
                    check("%s — battery 의 *CONTROL_TERMINATION 이 주 덱의 것과 함께 실린다(둘 — 문서 그대로 · 고르지 않는다)" % name,
                          terms == 2, terms)

        print("[E — 준 오프셋]")
        text = battery_yaml("stacked", {})
        std, _ = standalone(root, "e1", binary, text)
        d = setup(root, "e1", binary, text, "    node_id_offset: 1000000\n    elem_id_offset: 2000000\n")
        rc, out = run(binary, d, "assemble", "a.yaml")
        if check("★E-1 node_id_offset 1000000 · elem_id_offset 2000000 → rc 0", rc == 0, out[-300:]) and std:
            defs, refs, bdefs, brefs, _ = deck_facts(os.path.join(d, "ba.k"))
            sdefs, srefs = facts(blocks_of(std)[0])
            off = base_offsets(base_defs)
            off = {f: (o if any(POOL.get(g, g) == f for g in sdefs) else 0) for f, o in off.items()}
            off["node"], off["elem"] = 1000000, 2000000
            why = shifted_ok(sdefs, srefs, bdefs, brefs, off)
            dup, dangling = integrity(defs, refs)
            check("E-1   └ 절점 +1000000 · 요소 +2000000 · 나머지 족은 저절로 · 겹침 · 끊긴 참조 없음",
                  not why and not dup and not dangling, (why, dup, dangling))
        d = setup(root, "e2", binary, text, "    node_id_offset: 5\n")
        rc, out = run(binary, d, "assemble", "a.yaml")
        check("★E-2 node_id_offset 5(상자 최대 절점 아래로 걸친다) → rc 1 · node_id_offset 을 말한다 · 아무것도 쓰지 않는다",
              rc == 1 and "node_id_offset" in out and not [f for f in os.listdir(d) if f.startswith(("ba.", "bt_"))],
              (rc, out[-300:]))

        print("[I — use_include: false]")
        text = battery_yaml("stacked", {"mode": "dent"})
        d = setup(root, "i1", binary, text, "    use_include: false\n")
        rc, out = run(binary, d, "assemble", "a.yaml")
        main_k = os.path.join(d, "ba.k")
        if check("★I use_include: false → rc 0 · battery 덱 파일을 쓰지 않는다", rc == 0 and os.path.exists(main_k)
                 and not [f for f in os.listdir(d) if f.startswith("bt_")], (rc, out[-300:])):
            defs, refs, _, _, incs = deck_facts(main_k)
            dup, dangling = integrity(defs, refs)
            std, _ = standalone(root, "i1", binary, text)
            sdefs, _ = facts(blocks_of(std)[0])
            n_ok = len(defs.get("node", [])) == len(base_defs.get("node", [])) + len(sdefs.get("node", []))
            check("I   └ 주 덱에 *INCLUDE 가 없고 battery 카드가 펼쳐져 있다 · 겹침 · 끊긴 참조 없음",
                  not incs and n_ok and not dup and not dangling, (incs, n_ok, dup, dangling))

        print("[D — *INCLUDE_DYNAIN]")
        text = battery_yaml("stacked", {"phase": "2", "use_dynain": "true", "dynain_file": "p1.dynain"})
        d = setup(root, "d1", binary, text, "")
        rc, out = run(binary, d, "assemble", "a.yaml")
        check("★D phase 2 · use_dynain · dynain_file → rc 1 · INCLUDE_DYNAIN 을 말한다 · 아무것도 쓰지 않는다(옮기면 어긋난다)",
              rc == 1 and "INCLUDE_DYNAIN" in out and not [f for f in os.listdir(d) if f.startswith(("ba.", "bt_"))],
              (rc, out[-300:]))

        print("[L — battery 뒤의 op 이 내는 번호]")
        text = battery_yaml("stacked", {"mode": "dent"})
        d = setup(root, "l1", binary, text,
                  "  - type: contact\n    contacts:\n      - action: create\n        type: automatic_single_surface\n"
                  "        slave:\n          pid: 1\n        title: AfterBattery\n", extra_base=False)
        rc, out = run(binary, d, "assemble", "a.yaml")
        if check("★L battery 뒤 contact create → rc 0", rc == 0, out[-300:]):
            defs, refs, _, _, _ = deck_facts(os.path.join(d, "ba.k"))
            dup, dangling = integrity(defs, refs)
            check("★L   └ 새 접촉 · 세트 번호가 battery 의 것과 겹치지 않는다(예전엔 접촉 1 을 다시 냈다)", not dup and not dangling,
                  (dup, dangling))
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
