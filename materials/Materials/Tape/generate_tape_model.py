#!/usr/bin/env python3
"""
Tape Compression Model Generator for LS-DYNA
=============================================
3-layer stack: Al (10μm) / Tape (30μm) / Al (10μm)
3x3 in-plane hex mesh, half-sine pressure on top face.

Generates two K-files:
  1. tape_viscoelastic.k  — MAT_VISCOELASTIC (MAT_006) for tape
  2. tape_elastic.k       — MAT_ELASTIC (MAT_001) for tape (equilibrium modulus)

Unit system: mm, s, ton  →  Force=N, Stress=MPa, Density=ton/mm³
"""

import math
import os
import argparse

# ============================================================
# Geometry
# ============================================================
NX, NY = 3, 3              # in-plane elements
DX, DY = 0.1, 0.1          # mm (100 μm per element)

# Layer thicknesses (mm)
T_BOT_AL  = 0.010           # 10 μm
T_TAPE    = 0.030           # 30 μm
T_TOP_AL  = 0.010           # 10 μm

Z_LEVELS = [
    0.0,
    T_BOT_AL,
    T_BOT_AL + T_TAPE,
    T_BOT_AL + T_TAPE + T_TOP_AL,
]

# ============================================================
# Material properties  (mm, s, ton → MPa)
# ============================================================
# Aluminum
AL_RO   = 2.7e-9    # ton/mm³  (2700 kg/m³)
AL_E    = 70000.0    # MPa
AL_NU   = 0.33

# Tape — viscoelastic (realistic acrylic PSA)
TAPE_RO   = 1.1e-9   # ton/mm³  (1100 kg/m³)
TAPE_BULK = 2000.0    # MPa  (nearly incompressible)
TAPE_G0   = 0.30      # MPa  short-time shear modulus  → E_inst ≈ 0.9 MPa
TAPE_GI   = 0.01      # MPa  long-time shear modulus   → E_equil ≈ 0.03 MPa
TAPE_BETA = 500.0     # 1/s  decay constant  (τ ≈ 2 ms)

# Tape — elastic (equilibrium modulus for comparison)
TAPE_E_ELASTIC = 3.0 * TAPE_GI   # ≈ 0.03 MPa
TAPE_NU_ELASTIC = 0.499           # nearly incompressible

# ============================================================
# Loading
# ============================================================
P_MAX    = 0.02      # MPa peak pressure (half-sine)
T_END    = 0.006     # s   (6 ms — 5 ms load + 1 ms free vibration)
T_LOAD   = 0.005     # s   half-sine duration
N_CURVE  = 51        # points in load curve

# ============================================================
# Output
# ============================================================
D3PLOT_DT = 0.0001   # s  (100 μs → 60 frames)


def node_id(i, j, k):
    """Node ID from grid indices (i=0..NX, j=0..NY, k=0..3)."""
    return k * (NX + 1) * (NY + 1) + j * (NX + 1) + i + 1


def generate_nodes():
    """Generate *NODE cards."""
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
    """Generate *ELEMENT_SOLID cards for 3 layers (PID 1,2,3)."""
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


def generate_top_segments():
    """Segment set for top face (k=3 layer, SID=1)."""
    lines = [
        "*SET_SEGMENT_TITLE",
        "Top face segments",
        "$      SID       DA1       DA2       DA3       DA4    SOLVER",
        f"{'1':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'MECH':>10s}",
    ]
    for j in range(NY):
        for i in range(NX):
            n1 = node_id(i,   j,   3)
            n2 = node_id(i+1, j,   3)
            n3 = node_id(i+1, j+1, 3)
            n4 = node_id(i,   j+1, 3)
            lines.append(f"{n1:10d}{n2:10d}{n3:10d}{n4:10d}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}")
    return "\n".join(lines)


def generate_bottom_nodeset():
    """Node set for bottom face BC (k=0, SID=2)."""
    lines = [
        "*SET_NODE_LIST_TITLE",
        "Bottom face nodes",
        "$      SID       DA1       DA2       DA3       DA4    SOLVER",
        f"{'2':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'MECH':>10s}",
    ]
    row = []
    for j in range(NY + 1):
        for i in range(NX + 1):
            row.append(node_id(i, j, 0))
            if len(row) == 8:
                lines.append("".join(f"{n:10d}" for n in row))
                row = []
    if row:
        lines.append("".join(f"{n:10d}" for n in row) + "".join(f"{'0':>10s}" for _ in range(8 - len(row))))
    return "\n".join(lines)


