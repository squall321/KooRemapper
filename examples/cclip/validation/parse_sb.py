# 스프링백 결과 판정 — 초기응력만으로 팁이 자유높이(+δ_op)로 복원되는지 확인한다.
import json
import os
import re
import sys

VD = os.path.dirname(os.path.abspath(__file__))
c = json.load(open(os.path.join(VD, "report.json")))["clips"][0]
d_op = c["operating_deflection"]        # 0.15 = 자유높이 - 설치높이
h_inst = c["installed_height"]          # 0.50
h_free = c["free_height"]               # 0.65
TIP = {105, 106, 107, 108}
NUM = re.compile(r"[-+]?\d*\.?\d+[eE][-+]?\d+|[-+]?\d+\.\d+")


def find(n):
    for r, _, f in os.walk(VD):
        if n in f:
            return os.path.join(r, n)
    return None


nd = find("nodout")
if not nd:
    print("FAIL: nodout 없음 (실행 실패)")
    sys.exit(2)

# 변위 블록만(회전 블록 제외) tip z-disp / z-coor
states = {}
cur, is_disp = None, False
for ln in open(nd, errors="replace"):
    mt = re.search(r"at time\s+(\S+)", ln)
    if mt:
        cur = float(mt.group(1)); is_disp = False; continue
    if "x-disp" in ln:
        is_disp = True; continue
    if "x-rot" in ln:
        is_disp = False; continue
    if is_disp and cur is not None:
        m = re.match(r"\s*(\d+)\s+(.*)", ln)
        if m and int(m.group(1)) in TIP:
            v = [float(x) for x in NUM.findall(m.group(2))]
            if len(v) >= 12:
                states.setdefault(round(cur, 6), []).append((v[2], v[11]))  # z-disp, z-coor

if not states:
    print("FAIL: nodout에 tip 변위 상태 없음")
    sys.exit(2)

print("=" * 68)
print(" cclip 선응력 스프링백 — LS-DYNA 검증 (*INITIAL_STRESS_SHELL 부호·크기)")
print("=" * 68)
print(f" 설정: 발 고정, 외력 0, 초기응력만. 눌린 형상(z_tip={h_inst}) 에서 출발.")
print(f" 기대: 응력이 해방되며 팁이 +z로 복원 → z_tip → 자유높이 {h_free} (Δ=+{d_op})")
print("-" * 68)
print(f" {'time':>7} {'tip z-disp[mm]':>16} {'tip z-coord[mm]':>17}")
for t in sorted(states):
    dz = sum(a for a, _ in states[t]) / len(states[t])
    zc = sum(b for _, b in states[t]) / len(states[t])
    print(f" {t:7.3f} {dz:+16.5f} {zc:17.5f}")

t_e = max(states)
dz = sum(a for a, _ in states[t_e]) / len(states[t_e])
zc = sum(b for _, b in states[t_e]) / len(states[t_e])
print("-" * 68)
sign_ok = dz > 0
err = abs(dz - d_op) / d_op
print(f" 최종 스프링백:  Δz = {dz:+.5f} mm   (기대 +{d_op})   오차 {err*100:.1f}%")
print(f" 최종 팁 높이:   z  = {zc:.5f} mm   (자유높이 {h_free})")
print(f" [1] 부호(위로 복원): {'PASS' if sign_ok else 'FAIL — 팁이 아래로 움직임(응력 부호 반대)'}")
ok2 = err <= 0.15
print(f" [2] 크기(δ_op 복원, ±15%): {'PASS' if ok2 else 'REVIEW'}")
print("=" * 68)
ok = sign_ok and ok2
print(f" 판정: {'PASS — 초기응력이 눌림량 δ_op 를 정확히 인코딩(부호·크기 모두 검증)' if ok else 'REVIEW'}")
sys.exit(0 if ok else 1)
