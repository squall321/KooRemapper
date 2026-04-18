#!/usr/bin/env python3
"""
Tape Shear Model Generator for LS-DYNA
=======================================
3-layer stack: Al (10μm) / Tape (30μm) / Al (10μm)
3x3 in-plane hex mesh, half-sine shear traction on top face (X-direction).

Bottom face: XYZ fixed
Top face: distributed X-force (equivalent to uniform shear stress)

Unit system: mm, s, ton  →  Force=N, Stress=MPa, Density=ton/mm³
"""

import math
import os
import argparse

# ============================================================
# Geometry (same as compression model)
# ============================================================
NX, NY = 3, 3
DX, DY = 0.1, 0.1  # mm

T_BOT_AL = 0.010
T_TAPE   = 0.030
T_TOP_AL = 0.010

Z_LEVELS = [0.0, T_BOT_AL, T_BOT_AL + T_TAPE, T_BOT_AL + T_TAPE + T_TOP_AL]

# ============================================================
# Materials (identical to compression model)
# ============================================================
AL_RO = 2.7e-9
AL_E  = 70000.0
AL_NU = 0.33

TAPE_RO   = 1.1e-9
TAPE_BULK = 2000.0
TAPE_G0   = 0.30
TAPE_GI   = 0.01
TAPE_BETA = 500.0

TAPE_E_ELASTIC  = 3.0 * TAPE_GI   # 0.03 MPa
TAPE_NU_ELASTIC = 0.499

# ============================================================
# Loading
# ============================================================
TAU_MAX  = 1.0       # MPa peak shear stress (overridden by --shear)
T_END    = 0.006     # s
T_LOAD   = 0.005     # s
N_CURVE  = 51

D3PLOT_DT = 0.0001   # s


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


def generate_bottom_nodeset():
    """Node set SID=2 for bottom face BC (k=0)."""
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


def generate_shear_load_cards(tau_max):
    """
    Distributed X-force on top face nodes (k=3).
    Force per node = tau_max * tributary_area.

    For 3x3 mesh (4x4 = 16 nodes):
      Corner nodes (4): A_trib = DX*DY/4
      Edge nodes (8):   A_trib = DX*DY/2
      Interior nodes(4): A_trib = DX*DY

    Load curve scales to 1.0 at peak; force magnitude baked into node load.
    """
    lines = []

    # Load curve (LCID=1): half-sine, peak=1.0
    lines.append("*DEFINE_CURVE_TITLE")
    lines.append("Half-sine shear")
    lines.append("$     LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP     LCINT")
    lines.append(f"{'1':>10s}{'0':>10s}{'1.0':>10s}{'1.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0':>10s}{'0':>10s}")
    for n in range(N_CURVE):
        t = n * T_LOAD / (N_CURVE - 1)
        v = math.sin(math.pi * t / T_LOAD)
        lines.append(f"{t:20.10e}{v:20.10e}")
    lines.append(f"{T_END:20.10e}{0.0:20.10e}")
    lines.append("$")

    # Node forces via *LOAD_NODE_SET for each tributary area group
    # Group 1: corner nodes (SID=10)
    # Group 2: edge nodes (SID=11)
    # Group 3: interior nodes (SID=12)

    corners = []
    edges = []
    interiors = []

    for j in range(NY + 1):
        for i in range(NX + 1):
            nid = node_id(i, j, 3)  # k=3 = top face
            is_edge_i = (i == 0 or i == NX)
            is_edge_j = (j == 0 or j == NY)
            if is_edge_i and is_edge_j:
                corners.append(nid)
            elif is_edge_i or is_edge_j:
                edges.append(nid)
            else:
                interiors.append(nid)

    # Force per node
    f_corner   = tau_max * DX * DY / 4.0   # N
    f_edge     = tau_max * DX * DY / 2.0
    f_interior = tau_max * DX * DY

    groups = [
        (10, "Top corner nodes", corners, f_corner),
        (11, "Top edge nodes", edges, f_edge),
        (12, "Top interior nodes", interiors, f_interior),
    ]

    for sid, title, nids, force in groups:
        if not nids:
            continue
        lines.append(f"*SET_NODE_LIST_TITLE")
        lines.append(title)
        lines.append("$      SID       DA1       DA2       DA3       DA4    SOLVER")
        lines.append(f"{sid:10d}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'0.0':>10s}{'MECH':>10s}")
        row = []
        for n in nids:
            row.append(n)
            if len(row) == 8:
                lines.append("".join(f"{nd:10d}" for nd in row))
                row = []
        if row:
            lines.append("".join(f"{nd:10d}" for nd in row) + "".join(f"{'0':>10s}" for _ in range(8 - len(row))))

        # *LOAD_NODE_SET: DOF=1 (X-direction)
        lines.append("*LOAD_NODE_SET")
        lines.append("$     NSID       DOF      LCID        SF       CID")
        lines.append(f"{sid:10d}{'1':>10s}{'1':>10s}{force:10.4e}{'0':>10s}")

    return "\n".join(lines)


