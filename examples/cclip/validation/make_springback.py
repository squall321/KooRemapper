# analytic 선응력 클립에서 클립만 추출해 발고정+초기응력 스프링백 덱을 생성한다.
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "clip_board_cclip.k"
OUT = sys.argv[2] if len(sys.argv) > 2 else "springback.k"
FOOT = [57, 58, 59, 60, 61, 62, 63, 64]     # 발(z=0) — 고정
TIP = [105, 106, 107, 108]                  # 팁(z=0.5) — 스프링백 관측

lines = open(SRC).read().splitlines()

# 키워드 블록 분해
blocks = []       # (keyword, [raw lines])
kw = None
buf = []
for ln in lines:
    if ln.strip().startswith("*"):
        if kw is not None:
            blocks.append((kw, buf))
        kw = ln.strip().upper()
        buf = []
    else:
        buf.append(ln)
if kw is not None:
    blocks.append((kw, buf))

# 클립 노드 = 요소가 참조하는 노드
elem_lines = []
for k, b in blocks:
    if k.startswith("*ELEMENT_SHELL"):
        elem_lines += b
clip_nids = set()
for ln in elem_lines:
    if ln.strip() and not ln.strip().startswith("$"):
        try:
            clip_nids.update(int(ln[c:c + 8]) for c in range(16, 48, 8))
        except ValueError:
            pass

out = ["*KEYWORD", "*TITLE", "cclip prestress springback (foot fixed, initial-stress relax)"]

# NODE (클립만), ELEMENT/PART/SECTION/MAT/INITIAL_STRESS 는 원문 verbatim
for k, b in blocks:
    if k.startswith("*NODE"):
        out.append("*NODE")
        for ln in b:
            if not ln.strip() or ln.strip().startswith("$"):
                continue
            try:
                nid = int(ln[0:8])
            except ValueError:
                continue
            if nid in clip_nids:
                out.append(ln)
    elif k.startswith(("*ELEMENT_SHELL", "*PART", "*SECTION_SHELL",
                       "*MAT_", "*INITIAL_STRESS_SHELL")):
        out.append(k)
        out += b

# 발 고정
out += ["*SET_NODE_LIST_TITLE", "CCLIP_FOOT", "%10d" % 1,
        "".join("%10d" % n for n in FOOT)]
out += ["*BOUNDARY_SPC_SET", "%10d%10d%10d%10d%10d%10d%10d%10d" % (1, 0, 1, 1, 1, 1, 1, 1)]

# 팁 관측
out += ["*SET_NODE_LIST_TITLE", "CCLIP_TIP", "%10d" % 2,
        "".join("%10d" % n for n in TIP)]
out += ["*DATABASE_HISTORY_NODE_SET", "%10d" % 2]

# implicit 정적 — 초기응력 완화로 평형(스프링백) 탐색
out += [
    "*CONTROL_IMPLICIT_GENERAL", "%10d%10.3f" % (1, 0.1),
    "*CONTROL_IMPLICIT_SOLUTION", "%10d%10d%10d%10.4f%10.4f" % (12, 50, 20, 0.0005, 0.005),
    "*CONTROL_IMPLICIT_AUTO", "%10d%10d%10d%10.1f%10.1f" % (1, 11, 5, 0.0, 0.0),
    "*CONTROL_TERMINATION", "%10.1f" % 1.0,
    "*DATABASE_NODOUT", "%10.4f%10d" % (0.05, 0),
    "*DATABASE_GLSTAT", "%10.4f%10d" % (0.05, 0),
    "*DATABASE_ELOUT", "%10.4f%10d" % (0.05, 0),
    "*END",
]
open(OUT, "w").write("\n".join(out) + "\n")
print(f"wrote {OUT}: {len(clip_nids)} clip nodes, foot={FOOT}, tip={TIP}")
