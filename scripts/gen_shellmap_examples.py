#!/usr/bin/env python3
"""Generate example K-files for shellmap command."""

import math
import os

DOLLAR = "$"
C = DOLLAR + "#"

def write_shell_kfile(filepath, comment_lines, nodes, elems):
    with open(filepath, 'w') as f:
        for line in comment_lines:
            f.write(C + ' ' + line + '\n')
        f.write('*KEYWORD\n')
        f.write('*NODE\n')
        f.write(C + '   nid               x               y               z\n')
        for nid, x, y, z in nodes:
            f.write(f'{nid:10d}{x:16.7e}{y:16.7e}{z:16.7e}\n')
        f.write('*ELEMENT_SHELL\n')
        f.write(C + '   eid     pid      n1      n2      n3      n4\n')
        for eid, pid, n1, n2, n3, n4 in elems:
            f.write(f'{eid:10d}{pid:10d}{n1:10d}{n2:10d}{n3:10d}{n4:10d}\n')
        f.write('*END\n')

def write_solid_kfile(filepath, comment_lines, nodes, elems):
    with open(filepath, 'w') as f:
        for line in comment_lines:
            f.write(C + ' ' + line + '\n')
        f.write('*KEYWORD\n')
        f.write('*NODE\n')
        f.write(C + '   nid               x               y               z\n')
        for nid, x, y, z in nodes:
            f.write(f'{nid:10d}{x:16.7e}{y:16.7e}{z:16.7e}\n')
        f.write('*ELEMENT_SOLID\n')
        f.write(C + '   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8\n')
        for e in elems:
            f.write(f'{e[0]:8d}{e[1]:8d}{e[2]:8d}{e[3]:8d}{e[4]:8d}{e[5]:8d}{e[6]:8d}{e[7]:8d}{e[8]:8d}{e[9]:8d}\n')
        f.write('*END\n')

def make_flat_hex_mesh(n_xi, n_yj, n_zk, x_positions, width, thickness):
    """Generate flat HEX8 mesh nodes and elements.
    x_positions: list of X coords for each i-station (length n_xi+1)
    """
    nodes = []
    fnid = 1
    for k in range(n_zk + 1):
        z_val = -thickness/2 + k * thickness / n_zk
        for j in range(n_yj + 1):
            y_val = j * width / n_yj
            for i in range(n_xi + 1):
                nodes.append((fnid, x_positions[i], y_val, z_val))
                fnid += 1

    def nidx(i, j, k):
        return k * (n_yj+1) * (n_xi+1) + j * (n_xi+1) + i + 1

    elems = []
    feid = 1
    for i in range(n_xi):
        for j in range(n_yj):
            n1 = nidx(i, j, 0);     n2 = nidx(i+1, j, 0)
            n3 = nidx(i+1, j+1, 0); n4 = nidx(i, j+1, 0)
            n5 = nidx(i, j, 1);     n6 = nidx(i+1, j, 1)
            n7 = nidx(i+1, j+1, 1); n8 = nidx(i, j+1, 1)
            elems.append((feid, 1, n1, n2, n3, n4, n5, n6, n7, n8))
            feid += 1

    return nodes, elems


###############################################################################
# 1. shellmap_arc: 30-degree cylinder arc (R=10, width=2)
###############################################################################

def gen_arc():
    R = 10.0
    angle_deg = 30.0
    angle_rad = math.radians(angle_deg)
    n_arc = 4
    n_w = 2
    width = 2.0
    thickness = 0.2

    # Bent shell nodes
    nodes = []
    nid = 1
    for i in range(n_arc + 1):
        theta = angle_rad * i / n_arc
        x = R * math.cos(theta)
        z = R * math.sin(theta)
        for j in range(n_w + 1):
            y = j * width / n_w
            nodes.append((nid, x, y, z))
            nid += 1

    # QUAD4 elements
    elems = []
    eid = 1
    for i in range(n_arc):
        for j in range(n_w):
            n1 = i * (n_w+1) + j + 1
            n2 = i * (n_w+1) + j + 2
            n3 = (i+1) * (n_w+1) + j + 2
            n4 = (i+1) * (n_w+1) + j + 1
            elems.append((eid, 1, n1, n2, n3, n4))
            eid += 1

    outdir = 'examples/shellmap_arc'
    write_shell_kfile(
        os.path.join(outdir, 'arc_shell.k'),
        ['LS-DYNA Keyword File',
         'Bent QUAD4 shell - 30 degree arc, R=10, width=2',
         'For shellmap example: simple cylindrical bend'],
        nodes, elems
    )

    # Flat detail: finer mesh (8x4x1 = 32 elements)
    arc_len = R * angle_rad
    n_xi = n_arc * 2  # 8
    n_yj = n_w * 2    # 4
    x_positions = [arc_len * i / n_xi for i in range(n_xi + 1)]

    flat_nodes, flat_elems = make_flat_hex_mesh(n_xi, n_yj, 1, x_positions, width, thickness)
    write_solid_kfile(
        os.path.join(outdir, 'arc_flat.k'),
        ['LS-DYNA Keyword File',
         f'Flat detail mesh for arc shellmap example',
         f'X: 0 to {arc_len:.4f} (arc length), Y: 0 to {width}, Z: {-thickness/2} to {thickness/2}',
         f'{n_xi}x{n_yj}x1 = {n_xi*n_yj} hex elements'],
        flat_nodes, flat_elems
    )

    print(f'Arc shell:  {len(nodes)} nodes, {len(elems)} elements -> {outdir}/arc_shell.k')
    print(f'Arc flat:   {len(flat_nodes)} nodes, {len(flat_elems)} elements -> {outdir}/arc_flat.k')


