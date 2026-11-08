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
  · 오프셋 = battery 번호가 기존 모델의 그 족 번호와 실제로 겹칠 때만 그 족 최대값(상자 + 모든 족을 겹치게 덧붙인 정의 — 파트는 겹치지
    않아 그대로), 최대값 위가 칸 상한을 넘으면 통째로 들어가는 빈자리 — battery 가 쓰지 않는 족 · 겹치지 않는 족은 0

무엇을 보나.
  A 적층 기본 · dent · bare · phase 2 · pouch 예압(INITIAL_STRESS_SHELL) · TSHELL, 권취 기본 · dent · phase 2 — 위 넷
  E-1 node_id_offset 1000000 · elem_id_offset 2000000 → 그 값   E-2 node_id_offset 5(상자 절점과 실제로 겹친다) → rc 1 · 아무것도
      쓰지 않는다
  B   (2026-11-08 · 6차 검토 G3 — 실제로 겹칠 때만 옮긴다) B-1 큰 번호 덱(절점 90000001~ · 요소 99990001 · 5000) → 옮기지 않고 rc 0 ·
      battery 덱이 단독 덱과 바이트까지 같다(예전엔 8칸 상한으로 rc 1) · B-2 겹치는데 최대값 위가 8칸을 넘는다 → 빈자리로 ·
      B-3 node_id_offset 5 · 큰 번호 덱(겹치지 않는다) → rc 0(예전엔 최대값 아래라며 rc 1) · B-4 battery 둘 → 뒤 덱이 앞 덱 위로
  I   use_include: false → battery 덱 파일 없음 · 주 덱에 *INCLUDE 없음 · 한 덱에서 위 판정
  D   phase 2 · use_dynain · dynain_file → rc 1(옮기면 그 dynain 의 번호와 어긋난다) · 아무것도 쓰지 않는다 · D-2 겹치지 않는 큰 번호
      덱이면 옮기지 않으니 받는다(2026-11-08)
  L   battery 뒤의 contact 가 낸 접촉 · 세트 번호도 battery 와 겹치지 않는다(뒤 op 의 번호 발급이 battery 덱을 센다)
  G   battery 앞의 boundary · rbe · load · contact · matswap 이 같은 실행에서 낸 세트 · 섹션 번호와도 겹치지 않는다(2026-11-08 전엔
      제 훑기로 낸 번호가 공용 커서에 없어 SID 1 · SECID 3 이 둘)

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

# 번호가 큰 기존 모델(6차 검토 G3 재현 bigid2) — battery 의 어느 족과도 겹치지 않는다(파트 · 섹션 · 재질 5000 · 절점 90000001~08 ·
# 요소 99990001)
BIG = """*KEYWORD
*PART
box
      5000      5000      5000
*SECTION_SOLID
      5000         1
*MAT_ELASTIC
      5000  7.85e-09  210000.0       0.3
*NODE
90000001        0.000000        0.000000        0.000000
90000002        1.000000        0.000000        0.000000
90000003        0.000000        1.000000        0.000000
90000004        1.000000        1.000000        0.000000
90000005        0.000000        0.000000        1.000000
90000006        1.000000        0.000000        1.000000
90000007        0.000000        1.000000        1.000000
90000008        1.000000        1.000000        1.000000
*ELEMENT_SOLID
99990001    50009000000190000002900000049000000390000005900000069000000890000007
*END
"""

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
        elif kw.startswith("*SECTION_") and title:   # 묶음마다 제목 줄 + 카드(셸은 Card 1 · 2)
            per = 3 if kw.startswith("*SECTION_SHELL") else 2
            for q in range(0, len(ls), per):
                d("section", num(ls[q + 1], 0, 10))
        elif kw == "*SECTION_SHELL":
            for q in range(0, len(ls), 2):
                d("section", num(ls[q], 0, 10))
        elif kw.startswith("*SECTION_"):
            for l in ls:
                d("section", num(l, 0, 10))
        elif kw == "*HOURGLASS":
            for l in ls:
                d("hourglass", num(l, 0, 10))
        elif kw == "*HOURGLASS_TITLE":
            for q in range(1, len(ls), 2):
                d("hourglass", num(ls[q], 0, 10))
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
            c0 = 1 if (kw.endswith("_ID") or kw.endswith("_TITLE")) else 0   # ID 카드가 없는 접촉(offset tied 의 _OFFSET)은 Card 1 부터
            if c0:
                d("contact", num(ls[0], 0, 10))
            c1 = ls[c0]
            for idc, tc in ((0, 20), (10, 30)):
                t = num(c1, tc, tc + 10)
                if t != 5:
                    r(STYP[t], num(c1, idc, idc + 10))
            if len(ls) > c0 + 3:   # Card A 의 LCIDAB — Card B(PENMAX …)에는 번호 칸이 없다(2026-11-08 · P2 — 예전엔 그 21~30열을 곡선으로 셌다)
                r("curve", num(ls[c0 + 3], 20, 30))
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


