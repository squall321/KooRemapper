"""
Convert 3pt_bending.k (HEX8 20x2x2) -> 3pt_bending_tet4.k (TET4 via 5-tet decomposition).
Node IDs and positions are preserved so BCs remain valid.
"""
import os, sys

# Grid dimensions
nx, ny, nz = 20, 2, 2   # hex cells
dx, dy, dz = 5.0, 2.5, 5.0  # mm per cell

# Node ID: iz*(ny+1)*(nx+1) + iy*(nx+1) + ix + 1  (1-indexed)
def nid(ix, iy, iz):
    return iz*(ny+1)*(nx+1) + iy*(nx+1) + ix + 1

lines = []
lines.append("*KEYWORD")
lines.append("3-Point Bending - Rubber Beam TET4")
lines.append("$--- Termination / Timestep ----------------------------")
lines.append("*CONTROL_TERMINATION")
lines.append("$  ENDTIM    ENDCYC     DTMIN    ENDENG    ENDMAS")
lines.append("     1.0         0       0.0       0.0       0.0")
lines.append("*CONTROL_TIMESTEP")
lines.append("$   DTINIT    TSSFAC")
lines.append("       0.0  0.900000")
lines.append("$--- Load curve (ramp 0->1, scaled to -10mm) ----------")
lines.append("*DEFINE_CURVE")
lines.append("$    LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP")
lines.append("         1         0       1.0     -10.0       0.0       0.0         0")
lines.append("$                A1                  O1")
lines.append("                 0.0                 0.0")
lines.append("                 1.0                 1.0")
lines.append("$--- Material / Section / Part placeholder (filled by matswap) ---")
lines.append("*MAT_ELASTIC")
lines.append("$      MID       RHO         E        PR        DA        DB")
lines.append("         1  7.85E-09  2.10E+05      0.30       0.0       0.0")
lines.append("*SECTION_SOLID_TITLE")
lines.append("Tet4_Section")
lines.append("$    SECID    ELFORM       AET")
lines.append("         1        13         0")
lines.append("*PART")
lines.append("Rubber_Beam")
lines.append("$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID")
lines.append("         1         1         1         0         0         0         0         0")
lines.append("$--- Boundary: Y-fixed at supports ----------------------")
lines.append("*BOUNDARY_SPC_SET")
lines.append("$    NSID      CID    DOFX    DOFY    DOFZ   DOFRX   DOFRY   DOFRZ")
lines.append("         1         0       0       1       0       0       0       0")
lines.append("*SET_NODE_LIST")
lines.append("$       SID")
lines.append("         1")
# Roller nodes: x=0,y=0,z=0 ; x=100,y=0,z=0 ; x=0,y=0,z=10 ; x=100,y=0,z=10
roller_nodes = [nid(0,0,0), nid(nx,0,0), nid(0,0,nz), nid(nx,0,nz)]
lines.append("  ".join(f"{n:8d}" for n in roller_nodes))
lines.append("$--- Boundary: X-fixed at left support ------------------")
lines.append("*BOUNDARY_SPC_SET")
lines.append("$    NSID      CID    DOFX    DOFY    DOFZ   DOFRX   DOFRY   DOFRZ")
lines.append("         2         0       1       0       0       0       0       0")
lines.append("*SET_NODE_LIST")
lines.append("$       SID")
lines.append("         2")
left_nodes = [nid(0,0,0), nid(0,0,nz)]
lines.append("  ".join(f"{n:8d}" for n in left_nodes))
lines.append("$--- Boundary: Z-fixed at z=0 face ----------------------")
lines.append("*BOUNDARY_SPC_SET")
lines.append("$    NSID      CID    DOFX    DOFY    DOFZ   DOFRX   DOFRY   DOFRZ")
lines.append("         3         0       0       0       1       0       0       0")
lines.append("*SET_NODE_LIST")
lines.append("$       SID")
lines.append("         3")
z0_nodes = [nid(ix, iy, 0) for iy in range(ny+1) for ix in range(nx+1)]
# Write 8 per line
for i in range(0, len(z0_nodes), 8):
    lines.append("  ".join(f"{n:8d}" for n in z0_nodes[i:i+8]))
lines.append("$--- Prescribed displacement at center top (x=50, y=5) --")
lines.append("*BOUNDARY_PRESCRIBED_MOTION_SET")
lines.append("$    NSID       DOF       VAD      LCID        SF       VID     DEATH      BIRTH")
lines.append("         4         2         2         1       1.0         0 1.000E+28       0.0")
lines.append("*SET_NODE_LIST")
lines.append("$       SID")
lines.append("         4")
# Center top nodes: x=50, y=5, all z layers
center_top = [nid(nx//2, ny, iz) for iz in range(nz+1)]
lines.append("  ".join(f"{n:8d}" for n in center_top))

# Nodes
lines.append("$--- Nodes -----------------------------------------------")
lines.append("*NODE")
for iz in range(nz+1):
    for iy in range(ny+1):
        for ix in range(nx+1):
            x = ix * dx
            y = iy * dy
            z = iz * dz
            lines.append(f"{nid(ix,iy,iz):8d}{x:16.6f}{y:16.6f}{z:16.6f}")

# Elements (TET4 via 5-tet decomposition, stored as degenerate SOLID)
lines.append("$--- Elements (TET4 as degenerate SOLID) ----------------")
lines.append("*ELEMENT_SOLID")
eid = 1
for iz in range(nz):
    for iy in range(ny):
        for ix in range(nx):
            # 8 corners
            n0 = nid(ix,   iy,   iz  )
            n1 = nid(ix+1, iy,   iz  )
            n2 = nid(ix+1, iy+1, iz  )
            n3 = nid(ix,   iy+1, iz  )
            n4 = nid(ix,   iy,   iz+1)
            n5 = nid(ix+1, iy,   iz+1)
            n6 = nid(ix+1, iy+1, iz+1)
            n7 = nid(ix,   iy+1, iz+1)
            # 5-tet decomposition (all positive Jacobian)
            tets = [
                (n0, n1, n3, n4),
                (n1, n4, n5, n6),
                (n1, n2, n3, n6),
                (n3, n4, n6, n7),
                (n1, n3, n4, n6),
            ]
            pid = 1
            for (a, b, c, d) in tets:
                # TET4 as degenerate HEX8: n1 n2 n3 n4 n4 n4 n4 n4
                lines.append(f"{eid:8d}{pid:8d}{a:8d}{b:8d}{c:8d}{d:8d}{d:8d}{d:8d}{d:8d}{d:8d}")
                eid += 1
lines.append("*END")

out = "tests/integration/3pt_bending_tet4.k"
with open(out, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"Written {out}: {eid-1} TET4 elements, {(nx+1)*(ny+1)*(nz+1)} nodes")
