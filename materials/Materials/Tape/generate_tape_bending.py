#!/usr/bin/env python3
"""
Tape Bending (Cantilever) Model Generator for LS-DYNA
======================================================
3-layer cantilever beam: Al (10μm) / Tape (30μm) / Al (10μm)
Fixed at x=0, half-sine Z-force at x=Lx (free end).

Demonstrates constrained layer damping:
  - Phase difference between top/bottom Al
  - Energy dissipation in viscoelastic tape
  - Effect of G0, GI, BETA on damping

Unit system: mm, s, ton → Force=N, Stress=MPa
"""

import math
import os
import argparse
import itertools

# ============================================================
# Geometry
# ============================================================
NX = 20          # elements along beam length
NY = 3           # elements along beam width
DX = 0.1         # mm → beam length = 2.0 mm
DY = 0.1         # mm → beam width  = 0.3 mm

T_BOT_AL = 0.010   # 10 μm
T_TAPE   = 0.030   # 30 μm
T_TOP_AL = 0.010   # 10 μm

LX = NX * DX       # 2.0 mm
LY = NY * DY       # 0.3 mm

Z_LEVELS = [0.0, T_BOT_AL, T_BOT_AL + T_TAPE, T_BOT_AL + T_TAPE + T_TOP_AL]

# ============================================================
# Default materials
# ============================================================
AL_RO = 2.7e-9
AL_E  = 70000.0
AL_NU = 0.33

TAPE_RO   = 1.1e-9
TAPE_BULK = 2000.0

# ============================================================
# Loading defaults
# ============================================================
F_MAX    = 1.0e-4    # N peak force (0.1 mN)
T_LOAD   = 0.0005    # s (0.5 ms half-sine)
T_END    = 0.003     # s (3 ms total — see free vibration/damping)
N_CURVE  = 51
D3PLOT_DT = 2.0e-5   # s (20 μs → 150 frames)


def node_id(i, j, k):
    return k * (NX + 1) * (NY + 1) + j * (NX + 1) + i + 1


def generate_nodes():
    lines = ["*NODE"]
    for k in range(4):
        z = Z_LEVELS[k]
        for j in range(NY + 1):
            y = j * DY
            for i in range(NX + 1):
                x = i * DX
                nid = node_id(i, j, k)
                lines.append(f"{nid:8d}{x:16.8e}{y:16.8e}{z:16.8e}       0       0")
    return "\n".join(lines)


def generate_elements():
    lines = ["*ELEMENT_SOLID"]
    eid = 0
    for k in range(3):
        pid = k + 1
        for j in range(NY):
            for i in range(NX):
                eid += 1
                n1 = node_id(i,   j,   k)
                n2 = node_id(i+1, j,   k)
                n3 = node_id(i+1, j+1, k)
                n4 = node_id(i,   j+1, k)
                n5 = node_id(i,   j,   k+1)
                n6 = node_id(i+1, j,   k+1)
                n7 = node_id(i+1, j+1, k+1)
                n8 = node_id(i,   j+1, k+1)
                lines.append(
                    f"{eid:8d}{pid:8d}{n1:8d}{n2:8d}{n3:8d}{n4:8d}"
                    f"{n5:8d}{n6:8d}{n7:8d}{n8:8d}"
                )
    return "\n".join(lines)


def generate_fixed_end_nodeset():
    """Node set SID=2: all nodes at x=0 (fixed end)."""
    lines = [
        "*SET_NODE_LIST_TITLE", "Fixed end (x=0)",
        "$      SID       DA1       DA2       DA3       DA4    SOLVER",
        f"{'2':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'MECH':>10s}",
    ]
    row = []
    for k in range(4):
        for j in range(NY + 1):
            row.append(node_id(0, j, k))
            if len(row) == 8:
                lines.append("".join(f"{n:10d}" for n in row))
                row = []
    if row:
        lines.append("".join(f"{n:10d}" for n in row) + "".join(f"{'0':>10s}" for _ in range(8 - len(row))))
    return "\n".join(lines)