###############################################################################
# 2. shellmap_spline: S-curve (z = 1.5*sin(2*pi*t))
###############################################################################

def gen_spline():
    n_along = 8
    n_width = 2
    width = 2.0
    amp = 1.5
    thickness = 0.2

    # Bent shell nodes
    nodes = []
    nid = 1
    for i in range(n_along + 1):
        t = i / n_along
        x = 10.0 * t
        z = amp * math.sin(2 * math.pi * t)
        for j in range(n_width + 1):
            y = j * width / n_width
            nodes.append((nid, x, y, z))
            nid += 1

    elems = []
    eid = 1
    for i in range(n_along):
        for j in range(n_width):
            n1 = i * (n_width+1) + j + 1
            n2 = i * (n_width+1) + j + 2
            n3 = (i+1) * (n_width+1) + j + 2
            n4 = (i+1) * (n_width+1) + j + 1
            elems.append((eid, 1, n1, n2, n3, n4))
            eid += 1

    outdir = 'examples/shellmap_spline'
    write_shell_kfile(
        os.path.join(outdir, 'spline_shell.k'),
        ['LS-DYNA Keyword File',
         'S-curve spline shell - varying curvature',
         'x(t) = 10*t, z(t) = 1.5*sin(2*pi*t), width Y=0..2',
         'For shellmap example: non-uniform curvature surface'],
        nodes, elems
    )

    # Compute arc lengths
    arc_lengths = [0.0]
    n_sub = 1000
    for i in range(1, n_along + 1):
        t0 = (i-1) / n_along
        t1 = i / n_along
        seg = 0.0
        for k in range(n_sub):
            ta = t0 + (t1-t0)*k/n_sub
            tb = t0 + (t1-t0)*(k+1)/n_sub
            xa = 10*ta; za = amp*math.sin(2*math.pi*ta)
            xb = 10*tb; zb = amp*math.sin(2*math.pi*tb)
            seg += math.sqrt((xb-xa)**2 + (zb-za)**2)
        arc_lengths.append(arc_lengths[-1] + seg)

    total_arc = arc_lengths[-1]

    # Flat detail: finer mesh (16x4x1 = 64 elements)
    n_xi = n_along * 2
    n_yj = n_width * 2

    # Interpolate arc lengths to get x positions for finer grid
    x_positions = []
    for i in range(n_xi + 1):
        frac = i / n_xi
        seg_idx = int(frac * n_along)
        if seg_idx >= n_along:
            seg_idx = n_along - 1
        local_frac = frac * n_along - seg_idx
        x_val = arc_lengths[seg_idx] + local_frac * (arc_lengths[seg_idx+1] - arc_lengths[seg_idx])
        x_positions.append(x_val)

    flat_nodes, flat_elems = make_flat_hex_mesh(n_xi, n_yj, 1, x_positions, width, thickness)
    write_solid_kfile(
        os.path.join(outdir, 'spline_flat.k'),
        ['LS-DYNA Keyword File',
         f'Flat detail mesh for spline shellmap example',
         f'X: 0 to {total_arc:.4f} (arc length), Y: 0 to {width}, Z: {-thickness/2} to {thickness/2}',
         f'{n_xi}x{n_yj}x1 = {n_xi*n_yj} hex elements'],
        flat_nodes, flat_elems
    )

    print(f'Spline shell: {len(nodes)} nodes, {len(elems)} elements -> {outdir}/spline_shell.k')
    print(f'Spline flat:  {len(flat_nodes)} nodes, {len(flat_elems)} elements -> {outdir}/spline_flat.k')
    print(f'Spline arc length: {total_arc:.4f}')


if __name__ == '__main__':
    gen_arc()
    gen_spline()
    print('\nDone! Now run:')
    print('  KooRemapper shellmap examples/shellmap_arc/arc_shell.k examples/shellmap_arc/arc_flat.k examples/shellmap_arc/arc_mapped.k')
    print('  KooRemapper shellmap examples/shellmap_spline/spline_shell.k examples/shellmap_spline/spline_flat.k examples/shellmap_spline/spline_mapped.k')
