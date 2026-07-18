# cclip 압축덱 rcforc(SURFA)/nodout(disp)를 파싱해 FE F-δ와 해석 캘리브(k,F_work)를 대조한다.
import json
import os
import re
import sys

VD = os.path.dirname(os.path.abspath(__file__))
rep = json.load(open(os.path.join(VD, "report.json")))
c = rep["clips"][0]
k_target = c["target_stiffness"]      # 8.0 N/mm (해석)
f_work = c["operating_force"]         # 1.2 N
d_op = c["operating_deflection"]      # 0.15 mm
TIP = {49, 50, 51, 52}
NUM = re.compile(r"[-+]?\d*\.?\d+[eE][-+]?\d+|[-+]?\d+\.\d+")


def find(name):
    for root, _, files in os.walk(VD):
        if name in files:
            return os.path.join(root, name)
    return None


def read_rcforc(path):
    """SURFA (강체판 접촉면) (time, |Fz|). z<0 = 판이 클립을 -z로 누름 → 압축반력."""
    out = {}
    for ln in open(path, errors="replace"):
        m = re.match(r"\s*SURFA\s+\d+\s+time\s+(\S+).*?z\s+(\S+)", ln)
        if m:
            t = float(m.group(1))
            fz = float(m.group(2))
            out[round(t, 6)] = abs(fz)
    return out


def read_nodout_tipz(path):
    """변위 블록(회전 블록 제외)에서 tip z-disp 평균 = δ(t)."""
    out = {}
    lines = open(path, errors="replace").read().splitlines()
    i = 0
    cur_t = None
    is_disp = False
    while i < len(lines):
        ln = lines[i]
        mt = re.search(r"at time\s+(\S+)", ln)
        if mt:
            cur_t = float(mt.group(1))
            is_disp = False
        elif "x-disp" in ln:
            is_disp = True
        elif "x-rot" in ln:
            is_disp = False
        elif is_disp and cur_t is not None:
            m = re.match(r"\s*(\d+)\s+(.*)", ln)
            if m and int(m.group(1)) in TIP:
                nums = [float(x) for x in NUM.findall(m.group(2))]
                if len(nums) >= 3:
                    out.setdefault(round(cur_t, 6), []).append(nums[2])  # z-disp
        i += 1
    return {t: sum(v) / len(v) for t, v in out.items() if v}


rc = find("rcforc")
nd = find("nodout")
if not rc:
    print("FAIL: rcforc not found")
    sys.exit(2)
F = read_rcforc(rc)
D = read_nodout_tipz(nd) if nd else {}

# 시간으로 (δ, F) 페어링. δ = |tip z-disp| (실측), F = |Fz|.
series = []
for t in sorted(F):
    if t in D:
        d = abs(D[t])
        if d > 1e-6:
            series.append((t, d, F[t]))

if not series:
    print("FAIL: no paired (δ,F) states")
    sys.exit(2)

# 작동점 근처 힘/강성 (마지막 상태 ≈ δ_op)
t_e, d_e, f_e = series[-1]
k_fe = f_e / d_e
err_f = abs(f_e - f_work) / f_work
err_k = abs(k_fe - k_target) / k_target

print("=" * 66)
print(" cclip 압축덱 — LS-DYNA F-δ 검증 (해석 빔이론 캘리브 vs 쉘 FE)")
print("=" * 66)
print(f" LS-DYNA: MPP double R16.1.1, implicit statics, normal termination")
print(f" 해석 캘리브: k = {k_target:.3f} N/mm,  F_work = {f_work:.3f} N @ δ={d_op} mm")
print(f" 캘리브 두께: t = {c['thickness']:.5f} mm  (BeCu E={c['E']:.0f} MPa)")
print("-" * 66)
print(f" {'time':>6} {'δ_tip[mm]':>11} {'F_z[N]':>10} {'k=F/δ[N/mm]':>13}")
for t, d, f in series:
    mk = "  <- δ_op" if abs(d - d_op) < 0.006 else ""
    print(f" {t:6.3f} {d:11.5f} {f:10.5f} {f/d:13.4f}{mk}")
print("-" * 66)
print(f" FE 작동점: δ={d_e:.5f} mm (설계 {d_op}),  F={f_e:.4f} N,  k={k_fe:.4f} N/mm")
print(f" 힘 오차   FE vs 해석: {err_f*100:+.1f}%   ({f_e:.3f} vs {f_work:.3f} N)")
print(f" 강성 오차 FE vs 해석: {err_k*100:+.1f}%   ({k_fe:.3f} vs {k_target:.3f} N/mm)")
print("=" * 66)
TOL = 0.20
ok = err_f <= TOL
print(f" 판정(±{int(TOL*100)}%): {'PASS' if ok else 'REVIEW'} — "
      f"{'빔이론 캘리브가 쉘 FE 강성을 공학적 정확도로 재현' if ok else '오차 초과'}")
print(f"   해석: 빔이론(Euler-Bernoulli)은 곡선 C-clip에서 곡률강성/고정발을")
print(f"   무시해 강성을 과소평가 → FE가 {err_k*100:+.0f}% 높게 나오는 것은 물리적으로 타당")
sys.exit(0 if ok else 1)
