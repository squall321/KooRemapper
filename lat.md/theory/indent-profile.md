# Indent profile h(d), h''(d)

Stub mirroring `docs/KooRemapper_Theory_Document.md` §(40.3 derivation).

Source code: (see See-also)

## Summary

Quarter-arc fillet: k = depth/(r1+r2). In r1 zone: h(d) = -depth + k·r1·(1 - √(1 - (d/r1)²)). Curvature h''(d) has a singularity at d=r1, capped at strainLimit/(thickness/2). For emboss (depth<0), exact mirror of indent.

## See also

- [IndentProfile.cpp](../../src/assembly/IndentProfile.cpp)
- [ClosedLoop.cpp](../../src/assembly/ClosedLoop.cpp)
