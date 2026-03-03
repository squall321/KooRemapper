"""
3-point bending test model generator for KooRemapper implicit testing.
Beam: 100 x 10 x 5 mm (L x W x H), Steel, HEX8 mesh
Supports: Y-fixed at bottom face x=0 and x=100 (roller)
Load:     Prescribed displacement -2mm at center top (x=50, y=5)
"""
import os

# ── Geometry ──────────────────────────────────────────────────────────────
L = 100.0   # length (X)
W = 10.0    # width  (Z)
H = 5.0     # height (Y)
NX = 20     # elements along X
NY = 2      # elements along Y
NZ = 2      # elements along Z

dx = L / NX
dy = H / NY
dz = W / NZ

# ── Node generation ───────────────────────────────────────────────────────
# Node ID: nid(ix, iy, iz) = iz*(NX+1)*(NY+1) + iy*(NX+1) + ix + 1
def nid(ix, iy, iz):
    return iz*(NX+1)*(NY+1) + iy*(NX+1) + ix + 1

nodes = []
for iz in range(NZ+1):
    for iy in range(NY+1):
        for ix in range(NX+1):
            x = ix * dx
            y = iy * dy
            z = iz * dz
            nodes.append((nid(ix,iy,iz), x, y, z))

# ── Element generation ────────────────────────────────────────────────────
# HEX8: n1-n8 from LS-DYNA convention (bottom face CCW from front, then top)
elements = []
eid = 1
for iz in range(NZ):
    for iy in range(NY):
        for ix in range(NX):
            n1 = nid(ix,   iy,   iz)
            n2 = nid(ix+1, iy,   iz)
            n3 = nid(ix+1, iy+1, iz)
            n4 = nid(ix,   iy+1, iz)
            n5 = nid(ix,   iy,   iz+1)
            n6 = nid(ix+1, iy,   iz+1)
            n7 = nid(ix+1, iy+1, iz+1)
            n8 = nid(ix,   iy+1, iz+1)
            elements.append((eid, 1, n1, n2, n3, n4, n5, n6, n7, n8))
            eid += 1

# ── Boundary conditions ───────────────────────────────────────────────────
# Support A (x=0): bottom face (iy=0) — constrain Y, allow X/Z rotation → dof=2
# Support B (x=L): bottom face (iy=0) — constrain Y and X → dof=2+1 (pin)
# Also constrain Z-symmetry: all nodes at z=0, iy=0 constrain Z to prevent sliding
support_A = []  # y-constrained only (roller)
support_B = []  # y+x constrained (pin to prevent rigid body)
z_constrain = [] # z-constrain all bottom nodes at z=0 face

for iz in range(NZ+1):
    for n in [nid(0,  0, iz)]:  # x=0, bottom
        support_A.append(n)
    for n in [nid(NX, 0, iz)]:  # x=L, bottom
        support_A.append(n)

# Prevent rigid body in X: fix one node in X at support
support_B_x = [nid(0, 0, iz) for iz in range(NZ+1)]  # x=0 bottom: fix X too

# Prevent rigid body in Z: fix one Z-plane
support_z = [nid(ix, iy, 0) for ix in range(NX+1) for iy in range(NY+1)]

# Load: prescribed displacement at center top nodes (ix=NX//2, iy=NY, all iz)
load_nset = [nid(NX//2, NY, iz) for iz in range(NZ+1)]

# ── LCSS: load curve for prescribed displacement ───────────────────────────
# Static: ramp from 0 to -2mm over endtime
# We'll use LCID=1

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "integration")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "3pt_bending.k")