def generate_common_keywords():
    return f"""$
$ ============================================================
$ CONTROL
$ ============================================================
*KEYWORD
*TITLE
Tape Shear Test
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
    return f"""$
$ ============================================================
$ MATERIAL — Tape Viscoelastic (MAT_006)
$ ============================================================
*MAT_VISCOELASTIC
$      MID        RO      BULK        G0        GI      BETA
         2{TAPE_RO:10.3e}{TAPE_BULK:10.1f}{TAPE_G0:10.4f}{TAPE_GI:10.4f}{TAPE_BETA:10.1f}
$"""


def generate_mat_elastic_tape():
    return f"""$
$ ============================================================
$ MATERIAL — Tape Elastic (MAT_001) — equilibrium modulus
$ ============================================================
*MAT_ELASTIC
$      MID        RO         E        PR        DA        DB  NOT_USED
         2{TAPE_RO:10.3e}{TAPE_E_ELASTIC:10.4f}{TAPE_NU_ELASTIC:10.4f}       0.0       0.0       0.0
$"""


def generate_bc():
    return f"""$
$ ============================================================
$ BOUNDARY CONDITIONS — bottom face XYZ fixed
$ ============================================================
*BOUNDARY_SPC_SET
$     NSID       CID      DOFX      DOFY      DOFZ     DOFRX     DOFRY     DOFRZ
         2         0         1         1         1         0         0         0
$"""


def write_kfile(filepath, mat_section, tau_max):
    with open(filepath, "w") as f:
        f.write(generate_common_keywords())
        f.write("\n")
        f.write(mat_section)
        f.write("\n")
        f.write(generate_bc())
        f.write("\n$\n")
        f.write("$ ============================================================\n")
        f.write("$ MESH\n")
        f.write("$ ============================================================\n")
        f.write(generate_nodes())
        f.write("\n")
        f.write(generate_elements())
        f.write("\n$\n")
        f.write("$ ============================================================\n")
        f.write("$ SETS & LOADING\n")
        f.write("$ ============================================================\n")
        f.write(generate_bottom_nodeset())
        f.write("\n")
        f.write(generate_shear_load_cards(tau_max))
        f.write("\n*END\n")
    print(f"  Written: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Generate tape shear K-files")
    parser.add_argument("--outdir", default=".", help="Output directory")
    parser.add_argument("--shear", type=float, default=TAU_MAX, help="Peak shear stress (MPa)")
    args = parser.parse_args()

    tau = args.shear
    os.makedirs(args.outdir, exist_ok=True)

    print("Tape Shear Model Generator")
    print(f"  Geometry: {NX}x{NY} in-plane, 3 layers")
    print(f"  Shear: half-sine {tau} MPa, {T_LOAD*1000:.0f} ms (X-direction)")
    print()

    write_kfile(
        os.path.join(args.outdir, "tape_shear_viscoelastic.k"),
        generate_mat_viscoelastic(),
        tau,
    )
    write_kfile(
        os.path.join(args.outdir, "tape_shear_elastic.k"),
        generate_mat_elastic_tape(),
        tau,
    )

    print("\nDone!")


if __name__ == "__main__":
    main()