def generate_load_curve(peak_pressure=None):
    """Half-sine load curve (LCID=1)."""
    pmax = peak_pressure if peak_pressure is not None else P_MAX
    lines = [
        "*DEFINE_CURVE_TITLE",
        "Half-sine pressure",
        "$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP     LCINT",
        f"{'1':>10s}{'0':>10s}{'1.0':>10s}{'1.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0':>10s}{'0':>10s}",
    ]
    for n in range(N_CURVE):
        t = n * T_LOAD / (N_CURVE - 1)
        p = pmax * math.sin(math.pi * t / T_LOAD)
        lines.append(f"{t:20.10e}{p:20.10e}")
    # After load ends, zero
    lines.append(f"{T_END:20.10e}{0.0:20.10e}")
    return "\n".join(lines)


def generate_common_keywords():
    """Keywords shared between both models."""
    return f"""$
$ ============================================================
$ CONTROL
$ ============================================================
*KEYWORD
*TITLE
Tape Compression Test
$
*CONTROL_TERMINATION
$   ENDTIM    ENDCYC     DTMIN    ENDENG    ENDMAS      NOSOL
{T_END:10.4e}         0       0.0       0.0     1.E+8         0
$
*CONTROL_TIMESTEP
$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS      LCTM     ERODE     MS1ST
       0.0       0.9         0       0.0       0.0         0         0         0
$
*CONTROL_ENERGY
$     HGEN      RWEN    SLNTEN     RYLEN
         2         2         2         1
$
*CONTROL_HOURGLASS
$      IHQ        QH
         6    0.1000
$
$ ============================================================
$ DATABASE
$ ============================================================
*DATABASE_GLSTAT
$       DT
{D3PLOT_DT:10.4e}
$
*DATABASE_MATSUM
$       DT
{D3PLOT_DT:10.4e}
$
*DATABASE_NODOUT
$       DT
{D3PLOT_DT:10.4e}
$
*DATABASE_ELOUT
$       DT
{D3PLOT_DT:10.4e}
$
*DATABASE_BINARY_D3PLOT
$       DT      LCDT      BEAM     NPLTC    PSETID
{D3PLOT_DT:10.4e}         0         0         0         0
$
*DATABASE_EXTENT_BINARY
$    NEIPH     NEIPS    MAXINT    STRFLG    SIGFLG    EPSFLG    RLTFLG    ENGFLG
         0         0         3         1         1         1         1         1
$   CMPFLG    IEVERP    BEAMIP     DCOMP      SHGE     STSSZ    N3THDT   IALEMAT
         0         0         0         1         1         1         2         1
$  NINTSLD   PKP_SEN      SCLP     HYDRO     MSSCL     THERM    INTOUT    NODOUT
         8         0       1.0         0         0         0  ALL       ALL
$
$ ============================================================
$ SECTION
$ ============================================================
*SECTION_SOLID_TITLE
Solid section
$    SECID    ELFORM       AET    AFAC     BFAC     CFAC     DFAC
         1         1         0
$
$ ============================================================
$ PARTS
$ ============================================================
*PART
Bottom Aluminum
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         1         1         1         0         0         0         0         0
$
*PART
Tape Layer
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         2         1         2         0         0         0         0         0
$
*PART
Top Aluminum
$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID
         3         1         1         0         0         0         0         0
$
$ ============================================================
$ MATERIALS — Aluminum (MAT_001)
$ ============================================================
*MAT_ELASTIC
$      MID        RO         E        PR        DA        DB  NOT_USED
         1{AL_RO:10.3e}{AL_E:10.1f}{AL_NU:10.4f}       0.0       0.0       0.0
$"""