lines = []
lines.append("*KEYWORD")
lines.append("3-Point Bending - Steel Beam")
lines.append("$--- Termination / Timestep ------------------------------------")
lines.append("*CONTROL_TERMINATION")
lines.append("$  ENDTIM    ENDCYC     DTMIN    ENDENG    ENDMAS")
lines.append("     1.0         0       0.0       0.0       0.0")
lines.append("*CONTROL_TIMESTEP")
lines.append("$   DTINIT    TSSFAC")
lines.append("       0.0  0.900000")
lines.append("$--- Load curve (ramp 0->1, scaled to -2mm) --------------------")
lines.append("*DEFINE_CURVE")
lines.append("$    LCID      SIDR       SFA       SFO      OFFA      OFFO    DATTYP")
lines.append("         1         0       1.0      -2.0       0.0       0.0         0")
lines.append("$                A1                  O1")
lines.append("                 0.0                 0.0")
lines.append("                 1.0                 1.0")
lines.append("$--- Material --------------------------------------------------")
lines.append("*MAT_ELASTIC")
lines.append("$      MID       RHO         E        PR        DA        DB")
lines.append("         1  7.85E-09  2.10E+05      0.30       0.0       0.0")
lines.append("$--- Section ---------------------------------------------------")
lines.append("*SECTION_SOLID")
lines.append("$    SECID    ELFORM       AET")
lines.append("         1         1         0")
lines.append("$--- Part -------------------------------------------------------")
lines.append("*PART")
lines.append("Beam")
lines.append("$      PID     SECID       MID     EOSID      HGID      GRAV    ADPOPT      TMID")
lines.append("         1         1         1         0         0         0         0         0")
lines.append("$--- Boundary: Y-fixed at supports (rollers at x=0 and x=L) ----")
lines.append("*BOUNDARY_SPC_SET")
lines.append("$    NSID      CID    DOFX    DOFY    DOFZ   DOFRX   DOFRY   DOFRZ")
lines.append("         1         0       0       1       0       0       0       0")
lines.append("*SET_NODE_LIST")
lines.append("$       SID")
lines.append("         1")

# 8 per line
def write_node_list(lst):
    row = []
    for n in lst:
        row.append(f"{n:10d}")
        if len(row) == 8:
            lines.append("".join(row))
            row = []
    if row:
        lines.append("".join(row))

write_node_list(support_A)
lines.append("")

lines.append("$--- Boundary: X-fixed at left support (prevent rigid body X) --")
lines.append("*BOUNDARY_SPC_SET")
lines.append("$    NSID      CID    DOFX    DOFY    DOFZ   DOFRX   DOFRY   DOFRZ")
lines.append("         2         0       1       0       0       0       0       0")
lines.append("*SET_NODE_LIST")
lines.append("$       SID")
lines.append("         2")
write_node_list(support_B_x)

lines.append("$--- Boundary: Z-fixed at z=0 face (prevent rigid body Z) ------")
lines.append("*BOUNDARY_SPC_SET")
lines.append("$    NSID      CID    DOFX    DOFY    DOFZ   DOFRX   DOFRY   DOFRZ")
lines.append("         3         0       0       0       1       0       0       0")
lines.append("*SET_NODE_LIST")
lines.append("$       SID")
lines.append("         3")
write_node_list(support_z)

lines.append("$--- Prescribed displacement at center top (x=50, y=5mm) --------")
lines.append("*BOUNDARY_PRESCRIBED_MOTION_SET")
lines.append("$    NSID       DOF       VAD      LCID        SF       VID     DEATH      BIRTH")
lines.append("         4         2         2         1       1.0         0 1.000E+28       0.0")
lines.append("*SET_NODE_LIST")
lines.append("$       SID")
lines.append("         4")
write_node_list(load_nset)

lines.append("$--- Nodes -------------------------------------------------------")
lines.append("*NODE")
for (n, x, y, z) in nodes:
    lines.append(f"{n:8d}{x:16.6f}{y:16.6f}{z:16.6f}")
lines.append("")

lines.append("$--- Elements ----------------------------------------------------")
lines.append("*ELEMENT_SOLID")
for (e, pid, n1,n2,n3,n4,n5,n6,n7,n8) in elements:
    lines.append(f"{e:8d}{pid:8d}{n1:8d}{n2:8d}{n3:8d}{n4:8d}{n5:8d}{n6:8d}{n7:8d}{n8:8d}")
lines.append("")

lines.append("*END")

with open(out_path, "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"Generated: {out_path}")
print(f"  Nodes:    {len(nodes)}")
print(f"  Elements: {len(elements)}")
print(f"  Load nodes (center top): {load_nset}")
