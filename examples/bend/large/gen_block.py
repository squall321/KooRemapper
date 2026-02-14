"""Generate a large HEX8 block mesh for bend testing.
50x40x5 = 10,000 elements, X:0-100, Y:0-50, Z:0-2
"""

nx, ny, nz = 50, 40, 5
x_max, y_max, z_max = 100.0, 50.0, 2.0

dx = x_max / nx
dy = y_max / ny
dz = z_max / nz

def node_id(i, j, k):
    return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i + 1

with open("tests/bend_test_large_block.k", "w") as f:
    f.write("$# Large HEX8 block for bend testing\n")
    f.write(f"$# X: 0..{x_max:.0f}, Y: 0..{y_max:.0f}, Z: 0..{z_max:.0f}\n")
    f.write(f"$# Elements: {nx}x{ny}x{nz} = {nx*ny*nz}\n")
    f.write(f"$# Nodes: {(nx+1)*(ny+1)*(nz+1)}\n")
    f.write("$# PID=1, E=210000, nu=0.3\n")
    f.write("*KEYWORD\n")

    # Nodes
    f.write("*NODE\n")
    f.write("$#   nid               x               y               z\n")
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                nid = node_id(i, j, k)
                x = i * dx
                y = j * dy
                z = k * dz
                f.write(f"{nid:8d}{x:16.9e}{y:16.9e}{z:16.9e}\n")

    # Elements
    f.write("*ELEMENT_SOLID\n")
    f.write("$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8\n")
    eid = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                eid += 1
                n1 = node_id(i, j, k)
                n2 = node_id(i+1, j, k)
                n3 = node_id(i+1, j+1, k)
                n4 = node_id(i, j+1, k)
                n5 = node_id(i, j, k+1)
                n6 = node_id(i+1, j, k+1)
                n7 = node_id(i+1, j+1, k+1)
                n8 = node_id(i, j+1, k+1)
                f.write(f"{eid:8d}{1:8d}{n1:8d}{n2:8d}{n3:8d}{n4:8d}{n5:8d}{n6:8d}{n7:8d}{n8:8d}\n")

    # Material
    f.write("*MAT_ELASTIC\n")
    f.write("$#     mid        ro         e        pr\n")
    f.write("         1  7.85E-09  2.10E+05       0.3\n")

    # Section
    f.write("*SECTION_SOLID\n")
    f.write("$#  secid    elform\n")
    f.write("         1         1\n")

    # Part
    f.write("*PART\n")
    f.write("Large block\n")
    f.write("$#     pid     secid       mid\n")
    f.write("         1         1         1\n")

    f.write("*END\n")

print(f"Generated: {(nx+1)*(ny+1)*(nz+1)} nodes, {nx*ny*nz} elements")
