import numpy as np

# 원통형 굽힘: w(x) = A * (x/L)^2
# 100mm x 100mm 영역, 50x50 그리드
# A = 1.0 mm (중앙 최대 처짐)

nx, ny = 50, 50
L = 100.0  # mm
A = 1.0    # mm

x = np.linspace(0, L, nx)
y = np.linspace(0, L, ny)

with open('/d/KooRemapper/tests/warpage_cylindrical.dat', 'w') as f:
    for j in range(ny):
        row = []
        for i in range(nx):
            # w(x) = A * (x/L - 0.5)^2 - A/4  (중앙에서 최대)
            w = A * ((x[i]/L - 0.5)**2 - 0.25)  # -0.25 to 0 mm
            row.append(f'{w:.6f}')
        f.write('\t'.join(row) + '\n')

print('Cylindrical warpage data created: 50x50 grid, max deflection = 0 mm, min = -0.25 mm')
