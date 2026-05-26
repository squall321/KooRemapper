# Module: src/validation/

| File | Role |
|------|------|
| [ElementQualityChecker.cpp](../../src/validation/ElementQualityChecker.cpp) | aspect ratio / Jacobian / warping |
| [IntersectionDetector.cpp](../../src/validation/IntersectionDetector.cpp) | self-intersection / overlap detection |
| [MaterialCardValidator.cpp](../../src/validation/MaterialCardValidator.cpp) | sanity-check `*MAT_*` field formatting |

## Thresholds (from [[commands/offset#offset — shell offset → solid extrusion (§22)]] integration)

| Metric | Warn | Error |
|--------|------|-------|
| Aspect ratio | > 10 | > 20 |
| Jacobian | < 0.1 | < -1e-10 (`MIN_JACOBIAN_ERROR`) |
| Warping | > 30° | > 45° |

Warping can hit 180° on mixed surfaces (top+side) — acceptable if Jacobian is good.

`MaterialCardValidator` enforces the [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]] (10-char
fixed-width).
