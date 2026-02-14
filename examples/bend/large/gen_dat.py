"""Generate 50x50 dat file for large block (X:0-100, Y:0-50).
w = 0.5 * sin(pi*x/100) * sin(pi*y/50)
Grid is in normalized [0,1]x[0,1] coordinates, auto-mapped to BB.
Row 0 = y_max, row N-1 = y_min.
"""
import math

n = 50
with open("tests/bend_test_large.dat", "w") as f:
    for row in range(n + 1):
        y = 1.0 - row / n  # row 0 = y_max = 1.0
        vals = []
        for col in range(n + 1):
            x = col / n  # col 0 = x_min = 0.0
            w = 0.5 * math.sin(math.pi * x) * math.sin(math.pi * y)
            vals.append(f"{w:.6f}")
        f.write(" ".join(vals) + "\n")

print(f"Generated {n+1}x{n+1} dat grid")