CAP8, CAP10 = 99999999, 2 ** 31 - 1   # 절점 · 요소 · 파트는 요소 줄의 8칸, 나머지는 10칸(int)


def place(battery, taken, cap):
    """battery 번호를 taken 위에 놓을 자리 — C++(`bat::placeBatteryIds`)와 따로 쓴 같은 규칙. 겹치지 않으면 0, 겹치면 기존
    최대값(그 위로), 그게 상한을 넘으면 battery 범위가 통째로 들어가는 가장 낮은 빈자리(위로만). 못 놓으면 None."""
    b, t = sorted(set(battery)), sorted(set(taken))
    if not b or not set(b) & set(t):
        return 0
    if b[-1] + t[-1] <= cap:
        return t[-1]
    spans = []
    for v in t:
        if spans and v == spans[-1][1] + 1:
            spans[-1][1] = v
        else:
            spans.append([v, v])
    width = b[-1] - b[0]
    for k, (_lo, hi) in enumerate(spans):
        start = max(hi + 1, b[0] + 1)
        room = spans[k + 1][0] - 1 if k + 1 < len(spans) else cap
        if start + width <= min(room, cap):
            return start - b[0]
    return None


def pooled(defs):
    out = {}
    for f, v in defs.items():
        out.setdefault(POOL.get(f, f), set()).update(v)
    return out