def generate_mat_viscoelastic():
    """MAT_VISCOELASTIC (MAT_006) for tape."""
    return f"""$
$ ============================================================
$ MATERIAL — Tape Viscoelastic (MAT_006)
$ ============================================================
$ G(t) = GI + (G0 - GI) * exp(-BETA * t)
$ G0 = {TAPE_G0} MPa (E_inst ~ {3*TAPE_G0:.2f} MPa)
$ GI = {TAPE_GI} MPa (E_equil ~ {3*TAPE_GI:.2f} MPa)
$ BETA = {TAPE_BETA} /s  (relaxation time ~ {1/TAPE_BETA*1000:.1f} ms)
$
*MAT_VISCOELASTIC
$      MID        RO      BULK        G0        GI      BETA
         2{TAPE_RO:10.3e}{TAPE_BULK:10.1f}{TAPE_G0:10.4f}{TAPE_GI:10.4f}{TAPE_BETA:10.1f}
$"""


def generate_mat_elastic_tape():
    """MAT_ELASTIC for tape (equilibrium modulus for comparison)."""
    return f"""$
$ ============================================================
$ MATERIAL — Tape Elastic (MAT_001) — equilibrium modulus
$ ============================================================
$ E = 3 * GI = {TAPE_E_ELASTIC:.4f} MPa  (long-time/static modulus)
$ nu = {TAPE_NU_ELASTIC}  (nearly incompressible)
$
*MAT_ELASTIC
$      MID        RO         E        PR        DA        DB  NOT_USED
         2{TAPE_RO:10.3e}{TAPE_E_ELASTIC:10.4f}{TAPE_NU_ELASTIC:10.4f}       0.0       0.0       0.0
$"""


def generate_bc_and_load():
    """Boundary conditions and load."""
    return f"""$
$ ============================================================
$ BOUNDARY CONDITIONS
$ ============================================================
$ Bottom face: fix all translations
*BOUNDARY_SPC_SET
$     NSID       CID      DOFX      DOFY      DOFZ     DOFRX     DOFRY     DOFRZ
         2         0         1         1         1         0         0         0
$
$ ============================================================
$ LOADING — half-sine pressure on top face
$ ============================================================
*LOAD_SEGMENT_SET
$     SSID      LCID        SF        AT
         1         1{1.0:10.4f}       0.0
$"""


def write_kfile(filepath, mat_section, peak_pressure=None):
    """Write complete K-file."""
    with open(filepath, "w") as f:
        f.write(generate_common_keywords())
        f.write("\n")
        f.write(mat_section)
        f.write("\n")
        f.write(generate_bc_and_load())
        f.write("\n$\n")
        f.write("$ ============================================================\n")
        f.write("$ MESH\n")
        f.write("$ ============================================================\n")
        f.write(generate_nodes())
        f.write("\n")
        f.write(generate_elements())
        f.write("\n$\n")
        f.write("$ ============================================================\n")
        f.write("$ SETS\n")
        f.write("$ ============================================================\n")
        f.write(generate_top_segments())
        f.write("\n")
        f.write(generate_bottom_nodeset())
        f.write("\n")
        f.write(generate_load_curve(peak_pressure))
        f.write("\n*END\n")
    print(f"  Written: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Generate tape compression K-files")
    parser.add_argument("--outdir", default=".", help="Output directory")
    parser.add_argument("--pressure", type=float, default=P_MAX, help="Peak pressure (MPa)")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    print("Tape Compression Model Generator")
    print(f"  Geometry: {NX}x{NY} in-plane, 3 layers ({T_BOT_AL*1000:.0f}/{T_TAPE*1000:.0f}/{T_TOP_AL*1000:.0f} μm)")
    print(f"  Elements: {NX*NY*3}, Nodes: {(NX+1)*(NY+1)*4}")
    pp = args.pressure
    print(f"  Load: half-sine {pp} MPa, {T_LOAD*1000:.0f} ms")
    print(f"  Tape viscoelastic: G0={TAPE_G0} MPa, GI={TAPE_GI} MPa, β={TAPE_BETA}/s")
    print(f"  Tape elastic: E={TAPE_E_ELASTIC:.4f} MPa, ν={TAPE_NU_ELASTIC}")
    print()

    # Viscoelastic model
    write_kfile(
        os.path.join(args.outdir, "tape_viscoelastic.k"),
        generate_mat_viscoelastic(),
        peak_pressure=pp,
    )

    # Elastic model
    write_kfile(
        os.path.join(args.outdir, "tape_elastic.k"),
        generate_mat_elastic_tape(),
        peak_pressure=pp,
    )

    print("\nDone!")


if __name__ == "__main__":
    main()