def generate_tip_load(f_max):
    """Uniform Z-force on all free-end nodes. Force baked into curve."""
    lines = []

    # Collect ALL free-end nodes (i=NX, all j, all k)
    tip_nodes = []
    for k in range(4):
        for j in range(NY + 1):
            tip_nodes.append(node_id(NX, j, k))

    n_tip = len(tip_nodes)
    force_per_node = f_max / n_tip

    # Node set SID=10
    lines.append("*SET_NODE_LIST_TITLE")
    lines.append("Tip nodes (free end)")
    lines.append("$      SID       DA1       DA2       DA3       DA4    SOLVER")
    lines.append(f"{'10':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'MECH':>10s}")
    row = []
    for n in tip_nodes:
        row.append(n)
        if len(row) == 8:
            lines.append("".join(f"{nd:10d}" for nd in row))
            row = []
    if row:
        lines.append("".join(f"{nd:10d}" for nd in row) +
                      "".join(f"{'0':>10s}" for _ in range(8 - len(row))))

    # Load curve LCID=1: half-sine with force_per_node baked in (negative Z)
    lines.append("*DEFINE_CURVE_TITLE")
    lines.append("Half-sine bending load")
    lines.append("$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP     LCINT")
    lines.append(f"{'1':>10s}{'0':>10s}{'1.0':>10s}{'1.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0':>10s}{'0':>10s}")
    for n in range(N_CURVE):
        t = n * T_LOAD / (N_CURVE - 1)
        v = -force_per_node * math.sin(math.pi * t / T_LOAD)
        lines.append(f"{t:20.10e}{v:20.10e}")
    lines.append(f"{T_END:20.10e}{0.0:20.10e}")

    # LOAD_NODE_SET with SF=1.0 (all magnitude in curve)
    lines.append("*LOAD_NODE_SET")
    lines.append("$     NSID       DOF      LCID        SF       CID")
    lines.append(f"{'10':>10s}{'3':>10s}{'1':>10s}{'1.0':>10s}{'0':>10s}")

    return "\n".join(lines)


def generate_common(title="Tape Bending Test"):
    return f"""$
*KEYWORD
*TITLE
{title}
$
*CONTROL_TERMINATION
$   ENDTIM    ENDCYC     DTMIN    ENDENG    ENDMAS      NOSOL
{T_END:10.4e}         0       0.0       0.0     1.E+8         0
$
*CONTROL_TIMESTEP
       0.0       0.9         0       0.0       0.0         0         0         0
$
*CONTROL_ENERGY
         2         2         2         1
$
*CONTROL_HOURGLASS
         6    0.1000
$
*DATABASE_GLSTAT
{D3PLOT_DT:10.4e}
*DATABASE_MATSUM
{D3PLOT_DT:10.4e}
*DATABASE_NODOUT
{D3PLOT_DT:10.4e}
*DATABASE_ELOUT
{D3PLOT_DT:10.4e}
*DATABASE_BINARY_D3PLOT
{D3PLOT_DT:10.4e}         0         0         0         0
$
*DATABASE_EXTENT_BINARY
         0         0         3         1         1         1         1         1
         0         0         0         1         1         1         2         1
         8         0       1.0         0         0         0  ALL       ALL
$
*SECTION_SOLID_TITLE
Solid section
         1         1         0
$
*PART
Bottom Aluminum
         1         1         1         0         0         0         0         0
*PART
Tape Layer
         2         1         2         0         0         0         0         0
*PART
Top Aluminum
         3         1         1         0         0         0         0         0
$
*MAT_ELASTIC
$      MID        RO         E        PR
         1{AL_RO:10.3e}{AL_E:10.1f}{AL_NU:10.4f}       0.0       0.0       0.0
$"""


def mat_viscoelastic(mid, ro, bulk, g0, gi, beta):
    return f"""$
*MAT_VISCOELASTIC
$      MID        RO      BULK        G0        GI      BETA
{mid:10d}{ro:10.3e}{bulk:10.1f}{g0:10.4f}{gi:10.4f}{beta:10.1f}
$"""