def expected_offsets(base_defs, std_defs):
    """족마다 battery(단독 덱) 번호가 기존(base) 번호와 **실제로** 겹칠 때만 옮긴다(2026-11-08 · 6차 검토 G3)."""
    b, s = pooled(base_defs), pooled(std_defs)
    return {f: place(v, b.get(f, ()), CAP8 if f in ("node", "elem", "part") else CAP10) for f, v in s.items()}


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
        print("[A — 겹치는 족만 기존 모델의 최대값 위로]")
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
            off = expected_offsets(base_defs, sdefs)
            why = shifted_ok(sdefs, srefs, bdefs, brefs, off)
            check("%s — 얹은 battery = 단독 battery + 겹치는 족만 기존 최대값(정의 · 참조 · 안 겹치는 파트는 그대로)" % name,
                  not why, (why, off))
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
            off = expected_offsets(base_defs, sdefs)
            off["node"], off["elem"] = 1000000, 2000000
            why = shifted_ok(sdefs, srefs, bdefs, brefs, off)
            dup, dangling = integrity(defs, refs)
            check("E-1   └ 절점 +1000000 · 요소 +2000000 · 나머지 족은 저절로 · 겹침 · 끊긴 참조 없음",
                  not why and not dup and not dangling, (why, dup, dangling))
        d = setup(root, "e2", binary, text, "    node_id_offset: 5\n")
        rc, out = run(binary, d, "assemble", "a.yaml")
        check("★E-2 node_id_offset 5(battery 절점 6~ 이 상자 절점과 실제로 겹친다) → rc 1 · node_id_offset 을 말한다 · 아무것도 쓰지 않는다",
              rc == 1 and "node_id_offset" in out and "겹친다" in out
              and not [f for f in os.listdir(d) if f.startswith(("ba.", "bt_"))], (rc, out[-300:]))

        print("[B — 겹치지 않는 큰 번호 덱 · 빈자리 · 겹치지 않는 준 오프셋]")
        # 예전엔 족마다 기존 최대값만큼 늘 옮겨, 범위가 겹치지 않아도 8칸 상한을 넘었다(6차 검토 G3 — 절점 90000001~08 · 요소
        # 99990001 인 덱이 rc 1, 운영은 rc 0 에 겹침 없음). 준 오프셋도 기존 최대값 아래로 걸치면 겹치지 않아도 거절했다
        text = battery_yaml("stacked", {"mode": "dent"})
        std, _ = standalone(root, "b1", binary, text)
        sdefs, srefs = facts(blocks_of(std)[0])
        for tag, ops, want in (("B-1 큰 번호 덱", "", {}),
                               ("B-3 node_id_offset 5 · 큰 번호 덱(겹치지 않는다)", "    node_id_offset: 5\n", {"node": 5})):
            d = setup(root, tag[:3], binary, text, ops, extra_base=False)
            with open(os.path.join(d, "box.k"), "w", encoding="utf-8") as f:
                f.write(BIG)
            rc, out = run(binary, d, "assemble", "a.yaml")
            if not check("★%s → rc 0(예전엔 8칸 상한 · 최대값 아래로 걸친다며 rc 1)" % tag, rc == 0, out[-300:]):
                continue
            defs, refs, bdefs, brefs, incs = deck_facts(os.path.join(d, "ba.k"))
            dup, dangling = integrity(defs, refs)
            off = {f: 0 for f in pooled(sdefs)}
            off.update(want)
            why = shifted_ok(sdefs, srefs, bdefs, brefs, off)
            check("★%s   └ 겹치지 않는 족은 옮기지 않는다(%s) · 겹침 · 끊긴 참조 없음" % (tag, want or "전부 그대로"),
                  not why and not dup and not dangling, (why, dup, dangling))
            if not want and len(incs) == 1:
                check("%s   └ 얹은 battery 덱 = 단독 battery 덱(바이트)" % tag,
                      open(std, "rb").read() == open(os.path.join(d, incs[0]), "rb").read())
        # B-2 겹치는데 최대값 위가 8칸 상한을 넘는다 — 상자(절점 1~198) + 쓰지 않는 절점 99999990 → 빈자리(199~)로
        d = setup(root, "b2", binary, text, "", extra_base=False)
        p = os.path.join(d, "box.k")
        body = open(p, encoding="utf-8").read()
        with open(p, "w", encoding="utf-8") as f:
            f.write(body.replace("*END", "*NODE\n99999990             0.0             0.0             0.0\n*END"))
        rc, out = run(binary, d, "assemble", "a.yaml")
        if check("★B-2 상자 + 절점 99999990 → rc 0(최대값 위는 8칸을 넘으니 빈자리로 · 예전엔 rc 1)", rc == 0, out[-300:]):
            bl, _ = blocks_of(p)
            bdefs0, _ = facts(bl)
            defs, refs, bdefs, brefs, _ = deck_facts(os.path.join(d, "ba.k"))
            dup, dangling = integrity(defs, refs)
            off = expected_offsets(bdefs0, sdefs)
            why = shifted_ok(sdefs, srefs, bdefs, brefs, off)
            check("★B-2   └ battery 절점이 상자 절점 바로 위 빈자리(+198) · 겹침 · 끊긴 참조 없음",
                  off.get("node") == 198 and not why and not dup and not dangling, (off.get("node"), why, dup, dangling))
        # B-4 battery 둘(큰 번호 덱) — 앞 battery 를 옮기지 않았으니 뒤 battery 는 그것과 겹친다 → 그 위로
        d = setup(root, "b4", binary, text, "", extra_base=False)
        with open(os.path.join(d, "box.k"), "w", encoding="utf-8") as f:
            f.write(BIG)
        with open(os.path.join(d, "a.yaml"), "w", encoding="utf-8") as f:
            f.write("base_model: box.k\noutput: ba\noperations:\n  - type: battery\n    config: bat.yaml\n"
                    "  - type: battery\n    config: bat.yaml\n    output: bt2\n")
        rc, out = run(binary, d, "assemble", "a.yaml")
        if check("★B-4 큰 번호 덱에 battery 둘 → rc 0", rc == 0, out[-300:]):
            defs, refs, _, _, incs = deck_facts(os.path.join(d, "ba.k"))
            dup, dangling = integrity(defs, refs)
            check("★B-4   └ 두 battery 덱이 서로 겹치지 않는다(뒤 덱이 앞 덱 위로) · 끊긴 참조 없음",
                  len(incs) == 2 and not dup and not dangling, (incs, dup, dangling))

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
        # D-2 겹치지 않는 큰 번호 덱이면 옮기지 않으니 그 dynain 의 번호가 그대로 맞는다 → 받는다(2026-11-08 · G3 — 예전엔 늘 옮겨 거절)
        d = setup(root, "d2", binary, text, "", extra_base=False)
        with open(os.path.join(d, "box.k"), "w", encoding="utf-8") as f:
            f.write(BIG)
        rc, out = run(binary, d, "assemble", "a.yaml")
        incs = blocks_of(os.path.join(d, "ba.k"))[1] if rc == 0 else []
        dyn = [l for l in open(os.path.join(d, incs[0]), encoding="utf-8")] if len(incs) == 1 else []
        check("★D-2 같은 battery 를 큰 번호 덱에 → rc 0 · 옮기지 않아 *INCLUDE_DYNAIN p1.dynain 이 그대로 실린다(예전엔 rc 1)",
              rc == 0 and any(l.upper().startswith("*INCLUDE_DYNAIN") for l in dyn) and any(l.strip() == "p1.dynain" for l in dyn),
              (rc, incs, out[-300:]))

        print("[G — battery 앞의 op 이 같은 실행에서 낸 번호]")
        # 앞 op 이 제 훑기로 낸 번호(boundary · rbe 의 SET_NODE · load 의 SET_SEGMENT · contact 의 세트 · matswap 의 SECID)가 공용
        # 커서에 없어 battery 가 그 위로 옮기지 않았다(2026-11-08 · 6차 검토 G1 — 실측: box + boundary 뒤 battery 의 SID 1 이 둘 ·
        # matswap 뒤 SECID 3 이 둘)
        text = battery_yaml("stacked", {"mode": "dent"})
        before_ops = (
            ("boundary", "  - type: boundary\n    boundaries:\n      - part: 1\n        dof: xyz\n"
                         "        direction: [0, 0, -1]\n        select: direction\n        angle: 45.0\n"),
            ("rbe(rbe2 spider)", "  - type: rbe\n    rbe:\n      - part: 1\n        select: direction\n"
                                 "        direction: [0, 0, 1]\n        angle: 45.0\n        type: rbe2\n        mode: spider\n"),
            ("load", "  - type: load\n    loads:\n      - part: 1\n        mode: pressure\n        value: 1.0\n"
                     "        direction: [0, 0, 1]\n        select: direction\n        angle: 45.0\n"
                     "        curve:\n          - [0.0, 0.0]\n          - [0.001, 1.0]\n"),
            ("contact", "  - type: contact\n    contacts:\n      - action: create\n        type: automatic_single_surface\n"
                        "        slave:\n          pid: 1\n        title: BeforeBattery\n"),
            ("matswap(two_cubes + rubber)", None))
        for k, (name, op_text) in enumerate(before_ops):
            if op_text is None:   # matswap — 예제 덱 둘(PID 1 · 2)에 번들을 바꿔 넣는다
                d = os.path.join(root, "g%d" % k)
                os.makedirs(d)
                for f in ("two_cubes.k", "rubber.k"):
                    shutil.copyfile(os.path.join(REPO, "examples", "matswap", f), os.path.join(d, f))
                with open(os.path.join(d, "bat.yaml"), "w", encoding="utf-8") as f:
                    f.write(text)
                with open(os.path.join(d, "a.yaml"), "w", encoding="utf-8") as f:
                    f.write("base_model: two_cubes.k\noutput: ba\noperations:\n  - type: matswap\n    bundle: rubber.k\n"
                            "    pid: 1\n  - type: battery\n    config: bat.yaml\n")
            else:
                d = setup(root, "g%d" % k, binary, text, "", extra_base=False)
                with open(os.path.join(d, "a.yaml"), "w", encoding="utf-8") as f:
                    f.write("base_model: box.k\noutput: ba\noperations:\n" + op_text + "  - type: battery\n    config: bat.yaml\n")
            rc, out = run(binary, d, "assemble", "a.yaml")
            if not check("★G %s 뒤 battery → rc 0" % name, rc == 0, out[-300:]):
                continue
            try:
                defs, refs, _, _, _ = deck_facts(os.path.join(d, "ba.k"))
            except DeckUnreadable as e:
                check("★G %s   └ 덱을 칸대로 읽는다" % name, False, e)
                continue
            dup, dangling = integrity(defs, refs)
            if op_text is None:
                # two_cubes.k 는 8칸 덱에 10칸 번호를 쓴 예제다(리더는 토큰으로 읽는다) — 이 칸 표로는 절점 · 요소 · 파트 칸을 읽지
                # 못하니 번호 족(섹션 · 재질 · 모래시계 · 세트 · 곡선)만 본다
                fams = {"section", "mat", "hourglass", "tmat", "curve", "contact"} | set(SET_KIND.values())
                dup = {f: v for f, v in dup.items() if f in fams}
                dangling = [x for x in dangling if x[0] in fams]
            check("★G %s   └ 앞 op 이 낸 세트 · 섹션 번호와 battery 의 것이 겹치지 않는다 · 끊긴 참조 없음" % name,
                  not dup and not dangling, (dup, dangling))

        # 제 훑기로 낸 세트가 공용 커서에도 오른다 — 뒤 op 이 커서로 같은 종류의 세트를 내도 겹치지 않는다(실측: load 의 SET_SEGMENT 1
        # 뒤 offset tied 셸 층이 커서 0 에서 SET_SEGMENT 1 을 다시 냈다 · 2026-11-08 · G1 「allocator 마다 커서를 올린다」)
        d = setup(root, "g_cursor", binary, text, "", extra_base=False)
        with open(os.path.join(d, "a.yaml"), "w", encoding="utf-8") as f:
            f.write("base_model: box.k\noutput: ba\nmaterial:\n  E: 210000\n  nu: 0.3\noperations:\n" + before_ops[2][1] +
                    "  - type: offset\n    source_pid: 1\n    element_type: shell\n    thickness: 1.0\n    num_layers: 1\n"
                    "    offset_direction: +z\n    connection_mode: tied\n    new_pid: 10\n    material_card: |\n"
                    "      *MAT_ELASTIC\n      $#     mid        ro         e        pr\n"
                    "           @MID@  7.85E-09  2.10E+05       0.3\n")
        rc, out = run(binary, d, "assemble", "a.yaml")
        if check("★G 커서 — load 뒤 offset(element_type: shell · tied) → rc 0", rc == 0, out[-300:]):
            defs, refs, _, _, _ = deck_facts(os.path.join(d, "ba.k"))
            dup, dangling = integrity(defs, refs)
            check("★G 커서   └ load 의 SET_SEGMENT 와 offset 이 커서로 낸 SET_SEGMENT 가 겹치지 않는다(예전엔 둘 다 1)",
                  not dup and not dangling and len(defs.get("set_segment", [])) == 3, (dup, dangling, defs.get("set_segment")))

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