def mat_elastic_tape(mid, ro, e_val, nu):
    return f"""$
*MAT_ELASTIC
$      MID        RO         E        PR
{mid:10d}{ro:10.3e}{e_val:10.4f}{nu:10.4f}       0.0       0.0       0.0
$"""


def write_kfile(filepath, mat_section, f_max, title="Tape Bending Test"):
    with open(filepath, "w") as f:
        f.write(generate_common(title))
        f.write("\n")
        f.write(mat_section)
        f.write("\n")
        f.write("*BOUNDARY_SPC_SET\n")
        f.write("         2         0         1         1         1         0         0         0\n")
        f.write("$\n")
        f.write(generate_nodes())
        f.write("\n")
        f.write(generate_elements())
        f.write("\n")
        f.write(generate_fixed_end_nodeset())
        f.write("\n")
        f.write(generate_tip_load(f_max))
        f.write("\n*END\n")


def generate_doe(outdir, f_max):
    """Generate full DOE matrix."""
    os.makedirs(outdir, exist_ok=True)

    cases = []

    # === 1. Elastic baseline ===
    e_equil = 3 * 0.01  # 0.03 MPa (equilibrium)
    name = "elastic_equil"
    d = os.path.join(outdir, name)
    os.makedirs(d, exist_ok=True)
    mat = mat_elastic_tape(2, TAPE_RO, e_equil, 0.499)
    write_kfile(os.path.join(d, "main.k"), mat, f_max, f"Bending Elastic E={e_equil:.3f}")
    cases.append((name, f"Elastic E={e_equil:.3f} MPa"))

    # === 2. Stiff elastic (same as G0 instantaneous) ===
    e_inst = 3 * 0.3  # 0.9 MPa
    name = "elastic_stiff"
    d = os.path.join(outdir, name)
    os.makedirs(d, exist_ok=True)
    mat = mat_elastic_tape(2, TAPE_RO, e_inst, 0.45)
    write_kfile(os.path.join(d, "main.k"), mat, f_max, f"Bending Elastic E={e_inst:.3f}")
    cases.append((name, f"Elastic E={e_inst:.3f} MPa (stiff)"))

    # === 3. Viscoelastic baseline ===
    name = "visco_baseline"
    d = os.path.join(outdir, name)
    os.makedirs(d, exist_ok=True)
    mat = mat_viscoelastic(2, TAPE_RO, TAPE_BULK, 0.3, 0.01, 500.0)
    write_kfile(os.path.join(d, "main.k"), mat, f_max, "Bending Visco G0=0.3 GI=0.01 B=500")
    cases.append((name, "Visco baseline: G0=0.3, GI=0.01, BETA=500"))

    # === 4. G0/GI ratio study (fix BETA=500) ===
    g0_gi_combos = [
        (0.3,  0.25,  "ratio_1.2x"),    # G0/GI=1.2  (거의 탄성)
        (0.3,  0.1,   "ratio_3x"),       # G0/GI=3
        (0.3,  0.01,  "ratio_30x"),      # G0/GI=30   (baseline)
        (0.3,  0.001, "ratio_300x"),     # G0/GI=300  (극한 감쇠)
        (3.0,  0.1,   "ratio_30x_highG"),# G0/GI=30 but 10x stiffer
    ]
    for g0, gi, tag in g0_gi_combos:
        name = f"visco_{tag}"
        d = os.path.join(outdir, name)
        os.makedirs(d, exist_ok=True)
        mat = mat_viscoelastic(2, TAPE_RO, TAPE_BULK, g0, gi, 500.0)
        write_kfile(os.path.join(d, "main.k"), mat, f_max,
                    f"Bending G0={g0} GI={gi} B=500 (ratio={g0/gi:.0f}x)")
        cases.append((name, f"G0={g0}, GI={gi}, BETA=500 (ratio={g0/gi:.0f}x)"))

    # === 5. BETA study (fix G0=0.3, GI=0.01) ===
    betas = [50, 200, 500, 2000, 10000]
    for beta in betas:
        tau_ms = 1.0 / beta * 1000
        name = f"visco_beta_{beta}"
        d = os.path.join(outdir, name)
        os.makedirs(d, exist_ok=True)
        mat = mat_viscoelastic(2, TAPE_RO, TAPE_BULK, 0.3, 0.01, float(beta))
        write_kfile(os.path.join(d, "main.k"), mat, f_max,
                    f"Bending G0=0.3 GI=0.01 B={beta} (tau={tau_ms:.1f}ms)")
        cases.append((name, f"G0=0.3, GI=0.01, BETA={beta} (tau={tau_ms:.1f}ms)"))

    # === 6. Realistic tape comparison (3 types) ===
    realistic_tapes = [
        ("soft_acrylic",    1.1e-9, 2000.0, 1.0,  0.01,  200.0, "Soft Acrylic PSA (VHB)"),
        ("stiff_pu",        1.2e-9, 2500.0, 5.0,  0.1,   500.0, "Stiff PU Structural"),
        ("ultra_damping",   1.3e-9, 1500.0, 3.0,  0.003, 100.0, "Ultra-Damping Butyl"),
    ]
    for tag, ro, bulk, g0, gi, beta, desc in realistic_tapes:
        tau_ms = 1.0 / beta * 1000
        name = f"tape_{tag}"
        d = os.path.join(outdir, name)
        os.makedirs(d, exist_ok=True)
        mat = mat_viscoelastic(2, ro, bulk, g0, gi, beta)
        write_kfile(os.path.join(d, "main.k"), mat, f_max,
                    f"{desc}: G0={g0} GI={gi} B={beta}")
        cases.append((name, f"{desc}: G0={g0}, GI={gi}, BETA={beta} (tau={tau_ms:.1f}ms)"))

    # Elastic equivalents for the 3 tapes (using their G0 as stiff elastic)
    for tag, ro, bulk, g0, gi, beta, desc in realistic_tapes:
        e_equil_tape = 3.0 * gi
        name = f"tape_{tag}_elastic"
        d = os.path.join(outdir, name)
        os.makedirs(d, exist_ok=True)
        mat = mat_elastic_tape(2, ro, e_equil_tape, 0.499)
        write_kfile(os.path.join(d, "main.k"), mat, f_max,
                    f"{desc} Elastic E={e_equil_tape:.4f}")
        cases.append((name, f"{desc} Elastic: E={e_equil_tape:.4f} MPa (equil)"))

    # Write case list
    with open(os.path.join(outdir, "cases.txt"), "w") as f:
        f.write("# Bending DOE Case List\n")
        f.write(f"# Force: {f_max} N half-sine, {T_LOAD*1000:.1f} ms\n")
        f.write(f"# Beam: {LX}x{LY}mm, layers {T_BOT_AL*1000:.0f}/{T_TAPE*1000:.0f}/{T_TOP_AL*1000:.0f} um\n")
        f.write(f"# Elements: {NX*NY*3}, Nodes: {(NX+1)*(NY+1)*4}\n\n")
        for name, desc in cases:
            f.write(f"{name:30s}  {desc}\n")

    return cases


def main():
    parser = argparse.ArgumentParser(description="Generate tape bending DOE")
    parser.add_argument("--outdir", default="/data/tape_study/bending_doe",
                        help="Output directory for DOE cases")
    parser.add_argument("--force", type=float, default=F_MAX,
                        help="Peak tip force (N)")
    args = parser.parse_args()

    print("Tape Bending DOE Generator")
    print(f"  Beam: {LX}x{LY} mm, layers {T_BOT_AL*1000:.0f}/{T_TAPE*1000:.0f}/{T_TOP_AL*1000:.0f} μm")
    print(f"  Elements: {NX*NY*3}, Nodes: {(NX+1)*(NY+1)*4}")
    print(f"  Load: {args.force} N half-sine, {T_LOAD*1000:.1f} ms")
    print(f"  Duration: {T_END*1000:.1f} ms")
    print()

    cases = generate_doe(args.outdir, args.force)

    print(f"\nGenerated {len(cases)} cases in {args.outdir}/")
    for name, desc in cases:
        print(f"  {name:30s} {desc}")
    print("\nDone!")


if __name__ == "__main__":
    main()
